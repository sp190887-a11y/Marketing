// V15.2 unified account menu and readable legal documents.
(function () {
  'use strict';

  const App = window.CalendarApp;
  if (!App) return;
  const CONTACT_KEY = 'calendar_account_v15';

  const css = document.createElement('style');
  css.textContent = `
    .app-topbar__actions #documentationEntry{display:none!important}
    .app-topbar__actions{margin-left:auto}
    #accountEntry{display:flex;align-items:center;gap:8px;max-width:180px}
    #accountEntry:before{content:'◉';font-size:15px;color:#d8f0ff}
    .account-shell{padding:0!important;overflow:hidden!important}
    .account-cover{padding:21px 20px 18px;background:linear-gradient(145deg,#173a59 0%,#10283f 62%,#381c3a 125%);border-bottom:1px solid #31506b}
    .account-cover__top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
    .account-cover__eyebrow{font-size:12px;color:#8ecbe4;letter-spacing:.08em;font-weight:850}
    .account-cover h2{font-size:28px;line-height:1.05;margin:7px 0 7px}
    .account-cover p{margin:0;color:#bad0e2;line-height:1.4;font-size:14px}
    .account-avatar{width:48px;height:48px;border-radius:16px;background:linear-gradient(145deg,#55b8db,#df5d91);display:grid;place-items:center;font-size:21px;font-weight:900;box-shadow:0 10px 25px #0004}
    .account-close{position:absolute;right:15px;top:15px;width:38px;height:38px;border:0;border-radius:12px;background:#07172799;color:#fff;font-size:22px}
    .account-content{padding:15px 16px 18px}
    .profile-strip{display:flex;align-items:center;justify-content:space-between;gap:12px;background:#0a192a;border:1px solid #243f59;border-radius:16px;padding:13px 14px;margin-bottom:12px}
    .profile-strip b{display:block;font-size:15px}.profile-strip small{display:block;color:#87a1b9;margin-top:3px}
    .profile-strip button{border:0;border-radius:11px;background:#2f78b7;color:#fff;padding:10px 14px;font-weight:800;white-space:nowrap}
    .account-menu{display:grid;gap:8px}
    .account-menu button{width:100%;border:1px solid #263f59;border-radius:15px;background:#10243a;color:#fff;padding:13px 14px;display:grid;grid-template-columns:39px 1fr 20px;gap:11px;align-items:center;text-align:left}
    .account-menu button i{width:39px;height:39px;border-radius:12px;background:#193550;color:#a9d7ea;display:grid;place-items:center;font-style:normal;font-size:19px}
    .account-menu button b{display:block;font-size:15px}.account-menu button small{display:block;color:#87a0b8;margin-top:3px;line-height:1.25}
    .account-menu button em{font-style:normal;color:#6f8aa3;font-size:22px}
    .account-menu button[data-menu='support'] i{background:#38243d;color:#f2a8ca}
    .account-menu button[data-menu='documents'] i{background:#352f1d;color:#f1cf66}
    .account-pane{display:none}.account-pane.on{display:block}
    .pane-back{border:0;background:transparent;color:#abd0ea;padding:2px 0 13px;font-weight:800;font-size:14px}
    .pane-title{font-size:23px;margin:0 0 6px}.pane-lead{color:#9eb4c8;line-height:1.45;margin:0 0 16px}
    .guide-steps{list-style:none;padding:0;margin:0;counter-reset:guide}
    .guide-steps li{counter-increment:guide;display:grid;grid-template-columns:36px 1fr;gap:11px;margin:13px 0;color:#d9e5ef;line-height:1.45}
    .guide-steps li:before{content:counter(guide);width:32px;height:32px;border-radius:11px;background:#1e405f;color:#fff;display:grid;place-items:center;font-weight:900}
    .tip-card{background:#0b1b2d;border:1px solid #26425c;border-radius:15px;padding:14px;margin:10px 0}
    .tip-card b{display:block;margin-bottom:5px}.tip-card p{margin:0;color:#adc0d1;line-height:1.45}
    .material-row{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0 16px}
    .material-row span{background:#162e47;border:1px solid #2d4b65;border-radius:999px;padding:7px 10px;color:#c9d9e7;font-size:13px;font-weight:700}
    .document-list{display:grid;gap:9px}
    .document-list button{width:100%;border:1px solid #29455f;border-radius:15px;background:#10243a;color:#fff;padding:14px;display:flex;align-items:center;justify-content:space-between;text-align:left;font-weight:800}
    .document-list button span{color:#7994ac;font-size:22px}
    .document-page{position:fixed;z-index:140;inset:0;background:#07111f;overflow:auto}
    .document-page.hide{display:none}
    .document-header{position:sticky;top:0;z-index:2;display:flex;align-items:center;gap:11px;background:#091726ed;backdrop-filter:blur(14px);padding:calc(10px + env(safe-area-inset-top)) 14px 10px;border-bottom:1px solid #203850}
    .document-header button{width:42px;height:42px;border:0;border-radius:13px;background:#152b42;color:#fff;font-size:24px}
    .document-header b{font-size:17px}
    .document-body{max-width:680px;margin:auto;padding:22px 20px calc(40px + env(safe-area-inset-bottom));color:#d8e4ee;line-height:1.6}
    .document-body .draft{display:inline-flex;border:1px solid #6d5c2c;background:#312b18;color:#f0d87b;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:800}
    .document-body h1{font-size:28px;line-height:1.12;margin:14px 0 8px}.document-body h2{font-size:18px;margin:23px 0 7px;color:#fff}
    .document-body p,.document-body li{color:#b9cbda}.document-body ul{padding-left:20px}.document-body strong{color:#fff}
    .document-note{border:1px solid #38546e;background:#0e2135;border-radius:15px;padding:13px 14px;margin:16px 0;color:#c7d8e7}
    .cabinet-footer__actions button[data-help],.cabinet-footer__actions button[data-about]{display:none}
    @media(max-width:420px){.account-cover{padding-right:62px}.account-cover h2{font-size:25px}.account-menu button{padding:11px 12px}.profile-strip{align-items:flex-start}.profile-strip button{padding:9px 11px}}
  `;
  document.head.appendChild(css);

  function contact() {
    try { return JSON.parse(localStorage.getItem(CONTACT_KEY) || 'null'); }
    catch (_) { return null; }
  }

  const documents = {
    terms: {
      title: 'Пользовательское соглашение',
      body: `<span class="draft">Редакция 1.0 · 15 сентября 2026</span><h1>Пользовательское соглашение</h1><p>Настоящие условия регулируют использование приложения «Нарисуй сам» для съёмки рисунков, создания календарных макетов и передачи заказа в типографию.</p><h2>1. Возможности сервиса</h2><p>Пользователь может создать проект без регистрации, сфотографировать обложку и 12 месяцев, проверить страницы, добавить события и получить макеты A4 и A3.</p><h2>2. Учётная запись</h2><p>Вход нужен для синхронизации проектов между устройствами, восстановления доступа и сопровождения заказа. Доступные способы входа могут включать электронную почту, Telegram, MAX и VK.</p><h2>3. Пользовательские материалы</h2><p>Пользователь подтверждает, что вправе использовать загружаемые рисунки и фотографии. Авторские права на рисунки сохраняются за их владельцем. Сервис получает право обработать материалы только для создания макета, хранения проекта и выполнения заказа.</p><h2>4. Печать и заказ</h2><p>До оплаты пользователь проверяет страницы, даты, формат и итоговый PDF. Стоимость, срок изготовления, доставка и порядок оплаты показываются отдельно перед оформлением заказа.</p><h2>5. Ограничение ответственности</h2><p>Автоматическое распознавание может потребовать проверки или пересъёмки. Пользователь должен подтвердить итоговый макет перед отправкой в печать.</p><h2>6. Оператор</h2><p>Заказы, оплата и кассовые чеки оформляются через ИП. Полные реквизиты оператора и контакты будут внесены до публичного запуска.</p>`
    },
    privacy: {
      title: 'Политика конфиденциальности',
      body: `<span class="draft">Редакция 1.0 · 15 сентября 2026</span><h1>Политика конфиденциальности</h1><p>Политика объясняет, какие данные использует приложение «Нарисуй сам» и зачем они нужны.</p><h2>1. Какие данные обрабатываются</h2><ul><li>адрес электронной почты или идентификатор выбранного способа входа;</li><li>название проекта, рисунки, фотографии страниц и созданные PDF;</li><li>добавленные пользователем даты и подписи событий;</li><li>технические сведения об устройстве, ошибке, странице и этапе работы;</li><li>контактные и платёжные сведения, необходимые для оформления заказа.</li></ul><h2>2. Для чего нужны данные</h2><p>Для сохранения и синхронизации проекта, обработки фотографий, создания календаря, выполнения заказа, отправки уведомлений и работы поддержки.</p><h2>3. Хранение и передача</h2><p>Данные хранятся столько, сколько необходимо для работы проекта, исполнения заказа и требований закона. Передача допускается только сервисам, которые обеспечивают авторизацию, хранение, оплату, доставку и связь с пользователем.</p><h2>4. Детские рисунки</h2><p>Если календарь создаёт ребёнок, загрузку материалов и оформление заказа выполняет родитель или другой законный представитель.</p><h2>5. Права пользователя</h2><p>Пользователь может запросить сведения об обработке данных, исправление, выгрузку или удаление аккаунта и проектов, если закон не требует сохранить отдельные документы.</p><h2>6. Контакты</h2><p>Контакт оператора для обращений по персональным данным будет указан вместе с полными реквизитами ИП до запуска.</p>`
    },
    operator: {
      title: 'Юридическая информация',
      body: `<span class="draft">Редакция 1.0 · 15 сентября 2026</span><h1>Юридическая информация</h1><div class="document-note"><strong>Принятое решение:</strong> оператором сервиса, продавцом печатной продукции и получателем оплаты выступает ИП. Кассовый чек формируется от имени этого ИП.</div><h2>Реквизиты оператора</h2><p>Перед публикацией здесь указываются полные ФИО индивидуального предпринимателя, ИНН, ОГРНИП, юридический адрес, электронная почта и телефон.</p><h2>Оплата и чеки</h2><p>Перед оплатой пользователь видит состав заказа, форматы, количество, цену, способ получения и итоговую сумму. После оплаты электронный чек направляется по указанным контактным данным.</p><h2>Изготовление</h2><p>Печатная продукция изготавливается по утверждённому пользователем макету. Условия производства, сроки, доставка, возврат и порядок рассмотрения претензий указываются при оформлении заказа.</p><h2>Поддержка</h2><p>Связаться с поддержкой можно из меню аккаунта или кнопкой «Сообщить о проблеме» во время съёмки.</p>`
    }
  };

  function createDocumentPage() {
    let page = document.getElementById('legalDocumentV15');
    if (page) return page;
    page = document.createElement('article');
    page.id = 'legalDocumentV15';
    page.className = 'document-page hide';
    page.innerHTML = `<div class="document-header"><button aria-label="Назад">‹</button><b></b></div><div class="document-body"></div>`;
    document.body.appendChild(page);
    page.querySelector('button').onclick = () => page.classList.add('hide');
    return page;
  }

  function showDocument(type) {
    const data = documents[type];
    if (!data) return;
    const page = createDocumentPage();
    page.querySelector('.document-header b').textContent = data.title;
    page.querySelector('.document-body').innerHTML = data.body;
    page.classList.remove('hide');
    page.scrollTop = 0;
  }

  function openSupport() {
    const support = document.getElementById('supportModalV15');
    const account = document.getElementById('accountModal');
    if (account) account.classList.add('hide');
    if (support) support.classList.remove('hide');
  }

  function buildUnifiedMenu() {
    const modal = document.getElementById('accountModal');
    if (!modal) return;
    const card = modal.querySelector('.service-card');
    card.className = 'service-card account-shell';
    card.innerHTML = `
      <button class="account-close" data-close-account aria-label="Закрыть">×</button>
      <div class="account-cover"><div class="account-cover__top"><div><div class="account-cover__eyebrow">АМПЛИТУДА</div><h2>Нарисуй сам</h2><p>Календарь из ваших рисунков</p></div><div class="account-avatar">АМ</div></div></div>
      <div class="account-content">
        <section class="account-pane on" data-account-pane="menu">
          <div class="profile-strip"><div><b data-profile-name>Гостевой режим</b><small data-profile-note>Проекты сохраняются на этом устройстве</small></div><button data-open-login>Войти</button></div>
          <nav class="account-menu">
            <button data-menu="start"><i>1</i><span><b>Как начать</b><small>От рисунка до двух готовых PDF</small></span><em>›</em></button>
            <button data-menu="scan"><i>⌁</i><span><b>Съёмка страниц</b><small>Свет, положение телефона и пересъёмка</small></span><em>›</em></button>
            <button data-menu="about"><i>✎</i><span><b>О проекте</b><small>Для детей, взрослых и семейных историй</small></span><em>›</em></button>
            <button data-menu="documents"><i>§</i><span><b>Документы</b><small>Соглашение, политика и реквизиты</small></span><em>›</em></button>
            <button data-menu="support"><i>?</i><span><b>Поддержка</b><small>Сообщить о проблеме</small></span><em>›</em></button>
          </nav>
        </section>
        <section class="account-pane" data-account-pane="login"><button class="pane-back" data-back>‹ Назад</button><h3 class="pane-title">Вход</h3><p class="pane-lead">Войдите, чтобы позже продолжить проект на другом устройстве.</p><div class="auth-options"><button class="auth-option" data-social="telegram">Telegram<small>Вход через аккаунт</small></button><button class="auth-option" data-social="max">MAX<small>Вход через аккаунт</small></button><button class="auth-option" data-social="vk">VK<small>Вход через аккаунт</small></button><button class="auth-option" data-show-email>Почта<small>Код придёт в письме</small></button></div><div class="auth-email"><label for="menuEmailV15">Электронная почта</label><input id="menuEmailV15" type="email" inputmode="email" autocomplete="email" placeholder="name@example.ru"><button class="service-submit" data-save-email>Продолжить</button><p class="form-note">На тесте профиль сохраняется только на этом устройстве. Настоящее подтверждение включится на сервере.</p></div><button class="text-action hide" data-local-logout>Выйти из тестового профиля</button></section>
        <section class="account-pane" data-account-pane="start"><button class="pane-back" data-back>‹ Назад</button><h3 class="pane-title">Как начать</h3><p class="pane-lead">Один проект — обложка и 12 месяцев.</p><ol class="guide-steps"><li>Нарисуйте страницы карандашами, фломастерами или красками.</li><li>Создайте проект и сфотографируйте через приложение все 13 страниц по порядку.</li><li>Проверьте рисунки и найденные даты. Любую страницу можно открыть и переснять.</li><li>Добавьте дни рождения и события — не больше двух на один день.</li><li>Получите сразу два файла: A4 и A3.</li></ol></section>
        <section class="account-pane" data-account-pane="scan"><button class="pane-back" data-back>‹ Назад</button><h3 class="pane-title">Съёмка страниц</h3><p class="pane-lead">Приложение само выравнивает лист и убирает фотографию сетки.</p><div class="tip-card"><b>Ровный свет</b><p>Снимайте без резких теней и бликов. Лучше положить лист на однотонную поверхность.</p></div><div class="tip-card"><b>Весь лист в рамке</b><p>Держите телефон параллельно бумаге. Все четыре угловые метки должны быть видны.</p></div><div class="tip-card"><b>Проверка результата</b><p>После съёмки сравните изображение. Если линии потерялись или страница определилась неверно — нажмите «Переснять».</p></div></section>
        <section class="account-pane" data-account-pane="about"><button class="pane-back" data-back>‹ Назад</button><h3 class="pane-title">О проекте</h3><p class="pane-lead">«Нарисуй сам» помогает превратить бумажные рисунки в настоящий семейный календарь.</p><div class="material-row"><span>Карандаши</span><span>Фломастеры</span><span>Мелки</span><span>Краски</span></div><div class="tip-card"><b>Для детей и взрослых</b><p>Можно рисовать одному, всей семьёй или сохранить памятные рисунки за год.</p></div><div class="tip-card"><b>Чистый печатный макет</b><p>Фотография проходит обработку через приложение. Рисунок сохраняется отдельно, а календарная сетка и даты строятся заново.</p></div></section>
        <section class="account-pane" data-account-pane="documents"><button class="pane-back" data-back>‹ Назад</button><h3 class="pane-title">Документы</h3><p class="pane-lead">Тексты уже открываются и читаются полностью. Перед запуском останется внести точные реквизиты ИП.</p><div class="document-list"><button data-document="terms">Пользовательское соглашение <span>›</span></button><button data-document="privacy">Политика конфиденциальности <span>›</span></button><button data-document="operator">Юридическая информация <span>›</span></button></div></section>
      </div>`;

    function showPane(name) {
      card.querySelectorAll('[data-account-pane]').forEach(pane => pane.classList.toggle('on', pane.dataset.accountPane === name));
      card.scrollTop = 0;
    }
    function refreshProfile() {
      const saved = contact();
      card.querySelector('[data-profile-name]').textContent = saved ? saved.value : 'Гостевой режим';
      card.querySelector('[data-profile-note]').textContent = saved ? 'Тестовый профиль на этом устройстве' : 'Проекты сохраняются на этом устройстве';
      card.querySelector('[data-open-login]').textContent = saved ? 'Профиль' : 'Войти';
      card.querySelector('[data-local-logout]').classList.toggle('hide', !saved);
      const entry = document.getElementById('accountEntry');
      if (entry) entry.textContent = saved ? saved.value : 'Войти';
    }
    card.querySelector('[data-close-account]').onclick = () => modal.classList.add('hide');
    card.querySelector('[data-open-login]').onclick = () => showPane('login');
    card.querySelectorAll('[data-back]').forEach(button => button.onclick = () => showPane('menu'));
    card.querySelectorAll('[data-menu]').forEach(button => button.onclick = () => {
      if (button.dataset.menu === 'support') { openSupport(); return; }
      showPane(button.dataset.menu);
    });
    card.querySelectorAll('[data-document]').forEach(button => button.onclick = () => showDocument(button.dataset.document));
    card.querySelectorAll('[data-social]').forEach(button => button.onclick = () => {
      const label = button.dataset.social === 'max' ? 'MAX' : button.dataset.social === 'vk' ? 'VK' : 'Telegram';
      toast(`Вход через ${label} подключится на сервере`, 3200);
    });
    card.querySelector('[data-show-email]').onclick = () => card.querySelector('#menuEmailV15').focus();
    card.querySelector('[data-save-email]').onclick = () => {
      const value = card.querySelector('#menuEmailV15').value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) { toast('Проверьте адрес электронной почты'); return; }
      localStorage.setItem(CONTACT_KEY, JSON.stringify({type:'email', value, savedAt:new Date().toISOString()}));
      refreshProfile(); showPane('menu'); toast('Тестовый профиль сохранён');
    };
    card.querySelector('[data-local-logout]').onclick = () => {
      localStorage.removeItem(CONTACT_KEY); refreshProfile(); showPane('menu');
    };
    modal.resetMenu = () => { refreshProfile(); showPane('menu'); };
    refreshProfile(); showPane('menu');
  }

  App.register({
    id: 'unified-account-menu',
    version: '1.2.0',
    start() {
      App.version = '15.2';
      const separateHelp = document.getElementById('documentationEntry');
      if (separateHelp) separateHelp.remove();
      const oldHelpModal = document.getElementById('documentationModal');
      if (oldHelpModal) oldHelpModal.remove();
      buildUnifiedMenu();
      const entry = document.getElementById('accountEntry');
      const modal = document.getElementById('accountModal');
      if (entry && modal) entry.onclick = () => { modal.resetMenu?.(); modal.classList.remove('hide'); };

      const footer = document.querySelector('.cabinet-footer__actions');
      if (footer) {
        footer.innerHTML = '<button data-documents>Документы</button><button data-support>Поддержка</button>';
        footer.querySelector('[data-documents]').onclick = () => {
          modal.resetMenu?.(); modal.classList.remove('hide');
          modal.querySelector('[data-menu="documents"]')?.click();
        };
        footer.querySelector('[data-support]').onclick = openSupport;
      }
      createDocumentPage();
    }
  });
})();
