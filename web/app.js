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
    await micropip.install(["jinja2", "markupsafe"]);

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
    pyodide.runPython(`
from otfposter.parse import parse
from otfposter.render import render_html
from otfposter import validate
import json

def generate(text, month=None, theme="", tagline=""):
    """Parse a pasted post and render the poster. Returns JSON for JS."""
    year = mo = None
    if month:
        year, mo = (int(p) for p in month.split("-"))
    m, report = parse(text, year=year, month=mo)
    if theme:
        m.theme = theme
    if tagline:
        m.tagline = tagline

    notes = []
    if not report.clean:
        notes.append(report.render())
    issues = validate.check(m)
    errors = [msg for sev, msg in issues if sev == "error"]
    if issues:
        notes.append(validate.report(issues))

    return json.dumps({
        "slug": m.slug,
        "html": render_html(m, allow_fetch=False),
        "notes": "\\n".join(n for n in notes if n.strip()),
        "errors": errors,
        "days": len(m.days),
    })
`);

    renderExampleButtons();
    els.go.disabled = false;
    els.go.textContent = "Generate poster";
    status("Ready — paste a monthly thread and hit Generate.");
  } catch (err) {
    console.error(err);
    els.go.textContent = "Generate poster";
    status("Could not start: " + err.message, true);
  }
}

function renderExampleButtons() {
  const names = Object.keys(examples).sort().reverse();
  els.examples.innerHTML = "";
  for (const slug of names) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = slug;
    b.onclick = () => {
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
  const text = els.src.value.trim();
  if (!text) { status("Paste the monthly thread first.", true); return; }

  els.go.disabled = true;
  status("Parsing and rendering…");
  showReport("");
  els.png.hidden = els.html.hidden = true;

  // A tick, so the browser paints the status before Pyodide blocks the thread.
  await new Promise((r) => setTimeout(r, 30));

  try {
    const fn = pyodide.globals.get("generate");
    const raw = fn(text, els.month.value.trim() || null,
                   els.theme.value.trim(), els.tagline.value.trim());
    fn.destroy();
    const res = JSON.parse(raw);

    current = { html: res.html, slug: res.slug, days: res.days };
    els.previewWrap.hidden = false;
    await new Promise((resolve) => {
      els.preview.onload = resolve;
      els.preview.srcdoc = res.html;
    });
    const doc = els.preview.contentDocument;
    if (doc.fonts && doc.fonts.status !== "loaded") await doc.fonts.ready;
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
    status("Could not parse that: " + msg, true);
  } finally {
    els.go.disabled = false;
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
  download(new Blob([current.html], { type: "text/html" }),
           `otf_${current.slug}.html`);
};

els.png.onclick = async () => {
  const doc = els.preview.contentDocument;
  const node = doc && doc.querySelector(".poster");
  if (!node) { status("Preview isn't ready yet.", true); return; }

  els.png.disabled = true;
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
    els.png.disabled = false;
  }
};

els.go.onclick = generate;
// Tracks the container, not just the window: catches the panel becoming
// visible, a collapsed pane opening, and plain window resizes alike.
new ResizeObserver(fitPreview).observe(els.stage);
boot();
