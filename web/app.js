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
  go: $("go"), png: $("png"), html: $("html"), status: $("status"),
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
  // A zero-width container (hidden tab, collapsed pane, print) would scale the
  // poster to nothing and it would never come back. Wait for a real width --
  // the ResizeObserver below calls again once there is one.
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

let pyodide = null;
let examples = {};
let current = { html: "", slug: "poster", days: 0 };
const editorState = new OTFEditor.EditorState();
let draftStore=null, activeDraftId=null, savedSuccessfully=false, openingDraft=false;
try { draftStore=new OTFWorkspace.DraftStore(localStorage); } catch { /* Storage may be disabled. */ }
const editor = new ScheduleEditor(document, editorState, () => {
  saveLocal();
  syncControls();
  status("Edits pending — regenerate to update the poster and downloads.");
});

function syncControls() {
  const generated = Boolean(editorState.current);
  for (const id of ['navPoster', 'navDays']) $(id).hidden = !generated;
  els.sourceInputs.hidden = generated;
  els.sourceInputs.disabled = editorState.busy;
  $('sourceComplete').hidden = !generated;
  els.restart.hidden = !generated;
  els.restart.disabled = editorState.busy;
  els.go.disabled = !pyodide || editorState.busy || generated;
  els.regenerate.disabled = !editorState.draft || editorState.busy;
  els.editorFields.disabled = editorState.busy;
  els.png.disabled = els.html.disabled = !editorState.canDownload;
  $('exportMore').disabled=!editorState.canDownload;
  $('undo').disabled=!editorState.canUndo; $('redo').disabled=!editorState.canRedo;
  for(const id of ['draftName','saveCopy','backupDraft','shareDraft'])$(id).disabled=editorState.busy||!generated;
  for(const id of ['openSaved','deleteSaved','backupSaved'])$(id).disabled=editorState.busy||!$('savedPicker').value;
  $('importDraft').disabled=editorState.busy;
  els.editStatus.textContent = editorState.busy ? "Working…" : editorState.dirty
    ? "Edits pending — regenerate before downloading." : "Preview is up to date.";
  for (const button of els.examples.querySelectorAll('button')) button.disabled = editorState.busy;
}

function status(text, isError = false) {
  els.status.textContent = text;
  els.status.classList.toggle("err", isError);
}

function showReport(text) {
  els.report.hidden = !text;
  els.report.textContent = text || "";
}

async function boot() {
  try {
    status("Loading Python runtime (one-off, ~10s)…");
    pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/",
    });

    status("Loading template engine…");
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    try { await micropip.install(["jinja2", "markupsafe"]); }
    finally { micropip.destroy(); }

    status("Loading poster generator…");
    const bundle = await (await fetch("bundle.json")).json();
    examples = bundle.examples || {};

    const FS = pyodide.FS;
    FS.mkdir("/app");
    for (const [path, content] of Object.entries(bundle.files)) {
      const parts = path.split("/");
      let dir = "/app";
      for (const part of parts.slice(0, -1)) {
        dir += "/" + part;
        try { FS.mkdir(dir); } catch (e) { /* already there */ }
      }
      FS.writeFile("/app/" + path, content, { encoding: "utf8" });
    }
    pyodide.runPython(`import sys; sys.path.insert(0, "/app")`);
    pyodide.runPython("from browser_bridge import generate, regenerate, export_schedule");

    renderExampleButtons();
    syncControls();
    els.go.textContent = "Generate poster";
    status("Ready — paste a monthly thread and hit Generate.");
    await restoreStartup();
  } catch (err) {
    console.error(err);
    pyodide = null;
    els.go.textContent = "Generate poster";
    status("Could not start: " + err.message, true);
  }
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
      savePaste();
      status(`Loaded the ${slug} thread — hit Generate.`);
      showReport("");
    };
    els.examples.appendChild(b);
  }
}

async function generate() {
  if (!pyodide || editorState.busy || editorState.current) return;
  const text = els.src.value.trim();
  if (!text) { status("Paste the monthly thread first.", true); return; }
  await renderPoster("generate", [text, els.month.value.trim() || null]);
}

function restartFromText() {
  if (editorState.busy || !editorState.current) return;
  $('restartExplanation').textContent=savedSuccessfully
    ? 'This clears the current editing session. Your saved poster and original text will be kept, so you can return to them. Generate again to start a separate fresh poster.'
    : 'This removes the current customizations. Autosave is unavailable: download a draft backup first if you want to keep these edits. Your original text will stay in the text box.';
  $('restartDialog').showModal();
}

function confirmRestart() {
  if (editorState.busy || !editorState.current) return;
  $('restartDialog').close();
  const previouslySaved=savedSuccessfully;
  saveLocal();
  if(previouslySaved && !savedSuccessfully){status('Autosave failed. Your draft is still open; download a backup before restarting.',true);return;}
  activeDraftId=null; savedSuccessfully=false;
  $('draftName').value='';
  $('lastDownload').hidden=true;
  try { draftStore?.clearActive(); } catch { /* Previous save message already explains failure. */ }
  editorState.reset();
  savePaste();
  current = {html:'', slug:'poster', days:0};
  editor.selectedDay = editor.selectedKeyDate = editor.selectionMonth = null;
  for (const id of ['titleSection','keyDateSection','workoutSection','notesSection','monthlyNotesSection','eventsSection','additionalInfoSection','creditsSection']) $(id).open = false;
  els.previewWrap.hidden = $('editorWrap').hidden = true;
  els.preview.srcdoc = '';
  els.png.hidden = els.html.hidden = true;
  previewFullSize = false;
  els.stage.classList.toggle('full-size', false);
  $('previewZoom').textContent = 'View full size';
  $('previewZoom').setAttribute('aria-pressed', 'false');
  showReport(''); syncControls();
  status('Edit your original text, then select Generate poster to start again.');
  els.src.focus();
}

async function regenerate() {
  if (!editorState.draft || editorState.busy) return;
  const errors = OTFEditor.validateDraft(editorState.draft);
  if (errors.length) {
    showReport(errors.join("\n"));
    status("Fix the editor errors before regenerating.", true);
    els.editStatus.textContent = errors.join(" ");
    return;
  }
  await renderPoster("regenerate", [JSON.stringify(editorState.draft)]);
}

async function renderPoster(method, args, options={}) {
  if (!editorState.begin()) return;
  let failure = "";
  syncControls();
  status(method === "generate" ? "Parsing and rendering…" : "Rendering your edits…");
  await new Promise(resolve => setTimeout(resolve, 30));
  try {
    const fn = pyodide.globals.get(method);
    let res;
    try { res = JSON.parse(fn(...args)); }
    finally { fn.destroy(); }
    els.previewWrap.hidden = false;
    await new Promise((resolve) => {
      els.preview.onload = resolve;
      els.preview.srcdoc = res.html;
    });
    const doc = els.preview.contentDocument;
    if (doc.fonts && doc.fonts.status !== "loaded") await doc.fonts.ready;
    current = { html: res.html, slug: res.slug, days: res.days };
    if(options.fresh)editorState.reset();
    editorState.accept(res);
    if(options.state)editorState.restore(options.state);
    editor.render();
    fitPreview();
    els.png.hidden = els.html.hidden = false;
    showReport(res.notes);

    if (res.errors.length) {
      status(`Rendered, but ${res.errors.length} problem(s) found — see below.`, true);
    } else if (res.notes) {
      status("Rendered with warnings — see below.");
    } else {
      status("Rendered cleanly.");
    }
    if (method === 'generate') $('posterTitle').focus();
    if(!openingDraft)saveLocal();
  } catch (err) {
    console.error(err);
    const msg = String(err.message || err).trim().split("\n").pop();
    failure = (method === "generate" ? "Could not parse that: " : "Could not regenerate: ") + msg;
    status(failure, true);
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
    $('saveStatus').textContent='Saved on this device.';refreshSaved();
  }catch(err){$('saveStatus').textContent='Not saved: '+err.message+' Download a draft backup before closing.';}
}
function refreshSaved() {
  if(!draftStore)return;
  try {
    const picker=$('savedPicker'), selected=activeDraftId || picker.value;
    picker.replaceChildren();
    const blank=document.createElement('option');blank.value='';blank.textContent='Choose a saved poster';picker.append(blank);
    const documents=draftStore.list();
    for(const doc of documents){
      const option=document.createElement('option');option.value=doc.id;
      option.textContent=doc.name+(doc.updatedAt?' · '+new Date(doc.updatedAt).toLocaleDateString():'');picker.append(option);
    }
    picker.value=documents.some(doc=>doc.id===selected)?selected:'';syncControls();
  }catch(err){$('saveStatus').textContent='Cannot read saved posters: '+err.message;}
}
async function openDocument(doc,newCopy=false) {
  if(editorState.busy)return;
  if(editorState.draft && !savedSuccessfully){saveLocal();if(!savedSuccessfully){status('Download your current draft before opening another poster.',true);return;}}
  openingDraft=true;
  try {
    const ok=await renderPoster('regenerate',[JSON.stringify(doc.state.rendered)],{fresh:true,state:doc.state});
    if(!ok)return;
    activeDraftId=newCopy?crypto.randomUUID():doc.id;
    els.src.value=doc.source||'';els.month.value='';$('draftName').value=(doc.name || current.slug)+(newCopy?' (copy)':'');
    status(editorState.dirty?'Restored your draft with pending edits. Regenerate when ready.':'Saved poster restored.');
  }finally{openingDraft=false;}
  saveLocal();syncControls();
}
async function restoreStartup() {
  refreshSaved();
  try {
    if(location.hash.startsWith('#draft=')){
      const data=await OTFWorkspace.decodeShare(location.hash.slice(7));
      await openDocument(OTFWorkspace.decodeBackup(JSON.stringify(data)),true);
      history.replaceState(null,'',location.href.split('#')[0]);
    }else if(draftStore?.active){await openDocument(draftStore.load(draftStore.active));}
    else {const source=draftStore?.readSource();if(source){els.src.value=source.text;els.month.value=source.month;$('saveStatus').textContent='Restored your unfinished paste.';}}
  }catch(err){$('saveStatus').textContent=err.message+' Existing saved posters have been kept.';}
}
function historyChange(action){if(editorState.busy)return;editorState[action]();editor.render();saveLocal();syncControls();}
function savePaste(){
  if(editorState.current)return;
  try{if(!draftStore)throw new Error('Browser storage is unavailable.');draftStore.saveSource(els.src.value,els.month.value);$('saveStatus').textContent='Thread text saved on this device.';}
  catch(err){$('saveStatus').textContent='Thread text could not be saved: '+err.message;}
}
els.src.oninput=els.month.oninput=savePaste;
$('undo').onclick=()=>historyChange('undo');$('redo').onclick=()=>historyChange('redo');
$('draftName').oninput=saveLocal;
$('saveCopy').onclick=()=>{activeDraftId=crypto.randomUUID();$('draftName').value=($('draftName').value||current.slug)+' (copy)';saveLocal();};
$('backupDraft').onclick=()=>{if(editorState.draft)download(new Blob([JSON.stringify(draftDocument(),null,2)],{type:'application/json'}),`otf_${current.slug}_draft.json`);};
$('savedPicker').onchange=syncControls;
$('openSaved').onclick=async()=>{try{await openDocument(draftStore.load($('savedPicker').value));}catch(err){$('saveStatus').textContent=err.message;}};
$('backupSaved').onclick=()=>{try{download(new Blob([draftStore.raw($('savedPicker').value)],{type:'application/json'}),'otf_saved_draft.json');}catch(err){$('saveStatus').textContent=err.message;}};
let deletingId=null;
$('deleteSaved').onclick=()=>{deletingId=$('savedPicker').value;if(deletingId)$('deleteDialog').showModal();};
$('deleteCancel').onclick=()=>$('deleteDialog').close();
$('deleteConfirm').onclick=()=>{
  try{draftStore.remove(deletingId);if(deletingId===activeDraftId){activeDraftId=null;savedSuccessfully=false;}refreshSaved();$('saveStatus').textContent='Saved poster deleted. The open editor is unchanged.';}
  catch(err){$('saveStatus').textContent=err.message;}$('deleteDialog').close();
};
$('importDraft').onchange=async()=>{
  const file=$('importDraft').files?.[0];if(!file)return;
  try{if(file.size>2_000_000)throw new Error('Draft file is too large.');await openDocument(OTFWorkspace.decodeBackup(await file.text()),true);}
  catch(err){$('saveStatus').textContent='Import failed: '+err.message;}finally{$('importDraft').value='';}
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

els.html.onclick = () => {
  if (!editorState.canDownload) return;
  download(new Blob([current.html], { type: "text/html" }),
           `otf_${current.slug}.html`);
};

els.png.onclick = async () => {
  if (!editorState.canDownload) return;
  const doc = els.preview.contentDocument;
  const node = doc && doc.querySelector(".poster");
  if (!node) { status("Preview isn't ready yet.", true); return; }

  if (!editorState.begin()) return;
  syncControls();
  status("Rendering PNG…");
  try {
    // Wait for the inlined webfonts inside the iframe before rasterising,
    // otherwise the capture lands mid-swap and the headings come out wrong.
    if (doc.fonts && doc.fonts.status !== "loaded") await doc.fonts.ready;
    const dataUrl = await htmlToImage.toPng(node, {
      pixelRatio: 2,
      width: node.offsetWidth,
      height: node.offsetHeight,
      backgroundColor: "#ffffff",
      cacheBust: false,
    });
    const blob = await (await fetch(dataUrl)).blob();
    download(blob, `otf_${current.slug}.png`);
    status("PNG downloaded.");
  } catch (err) {
    console.error(err);
    status("PNG export failed — use Download HTML and print to PDF instead.", true);
  } finally {
    editorState.finish();
    syncControls();
  }
};

els.go.onclick = generate;
$('exportMore').onclick=async()=>{
  if(!editorState.canDownload||!editorState.begin())return;
  syncControls();const kind=$('exportFormat').value;let frame=null;
  status('Preparing your export…');
  try{
    if(kind==='pdf'){
      const doc=els.preview.contentDocument;await doc.fonts.ready;
      download(await OTFExports.posterPDF(doc.querySelector('.poster'),htmlToImage,PDFLib),`otf_${current.slug}.pdf`);
    }else{
      const fn=pyodide.globals.get('export_schedule');let data;
      try{data=JSON.parse(fn(JSON.stringify(editorState.draft),kind));}finally{fn.destroy();}
      if(kind==='ics')download(new Blob([data.text],{type:'text/calendar;charset=utf-8'}),`otf_${current.slug}.ics`);
      else{
        frame=document.createElement('iframe');frame.title='Preparing image export';
        frame.style.cssText=`position:fixed;left:-20000px;top:0;width:${data.width}px;height:${data.height}px;border:0;`;
        document.body.appendChild(frame);
        await new Promise(resolve=>{frame.onload=resolve;frame.srcdoc=data.html;});
        const doc=frame.contentDocument;await doc.fonts.ready;
        const node=doc.querySelector('.poster'),content=doc.querySelector('.compact-content');
        const style=doc.defaultView.getComputedStyle(node),available=data.height-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom)-16;
        if(content.offsetHeight>available)content.style.transform=`scale(${available/content.offsetHeight})`;
        const url=await htmlToImage.toPng(node,{pixelRatio:1,width:data.width,height:data.height,backgroundColor:'#ffffff'});
        download(await (await fetch(url)).blob(),`otf_${current.slug}_${kind}.png`);
      }
    }
    status('Export downloaded.');
  }catch(err){status('Export failed: '+err.message,true);}
  finally{frame?.remove();editorState.finish();syncControls();}
};
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
// Open disclosures before following their section anchors.
for (const anchor of document.querySelectorAll('a[href="#help"]')) {
  anchor.onclick = () => { $(anchor.getAttribute('href').slice(1)).open = true; };
}
addEventListener('beforeunload', event => {
  if (editorState.draft && !savedSuccessfully) { event.preventDefault(); event.returnValue = ''; }
});
addEventListener('storage',event=>{
  if(activeDraftId && event.key==='otf-draft:'+activeDraftId){
    // Another tab changed the same saved poster. Keep both edits as separate copies.
    activeDraftId=crypto.randomUUID();$('draftName').value+=' (this tab)';saveLocal();
    $('saveStatus').textContent='Another tab changed this poster. Your edits were saved as a separate copy.';
  }else refreshSaved();
});
// Tracks the container, not just the window: catches the panel becoming
// visible, a collapsed pane opening, and plain window resizes alike.
new ResizeObserver(fitPreview).observe(els.stage);
boot();
