/* Runs the real otfposter package in the browser under Pyodide.
 *
 * Nothing here reimplements parsing: bundle.json carries the same .py files and
 * Jinja template that CI uses, they are written into Pyodide's virtual
 * filesystem, and the page just calls into them. A poster generated here is the
 * same poster CI generates.
 */
const $ = (id) => document.getElementById(id);
const els = {
  src: $("src"), month: $("month"), theme: $("theme"), tagline: $("tagline"),
  go: $("go"), png: $("png"), html: $("html"), status: $("status"),
  report: $("report"), preview: $("preview"), previewWrap: $("previewWrap"),
  examples: $("examples"), dims: $("dims"), stage: $("stage"),
  regenerate: $("regenerate"), editorFields: $("editorFields"), editStatus: $("editStatus"),
};

const POSTER_WIDTH = 1200;

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
  const scale = Math.min(available / POSTER_WIDTH, 1);
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
const editor = new ScheduleEditor(document, editorState, () => {
  syncControls();
  status("Edits pending — regenerate to update the poster and downloads.");
});

function syncControls() {
  els.go.disabled = !pyodide || editorState.busy;
  els.regenerate.disabled = !editorState.draft || editorState.busy;
  els.editorFields.disabled = editorState.busy;
  els.png.disabled = els.html.disabled = !editorState.canDownload;
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
    pyodide.runPython("from browser_bridge import generate, regenerate");

    renderExampleButtons();
    syncControls();
    els.go.textContent = "Generate poster";
    status("Ready — paste a monthly thread and hit Generate.");
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
      if (editorState.busy) return;
      els.src.value = examples[slug];
      els.month.value = "";
      els.theme.value = "";
      els.tagline.value = "";
      status(`Loaded the ${slug} thread — hit Generate.`);
      showReport("");
    };
    els.examples.appendChild(b);
  }
}

async function generate() {
  if (!pyodide || editorState.busy) return;
  const text = els.src.value.trim();
  if (!text) { status("Paste the monthly thread first.", true); return; }
  if (editorState.dirty && !confirm("Replace your pending edits with a newly parsed schedule?")) return;
  await renderPoster("generate", [text, els.month.value.trim() || null,
    els.theme.value.trim(), els.tagline.value.trim()]);
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

async function renderPoster(method, args) {
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
    editorState.accept(res);
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
}

function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
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
els.regenerate.onclick = regenerate;
addEventListener('beforeunload', event => {
  if (editorState.dirty) { event.preventDefault(); event.returnValue = ''; }
});
// Tracks the container, not just the window: catches the panel becoming
// visible, a collapsed pane opening, and plain window resizes alike.
new ResizeObserver(fitPreview).observe(els.stage);
boot();
