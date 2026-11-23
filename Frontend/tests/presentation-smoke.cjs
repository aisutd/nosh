// Run with Vite on 127.0.0.1:5173 and NODE_PATH pointing to Playwright.
// API fixtures exercise the real live UI without writing to an account.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const origin = 'http://127.0.0.1:5173';
const availability = { required_ingredients: ['pasta', 'tomato', 'fresh basil'], available_ingredients: ['pasta', 'tomato'], missing_ingredients: ['fresh basil'], unresolved_ingredients: [], substitutions: [{ ingredient: 'fresh basil', replacement_ingredients: ['dried basil'], instructions: 'Use dried basil.', limitations: 'Flavor differs.' }], pantry_match: 2/3, coverage: 1 };
const recipe = { id: 'pasta', title: 'Tomato basil pasta', ingredients: ['200 g pasta', '300 g tomato'], directions: ['Boil pasta.', 'Simmer sauce.'], total_time: '20 minutes', availability };
(async () => {
 const browser = await chromium.launch({ headless: true, channel: 'chrome' });
 try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const errors = []; const sampleRequests = []; let saved = false; let cooked = false; let failScan = true;
  page.on('pageerror', e => errors.push(e.message));
  await page.addInitScript(() => {
    if (location.pathname !== '/presentation-sample') localStorage.setItem('access_token', 'test-token');
  });
  await page.route('**:8000/**', async route => {
   if (route.request().frame().url().includes('/presentation-sample')) sampleRequests.push(route.request().url());
   const url = new URL(route.request().url()); const path = url.pathname;
   let json = {};
   if (path === '/health') json = { app: 'nosh' };
   else if (path === '/me') json = { username: 'Presenter' };
   else if (path === '/ingredients' || path === '/ingredients/add') json = { ingredients: ['pasta', 'tomato', 'dried basil'] };
   else if (path === '/recipes/saved-ids') json = { saved: saved ? ['pasta'] : [] };
   else if (path === '/scan') {
    if (failScan) { failScan = false; return route.fulfill({ status: 503, json: { detail: 'Test scanner unavailable' } }); }
    json = { ingredients: ['pasta', 'tomato', 'dried basil'] };
   }
   else if (path === '/recipes/options') json = { status: 'ok', recipes: [recipe] };
   else if (path === '/recipes/save/pasta') { saved = true; json = { saved: ['pasta'] }; }
   else if (path === '/recipes/saved') json = saved ? [recipe] : [];
   else if (path === '/recipes/pasta') json = recipe;
   else if (path === '/recipes/saved-generate/pasta') json = { result: { status: 'ok', source_recipe: recipe.title, original_servings: 2, recipe: 'Recipe Name: Tomato pasta\nSteps:\n1. Boil pasta.\n2. Simmer sauce.', inventory_ingredients: recipe.ingredients, recipes: [recipe] } };
   else if (path === '/voice/turn') json = { answer: 'Simmer the sauce gently.', step: 0 };
   else if (path === '/inventory/consume') { cooked = true; json = { warnings: [] }; }
   else if (path === '/inventory') json = [{ name: 'pasta', quantity: cooked ? 200 : 500, unit: 'g' }];
   else if (path.startsWith('/memory')) json = { preferences: null, sessions: [] };
   else if (path === '/recipes/browse') json = [];
   await route.fulfill({ json });
  });
  await page.goto(`${origin}/presentation`);
  const heading = name => page.getByRole('heading', { name, exact: true });
  const live = page.frameLocator('iframe[title="NOSH live app"]');
  await page.getByRole('button', { name: 'Preparation', exact: true }).click();
  await page.getByRole('button', { name: 'Check / Retry readiness' }).click();
  await page.getByText('Account: Signed in as Presenter').waitFor();
  await page.getByRole('button', { name: 'Close preparation' }).click();
  await page.getByRole('button', { name: 'Begin presentation' }).click();
  const next = async () => {
    await page.getByRole('main', { name: 'NOSH guided presentation' }).focus();
    await page.keyboard.press('ArrowRight');
  };
  assert.equal(await page.getByRole('navigation', { name: 'Presentation chapters' }).count(), 0);
  assert.equal(await page.locator('.presentation-eyebrow').filter({ hasText: /PDF/ }).count(), 0);
  await next(); await heading('Learning to cook has a high barrier to entry.').waitFor();
  await next(); await heading('Learning to cook has a high barrier to entry.').waitFor();
  await live.getByRole('heading', { name: 'Your AI cooking buddy.' }).waitFor();
  await live.getByRole('link', { name: /Find recipes/ }).click();
  await heading('Learning to cook has a high barrier to entry.').waitFor();
  await live.getByRole('button', { name: 'Scan fridge', exact: true }).click();
  await heading('From your fridge to your pantry.').waitFor();
  await next(); await heading('Train. Evaluate. Improve. Repeat.').waitFor();
  await next(); await heading('Track ingredients across frames.').waitFor();
  const upload = { name: 'test.png', mimeType: 'image/png', buffer: Buffer.from('test-fixture') };
  await live.getByRole('button', { name: 'Choose a photo' }).click();
  await live.locator('input[type=file][accept="image/*"]').setInputFiles(upload);
  await page.getByText(/Scan: Test scanner unavailable/).waitFor();
  await next(); await heading('Track ingredients across frames.').waitFor();
  await live.getByRole('button', { name: 'Retry scan' }).click();
  await live.getByRole('button', { name: 'Choose a photo' }).click();
  await live.locator('input[type=file][accept="image/*"]').setInputFiles(upload);
  await live.getByRole('button', { name: 'Find Recipes', exact: true }).click();
  await heading('Real recipes ground the suggestions.').waitFor();
  assert.equal(await live.getByRole('button', { name: 'Inspect substitutions' }).count(), 0);
  await next();
  await heading('Make the most of what you have.').waitFor();
  await live.getByRole('button', { name: 'Save', exact: true }).click();
  await heading('Keep a recipe worth cooking.').waitFor();
  await live.getByRole('link', { name: 'Saved', exact: true }).click();
  await live.getByRole('link', { name: /Tomato basil pasta/ }).click();
  await live.getByLabel('Servings', { exact: true }).selectOption('3');
  await heading('A meal for one. Or a few.').waitFor();
  await live.getByRole('tab', { name: 'Steps', exact: true }).click();
  await heading('A meal for one. Or a few.').waitFor(); // tab selection is not voice
  await live.getByLabel('Speak replies').uncheck();
  await live.getByLabel('Your cooking question').fill('How long?');
  await live.getByRole('button', { name: 'Send', exact: true }).click();
  await heading('Cooking help, hands free.').waitFor();
  await live.getByText('Simmer the sauce gently.').waitFor();
  await live.getByRole('button', { name: 'Mark as cooked' }).click();
  await live.getByText('Inventory updated.', { exact: true }).waitFor();
  await next(); await heading('Cooking help, hands free.').waitFor();
  await live.getByRole('link', { name: 'Me', exact: true }).click();
  await live.getByRole('link', { name: 'My inventory', exact: true }).click();
  await heading('Keep track of what’s left.').waitFor();
  const liveUrl = page.frames().find(f => f.url().endsWith('/inventory')).url();
  await page.getByRole('button', { name: 'Use sample demo' }).click();
  const sample = page.frameLocator('iframe[title="NOSH sample demo"]');
  await heading('From your fridge to your pantry.').waitFor();
  await sample.getByRole('button', { name: 'Scan fridge' }).click();
  await sample.getByRole('button', { name: 'Simulate video scan' }).click();
  await heading('Track ingredients across frames.').waitFor();
  await sample.getByRole('button', { name: 'Review pantry' }).click();
  await sample.getByRole('button', { name: 'Find Recipes' }).click();
  assert.equal(await sample.getByRole('button', { name: 'Inspect substitutions' }).count(), 0);
  await next();
  await sample.getByRole('button', { name: 'Save recipe' }).click();
  await sample.getByRole('button', { name: 'Saved', exact: true }).click();
  await sample.getByRole('button', { name: 'Open tomato basil pasta' }).click();
  await sample.getByLabel('Servings').selectOption('3');
  await sample.getByRole('tab', { name: 'Steps', exact: true }).click();
  await heading('A meal for one. Or a few.').waitFor();
  await sample.getByRole('button', { name: 'Can I use dried basil?' }).click();
  await heading('Cooking help, hands free.').waitFor();
  await sample.getByRole('button', { name: 'Mark as cooked' }).click();
  await next(); await heading('Cooking help, hands free.').waitFor();
  await sample.getByRole('button', { name: 'My inventory' }).click();
  await heading('Keep track of what’s left.').waitFor();
  await sample.getByText('pasta: 200 g', { exact: true }).waitFor();
  await next();
  await heading('What challenged us.').waitFor();
  await sample.getByRole('heading', { name: 'Your AI cooking buddy.' }).waitFor();
  await page.screenshot({ path: '/tmp/nosh-guided-desktop.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/nosh-guided-mobile.png' });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: 'Reset sample' }).click();
  await sample.getByRole('button', { name: 'Saved', exact: true }).click();
  await sample.getByText('Save a recipe from your results first.').waitFor();
  assert.equal(await page.evaluate(() => localStorage.getItem('access_token')), 'test-token');
  assert.deepEqual(sampleRequests, []);
  await page.getByRole('button', { name: 'Return to live app' }).click();
  assert.equal(page.frames().find(f => f.url() === liveUrl)?.url(), liveUrl);
  await live.getByRole('heading', { name: 'Inventory', exact: true }).waitFor();
  await page.getByRole('main', { name: 'NOSH guided presentation' }).focus();
  await page.keyboard.press('End');
  await page.evaluate(() => window.postMessage({ type: 'nosh-demo', kind: 'navigation', path: '/inventory' }, location.origin));
  await page.waitForTimeout(100);
  await heading('What challenged us.').waitFor();
  await live.getByRole('heading', { name: 'Your AI cooking buddy.' }).waitFor();
  assert.equal(await page.evaluate(() => localStorage.getItem('access_token')), 'test-token');
  await next(); await heading('Where NOSH goes next.').waitFor();
  await next(); await heading('Thank you.').waitFor();
  // Keyboard storytelling, rapid genuine iframe events, and rejection of forged origins.
  await page.getByRole('button', { name: 'Back to start', exact: true }).click();
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.getByRole('main', { name: 'NOSH guided presentation' }).focus();
  await page.keyboard.press('ArrowRight');
  await heading('Learning to cook has a high barrier to entry.').waitFor();
  await page.keyboard.press('ArrowLeft');
  await heading('Your ingredients. Your next meal.').waitFor();
  const liveFrame = page.frames().find(f => f.url().endsWith('/intro'));
  await liveFrame.evaluate(() => {
    for (const feature of ['scan', 'rag', 'servings', 'voice'])
      parent.postMessage({ type: 'nosh-demo', kind: 'action', feature }, location.origin);
  });
  await heading('Cooking help, hands free.').waitFor();
  await liveFrame.evaluate(() => parent.postMessage({ type: 'nosh-demo', kind: 'action', feature: 'inventory' }, location.origin));
  await page.evaluate(() => window.dispatchEvent(new MessageEvent('message', {
    origin: 'https://untrusted.example', source: document.querySelector('iframe').contentWindow,
    data: { type: 'nosh-demo', kind: 'navigation', path: '/inventory' },
  })));
  await page.waitForTimeout(300);
  await heading('Cooking help, hands free.').waitFor();
  await page.route('**:8000/health', route => route.fulfill({ status: 503, json: { detail: 'Test service unavailable' } }));
  await page.getByRole('button', { name: 'Preparation', exact: true }).click();
  await page.getByRole('button', { name: 'Check / Retry readiness' }).click();
  await page.getByText('Backend: Unavailable — start the backend and retry').waitFor();
  assert.deepEqual(errors, []);
  console.log('PASS: live walkthrough, failed scan/retry, inventory gate, sample isolation/reset, serving/voice controls, iframe validation, desktop/mobile.');
 } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
