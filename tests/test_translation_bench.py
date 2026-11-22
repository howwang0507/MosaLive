"""Offline tests for translation_bench; Ollama and models.py are stubbed."""
import json,sys,tempfile,types,unittest
from unittest import mock
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import translation_bench as tb

SYSTEM='You translate. '+tb.ACRONYM_CLAUSE+' Output only the translation.'
stub=types.ModuleType('models')
stub.translation_messages=lambda text,context,terms,draft=None:[{'role':'system','content':SYSTEM},{'role':'user','content':text}]

class BenchTests(unittest.TestCase):
    def test_variants_change_one_thing(self):
        base=stub.translation_messages('hi',[],[])
        self.assertEqual(tb.apply_variant(base,'baseline'),base)
        caps=tb.apply_variant(base,'caps_rule')
        self.assertTrue(caps[0]['content'].startswith(SYSTEM) and 'ALL CAPS' in caps[0]['content'])
        reword=tb.apply_variant(base,'acronym_reword')
        self.assertNotIn(tb.ACRONYM_CLAUSE,reword[0]['content']);self.assertIn('NASA',reword[0]['content'])
        self.assertEqual(base[0]['content'],SYSTEM)  # input not mutated
        self.assertEqual(caps[1],base[1])

    def test_missing_clause_raises(self):
        with self.assertRaises(ValueError):tb.apply_variant([{'role':'system','content':'other'}],'acronym_reword')
        with self.assertRaises(ValueError):tb.apply_variant([{'role':'system','content':SYSTEM}],'nope')

    def test_run_and_summary(self):
        segs=[{'source':'Aerosmith cancelled their tour.','reference_zh_tw':'Aerosmith 取消了巡迴演唱會。'},
              {'source':'I will not go.','reference_zh_tw':'我不會去。'}]
        def fake(messages):
            src=messages[-1]['content'];caps='ALL CAPS' in messages[0]['content']
            zh={'Aerosmith cancelled their tour.':'Aerosmith 取消了巡迴演唱會。' if caps else 'Aerosmith 取消了 TOUR。',
                'I will not go.':'我會去。'}[src]
            return dict(text=zh,done_reason='stop',eval_tokens=5,wall_ms=100.0)
        with mock.patch.dict(sys.modules, {'models': stub}):
            rows=tb.run(segs,['baseline','caps_rule'],2,fake)
        self.assertEqual(len(rows),8)
        s=tb.summarize(rows)
        self.assertEqual(s['baseline']['counts']['uppercased_source_word'],2)
        self.assertNotIn('uppercased_source_word',s['caps_rule']['counts'])
        self.assertEqual(s['baseline']['counts']['possible_missing_negation'],2)
        self.assertEqual(s['caps_rule']['calls'],4)

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            ref=Path(d)/'r.json';ref.write_text(json.dumps({'segments':[]}),encoding='utf-8')
            with self.assertRaises(SystemExit):tb.main(['--reference',str(ref),'--out',d])

if __name__=='__main__':unittest.main()
