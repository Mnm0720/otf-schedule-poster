/* Runs the real otfposter package in the browser under Pyodide.
 *
 * Nothing here reimplements parsing: bundle.json carries the same .py files and
 * Jinja template that CI uses, they are written into Pyodide's virtual
 * filesystem, and the page just calls into them. A poster generated here is the
 * same poster CI generates.
 */
const $ = (id) => document.getElementById(id);
const els = {
  src: $("src"), month: $("month"), sourceInputs: $("sourceInputs"), restart: $("restart"),
  go: $("go"), status: $("status"),
  report: $("report"), preview: $("preview"), previewWrap: $("previewWrap"),
  examples: $("examples"), dims: $("dims"), stage: $("stage"),
  regenerate: $("regenerate"), editorFields: $("editorFields"), editStatus: $("editStatus"),
};

const POSTER_WIDTH = 1200;
let previewFullSize = false;

/** Scale the full-size poster iframe down to whatever width the page has. */
function fitPreview() {
  const doc = els.preview.contentDocument;
  const poster = doc && doc.querySelector(".poster");
  if (!poster) return;
  const available = els.stage.clientWidth;
  if (available < 1) return;

  const height = poster.offsetHeight;
  const scale = previewFullSize ? 1 : Math.min(available / POSTER_WIDTH, 1);
  els.preview.style.height = height + "px";
  els.preview.style.transform = `scale(${scale})`;
  els.stage.style.height = Math.round(height * scale) + "px";
  els.dims.textContent =
    `${current.slug} · ${current.days} days · ${POSTER_WIDTH}×${height}`;
}

const runtime = OTFRuntime.createRuntime();
let runtimeReady = false, booting = false;
let sourceTouched = false;
let examples = {};
let current = { html: "", slug: "poster", days: 0 };
const editorState = new OTFEditor.EditorState();
let draftStore=null, activeDraftId=null, savedSuccessfully=false, openingDraft=false;
let saveMessage = '';
try { draftStore=new OTFWorkspace.DraftStore(localStorage); } catch { /* Storage may be disabled. */ }
const editor = new ScheduleEditor(document, editorState, () => {
  saveLocal();
  syncControls();
  status("Edits saved locally when available. Update preview before downloading.");
});

let toastTimer = null;
function showToast(text) {
  const el = $('toast');
  el.textContent = text;
  el.hidden = false;
  el.classList.remove('fade-out');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.add('fade-out');
    setTimeout(() => { el.hidden = true; el.classList.remove('fade-out'); }, 300);
  }, 3000);
}

function syncControls() {
  const generated = Boolean(editorState.current);
  for (const id of ['navPoster', 'navDays']) $(id).hidden = !generated;
  $('examplesWrap').hidden = generated;
  $('sampleSection').hidden = generated;
  $('howTo').hidden = generated;
  els.sourceInputs.hidden = generated;
  els.sourceInputs.disabled = editorState.busy;
  $('sourceComplete').hidden = !generated;
  els.restart.hidden = !generated;
  els.restart.disabled = editorState.busy;
  els.go.disabled = !runtimeReady || editorState.busy || generated;
  els.go.hidden = generated;
  els.regenerate.disabled = !runtimeReady || !editorState.draft || editorState.busy;
  els.editorFields.disabled = editorState.busy;
  $('exportBtn').disabled=!runtimeReady || !editorState.canDownload;
  const undoBtn=$('undo'), redoBtn=$('redo');
  undoBtn.disabled=!runtimeReady || !editorState.canUndo;
  redoBtn.disabled=!runtimeReady || !editorState.canRedo;
  undoBtn.textContent='Previous version';redoBtn.textContent='Next version';
  undoBtn.setAttribute('aria-label',editorState.undoLabel ? `Previous version: ${editorState.undoLabel}` : 'Previous version');
  redoBtn.setAttribute('aria-label',editorState.redoLabel ? `Next version: ${editorState.redoLabel}` : 'Next version');
  for(const id of ['draftName','backupDraft','shareDraft'])$(id).disabled=editorState.busy||!generated;
  $('openDrafts').disabled = editorState.busy || !runtimeReady;
  for(const id of ['openSaved','deleteSaved','backupSaved'])$(id).disabled=editorState.busy||!$('savedPicker').value;
  $('importDraft').disabled=editorState.busy;
  els.editStatus.textContent = editorState.busy ? "Working…" : editorState.dirty
    ? "Preview needs updating. Your pending edits are kept." : editorState.current?.errors?.length
      ? "Fix the schedule errors before downloading." : "Preview is up to date.";
  if(generated && !savedSuccessfully && !editorState.busy)els.editStatus.textContent='Not saved in this browser. Download a draft backup. '+els.editStatus.textContent;
  $('emergencyBackup').hidden=!generated || savedSuccessfully;
  $('emergencyBackup').disabled=editorState.busy;
  $('previewNeedsUpdate').hidden=!generated || (runtimeReady && editorState.canDownload);
  $('readyDownload').hidden=!runtimeReady || !editorState.canDownload;
  $('exportAgain').disabled=!runtimeReady || !editorState.canDownload;
  $('exportShare').disabled=editorState.busy||!generated;
  $('sourceReferenceSection').hidden=!generated;
  $('sourceReference').value=els.src.value;
  for (const button of els.examples.querySelectorAll('button')) button.disabled = editorState.busy;
  updateDraftStatus();
}

function updateDraftStatus() {
  const el = $('draftStatus');
  if (!editorState.current) { el.textContent = saveMessage; return; }
  const name = $('draftName').value.trim() || current.slug;
  el.textContent = `Editing: ${name}`;
  $('autosaveStatus').textContent=saveMessage || 'Draft has not been saved yet.';
  $('autosaveStatus').classList.toggle('err',!savedSuccessfully);
  const d=editorState.draft;
  $('activeMonth').textContent=new Intl.DateTimeFormat('en',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(Date.UTC(d.year,d.month-1,1)));
}

function saveFeedback(text) {
  saveMessage=text;$('saveStatus').textContent=text;$('autosaveStatus').textContent=text;
  $('autosaveStatus').classList.toggle('err',!savedSuccessfully);
  if(!editorState.current){$('draftStatus').textContent=text;}
}

function status(text, isError = false) {
  els.status.textContent = text;
  els.status.classList.toggle("err", isError);
}

function showReport(text) {
  els.report.hidden = Boolean(editorState.current) || !text;
  els.report.textContent = text || "";
}

function showIssues(issues=[]) {
  const list=$('issueList');list.replaceChildren();$('editorIssues').hidden=!issues.length;
  for(const issue of issues){
    const li=document.createElement('li'),message=document.createElement('span');
    message.textContent=(issue.severity==='error'?'Fix before downloading: ':'Review: ')+issue.message;li.append(message);
    const button=document.createElement('button');button.type='button';button.className='ghost';
    button.textContent=issue.day?`Check date ${editorState.draft.month}/${issue.day}`:'Check item';
    button.onclick=()=>editor.focusIssue(issue);li.append(button);list.append(li);
  }
}

function showImportReview() {
  const review=editorState.importReview,summary=review?.summary;
  $('importSummary').textContent=summary ? `${summary.recognizedDays.length} dates explicitly read from the thread; ${summary.inferredDays.length} dates filled as Standard. Review inferred dates in Review all dates.` : '';
  const list=$('importIssues');list.replaceChildren();
  for(const issue of review?.issues||[]){const li=document.createElement('li');li.textContent=issue.message;list.append(li);}
}

function showPendingIssues() {
  const errors=OTFEditor.validateDraft(editorState.draft);
  showIssues(errors.map(message=>({severity:'error',message})));
  showReport(errors.join('\n'));
  status(errors.length ? 'Pending edits restored with errors. Fix the marked items, then update the preview.'
    : 'Pending edits restored. Update preview before downloading.',Boolean(errors.length));
}

function runtimeFailure(err) {
  if(!err?.runtimeUnavailable)return;
  runtimeReady=false;
  $('retryBoot').hidden=false;
}

async function boot() {
  if(booting)return;booting=true;runtimeReady=false;
  $('retryBoot').hidden=true;syncControls();
  try {
    const loaded=await runtime.initialize(text=>status(text));
    examples=loaded.examples||{};runtimeReady=true;
    renderExampleButtons();
    syncControls();
    els.go.textContent = "Generate poster";
    status(editorState.current ? 'Editor reloaded. Your edits are kept.' : 'Ready — paste a monthly thread and hit Generate.');
    if(!editorState.current && !sourceTouched)await restoreStartup();
  } catch (err) {
    console.error(err);
    runtimeReady = false;
    els.go.textContent = "Generate poster";
    status("Could not load the editor. Your text is kept. Check your connection and select Retry loading. " + err.message, true);
    $('retryBoot').hidden=false;
  } finally {booting=false;syncControls();}
}

function renderExampleButtons() {
  const names = Object.keys(examples).sort().reverse();
  els.examples.replaceChildren();
  for (const slug of names) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = slug;
    b.onclick = () => {
      if (editorState.busy || editorState.current) return;
      els.src.value = examples[slug];
      els.month.value = "";
      sourceTouched=true;
      savePaste();
      status(`Loaded the ${slug} thread — hit Generate.`);
      showReport("");
    };
    els.examples.appendChild(b);
  }
}

async function generate() {
  if (!runtimeReady || editorState.busy || editorState.current) return;
  const text = els.src.value.trim();
  if (!text) {
    status("Paste the monthly thread first. Copy the whole Reddit post \u2014 title, prose, and the category lists \u2014 and try again.", true);
    return;
  }
  await renderPoster("generate", [text, els.month.value.trim() || null]);
}

function restartFromText() {
  if (editorState.busy || !editorState.current) return;
  $('restartExplanation').textContent=savedSuccessfully
    ? 'This clears the current editing session. Your saved draft and original text will be kept, so you can return to them. Generate again to start a separate fresh poster.'
    : 'This removes the current customizations. Autosave is unavailable: download a draft backup first if you want to keep these edits. Your original text will stay in the text box.';
  $('restartDialog').showModal();
}

function confirmRestart() {
  if (editorState.busy || !editorState.current) return;
  $('restartDialog').close();
  const previouslySaved=savedSuccessfully;
  saveLocal();
  if(previouslySaved && !savedSuccessfully){status('Autosave failed. Your draft is still open; download a backup before restarting.',true);return;}
  activeDraftId=null; savedSuccessfully=false;saveMessage='';
  $('draftName').value='';
  $('lastDownload').hidden=true;
  $('exportConfirm').hidden=$('exportActions').hidden=true;
  try { draftStore?.clearActive(); } catch { /* Previous save message already explains failure. */ }
  editorState.reset();
  sourceTouched=true;
  savePaste();
  current = {html:'', slug:'poster', days:0};
  editor.selectedDay = editor.selectedKeyDate = editor.selectionMonth = null;
  for (const id of ['titleSection','keyDateSection','workoutSection','notesSection','monthlyNotesSection','eventsSection','additionalInfoSection','creditsSection']) $(id).open = false;
  els.previewWrap.hidden = $('editorWrap').hidden = true;
  els.preview.srcdoc = '';
  previewFullSize = false;
  els.stage.classList.toggle('full-size', false);
  $('previewZoom').textContent = 'View full size';
  $('previewZoom').setAttribute('aria-pressed', 'false');
  showReport('');showIssues();syncControls();
  status('Edit your original text, then select Generate poster to start again.');
  els.src.focus();
}

async function regenerate() {
  if (!runtimeReady || !editorState.draft || editorState.busy) return;
  const errors = OTFEditor.validateDraft(editorState.draft);
  if (errors.length) {
    showReport(errors.join("\n"));
    showIssues(errors.map(message=>({severity:'error',message})));
    status("Fix the editor errors before updating the preview.", true);
    els.editStatus.textContent = errors.join(" ");
    return;
  }
  await renderPoster("regenerate", [JSON.stringify(editorState.draft)]);
}

async function renderPoster(method, args, options={}) {
  const previous={result:editorState.current,state:editorState.current?editorState.snapshot():null,current:{...current},
    html:els.preview.srcdoc,previewHidden:els.previewWrap.hidden,editorHidden:$('editorWrap').hidden,
    selectedDay:editor.selectedDay,selectedKeyDate:editor.selectedKeyDate,selectionMonth:editor.selectionMonth};
  if (!editorState.begin()) return;
  let failure = "";
  syncControls();
  status(method === "generate" ? "Parsing and rendering…" : "Rendering your edits…");
  await new Promise(resolve => setTimeout(resolve, 30));
  try {
    const res = JSON.parse(await runtime.execute(method,args));
    els.previewWrap.hidden = false;
    await new Promise((resolve) => {
      els.preview.onload = resolve;
      els.preview.srcdoc = res.html;
    });
    const doc = els.preview.contentDocument;
    if (doc.fonts && doc.fonts.status !== "loaded") await doc.fonts.ready;
    current = { html: res.html, slug: res.slug, days: res.days };
    if(options.fresh)editorState.reset();
    const checkpoint = options.checkpoint ?? (method === 'regenerate' && !options.fresh);
    editorState.accept(res, {checkpoint});
    if(method==='generate')editorState.importReview={issues:(res.issues||[]).filter(i=>i.source==='import'),summary:res.importSummary||null};
    if(options.state)editorState.restore(options.state);
    editor.render();
    fitPreview();
    showReport(res.notes);
    showIssues(res.issues||[]);showImportReview();

    if (res.errors.length) {
      status(`Rendered, but ${res.errors.length} problem(s) found — see below.`, true);
    } else if (res.notes) {
      status("Rendered with warnings — see below.");
    } else {
      status("Rendered cleanly.");
    }
    if(editorState.dirty)showPendingIssues();
    if (method === 'generate') {
      $('editorTitle').focus({preventScroll:true});
      $('editorWrap').scrollIntoView?.({block:'start'});
    }
    if(!openingDraft)saveLocal();
  } catch (err) {
    console.error(err);
    runtimeFailure(err);
    current=previous.current;
    if(previous.state){editorState.accept(previous.result);editorState.restore(previous.state);}
    else editorState.reset();
    editor.selectedDay=previous.selectedDay;editor.selectedKeyDate=previous.selectedKeyDate;editor.selectionMonth=previous.selectionMonth;
    if(previous.state)editor.render();
    $('editorWrap').hidden=previous.editorHidden;
    if(els.preview.srcdoc!==previous.html)await new Promise(resolve=>{
      els.preview.onload=resolve;els.preview.srcdoc=previous.html||'';
    });
    els.previewWrap.hidden=previous.previewHidden;
    fitPreview();
    const rawMsg = String(err.message || err).trim();
    const isFriendlyParseError = method === "generate" && rawMsg.includes("Technical detail:");
    const msg = isFriendlyParseError ? rawMsg : rawMsg.split("\n").pop();
    const prefix = method === "generate" ? (isFriendlyParseError ? "" : "Could not parse that: ") : "Could not regenerate: ";
    failure = prefix + msg;
    status(failure, true);
    showReport(failure);
    showIssues([{severity:'error',message:failure}]);
  } finally {
    editorState.finish();
    syncControls();
    if (failure) els.editStatus.textContent = failure;
  }
  return !failure;
}

function draftDocument() {
  return {version:1,id:activeDraftId || crypto.randomUUID(),name:$('draftName').value.trim() || current.slug,
    source:els.src.value,state:editorState.snapshot()};
}
function saveLocal() {
  if(!editorState.draft || openingDraft)return;
  savedSuccessfully=false;
  try {
    if(!draftStore)throw new Error('Browser storage is unavailable.');
    activeDraftId ??= crypto.randomUUID();
    if(!$('draftName').value.trim())$('draftName').value=current.slug;
    draftStore.save(draftDocument());savedSuccessfully=true;
    saveFeedback('Saved in this browser.');refreshSaved();
  }catch(err){saveFeedback('Not saved: '+err.message+' Download a draft backup before closing.');}
}
function refreshSaved() {
  if(!draftStore)return;
  try {
    const picker=$('savedPicker'), selected=activeDraftId || picker.value;
    picker.replaceChildren();
    const blank=document.createElement('option');blank.value='';blank.textContent='Choose a saved draft';picker.append(blank);
    const documents=draftStore.list();
    for(const doc of documents){
      const option=document.createElement('option');option.value=doc.id;
      option.textContent=doc.name+(doc.updatedAt?' \xb7 '+new Date(doc.updatedAt).toLocaleDateString():'');picker.append(option);
    }
    picker.value=documents.some(doc=>doc.id===selected)?selected:'';syncControls();
  }catch(err){$('saveStatus').textContent='Cannot read saved drafts: '+err.message;}
}
async function openDocument(doc,newCopy=false) {
  if(editorState.busy)return false;
  if(editorState.draft){saveLocal();if(!savedSuccessfully){saveFeedback('Not saved: download your current draft before opening another.');return false;}}
  openingDraft=true;
  try {
    const ok=await renderPoster('restore',[JSON.stringify(doc.state.rendered)],{fresh:true,state:doc.state});
    if(!ok){$('saveStatus').textContent='Could not open that draft. Your current poster is kept. Try again or choose another draft.';return false;}
    activeDraftId=newCopy?crypto.randomUUID():doc.id;
    els.src.value=doc.source||'';els.month.value='';$('draftName').value=(doc.name || current.slug)+(newCopy?' (copy)':'');
    const name = doc.name || current.slug;
    showToast(`✔ "${name}" draft loaded`);
  }finally{openingDraft=false;}
  saveLocal();syncControls();showImportReview();return true;
}
async function restoreStartup() {
  refreshSaved();
  try {
    if(location.hash.startsWith('#draft=')){
      const data=await OTFWorkspace.decodeShare(location.hash.slice(7));
      if(await openDocument(OTFWorkspace.decodeBackup(JSON.stringify(data)),true))history.replaceState(null,'',location.href.split('#')[0]);
    }else if(draftStore?.active){await openDocument(draftStore.load(draftStore.active));}
    else {const source=draftStore?.readSource();if(source && !els.src.value){els.src.value=source.text;els.month.value=source.month;saveFeedback('Restored your unfinished paste.');}}
  }catch(err){saveFeedback(err.message+' Existing saved drafts have been kept.');}
}
async function historyChange(action){
  if(!runtimeReady || editorState.busy)return;
  if(action==='undo'?!editorState.canUndo:!editorState.canRedo)return;
  const before=editorState.snapshot();
  const movement=editorState[action]();
  editor.render();syncControls();
  if(movement?.pending){saveLocal();syncControls();showPendingIssues();return;}
  if(!await renderPoster('regenerate',[JSON.stringify(editorState.draft)],{checkpoint:false})){
    const message=els.editStatus.textContent;
    editorState.restore(before);editor.render();saveLocal();syncControls();els.editStatus.textContent=message;
  }
}
function savePaste(){
  if(editorState.current)return;
  try{if(!draftStore)throw new Error('Browser storage is unavailable.');draftStore.saveSource(els.src.value,els.month.value);saveFeedback('Thread text saved in this browser.');}
  catch(err){saveFeedback('Thread text could not be saved: '+err.message);}
}
els.src.oninput=els.month.oninput=()=>{sourceTouched=true;savePaste();};
$('undo').onclick=()=>historyChange('undo');$('redo').onclick=()=>historyChange('redo');
$('draftName').oninput=()=>{saveLocal();syncControls();};
$('backupDraft').onclick=()=>{if(editorState.draft)download(new Blob([JSON.stringify(draftDocument(),null,2)],{type:'application/json'}),`otf_${current.slug}_draft.json`);};
$('emergencyBackup').onclick=()=>$('backupDraft').onclick();
$('openDrafts').onclick=()=>{if(!editorState.busy){refreshSaved();$('draftsDialog').showModal();}};
$('closeDrafts').onclick=()=>$('draftsDialog').close();
$('savedPicker').onchange=syncControls;
$('openSaved').onclick=async()=>{
  const selected=$('savedPicker').value;
  try{
    if(await openDocument(draftStore.load(selected)))$('draftsDialog').close();
    else $('savedPicker').value=selected;
    syncControls();
  }catch(err){$('saveStatus').textContent=err.message;}
};
$('backupSaved').onclick=()=>{try{download(new Blob([draftStore.raw($('savedPicker').value)],{type:'application/json'}),'otf_saved_draft.json');}catch(err){$('saveStatus').textContent=err.message;}};
let deletingId=null;
$('deleteSaved').onclick=()=>{deletingId=$('savedPicker').value;if(deletingId)$('deleteDialog').showModal();};
$('deleteCancel').onclick=()=>$('deleteDialog').close();
$('deleteConfirm').onclick=()=>{
  try{draftStore.remove(deletingId);if(deletingId===activeDraftId){activeDraftId=null;savedSuccessfully=false;saveFeedback('Not saved: this draft was deleted. Download a backup or keep editing to save a new copy.');}refreshSaved();$('saveStatus').textContent='Draft deleted. The open editor is unchanged.';}
  catch(err){$('saveStatus').textContent=err.message;}$('deleteDialog').close();
};
$('importDraft').onchange=async()=>{
  const file=$('importDraft').files?.[0];if(!file)return;
  try{if(file.size>2_000_000)throw new Error('Draft file is too large.');
    if(await openDocument(OTFWorkspace.decodeBackup(await file.text()),true))$('draftsDialog').close();syncControls();
  }catch(err){$('saveStatus').textContent='Import failed: '+err.message;}finally{$('importDraft').value='';}
};
$('shareDraft').onclick=async()=>{
  if(!editorState.draft||editorState.busy)return;
  try{
    const encoded=await OTFWorkspace.encodeShare({version:1,name:$('draftName').value||current.slug,
      state:{draft:editorState.draft,rendered:editorState.rendered,initial:editorState.draft,past:[],future:[]}});
    $('shareLink').value=location.href.split('#')[0]+'#draft='+encoded;
    $('shareStatus').textContent='';$('shareDialog').showModal();
  }catch(err){status(err.message,true);}
};
$('closeShare').onclick=()=>$('shareDialog').close();
$('copyShare').onclick=async()=>{
  try{await navigator.clipboard.writeText($('shareLink').value);$('shareStatus').textContent='Link copied. Send it to another mod.';}
  catch{$('shareLink').focus();$('shareLink').select();$('shareStatus').textContent='Select and copy the link above.';}
};

let lastDownloadUrl=null;
function download(blob, name) {
  if(lastDownloadUrl)URL.revokeObjectURL(lastDownloadUrl);
  const url = URL.createObjectURL(blob);
  lastDownloadUrl=url;
  $('lastDownload').href=url;$('lastDownload').textContent='Open '+name;$('lastDownload').hidden=false;
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function doExport() {
  if(!runtimeReady||!editorState.canDownload||!editorState.begin())return;
  syncControls();const kind=$('exportFormat').value;let frame=null;let fileName='';
  status('Preparing your export…');$('exportStatus').textContent='Preparing your download…';
  try{
    const imageLibrary=['png','pdf','phone','social'].includes(kind)?await OTFRuntime.loadExportLibrary('image'):null;
    if(kind==='png'){
      const doc=els.preview.contentDocument;
      const node=doc&&doc.querySelector('.poster');
      if(!node){status("Preview isn't ready yet.",true);return;}
      if(doc.fonts&&doc.fonts.status!=='loaded')await doc.fonts.ready;
      const blob=await imageLibrary.toBlob(node,{pixelRatio:2,width:node.offsetWidth,height:node.offsetHeight,backgroundColor:'#ffffff',cacheBust:false});
      if(!blob)throw new Error('The image could not be created. Try downloading again.');
      fileName=`otf_${current.slug}.png`;
      download(blob,fileName);
    }else if(kind==='html'){
      fileName=`otf_${current.slug}.html`;
      download(new Blob([current.html],{type:'text/html'}),fileName);
    }else if(kind==='pdf'){
      const doc=els.preview.contentDocument;await doc.fonts.ready;
      fileName=`otf_${current.slug}.pdf`;
      const pdfLibrary=await OTFRuntime.loadExportLibrary('pdf');
      download(await OTFExports.posterPDF(doc.querySelector('.poster'),imageLibrary,pdfLibrary),fileName);
    }else{
      const data=JSON.parse(await runtime.execute('export_schedule',[JSON.stringify(editorState.draft),kind]));
      if(kind==='ics'){fileName=`otf_${current.slug}.ics`;download(new Blob([data.text],{type:'text/calendar;charset=utf-8'}),fileName);}
      else{
        frame=document.createElement('iframe');frame.title='Preparing image export';
        frame.style.cssText=`position:fixed;left:-20000px;top:0;width:${data.width}px;height:${data.height}px;border:0;`;
        document.body.appendChild(frame);
        await new Promise(resolve=>{frame.onload=resolve;frame.srcdoc=data.html;});
        const doc=frame.contentDocument;await doc.fonts.ready;
        const node=doc.querySelector('.poster'),content=doc.querySelector('.compact-content');
        const style=doc.defaultView.getComputedStyle(node),available=data.height-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom)-16;
        if(content.offsetHeight>available)content.style.transform=`scale(${available/content.offsetHeight})`;
        const blob=await imageLibrary.toBlob(node,{pixelRatio:1,width:data.width,height:data.height,backgroundColor:'#ffffff'});
        if(!blob)throw new Error('The image could not be created. Try downloading again.');
        fileName=`otf_${current.slug}_${kind}.png`;
        download(blob,fileName);
      }
    }
    status('Export downloaded.');
    const confirm=$('exportConfirm');
    confirm.textContent=`Downloaded ${fileName}. Use Open file to view it.`;
    confirm.hidden=false;$('exportActions').hidden=false;$('exportStatus').textContent='Your file is ready. Check your browser downloads.';
  }catch(err){runtimeFailure(err);status('Export failed: '+err.message,true);$('exportStatus').textContent='Export failed: '+err.message;}
  finally{frame?.remove();editorState.finish();syncControls();}
}

els.go.onclick = generate;
$('retryBoot').onclick=boot;
$('exportBtn').onclick=doExport;
$('exportAgain').onclick=doExport;
$('exportShare').onclick=()=>$('shareDraft').onclick();
els.restart.onclick = restartFromText;
$('restartCancel').onclick = () => $('restartDialog').close();
$('restartConfirm').onclick = confirmRestart;
els.regenerate.onclick = regenerate;
$('previewZoom').onclick = () => {
  previewFullSize = !previewFullSize;
  els.stage.classList.toggle('full-size', previewFullSize);
  $('previewZoom').textContent = previewFullSize ? 'Fit to width' : 'View full size';
  $('previewZoom').setAttribute('aria-pressed', String(previewFullSize));
  els.stage.scrollLeft = els.stage.scrollTop = 0;
  fitPreview();
};
for (const anchor of document.querySelectorAll('a[href="#help"]')) {
  anchor.onclick = () => { $(anchor.getAttribute('href').slice(1)).open = true; };
}
addEventListener('beforeunload', event => {
  if (editorState.draft && !savedSuccessfully) { event.preventDefault(); event.returnValue = ''; }
});
addEventListener('storage',event=>{
  if(activeDraftId && event.key==='otf-draft:'+activeDraftId){
    activeDraftId=crypto.randomUUID();$('draftName').value+=' (this tab)';saveLocal();
    saveFeedback(savedSuccessfully?'Another tab changed this draft. Your edits were saved as a separate copy.':'Not saved: another tab changed this draft. Download a backup of your edits.');
  }else refreshSaved();
});
new ResizeObserver(fitPreview).observe(els.stage);
boot();
