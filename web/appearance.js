/* Reusable style snapshots deliberately exclude schedule and date-linked copy. */
(function(root){
  'use strict';
  const clone=value=>JSON.parse(JSON.stringify(value));
  const fields=['appearance','category_styles','note_style','footnote_styles','credits'];
  const flags=['calendar_icons','show_marked_dates','show_highlights','show_repeat_map','show_workout_guide'];
  const object=value=>value && typeof value==='object' && !Array.isArray(value);
  function style(value){
    if(!object(value))throw new Error('Preset style must be an object.');
    for(const [key,item] of Object.entries(value)){
      if(key==='color' && typeof item==='string' && /^#[0-9a-f]{6}$/i.test(item))continue;
      if(key==='icon' && typeof item==='string' && /^[a-z_]+$/.test(item))continue;
      if(key==='visible' && typeof item==='boolean')continue;
      throw new Error('Preset contains an invalid style setting.');
    }
  }
  function validatePreset(preset){
    if(!object(preset) || preset.version!==1)throw new Error('Unsupported appearance preset version.');
    if(typeof preset.name!=='string' || !preset.name.trim() || preset.name.length>80)throw new Error('Give the preset a name of 1–80 characters.');
    if(!object(preset.settings))throw new Error('Preset settings must be an object.');
    for(const [key,value] of Object.entries(preset.settings)){
      if(!fields.includes(key))throw new Error('Preset contains schedule data or unsupported settings.');
      if(key==='credits'){if(typeof value!=='string' || value.length>4000)throw new Error('Preset credits must be plain text.');continue;}
      if(!object(value))throw new Error('Preset settings must be objects.');
      if(key==='appearance'){
        for(const [setting,item] of Object.entries(value)){
          if(setting==='layout' && ['clean','reference'].includes(item))continue;
          if(setting==='density' && ['comfortable','compact'].includes(item))continue;
          if(flags.includes(setting) && typeof item==='boolean')continue;
          throw new Error(`Unsupported preset ${setting}.`);
        }
      }else if(key==='note_style')style(value);
      else for(const [name,item] of Object.entries(value)){
        if(!/^[a-z0-9_:-]+$/i.test(name) || (key==='category_styles' && name.startsWith('custom_')))throw new Error('Preset contains unsupported workout styles.');
        style(item);
      }
    }
    if(JSON.stringify(preset).length>64000)throw new Error('Appearance preset is too large.');
    return clone(preset);
  }
  function capturePreset(schedule,name){
    const settings={};
    for(const key of fields)settings[key]=clone(schedule[key] ?? (key==='credits'?'':{}));
    settings.category_styles=Object.fromEntries(Object.entries(settings.category_styles).filter(([key])=>!key.startsWith('custom_')));
    return validatePreset({version:1,name:name.trim(),settings});
  }
  function applyPreset(schedule,preset){
    const safe=validatePreset(preset), result=clone(schedule);
    for(const [key,value] of Object.entries(safe.settings)){
      result[key]=key==='category_styles'
        ? {...Object.fromEntries(Object.entries(result.category_styles||{}).filter(([name])=>name.startsWith('custom_'))),...clone(value)}
        : clone(value);
    }
    return result;
  }
  class PresetStore{
    static KEY='otf-appearance-presets-v1';
    constructor(storage){this.storage=storage;}
    read(){
      const raw=this.storage.getItem(PresetStore.KEY);
      if(raw===null)return {version:1,presets:[],defaultName:null};
      let data;try{data=JSON.parse(raw);}catch{throw new Error('Appearance preset storage is corrupt; export your current style before repairing it.');}
      if(!object(data)||data.version!==1||!Array.isArray(data.presets)||data.presets.length>20)throw new Error('Unsupported appearance preset storage; existing data was kept.');
      data.presets=data.presets.map(validatePreset);
      if(data.defaultName!==null && typeof data.defaultName!=='string')throw new Error('Invalid default appearance preset.');
      return data;
    }
    list(){return this.read().presets;}
    defaultPreset(){const data=this.read();return data.presets.find(p=>p.name===data.defaultName)||null;}
    save(preset,makeDefault=false){
      const safe=validatePreset(preset),data=this.read();
      data.presets=data.presets.filter(p=>p.name!==safe.name);data.presets.push(safe);
      if(data.presets.length>20)throw new Error('Keep at most 20 appearance presets.');
      if(makeDefault)data.defaultName=safe.name;
      this.storage.setItem(PresetStore.KEY,JSON.stringify(data));return safe;
    }
    clearDefault(){const data=this.read();data.defaultName=null;this.storage.setItem(PresetStore.KEY,JSON.stringify(data));}
  }
  const api={capturePreset,applyPreset,validatePreset,PresetStore};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OTFAppearance=api;
})(globalThis);
