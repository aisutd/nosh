// Browser globals and HTTP responses exist only in this test process.
const { test, before, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let api;
const originalFetch = global.fetch;
before(async () => {
  global.window = { location: { protocol: 'http:', hostname: 'localhost' } };
  global.localStorage = { getItem: () => 'test-token' };
  const source = fs.readFileSync(new URL('../src/lib/api.js', `file://${__filename}`), 'utf8').replace('import.meta.env.VITE_API_URL', 'undefined');
  api = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
});
afterEach(() => { global.fetch = originalFetch; });
test('HTTP failures retain status and actionable detail', async () => {
  global.fetch = async () => new Response(JSON.stringify({ detail: 'Session expired' }), { status: 401 });
  await assert.rejects(api.request('/me'), error => error.status === 401 && error.message === 'Session expired');
});
test('network failure gives a recoverable message and preserves the cause', async () => {
  const failure = new TypeError('Failed to fetch');
  global.fetch = async () => { throw failure; };
  await assert.rejects(api.request('/ingredients'), error => error.message.includes('backend') && error.cause === failure);
});
test('requests time out and can be retried', async () => {
  global.fetch = (_url, options) => new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
  await assert.rejects(api.request('/scan', { timeout: 5 }), /taking longer/);
  global.fetch = async () => new Response(JSON.stringify({ ingredients: ['lemon'] }));
  assert.deepEqual(await api.request('/ingredients'), { ingredients: ['lemon'] });
});
test('page cancellation is distinguishable from a service timeout', async () => {
  global.fetch = (_url, options) => new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
  const controller = new AbortController();
  const promise = api.request('/recipes/options', { signal: controller.signal });
  controller.abort();
  await assert.rejects(promise, error => error.name === 'AbortError');
});
test('memory requests use current auth and explain field validation', async () => {
  global.fetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8000/memory/preferences');
    assert.equal(options.headers.Authorization, 'Bearer test-token');
    return new Response(JSON.stringify({ detail: [{ msg: 'Use at most 10 preferences' }] }), { status: 422 });
  };
  await assert.rejects(api.memoryRequest('/preferences', { method: 'PUT' }), /at most 10/);
});
