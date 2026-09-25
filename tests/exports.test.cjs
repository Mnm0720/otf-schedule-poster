const {test}=require('node:test');
const assert=require('node:assert/strict');
const {posterPDF}=require('../web/exports.js');

for(const [name,width,height] of [['tall poster',1200,4800],['wide poster',2000,1000]]) {
 test(`PDF exports the entire ${name} on one A4 page without clipping`,async()=>{
  const node={offsetWidth:width,offsetHeight:height};
  const image={id:'complete poster'};const pages=[];const drawings=[];
  const png='data:image/png;base64,complete-image';
  let captures=0;
  const htmlToImage={async toCanvas(target,options){
   captures++;assert.equal(target,node);
   assert.deepEqual(options,{pixelRatio:2,backgroundColor:'#ffffff'});
   return {toDataURL(type){assert.equal(type,'image/png');return png;}};
  }};
  const PDFLib={PDFDocument:{async create(){return {
   async embedPng(data){assert.equal(data,png);return image;},
   addPage(size){pages.push(size);return {drawImage(img,placement){assert.equal(img,image);drawings.push(placement);}};},
   async save(){return new Uint8Array([37,80,68,70]);}
  };}}};
  const blob=await posterPDF(node,htmlToImage,PDFLib);
  assert.equal(captures,1);assert.deepEqual(pages,[[595.28,841.89]]);
  assert.equal(drawings.length,1);
  const placement=drawings[0];
  assert.deepEqual(Object.keys(placement).sort(),['height','width','x','y']);
  assert.ok(placement.x>=24 && placement.y>=24-1e-9);
  assert.ok(placement.x+placement.width<=595.28-24+1e-9);
  assert.ok(placement.y+placement.height<=841.89-24+1e-9);
  assert.ok(Math.abs(placement.width/placement.height-width/height)<1e-9,'aspect ratio is preserved');
  assert.ok(Math.abs(placement.width-(595.28-48))<1e-9 || Math.abs(placement.height-(841.89-48))<1e-9,'the poster fills the available width or height');
  assert.equal(blob.type,'application/pdf');assert.equal(blob.size,4);
 });
}

test('PDF capture failures reject instead of returning an incomplete download',async()=>{
 const htmlToImage={async toCanvas(){throw new Error('Image capture failed');}};
 await assert.rejects(posterPDF({offsetWidth:1200,offsetHeight:4800},htmlToImage,{}),/Image capture failed/);
});
