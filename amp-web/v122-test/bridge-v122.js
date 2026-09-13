(function(){
'use strict';
const NATIVE=window.fetch.bind(window);let CFG=null;
async function cfg(){if(CFG)return CFG;const r=await NATIVE('../v122-test/',{cache:'no-store'}),s=await r.text();const api=(s.match(/const API="([^"]+)"/)||[])[1],auth=(s.match(/AUTH="([^"]+)"/)||[])[1];if(!api||!auth)throw new Error('Не найдена конфигурация Neon');return CFG={api,auth,profile:'amp_api'}}
function key(){return sessionStorage.getItem('ampWebKey')||''}
async function rpc(name,args={}){const c=await cfg(),r=await NATIVE(c.api+'/rpc/'+name,{method:'POST',headers:{Authorization:'Bearer '+c.auth,'Content-Type':'application/json','Accept-Profile':c.profile,'Content-Profile':c.profile},body:JSON.stringify(args)});const t=await r.text();let j;try{j=t?JSON.parse(t):null}catch{j=t}if(!r.ok){const e=new Error(j?.message||j?.error||String(j||('HTTP '+r.status)));e.status=r.status;throw e}return j}
async function call(action,payload={}){const k=key();if(!k){const e=new Error('Требуется вход');e.status=401;throw e}return rpc('call',{p_key:k,p_action:action,p_payload:payload})}
function jr(o,status=200){return new Response(JSON.stringify(o),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}})}
async function body(opt={}){if(opt.body==null)return{};if(typeof opt.body==='string')return JSON.parse(opt.body||'{}');if(opt.body instanceof Blob)return JSON.parse(await opt.body.text());return opt.body}
function b64(u){let s='';for(let i=0;i<u.length;i+=32768)s+=String.fromCharCode(...u.subarray(i,i+32768));return btoa(s)}
async function fileBlob(id){const x=await call('file_get',{id});if(!x?.ok)throw new Error(x?.error||'Файл не найден');const bin=atob(x.b64),u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);return{x,blob:new Blob([u],{type:x.mime||'application/octet-stream'})}}
window.fetch=async function(input,opt={}){const url=new URL(typeof input==='string'?input:input.url,location.href);if(url.origin!==location.origin||!url.pathname.startsWith('/api/'))return NATIVE(input,opt);const p=url.pathname,m=(opt.method||'GET').toUpperCase();try{
if(p==='/api/health')return jr(await call('health'));
if(p==='/api/state'&&m==='GET')return jr(await call('state_get'));
if(p==='/api/state'&&m==='POST')return jr(await call('state_save',{state:await body(opt)}));
if(p==='/api/restore-backup'&&m==='POST')return jr(await call('restore_backup'));
if(p==='/api/upload'&&m==='POST'){let ab;if(opt.body instanceof Blob)ab=await opt.body.arrayBuffer();else if(opt.body instanceof ArrayBuffer)ab=opt.body;else ab=new TextEncoder().encode(String(opt.body||'')).buffer;const u=new Uint8Array(ab),h=new Headers(opt.headers||{});if(!u.length||u.length>4000000)return jr({ok:false,error:'Файл должен быть от 1 байта до 4 МБ'},400);let name='file.bin';try{name=decodeURIComponent(h.get('X-Filename')||name)}catch{}return jr(await call('file_put',{name,mime:h.get('Content-Type')||'application/octet-stream',b64:b64(u)}))}
if(p==='/api/file'&&m==='GET'){const {x,blob}=await fileBlob(url.searchParams.get('id')||'');return new Response(blob,{status:200,headers:{'Content-Type':x.mime||'application/octet-stream'}})}
if(p==='/api/open-attachment'&&m==='POST'){const q=await body(opt),id=String(q.relative_path||'').split('/').pop(),f=await fileBlob(id),u=URL.createObjectURL(f.blob);window.open(u,'_blank','noopener');setTimeout(()=>URL.revokeObjectURL(u),60000);return jr({ok:true})}
if(p==='/api/open-attachments'&&m==='POST')return jr({ok:true});
if(p==='/api/kpi/unlock'&&m==='POST'){const q=await body(opt);return jr(await call('kpi_unlock',{password:String(q.password||'')}))}
if(p==='/api/kpi/password'&&m==='POST'){const q=await body(opt),h=new Headers(opt.headers||{});return jr(await call('kpi_password',{password:String(q.password||''),token:String(h.get('X-KPI-Token')||'')}))}
if(p==='/api/integrations/config'&&m==='GET')return jr(await call('config_get',{id:'integrations'}));
if(p==='/api/integrations/status'&&m==='GET'){const g=await call('config_get',{id:'integrations'}),c=g?.config||{},bot=c.bot||{},yd=c.yandex_disk||{};return jr({ok:true,telegram:{configured:!!bot.token,enabled:!!bot.enabled},yandex:{configured:!!yd.oauth_token,enabled:!!yd.enabled},queue_pending:0})}
if(p==='/api/save-courier-config'&&m==='POST')return jr(await call('config_set',{id:'integrations',value:await body(opt)}));
if(p==='/api/integrations/test'&&m==='POST')return jr({ok:true,result:{telegram:{ok:false,message:'Настройки сохранены'},yandex:{ok:false,message:'Настройки сохранены'}}});
if((p==='/api/sync/export-work'||p==='/api/sync/export-changes')&&m==='POST'){const st=await call('state_get'),clean=structuredClone(st);delete clean.cloud;const pkg=p.endsWith('export-work')?{schema:'amp-marketing-work-copy-v2',created_at:new Date().toISOString(),base_snapshot:clean,state:clean}:{schema:'amp-marketing-changes-v2',created_at:new Date().toISOString(),base_snapshot:clean.sync?.edit_base||clean,edited_state:clean};return new Response(JSON.stringify(pkg,null,2),{status:200,headers:{'Content-Type':'application/json; charset=utf-8'}})}
if(p==='/api/sync/read-package'&&m==='POST'){let txt=opt.body instanceof Blob?await opt.body.text():typeof opt.body==='string'?opt.body:new TextDecoder().decode(opt.body);return jr({ok:true,package:JSON.parse(txt)})}
return jr({ok:false,error:'WEB API пока не реализован: '+p},404)}catch(e){console.error('AMP WEB bridge',p,e);return jr({ok:false,error:e.message||String(e)},e.status===401?401:500)}};
})();
