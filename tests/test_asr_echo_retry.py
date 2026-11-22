import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import numpy as np
import models as m

class Word:
    def __init__(self,word,end):self.word,self.end=word,end
class Segment:
    def __init__(self,text,words):
        self.text,self.words,self.start,self.end=text,words,0.,2.
        self.avg_logprob,self.no_speech_prob,self.compression_ratio=-.3,.05,1.2
class Info:language,language_probability='en',.99

class Whisper:
    """Echoes the prompt when one is given; otherwise returns the real words (2026-10-24 seq 41 pattern)."""
    def __init__(self,with_prompt=' and chat.',without=' will be issued because the quake did not meet magnitude 6.5.'):
        self.calls=[];self.with_prompt,self.without=with_prompt,without
    def transcribe(self,audio,**kw):
        self.calls.append(kw);text=self.with_prompt if kw['initial_prompt'] else self.without
        return iter([Segment(text,[Word(' '+w,.3+i*.2) for i,w in enumerate(text.split())])]),Info()

def recognize(model,overlap_ms=224,prompt='Twitch, chat',samples=48000,enabled=True):
    # 48000 samples = 3 s, above the provisional 2 s minimum; the guard itself is off by default.
    with patch.object(m,'model',model),patch.object(m,'asr_prompt',lambda:prompt),patch.object(m,'ASR_ECHO_RETRY',enabled),patch.dict(m.METRICS,{},clear=False):
        for key in ('asr_prompt_echo_retries','asr_prompt_echo_changed','asr_prompt_echo_skipped_short'):m.METRICS.pop(key,None)
        audio=np.zeros(samples,np.float32) if samples is not None else None
        result=m.live_recognize(audio,overlap_ms,'en')
        return result,dict(m.METRICS)

class PromptEchoRetryTests(unittest.TestCase):
    def test_echo_after_hard_cut_is_decoded_once_without_prompt(self):
        model=Whisper();result,metrics=recognize(model)
        self.assertEqual(result['text'],'will be issued because the quake did not meet magnitude 6.5.')
        self.assertTrue(result['asr_prompt_echo_retry']);self.assertEqual(result['asr_echo_text'],'and chat.')
        self.assertIsInstance(result['asr_retry_ms'],float)
        self.assertEqual(len(model.calls),2);self.assertIsNone(model.calls[1]['initial_prompt'])
        first,second=dict(model.calls[0]),dict(model.calls[1]);first.pop('initial_prompt');second.pop('initial_prompt')
        self.assertEqual(first,second)                                    # every other decoding setting unchanged
        self.assertEqual((metrics['asr_prompt_echo_retries'],metrics['asr_prompt_echo_changed']),(1,1))

    def test_no_retry_without_hard_cut_or_for_real_sentences(self):
        for model,overlap in ((Whisper(),0),(Whisper(with_prompt=' Thank you chat, see you tomorrow.'),224)):
            result,_=recognize(model,overlap)
            self.assertEqual(len(model.calls),1);self.assertNotIn('asr_prompt_echo_retry',result)

    def test_at_most_one_retry_and_empty_retry_is_kept(self):
        model=Whisper(without=' chat.');result,_=recognize(model)
        self.assertEqual(len(model.calls),2);self.assertEqual(result['text'],'chat.')       # real "chat" survives without the prompt
        model=Whisper(without='');result,metrics=recognize(model)
        self.assertEqual((len(model.calls),result['text']),(2,''))
        self.assertEqual(metrics['asr_prompt_echo_changed'],1)

    def test_disabled_or_empty_glossary_never_retries(self):
        model=Whisper();recognize(model,enabled=False);self.assertEqual(len(model.calls),1)
        model=Whisper();recognize(model,prompt=None);self.assertEqual(len(model.calls),1)

    def test_echo_detection(self):
        for text,expected in (('and chat.',True),('Chat.',True),('Twitch chat',True),('Okay, chat!',True),
                              ('Thank you chat',False),('',False),('and',False),('chatting',False)):
            self.assertEqual(m.prompt_echo(text,'Twitch, chat'),expected,text)
        self.assertFalse(m.prompt_echo('chat',None))

    def test_health_reports_retry_summary(self):
        summary=m.echo_retry_summary()
        self.assertEqual(set(summary),{'enabled','min_audio_ms','retries','changed','skipped_short','window','retry_ms_p50','retry_ms_p95'})

    def test_off_by_default_until_gpu_confirmation(self):
        # 2026-10-25 synthetic positive control: a real "chat" (1.44 s segment) was lost after a retry.
        import importlib,os
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop('MOSA_ASR_ECHO_RETRY',None);os.environ.pop('MOSA_ASR_ECHO_MIN_MS',None)
            self.addCleanup(importlib.reload,m);importlib.reload(m)
            self.assertFalse(m.ASR_ECHO_RETRY);self.assertEqual(m.ECHO_MIN_AUDIO_MS,2000)

    def test_minimum_audio_length_boundary(self):
        # Real "chat" segments measured 0.58-1.76 s; prompt echoes covered 2.34-6.14 s of speech.
        model=Whisper();result,metrics=recognize(model,samples=31984)          # 1999 ms
        self.assertEqual(len(model.calls),1);self.assertEqual(result['text'],'and chat.')
        self.assertEqual(metrics['asr_prompt_echo_skipped_short'],1);self.assertNotIn('asr_prompt_echo_retries',metrics)
        model=Whisper();result,_=recognize(model,samples=32000)                # exactly 2000 ms
        self.assertEqual(len(model.calls),2);self.assertEqual(result['asr_retry_audio_ms'],2000.0)
        model=Whisper();recognize(model,samples=None)                          # length unknown: never retry
        self.assertEqual(len(model.calls),1)

    def test_minimum_is_configurable_and_validated(self):
        with patch.object(m,'ECHO_MIN_AUDIO_MS',1000):
            model=Whisper();recognize(model,samples=16000);self.assertEqual(len(model.calls),2)
        import os
        from live_audio import env_ms
        for bad in ('fast','100','20000'):
            with patch.dict(os.environ,{'MOSA_ASR_ECHO_MIN_MS':bad}),self.assertRaises(ValueError):env_ms('MOSA_ASR_ECHO_MIN_MS',2000,500,10000)

if __name__=='__main__':unittest.main()
