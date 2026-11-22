import asyncio,unittest
from fastapi import HTTPException
from quality_checks import quality_flags,TranslationCache,preview_has_progress,assess_segment,static_prompt
from reliable_batches import BatchCache

class QualityRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_chat_hint_preserves_names_and_ordinary_conversation(self):
        from quality_checks import livestream_translation_hint
        for text in ['Chat, what do you think?', 'Thank you, CHAT!', "Let's chat after dinner."]:
            hint=livestream_translation_hint(text)
            self.assertIn('聊天室',hint)
            self.assertIn('ordinary conversation',hint)
            self.assertIn('Chad is a distinct person name',hint)
        for text in ['Chad is my friend.', 'I use Snapchat.', 'The cathedral is beautiful.']:
            self.assertEqual(livestream_translation_hint(text),'')
    def test_uncertain_speech_is_retained_but_hallucination_is_rejected(self):
        from types import SimpleNamespace
        self.assertEqual(assess_segment(SimpleNamespace(avg_logprob=-1.2,no_speech_prob=.05)),(True,True))
        self.assertFalse(assess_segment(SimpleNamespace(avg_logprob=-1.8,no_speech_prob=.5))[0])
        self.assertFalse(assess_segment(SimpleNamespace(compression_ratio=3))[0])
        self.assertEqual(static_prompt(['OpenAI','OpenAI','  MosaSub  ']),'OpenAI, MosaSub')
        self.assertLessEqual(len(static_prompt(['term'+str(i) for i in range(100)])),200)
        self.assertIn('missing_glossary_term',quality_flags('ultimate','特殊能力',terms=[{'ja':'ultimate','zh':'大絕'}]))
    async def test_explicit_playback_reset_cancels_only_obsolete_work(self):
        cache=BatchCache();started=asyncio.Event();release=asyncio.Event()
        async def slow():
            started.set();await release.wait();yield 'obsolete\n'
        old=cache.start(('old','0'),b'a',(),slow)
        await started.wait()
        await cache.cancel_sessions(['old'])
        self.assertTrue(old['done']);self.assertTrue(old['task'].cancelled())
        self.assertEqual([line async for line in cache.stream(old)],[])
        async def fresh():yield 'current\n'
        new=cache.start(('new','0'),b'b',(),fresh)
        self.assertEqual([line async for line in cache.stream(new)],['current\n'])
    def test_preview_batches_small_additions_but_allows_corrections(self):
        self.assertFalse(preview_has_progress('Wait here now','Wait here'))
        self.assertFalse(preview_has_progress('Wait here','Wait here'))
        self.assertTrue(preview_has_progress('Do not attack','Do attack'))
        self.assertTrue(preview_has_progress('Wait here.','Wait here'))
        self.assertTrue(preview_has_progress('Wait here until everyone arrives','Wait here'))
    def test_numbers_negation_and_cache_isolation(self):
        self.assertEqual(quality_flags('Wait ten seconds.','等十秒。','en'),[])
        self.assertEqual(quality_flags('あと10秒待ってください','請再等10秒。','ja'),[])
        self.assertIn('number_mismatch',quality_flags('Wait ten seconds.','等二十秒。','en'))
        self.assertIn('possible_missing_negation',quality_flags('Do not attack.','現在攻擊。','en'))
        self.assertIn('possible_missing_negation',quality_flags('지금 공격하지 마세요.','現在攻擊。','ko'))
        self.assertEqual(quality_flags('まだ攻撃しないで。','先不要攻擊。','ja'),[])
        cache=TranslationCache(2);cache.put(('hello','context-a'),'你好')
        self.assertIsNone(cache.get(('hello','context-b')))
        cache.put('b','B');cache.put('c','C')
        self.assertIsNone(cache.get(('hello','context-a')))

    async def test_replay_continues_when_reader_leaves(self):
        cache=BatchCache();release=asyncio.Event();calls=[]
        async def produce():
            calls.append(1);yield 'partial\n';await release.wait();yield 'final\n'
        entry=cache.start(('session','0'),b'a',('fast',),produce)
        reader=cache.stream(entry)
        self.assertEqual(await anext(reader),'partial\n');await reader.aclose()
        release.set();await entry['task']
        retry=cache.start(('session','0'),b'a',('fast',),produce)
        self.assertEqual([line async for line in cache.stream(retry)],['partial\n','final\n'])
        self.assertEqual(len(calls),1)
        with self.assertRaises(HTTPException):cache.start(('session','0'),b'changed',('fast',),produce)

if __name__=='__main__':unittest.main()
