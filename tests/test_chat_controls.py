import io,json,sys,tempfile,unittest,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import numpy as np
import build_chat_controls as builder
import check_chat_controls as checker

def write(path,audio,rate=16000):
    with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())

def speech(seconds,dips_every=.5):
    """Tone with a 40 ms near-silent dip every dips_every seconds, like gaps between words."""
    t=np.arange(int(16000*seconds))/16000;audio=(.2*np.sin(2*np.pi*200*t)).astype(np.float32)
    for start in np.arange(dips_every,seconds,dips_every):audio[int(start*16000):int(start*16000)+640]*=.01
    return audio

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.rec=Path(tempfile.mkdtemp())
        write(self.rec/'long-a.wav',np.concatenate([np.zeros(8000,np.float32),speech(9,.25)]))
        write(self.rec/'long-b.wav',speech(8.5,.25))
        write(self.rec/'chat-chat-1.wav',np.concatenate([np.zeros(4000),speech(.4,1)]).astype(np.float32))
        write(self.rec/'chat-thanks-chat-2.wav',speech(.7,1),rate=44100)

    def test_samples_categories_and_cut_points(self):
        manifest,samples=builder.build(self.rec,Path(tempfile.mkdtemp()))
        self.assertEqual(len(samples),12)
        self.assertEqual({s['phrase'] for s in samples},{'chat','thanks chat'})
        cuts=[s for s in samples if s['category']=='after_cut']
        self.assertEqual(len(cuts),8)
        for s in cuts:
            target=int(s['id'].rsplit('-',1)[1])
            self.assertLessEqual(abs(s['speech_ms']-target),170)        # +-150 ms window, cut on a 20 ms frame boundary
            self.assertLessEqual(s['speech_ms']%250,20)                 # every +-150 ms window holds a dip; the cut starts in it
        data=json.loads(manifest.read_text(encoding='utf-8'))
        self.assertEqual(len(data['samples']),12);self.assertTrue(all(Path(s['path']).exists() for s in data['samples']))
        with self.assertRaises(FileExistsError):builder.build(self.rec,manifest.parent)

    def test_rejects_short_passages_and_phrases_without_chat(self):
        short=Path(tempfile.mkdtemp());write(short/'long-a.wav',speech(5));write(short/'chat-chat.wav',speech(.4,1))
        with self.assertRaises(ValueError):builder.build(short,Path(tempfile.mkdtemp()))
        bad=Path(tempfile.mkdtemp());write(bad/'long-a.wav',speech(9));write(bad/'chat-hello-1.wav',speech(.4,1))
        with self.assertRaises(ValueError):builder.build(bad,Path(tempfile.mkdtemp()))

    def test_phrase_from_file_name(self):
        self.assertEqual(builder.phrase(Path('chat-thanks-chat-12.wav')),'thanks chat')
        self.assertEqual(builder.phrase(Path('chat-okay-chat.wav')),'okay chat')

def result(sample_id,category,phrase,finals):
    return dict(id=sample_id,category=category,phrase=phrase,source=phrase,
                events=[dict(type='final',seq=i,**f) for i,f in enumerate(finals)])

class CheckTests(unittest.TestCase):
    def test_kept_lost_and_lost_after_retry(self):
        rows=[checker.check_sample(r) for r in (
            result('a','after_cut','chat',[{'original':'and the boss is'},{'original':'chat.'}]),
            result('b','after_cut','thanks chat',[{'original':'thanks.','asr_prompt_echo_retry':True,'asr_echo_text':'thanks chat.'}]),
            result('c','alone','chat',[{'original':'Chad.'}]),
            result('d','after_cut','chat',[{'original':'Chat.','asr_prompt_echo_retry':True,'asr_echo_text':'chat.'}]))]
        self.assertEqual([(r['kept'],r['lost_after_retry']) for r in rows],[(True,False),(False,True),(False,False),(True,False)])
        summary=checker.summarize(rows)
        self.assertEqual(summary['after_cut'],dict(samples=3,kept=2,lost=1,retried=2,lost_after_retry=1))
        self.assertEqual(summary['alone'],dict(samples=1,kept=0,lost=1,retried=0,lost_after_retry=0))

if __name__=='__main__':unittest.main()
