import asyncio,contextlib,io,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))

class FakeClient:
    def __init__(self,payload=None,error=None):self.payload=payload;self.error=error
    async def get(self,*args,**kwargs):
        if self.error:raise self.error
        payload=self.payload
        class Response:
            def raise_for_status(self):pass
            def json(self):return payload
        return Response()

class SpeedMetricTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_cpu_offload_is_reported_and_warned(self):
        import models as m
        payload={'models':[{'name':m.NMT,'model':m.NMT,'size':4*1048576*1000,'size_vram':2*1048576*1000,'context_length':2048}]}
        out=io.StringIO()
        with patch.dict(m.placement,{},clear=True),contextlib.redirect_stdout(out):
            await m.check_placement(FakeClient(payload),warn=True)
            self.assertEqual(m.placement['gpu_share'],.5)
            self.assertEqual((m.placement['vram_mib'],m.placement['size_mib']),(2000,4000))
        self.assertIn('only 50% on GPU',out.getvalue())

    async def test_full_gpu_is_quiet_and_missing_model_or_ollama_is_explicit(self):
        import models as m
        out=io.StringIO()
        with patch.dict(m.placement,{},clear=True),contextlib.redirect_stdout(out):
            await m.check_placement(FakeClient({'models':[{'name':m.NMT+':latest','size':100,'size_vram':100}]}),warn=True)
            self.assertEqual(m.placement['gpu_share'],1.0)
            await m.check_placement(FakeClient({'models':[{'name':'other:1b','size':1,'size_vram':0}]}))
            self.assertIsNone(m.placement['gpu_share']);self.assertIn('not loaded',m.placement['note'])
            await m.check_placement(FakeClient(error=OSError('down')))
            self.assertIsNone(m.placement['gpu_share']);self.assertIn('unavailable',m.placement['note'])
        self.assertEqual(out.getvalue(),'')

    def test_timing_summary_is_bounded_and_counts_repairs_only_for_translated(self):
        import models as m
        with patch.object(m,'timings',m.deque(maxlen=200)):
            self.assertEqual(m.timing_summary()['captions'],0)
            for i in range(250):
                m.timings.append(dict(asr_ms=100+i,nmt_queue_ms=0,nmt_ms=None if i%5==0 else 200+i,repaired=i%10==1))
            summary=m.timing_summary()
        self.assertEqual(summary['captions'],200)
        self.assertEqual(summary['translated'],160)
        self.assertEqual(summary['repair_rate'],round(20/160,3))
        self.assertLessEqual(summary['asr_ms_p50'],summary['asr_ms_p95'])
        self.assertLessEqual(summary['nmt_ms_p50'],summary['nmt_ms_p95'])

    async def test_health_exposes_timing_and_placement(self):
        import httpx,models as m
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app),base_url='http://127.0.0.1:8790') as client:
            with patch.object(m,'ready',False):
                body=(await client.get('/health')).json()
        self.assertIn('timing',body);self.assertIn('translation_placement',body)

if __name__=='__main__':unittest.main()

class OllamaPhaseTimingTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_records_ollama_phase_durations(self):
        import json,httpx,models as m
        lines=[{'message':{'content':'你'}},{'message':{'content':'好'}},
               {'done':True,'done_reason':'stop','total_duration':450_000_000,'load_duration':2_000_000,
                'prompt_eval_count':420,'prompt_eval_duration':60_000_000,'eval_count':20,'eval_duration':380_000_000}]
        body='\n'.join(json.dumps(x) for x in lines).encode()
        transport=httpx.MockTransport(lambda request:httpx.Response(200,content=body))
        real=httpx.AsyncClient
        with patch.object(m,'ollama_calls',m.deque(maxlen=200)), \
             patch.object(m.httpx,'AsyncClient',lambda **kw:real(transport=transport)):
            text=''.join([t async for t in m.ollama_tokens('Hello',[],[])])
            summary=m.ollama_summary()
            call=m.ollama_calls[0]
        self.assertEqual(text,'你好')
        self.assertEqual((call['load_ms'],call['prompt_ms'],call['prompt_tokens'],call['eval_ms'],call['eval_tokens']),(2.0,60.0,420,380.0,20))
        self.assertIsNotNone(call['first_token_ms'])
        self.assertEqual(summary['calls'],1);self.assertEqual(summary['tokens_per_second_p50'],52.6)

    async def test_missing_fields_stay_unknown(self):
        import models as m
        with patch.object(m,'ollama_calls',m.deque(maxlen=200)):
            m.record_ollama_call({'done':True},0.0,None)
            self.assertIsNone(m.ollama_calls[0]['prompt_ms'])
            self.assertIsNone(m.ollama_summary()['tokens_per_second_p50'])
