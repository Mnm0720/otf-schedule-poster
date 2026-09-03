(function(root){
 function pageSlices(height,maxHeight,boundaries){
   const slices=[];let top=0;
   while(top<height){let end=Math.min(height,top+maxHeight);
     if(end<height){const safe=boundaries.filter(y=>y>top+maxHeight*.3 && y<=end);if(safe.length)end=Math.max(...safe);}
     slices.push([top,end]);top=end;
   }return slices;
 }
 async function posterPDF(node,htmlToImage,PDFLib){
   const canvas=await htmlToImage.toCanvas(node,{pixelRatio:2,backgroundColor:'#ffffff'});
   const pageWidth=595.28,pageHeight=841.89,margin=24,scale=(pageWidth-margin*2)/node.offsetWidth;
   const maxHeight=Math.floor((pageHeight-margin*2)/scale);
   // Cut after whole sections/rows, never through a short card in a parallel column.
   const box=node.getBoundingClientRect();
   const blocks=[...node.querySelectorAll('tr,.strength,.row3,.bottom,.poster-extra,.poster-credits')].map(el=>el.getBoundingClientRect());
   const ratio=node.offsetHeight/box.height;
   const boundaries=blocks.map(b=>Math.ceil((b.bottom-box.top)*ratio)).filter(y=>
     !blocks.some(b=>(b.top-box.top)*ratio+2<y && (b.bottom-box.top)*ratio-2>y));
   const pdf=await PDFLib.PDFDocument.create();
   for(const [top,end] of pageSlices(node.offsetHeight,maxHeight,boundaries)){
     const crop=document.createElement('canvas');crop.width=canvas.width;crop.height=(end-top)*2;
     crop.getContext('2d').drawImage(canvas,0,top*2,canvas.width,crop.height,0,0,crop.width,crop.height);
     const img=await pdf.embedPng(crop.toDataURL('image/png'));
     const page=pdf.addPage([pageWidth,pageHeight]);const h=(end-top)*scale;
     page.drawImage(img,{x:margin,y:pageHeight-margin-h,width:pageWidth-margin*2,height:h});
   }
   return new Blob([await pdf.save()],{type:'application/pdf'});
 }
 const api={pageSlices,posterPDF};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OTFExports=api;
})(globalThis);
