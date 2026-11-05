'use strict';
// Synthetic browser verification for Print Page, print CSS and unsaved form values.
// Run against a private seeded environment. No actual printer or PDF is required.
const assert = require('assert/strict');
const {chromium}=require('playwright');
const credentials=require('./credentials.cjs');

(async()=>{
 const browser=await chromium.launch({executablePath:process.env.QWOMS_CHROMIUM_PATH||undefined,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  await page.addInitScript(()=>{
   window.__qwomsPrintCalls=[];
   window.print=()=>{
    window.dispatchEvent(new Event('beforeprint'));
    window.__qwomsPrintCalls.push({
     heading:document.querySelector('.print-document-heading h1')?.textContent,
     text:document.querySelector('#main')?.textContent,
     values:Array.from(document.querySelectorAll('.print-field-value')).map(n=>n.textContent),
     ready:document.body.classList.contains('print-ready')
    });
    window.dispatchEvent(new Event('afterprint'));
   };
  });
  const user=credentials('manager',process.env.QWOMS_TEST_CREDENTIAL_FILE);
  await page.goto(process.env.QWOMS_TEST_BASE_URL||'http://127.0.0.1:8000');
  await page.locator('#login-form [name=username]').fill(user.username);
  await page.locator('#login-form [name=password]').fill(user.password);
  await page.locator('#login-form button').click();
  await page.locator('.dashboard-welcome h1').waitFor();
  await page.locator('#print-current-page').click();
  let snapshots=await page.evaluate(()=>window.__qwomsPrintCalls);
  assert.equal(snapshots.length,1);
  assert.equal(snapshots[0].ready,true);
  assert.match(snapshots[0].heading,/Good morning/i);
  assert.equal(await page.locator('.print-document-heading').count(),0,'temporary print heading should be removed');
  assert.equal(await page.locator('.print-field-value').count(),0,'live form should not retain print snapshots');

  await page.locator('.sidebar [data-view=new]').click();
  await page.locator('#new-form [name=title]').fill('Unsaved synthetic print form');
  await page.locator('#print-current-page').click();
  snapshots=await page.evaluate(()=>window.__qwomsPrintCalls);
  assert.equal(snapshots.length,2);
  assert(snapshots[1].values.includes('Unsaved synthetic print form'));
  assert.equal(await page.locator('#new-form [name=title]').inputValue(),'Unsaved synthetic print form');
  assert.equal(await page.locator('.print-field-value').count(),0);

  await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).display),'none');
  assert.equal(await page.locator('.topbar').evaluate(el=>getComputedStyle(el).display),'none');
  await page.emulateMedia({media:'screen'});
  await page.locator('.sidebar [data-view=orders]').click();
  await page.locator('#main h1').waitFor();
  await page.locator('#print-current-page').click();
  snapshots=await page.evaluate(()=>window.__qwomsPrintCalls);
  assert.equal(snapshots.length,3);
  assert.match(snapshots[2].heading,/work orders/i);
  console.log('QWOMS browser print checks passed: dashboard, unsaved work form, register, print styling');
 }finally{await browser.close()}
})().catch(require('./safe-error.cjs'));
