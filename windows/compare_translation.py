"""Controlled text-only Ollama comparison; never changes the backend default."""
import asyncio,json,time,statistics
from pathlib import Path
import httpx
from models import translation_messages,convert
from quality_checks import quality_flags

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'quality/translation-models-0.3.4.json'

async def main():
    cases=[s for s in json.loads((ROOT/'quality/manifest.json').read_text(encoding='utf-8'))['samples'] if s.get('source')]
    cases.extend([
        dict(id='ko-vinegar-control',source='식초를 넣지 말고 소금을 조금 넣어 주세요.',reference_translation='不要加醋，請加一點鹽。'),
        dict(id='ko-new-time',source='다섯 초만 기다린 다음 다시 시작하세요.',reference_translation='只等五秒後再重新開始。'),
        dict(id='ja-new-place',source='京都ではなく、大阪駅で待ってください。',reference_translation='請在大阪站等，不是京都。')])
    terms=json.loads((ROOT/'glossary.json').read_text(encoding='utf-8'))
    report=dict(complete=False,note='Text-only warm-model comparison. No concurrent ASR, no human accuracy score. Rules can produce false positives.',models={},results=[])
    def save():OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=120) as client:
        async def warm(model):
            r=await client.post('/api/chat',json={'model':model,'messages':translation_messages('Hello.',[],[]),'stream':False,'keep_alive':'10m','options':{'temperature':0,'num_ctx':2048,'num_predict':16}})
            r.raise_for_status()
        try:
            for model,other in [('qwen2.5:7b','qwen2.5:3b'),('qwen2.5:3b','qwen2.5:7b')]:
                r=await client.post('/api/generate',json={'model':other,'keep_alive':0});r.raise_for_status()
                await warm(model)
                r=await client.post('/api/show',json={'model':model});r.raise_for_status()
                report['models'][model]=r.json().get('details',{})
                for case in cases:
                    started=time.perf_counter();first=None;text='';done=False;metadata={}
                    required=[t for t in terms if t['ja'].casefold() in case['source'].casefold()]
                    row=dict(model=model,**case)
                    try:
                        async with asyncio.timeout(30),client.stream('POST','/api/chat',json={'model':model,'messages':translation_messages(case['source'],[],required),'stream':True,'keep_alive':'10m','options':{'temperature':0,'num_ctx':2048,'num_predict':160}}) as response:
                            response.raise_for_status()
                            async for line in response.aiter_lines():
                                if not line:continue
                                event=json.loads(line)
                                if event.get('error'):raise RuntimeError(event['error'])
                                token=event.get('message',{}).get('content','')
                                if token and first is None:first=(time.perf_counter()-started)*1000
                                text+=token
                                if event.get('done'):done=True;metadata=event
                        if not done or metadata.get('done_reason')=='length':raise RuntimeError('Incomplete translation')
                        row.update(translation=convert.convert(text.strip()),first_token_ms=first,total_ms=(time.perf_counter()-started)*1000,
                                   eval_ms=metadata.get('eval_duration',0)/1e6,load_ms=metadata.get('load_duration',0)/1e6)
                        row['rule_flags']=quality_flags(case['source'],row['translation'],case['id'][:2],required)
                    except Exception as error:row['error']=str(error) or type(error).__name__
                    report['results'].append(row);save()
                    print(json.dumps(row,ensure_ascii=False),flush=True)
            report['complete']=True;save()
        finally:
            await client.post('/api/generate',json={'model':'qwen2.5:3b','keep_alive':0})
            await warm('qwen2.5:7b')

if __name__=='__main__':asyncio.run(main())
