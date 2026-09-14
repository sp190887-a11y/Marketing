/* Stage 10.1.6 — client role is client-only. Admin UI is never reachable from this bundle. */
try{admin=false}catch(e){}
head=function(title,sub){return `<header class="top"><div class="brand"><div class="logo"><img src="./amp-logo.svg?v=10.1.6" alt="Амплитуда"></div><div><h1 class="title">${title}</h1><div class="sub">${sub||''}</div></div></div></header>`};
document.addEventListener('click',e=>{const b=e.target.closest('[data-action="toggle-admin"]');if(!b)return;e.preventDefault();e.stopImmediatePropagation();},true);
try{render()}catch(e){}
