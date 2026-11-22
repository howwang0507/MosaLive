import importlib,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import numpy as np
import live_audio
from live_audio import LiveSession,FRAME

def vad(frame):return 1. if np.abs(frame).max()>.01 else 0.
def speech(frames):return np.full(frames*FRAME,.3,np.float32)
def silence(frames):return np.zeros(frames*FRAME,np.float32)

def feed(state,*parts):
    """Send audio in 320 ms batches like the extension and collect final jobs."""
    audio=np.concatenate(parts);jobs=[]
    for i in range(0,len(audio),5120):jobs+=state.push(audio[i:i+5120])
    return [j for j in jobs if j['final']]

class BreathCutTests(unittest.TestCase):
    def setUp(self):
        enabled=patch.object(live_audio,'BREATH_CUT',True);enabled.start();self.addCleanup(enabled.stop)

    def test_off_by_default(self):
        self.addCleanup(importlib.reload,live_audio)
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop('MOSA_BREATH_CUT',None);importlib.reload(live_audio)
            self.assertFalse(live_audio.BREATH_CUT)
            finals=feed(live_audio.LiveSession(vad=vad),speech(160),silence(5),speech(60))
        self.assertEqual(finals[0]['endpoint_reason'],'continuous_limit')

    def test_hard_limit_cuts_at_last_breath_without_losing_audio(self):
        state=LiveSession(vad=vad)
        finals=feed(state,speech(160),silence(5),speech(60),silence(40))
        self.assertEqual([f['endpoint_reason'] for f in finals],['breath_cut','silence'])
        first,second=finals
        # The cut lands inside the 5-frame breath (frames 160-164), not at the 188-frame limit.
        self.assertTrue(160*32<=first['speech_end_ms']<=165*32,first['speech_end_ms'])
        self.assertEqual(first['commit_samples'],round(first['speech_end_ms']*16))
        # The next caption starts exactly where the first one stopped: no gap, no duplicated audio.
        self.assertEqual(second['speech_start_ms'],first['speech_end_ms'])
        self.assertEqual(second['overlap_ms'],0)
        self.assertEqual(len(first['audio']),round(first['speech_end_ms']*16))
        self.assertEqual(second['seq'],first['seq']+1)

    def test_continuous_speech_without_breath_keeps_plain_hard_cut(self):
        state=LiveSession(vad=vad)
        finals=feed(state,speech(200),silence(40))
        self.assertEqual(finals[0]['endpoint_reason'],'continuous_limit')
        self.assertGreater(finals[1]['overlap_ms'],0)   # existing overlap de-duplication path

    def test_breath_cut_can_be_disabled(self):
        with patch.object(live_audio,'BREATH_CUT',False):
            finals=feed(LiveSession(vad=vad),speech(160),silence(5),speech(60))
        self.assertEqual(finals[0]['endpoint_reason'],'continuous_limit')

    def test_breath_outside_lookback_is_ignored(self):
        finals=feed(LiveSession(vad=vad),speech(100),silence(5),speech(100))
        self.assertEqual(finals[0]['endpoint_reason'],'continuous_limit')

class SoftCutTests(unittest.TestCase):
    def test_off_by_default(self):
        self.assertEqual(live_audio.SOFT_CUT_FRAMES,0)
        finals=feed(LiveSession(vad=vad),speech(120),silence(7),speech(20),silence(40))
        self.assertEqual([f['endpoint_reason'] for f in finals],['silence'])

    def test_long_turn_finalizes_on_short_breath(self):
        with patch.object(live_audio,'SOFT_CUT_FRAMES',110),patch.object(live_audio,'SOFT_PAUSE_FRAMES',6):
            state=LiveSession(vad=vad)
            early=feed(state,speech(60),silence(7),speech(60))      # breath before 3.5 s: no cut
            self.assertEqual(early,[])
            finals=feed(state,silence(7),speech(30),silence(40))
        self.assertEqual([f['endpoint_reason'] for f in finals],['soft_pause','silence'])
        self.assertLess(finals[0]['speech_end_ms'],finals[1]['speech_start_ms'])

    def test_soft_cut_validation(self):
        for value in ('1000','abc'):
            with patch.dict(os.environ,{'MOSA_SOFT_CUT_MS':value}),self.assertRaises(ValueError):importlib.reload(live_audio)
        importlib.reload(live_audio)

if __name__=='__main__':unittest.main()

class ServicePathTests(unittest.IsolatedAsyncioTestCase):
    async def test_breath_cut_produces_two_translated_finals_through_the_service(self):
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from test_speculative_final import run_turn
        audio=(np.concatenate([speech(160),silence(5),speech(60),silence(40)])*32768).astype('<i2').tobytes()
        chunks=[audio[i:i+10240] for i in range(0,len(audio),10240)]
        with patch.object(live_audio,'BREATH_CUT',True):finals,events,_,_=await run_turn(True,chunks)
        self.assertEqual([f['endpoint_reason'] for f in finals],['breath_cut','silence'])
        self.assertTrue(all(f['translation'] for f in finals))
        self.assertFalse([e for e in events if e['type']=='error'])
