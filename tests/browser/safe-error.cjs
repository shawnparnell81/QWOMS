module.exports = function(error) {
  let raw=require('./credentials.cjs').redact(String(error.message||error));for(const [key,value] of Object.entries(process.env)){if(/PASSWORD|SECRET|TOKEN/i.test(key)&&value&&value.length>3)raw=raw.split(value).join('[REDACTED]')}const message=raw.split('\n').filter(line=>!/(cookie:|authorization:|qwoms_token=|qwoms_csrf=|bearer\s)/i.test(line)).join('\n');
  console.error((error.name||'Test error')+': '+message);
  process.exit(1);
};
