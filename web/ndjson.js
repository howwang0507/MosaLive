export async function* readNDJSON(body){
 const reader=body.getReader(),decoder=new TextDecoder();let rest='';
 try{
  while(true){const {done,value}=await reader.read();if(done)break;rest+=decoder.decode(value,{stream:true});
   let i;while((i=rest.indexOf('\n'))>=0){const line=rest.slice(0,i);rest=rest.slice(i+1);if(line.trim())yield JSON.parse(line);}
  }
  rest+=decoder.decode();if(rest.trim())yield JSON.parse(rest);
 }finally{reader.releaseLock();}
}
