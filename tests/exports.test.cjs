const {test}=require('node:test');const assert=require('node:assert/strict');
test('PDF pagination covers all pixels, prefers safe boundaries, and handles long blocks',()=>{
 const {pageSlices}=require('../web/exports.js');
 assert.deepEqual(pageSlices(2800,1500,[800,1400,1900,2800]),[[0,1400],[1400,2800]]);
 assert.deepEqual(pageSlices(4000,1500,[]),[[0,1500],[1500,3000],[3000,4000]]);
});
