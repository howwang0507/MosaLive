import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
from quality_checks import sanitize_prompt,has_repeating_ngrams,assess_segment,static_prompt

class PromptGuardTests(unittest.TestCase):
    def test_normal_source_reference_is_allowed(self):
        self.assertEqual(sanitize_prompt('We should go to Tokyo.',[]),'We should go to Tokyo.')
        self.assertEqual(sanitize_prompt('東京に行きましょう。',['今日は晴れです。']),'東京に行きましょう。')

    def test_cross_round_copy_is_rejected(self):
        self.assertEqual(sanitize_prompt('We should go to Tokyo!',['We should go to Tokyo.']),'')
        self.assertEqual(sanitize_prompt('지금은 서울로 이동하고 있어요',['지금은 서울로 이동하고 있어요.']),'')

    def test_loops_and_music_cannot_enter_context(self):
        for text in ['♪ ♪ ♪','...!!!','go home go home go home','ありがとうありがとうありがとう','[Music]','Thanks for watching!']:
            self.assertEqual(sanitize_prompt(text,[]),'',text)
        self.assertTrue(has_repeating_ngrams('go home go home go home'))

    def test_real_signoff_stays_visible_but_weak_music_is_rejected(self):
        self.assertTrue(assess_segment(SimpleNamespace(text='Thanks for watching!',no_speech_prob=.01,avg_logprob=-.1))[0])
        self.assertFalse(assess_segment(SimpleNamespace(text='Thanks for watching!',no_speech_prob=.5,avg_logprob=-1.1))[0])
        self.assertFalse(assess_segment(SimpleNamespace(text='♪ ♪'))[0])

    def test_limits_and_static_terms(self):
        self.assertLessEqual(len(sanitize_prompt('a unique long sentence '*100,[])),300)
        self.assertEqual(static_prompt(['Tokyo','MosaSub']),'Tokyo, MosaSub')
        self.assertEqual(sanitize_prompt('We should go to Tokyo.',['We should go to Tokyo.']+['other']*10),'We should go to Tokyo.')

if __name__=='__main__':unittest.main()
