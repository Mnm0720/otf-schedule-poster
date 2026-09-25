/* Main-thread transport only. Python work stays in runtime-worker.js. */
(function (root) {
  'use strict';
  const PROTOCOL = 1;
  const scripts = new Map();
  const EXPORT_LIBRARIES = {
    image: ['https://cdn.jsdelivr.net/npm/html-to-image@1.11.11/dist/html-to-image.min.js', 'htmlToImage'],
    pdf: ['https://cdn.jsdelivr.net/npm/pdf-lib@1.17.1/dist/pdf-lib.min.js', 'PDFLib'],
  };

  function createRuntime(options = {}) {
    const config = { protocol: PROTOCOL, workerUrl: 'runtime-worker.js', bundleUrl: 'bundle.json', ...root.OTF_BUILD, ...options };
    const WorkerClass = options.Worker || root.Worker;
    let worker = null, ready = false, initializing = null, nextId = 0;
    const pending = new Map();

    function stop(error) {
      error.runtimeUnavailable = true;
      ready = false;
      if (worker) worker.terminate();
      worker = null;
      for (const request of pending.values()) {
        clearTimeout(request.timer);
        request.reject(error);
      }
      pending.clear();
    }

    function request(type, payload, progress, timeoutMs) {
      const id = ++nextId;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => stop(new Error(
          type === 'initialize' ? 'Loading timed out. Check your connection and select Retry.'
            : 'Updating the poster timed out. Your draft is still available; select Retry loading to continue.'
        )), timeoutMs);
        pending.set(id, { resolve, reject, progress, timer });
        try { worker.postMessage({ id, type, ...payload }); }
        catch (error) { stop(error); }
      });
    }

    function initialize(progress = () => {}) {
      if (initializing) return initializing;
      if (ready) return Promise.resolve(client.info);
      if (!WorkerClass) return Promise.reject(new Error('This browser cannot run the editor. Try an updated browser.'));
      try {
        worker = new WorkerClass(config.workerUrl);
        worker.onmessage = ({ data }) => {
          const item = pending.get(data.id);
          if (!item) return;
          if (data.type === 'progress') { if (item.progress) item.progress(data.message); return; }
          clearTimeout(item.timer);
          pending.delete(data.id);
          if (data.type === 'error') item.reject(new Error(data.error || 'The poster could not be updated.'));
          else item.resolve(data.result);
        };
        worker.onerror = event => {
          if (event.preventDefault) event.preventDefault();
          stop(new Error(event.message || 'The editor could not start. Check your connection and select Retry.'));
        };
        worker.onmessageerror = () => stop(new Error('The editor could not read a response. Reload to try again.'));
      } catch (error) { stop(error); return Promise.reject(error); }
      initializing = request('initialize', { config: { bundleUrl: config.bundleUrl, protocol: config.protocol } }, progress,
        options.startupTimeoutMs || 90000)
        .then(info => { ready = true; client.info = info; return info; })
        .catch(error => { stop(error); throw error; })
        .finally(() => { initializing = null; });
      return initializing;
    }

    const client = {
      initialize,
      get ready() { return ready; },
      execute(method, args = []) {
        if (!ready) return Promise.reject(Object.assign(new Error('The editor is not ready. Retry loading it first.'), {runtimeUnavailable:true}));
        return request('execute', { method, args }, null, options.executeTimeoutMs || 60000);
      },
      dispose() { stop(new Error('The editor was closed.')); },
    };
    return client;
  }

  function loadScript(url, globalName, options = {}) {
    const scope = options.scope || root;
    const document = options.document || root.document;
    if (scope[globalName]) return Promise.resolve(scope[globalName]);
    const key = `${url}|${globalName}`;
    if (scripts.has(key)) return scripts.get(key);
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const timer = setTimeout(() => finish(new Error('The download tools took too long to load. Please try again.')), options.timeoutMs || 30000);
      function finish(error) {
        clearTimeout(timer);
        script.onload = script.onerror = null;
        if (error) { script.remove(); scripts.delete(key); reject(error); }
        else resolve(scope[globalName]);
      }
      script.src = url;
      script.async = true;
      script.onload = () => finish(scope[globalName] ? null : new Error('The download tools did not load correctly. Please try again.'));
      script.onerror = () => finish(new Error('Could not load the download tools. Check your connection and try again.'));
      document.head.appendChild(script);
    });
    scripts.set(key, promise);
    return promise;
  }

  function loadExportLibrary(kind) {
    const library = EXPORT_LIBRARIES[kind];
    if (!library) return Promise.reject(new Error('Unknown download format.'));
    return loadScript(...library);
  }

  const api = { PROTOCOL, createRuntime, create: createRuntime, loadScript, loadExportLibrary };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.OTFRuntime = api;
})(globalThis);
