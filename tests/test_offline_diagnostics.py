import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'windows'))
import diagnose_errors as diagnose


def segment(source='Alice has three cats', start=0, end=1000, translation='愛麗絲有三隻貓'):
    return dict(source=source, start_ms=start, end_ms=end, reference_zh_tw=translation)


def final(seq, text, translation='', start=0, end=1000):
    return dict(type='final', seq=seq, original=text, translation=translation,
                speech_start_ms=start, speech_end_ms=end)


class OfflineDiagnosticTests(unittest.TestCase):
    def test_deletion_insertion_substitution_and_empty_inputs(self):
        for reference, hypothesis, expected in [(['a', 'b'], ['a'], 'D'),
                                                (['a'], ['a', 'b'], 'I'),
                                                (['a'], ['b'], 'S')]:
            self.assertIn(expected, [op for op, _, _ in diagnose.align_words(reference, hypothesis)])
        self.assertEqual(diagnose.align_words([], []), [])
        self.assertEqual(diagnose.align_words([], ['a']), [('I', None, 0)])

    def test_number_proper_noun_and_interior_categories(self):
        result = diagnose.word_errors(
            [segment('We saw Alice carrying 3 very large cats near home')],
            [final(1, 'We saw Alex carrying 4 very large cats near houses')])
        self.assertEqual(result['operations']['S'], 3)
        self.assertEqual(result['categories']['number'], 1)
        self.assertEqual(result['categories']['proper_noun'], 1)
        self.assertEqual(result['locations']['interior'], 2)
        self.assertEqual(result['locations']['boundary'], 1)

    def test_deletion_without_anchor_is_unknown(self):
        result = diagnose.word_errors([segment('hello')], [])
        self.assertEqual(result['locations'], {'unknown': 1})

    def test_translation_exact_and_one_error_are_separate(self):
        refs = [segment('Alice has three cats')]
        exact = diagnose.translation_subset(refs, [final(1, 'Alice has three cats', '愛麗絲有三隻貓')])
        one = diagnose.translation_subset(refs, [final(1, 'Alice has three dogs', '愛麗絲有三隻狗')])
        bad = diagnose.translation_subset(refs, [final(1, 'Alex has three dogs', '愛麗絲有三隻狗')])
        self.assertEqual((exact['exact'], exact['rows'][0]['chrf']), (1, 100))
        self.assertEqual(one['one_error'], 1)
        self.assertEqual(bad['selected'], 0)

    def test_split_caption_allowed_cross_reference_caption_excluded(self):
        refs = [segment('hello world', translation='你好世界')]
        split = [final(1, 'hello', '你好', end=500), final(2, 'world', '世界', start=500)]
        self.assertEqual(diagnose.translation_subset(refs, split)['selected'], 1)
        refs = [segment('hello', end=500), segment('world', start=500)]
        merged = diagnose.translation_subset(refs, [final(1, 'hello world', '你好世界')])
        self.assertEqual(merged['selected'], 0)
        self.assertEqual(merged['excluded']['caption_spans_multiple_references'], 2)

    def test_audio_must_overlap_and_translation_must_exist(self):
        self.assertEqual(diagnose.translation_subset([segment('hello')], [final(1, 'hello', '你好', start=1000, end=2000)])['selected'], 0)
        self.assertEqual(diagnose.translation_subset([segment('hello')], [final(1, 'hello')])['selected'], 0)

    def test_observed_retraction_and_appended_tail_distance(self):
        events = [dict(type='partial', phase='asr', seq=1, stable_original=text) for text in ['hello', '', 'hello world']]
        events.append(dict(type='partial', phase='stable', seq=1, original='hello', stable_original='hello', translation='你好'))
        result = diagnose.agreement_shadow(events, [final(1, 'hello world', '你好世界')])
        self.assertEqual(result['observed_retractions'], 1)
        self.assertEqual(result['pairs'][0]['edit_distance'], 2)
        self.assertTrue(result['pairs'][0]['final_starts_with_preview'])

    def test_utf8_reference_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'reference.json'
            path.write_text(json.dumps({'中文': '參考'}, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(diagnose.read_json(path), {'中文': '參考'})

    def test_multi_run_cli_utf8_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref = root / 'reference.json'
            ref.write_text(json.dumps({'segments': [segment('hello', translation='你好')]}), encoding='utf-8')
            paths = [root / 'A.json', root / 'B.json']
            for path in paths:
                path.write_text(json.dumps({'results': [{'id': 'sample', 'events': [final(1, 'hello', '你好')]}]}, ensure_ascii=False), encoding='utf-8')
            output = root / 'out.json'
            args = ['diagnose_errors.py', *map(str, paths), '--reference', str(ref), '--save', str(output)]
            with patch.object(sys, 'argv', args), redirect_stdout(io.StringIO()):
                diagnose.main()
            self.assertEqual(set(diagnose.read_json(output)['reports']), {'A:sample', 'B:sample'})
            before = output.read_bytes()
            with patch.object(sys, 'argv', args), self.assertRaises(SystemExit):
                diagnose.main()
            self.assertEqual(output.read_bytes(), before)

    def test_discontinuous_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'ref.json').write_text('{"segments": []}', encoding='utf-8')
            for key in ['reconnects', 'dropped_audio_ms', 'playback_reset_count', 'overflow_count']:
                (root / 'run.json').write_text(json.dumps({'results': [{'id': 's', 'metrics': {key: 1}}]}), encoding='utf-8')
                args = ['diagnose_errors.py', str(root / 'run.json'), '--reference', str(root / 'ref.json'), '--save', str(root / 'new.json')]
                with patch.object(sys, 'argv', args), self.assertRaises(SystemExit):
                    diagnose.main()
                self.assertFalse((root / 'new.json').exists())


if __name__ == '__main__':
    unittest.main()
