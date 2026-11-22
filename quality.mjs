export function decodeContext(header=''){
 if(header.length>8000)throw Error('前文過長');
 const x=header?JSON.parse(decodeURIComponent(header)):[];
 if(!Array.isArray(x)||x.length>2||x.some(s=>typeof s!=='string'||s.length>300))throw Error('前文必須為最多兩段日文');
 return x;
}
export function validateGlossary(x){
 if(!Array.isArray(x)||x.length>100||x.some(t=>!t||typeof t.ja!=='string'||typeof t.zh!=='string'||!t.ja.trim()||!t.zh.trim()||t.ja.length>60||t.zh.length>60))throw Error('glossary.json 格式錯誤，請使用 ja/zh 短詞陣列');
 return x;
}
