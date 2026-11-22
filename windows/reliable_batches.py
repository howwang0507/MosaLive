"""Bounded replay cache: disconnecting a client doesn't cancel an accepted batch."""
import asyncio,hashlib,time,json
from collections import OrderedDict
from fastapi import HTTPException

class BatchCache:
    def __init__(self,limit=64):self.items=OrderedDict();self.limit=limit
    async def cancel_sessions(self,session_ids):
        entries=[entry for key,entry in self.items.items()
               if key[0] in session_ids and not entry['done']]
        tasks=[entry['task'] for entry in entries]
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        for entry in entries:entry['done']=True;entry['changed'].set()
    def start(self,key,payload,options,produce):
        digest=hashlib.sha256(payload+repr(options).encode()).hexdigest()
        existing=self.items.get(key)
        if existing:
            if existing['digest']!=digest:raise HTTPException(409,'Batch payload changed')
            self.items.move_to_end(key);return existing
        now=time.monotonic()
        for k in list(self.items):
            if self.items[k]['done'] and now-self.items[k]['created']>120:self.items.pop(k)
        while len(self.items)>=self.limit:
            victim=next((k for k,v in self.items.items() if v['done']),None)
            if victim is None:raise HTTPException(503,'Replay cache busy')
            self.items.pop(victim)
        entry=dict(digest=digest,lines=[],done=False,changed=asyncio.Event(),created=now)
        self.items[key]=entry
        async def run():
            try:
                async for line in produce():entry['lines'].append(line);entry['changed'].set()
            except Exception as error:
                entry['lines'].append(json.dumps({'type':'error','error':str(error)})+'\n')
            finally:entry['done']=True;entry['changed'].set()
        entry['task']=asyncio.create_task(run())
        return entry
    async def stream(self,entry):
        index=0
        while True:
            while index<len(entry['lines']):
                yield entry['lines'][index];index+=1
            if entry['done']:break
            entry['changed'].clear()
            await entry['changed'].wait()
