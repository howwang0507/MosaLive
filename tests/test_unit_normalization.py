"""Offline-only scorer regression tests; no service or model imports."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'windows'))
import score_eval as score


class UnitNormalizationTests(unittest.TestCase):
    def test_common_units(self):
        for left, right in [('12 km', 'twelve kilometers'), ('5 kg', 'five kilograms'),
                            ('2.4GHz', '2.4 gigahertz'), ('30%', 'thirty percent'),
                            ('2 kilometres', '2 KM'), ('1 kilogram', 'one kg')]:
            with self.subTest(left=left):
                self.assertEqual(score.tokens(left, True), score.tokens(right, True))

    def test_raw_tokens_stay_literal(self):
        self.assertEqual(score.tokens('12 km 5 kg 2.4GHz 30%', False),
                         ['12', 'km', '5', 'kg', '2.4', 'ghz', '30'])
        self.assertGreater(score.wer('12 kilometers', '12 km', False), 0)

    def test_units_do_not_change_values_or_other_words(self):
        for left, right in [('3 kg', '30 kg'), ('-3 km', '3 km'),
                            ('2.4 GHz', '24 GHz'), ('3 kg', '3 km'),
                            ('kilograms', 'kilogramson'), ('ghz', 'ghc')]:
            with self.subTest(left=left):
                self.assertNotEqual(score.tokens(left, True), score.tokens(right, True))


if __name__ == '__main__':
    unittest.main()
