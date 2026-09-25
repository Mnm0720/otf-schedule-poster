const test = require('node:test');
const assert = require('node:assert/strict');
const Runtime = require('../web/runtime.js');
const { createEngine } = require('../web/runtime-worker.js');

const bundle = { schemaVersion: 1, bridgeVersion: 1, files: { 'browser_bridge.py': '# bridge' }, examples: { '2026-09': 'example' } };

test('worker runtime fetches the bundle concurrently and loads bundled jinja2', async () => {
  const calls = [];
  let resolveRuntime;
  const proxy = { destroy() { calls.push('destroy'); } };
  const fn = Object.assign((...args) => JSON.stringify({ args }), proxy);
  const py = { loadPackage: async name => calls.push(name), FS: { mkdirTree() {}, writeFile() {} },
    runPython() {}, globals: { get: () => fn } };
  const engine = createEngine({ fetch: async () => { calls.push('fetch'); return { ok: true, json: async () => bundle }; },
    loadPyodide: () => { calls.push('python'); return new Promise(resolve => { resolveRuntime = resolve; }); } });
  const ready = engine.initialize({ bundleUrl: 'bundle.abc.json', protocol: 1 }, () => {});
  await Promise.resolve();
  assert.deepEqual(calls, ['fetch', 'python']);
  resolveRuntime(py);
  assert.deepEqual(await ready, { examples: bundle.examples });
  assert.ok(calls.includes('jinja2'));
  assert.ok(!calls.includes('micropip'));
  assert.deepEqual(JSON.parse(await engine.execute('generate', ['text'])), { args: ['text'] });
  assert.equal(calls.at(-1), 'destroy');
  assert.deepEqual(JSON.parse(await engine.execute('restore', ['saved draft'])), { args: ['saved draft'] });
  await assert.rejects(engine.execute('eval', []), /Unsupported/);
});

test('bundle errors fail clearly before writing Python files', async () => {
  const py = { loadPackage: async () => {}, FS: { mkdirTree() { throw new Error('must not write'); } } };
  for (const [response, expected] of [
    [{ ok: false, status: 404 }, /404/],
    [{ ok: true, json: async () => ({ ...bundle, bridgeVersion: 99 }) }, /compatible/],
    [{ ok: true, json: async () => ({ ...bundle, files: { '../outside.py': 'x' } }) }, /path/],
  ]) {
    const engine = createEngine({ fetch: async () => response, loadPyodide: async () => py });
    await assert.rejects(engine.initialize({ bundleUrl: 'bundle.json', protocol: 1 }), expected);
  }
});

test('transport reports progress, returns strings, and retries with a new worker', async () => {
  const workers = [];
  class Worker {
    constructor(url) { this.url = url; workers.push(this); }
    postMessage(message) { this.request = message; }
    terminate() { this.terminated = true; }
    reply(message) { this.onmessage({ data: { id: this.request.id, ...message } }); }
  }
  const client = Runtime.createRuntime({ Worker, workerUrl: 'runtime-worker.123.js', bundleUrl: 'bundle.456.json' });
  const progress = [];
  const first = client.initialize(value => progress.push(value));
  workers[0].reply({ type: 'progress', message: 'Loading poster generator…' });
  workers[0].reply({ type: 'error', error: 'Network unavailable' });
  await assert.rejects(first, /Network unavailable/);
  assert.equal(workers[0].terminated, true);
  const second = client.initialize();
  assert.equal(workers.length, 2);
  assert.equal(workers[1].request.config.bundleUrl, 'bundle.456.json');
  workers[1].reply({ type: 'result', result: { examples: {} } });
  await second;
  const execution = client.execute('regenerate', ['{}']);
  workers[1].reply({ type: 'result', result: '{"slug":"2026-09"}' });
  assert.equal(await execution, '{"slug":"2026-09"}');
  assert.deepEqual(progress, ['Loading poster generator…']);
  client.dispose();
});

test('startup timeouts terminate the worker and permit retry', async () => {
  const workers = [];
  class Worker { constructor() { workers.push(this); } postMessage() {} terminate() { this.terminated = true; } }
  const client = Runtime.createRuntime({ Worker, startupTimeoutMs: 5 });
  await assert.rejects(client.initialize(), /timed out/);
  assert.equal(workers[0].terminated, true);
  await assert.rejects(client.initialize(), /timed out/);
  assert.equal(workers.length, 2);
});

test('execution timeout signals runtime recovery, while Python validation keeps the worker ready', async () => {
  const workers=[];
  class Worker {
    constructor(){workers.push(this);}
    postMessage(message){this.request=message;}
    terminate(){this.terminated=true;}
    reply(message){this.onmessage({data:{id:this.request.id,...message}});}
  }
  const client=Runtime.createRuntime({Worker,executeTimeoutMs:5});
  const ready=client.initialize();
  workers[0].reply({type:'result',result:{examples:{}}});
  await ready;
  assert.equal(client.ready,true);
  const invalid=client.execute('regenerate',['{}']);
  workers[0].reply({type:'error',error:'September 1 must repeat an earlier day'});
  await assert.rejects(invalid,error=>!error.runtimeUnavailable && /earlier/.test(error.message));
  assert.equal(client.ready,true);
  await assert.rejects(client.execute('regenerate',['{}']),error=>error.runtimeUnavailable===true && /Retry/.test(error.message));
  assert.equal(client.ready,false);
  assert.equal(workers[0].terminated,true);
  await assert.rejects(client.execute('regenerate',['{}']),error=>error.runtimeUnavailable===true);
  const restarted=client.initialize();
  workers[1].reply({type:'result',result:{examples:{}}});
  await restarted;
  assert.equal(client.ready,true);
  client.dispose();
});

test('lazy export loader shares requests and can retry after a failed script', async () => {
  const scope = {};
  const scripts = [];
  const document = { createElement: () => ({ remove() {} }), head: { appendChild(script) { scripts.push(script); } } };
  const options = { scope, document, timeoutMs: 100 };
  const first = Runtime.loadScript('https://example.test/image.js', 'htmlToImage', options);
  const duplicate = Runtime.loadScript('https://example.test/image.js', 'htmlToImage', options);
  assert.equal(first, duplicate);
  scripts[0].onerror();
  await assert.rejects(first, /load/);
  const retry = Runtime.loadScript('https://example.test/image.js', 'htmlToImage', options);
  scope.htmlToImage = { toBlob() {} };
  scripts[1].onload();
  assert.equal(await retry, scope.htmlToImage);
});
