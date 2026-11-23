// Uses isolated API fixtures. Run with Vite on 127.0.0.1:5173 and Playwright in NODE_PATH.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({ headless: true, channel: 'chrome' });
 try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.addInitScript(() => localStorage.setItem('access_token', 'scan-test'));
  let result = ['tomato', 'pasta', 'basil', 'onion']; let failure = false; let release; let hold = false;
  await page.route('**:8000/**', async route => {
   const path = new URL(route.request().url()).pathname;
   if (path === '/scan' || path === '/scan-video') {
    if (hold) await new Promise(resolve => { release = resolve; });
    return route.fulfill({ status: failure ? 503 : 200, json: failure ? { detail: 'Scanner unavailable' } : { ingredients: result } });
   }
   const json = path === '/me' ? { username: 'Presenter' } : path === '/recipes/saved-ids' ? { saved: [] }
    : path === '/recipes/browse' ? [] : { ingredients: result };
   return route.fulfill({ json });
  });
  await page.goto('http://127.0.0.1:5173/pantry');
  await page.getByText('Hi, Presenter').waitFor();
  const toast = page.locator('.scan-confirmation');
  const upload = async (media = 'image') => {
   await page.getByRole('button', { name: 'Scan fridge', exact: true }).click();
   await page.getByRole('button', { name: media === 'image' ? 'Choose a photo' : 'Choose a video' }).click();
   await page.locator(`input[type=file][accept="${media}/*"]`).setInputFiles({ name: media === 'image' ? 'fridge.png' : 'fridge.mp4', mimeType: `${media}/${media === 'image' ? 'png' : 'mp4'}`, buffer: Buffer.from('scan fixture') });
  };
  hold = true;
  await upload();
  await page.getByRole('button', { name: 'Scanning...', exact: true }).waitFor();
  assert.equal(await toast.count(), 0);
  while (!release) await page.waitForTimeout(20);
  release(); hold = false;
  await toast.getByText('Image uploaded and scanned. Found 4 ingredients.').waitFor();
  await page.screenshot({ path: '/tmp/nosh-scan-confirmation.png' });
  const bounds = await toast.boundingBox();
  assert(bounds.x >= 0 && bounds.x + bounds.width <= 390);
  const scanBounds = await page.getByRole('button', { name: 'Scan fridge', exact: true }).boundingBox();
  assert(bounds.y + bounds.height <= scanBounds.y);
  await page.getByRole('button', { name: 'Dismiss scan confirmation' }).click();
  assert.equal(await toast.count(), 0);
  result = ['tomato']; await upload('video');
  await toast.getByText('Video uploaded and scanned. Found 1 ingredient.').waitFor();
  await page.waitForTimeout(3000);
  await upload('video'); // identical message must receive a fresh five-second lifetime
  await toast.getByText('Video uploaded and scanned. Found 1 ingredient.').waitFor();
  await page.waitForTimeout(3000);
  assert.equal(await toast.count(), 1);
  await toast.waitFor({ state: 'detached', timeout: 3000 });
  result = []; await upload();
  await toast.getByText('Image uploaded and scanned. No ingredients detected—try a clearer photo.').waitFor();
  // A cancelled picker never creates a new success notification.
  await page.getByRole('button', { name: 'Dismiss scan confirmation' }).click();
  await page.getByRole('button', { name: 'Scan fridge', exact: true }).click();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.locator('input[type=file][accept="image/*"]').setInputFiles([]);
  assert.equal(await toast.count(), 0);
  failure = true; await upload();
  await page.getByRole('alert').getByText('Scanner unavailable').waitFor();
  assert.equal(await toast.count(), 0);
  await page.getByRole('button', { name: 'Retry scan' }).waitFor();
  failure = false;
  await page.evaluate(() => {
   window.dispatchEvent(new CustomEvent('nosh-scan-status', { detail: { scanning: true } }));
   window.dispatchEvent(new CustomEvent('nosh-scan', { detail: ['tomato', 'tomato'] }));
   window.dispatchEvent(new CustomEvent('nosh-scan-status', { detail: { scanning: false } }));
  });
  await toast.getByText('Scan complete. Found 1 ingredient.').waitFor();
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('nosh-scan-status', { detail: { scanning: true } })));
  await toast.waitFor({ state: 'detached' });
  // The same notice fits within the real embedded phone, not the parent presentation.
  result = ['pasta', 'tomato'];
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('http://127.0.0.1:5173/presentation');
  await page.getByRole('button', { name: 'Begin presentation' }).click();
  const phone = page.frameLocator('iframe[title="NOSH live app"]');
  await phone.getByRole('link', { name: /Find recipes/ }).click();
  await phone.getByRole('button', { name: 'Scan fridge', exact: true }).click();
  await phone.getByRole('button', { name: 'Choose a photo' }).click();
  await phone.locator('input[type=file][accept="image/*"]').setInputFiles({ name: 'fridge.png', mimeType: 'image/png', buffer: Buffer.from('fixture') });
  await phone.getByText('Image uploaded and scanned. Found 2 ingredients.').waitFor();
  await page.screenshot({ path: '/tmp/nosh-scan-confirmation-phone.png' });
  await phone.getByRole('button', { name: 'Dismiss scan confirmation' }).click();
  await page.getByRole('button', { name: 'Use sample demo' }).click();
  const sample = page.frameLocator('iframe[title="NOSH sample demo"]');
  await sample.getByRole('button', { name: 'Scan fridge' }).click();
  await sample.getByRole('button', { name: 'Simulate photo scan' }).click();
  await sample.getByText('Simulated: Image uploaded and scanned. Found 3 ingredients.').waitFor();
  assert.deepEqual(errors, []);
  console.log('PASS: image/video, loading, zero detections, errors, cancel, repeated upload, five-second expiry, dismiss, native events, sample label, embedded phone.');
 } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
