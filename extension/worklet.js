// Energy packetizer; backend Silero validates speech and applies adaptive endpointing.
class Segmenter extends AudioWorkletProcessor{
 constructor(options){super();this.live=options?.processorOptions?.live===true;this.acc=0;this.sum=0;this.count=0;this.samples=[];this.quiet=0;this.voiced=false;
  this.port.onmessage=({data})=>{if(data==='reset'){this.resetAudioState();this.port.postMessage({resetDone:true});return;}if(data==='flush'){this.emit();if(this.live)this.port.postMessage({flush:true});}};
 }
 resetAudioState(){this.samples=[];this.acc=0;this.sum=0;this.count=0;this.quiet=0;this.voiced=false;}
 emit(){if(this.samples.length&&(this.live||this.voiced))this.port.postMessage(new Float32Array(this.samples));this.samples=[];this.quiet=0;this.voiced=false;}
 process(inputs,outputs){
  const channels=inputs[0];if(!channels?.length)return true;
  let energy=0;for(let i=0;i<channels[0].length;i++){let x=0;for(const c of channels)x+=c[i];energy+=(x/channels.length)**2;}
  const speech=Math.sqrt(energy/channels[0].length)>.006;
  if(speech){this.voiced=true;this.quiet=0;}else this.quiet+=channels[0].length/sampleRate;
  for(let i=0;i<channels[0].length;i++){
   let x=0;for(const c of channels)x+=c[i];x/=channels.length;
   this.sum+=x;this.count++;this.acc+=16000;
   if(this.acc>=sampleRate){this.acc-=sampleRate;this.samples.push(this.sum/this.count);this.sum=0;this.count=0;}
   if(this.samples.length===(this.live?5120:96000))this.emit();
  }
  if(!this.live&&this.samples.length>=12800&&this.quiet>=(this.samples.length>=48000?.24:.45))this.emit();
  return true;
 }
}
registerProcessor('segmenter',Segmenter);
