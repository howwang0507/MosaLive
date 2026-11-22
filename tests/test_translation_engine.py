import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import models as m

class TranslationEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_delegates_without_changing_arguments_or_chunks(self):
        calls=[]
        async def fake(*args):calls.append(args);yield '第一';yield '段'
        with patch.object(m,'ollama_tokens',fake):
            engine=m.create_translator('ollama')
            self.assertEqual([x async for x in engine.tokens('source',['context'],[],'draft')],['第一','段'])
        self.assertEqual(calls,[('source',['context'],[],'draft')])

    async def test_reserved_engine_fails_explicitly(self):
        engine=m.create_translator('ctranslate2')
        with self.assertRaisesRegex(NotImplementedError,'not implemented'):engine.validate_configuration()
        with self.assertRaises(NotImplementedError):[x async for x in engine.tokens('source',[],[])]
        with self.assertRaises(ValueError):m.create_translator('typo')

    async def test_live_history_is_bounded_and_reset_discards_session(self):
        import asyncio,json,httpx,numpy as np
        from live_audio import LiveSession
        m.ready=True;m.gate=asyncio.Lock();m.nmt_gate=asyncio.Lock();m.sessions.clear()
        state=LiveSession(vad=lambda frame:1.)
        m.sessions['history-test']=state
        utterances=['Alpha','Bravo','Charlie','Delta','Echo','Foxtrot','Golf','Hotel','India','Juliet','Kilo','Lima']
        audio=(np.ones(8192)*10000).astype('<i2').tobytes()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app),base_url='http://127.0.0.1:8790') as client:
            for text in utterances:
                with patch.object(m,'live_recognize',lambda *a:dict(text=text,language='en',language_probability=.99)):
                    response=await client.post('/live/frame',content=audio,headers={'X-Mosa-Session':'history-test','X-Mosa-Flush':'1','X-Mosa-Display':'original'})
                self.assertTrue(any(e['type']=='final' for e in map(json.loads,response.text.splitlines())),response.text)
            self.assertEqual(state.recent_transcripts.maxlen,10)
            self.assertEqual(list(state.recent_transcripts),utterances[-10:])
            with patch.object(m,'LiveSession',lambda *a,**kw:LiveSession(vad=lambda frame:0.)):
                response=await client.post('/live/frame',content=b'',headers={'X-Mosa-Session':'fresh-session','X-Mosa-Supersedes':'history-test','X-Mosa-Flush':'1','X-Mosa-Batch':'0','X-Mosa-Offset':'0'})
            self.assertNotIn('history-test',m.sessions)
            self.assertEqual(list(m.sessions['fresh-session'].recent_transcripts),[])
            self.assertEqual(m.sessions['fresh-session'].history,[])
            self.assertFalse(any(e['type']=='final' for e in map(json.loads,response.text.splitlines())))

if __name__=='__main__':unittest.main()
