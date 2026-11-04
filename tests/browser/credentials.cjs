const fs=require('fs');
const sensitive=new Set();
const roles={manager:['demo.manager','QWOMS_BOOTSTRAP_PASSWORD'],quality:['demo.quality','QWOMS_DEMO_QUALITY_PASSWORD'],engineering:['demo.engineer','QWOMS_DEMO_ENGINEERING_PASSWORD'],production:['demo.production','QWOMS_DEMO_PRODUCTION_PASSWORD'],gate:['demo','QWOMS_DEMO_GATE_PASSWORD']};
module.exports=function(role,file){
 if(file){const [username,password]=fs.readFileSync(file,'utf8').trim().split(/\r?\n/);if(!username||!password)throw Error('Credential file is incomplete for '+role);sensitive.add(password);if(role==='gate')sensitive.add(Buffer.from(username+':'+password).toString('base64'));return {username,password}}
 const [username,key]=roles[role];const password=process.env[key];if(!password)throw Error('Secure hosted credential binding not available: '+key);sensitive.add(password);if(role==='gate')sensitive.add(Buffer.from(username+':'+password).toString('base64'));return {username,password};
};

module.exports.redact=function(message){for(const value of sensitive)if(value.length>3)message=message.split(value).join("[REDACTED]");return message};

module.exports.protect=value=>sensitive.add(value);
