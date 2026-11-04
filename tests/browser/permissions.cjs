const {chromium}=require('playwright');const credentials=require('./credentials.cjs');const fs=require('fs');
(async()=>{
 const browser=await chromium.launch(require('./launch.cjs')());const base=process.env.QWOMS_TEST_BASE_URL||'http://127.0.0.1:8000';const gate=credentials('gate',process.env.QWOMS_TEST_GATE_CREDENTIAL_FILE);const results=[];
 const check=(name,actual,expected)=>{results.push({name,actual,expected,passed:actual===expected})};
 const anonymous=await browser.newPage({httpCredentials:gate});await anonymous.goto(base);check('Unauthenticated dashboard denied',await anonymous.evaluate(async()=> (await fetch('/api/dashboard')).status),401);
 for(const role of ['manager','quality','engineering','production']){
  const p=await browser.newPage({viewport:{width:1440,height:1000},httpCredentials:gate});const auth=credentials(role);await p.goto(base);await p.locator('#login-form [name=username]').fill(auth.username);await p.locator('#login-form [name=password]').fill(auth.password);await p.locator('#login-form button').click();await p.getByRole('heading',{name:'My assigned work'}).waitFor();
  check(role+' dashboard accessible',await p.evaluate(async()=> (await fetch('/api/dashboard')).status),200);
  check(role+' audit permission',await p.evaluate(async()=> (await fetch('/api/admin/audit')).status),role==='manager'?200:403);
  const request={recipient_id:1,body:'Synthetic CSRF denial probe'};
  check(role+' mutation without CSRF denied',await p.evaluate(async body=>(await fetch('/api/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).status,request),403);
  if(role==='production'){
   check('Production account creation denied',await p.evaluate(async()=>{const csrf=document.cookie.split('; ').find(x=>x.startsWith('qwoms_csrf='))?.split('=').slice(1).join('=');return (await fetch('/api/admin/users',{method:'POST',headers:{'Content-Type':'application/json','X-QWOMS-CSRF':csrf||''},body:JSON.stringify({username:'synthetic-forbidden-'+Date.now(),display_name:'Synthetic Forbidden',role:'Production',site:'Synthetic',password:'Synthetic-denied-only!'})})).status}),403);
  }
  await p.close();
 }
 console.log(JSON.stringify(results,null,2));if(process.env.QWOMS_TEST_EVIDENCE_FILE)fs.writeFileSync(process.env.QWOMS_TEST_EVIDENCE_FILE,JSON.stringify({base,checked_at:new Date().toISOString(),results},null,2));await browser.close();if(results.some(r=>!r.passed))process.exitCode=1;
})().catch(require('./safe-error.cjs'));
