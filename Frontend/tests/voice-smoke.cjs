// Test-only browser and API doubles. Never imported by the application.
// Run with NODE_PATH pointing to a Playwright installation and Vite on localhost:5173.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const calls = [];
  const recipe = 'Recipe Name: Toast\nChanges:\n- none\nSteps:\n1. Toast bread.\n2. Serve warm.';
  await page.addInitScript(() => {
    window.SpeechRecognition = class {
      start() { this.onstart?.(); window.testMic = this; }
      abort() { this.onend?.(); }
    };
  });
  await page.route('**:8000/**', async route => {
    if (route.request().url().endsWith('/voice/turn')) {
      const body = route.request().postDataJSON(); calls.push(body);
      if (body.message === 'fail') return route.fulfill({ status: 503, json: { detail: 'Recipe service unavailable' } });
      return route.fulfill({ json: { answer: body.message === 'next step' ? 'Step 1. Toast bread.' : 'Use a warm pan.', step: 0 } });
    }
    if (route.request().url().includes('/recipes/saved-generate/')) {
      return route.fulfill({ json: { result: { status: 'ok', recipe } } });
    }
    if (route.request().url().endsWith('/recipes/toast')) {
      return route.fulfill({ json: { id: 'toast', title: 'Toast', ingredients: ['bread'] } });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto('http://127.0.0.1:5173/pantry');
  await page.getByRole('heading', { name: 'Your ingredients' }).waitFor();
  assert.equal(await page.getByRole('heading', { name: 'Cook with NOSH' }).count(), 0);
  await page.goto('http://127.0.0.1:5173/cook/toast');
  await page.getByRole('tab', { name: 'Steps', exact: true }).click();
  await page.getByLabel('Speak replies').uncheck();
  await page.getByLabel('Your cooking question').fill('How do I toast bread?');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.getByText('Use a warm pan.', { exact: false }).waitFor();
  await page.getByRole('button', { name: 'Start listening', exact: true }).click();
  await page.getByRole('button', { name: 'Stop listening', exact: true }).waitFor();
  await page.evaluate(() => window.testMic.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: 'next step' }], { isFinal: true })] }));
  await page.getByText('Step 1. Toast bread.', { exact: false }).waitFor();
  assert.equal(calls[1].message, 'next step');
  assert.equal(calls[1].step, 0);
  await page.getByLabel('Your cooking question').fill('fail');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'Recipe service unavailable' }).waitFor();
  assert.equal(await page.getByLabel('Your cooking question').inputValue(), 'fail');
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await page.getByRole('button', { name: 'Start listening', exact: true }).click();
  await page.evaluate(() => window.testMic.onerror({ error: 'not-allowed' }));
  await page.getByRole('alert').filter({ hasText: 'Microphone access was denied' }).waitFor();
  await page.screenshot({ path: '/tmp/nosh-week4-voice.png', fullPage: true });
  // Unsupported browsers retain the typed path.
  const unsupported = await browser.newPage();
  await unsupported.addInitScript(() => { window.SpeechRecognition = undefined; window.webkitSpeechRecognition = undefined; });
  await unsupported.route('**:8000/**', async route => {
    if (route.request().url().includes('/recipes/saved-generate/')) return route.fulfill({ json: { result: { status: 'ok', recipe } } });
    return route.fulfill({ json: { id: 'toast', title: 'Toast', ingredients: ['bread'] } });
  });
  await unsupported.goto('http://127.0.0.1:5173/cook/toast');
  await unsupported.getByRole('tab', { name: 'Steps', exact: true }).click();
  await unsupported.getByText('Voice recognition is unavailable', { exact: false }).waitFor();
  assert(await unsupported.getByRole('button', { name: 'Start listening', exact: true }).isDisabled());
  console.log('PASS: typed questions, mic transcripts, step state, API errors/retry, denied permission, unsupported browser, mobile layout');
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
