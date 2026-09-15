// V15.3 bridge to the Python server. The app keeps working locally when offline.
(function () {
  'use strict';

  const App = window.CalendarApp;
  if (!App) return;
  const DEVICE_KEY = 'calendar_device_id_v15';
  const AUTH_KEY = 'calendar_auth_token_v15';
  const state = {online:false, config:null, syncTimer:null};

  function deviceId() {
    let value = localStorage.getItem(DEVICE_KEY);
    if (!value) {
      value = 'device_' + (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') : Date.now().toString(36) + Math.random().toString(36).slice(2));
      localStorage.setItem(DEVICE_KEY, value);
    }
    return value;
  }

  async function api(path, options={}) {
    const headers = new Headers(options.headers || {});
    headers.set('X-Device-Id', deviceId());
    const token = localStorage.getItem(AUTH_KEY);
    if (token) headers.set('Authorization', 'Bearer ' + token);
    if (options.body && !(options.body instanceof Blob) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await fetch(path, {...options, headers});
    const type = response.headers.get('content-type') || '';
    const body = type.includes('application/json') ? await response.json() : await response.blob();
    if (!response.ok) throw new Error(body?.error || `HTTP ${response.status}`);
    return body;
  }

  function projectPayload(project) {
    return {
      version: project.version,
      pages: project.pages || [],
      events: project.events || [],
      contact: project.contact || '',
      created: project.created,
      updated: project.updated,
      pdf_formats: ['A4','A3']
    };
  }

  function queueProjectSync() {
    if (!state.online || !S.proj) return;
    clearTimeout(state.syncTimer);
    state.syncTimer = setTimeout(async () => {
      try {
        await api('/api/projects', {method:'POST', body:JSON.stringify({id:S.proj.id,title:S.proj.title||'Мой календарь',payload:projectPayload(S.proj)})});
        App.emit('server-project-saved', {projectId:S.proj.id});
      } catch (error) {
        console.warn('Project sync deferred:', error.message);
      }
    }, 500);
  }

  async function uploadPage(key, blob) {
    if (!state.online || !(blob instanceof Blob)) return;
    const match = /^([^:]+):(\d{1,2}):(source|processed)$/.exec(key);
    if (!match) return;
    const [,projectId,page,kind] = match;
    try {
      await api(`/api/projects/${encodeURIComponent(projectId)}/pages/${page}/${kind}`, {method:'PUT',headers:{'Content-Type':blob.type||'image/jpeg'},body:blob});
      App.emit('server-page-saved', {projectId,page:+page,kind});
    } catch (error) {
      console.warn('Page sync deferred:', error.message);
    }
  }

  async function restoreProjects() {
    if (!state.online) return;
    try {
      const result = await api('/api/projects');
      const local = projectIndex();
      for (const remote of result.projects || []) {
        if (!local.some(item => item.id === remote.id)) {
          const project = {id:remote.id,title:remote.title,...remote.payload};
          localStorage.setItem('calv13_project_' + remote.id, JSON.stringify(project));
          local.push({id:remote.id,title:remote.title,updated:remote.updated_at,done:(project.pages||[]).filter(Boolean).length,finalF:'A4'});
        }
      }
      saveIndex(local.sort((a,b)=>String(b.updated||'').localeCompare(String(a.updated||''))).slice(0,30));
      if (document.getElementById('cabinet') && !document.getElementById('cabinet').classList.contains('hide')) renderCabinet();
    } catch (error) {
      console.warn('Project restore deferred:', error.message);
    }
  }

  function addConsentControls() {
    const pane = document.querySelector('#accountModal [data-account-pane="login"]');
    const submit = pane?.querySelector('[data-save-email]');
    if (!pane || !submit || pane.querySelector('.server-consents')) return;
    const controls = document.createElement('div');
    controls.className = 'server-consents';
    controls.innerHTML = `
      <label><input type="checkbox" data-accept-terms> <span>Принимаю <button type="button" data-open-terms>Пользовательское соглашение</button> и <button type="button" data-open-offer>оферту</button></span></label>
      <label><input type="checkbox" data-accept-personal> <span>Отдельно даю <button type="button" data-open-personal>согласие на обработку персональных данных</button></span></label>`;
    pane.querySelector('.auth-email').insertBefore(controls, submit);
    const style = document.createElement('style');
    style.textContent = `.server-consents{display:grid;gap:10px;margin:14px 0 2px}.server-consents label{display:grid;grid-template-columns:22px 1fr;gap:8px;align-items:start;color:#c9d8e6;font-size:13px;line-height:1.35}.server-consents input{width:20px!important;height:20px;margin:0;accent-color:#2f78b7}.server-consents button{display:inline;border:0;background:transparent;color:#8fc7e8;padding:0;text-align:left;text-decoration:underline;font:inherit}`;
    document.head.appendChild(style);
    const clickDocument = slug => document.querySelector(`#accountModal [data-document="${slug}"]`)?.click();
    controls.querySelector('[data-open-terms]').onclick = () => clickDocument('terms');
    controls.querySelector('[data-open-offer]').onclick = () => openLegal('offer');
    controls.querySelector('[data-open-personal]').onclick = () => openLegal('personal-data-consent');
    const original = submit.onclick;
    submit.onclick = async event => {
      if (!controls.querySelector('[data-accept-terms]').checked) { toast('Примите соглашение и оферту'); return; }
      if (!controls.querySelector('[data-accept-personal]').checked) { toast('Подтвердите отдельное согласие на обработку данных'); return; }
      const email = pane.querySelector('#menuEmailV15').value.trim();
      let code = pane.querySelector('#menuCodeV15');
      try {
        if (!code) {
          const requested = await api('/api/auth/email/request',{method:'POST',body:JSON.stringify({email})});
          code = document.createElement('input');
          code.id='menuCodeV15'; code.inputMode='numeric'; code.autocomplete='one-time-code';
          code.maxLength=6; code.placeholder='Код из письма'; code.style.marginTop='10px';
          controls.parentNode.insertBefore(code, controls);
          if (requested.development_code) code.value=requested.development_code;
          submit.textContent='Войти'; code.focus();
          toast(requested.delivery==='development' ? 'Тестовый код подставлен' : 'Код отправлен на почту');
          return;
        }
        const verified = await api('/api/auth/email/verify',{method:'POST',body:JSON.stringify({email,code:code.value})});
        localStorage.setItem(AUTH_KEY, verified.token);
        original?.call(submit, event);
        for (const slug of ['terms','offer','personal-data-consent']) {
          await api('/api/consents',{method:'POST',body:JSON.stringify({document_slug:slug,accepted:true,source:'email-registration'})});
        }
        queueProjectSync();
        toast('Вход выполнен');
      } catch (error) {
        toast(error.message || 'Не удалось выполнить вход');
      }
    };
  }

  function connectAuthProviders() {
    const pane = document.querySelector('#accountModal [data-account-pane="login"]');
    if (!pane) return;
    pane.querySelectorAll('[data-social]').forEach(button => button.onclick = () => {
      const provider=button.dataset.social;
      const label=provider==='max'?'MAX':provider==='vk'?'VK':'Telegram';
      toast(state.config?.auth?.[provider] ? `Вход через ${label} готов к подключению перенаправления` : `Вход через ${label} ещё не настроен`);
    });
    const logout=document.querySelector('#accountModal [data-local-logout]');
    if (logout) {
      const fallback=logout.onclick;
      logout.onclick=async event=>{
        try { if(localStorage.getItem(AUTH_KEY)) await api('/api/auth/logout',{method:'POST'}); } catch {}
        localStorage.removeItem(AUTH_KEY);
        fallback?.call(logout,event);
      };
    }
  }

  async function openLegal(slug, fallback) {
    if (!state.online) { fallback?.(); return; }
    try {
      const documentData = await api('/api/legal/' + slug);
      const page = document.getElementById('legalDocumentV15');
      page.querySelector('.document-header b').textContent = documentData.title;
      page.querySelector('.document-body').innerHTML = documentData.html;
      page.classList.remove('hide'); page.scrollTop = 0;
    } catch (error) {
      fallback?.();
    }
  }

  async function connectLegalDocuments() {
    if (!state.online) return;
    try {
      const result = await api('/api/legal');
      const list = document.querySelector('#accountModal .document-list');
      if (!list) return;
      list.innerHTML = (result.documents || []).map(doc => `<button data-server-document="${doc.slug}">${doc.title}<span>›</span></button>`).join('');
      list.querySelectorAll('[data-server-document]').forEach(button => button.onclick = () => openLegal(button.dataset.serverDocument));
    } catch (error) {
      console.warn('Legal documents use embedded copy:', error.message);
    }
  }

  function connectSupport() {
    const modal = document.getElementById('supportModalV15');
    const button = modal?.querySelector('[data-send]');
    if (!button) return;
    const fallback = button.onclick;
    button.onclick = async event => {
      if (!state.online) { fallback?.call(button,event); return; }
      const message = modal.querySelector('#supportMessageV15').value.trim();
      const contact = modal.querySelector('#supportContactV15').value.trim();
      if (message.length < 5) { toast('Коротко опишите, что произошло'); return; }
      try {
        const active = [...document.querySelectorAll('body > section')].find(section => !section.classList.contains('hide'));
        const result = await api('/api/support',{method:'POST',body:JSON.stringify({message,contact,project_id:S.proj?.id||'',page_number:Number.isInteger(S.i)?S.i:null,step:active?.id||'unknown',context:{version:App.version,userAgent:navigator.userAgent}})});
        modal.querySelector('#supportMessageV15').value=''; modal.classList.add('hide');
        toast(`Обращение отправлено: ${result.id}`,3800);
      } catch (error) {
        fallback?.call(button,event);
      }
    };
  }

  App.register({
    id: 'python-server-bridge',
    version: '1.3.0',
    async start() {
      App.version='15.4';
      App.server={state,api,deviceId,queueProjectSync,uploadPage};
      const originalSaveMeta=window.saveMeta;
      if (typeof originalSaveMeta==='function') window.saveMeta=function(...args){const result=originalSaveMeta.apply(this,args);queueProjectSync();return result};
      const originalPut=window.put;
      if (typeof originalPut==='function') window.put=async function(key,blob){const result=await originalPut(key,blob);uploadPage(key,blob);return result};
      const originalGet=window.get;
      if (typeof originalGet==='function') window.get=async function(key){let blob=await originalGet(key);if(blob||!state.online)return blob;const match=/^([^:]+):(\d{1,2}):(source|processed)$/.exec(key);if(!match)return null;try{blob=await api(`/api/projects/${encodeURIComponent(match[1])}/pages/${match[2]}/${match[3]}`);await originalPut(key,blob);return blob}catch{return null}};
      const originalIncident=window.incident;
      if (typeof originalIncident==='function') window.incident=function(code,message,context={}){
        const item=originalIncident(code,message,context);
        if(state.online)api('/api/support',{method:'POST',body:JSON.stringify({
          message:`${code}: ${String(message||'Техническая ошибка')}`,
          project_id:S.proj?.id||'',page_number:Number.isInteger(S.i)?S.i:null,
          step:document.querySelector('body > section:not(.hide)')?.id||'unknown',
          context:{...context,automatic:true,local_incident_id:item.id,version:App.version,userAgent:navigator.userAgent}
        })}).catch(error=>console.warn('Incident delivery deferred:',error.message));
        return item;
      };
      connectSupport();
      try {
        state.config=await api('/api/config'); state.online=true;
        addConsentControls();
        connectAuthProviders();
        const badge=document.querySelector('.serverbadge');if(badge)badge.textContent='Сервер подключен · проекты синхронизируются';
        await Promise.all([connectLegalDocuments(),restoreProjects()]);
      } catch {
        state.online=false;
      }
    }
  });
})();
