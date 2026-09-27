// UI contract test: speech predictions are stubbed, not an accuracy benchmark.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true,
    args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1200},permissions:['microphone']});
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    const liveStatus = await context.request.get('http://127.0.0.1:8000/api/status');
    assert.equal(liveStatus.status(), 200);
    // Isolate UI tests from an in-progress multi-GB local setup.
    let modelReady = true;
    await page.route('**/api/status', route => route.fulfill({json:modelReady
      ? {state:'ready',device:'cuda',setup:null}
      : {state:'not_loaded',setup:{stage:'downloading',model_download_percent:48}}}));
    await page.goto('http://127.0.0.1:8000');
    await page.screenshot({path:'.cache/interface.png',fullPage:true});
    assert.equal(await page.title(), 'Sawt · Arabic, as spoken');
    await page.route('**/api/transcribe', async route => {
      const body = route.request().postDataBuffer();
      assert(body.includes(Buffer.from('RIFF')));
      await route.fulfill({json:{text:'جاءَ الطالبِ',raw_text:'جَاءَ الطَّالِبِ',words:[{},{}],duration:1.5}});
    });
    await page.locator('#mic').click();
    await page.waitForFunction(() => document.querySelector('#record-label').textContent.includes('Listening'));
    await page.waitForTimeout(1600);
    await page.locator('#mic').click();
    await page.waitForFunction(() => !document.querySelector('#transcript').hidden);
    assert.equal(await page.locator('#transcript').textContent(), 'جاءَ الطالبِ');
    assert.equal(await page.locator('#audio').getAttribute('src').then(s => s.startsWith('blob:')), true);
    await page.screenshot({path:'.cache/interface-result.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({path:'.cache/interface-mobile.png',fullPage:true});
    modelReady = false;
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#engine-status').textContent.includes('Setting up'));
    assert.equal(await page.locator('#mic').isEnabled(), true);
    let requests = 0;
    page.on('request', r => { if (r.url().endsWith('/api/transcribe')) requests++; });
    await page.locator('#mic').click();
    await page.waitForFunction(() => document.querySelector('#record-label').textContent.includes('Listening'));
    await page.waitForTimeout(5500); // A status poll must not disable the stop button.
    assert.equal(await page.locator('#mic').isEnabled(), true);
    await page.locator('#mic').click();
    await page.waitForFunction(() => !document.querySelector('#playback').hidden);
    assert.equal(requests, 0);
    assert.equal(await page.locator('#transcribe-recording').isEnabled(), false);
    assert(await page.locator('#message').textContent().then(t => t.includes('recording is ready')));
    modelReady = true;
    await page.waitForFunction(() => !document.querySelector('#transcribe-recording').disabled);
    await page.locator('#transcribe-recording').click();
    await page.waitForFunction(() => !document.querySelector('#transcript').hidden);
    assert.equal(requests, 1);
    assert.deepEqual(errors, []);
    console.log('Browser passed: recording during setup, playback, deferred transcription, ready-model capture, desktop/mobile layout; model response stubbed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
