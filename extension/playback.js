// Observe the actual player, including Twitch replacing its video element.
(()=>{
 if(window.__mosaPlayback)return;window.__mosaPlayback=true;
 let video=null,dirty=false,waitingAt=null,lastReset=-Infinity,pauseTimer=null,currentSrc='',adVisible=null;
 const reset=()=>{dirty=false;waitingAt=null;const now=performance.now();if(now-lastReset<500)return;lastReset=now;chrome.runtime.sendMessage({target:'offscreen',type:'resync'}).catch(()=>{});};
 const wait=()=>{waitingAt??=performance.now();};
 const seek=()=>{dirty=true;reset();};
 const emptied=()=>{dirty=true;reset();};
 const sourceChanged=()=>{const src=video?.currentSrc||'';if(src!==currentSrc){currentSrc=src;reset();}};
 const playing=()=>{clearTimeout(pauseTimer);if(dirty||(waitingAt!==null&&performance.now()-waitingAt>=1500))reset();waitingAt=null;};
 const pause=()=>{reset();clearTimeout(pauseTimer);pauseTimer=setTimeout(()=>chrome.runtime.sendMessage({target:'offscreen',type:'playback-paused'}).catch(()=>{}),15000);};
 const handlers={waiting:wait,stalled:emptied,seeking:seek,emptied,playing,pause,loadstart:sourceChanged,loadedmetadata:sourceChanged,durationchange:sourceChanged,timeupdate:sourceChanged,adstart:emptied,adend:emptied};
 const scan=()=>{
  const ad=Boolean(document.querySelector('[data-a-target="video-ad-label"], [data-a-target="video-ad-countdown"]'));
  if(adVisible!==null&&ad!==adVisible)reset();adVisible=ad;
  // Twitch can also render muted preview/chat videos. Prefer its main player.
  const next=document.querySelector('[data-a-target="video-player"] video')||document.querySelector('video.html5-main-video')||document.querySelector('.bpx-player-video-wrap video')||document.querySelector('video');if(next===video){sourceChanged();return;}
  clearTimeout(pauseTimer);
  if(video){for(const [type,fn] of Object.entries(handlers))video.removeEventListener(type,fn);dirty=true;}
  video=next;currentSrc=video?.currentSrc||'';
  if(video){for(const [type,fn] of Object.entries(handlers))video.addEventListener(type,fn);if(dirty)reset();}
 };
 new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['src']});scan();
})();
