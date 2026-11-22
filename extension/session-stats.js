export class SessionStats {
 constructor(now=Date.now){this.now=now;this.started=now();this.buckets=[];this.recent=[];this.lastFinal=null;this.metrics={};this.status='等待音訊';}
 accept(e){
  const minute=Math.floor((this.now()-this.started)/60000);
  if(this.buckets.at(-1)?.minute!==minute)this.buckets.push({minute,finals:0,latencies:[],gaps:[],dropped_ms:0,overflow_dropped_ms:0,playback_dropped_ms:0,recoveries:0,capture_gaps:0,capture_gap_ms:0});
  if(this.buckets.length>60)this.buckets.shift();const b=this.buckets.at(-1);
  if(e.type==='status'||e.type==='activity')this.status=e.text||this.status;
  if(e.type==='gpu'&&Number.isFinite(e.used_mib))b.gpu_peak_mib=Math.max(b.gpu_peak_mib||0,e.used_mib);
  if(e.type==='partial')this.status=e.phase==='asr'?'已辨識原文，等待翻譯':'正在翻譯';
  if(e.type==='metrics'){
   b.dropped_ms+=Math.max(0,(e.dropped_audio_ms||0)-(this.metrics.dropped_audio_ms||0));
   b.overflow_dropped_ms+=Math.max(0,(e.overflow_dropped_audio_ms||0)-(this.metrics.overflow_dropped_audio_ms||0));
   b.playback_dropped_ms+=Math.max(0,(e.playback_dropped_audio_ms||0)-(this.metrics.playback_dropped_audio_ms||0));
   // Capture pauses (audio stopped arriving, e.g. while the video buffered); not caption delay.
   b.capture_gaps+=Math.max(0,(e.capture_gap_count||0)-(this.metrics.capture_gap_count||0));
   b.capture_gap_ms+=Math.max(0,(e.capture_gap_ms||0)-(this.metrics.capture_gap_ms||0));
   b.recoveries+=Math.max(0,(e.auto_recoveries||0)-(this.metrics.auto_recoveries||0));this.metrics=e;
  }
  if(e.type==='final'){
   b.finals++;this.status=e.translation_unavailable?'翻譯暫停，原文持續辨識中':'已產生字幕，持續收音';
   if(e.translation_unavailable)b.translation_fallbacks=(b.translation_fallbacks||0)+1;
   b.stages??={};
   for(const key of ['capture_to_caption_ms','asr_queue_ms','asr_ms','nmt_queue_ms','nmt_ms','delivery_wait_ms']){
    if(!Number.isFinite(e[key])||e[key]<0)continue;
    const values=b.stages[key]??=[];values.push(e[key]);if(values.length>600)values.shift();
   }
   if(Number.isFinite(e.after_speech_ms))b.latencies.push(e.after_speech_ms);
   if(this.lastFinal!==null)b.gaps.push(this.now()-this.lastFinal);this.lastFinal=this.now();
   if(b.latencies.length>600)b.latencies.shift();if(b.gaps.length>600)b.gaps.shift();
   this.recent.push({id:String(this.now())+'-'+e.seq,original:(e.original||'').slice(0,2000),translation:(e.translation||'').slice(0,2000),at:this.now()});
   if(this.recent.length>10)this.recent.shift();
  }
 }
 snapshot(){
  const p=(xs,q)=>xs.length?[...xs].sort((a,b)=>a-b)[Math.ceil(xs.length*q)-1]:null;
  return {status:this.status,metrics:this.metrics,recent:this.recent,minutes:this.buckets.map(b=>({minute:b.minute,finals:b.finals,dropped_ms:b.dropped_ms,overflow_dropped_ms:b.overflow_dropped_ms,playback_dropped_ms:b.playback_dropped_ms,recoveries:b.recoveries,gpu_peak_mib:b.gpu_peak_mib??null,p50_ms:p(b.latencies,.5),p95_ms:p(b.latencies,.95),stages:Object.fromEntries(Object.entries(b.stages||{}).map(([key,values])=>[key,{count:values.length,p50_ms:p(values,.5),p95_ms:p(values,.95)}])),average_gap_ms:b.gaps.length?b.gaps.reduce((a,c)=>a+c,0)/b.gaps.length:null,capture_gaps:b.capture_gaps,capture_gap_ms:b.capture_gap_ms,
   onset_p50_ms:p(b.stages?.capture_to_caption_ms||[],.5),onset_p95_ms:p(b.stages?.capture_to_caption_ms||[],.95)}))};
 }
}
