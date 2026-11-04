// Hosted traffic uses the managed proxy; loopback checks remain local.
module.exports=function(){
 const base=new URL(process.env.QWOMS_TEST_BASE_URL||'http://127.0.0.1:8000');
 const proxy=process.env.HTTPS_PROXY||process.env.HTTP_PROXY;
 return {executablePath:process.env.QWOMS_CHROMIUM_PATH||undefined,args:['--no-sandbox'],...(!['localhost','127.0.0.1','[::1]'].includes(base.hostname)&&proxy?{proxy:{server:proxy}}:{})};
};
