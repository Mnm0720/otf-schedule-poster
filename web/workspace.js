/* Versioned local drafts and portable snapshots; no server or accounts. */
(function(root){
 const PREFIX='otf-draft:', ACTIVE='otf-active', MAX=2_000_000;
 const clone=v=>JSON.parse(JSON.stringify(v));
 function validSchedule(d){
   if(!d || typeof d!=='object' || !Number.isInteger(d.year) || d.year<1900 || d.year>9998 ||
      !Number.isInteger(d.month) || d.month<1 || d.month>12 || !Array.isArray(d.days) || !d.days.length || d.days.length>31)
     throw new Error('Invalid schedule in draft.');
   if((d.schema_version??1)>2)throw new Error('This schedule needs a newer app version.');
   const length=new Date(Date.UTC(d.year,d.month,0)).getUTCDate(),seen=new Set();
   for(const day of d.days){
     if(!Number.isInteger(day.day)||day.day<1||day.day>length||seen.has(day.day)||!Array.isArray(day.entries))throw new Error('Invalid dates in draft.');
     seen.add(day.day);
     for(const e of day.entries)if(!e||typeof e.category!=='string')throw new Error('Invalid workout in draft.');
   }
   return d;
 }
 function decodeBackup(text){
   if(text.length>MAX)throw new Error('Draft file is too large.');
   let data;try{data=JSON.parse(text);}catch{throw new Error('Cannot read draft JSON. The original data has been kept.');}
   if(data?.version!==undefined && data.version!==1)throw new Error('Unsupported draft version. Keep this backup for a newer app.');
   // Plain Month JSON and v1 portable shares migrate into the v1 workspace envelope.
   if(!data?.state){const d=validSchedule(data?.schedule || data);data={version:1,name:data.name||`${d.year}-${String(d.month).padStart(2,'0')}`,source:'',state:{draft:d,rendered:d,initial:d,past:[],future:[]}};}
   if(data.version!==1)throw new Error('Unsupported draft version.');
   for(const key of ['draft','rendered','initial'])validSchedule(data.state[key]);
   for(const key of ['past','future']){
     if(!Array.isArray(data.state[key])||data.state[key].length>100)throw new Error('Invalid draft history.');
     data.state[key].forEach(validSchedule);
   }
   // Pick explicit fields so imported values cannot replace controller properties.
   return {version:1,id:typeof data.id==='string'?data.id:'',name:String(data.name||'Saved poster').slice(0,120),
     source:typeof data.source==='string'?data.source:'',updatedAt:data.updatedAt||'',
     state:clone({draft:data.state.draft,rendered:data.state.rendered,initial:data.state.initial,past:data.state.past,future:data.state.future})};
 }
 class DraftStore {
   constructor(storage){this.storage=storage;this.observed=new Map();}
   load(id){const raw=this.storage.getItem(PREFIX+id);if(!raw)throw new Error('Saved poster not found.');const doc=decodeBackup(raw);this.observed.set(id,raw);return {...doc,id};}
   save(doc){
     const old=this.storage.getItem(PREFIX+doc.id);if(old)decodeBackup(old);
     if(old && this.observed.get(doc.id)!==old)throw new Error('This poster changed in another tab. Save a separate copy.');
     const data={...doc,version:1,updatedAt:new Date().toISOString()};
     const text=JSON.stringify(data);decodeBackup(text);
     this.storage.setItem(PREFIX+doc.id,text);this.observed.set(doc.id,text);this.storage.setItem(ACTIVE,doc.id);return data;
   }
   list(){
     const docs=[];
     for(let i=0;i<this.storage.length;i++){const key=this.storage.key(i);if(!key?.startsWith(PREFIX))continue;
       const id=key.slice(PREFIX.length);try{docs.push({...decodeBackup(this.storage.getItem(key)),id});}catch{docs.push({id,name:'Unreadable draft — download a backup',broken:true});}}
     return docs.sort((a,b)=>(b.updatedAt||'').localeCompare(a.updatedAt||''));
   }
   get active(){return this.storage.getItem(ACTIVE);}
   clearActive(){this.storage.removeItem(ACTIVE);}
   remove(id){this.storage.removeItem(PREFIX+id);if(this.active===id)this.clearActive();}
   raw(id){return this.storage.getItem(PREFIX+id);}
   readSource(){
     const raw=this.storage.getItem('otf-source');if(!raw)return null;
     const source=JSON.parse(raw);
     if(source?.version!==1 || typeof source.text!=='string' || typeof source.month!=='string')throw new Error('Cannot read the saved source version.');
     return source;
   }
   saveSource(text,month){this.readSource();this.storage.setItem('otf-source',JSON.stringify({version:1,text,month}));}
 }
 async function transform(bytes,mode){
   const stream=new Blob([bytes]).stream().pipeThrough(mode==='zip'?new CompressionStream('gzip'):new DecompressionStream('gzip'));
   const reader=stream.getReader();const chunks=[];let size=0;
   while(true){const {value,done}=await reader.read();if(done)break;size+=value.length;
     if(size>MAX){await reader.cancel();throw new Error('Shared draft is too large.');}chunks.push(value);}
   const out=new Uint8Array(size);let offset=0;for(const chunk of chunks){out.set(chunk,offset);offset+=chunk.length;}return out;
 }
 async function encodeShare(data){
   decodeBackup(JSON.stringify(data));
   const bytes=await transform(new TextEncoder().encode(JSON.stringify(data)),'zip');
   let binary='';for(const b of bytes)binary+=String.fromCharCode(b);
   const text=btoa(binary).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
   if(text.length>12000)throw new Error('This draft is too large for a reliable link. Download a draft file instead.');
   return text;
 }
 async function decodeShare(text){
   if(text.length>20000)throw new Error('Shared draft is too large.');
   try{
     const binary=atob(text.replace(/-/g,'+').replace(/_/g,'/'));
     const bytes=await transform(Uint8Array.from(binary,c=>c.charCodeAt(0)),'unzip');
     const data=JSON.parse(new TextDecoder().decode(bytes));decodeBackup(JSON.stringify(data));return data;
   }catch(err){throw new Error('Cannot open shared draft: '+err.message);}
 }
 const api={DraftStore,decodeBackup,encodeShare,decodeShare,validSchedule};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OTFWorkspace=api;
})(globalThis);
