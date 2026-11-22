"""Contract tests without downloading models or claiming GPU execution."""
import importlib.util,json,unittest
from pathlib import Path
from unittest.mock import patch
import httpx

spec=importlib.util.spec_from_file_location('win_models',Path(__file__).with_name('models.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncio
        m.gate=asyncio.Lock();m.nmt_gate=asyncio.Lock()
        m.ready=True
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app),base_url='http://127.0.0.1:8790')
    async def asyncTearDown(self):await self.client.aclose()

    async def test_session_limit_reclaims_idle_sessions_across_many_restarts(self):
        import numpy as np
        from live_audio import LiveSession
        m.sessions.clear()
        with patch.object(m,'LiveSession',lambda *a,**kw:LiveSession(vad=lambda f:0)):
            for i in range(12):
                r=await self.client.post('/live/frame',content=np.zeros(512,dtype='<i2').tobytes(),headers={'X-Mosa-Session':f'idle-session-{i}','X-Mosa-Display':'original'})
                events=list(map(json.loads,r.text.splitlines()))
                self.assertEqual(events[-1]['type'],'batch_end',events)
                self.assertLessEqual(len(m.sessions),8)

    async def test_live_asr_applies_confidence_filter_and_returns_uncertainty(self):
        from types import SimpleNamespace
        import numpy as np
        segments=[SimpleNamespace(text='quiet speech',avg_logprob=-1.2,no_speech_prob=.05,compression_ratio=1),
                  SimpleNamespace(text=' hallucination',avg_logprob=-1.8,no_speech_prob=.5,compression_ratio=1)]
        fake=SimpleNamespace(transcribe=lambda *args,**kw:(segments,SimpleNamespace(language='en',language_probability=.8)))
        with patch.object(m,'model',fake):
            result=m.live_recognize(np.ones(8192))
        self.assertEqual(result['text'],'quiet speech');self.assertTrue(result['asr_uncertain'])

    async def test_live_asr_forwards_selected_language_to_whisper(self):
        from types import SimpleNamespace
        import numpy as np
        calls=[]
        fake=SimpleNamespace(transcribe=lambda *args,**kw:(calls.append(kw) or [],SimpleNamespace(language='en',language_probability=1.0)))
        with patch.object(m,'model',fake):
            m.live_recognize(np.ones(8192),0,'en')
        self.assertEqual(calls[0]['language'],'en')

    async def test_language_lock_header_reaches_live_asr(self):
        import numpy as np
        from live_audio import LiveSession
        calls=[]
        def recognize(audio,overlap_ms=0,language=None):
            calls.append(language)
            return dict(text='Locked language',language=language,language_probability=1.0,asr_uncertain=False)
        m.sessions.clear();m.sessions['language-lock-test']=LiveSession(vad=lambda frame:1.)
        with patch.object(m,'live_recognize',recognize):
            r=await self.client.post('/live/frame',content=(np.ones(8192)*10000).astype('<i2').tobytes(),headers={'X-Mosa-Session':'language-lock-test','X-Mosa-Flush':'1','X-Mosa-Display':'original','X-Mosa-ASR':'stream-en'})
        self.assertEqual(r.status_code,200);self.assertEqual(calls,['en'])

    async def test_low_confidence_source_is_flagged_and_not_retained_as_context(self):
        import numpy as np
        from live_audio import LiveSession
        m.sessions.clear()
        state=LiveSession(vad=lambda frame:1.);m.sessions['uncertain-test']=state
        def recognize(audio,overlap_ms=0):return dict(text='Possibly wrong',language='en',language_probability=.8,asr_uncertain=True)
        with patch.object(m,'live_recognize',recognize):
            r=await self.client.post('/live/frame',content=(np.ones(8192)*10000).astype('<i2').tobytes(),headers={'X-Mosa-Session':'uncertain-test','X-Mosa-Flush':'1','X-Mosa-Display':'original'})
        final=next(e for e in map(json.loads,r.text.splitlines()) if e['type']=='final')
        self.assertTrue(final['needs_human_review']);self.assertEqual(state.history,[])

    async def test_glossary_still_missing_after_repair_remains_flagged(self):
        import numpy as np
        from live_audio import LiveSession
        m.sessions.clear();m.sessions['glossary-test']=LiveSession(vad=lambda frame:1.)
        def recognize(audio,overlap_ms=0):return dict(text='ultimate',language='en',language_probability=.9)
        async def tokens(*args):yield '特殊能力'
        original_read=m.Path.read_text
        def read(path,*args,**kwargs):
            return '[{"ja":"ultimate","zh":"大絕"}]' if path.name=='glossary.json' else original_read(path,*args,**kwargs)
        with patch.object(m,'live_recognize',recognize),patch.object(m,'tokens',tokens),patch.object(m.Path,'read_text',read):
            r=await self.client.post('/live/frame',content=(np.ones(8192)*10000).astype('<i2').tobytes(),headers={'X-Mosa-Session':'glossary-test','X-Mosa-Flush':'1'})
        final=next(e for e in map(json.loads,r.text.splitlines()) if e['type']=='final')
        self.assertIn('missing_glossary_term',final['quality_flags']);self.assertTrue(final['needs_human_review'])

    async def test_next_batch_asr_runs_during_translation_and_context_stays_ordered(self):
        import asyncio,numpy as np
        from live_audio import LiveSession
        m.sessions.clear();m.batches=m.BatchCache()
        m.sessions['pipeline-test']=LiveSession(vad=lambda frame:1.)
        translating=asyncio.Event();second_asr=asyncio.Event();release=asyncio.Event()
        calls=[];contexts=[];loop=asyncio.get_running_loop()
        def recognize(audio,overlap_ms=0):
            calls.append(1)
            if len(calls)==2:loop.call_soon_threadsafe(second_asr.set)
            return dict(text='Alpha' if len(calls)==1 else 'Beta',language='en',language_probability=.9)
        async def translate(text,context,terms,draft=None):
            contexts.append(list(context))
            if text=='Alpha':translating.set();await release.wait()
            yield '甲' if text=='Alpha' else '乙'
        audio=(np.ones(8192)*10000).astype('<i2').tobytes()
        headers={'X-Mosa-Session':'pipeline-test','X-Mosa-Flush':'1'}
        async def send(number):
            return await self.client.post('/live/frame',content=audio,headers={**headers,'X-Mosa-Batch':str(number),'X-Mosa-Offset':str(number*8192)})
        with patch.object(m,'live_recognize',recognize),patch.object(m,'tokens',translate):
            first=asyncio.create_task(send(0));second=None
            try:
                await asyncio.wait_for(translating.wait(),2)
                second=asyncio.create_task(send(1))
                await asyncio.wait_for(second_asr.wait(),2)
                self.assertFalse(first.done(),'second ASR must finish before first translation')
            finally:
                release.set()
                responses=await asyncio.gather(first,*([second] if second else []))
        self.assertEqual(contexts,[[],['Alpha']])
        finals=[next(e for e in map(json.loads,r.text.splitlines()) if e['type']=='final') for r in responses]
        self.assertEqual([e['original'] for e in finals],['Alpha','Beta'])

    async def test_validation_and_origin(self):
        for body in ([],{'text':''},{'text':'こんにちは','review':'yes'},{'text':'あ','context':['a']*3}):
            self.assertEqual((await self.client.post('/translate-stream',json=body)).status_code,400)
        self.assertEqual((await self.client.get('/health',headers={'Origin':'https://evil.example'})).status_code,403)

    async def test_stream_review_and_fallback(self):
        calls=[]
        async def fake(text,context,terms,draft=None):
            calls.append((text,context,terms,draft))
            yield '这是一段';yield '字幕。'
        with patch.object(m,'tokens',fake):
            r=await self.client.post('/translate-stream',json={'text':'敵です','context':['前文'],'terms':[{'ja':'敵','zh':'敵人'},{'ja':'他','zh':'他'}],'review':True})
            events=[json.loads(s) for s in r.text.splitlines()]
            self.assertEqual(events[-1]['type'],'final');self.assertTrue(events[-1]['reviewed'])
            self.assertEqual(events[-1]['translation'],'這是一段字幕。')
            self.assertEqual(len(calls),2);self.assertEqual(len(calls[0][2]),1)
            self.assertEqual(calls[1][3],'這是一段字幕。')
            r=await self.client.post('/v1/chat/completions',json={'messages':[{'role':'user','content':'敵です'}]})
            self.assertEqual(r.json()['choices'][0]['message']['content'],'這是一段字幕。')

    async def test_stream_failure_not_final(self):
        async def broken(*args):
            yield '暫定字幕';raise RuntimeError('broken')
        with patch.object(m,'tokens',broken):
            r=await self.client.post('/translate-stream',json={'text':'あ'})
            events=[json.loads(s) for s in r.text.splitlines()]
            self.assertEqual(events[-1]['type'],'error')
            self.assertFalse(any(e['type']=='final' for e in events))

    async def test_real_ndjson_parser(self):
        original=httpx.AsyncClient
        for lines,fail in [([{'message':{'content':'譯文'}},{'done':True}],False),([{'message':{'content':'半句'}}],True),([{'error':'bad'}],True),([{'done':True,'done_reason':'length'}],True)]:
            transport=httpx.MockTransport(lambda r:httpx.Response(200,text='\n'.join(json.dumps(x) for x in lines)))
            with patch.object(m.httpx,'AsyncClient',lambda **kw:original(transport=transport,**kw)):
                if fail:
                    with self.assertRaises(RuntimeError):[t async for t in m.tokens('あ',[],[])]
                else:self.assertEqual([t async for t in m.tokens('あ',[],[])],['譯文'])

    async def test_asr_contract(self):
        from types import SimpleNamespace
        def detect(*args,**kw):
            self.assertIsNone(kw['language'])
            self.assertEqual(kw['task'],'transcribe')
            return [SimpleNamespace(text='Hello everyone',no_speech_prob=.01)],None
        fake=SimpleNamespace(transcribe=detect)
        with patch.object(m,'model',fake):
            r=await self.client.post('/v1/audio/transcriptions',files={'file':('test.wav',(m.ROOT/'web/test-ja.wav').read_bytes(),'audio/wav')})
            self.assertEqual(r.json(),{'text':'Hello everyone'})
        r=await self.client.post('/v1/audio/transcriptions',files={'file':('bad.wav',b'bad')})
        self.assertIn(r.status_code,(400,422))

    async def test_non_speech_skips_whisper(self):
        from unittest.mock import Mock
        fake=Mock()
        with patch.object(m,'model',fake),patch.object(m,'get_speech_timestamps',return_value=[]):
            self.assertEqual(m.recognize((m.ROOT/'web/test-ja.wav').read_bytes()),'')
        fake.transcribe.assert_not_called()

    async def test_korean_translation_and_reference_isolation(self):
        source='지금 공격하지 마세요.'
        messages=m.translation_messages(source,['앞 문장'],[{'ja':'공격','zh':'攻擊'}],draft='現在攻擊')
        self.assertEqual(messages[-1],{'role':'user','content':source})
        self.assertIn('앞 문장',messages[1]['content'])
        self.assertIn('現在攻擊',messages[1]['content'])
        self.assertNotIn('앞 문장',messages[-1]['content'])
        calls=[]
        async def fake(text,context,terms,draft=None):
            calls.append(text);yield '現在不要攻擊。'
        with patch.object(m,'tokens',fake):
            r=await self.client.post('/translate-stream',json={'text':source})
        self.assertEqual(calls,[source])
        self.assertEqual(json.loads(r.text.splitlines()[-1])['translation'],'現在不要攻擊。')

    async def test_live_validation_and_state(self):
        import numpy as np
        from live_audio import LiveSession
        async def fake_tokens(*args):
            raise AssertionError('Source-only must not call translation')
            yield ''
        def recognize(audio,overlap_ms=0):return dict(text='Hello everyone',language='en',language_probability=.9)
        m.sessions.clear()
        m.sessions['session-test']=LiveSession(vad=lambda frame:float(frame[0]>.1))
        headers={'X-Mosa-Session':'session-test','X-Mosa-Display':'original'}
        with patch.object(m,'live_recognize',recognize),patch.object(m,'tokens',fake_tokens):
            async def send(audio,flush=False):
                r=await self.client.post('/live/frame',content=audio.astype('<i2').tobytes(),
                                         headers={**headers,'X-Mosa-Flush':'1' if flush else '0'})
                return [json.loads(line) for line in r.text.splitlines()]
            a=await send(np.ones(512*48)*10000)
            self.assertEqual(a[0]['type'],'session');self.assertTrue(any(e.get('phase')=='asr' for e in a));self.assertEqual(a[-1]['type'],'batch_end')
            interim=await send(np.zeros(512*13))
            self.assertFalse(any(e['type']=='final' for e in interim))
            b=await send(np.zeros(512*15))
            final=next(e for e in b if e['type']=='final')
            self.assertEqual(final['seq'],0);self.assertTrue(final['source_only'])
            self.assertEqual(final['translation'],'')
        self.assertEqual((await self.client.post('/live/frame',content=b'bad',headers=headers)).status_code,400)
        self.assertEqual((await self.client.post('/live/frame',content=b'')).status_code,400)
        self.assertEqual((await self.client.post('/live/frame',content=bytes(128002),headers=headers)).status_code,413)

    async def test_live_negation_repair_is_bounded_and_flags_unresolved_translation(self):
        import numpy as np
        from live_audio import LiveSession
        for repair,expected_flag in [('現在不要攻擊。',False),('現在攻擊。',True)]:
            m.sessions.clear()
            m.sessions['repair-test']=LiveSession(vad=lambda f:1.)
            calls=[]
            async def fake_tokens(text,context,terms,draft=None):
                calls.append(draft);yield repair if draft is not None else '現在攻擊。'
            def recognize(audio,overlap_ms=0):return dict(text='Do not attack.',language='en',language_probability=.9)
            with patch.object(m,'tokens',fake_tokens),patch.object(m,'live_recognize',recognize):
                result=await self.client.post('/live/frame',content=(np.ones(16000)*10000).astype('<i2').tobytes(),
                    headers={'X-Mosa-Session':'repair-test','X-Mosa-Flush':'1'})
            final=next(e for e in map(json.loads,result.text.splitlines()) if e['type']=='final')
            self.assertEqual(len(calls),2)
            self.assertTrue(final['quality_repair_attempted'])
            self.assertEqual(final['needs_human_review'],expected_flag)

    async def test_batch_replay_and_missing_session_offset(self):
        import numpy as np
        from live_audio import LiveSession
        m.sessions.clear();m.batches=m.BatchCache()
        state=LiveSession(vad=lambda frame:0.0)
        m.sessions['replay-test']=state
        headers={'X-Mosa-Session':'replay-test','X-Mosa-Batch':'0','X-Mosa-Offset':'0','X-Mosa-Display':'original'}
        payload=np.zeros(5120,dtype='<i2').tobytes()
        first=await self.client.post('/live/frame',content=payload,headers=headers)
        second=await self.client.post('/live/frame',content=payload,headers=headers)
        self.assertEqual(first.text,second.text)
        self.assertEqual(state.offset,5120)
        changed=await self.client.post('/live/frame',content=payload+b'\x00\x00',headers=headers)
        self.assertEqual(changed.status_code,409)
        m.sessions.clear()
        missing=await self.client.post('/live/frame',content=payload,headers={**headers,'X-Mosa-Batch':'1','X-Mosa-Offset':'5120'})
        self.assertEqual(json.loads(missing.text)['code'],'session_lost')

    async def test_untranslated_detection_and_glossary_case(self):
        terms=[{'ja':'ultimate','zh':'大絕'}]
        self.assertEqual(m.apply_terms('請不要使用Ultimate','Do not use your Ultimate',terms),'請不要使用大絕')
        self.assertEqual(m.apply_terms('ultimately','ultimate',terms),'ultimately')
        self.assertTrue(m.needs_repair('現在everyone都到了','Now everyone is here'))
        self.assertFalse(m.needs_repair('OpenAI 已就緒','OpenAI is ready'))
        self.assertEqual(m.validate({'text':'Ultimate','terms':terms})[2],terms)

if __name__=='__main__':unittest.main()
