import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import numpy as np
import diagnose_chat_hallucination as diag

class Word:
    def __init__(self,word,end):self.word,self.end=word,end
class Segment:
    def __init__(self,text,words,no_speech=.05,logprob=-.3):
        self.text,self.words,self.start,self.end=text,words,0.,2.
        self.avg_logprob,self.no_speech_prob,self.compression_ratio=logprob,no_speech,1.2
class Info:language,language_probability='en',.99

class NumpyWord(Word):
    def __init__(self,word,end):super().__init__(word,np.float32(end))
class NumpySegment(Segment):
    """Real Faster-Whisper results carry numpy scalars; the JSON report must still serialize."""
    def __init__(self,*a,**k):
        super().__init__(*a,**k);self.avg_logprob,self.no_speech_prob,self.compression_ratio=np.float32(-.3),np.float32(.05),np.float32(1.2)

class FakeWhisper:
    """With the glossary prompt the fragment decodes to "and chat."; without it, to the real words."""
    def __init__(self):self.calls=[]
    def transcribe(self,audio,**kw):
        self.calls.append(kw)
        if kw['initial_prompt'] and 'chat' in kw['initial_prompt']:return iter([Segment(' and chat.',[Word(' and',.1),Word(' chat.',.5)])]),Info()
        return iter([Segment(' a traffic until March 2017.',[Word(' a',.15),Word(' traffic',.6),Word(' until',.9),Word(' March',1.2),Word(' 2017.',1.6)])]),Info()

def final(seq,start,end,text,reason='silence',overlap=0):
    return dict(type='final',seq=seq,speech_start_ms=start,speech_end_ms=end,original=text,endpoint_reason=reason,overlap_ms=overlap)

class ChatDiagnosisTests(unittest.TestCase):
    def test_finds_chat_only_finals_and_optionally_all_after_hard_cuts(self):
        finals=[final(0,0,6000,"It didn't open a tr-",'continuous_limit'),final(1,5800,7000,'chat.'),final(2,7500,9000,'Hello.'),
                final(3,9000,15000,'Long sentence','continuous_limit'),final(4,14800,16000,'and more words')]
        self.assertEqual([(e['seq'],cut) for e,_,cut in diag.suspects(finals)],[(1,True)])
        self.assertEqual([e['seq'] for e,_,_ in diag.suspects(finals,True)],[1,4])
        self.assertTrue(diag.SUSPECT.match(' And chat. '));self.assertFalse(diag.SUSPECT.match('the chat was fun'))

    def test_clip_matches_service_audio_window(self):
        audio=np.arange(32000,dtype=np.float32)
        piece=diag.clip(audio,final(1,500,1000,'chat.'))
        self.assertEqual((piece[0],len(piece)),(8000,(1000+diag.TAIL_MS-500)*16))

    def test_variants_separate_prompt_and_overlap_filter_effects(self):
        model=FakeWhisper()
        prompt=diag.glossary_prompt()
        variants={name:diag.recognize(model,np.zeros(16000,np.float32),224,'en',p,f,prompt)['text'] for name,p,f in diag.VARIANTS}
        self.assertEqual(variants['live'],'chat.')                         # " and" ends before the 224 ms overlap cutoff
        self.assertEqual(variants['no_prompt'],'traffic until March 2017.')  # " a" (0.15 s) is overlap audio from the previous caption
        self.assertEqual(variants['no_filter'],'and chat.')
        self.assertEqual(variants['neither'],'a traffic until March 2017.')
        self.assertTrue(all(c['word_timestamps'] and c['language']=='en' and c['beam_size']==1 for c in model.calls))
        rows=[dict(service_text='chat.',variants={n:{'text':t} for n,t in variants.items()})]
        summary=diag.summarize(rows)
        self.assertEqual((summary['live_contains_chat'],summary['no_prompt_contains_chat'],summary['live_replica_matches_service']),(1,0,1))

    def test_no_overlap_means_no_word_timestamps_like_the_service(self):
        model=FakeWhisper();diag.recognize(model,np.zeros(16000,np.float32),0,'en',False,True,None)
        self.assertFalse(model.calls[0]['word_timestamps'])

    def test_report_serializes_numpy_values(self):
        import json
        class NumpyWhisper:
            def transcribe(self,audio,**kw):return iter([NumpySegment(' chat.',[NumpyWord(' chat.',.5)])]),Info()
        out=diag.recognize(NumpyWhisper(),np.zeros(16000,np.float32),224,'en',True,True,'Twitch, chat')
        self.assertIn('"kept": true',json.dumps(out))

    def test_prompt_is_the_service_prompt(self):
        import models
        self.assertEqual(diag.glossary_prompt(),models.asr_prompt())

if __name__=='__main__':unittest.main()
