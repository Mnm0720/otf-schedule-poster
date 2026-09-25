/* The same parser/renderer used by the CLI, isolated from the editor UI. */
(function (scope) {
  'use strict';
  const INDEX_URL = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/';
  const METHODS = new Set(['generate', 'regenerate', 'restore', 'export_schedule']);

  function createEngine(environment) {
    let python = null;
    async function initialize(config, progress = () => {}) {
      if (config.protocol !== 1) throw new Error('This editor version is not compatible. Reload the page and try again.');
      progress('Loading the editor and schedule tools…');
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 30000);
      const bundlePromise = environment.fetch(config.bundleUrl, { signal: controller.signal })
        .then(response => {
          if (!response.ok) throw new Error(`Could not load the poster generator (HTTP ${response.status}). Please retry.`);
          return response.json();
        }).finally(() => clearTimeout(timer));
      // Start the local fetch before loading/compiling WebAssembly.
      const pythonPromise = Promise.resolve().then(() => environment.loadPyodide({ indexURL: INDEX_URL }))
        .then(async instance => {
          progress('Preparing poster templates…');
          await instance.loadPackage('jinja2');
          return instance;
        });
      const [bundle, instance] = await Promise.all([bundlePromise, pythonPromise]);
      if (bundle.schemaVersion !== 1 || bundle.bridgeVersion !== 1 || !bundle.files || typeof bundle.files !== 'object') {
        throw new Error('The poster files are not compatible with this editor. Reload the page and try again.');
      }
      for (const [path, content] of Object.entries(bundle.files)) {
        if (!/^[A-Za-z0-9_./-]+$/.test(path) || path.startsWith('/') || path.split('/').includes('..') || typeof content !== 'string') {
          throw new Error('The poster files contain an invalid path. Reload the page and try again.');
        }
      }
      progress('Finishing editor setup…');
      instance.FS.mkdirTree('/app');
      for (const [path, content] of Object.entries(bundle.files)) {
        const slash = path.lastIndexOf('/');
        if (slash !== -1) instance.FS.mkdirTree('/app/' + path.slice(0, slash));
        instance.FS.writeFile('/app/' + path, content, { encoding: 'utf8' });
      }
      instance.runPython('import sys; sys.path.insert(0, "/app")');
      instance.runPython('from browser_bridge import generate, regenerate, restore, export_schedule');
      python = instance;
      return { examples: bundle.examples || {} };
    }

    async function execute(method, args) {
      if (!METHODS.has(method)) throw new Error('Unsupported editor operation.');
      if (!python) throw new Error('The editor is not ready.');
      const fn = python.globals.get(method);
      try { return fn(...args); }
      finally { fn.destroy(); }
    }
    return { initialize, execute };
  }

  if (typeof module !== 'undefined' && module.exports) { module.exports = { createEngine }; return; }
  const engine = createEngine({
    fetch: (...args) => scope.fetch(...args),
    loadPyodide: options => {
      scope.importScripts(INDEX_URL + 'pyodide.js');
      return scope.loadPyodide(options);
    },
  });
  scope.onmessage = async ({ data }) => {
    try {
      const result = data.type === 'initialize'
        ? await engine.initialize(data.config, message => scope.postMessage({ id: data.id, type: 'progress', message }))
        : await engine.execute(data.method, data.args);
      scope.postMessage({ id: data.id, type: 'result', result });
    } catch (error) {
      scope.postMessage({ id: data.id, type: 'error', error: error.message || String(error) });
    }
  };
})(globalThis);
