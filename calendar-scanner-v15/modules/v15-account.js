// V15.1 account, documentation and support module.
(function () {
  'use strict';

  const App = window.CalendarApp;
  if (!App) return;

  const CONTACT_KEY = 'calendar_account_v15';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const style = document.createElement('style');
  style.textContent = `
    .app-topbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0 0 12px}
    .app-topbar__mark{display:flex;align-items:center;gap:9px;min-width:0;color:#b8cbe0;font-size:13px;font-weight:800;letter-spacing:.03em}
    .app-topbar__mark i{width:34px;height:34px;border-radius:11px;background:#18344f;display:grid;place-items:center;color:#fff;font-style:normal;font-size:19px}
    .app-topbar__actions{display:flex;gap:7px}
    .top-action{min-height:38px;border:1px solid #29455f;border-radius:12px;background:#102238;color:#eaf3fb;padding:8px 12px;font-weight:750;font-size:14px}
    .top-action.primary{border-color:#367eb7;background:#2f78b7}
    .top-action.account-on{background:#173953;border-color:#2c668d;max-width:145px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .service-modal{position:fixed;z-index:120;inset:0;background:#04101cdc;display:grid;place-items:end center;padding:18px}
    .service-modal.hide{display:none}
    .service-card{width:min(480px,100%);max-height:min(760px,calc(100dvh - 36px));overflow:auto;background:#0e2035;border:1px solid #294761;border-radius:24px;padding:18px;box-shadow:0 26px 70px #0008}
    .service-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:15px}
    .service-head h2{font-size:25px;line-height:1.1;margin:0 0 5px}.service-head p{margin:0;color:#9fb2ca;line-height:1.4}
    .service-close{flex:0 0 auto;width:38px;height:38px;border:0;border-radius:12px;background:#182d45;color:#fff;font-size:22px}
    .auth-options{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:12px 0}
    .auth-option{min-height:51px;border:1px solid #29445f;border-radius:14px;background:#132942;color:#fff;padding:11px;font-weight:800;text-align:left}
    .auth-option small{display:block;color:#92abc3;font-size:12px;font-weight:500;margin-top:3px}
    .auth-email{border-top:1px solid #263e57;margin-top:14px;padding-top:14px}
    .auth-email label,.support-form label{display:block;color:#c8d8e7;font-size:14px;font-weight:700;margin-bottom:7px}
    .auth-email input,.support-form input,.support-form textarea{width:100%;border:1px solid #2b4864;border-radius:13px;background:#0a192b;color:#fff;padding:13px;font-size:16px}
    .support-form textarea{min-height:118px;resize:vertical}
    .form-note{font-size:12px;color:#86a0ba;line-height:1.45;margin:9px 0 0}
    .service-submit{width:100%;border:0;border-radius:14px;background:#2f78b7;color:#fff;padding:14px;margin-top:10px;font-weight:850;font-size:15px}
    .signed-card{background:#102942;border:1px solid #2d5876;border-radius:15px;padding:14px;margin:12px 0}
    .signed-card b{display:block;margin-bottom:4px}.signed-card small{color:#9fb2ca}
    .text-action{border:0;background:transparent;color:#93b9dc;padding:10px 0;font-weight:700}
    .help-nav{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:14px;background:#09182a;padding:4px;border-radius:13px}
    .help-nav button{border:0;border-radius:10px;background:transparent;color:#9fb2ca;padding:10px 5px;font-weight:750;font-size:13px}
    .help-nav button.on{background:#244563;color:#fff}
    .help-pane{display:none}.help-pane.on{display:block}
    .help-pane h3{margin:17px 0 7px;font-size:17px}.help-pane p{color:#bfd0df;line-height:1.5;margin:0 0 10px}
    .help-list{margin:0;padding:0;list-style:none;counter-reset:help}
    .help-list li{counter-increment:help;display:grid;grid-template-columns:34px 1fr;gap:10px;align-items:start;margin:12px 0;color:#d9e5ef;line-height:1.45}
    .help-list li:before{content:counter(help);width:30px;height:30px;border-radius:10px;background:#1c3b58;display:grid;place-items:center;font-weight:850;color:#fff}
    .legal-link{width:100%;display:flex;justify-content:space-between;align-items:center;border:0;border-bottom:1px solid #263e57;background:transparent;color:#e6f0f8;padding:13px 2px;text-align:left;font-weight:700}
    .legal-link span{color:#7591aa}
    .cabinet-footer{margin:26px 2px 0;padding:19px 4px calc(12px + env(safe-area-inset-bottom));border-top:1px solid #1d334b;color:#7690aa;text-align:center}
    .cabinet-footer__actions{display:flex;justify-content:center;flex-wrap:wrap;gap:6px 14px;margin-bottom:10px}
    .cabinet-footer button{border:0;background:transparent;color:#a9c3da;padding:5px 0;font-weight:700;font-size:14px}
    .cabinet-footer small{font-size:12px;line-height:1.4}
    @media(min-width:560px){.service-modal{place-items:center}.app-topbar{margin-top:2px}}
    @media(max-width:390px){.app-topbar__mark span{display:none}.top-action{padding-inline:10px}.auth-options{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  function savedContact() {
    try { return JSON.parse(localStorage.getItem(CONTACT_KEY) || 'null'); }
    catch (_) { return null; }
  }

  function makeModal(id, body) {
    let modal = document.getElementById(id);
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = id;
    modal.className = 'service-modal hide';
    modal.innerHTML = `<div class="service-card" role="dialog" aria-modal="true">${body}</div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', event => { if (event.target === modal) closeModal(modal); });
    modal.querySelectorAll('[data-close]').forEach(button => button.onclick = () => closeModal(modal));
    return modal;
  }

  function openModal(modal) {
    modal.classList.remove('hide');
    const first = modal.querySelector('button,input,textarea');
    if (first) setTimeout(() => first.focus(), 20);
  }

  function closeModal(modal) { modal.classList.add('hide'); }

  function updateAccountButton() {
    const button = document.getElementById('accountEntry');
    if (!button) return;
    const account = savedContact();
    button.textContent = account ? account.value : 'Войти';
    button.title = account ? `Выполнен локальный вход: ${account.value}` : 'Войти или зарегистрироваться';
    button.classList.toggle('account-on', !!account);
  }

  function authModal() {
    const modal = makeModal('accountModal', `
      <div class="service-head"><div><h2>Вход</h2><p>Сохраняйте проекты и продолжайте работу на другом устройстве.</p></div><button class="service-close" data-close aria-label="Закрыть">×</button></div>
      <div class="auth-options">
        <button class="auth-option" data-provider="telegram">Telegram<small>Вход через аккаунт</small></button>
        <button class="auth-option" data-provider="max">MAX<small>Вход через аккаунт</small></button>
        <button class="auth-option" data-provider="vk">VK<small>Вход через аккаунт</small></button>
        <button class="auth-option" data-provider="email">Почта<small>Код придёт в письме</small></button>
      </div>
      <div class="auth-email">
        <label for="v15Email">Электронная почта</label>
        <input id="v15Email" type="email" inputmode="email" autocomplete="email" placeholder="name@example.ru">
        <button class="service-submit" data-email>Продолжить</button>
        <p class="form-note">Проектом можно пользоваться без входа. Серверная синхронизация и реальные коды подтверждения включатся после публикации.</p>
      </div>
      <div class="signed-card hide" data-signed></div>
      <button class="text-action hide" data-logout>Выйти из тестового профиля</button>`);
    const emailBox = modal.querySelector('.auth-email');
    const signed = modal.querySelector('[data-signed]');
    const logout = modal.querySelector('[data-logout]');
    const refresh = () => {
      const account = savedContact();
      emailBox.classList.toggle('hide', !!account);
      signed.classList.toggle('hide', !account);
      logout.classList.toggle('hide', !account);
      if (account) signed.innerHTML = `<b>Вы вошли как ${esc(account.value)}</b><small>Сейчас профиль хранится только на этом устройстве.</small>`;
      updateAccountButton();
    };
    modal.querySelectorAll('[data-provider]').forEach(button => {
      button.onclick = () => {
        const provider = button.dataset.provider;
        if (provider === 'email') { modal.querySelector('#v15Email').focus(); return; }
        const label = provider === 'max' ? 'MAX' : provider === 'vk' ? 'VK' : 'Telegram';
        toast(`Вход через ${label} включим на сервере`, 3200);
      };
    });
    modal.querySelector('[data-email]').onclick = () => {
      const value = modal.querySelector('#v15Email').value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) { toast('Проверьте адрес электронной почты'); return; }
      localStorage.setItem(CONTACT_KEY, JSON.stringify({type:'email', value, savedAt:new Date().toISOString()}));
      refresh();
      toast('Тестовый профиль сохранён на этом устройстве');
    };
    logout.onclick = () => { localStorage.removeItem(CONTACT_KEY); refresh(); };
    modal.refresh = refresh;
    refresh();
    return modal;
  }

  function helpModal() {
    const modal = makeModal('documentationModal', `
      <div class="service-head"><div><h2>Справка</h2><p>Всё необходимое для создания календаря.</p></div><button class="service-close" data-close aria-label="Закрыть">×</button></div>
      <div class="help-nav"><button class="on" data-pane="start">Начало</button><button data-pane="scan">Съёмка</button><button data-pane="about">О проекте</button></div>
      <section class="help-pane on" data-content="start"><ol class="help-list"><li>Нарисуйте обложку и 12 месяцев карандашами, фломастерами или красками.</li><li>Откройте новый проект и сфотографируйте через приложение все 13 страниц по порядку.</li><li>Проверьте найденные даты, добавьте дни рождения и события.</li><li>Получите сразу два готовых PDF — A4 и A3.</li></ol></section>
      <section class="help-pane" data-content="scan"><h3>Хороший снимок</h3><p>Положите лист ровно, обеспечьте мягкий свет без бликов и держите телефон параллельно бумаге. Все четыре угловые метки должны быть видны.</p><h3>Если приложение ошиблось</h3><p>Переснимите страницу. Сохранённые страницы доступны в меню проекта — любую можно открыть, проверить и заменить.</p></section>
      <section class="help-pane" data-content="about"><h3>«Нарисуй сам»</h3><p>Проект для детей и взрослых: бумажный рисунок проходит обработку через приложение, а календарная сетка и важные даты формируются отдельно.</p><button class="legal-link" data-legal="terms">Пользовательское соглашение <span>›</span></button><button class="legal-link" data-legal="privacy">Политика конфиденциальности <span>›</span></button><button class="legal-link" data-legal="operator">Юридическая информация <span>›</span></button></section>`);
    modal.querySelectorAll('[data-pane]').forEach(button => button.onclick = () => {
      modal.querySelectorAll('[data-pane]').forEach(item => item.classList.toggle('on', item === button));
      modal.querySelectorAll('[data-content]').forEach(item => item.classList.toggle('on', item.dataset.content === button.dataset.pane));
    });
    modal.querySelectorAll('[data-legal]').forEach(button => button.onclick = () => {
      const texts = {
        terms: 'Текст пользовательского соглашения и правила сервиса будут опубликованы до запуска.',
        privacy: 'Политика опишет хранение проектов, фотографий, контактных данных и обращений в поддержку.',
        operator: 'Оператор сервиса — ИП. Полные реквизиты укажем перед публикацией и подключением оплаты и чеков.'
      };
      toast(texts[button.dataset.legal], 5200);
    });
    return modal;
  }

  function supportModal() {
    const modal = makeModal('supportModalV15', `
      <div class="service-head"><div><h2>Поддержка</h2><p>Опишите проблему — приложение сохранит технические сведения о текущем шаге.</p></div><button class="service-close" data-close aria-label="Закрыть">×</button></div>
      <div class="support-form"><label for="supportMessageV15">Что произошло?</label><textarea id="supportMessageV15" placeholder="Например: приложение не распознало июнь"></textarea><label for="supportContactV15" style="margin-top:12px">Куда ответить</label><input id="supportContactV15" placeholder="Email, Telegram или MAX"><button class="service-submit" data-send>Отправить обращение</button><p class="form-note">До подключения сервера обращение сохраняется на этом устройстве. После публикации оно будет автоматически отправляться в поддержку.</p></div>`);
    modal.querySelector('[data-send]').onclick = () => {
      const message = modal.querySelector('#supportMessageV15').value.trim();
      const contact = modal.querySelector('#supportContactV15').value.trim();
      if (message.length < 5) { toast('Коротко опишите, что произошло'); return; }
      const active = [...document.querySelectorAll('body > section')].find(section => !section.classList.contains('hide'));
      const item = incident('USER_REPORT', message, {page:S.i, project:S.proj?.id || null, contact, step:active?.id || 'unknown'});
      modal.querySelector('#supportMessageV15').value = '';
      closeModal(modal);
      toast(`Обращение сохранено: ${item.id}`, 3800);
      App.emit('support-created', {id:item.id});
    };
    return modal;
  }

  App.register({
    id: 'account-help-support',
    version: '1.1.0',
    start() {
      App.version = '15.1';
      const cabinet = document.getElementById('cabinet');
      const brand = cabinet?.querySelector('.brand');
      if (!cabinet || !brand) return;
      const topbar = document.createElement('div');
      topbar.className = 'app-topbar';
      topbar.innerHTML = `<div class="app-topbar__mark"><i>✎</i><span>НАРИСУЙ САМ</span></div><div class="app-topbar__actions"><button id="documentationEntry" class="top-action">Справка</button><button id="accountEntry" class="top-action primary">Войти</button></div>`;
      cabinet.insertBefore(topbar, brand);
      const auth = authModal(), help = helpModal(), support = supportModal();
      document.getElementById('accountEntry').onclick = () => { auth.refresh(); openModal(auth); };
      document.getElementById('documentationEntry').onclick = () => openModal(help);
      const footer = document.createElement('footer');
      footer.className = 'cabinet-footer';
      footer.innerHTML = `<div class="cabinet-footer__actions"><button data-help>Как пользоваться</button><button data-support>Поддержка</button><button data-about>О проекте</button></div><small>«Нарисуй сам» · Амплитуда<br>Для детей и взрослых</small>`;
      cabinet.appendChild(footer);
      footer.querySelector('[data-help]').onclick = () => openModal(help);
      footer.querySelector('[data-support]').onclick = () => openModal(support);
      footer.querySelector('[data-about]').onclick = () => { openModal(help); help.querySelector('[data-pane="about"]').click(); };
      const scanSupport = document.getElementById('support');
      if (scanSupport) scanSupport.onclick = () => openModal(support);
      document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        document.querySelectorAll('.service-modal:not(.hide)').forEach(closeModal);
      });
      updateAccountButton();
    }
  });
})();
