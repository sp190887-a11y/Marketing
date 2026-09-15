// V15 product shell. Keeps the verified V14.5 scanner and adds independent modules.
(function () {
  'use strict';

  const App = window.CalendarApp = window.CalendarApp || {
    version: '15.0',
    modules: new Map(),
    register(module) {
      if (!module || !module.id) throw new Error('Module id is required');
      this.modules.set(module.id, module);
      if (typeof module.start === 'function') module.start(this);
      document.dispatchEvent(new CustomEvent('calendar:module-ready', {detail: {id: module.id}}));
    },
    emit(name, detail) {
      document.dispatchEvent(new CustomEvent('calendar:' + name, {detail}));
    }
  };

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const style = document.createElement('style');
  style.textContent = `
    :root{--paper:#fbfaf5;--ink:#102033;--cyan:#55b8db;--magenta:#df5d91;--sun:#f1c84b}
    .ver{display:none!important}
    .dual-note{margin-top:10px;padding:12px;border:1px solid #2c4562;border-radius:12px;color:#cfdaea;background:#0b1a2d}
    .pdf-grid{display:grid;gap:10px;margin-top:14px}
    .pdf-card{border:1px solid #29445f;border-radius:16px;background:#0d1b2e;padding:14px}
    .pdf-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
    .pdf-head b{font-size:20px}.pdf-head small{color:#9fb2ca}
    .pdf-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}
    .pdf-actions button{border:0;border-radius:12px;padding:12px 9px;font-weight:800;background:#17314d;color:#fff}
    .pdf-actions .download{background:#2f78b7}
    .page-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:14px}
    .page-card{border:1px solid #20344f;border-radius:15px;background:#0d1b2e;color:#fff;padding:0;overflow:hidden;text-align:left}
    .page-thumb{aspect-ratio:210/297;background:#f5f2e9;display:grid;place-items:center;overflow:hidden}
    .page-thumb img{width:100%;height:100%;object-fit:cover}
    .page-thumb span{color:#6f7f90;font-size:30px}
    .page-info{display:flex;justify-content:space-between;gap:6px;padding:10px;font-size:13px}
    .page-info strong{overflow:hidden;text-overflow:ellipsis}
    .page-ready{color:#52d89a}.page-empty{color:#7890aa}
    .page-auto{color:#f1c84b}
    .page-list-actions{grid-column:1/-1;display:grid;gap:8px;margin-top:4px}
    .sheet-modal{position:fixed;z-index:90;inset:0;background:#07111f;display:flex;flex-direction:column}
    .sheet-modal.hide{display:none}
    .sheet-modal header{flex:none}
    .sheet-body{padding:14px;overflow:auto;flex:1}
    .sheet-image{width:100%;max-height:67dvh;object-fit:contain;background:var(--paper);border-radius:14px}
    .segmented{display:grid;grid-template-columns:1fr 1fr;background:#0c1b2d;border-radius:12px;padding:3px;margin:0 0 10px}
    .segmented button{border:0;border-radius:10px;padding:10px;background:transparent;color:#aebfd2;font-weight:700}
    .segmented button.on{background:#294866;color:#fff}
    .sheet-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
    .sheet-actions button{border:0;border-radius:12px;padding:13px;background:#162941;color:#fff;font-weight:800}
    .sheet-actions .accent{background:#2f78b7}
    .help-modal{position:fixed;z-index:100;inset:0;background:#06101be8;display:grid;place-items:center;padding:20px}
    .help-modal.hide{display:none}
    .help-card{width:min(430px,100%);background:#102238;border:1px solid #2a4562;border-radius:22px;padding:20px}
    .help-card h2{margin:0 0 7px;font-size:26px}.help-card>p{color:#aebfd2;margin-top:0}
    .help-step{display:grid;grid-template-columns:38px 1fr;gap:10px;align-items:center;margin:13px 0}
    .help-step i{width:38px;height:38px;border-radius:12px;background:#1c3856;display:grid;place-items:center;font-style:normal;font-size:20px}
    .scan-help{width:44px;height:44px;border:0;border-radius:14px;background:#13243a;color:#fff;font-weight:900;font-size:20px}
    .event-limit{color:#ffd083;margin-top:8px;font-size:13px}
    .eventrow{padding:12px;border:1px solid #263f5b;border-radius:15px;background:#0b192b}
    .eventrow select,.eventrow input{min-height:44px}
    .eventrow>button{font-size:22px;font-weight:800;background:#4b2330!important}
    .eventpreview{border:1px solid #dce5ed}
    .event-columns{display:grid;grid-template-columns:100px 70px 1fr 42px;gap:7px;padding:0 12px 5px;color:#8da4bb;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
    .event-note{padding:12px 14px;border-radius:13px;background:#10253a;border:1px solid #28445f;color:#c7d7e6;font-size:13px;line-height:1.4;margin:0 0 14px}
    @media(max-width:520px){.event-columns{grid-template-columns:86px 58px 1fr 38px;padding-left:8px;padding-right:8px}.event-columns span:last-child{font-size:0}.event-columns span:last-child:after{content:'×';font-size:13px}}
    @media(min-width:700px){.page-grid{grid-template-columns:repeat(4,minmax(0,1fr));max-width:900px;margin:auto}.pdf-grid{grid-template-columns:1fr 1fr}}
  `;
  document.head.appendChild(style);

  App.register({
    id: 'product-shell',
    version: '1.0.0',
    start() {
      document.title = 'Нарисуй сам — календарь';
      document.querySelectorAll('.ver').forEach(el => el.remove());
      document.querySelectorAll('#review header small').forEach(el => el.textContent = 'Проверьте страницу');
      const brand = document.querySelector('.brand p');
      if (brand) brand.textContent = 'Обложка и 12 месяцев сохраняются автоматически. Любую страницу можно открыть и переснять.';
      const login = document.getElementById('loginCard');
      const cabinetBody = document.getElementById('cabinetBody');
      if (login) login.classList.add('hide');
      if (cabinetBody) cabinetBody.classList.remove('hide');
      const accountName = document.getElementById('accountName');
      if (accountName) accountName.textContent = 'Проекты на этом устройстве';
      const accountSmall = document.querySelector('.accountmeta small');
      if (accountSmall) accountSmall.textContent = 'Все проекты пока хранятся только на этом устройстве';
      const badge = document.querySelector('.serverbadge');
      if (badge) badge.textContent = 'Можно работать без регистрации';

      window.renderCabinet = function () {
        if (login) login.classList.add('hide');
        if (cabinetBody) cabinetBody.classList.remove('hide');
        if (accountName) accountName.textContent = 'Проекты на этом устройстве';
        const logout=document.getElementById('logoutBtn');
        if(logout) logout.style.display='none';
        const list=document.getElementById('projectList');
        if(!list) return;
        list.innerHTML='';
        const projects=projectIndex();
        if(!projects.length) list.innerHTML='<div class="newcard"><b>Пока нет проектов</b><div class="tiny" style="margin-top:5px">Создайте первый календарь</div></div>';
        for(const project of projects){
          const card=document.createElement('div');card.className='projectcard';
          const percent=Math.round((project.done||0)/13*100);
          card.innerHTML=`<div><h3>${esc(project.title||'Без названия')}</h3></div><b>${project.done||0}/13</b><p>Изменён ${new Date(project.updated||Date.now()).toLocaleString('ru-RU',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})}</p><div class="bar"><i style="width:${percent}%"></i></div><div class="projectactions"><button class="go">Продолжить</button><button class="del">Удалить</button></div>`;
          card.querySelector('.go').onclick=()=>openProject(project.id);
          card.querySelector('.del').onclick=()=>{if(confirm('Удалить проект?'))deleteProject(project.id)};
          list.appendChild(card);
        }
      };
      window.renderCabinet();
    }
  });

  App.register({
    id: 'clean-review',
    version: '1.0.0',
    start() {
      const oldProcess = window.process;
      if (typeof oldProcess !== 'function') return;
      window.process = async function (...args) {
        const result = await oldProcess.apply(this, args);
        const status = document.getElementById('status');
        const save = document.getElementById('save');
        if (!status || !S.pending) return result;
        if (save && !save.disabled) {
          status.className = 'status ok';
          status.innerHTML = `✓ <b>${esc(P[S.i])} готов</b><br><small>Проверьте страницу. Если всё хорошо — сохраните её.</small>`;
        } else if (S.pending.pageId && S.pending.pageId.confident) {
          status.className = 'status bad';
          status.innerHTML = `Сейчас нужна страница <b>${esc(P[S.i])}</b>.<br><small>В кадре другая страница — откройте нужную.</small>`;
        } else {
          status.className = 'status bad';
          status.innerHTML = 'Не удалось распознать страницу.<br><small>Держите телефон ровнее и убедитесь, что видны все четыре угловые метки.</small>';
        }
        const note = document.querySelector('#review header small');
        if (note) note.textContent = `Страница ${S.i + 1} из 13`;
        return result;
      };
    }
  });

  App.register({
    id: 'scan-help',
    version: '1.0.0',
    start() {
      const modal = document.createElement('div');
      modal.className = 'help-modal hide';
      modal.innerHTML = `
        <div class="help-card">
          <h2>Как сканировать</h2>
          <p>Начните с обложки. Следующую страницу приложение подскажет само.</p>
          <div class="help-step"><i>▱</i><span>Положите лист на ровную поверхность при равномерном свете.</span></div>
          <div class="help-step"><i>⌁</i><span>Не закрывайте четыре угловые метки и избегайте бликов и теней.</span></div>
          <div class="help-step"><i>▣</i><span>Держите телефон параллельно листу и поместите весь лист в рамку.</span></div>
          <div class="help-step"><i>●</i><span>Когда кадр станет ровным и резким, приложение снимет страницу автоматически.</span></div>
          <button class="btn primary">Понятно, начинаем</button>
        </div>`;
      document.body.appendChild(modal);
      const close = () => {
        modal.classList.add('hide');
        localStorage.setItem('calendar_scan_help_v15', '1');
      };
      modal.querySelector('button').onclick = close;
      modal.onclick = event => { if (event.target === modal) close(); };

      const header = document.querySelector('#scan header');
      const menu = document.getElementById('menu');
      if (header && menu) {
        const help = document.createElement('button');
        help.className = 'scan-help';
        help.type = 'button';
        help.textContent = '?';
        help.setAttribute('aria-label', 'Как сканировать');
        help.onclick = () => modal.classList.remove('hide');
        header.insertBefore(help, menu);
      }

      const oldOpenCam = window.openCam;
      if (typeof oldOpenCam === 'function') {
        window.openCam = async function (...args) {
          const result = await oldOpenCam.apply(this, args);
          if (!localStorage.getItem('calendar_scan_help_v15')) modal.classList.remove('hide');
          return result;
        };
      }
    }
  });

  function finalGrid(c, month) {
    if (!month) return c;
    const ctx = c.getContext('2d'), W = c.width, H = c.height;
    const start = M[month][0], days = M[month][1], rows = M[month][2];
    const left = W * 10 / 210, right = W * 200 / 210;
    const contentW = right - left, gap = contentW * .025, sideW = contentW * .245;
    const gridRight = right - sideW - gap, cw = (gridRight - left) / 7;
    const bottom = H * (1 - 21 / 297), ch = H * 10 / 297, head = H * 8 / 297;
    const top = bottom - head - rows * ch;
    const week = ['ПН','ВТ','СР','ЧТ','ПТ','СБ','ВС'];
    ctx.save();
    ctx.fillStyle = '#fff';
    ctx.fillRect(left, top - head * 1.15, right - left, bottom - top + head * 1.15);
    ctx.fillStyle = '#f2f6fa';
    ctx.fillRect(left, top, gridRight-left, head);
    ctx.fillStyle = '#fff6f3';
    ctx.fillRect(left + 5*cw, top, 2*cw, bottom-top);
    ctx.strokeStyle = '#b7c9dc';
    ctx.lineWidth = Math.max(1, W/1700);
    ctx.beginPath();
    for (let col=0; col<=7; col++) {
      const x=left+col*cw; ctx.moveTo(x,top); ctx.lineTo(x,bottom);
    }
    for (let row=0; row<=rows; row++) {
      const y=top+head+row*ch; ctx.moveTo(left,y); ctx.lineTo(gridRight,y);
    }
    ctx.moveTo(left,top);ctx.lineTo(gridRight,top);ctx.stroke();
    ctx.textBaseline='middle';
    ctx.textAlign='left';
    ctx.fillStyle='#26384b';
    ctx.font=`700 ${Math.round(head*.76)}px -apple-system,BlinkMacSystemFont,Arial`;
    ctx.fillText(P[month],left,top-head*.62);
    ctx.textAlign='center';
    ctx.font=`700 ${Math.round(head*.30)}px -apple-system,BlinkMacSystemFont,Arial`;
    for(let col=0;col<7;col++){
      ctx.fillStyle=col>=5?'#b24f55':'#26384b';
      ctx.fillText(week[col],left+col*cw+cw*.5,top+head*.5);
    }
    ctx.font=`800 ${Math.round(ch*.37)}px -apple-system,BlinkMacSystemFont,Arial`;
    for(let day=1;day<=days;day++){
      const k=start+day-1,row=Math.floor(k/7),col=k%7;
      ctx.fillStyle=col>=5?'#b24f55':'#182c40';
      ctx.fillText(String(day),left+col*cw+cw*.19,top+head+row*ch+ch*.31);
    }
    const sideX=gridRight+gap;
    ctx.fillStyle='#f5f8fb';
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(sideX,top,sideW,bottom-top,Math.max(8,W*.005));
    else ctx.rect(sideX,top,sideW,bottom-top);
    ctx.fill();
    ctx.textAlign='left';ctx.textBaseline='top';ctx.fillStyle='#26384b';
    ctx.font=`800 ${Math.round(head*.32)}px -apple-system,BlinkMacSystemFont,Arial`;
    ctx.fillText('ВАЖНЫЕ ДАТЫ',sideX+sideW*.09,top+head*.42,sideW*.82);
    ctx.restore();
    c.__calendarLayout={sideX,sideW,top,bottom,head};
    return c;
  }

  function finalEvents(c, month) {
    finalGrid(c, month);
    const layout=c.__calendarLayout;
    if(!layout) return c;
    const events=(S.proj?.events||[])
      .filter(e=>e.month===month && e.text && e.text.trim())
      .sort((a,b)=>a.day-b.day || a.text.localeCompare(b.text,'ru'))
      .filter((e,index,all)=>all.slice(0,index).filter(x=>x.day===e.day).length<2);
    const ctx=c.getContext('2d'), W=c.width;
    ctx.save();ctx.textAlign='left';ctx.textBaseline='top';
    const x=layout.sideX+layout.sideW*.09,maxW=layout.sideW*.82;
    let y=layout.top+layout.head*1.22;
    const line=Math.max(17,Math.round(W*.0074));
    if(!events.length){
      ctx.fillStyle='#8796a6';ctx.font=`500 ${Math.round(line*.68)}px -apple-system,BlinkMacSystemFont,Arial`;
      ctx.fillText('Добавьте дни рождения',x,y,maxW);
    }
    for(const event of events){
      if(y+line*1.6>layout.bottom-layout.head*.25) break;
      ctx.fillStyle='#d5528e';ctx.font=`800 ${Math.round(line*.78)}px -apple-system,BlinkMacSystemFont,Arial`;
      const day=String(event.day).padStart(2,'0');
      ctx.fillText(day,x,y,maxW*.2);
      ctx.fillStyle='#26384b';ctx.font=`650 ${Math.round(line*.68)}px -apple-system,BlinkMacSystemFont,Arial`;
      ctx.fillText(event.text.trim().slice(0,24),x+maxW*.22,y,maxW*.78);
      y+=line*1.38;
    }
    ctx.restore();return c;
  }

  function rounded(ctx,x,y,w,h,r,fill,stroke){
    ctx.beginPath();
    if(ctx.roundRect)ctx.roundRect(x,y,w,h,r);else ctx.rect(x,y,w,h);
    if(fill){ctx.fillStyle=fill;ctx.fill()}
    if(stroke){ctx.strokeStyle=stroke;ctx.stroke()}
  }

  function wrapped(ctx,text,x,y,maxWidth,lineHeight,maxLines=4){
    const words=String(text).split(/\s+/);let line='',lines=[];
    for(const word of words){const next=line?line+' '+word:word;if(ctx.measureText(next).width>maxWidth&&line){lines.push(line);line=word}else line=next}
    if(line)lines.push(line);
    lines.slice(0,maxLines).forEach((value,index)=>ctx.fillText(value,x,y+index*lineHeight));
  }

  function backCover(format='A4'){
    const c=document.createElement('canvas');
    c.width=format==='A3'?3508:2480;c.height=format==='A3'?4961:3508;
    const ctx=c.getContext('2d'),W=c.width,H=c.height,u=W/2480;
    const bg=ctx.createLinearGradient(0,0,W,H);bg.addColorStop(0,'#fffdf5');bg.addColorStop(.55,'#f3f8fb');bg.addColorStop(1,'#fff1f6');ctx.fillStyle=bg;ctx.fillRect(0,0,W,H);
    ctx.globalAlpha=.14;ctx.fillStyle='#55b8db';ctx.beginPath();ctx.arc(W*.08,H*.08,W*.20,0,Math.PI*2);ctx.fill();ctx.fillStyle='#df5d91';ctx.beginPath();ctx.arc(W*.94,H*.23,W*.17,0,Math.PI*2);ctx.fill();ctx.fillStyle='#f1c84b';ctx.beginPath();ctx.arc(W*.76,H*.94,W*.23,0,Math.PI*2);ctx.fill();ctx.globalAlpha=1;
    ctx.save();ctx.translate(W-360*u,250*u);ctx.rotate(-.55);rounded(ctx,-42*u,-155*u,84*u,310*u,34*u,'#f1c84b','#b98626');ctx.fillStyle='#df5d91';ctx.fillRect(-42*u,55*u,84*u,52*u);ctx.fillStyle='#f5dcc2';ctx.beginPath();ctx.moveTo(-42*u,-155*u);ctx.lineTo(0,-230*u);ctx.lineTo(42*u,-155*u);ctx.fill();ctx.fillStyle='#24384c';ctx.beginPath();ctx.moveTo(-10*u,-212*u);ctx.lineTo(0,-230*u);ctx.lineTo(10*u,-212*u);ctx.fill();ctx.restore();
    ctx.strokeStyle='#55b8db';ctx.lineWidth=18*u;ctx.lineCap='round';ctx.beginPath();ctx.arc(W-265*u,455*u,80*u,Math.PI,Math.PI*1.82);ctx.stroke();ctx.strokeStyle='#df5d91';ctx.beginPath();ctx.arc(W-265*u,455*u,55*u,Math.PI,Math.PI*1.82);ctx.stroke();ctx.strokeStyle='#f1c84b';ctx.beginPath();ctx.arc(W-265*u,455*u,30*u,Math.PI,Math.PI*1.82);ctx.stroke();
    const left=170*u,right=W-170*u;
    ctx.fillStyle='#33506b';ctx.font=`800 ${30*u}px Arial`;ctx.fillText('АМПЛИТУДА · НАРИСУЙ САМ',left,190*u);
    ctx.fillStyle='#102033';ctx.font=`900 ${102*u}px Arial`;ctx.fillText('Нарисуй свой год',left,335*u);
    ctx.fillStyle='#52677b';ctx.font=`500 ${39*u}px Arial`;wrapped(ctx,'Календарь для детей, взрослых и семейных историй',left,410*u,right-left,54*u,2);
    const cards=[
      ['1','Рисуйте','Карандашами, фломастерами, мелками или красками. Не выходите за рабочую область и не закрывайте угловые метки.'],
      ['2','Снимайте через приложение','Оно выровняет лист, очистит фон и отделит рисунок от сетки.'],
      ['3','Проверьте даты','Добавьте дни рождения и события — не больше двух на один день.'],
      ['4','Получите два файла','Приложение подготовит PDF сразу в форматах A4 и A3.']
    ];
    let y=590*u,cardH=300*u,gap=34*u;
    for(const [num,title,body] of cards){
      rounded(ctx,left,y,right-left,cardH,34*u,'rgba(255,255,255,.82)','rgba(87,123,153,.18)');
      const colors=['#55b8db','#df5d91','#f1c84b','#607fbe'];const color=colors[+num-1];
      rounded(ctx,left+34*u,y+44*u,116*u,116*u,34*u,color);
      ctx.fillStyle='#fff';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`900 ${56*u}px Arial`;ctx.fillText(num,left+92*u,y+102*u);
      ctx.textAlign='left';ctx.textBaseline='alphabetic';ctx.fillStyle='#102033';ctx.font=`850 ${43*u}px Arial`;ctx.fillText(title,left+182*u,y+88*u);
      ctx.fillStyle='#52677b';ctx.font=`500 ${31*u}px Arial`;wrapped(ctx,body,left+182*u,y+142*u,right-left-225*u,43*u,3);
      y+=cardH+gap;
    }
    const qr=540*u,qx=left,qy=y+55*u;
    rounded(ctx,qx,qy,qr,qr,42*u,'#fff','#9eb5c8');ctx.lineWidth=5*u;ctx.setLineDash([20*u,16*u]);ctx.strokeStyle='#7f9bb2';ctx.strokeRect(qx+32*u,qy+32*u,qr-64*u,qr-64*u);ctx.setLineDash([]);
    ctx.fillStyle='#1c3f5e';ctx.textAlign='center';ctx.font=`900 ${42*u}px Arial`;ctx.fillText('МЕСТО ДЛЯ QR-КОДА',qx+qr/2,qy+qr*.47);
    ctx.fillStyle='#71869a';ctx.font=`500 ${28*u}px Arial`;ctx.fillText('Ссылка на приложение',qx+qr/2,qy+qr*.57);
    const tx=qx+qr+75*u,tw=right-tx;
    ctx.textAlign='left';ctx.fillStyle='#102033';ctx.font=`900 ${54*u}px Arial`;ctx.fillText('С чего начать?',tx,qy+64*u);
    ctx.fillStyle='#52677b';ctx.font=`500 ${31*u}px Arial`;wrapped(ctx,'Откройте приложение по QR-коду, создайте календарь и начните с обложки. Во время съёмки приложение покажет подсказки.',tx,qy+124*u,tw,46*u,6);
    rounded(ctx,tx,qy+355*u,tw,118*u,28*u,'#102a43');ctx.fillStyle='#fff';ctx.font=`800 ${31*u}px Arial`;ctx.fillText('Поддержка: Telegram или MAX',tx+35*u,qy+427*u);
    ctx.fillStyle='#6b7e90';ctx.font=`600 ${25*u}px Arial`;ctx.fillText('Рисунки остаются вашими. Мы используем их только для создания календаря.',left,H-135*u);
    ctx.textAlign='right';ctx.fillStyle='#314b63';ctx.font=`800 ${27*u}px Arial`;ctx.fillText('amplituda · Нижний Новгород',right,H-135*u);
    return c;
  }

  App.register({
    id: 'calendar-layout',
    version: '1.0.0',
    start() {
      window.renderDigitalGrid = finalGrid;
      window.overlayEvents = finalEvents;
    }
  });

  App.register({
    id: 'event-editor-help',
    version: '1.0.0',
    start() {
      const title=document.querySelector('#dates .events h2');
      const lead=document.querySelector('#dates .events>p.subtle');
      const list=document.getElementById('eventList');
      if(title)title.textContent='Дни рождения и события';
      if(lead)lead.outerHTML='<div class="event-note">Найденные на бумаге даты появятся здесь. Выберите месяц и число, добавьте подпись. Крестик справа полностью удаляет событие. На один день можно добавить не больше двух записей.</div>';
      if(list&&!document.querySelector('#dates .event-columns')){
        const labels=document.createElement('div');labels.className='event-columns';
        labels.innerHTML='<span>Месяц</span><span>Число</span><span>Подпись</span><span>Удалить</span>';
        list.before(labels);
      }
      if(list){
        const labelRows=()=>list.querySelectorAll('.eventrow').forEach(row=>{
          const remove=row.querySelector('button');if(remove){remove.title='Удалить событие';remove.setAttribute('aria-label','Удалить событие')}
          const fields=row.querySelectorAll('select,input');
          fields[0]?.setAttribute('aria-label','Месяц');fields[1]?.setAttribute('aria-label','Число');fields[2]?.setAttribute('aria-label','Подпись события');
        });
        new MutationObserver(labelRows).observe(list,{childList:true,subtree:true});labelRows();
      }
    }
  });

  function ensureSheetModal() {
    let modal=document.getElementById('sheetModal');
    if(modal) return modal;
    modal=document.createElement('div');
    modal.id='sheetModal';modal.className='sheet-modal hide';
    modal.innerHTML=`
      <header><button class="ico close">‹</button><div style="flex:1"><b class="title">Страница</b><small>Просмотр сохранённого листа</small></div></header>
      <div class="sheet-body">
        <div class="segmented"><button class="final on">Готовый вид</button><button class="source">Исходное фото</button></div>
        <img class="sheet-image" alt="Сохранённая страница">
        <div class="sheet-actions"><button class="events">События</button><button class="accent retake">Переснять</button></div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.close').onclick=()=>modal.classList.add('hide');
    return modal;
  }

  async function pagePreview(index, mode='final') {
    const modal=ensureSheetModal(), image=modal.querySelector('.sheet-image');
    modal.dataset.page=String(index);modal.classList.remove('hide');
    const automatic=index===13;
    modal.querySelector('.title').textContent=automatic?'Задняя обложка':P[index];
    modal.querySelector('.segmented').style.display=automatic?'none':'grid';
    modal.querySelector('.sheet-actions').style.display=automatic?'none':'grid';
    if(automatic){
      const shown=await toBlob(backCover('A4'),.985);
      if(image.dataset.url)URL.revokeObjectURL(image.dataset.url);
      image.dataset.url=URL.createObjectURL(shown);image.src=image.dataset.url;return;
    }
    modal.querySelector('.events').style.visibility=index?'visible':'hidden';
    modal.querySelector('.final').classList.toggle('on',mode==='final');
    modal.querySelector('.source').classList.toggle('on',mode==='source');
    const key=`${S.proj.id}:${index}:${mode==='source'?'source':'processed'}`;
    const blob=await get(key);
    if(!blob){image.removeAttribute('src');return}
    let shown=blob;
    if(mode==='final'){
      const canvas=await blobToCanvas(blob);
      if(index>0) finalEvents(canvas,index);
      shown=await toBlob(canvas,.985);
    }
    if(image.dataset.url) URL.revokeObjectURL(image.dataset.url);
    image.dataset.url=URL.createObjectURL(shown);image.src=image.dataset.url;
  }

  App.register({
    id: 'page-gallery',
    version: '1.0.0',
    start() {
      const modal=ensureSheetModal();
      modal.querySelector('.final').onclick=()=>pagePreview(+modal.dataset.page,'final');
      modal.querySelector('.source').onclick=()=>pagePreview(+modal.dataset.page,'source');
      modal.querySelector('.retake').onclick=()=>{
        const index=+modal.dataset.page;modal.classList.add('hide');S.i=index;openCam();
      };
      modal.querySelector('.events').onclick=()=>{modal.classList.add('hide');openDates()};

      window.openPages=async function(){
        stop();
        const list=document.getElementById('plist');
        list.className='page-grid';list.innerHTML='';
        let done=0;
        for(let index=0;index<13;index++){
          const saved=!!S.proj.pages[index];if(saved)done++;
          const card=document.createElement('button');
          card.type='button';card.className='page-card';
          card.innerHTML=`<div class="page-thumb"><span>${saved?'…':'＋'}</span></div><div class="page-info"><strong>${esc(P[index])}</strong><span class="${saved?'page-ready':'page-empty'}">${saved?'Готово':'Нет снимка'}</span></div>`;
          card.onclick=()=>saved?pagePreview(index):(S.i=index,openCam());
          list.appendChild(card);
          if(saved){
            try{
              const blob=await get(`${S.proj.id}:${index}:processed`);
              if(blob){
                const canvas=await blobToCanvas(blob);
                if(index>0) finalEvents(canvas,index);
                const thumb=await toBlob(canvas,.78),url=URL.createObjectURL(thumb),img=new Image();
                img.onload=()=>URL.revokeObjectURL(url);img.src=url;
                card.querySelector('.page-thumb').replaceChildren(img);
              }
            }catch(error){console.error(error)}
          }
        }
        const back=document.createElement('button');back.type='button';back.className='page-card';
        back.innerHTML='<div class="page-thumb"><span>✦</span></div><div class="page-info"><strong>Задняя обложка</strong><span class="page-auto">Автоматически</span></div>';
        back.onclick=()=>pagePreview(13);list.appendChild(back);
        try{const preview=await toBlob(backCover('A4'),.78),url=URL.createObjectURL(preview),img=new Image();img.onload=()=>URL.revokeObjectURL(url);img.src=url;back.querySelector('.page-thumb').replaceChildren(img)}catch{}
        const actions=document.createElement('div');actions.className='page-list-actions';
        if(done===13){
          const button=document.createElement('button');button.className='btn primary';button.textContent='Проверить события и собрать PDF';button.onclick=openDates;actions.appendChild(button);
        }else if(TESTMODE&&done>0){
          const button=document.createElement('button');button.className='btn secondary testbtn';button.textContent='ТЕСТ: заполнить недостающие страницы';button.onclick=testFillPages;actions.appendChild(button);
        }
        list.appendChild(actions);show('pages');
      };
      document.getElementById('menu').onclick=window.openPages;
      document.getElementById('pback').onclick=()=>{renderCabinet();show('cabinet')};
    }
  });

  function validateEvents() {
    const counts=new Map();
    for(const event of (S.proj.events||[])){
      if(!event.text || !event.text.trim()) continue;
      const key=`${event.month}-${event.day}`,next=(counts.get(key)||0)+1;
      counts.set(key,next);
      if(next>2) return {ok:false,event};
    }
    return {ok:true};
  }

  async function buildPdf(format, onProgress) {
    const pages=[];
    const target=format==='A3'?{w:3508,h:4961,pw:841.89,ph:1190.55}:{w:2480,h:3508,pw:595.28,ph:841.89};
    for(let index=0;index<13;index++){
      const blob=await get(`${S.proj.id}:${index}:processed`);
      if(!blob) throw new Error(`Нет страницы ${index+1}`);
      let canvas=await blobToCanvas(blob);
      if(canvas.width!==target.w||canvas.height!==target.h){
        const resized=document.createElement('canvas');resized.width=target.w;resized.height=target.h;
        resized.getContext('2d').drawImage(canvas,0,0,target.w,target.h);canvas=resized;
      }
      if(index>0) finalEvents(canvas,index);
      const jpeg=await toBlob(canvas,.96);
      pages.push({bytes:new Uint8Array(await jpeg.arrayBuffer()),w:canvas.width,h:canvas.height});
      onProgress?.(index+1,14);
      await new Promise(resolve=>setTimeout(resolve,0));
    }
    const rear=backCover(format),rearJpeg=await toBlob(rear,.96);
    pages.push({bytes:new Uint8Array(await rearJpeg.arrayBuffer()),w:rear.width,h:rear.height});
    onProgress?.(14,14);
    const objects=[],pageIds=[];let next=3;
    for(let index=0;index<pages.length;index++){
      const pageId=next++,imageId=next++,contentId=next++;pageIds.push(pageId);
      const image=pages[index],stream=`q\n${target.pw} 0 0 ${target.ph} 0 0 cm\n/Im0 Do\nQ\n`;
      objects[pageId]=[u8(`${pageId} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${target.pw} ${target.ph}] /Resources << /XObject << /Im0 ${imageId} 0 R >> >> /Contents ${contentId} 0 R >>\nendobj\n`)];
      objects[imageId]=[u8(`${imageId} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${image.w} /Height ${image.h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${image.bytes.length} >>\nstream\n`),image.bytes,u8('\nendstream\nendobj\n')];
      objects[contentId]=[u8(`${contentId} 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}endstream\nendobj\n`)];
    }
    objects[1]=[u8('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')];
    objects[2]=[u8(`2 0 obj\n<< /Type /Pages /Count ${pages.length} /Kids [${pageIds.map(id=>id+' 0 R').join(' ')}] >>\nendobj\n`)];
    const header=u8('%PDF-1.4\n%âãÏÓ\n'),chunks=[header],offsets=[0];let position=header.length,max=objects.length-1;
    for(let id=1;id<=max;id++){offsets[id]=position;for(const chunk of objects[id]){chunks.push(chunk);position+=chunk.length}}
    const xref=position;let table=`xref\n0 ${max+1}\n0000000000 65535 f \n`;
    for(let id=1;id<=max;id++) table+=String(offsets[id]).padStart(10,'0')+' 00000 n \n';
    table+=`trailer\n<< /Size ${max+1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
    chunks.push(u8(table));return new Blob(chunks,{type:'application/pdf'});
  }

  function fileName(format) {
    const title=(S.proj.title||'Календарь').replace(/[^a-zа-яё0-9_-]+/gi,'_').replace(/^_+|_+$/g,'')||'Календарь';
    return `${title}_${format}.pdf`;
  }

  function download(format) {
    const blob=S.pdfs?.[format];if(!blob)return;
    const url=URL.createObjectURL(blob),link=document.createElement('a');
    link.href=url;link.download=fileName(format);document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),3000);
  }

  async function share(format) {
    const blob=S.pdfs?.[format];if(!blob)return;
    const file=new File([blob],fileName(format),{type:'application/pdf'});
    if(navigator.canShare&&navigator.canShare({files:[file]})){
      try{await navigator.share({title:`Календарь ${format}`,text:`Готовый календарь ${format}`,files:[file]});return}catch(error){if(error.name==='AbortError')return}
    }
    download(format);toast('Файл скачан — прикрепите его к письму',3200);
  }

  function renderPdfCards() {
    let wrap=document.getElementById('dualPdf');
    if(!wrap){
      wrap=document.createElement('div');wrap.id='dualPdf';wrap.className='pdf-grid';
      document.getElementById('pdfState').after(wrap);
    }
    wrap.innerHTML=['A4','A3'].map(format=>{
      const blob=S.pdfs?.[format],size=blob?(blob.size/1024/1024).toFixed(1)+' МБ':'—';
      return `<div class="pdf-card"><div class="pdf-head"><b>${format}</b><small>${size}</small></div><div class="pdf-actions"><button class="download" data-download="${format}">Скачать</button><button data-share="${format}">Отправить</button></div></div>`;
    }).join('');
    wrap.querySelectorAll('[data-download]').forEach(button=>button.onclick=()=>download(button.dataset.download));
    wrap.querySelectorAll('[data-share]').forEach(button=>button.onclick=()=>share(button.dataset.share));
  }

  App.register({
    id: 'dual-pdf',
    version: '1.0.0',
    start() {
      const formats=document.querySelector('#dates .summary');
      if(formats) formats.innerHTML='<b>Два готовых файла</b><div class="dual-note">Приложение автоматически подготовит календарь сразу в A4 и A3 и добавит красивую заднюю обложку с инструкцией и местом для QR-кода.</div>';
      const oldButton=document.getElementById('downloadPdf');
      if(oldButton) oldButton.classList.add('hide');
      S.pdfs=S.pdfs||{};

      window.buildFinal=async function(){
        const valid=validateEvents();
        if(!valid.ok){
          toast(`На ${valid.event.day} число добавлено больше двух событий`,4200);
          return;
        }
        show('finish');S.pdfs={};
        document.getElementById('sendPrint').disabled=true;
        document.getElementById('pdfProgress').style.width='2%';
        document.getElementById('pdfState').textContent='Подготавливаю A4…';
        document.getElementById('finishSummary').innerHTML=`<b>Будут созданы A4 и A3</b>13 отснятых страниц + задняя обложка · событий: ${(S.proj.events||[]).filter(e=>e.text&&e.text.trim()).length}<br><span class="mini">Оба файла собираются автоматически из одного проекта.</span>`;
        try{
          S.pdfs.A4=await buildPdf('A4',(done,total)=>{
            document.getElementById('pdfProgress').style.width=`${Math.round(done/total*48)}%`;
            document.getElementById('pdfState').textContent=`A4: страница ${done} из ${total}…`;
          });
          document.getElementById('pdfState').textContent='A4 готов. Подготавливаю A3…';
          S.pdfs.A3=await buildPdf('A3',(done,total)=>{
            document.getElementById('pdfProgress').style.width=`${50+Math.round(done/total*50)}%`;
            document.getElementById('pdfState').textContent=`A3: страница ${done} из ${total}…`;
          });
          document.getElementById('pdfProgress').style.width='100%';
          document.getElementById('pdfState').textContent='Оба PDF готовы';
          renderPdfCards();
          document.getElementById('sendPrint').disabled=false;
          App.emit('pdf-ready',{projectId:S.proj.id,formats:['A4','A3']});
        }catch(error){
          const item=incident('PDF_BUILD',String(error));
          document.getElementById('pdfState').textContent=`Не удалось собрать PDF · ${item.id}`;
        }
      };
      document.getElementById('buildBtn').onclick=window.buildFinal;
      document.getElementById('fback').onclick=openDates;
      document.getElementById('sendPrint').textContent='Отправить в типографию';
    }
  });

  document.querySelectorAll('.ver').forEach(el=>el.remove());
  console.info('CalendarApp V15 modules:', [...App.modules.keys()]);
})();
