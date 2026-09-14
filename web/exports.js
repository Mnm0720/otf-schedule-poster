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
   const pageWidth=595.28,pageHeight=841.89,margin=24;
   const availW=pageWidth-margin*2, availH=pageHeight-margin*2;
   const scale=Math.min(availW/node.offsetWidth, availH/node.offsetHeight);
   const w=node.offsetWidth*scale, h=node.offsetHeight*scale;
   const pdf=await PDFLib.PDFDocument.create();
   const img=await pdf.embedPng(canvas.toDataURL('image/png'));
   const page=pdf.addPage([pageWidth,pageHeight]);
   page.drawImage(img,{x:margin,y:pageHeight-margin-h,width:w,height:h});
   return new Blob([await pdf.save()],{type:'application/pdf'});
 }
 const api={pageSlices,posterPDF};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OTFExports=api;
})(globalThis);
