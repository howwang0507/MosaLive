import test from 'node:test';
import assert from 'node:assert/strict';
import {SessionStats} from '../extension/session-stats.js';

test('per-minute stats carry capture gaps and speech-start-to-final latency',()=>{
 let now=0;const stats=new SessionStats(()=>now);
 stats.accept({type:'metrics',capture_gap_count:0,capture_gap_ms:0});
 now=10000;stats.accept({type:'final',seq:1,after_speech_ms:1100,capture_to_caption_ms:4000});
 now=20000;stats.accept({type:'final',seq:2,after_speech_ms:1300,capture_to_caption_ms:6000});
 now=30000;stats.accept({type:'metrics',capture_gap_count:1,capture_gap_ms:7500});
 now=70000;stats.accept({type:'metrics',capture_gap_count:1,capture_gap_ms:7500});   // no new gap in minute 2
 now=80000;stats.accept({type:'metrics',capture_gap_count:3,capture_gap_ms:9500});
 const [m1,m2]=stats.snapshot().minutes;
 assert.equal(m1.capture_gaps,1);assert.equal(m1.capture_gap_ms,7500);
 assert.equal(m1.onset_p50_ms,4000);assert.equal(m1.onset_p95_ms,6000);
 assert.equal(m1.p50_ms,1100);
 assert.equal(m2.capture_gaps,2);assert.equal(m2.capture_gap_ms,2000);
 assert.equal(m2.onset_p50_ms,null);
});
