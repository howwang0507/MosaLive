import test from 'node:test';
import assert from 'node:assert/strict';
import {SessionStats} from '../extension/session-stats.js';
test('minute stats count deltas, bound memory and preserve unknown latency',()=>{
 let now=0;const stats=new SessionStats(()=>now);
 stats.accept({type:'metrics',dropped_audio_ms:20,overflow_dropped_audio_ms:12,playback_dropped_audio_ms:8,auto_recoveries:1});
 stats.accept({type:'metrics',dropped_audio_ms:20,overflow_dropped_audio_ms:12,playback_dropped_audio_ms:8,auto_recoveries:1});
 stats.accept({type:'final',seq:0,original:'hello',translation:'你好'});
 assert.equal(stats.snapshot().minutes[0].p50_ms,null);
 stats.accept({type:'gpu',used_mib:100});stats.accept({type:'gpu',used_mib:80});
 assert.equal(stats.snapshot().minutes[0].gpu_peak_mib,100);
 assert.equal(stats.snapshot().minutes[0].dropped_ms,20);
 assert.equal(stats.snapshot().minutes[0].overflow_dropped_ms,12);
 assert.equal(stats.snapshot().minutes[0].playback_dropped_ms,8);
 assert.equal(stats.snapshot().minutes[0].recoveries,1);
 for(let i=1;i<=65;i++){now=i*60000;stats.accept({type:'final',seq:i,after_speech_ms:i,original:'source',translation:'譯文'});}
 assert.equal(stats.snapshot().minutes.length,60);assert.equal(stats.snapshot().recent.length,10);
 assert.equal(stats.snapshot().minutes.at(-1).average_gap_ms,60000);
});
