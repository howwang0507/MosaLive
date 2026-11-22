import json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import numpy as np

SPEECH=(np.ones(16000)*10000).astype('<i2').tobytes()       # 1.0 s of speech
# The worklet sends 320 ms chunks, so the 416 ms pause preview and the 896 ms final arrive in different batches.
CHUNK=5120*2
SILENCE=[np.zeros(5120,dtype='<i2').tobytes()]*4
TEXT='We should wait for the team.'

def energy_vad(frame):return 1. if np.abs(frame).max()>.01 else 0.

async def run_turn(speculative,chunks=(SPEECH,*SILENCE)):
    import asyncio,httpx,models as m
    from live_audio import LiveSession
    state=LiveSession(vad=energy_vad);asr_calls=[];nmt_calls=[]
    def recognize(*args):
        asr_calls.append(1);return dict(text=TEXT,language='en',language_probability=.99)
    async def translate(*args):
        nmt_calls.append(args[0]);yield '我們應該等隊友。'
    events=[]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app),base_url='http://127.0.0.1:8790') as client:
        with patch.object(m,'ready',True),patch.object(m,'gate',asyncio.Lock()),patch.object(m,'nmt_gate',asyncio.Lock()),\
             patch.object(m,'sessions',{'speculative-test':state}),patch.object(m,'SPECULATIVE_FINAL',speculative),\
             patch.object(m,'read_json_cached',lambda path:[]),patch.object(m,'live_recognize',recognize),patch.object(m,'tokens',translate):
            for chunk in chunks:
                response=await client.post('/live/frame',content=chunk,headers={'X-Mosa-Session':'speculative-test','X-Mosa-ASR':'stream-en'})
                events+=[json.loads(line) for line in response.text.splitlines() if line]
    finals=[e for e in events if e['type']=='final']
    return finals,events,len(asr_calls),nmt_calls

class SpeculativeFinalTests(unittest.IsolatedAsyncioTestCase):
    async def test_unchanged_pause_reuses_asr_and_translation(self):
        finals,events,asr,nmt=await run_turn(True)
        self.assertEqual(len(finals),1)
        self.assertEqual(finals[0]['translation'],'我們應該等隊友。')
        self.assertTrue(finals[0]['asr_reused_from_pause']);self.assertTrue(finals[0]['speculative_translation_reused'])
        self.assertEqual(asr,2)          # periodic preview + pause preview; the final does not re-run ASR
        self.assertEqual(nmt,[TEXT])     # one translation, made at the pause and reused by the final
        self.assertTrue(any(e['type']=='partial' and e.get('phase')=='stable' and e.get('translation') for e in events))

    async def test_disabled_keeps_previous_behaviour_and_same_output(self):
        finals,_,asr,nmt=await run_turn(False)
        self.assertEqual(len(finals),1)
        self.assertEqual(finals[0]['translation'],'我們應該等隊友。')
        self.assertNotIn('asr_reused_from_pause',finals[0])
        self.assertEqual(asr,3);self.assertEqual(nmt,[TEXT])

    async def test_disabled_does_not_count_ordinary_preview_as_speculation(self):
        import models as m
        with patch.dict(m.METRICS,dict(speculative_translations=0,speculative_translation_reused=0,speculative_asr_reused=0)):
            finals,_,_,_=await run_turn(False)
            self.assertNotIn('speculative_translation_reused',finals[0])
            self.assertEqual(m.METRICS.get('speculative_translations',0),0)
            self.assertEqual(m.METRICS.get('speculative_translation_reused',0),0)

    async def test_existing_preview_without_pause_speculation_is_not_a_hit(self):
        import models as m
        speech=SPEECH*3
        chunks=tuple(speech[i:i+CHUNK] for i in range(0,len(speech),CHUNK))+tuple(SILENCE)
        with patch.dict(m.METRICS,dict(speculative_translations=0,speculative_translation_reused=0,speculative_asr_reused=0)):
            finals,events,_,_=await run_turn(True,chunks)
            self.assertTrue(any(e.get('phase')=='stable' for e in events))
            self.assertEqual(m.METRICS.get('speculative_translations',0),0)
            self.assertNotIn('speculative_translation_reused',finals[0])
            self.assertEqual(m.METRICS.get('speculative_translation_reused',0),0)

class PauseKeyTests(unittest.TestCase):
    def frames(self,state,samples):
        return state.push(np.frombuffer(samples,dtype='<i2').astype(np.float32)/32768)

    def test_final_carries_pause_key_only_when_no_speech_followed(self):
        from live_audio import LiveSession
        quiet=LiveSession(vad=energy_vad);self.frames(quiet,SPEECH)
        jobs=[job for chunk in SILENCE for job in self.frames(quiet,chunk)]
        preview,final=[j for j in jobs if not j['final']][-1],[j for j in jobs if j['final']][0]
        self.assertEqual(preview['silence_ms'],416);self.assertEqual(final['pause_key'],preview['pause_key'])

        resumed=LiveSession(vad=energy_vad);self.frames(resumed,SPEECH)
        jobs=[job for chunk in SILENCE[:2] for job in self.frames(resumed,chunk)]   # 640 ms: pause preview, no endpoint
        self.assertTrue(any(j.get('pause_key') for j in jobs if not j['final']))
        jobs=self.frames(resumed,SPEECH[:6400])+[job for chunk in SILENCE for job in self.frames(resumed,chunk)]
        final=[j for j in jobs if j['final']][0]
        later_preview=[j for j in jobs if not j['final'] and j.get('pause_key')][-1]
        self.assertEqual(final['pause_key'],later_preview['pause_key'])  # stale key from the first pause is never reused

    def test_hard_limit_never_reuses(self):
        from live_audio import LiveSession,MAX_SEGMENT_FRAMES
        state=LiveSession(vad=energy_vad)
        jobs=self.frames(state,(np.ones(MAX_SEGMENT_FRAMES*512+512)*10000).astype('<i2').tobytes())
        final=[j for j in jobs if j['final']][0]
        self.assertEqual(final['endpoint_reason'],'continuous_limit');self.assertNotIn('pause_key',final)

class SettingTests(unittest.TestCase):
    def test_defaults_and_validation(self):
        from live_audio import env_ms,MAX_SEGMENT_FRAMES,PAUSE_FRAMES
        self.assertEqual((MAX_SEGMENT_FRAMES,PAUSE_FRAMES),(188,28))
        with patch.dict(os.environ,{'X_MS':'4000'}):self.assertEqual(env_ms('X_MS',1,2000,10000),4000)
        for bad in ('fast','1500','20000'):
            with patch.dict(os.environ,{'X_MS':bad}),self.assertRaises(ValueError):env_ms('X_MS',1,2000,10000)

if __name__=='__main__':unittest.main()
