import unittest
import numpy as np
from live_audio import LiveSession,Agreement,FRAME,RATE

class LiveTests(unittest.TestCase):
    def test_adaptive_requires_stable_sentence_and_resumed_speech_revokes_hint(self):
        def state():
            s=LiveSession(vad=lambda f:float(f[0]>.1),endpoint_mode='adaptive')
            s.push(np.ones(FRAME*48,np.float32));s.push(np.zeros(FRAME*13,np.float32));return s
        for text,stable,uncertain in [('Please wait here.','Please wait',False),('Please wait here.','Please wait here.',True),('Please wait here','Please wait here',False)]:
            s=state();s.consider_endpoint(s.seq,text,stable,uncertain,416)
            self.assertFalse(any(j['final'] for j in s.push(np.zeros(FRAME*5,np.float32))))
        s=state();s.consider_endpoint(s.seq,'Please wait here.','Please wait here.',False,416)
        jobs=s.push(np.zeros(FRAME*5,np.float32))
        self.assertTrue(jobs[-1]['final']);self.assertEqual(jobs[-1]['endpoint_silence_ms'],576)
        s=state();s.consider_endpoint(s.seq,'Please wait here.','Please wait here.',False,416)
        s.push(np.ones(FRAME,np.float32))
        self.assertFalse(any(j['final'] for j in s.push(np.zeros(FRAME*18,np.float32))))
        self.assertTrue(s.push(np.zeros(FRAME*7,np.float32))[-1]['final'])

    def test_late_confirmation_finalizes_current_silence_without_waiting_for_next_packet(self):
        s=LiveSession(vad=lambda f:float(f[0]>.1),endpoint_mode='adaptive')
        s.push(np.ones(FRAME*48,np.float32));s.push(np.zeros(FRAME*20,np.float32))
        job=s.consider_endpoint(s.seq,'Please wait here.','Please wait here.',False,416,(48+13)*32)
        self.assertTrue(job['final']);self.assertEqual(job['endpoint_silence_ms'],640)
        self.assertEqual(job['speech_end_ms'],48*32)
        self.assertEqual(s.push(np.zeros(FRAME,np.float32)),[])
    def test_real_neural_vad_rejects_silence_and_tone(self):
        for audio in (np.zeros(RATE*4,np.float32),
                      (.1*np.sin(np.arange(RATE*4)*2*np.pi*440/RATE)).astype(np.float32)):
            state=LiveSession()
            jobs=[]
            for i in range(0,len(audio),7680):jobs.extend(state.push(audio[i:i+7680]))
            jobs.extend(state.push(np.zeros(0,np.float32),flush=True))
            self.assertEqual(jobs,[])

    def test_neural_endpoint_and_progress(self):
        s=LiveSession(vad=lambda frame:float(frame[0]>.1))
        a=s.push(np.ones(FRAME*48,np.float32))
        self.assertEqual(len(a),1);self.assertFalse(a[0]['final'])
        b=s.push(np.ones(FRAME*48,np.float32))
        self.assertEqual(b[0]['seq'],a[0]['seq'])
        preview=s.push(np.zeros(FRAME*13,np.float32))
        self.assertTrue(preview);self.assertFalse(any(j['final'] for j in preview))
        c=s.push(np.zeros(FRAME*15,np.float32))
        self.assertTrue(c[0]['final']);self.assertEqual(c[0]['seq'],0)
        self.assertEqual(c[0]['speech_end_ms'],3072)
        self.assertFalse(s.frames)
        self.assertEqual(s.push(np.zeros(RATE*4,np.float32)),[])

    def test_short_noise_and_bounded_continuous_speech(self):
        s=LiveSession(vad=lambda frame:float(frame[0]>.1))
        s.push(np.ones(FRAME*3,np.float32))
        self.assertEqual(s.push(np.zeros(FRAME*14,np.float32)),[])
        jobs=s.push(np.ones(FRAME*600,np.float32))
        self.assertEqual(sum(j['final'] for j in jobs),3)
        self.assertTrue(all(len(j['audio'])<=RATE*6.1 for j in jobs))
        self.assertEqual(len({j['seq'] for j in jobs}),len(jobs))

    def test_arbitrary_packet_edges_and_flush(self):
        s=LiveSession(vad=lambda frame:1.)
        for _ in range(20):s.push(np.ones(1000,np.float32))
        out=s.push(np.zeros(0,np.float32),flush=True)
        self.assertTrue(out[-1]['final']);self.assertEqual(s.carry.size,0)
        self.assertEqual(s.push(np.zeros(0,np.float32),flush=True),[])

    def test_agreement_and_retraction(self):
        a=Agreement()
        self.assertEqual(a.update('Hello world'),'')
        self.assertEqual(a.update('Hello world today'),'Hello world')
        self.assertEqual(a.update('Hello everyone'),'Hello')
        a=Agreement();a.update('こんばんは今日は')
        self.assertEqual(a.update('こんばんは今日も'),'こんばんは今日')
        a=Agreement();a.update('지금 공격하세요')
        self.assertEqual(a.update('지금 공격하지 마세요'),'지금')

    def test_native_keeps_acoustic_state_across_display_boundary_and_flushes_tail(self):
        made=[]
        class Native:
            def __init__(self):self.samples=0;self.reads=[];made.append(self)
            def feed(self,audio):self.samples+=len(audio)
            def read(self,final=False,boundary=False):
                self.reads.append((final,boundary))
                return {'text':'tail' if final else 'stream','language':'en'}
        state=LiveSession(vad=lambda f:float(f[0]>.1),native_factory=Native)
        jobs=state.push(np.ones(FRAME*188,np.float32))
        self.assertTrue(jobs[-1]['final']);self.assertEqual(len(made),1)
        tail=state.push(np.zeros(FRAME*28,np.float32))
        self.assertEqual(len(made),1)
        self.assertEqual(tail[-1]['native_result']['text'],'tail')
        self.assertIn((False,True),made[0].reads)
        self.assertEqual(made[0].reads[-1],(True,False))
        self.assertEqual(made[0].samples,FRAME*216)

if __name__=='__main__':unittest.main()
