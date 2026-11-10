const test=require('node:test');
const assert=require('node:assert/strict');
const {capturePreset,applyPreset,PresetStore}=require('../web/appearance.js');
const schedule=()=>({year:2026,month:11,theme:'Community',days:[{day:23,entries:[{category:'sig',title:'Strength in Numbers'}],three_g:true}],
 events:[{name:'A',start:1,end:2}],key_dates:[{days:[23],detail:'Named'}],category_styles:{sig:{color:'#123456'},custom_abc:{color:'#654321'}},
 appearance:{layout:'clean',calendar_icons:true},note_style:{icon:'groups',color:'#123456'},footnote_styles:{three_g:{icon:'groups'}},credits:'Image: u/test'});
const storage=()=>{const values=new Map();return {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),values};};

test('preset carries visual choices and credits without source dates or custom workouts',()=>{
 const source=schedule(), preset=capturePreset(source,'My style');
 assert.equal(preset.name,'My style');assert.equal(preset.version,1);
 assert.deepEqual(Object.keys(preset.settings).sort(),['appearance','category_styles','credits','footnote_styles','note_style']);
 assert.deepEqual(preset.settings.category_styles,{sig:{color:'#123456'}});
 const other={...schedule(),month:12,theme:'December',days:[{day:1,entries:[{category:'std'}]}],appearance:{layout:'reference'}};
 const before=JSON.stringify(other), applied=applyPreset(other,preset);
 assert.equal(JSON.stringify(other),before);assert.equal(applied.month,12);assert.equal(applied.theme,'December');
 assert.deepEqual(applied.days,other.days);assert.deepEqual(applied.events,other.events);assert.deepEqual(applied.key_dates,other.key_dates);
 assert.equal(applied.category_styles.sig.color,'#123456');assert.equal(applied.appearance.layout,'clean');
});

test('named presets and the default survive reload without overwriting corrupt stores',()=>{
 const backing=storage(), store=new PresetStore(backing), preset=capturePreset(schedule(),'My style');
 store.save(preset,true);assert.equal(new PresetStore(backing).defaultPreset().name,'My style');
 assert.equal(store.list().length,1);store.save(capturePreset(schedule(),'Other'),false);assert.equal(store.list().length,2);
 backing.setItem(PresetStore.KEY,'{bad');assert.throws(()=>store.list(),/preset/i);
 assert.throws(()=>store.save(preset),/preset/i);assert.equal(backing.getItem(PresetStore.KEY),'{bad');
});

test('failed storage and unsupported/imported data surface without changing the schedule',()=>{
 const source=schedule(), before=JSON.stringify(source);
 const store=new PresetStore({getItem:()=>null,setItem:()=>{throw new Error('quota');}});
 assert.throws(()=>store.save(capturePreset(source,'Style')),/quota/);
 assert.throws(()=>applyPreset(source,{version:99,name:'Future',settings:{}}),/version/i);
 assert.throws(()=>applyPreset(source,{version:1,name:'Unsafe',settings:{appearance:{density:'tiny'}}}),/density/i);
 assert.equal(JSON.stringify(source),before);
});
