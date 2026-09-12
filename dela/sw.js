const C='dela-local-v3';
const SHELL=['./','./index.html','./manifest.webmanifest','./icon-192.png','./icon-512.png'];
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(SHELL)))});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(xs=>Promise.all(xs.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).then(r=>{let q=r.clone();caches.open(C).then(c=>c.put('./index.html',q));return r}).catch(()=>caches.match('./index.html').then(r=>r||caches.match('./'))));return}e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(n=>{if(n.ok&&new URL(e.request.url).origin===location.origin){let q=n.clone();caches.open(C).then(c=>c.put(e.request,q))}return n}).catch(()=>r)))});
