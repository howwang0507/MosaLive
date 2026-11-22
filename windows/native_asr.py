"""Actual incremental transducer state, using official sherpa-onnx models."""
from functools import lru_cache
from pathlib import Path
import numpy as np
import sherpa_onnx
from setup_streaming import MODELS
ROOT=Path(__file__).resolve().parents[1]/'.models/streaming'

@lru_cache(maxsize=2)
def recognizer(model_key):
    folder=ROOT/MODELS[model_key]
    def choose(prefix):
        candidates=list(folder.glob(prefix+'*.onnx'))
        if not candidates:raise RuntimeError('Missing streaming model; run windows/setup_streaming.py')
        return str(sorted(candidates,key=lambda p:('int8' not in p.name,p.name))[0])
    return sherpa_onnx.OnlineRecognizer.from_transducer(tokens=str(folder/'tokens.txt'),
        encoder=choose('encoder'),decoder=choose('decoder'),joiner=choose('joiner'),
        num_threads=2,provider='cpu',enable_endpoint_detection=False)

class NativeStream:
    def __init__(self,language):
        self.language=language;self.model=recognizer('ko' if language=='ko' else 'multi');self.stream=self.model.create_stream()
        self.committed=0
    def feed(self,audio):
        self.stream.accept_waveform(16000,np.ascontiguousarray(audio,dtype=np.float32))
    def read(self,final=False,boundary=False):
        if final:
            self.feed(np.zeros(4800,np.float32));self.stream.input_finished()
        while self.model.is_ready(self.stream):self.model.decode_stream(self.stream)
        text=self.model.get_result(self.stream).strip()
        # A display boundary must not reset the acoustic state mid-word.
        # Keep the last space-delimited word for the next subtitle until final.
        if boundary and self.language in ('en','ko'):
            text=text.rsplit(' ',1)[0] if ' ' in text else ''
        visible=text[self.committed:].strip()
        if boundary:self.committed=max(self.committed,len(text))
        return dict(text=visible,language=self.language,
                    language_probability=None,asr_backend='zipformer-cpu')
