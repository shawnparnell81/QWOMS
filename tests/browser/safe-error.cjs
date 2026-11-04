module.exports = function(error) {
  const message=String(error.message||error).split('\n').filter(line=>!/(cookie:|authorization:|qwoms_token=|qwoms_csrf=|bearer\s)/i.test(line)).join('\n');
  console.error((error.name||'Test error')+': '+message);
  process.exit(1);
};
