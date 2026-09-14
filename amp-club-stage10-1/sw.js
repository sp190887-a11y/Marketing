const CACHE='amp-club-stage10-1-5';
const ASSETS=['./','./index.html','./styles.css?v=10.1.5','./overrides.css?v=10.1.5','./app-a.js?v=10.1.5','./app-b.js?v=10.1.5','./app-c.js?v=10.1.5','./app-d.js?v=10.1.5','./app-e.js?v=10.1.5','./save-links.js?v=10.1.5','./app-f.js?v=10.1.5','./amp-logo.svg?v=10.1.5','./manifest.webmanifest?v=10.1.5'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));return r}).catch(()=>caches.match(e.request).then(r=>r||caches.match('./index.html'))))});
