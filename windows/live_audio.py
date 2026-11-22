"""Incremental audio state; Silero inference is reused from faster-whisper.

Two-hypothesis agreement follows WhisperStreaming's published LocalAgreement
idea. This implementation does not copy its source. See THIRD_PARTY_NOTICES.md.
"""
import os,time,uuid,re
from collections import deque
import numpy as np
from faster_whisper.vad import get_vad_model

RATE=16000
FRAME=512

def env_ms(name,default,low,high):
    """Read an optional millisecond setting; invalid values fail at startup instead of silently."""
    raw=os.environ.get(name)
    if raw is None or raw.strip()=='':return default
    try:value=int(raw)
    except ValueError:raise ValueError(f'{name} must be whole milliseconds, got {raw!r}') from None
    if not low<=value<=high:raise ValueError(f'{name} must be between {low} and {high} ms, got {value}')
    return value

# 32 ms frames. Defaults keep the measured behaviour: 6.016 s hard limit, 896 ms conservative pause.
MAX_SEGMENT_FRAMES=round(env_ms('MOSA_MAX_SEGMENT_MS',6016,2000,10000)/32)
PAUSE_FRAMES=round(env_ms('MOSA_PAUSE_MS',896,320,2000)/32)
# At the hard limit, cut at the deepest breath in the last 1.5 s instead of mid-word;
# the words after the breath start the next caption. Off until measured on real speech
# (2026-10-24): set MOSA_BREATH_CUT=1 to try it. It moves the cut, it does not finalize sooner.
BREATH_CUT=os.environ.get('MOSA_BREATH_CUT','0')=='1'
BREATH_LOOKBACK_FRAMES=47
BREATH_MAX_PROBABILITY=.2
# Optional low-latency mode (0 = off): once a turn is this long, a short breath
# (MOSA_SOFT_PAUSE_MS of non-speech) finalizes it without waiting for the full pause.
SOFT_CUT_MS=env_ms('MOSA_SOFT_CUT_MS',0,0,10000)
if SOFT_CUT_MS and SOFT_CUT_MS<1500:raise ValueError('MOSA_SOFT_CUT_MS must be 0 (off) or at least 1500 ms')
SOFT_CUT_FRAMES=round(SOFT_CUT_MS/32)
SOFT_PAUSE_FRAMES=round(env_ms('MOSA_SOFT_PAUSE_MS',192,96,800)/32)

class NeuralVad:
    def __init__(self):
        self.session=get_vad_model().session
        self.h=np.zeros((1,1,128),np.float32)
        self.c=self.h.copy()
        self.context=np.zeros(64,np.float32)

    def __call__(self,frame):
        out,self.h,self.c=self.session.run(None,{'input':np.concatenate([self.context,frame])[None,:],
                                               'h':self.h,'c':self.c})
        self.context=frame[-64:].copy()
        return float(out.reshape(-1)[0])

class Agreement:
    def __init__(self):
        self.previous=''
        self.stable=''

    def update(self,text):
        # Confirm only the prefix shared by two consecutive hypotheses. Never
        # lock a half English/Korean word at the right edge.
        n=0
        for a,b in zip(self.previous,text):
            if a!=b:break
            n+=1
        prefix=text[:n]
        def word_char(c):return (c.isascii() and c.isalnum()) or '\uac00'<=c<='\ud7a3'
        if n<len(text) and n and word_char(text[n]) and word_char(text[n-1]):
            prefix=prefix.rsplit(' ',1)[0] if ' ' in prefix else ''
        self.previous=text
        # A later hypothesis can contradict the old prefix; retract it instead
        # of preserving a known incorrect prefix through the rest of the turn.
        self.stable=prefix.strip()
        return self.stable

class LiveSession:
    def __init__(self,vad=None,native_factory=None,endpoint_mode='conservative'):
        self.instance=uuid.uuid4().hex
        self.vad=vad or NeuralVad()
        self.carry=np.zeros(0,np.float32)
        self.preroll=deque(maxlen=7)
        self.frames=[]
        self.quiet=0
        self.voiced=0
        self.offset=0
        self.start=0
        self.seq=0
        self.last_preview=0
        self.agreement=Agreement()
        self.translation_source=''
        self.history=[]
        self.touched=time.monotonic()
        self.native_factory=native_factory;self.native=None
        self.overlap=0
        if endpoint_mode not in ('conservative','adaptive'):raise ValueError('Invalid endpoint mode')
        self.endpoint_mode=endpoint_mode;self.endpoint_seq=None
        self.pause_key=None
        self.probs=[]

    def consider_endpoint(self,seq,text,stable,uncertain=False,silence_ms=0,speech_end_ms=None):
        # Neither silence nor model punctuation alone proves a sentence ended.
        # Require agreement across hypotheses after a pause; resumed speech
        # invalidates the hint before the next boundary decision.
        enough=len(text)>=4 and (not text.isascii() or len(text.split())>=3)
        same_pause=speech_end_ms is None or self.offset-self.quiet*FRAME==round((speech_end_ms-silence_ms)*RATE/1000)
        if (self.endpoint_mode=='adaptive' and seq==self.seq and not uncertain and self.quiet>=13 and same_pause
                and silence_ms>=416 and text==stable and enough and re.search(r'[。！？.!?][」』”"]?$',text)):
            self.endpoint_seq=seq
            if self.quiet>=18:return self.finish()

    def finish(self,hard=False,force=False,soft=False):
        if not self.frames:return None
        # Keep 128ms of tail while excluding the endpoint silence.
        trim=max(0,self.quiet-4)
        frames=self.frames[:-trim] if trim else self.frames
        job=dict(seq=self.seq,audio=np.concatenate(frames),final=True,
                 speech_start_ms=self.start*1000/RATE,
                 speech_end_ms=(self.offset-self.quiet*FRAME)*1000/RATE,
                 commit_samples=self.offset,overlap_ms=self.overlap*32,
                 endpoint_silence_ms=self.quiet*32,
                 endpoint_reason='flush' if force else 'continuous_limit' if hard else 'soft_pause' if soft else
                 'confirmed_sentence' if self.endpoint_seq==self.seq else 'silence')
        if not hard and not force and self.pause_key==(self.seq,self.voiced):
            # Only silence followed the pause preview, so its ASR/translation can be reused.
            job['pause_key']=self.pause_key
        self.pause_key=None
        if self.native:job['native_result']=self.native.read(final=not hard,boundary=hard)
        tail=[f.copy() for f in frames[-8:]] if hard and not self.native else []
        valid=self.voiced>=4 or bool(job.get('native_result',{}).get('text'))
        self.frames=[];self.probs=[];self.quiet=0;self.voiced=0;self.last_preview=0;self.seq+=1
        if not hard:self.native=None
        self.endpoint_seq=None
        self.overlap=0
        if tail:
            self.preroll.extend(tail)
            self.overlap=len(self.preroll)
        return job if valid else None

    def breath_index(self):
        """Frame index inside the deepest 96 ms dip of the last 1.5 s, or None if speech never paused."""
        n=len(self.probs);best=None
        for j in range(max(3,n-BREATH_LOOKBACK_FRAMES),n-1):
            level=sum(self.probs[j-2:j+1])/3
            if best is None or level<best[0]:best=(level,j)
        return best[1] if best and best[0]<=BREATH_MAX_PROBABILITY else None

    def cut_at(self,index):
        """Finalize frames before index; frames from index on stay as the start of the next caption."""
        frames=self.frames[:index];end=self.start+index*FRAME
        job=dict(seq=self.seq,audio=np.concatenate(frames),final=True,
                 speech_start_ms=self.start*1000/RATE,speech_end_ms=end*1000/RATE,
                 # Later frames are still pending here, so only audio before the cut is safe to drop.
                 commit_samples=end,overlap_ms=self.overlap*32,endpoint_silence_ms=0,endpoint_reason='breath_cut')
        valid=sum(p>=.35 for p in self.probs[:index])>=4
        self.frames=self.frames[index:];self.probs=self.probs[index:];self.start=end
        self.voiced=sum(p>=.35 for p in self.probs);self.quiet=min(self.quiet,len(self.frames))
        self.pause_key=None;self.last_preview=0;self.seq+=1;self.endpoint_seq=None;self.overlap=0
        return job if valid else None

    def push(self,audio,flush=False):
        self.touched=time.monotonic()
        self.carry=np.concatenate([self.carry,audio])
        jobs=[]
        while len(self.carry)>=FRAME:
            frame=self.carry[:FRAME];self.carry=self.carry[FRAME:]
            self.offset+=FRAME
            probability=self.vad(frame)
            speech=probability>=(.35 if self.frames else .55)
            if not self.frames:
                if not speech and self.native is None:
                    self.preroll.append(frame.copy());self.overlap=max(0,self.overlap-1);continue
                self.frames=list(self.preroll);self.probs=[0.]*len(self.frames);self.preroll.clear()
                self.start=self.offset-FRAME*(len(self.frames)+1)
                if self.native_factory and self.native is None:
                    self.native=self.native_factory()
                    if self.frames:self.native.feed(np.concatenate(self.frames))
            self.frames.append(frame.copy());self.probs.append(probability)
            if self.native:self.native.feed(frame)
            if speech:self.quiet=0;self.voiced+=1;self.endpoint_seq=None
            else:self.quiet+=1
            # A short pause produces a hypothesis, not an irreversible boundary.
            pause=PAUSE_FRAMES if self.endpoint_mode=='conservative' else 18 if self.endpoint_seq==self.seq else 25
            soft=bool(SOFT_CUT_FRAMES) and len(self.frames)>=SOFT_CUT_FRAMES and self.quiet>=SOFT_PAUSE_FRAMES
            if self.quiet>=pause or soft or len(self.frames)>=MAX_SEGMENT_FRAMES:
                hard=self.quiet<pause and not soft
                breath=self.breath_index() if hard and BREATH_CUT and not self.native else None
                job=self.cut_at(breath) if breath else self.finish(hard=hard,soft=soft and self.quiet<pause)
                if job:jobs.append(job)
            elif (self.quiet==13 or len(self.frames)-self.last_preview>=(15 if self.native else 30)) and self.voiced>=12:
                self.last_preview=len(self.frames)
                # At most one preview per received batch, replaced by a final.
                jobs=[j for j in jobs if j['seq']!=self.seq]
                jobs.append(dict(seq=self.seq,audio=np.concatenate(self.frames),final=False,
                                 speech_start_ms=self.start*1000/RATE,speech_end_ms=self.offset*1000/RATE,
                                 overlap_ms=self.overlap*32,silence_ms=self.quiet*32))
                if self.native:jobs[-1]['native_result']=self.native.read()
                if self.quiet==13:jobs[-1]['pause_key']=self.pause_key=(self.seq,self.voiced)
        if flush:
            if len(self.carry):
                tail=self.carry;self.carry=np.zeros(0,np.float32)
                jobs.extend(self.push(np.pad(tail,(0,FRAME-len(tail)))))
            job=self.finish(force=True)
            if job:jobs.append(job)
        finals={j['seq'] for j in jobs if j['final']}
        return [j for j in jobs if j['final'] or j['seq'] not in finals]
