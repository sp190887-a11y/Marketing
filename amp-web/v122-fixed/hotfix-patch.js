(function(){if(window.__AMP_HOTFIX_20260914)return;window.__AMP_HOTFIX_20260914=true;
// V12.2 usability hotfix: collapse completed cards, per-section help, operational start date.
const AMP_DEFAULT_START_DATE='2026-09-14';
function workStartDate(){return (state&&state.work_start_date)||AMP_DEFAULT_START_DATE}
function beforeWorkStart(date){return !!date && date<workStartDate()}
function isOperationalOverdue(date){return !!date && date>=workStartDate() && date<today()}

if(!state.work_start_date){state.work_start_date=AMP_DEFAULT_START_DATE;markDirty();Promise.resolve(manualSave(true)).catch(()=>{});}

const SECTION_HELP_V122={
  tasks:{title:'Задачи',html:`<p><b>Для чего:</b> единый рабочий список. Сюда попадают ручные задачи, входящие и автоматические напоминания.</p><p><b>Как работать:</b> откройте карточку, уточните срок и описание, прикрепите файлы. После выполнения нажмите «Готово» — карточка перейдёт в «Готовые» и сразу свернётся.</p><p><b>Просрочка:</b> считается только начиная с установленной точки старта. Старые даты до неё не окрашиваются как просроченные.</p><p><b>Входящие:</b> материал можно превратить в задачу. Из задачи можно сделать пост или товар.</p>`},
  reviews:{title:'Отзывы',html:`<p><b>Для чего:</b> видеть площадки отзывов, кого уже просили и кто реально оставил отзыв.</p><p><b>Как работать:</b> добавьте человека, выберите площадку, нажмите «Попросить». Когда отзыв появился — укажите фактическую дату и отметьте «Оставил».</p><p>После отметки «Оставил» раскрытая площадка сворачивается, чтобы список не растягивался. История по человеку и площадке сохраняется.</p><p>Вкладки «Демо-отзывы» и «Ответы» — библиотека заготовок, а не факт опубликованного отзыва.</p>`},
  platforms:{title:'Площадки',html:`<p><b>Для чего:</b> учёт основных и дополнительных площадок компании.</p><p>Укажите название, категорию, ссылку, наличие и состояние. В блоке «Что сделать» ведите конкретные пункты работы; дата напоминания необязательна.</p><p>«Основные» требуют постоянной актуализации, «Дополнительные» могут быть разовыми. Неактуальное сначала отправляется в архив.</p>`},
  channels:{title:'Каналы',html:`<p><b>Для чего:</b> учёт каналов публикации и коммуникации.</p><p>Канал можно сделать активным/неактивным, отметить созданным или находящимся в процессе. Один источник может одновременно иметь несколько ролей.</p><p>В строках работы фиксируйте, что именно нужно настроить, проверить или обновить.</p>`},
  posts:{title:'Посты',html:`<p><b>Для чего:</b> хранить мастер-текст публикации и отмечать, куда он размещён.</p><p>Создайте пост, заполните дату, заголовок и полный текст, затем через «+» выберите площадки или целую свою папку площадок.</p><p>После публикации отмечайте результат по каждой площадке. При переводе самого поста в «Готово» карточка сразу сворачивается.</p>`},
  products:{title:'Товары',html:`<p><b>Для чего:</b> хранить карточки товаров и контролировать размещение на площадках.</p><p>Заполните название и описание, прикрепите материалы, через «+» добавьте нужные площадки или папки. По каждой площадке отмечайте размещение.</p><p>При переводе товара в «Готово» его карточка сразу сворачивается.</p>`},
  calendar:{title:'Календарь',html:`<p><b>Для чего:</b> общий календарный вид задач и других дат из Marketing.</p><p>Нажмите на дату или на «+» в пустом дне, чтобы создать задачу сразу на эту дату. Событие можно открыть прямо из календаря.</p><p>Календарь ничего не дублирует — он показывает те же рабочие данные по датам.</p>`},
  master:{title:'Библиотека',html:`<p><b>Для чего:</b> постоянные тексты и данные, которые часто нужны менеджеру: описания, реквизиты, шаблоны, инструкции и т.п.</p><p>Карточки можно искать, копировать, добавлять в избранное и перетаскивать. Избранные всегда сверху.</p><p>Удаление идёт через архив, поэтому случайно потерять запись сложнее.</p>`}
};
window.showSectionHelpV122=function(tab=currentTab){
  const h=SECTION_HELP_V122[tab];if(!h)return;
  $('#pickerTitle').textContent='Как работать · '+h.title;
  $('#pickerBody').innerHTML=`<div class="helpV122">${h.html}<div class="helpstartV122"><strong>Точка старта:</strong> ${fmtDate(workStartDate())}<br><span class="hint">Сроки раньше этой даты не считаются текущей просрочкой.</span></div></div><div class="detailactions"><button class="btn primary" onclick="picker.close()">Понятно</button></div>`;
  picker.showModal();
}
window.editWorkStartDateV122=function(){
  $('#pickerTitle').textContent='Точка старта AMP Marketing';
  $('#pickerBody').innerHTML=`<div class="settings-section"><div class="field"><label>С какой даты начинаем текущий учёт</label><input id="workStartDateV122" type="date" value="${esc(workStartDate())}"></div><div class="hint" style="margin-top:8px">Задачи со сроком раньше этой даты останутся в базе, но не будут считаться просроченными. Новая работа считается от этой точки.</div></div><div class="detailactions"><button class="btn" onclick="picker.close()">Отмена</button><button class="btn primary" onclick="saveWorkStartDateV122()">Сохранить</button></div>`;
  picker.showModal();
}
window.saveWorkStartDateV122=async function(){
  const v=$('#workStartDateV122')?.value||AMP_DEFAULT_START_DATE;
  state.work_start_date=v;markDirty();picker.close();await manualSave(false);render();
}

head=function(title,actions=''){
  const help=SECTION_HELP_V122[currentTab]?`<button class="btn helpbtnV122" onclick="showSectionHelpV122('${currentTab}')">? Как работать</button>`:'';
  return `<div class="viewhead"><div><h1>${esc(title)}</h1><div class="hint">${esc(unit().name)}</div></div><div class="toolbar">${help}${actions}</div></div>`;
};

setTaskDoneV11=function(id,status){
  const t=getTask(id);if(!t)return;const was=t.status;t.status=status;
  const b=taskEditBackupV11.get(id);if(b)b.status=status;
  if(status==='done'){openSets.tasks.delete(id);t.fresh=false;if(was!=='done')logEvent('task_done',{record_id:id,type:t.type,planned_minutes:t.planned_minutes||0});}
  touch(t);render();
};

changePost=function(id,k,v,rr=false){
  const p=getPost(id);if(!p)return;p[k]=v;touch(p);
  if(k==='status'&&v==='done')openSets.posts.delete(id);
  if(rr)render();
};
changeProduct=function(id,k,v,rr=false){
  const p=getProduct(id);if(!p)return;p[k]=v;touch(p);
  if(k==='status'&&v==='done')openSets.products.delete(id);
  if(rr)render();
};

toggleReviewDone=function(pid,sid,on){
  const p=unit().review_people.find(x=>x.id===pid);if(!p)return;
  p.placements=p.placements||{};let v=p.placements[sid]||(p.placements[sid]={status:'requested',requested_at:nowIso(),done_at:'',note:''});
  const was=v.status==='done';
  if(on){const inp=$('#rd_'+CSS.escape(pid)+'_'+CSS.escape(sid));const date=(inp?.value||v.pending_done_date||today());v.status='done';v.done_at=date+'T12:00:00Z';delete v.pending_done_date;if(!was)logEvent('review_added',{person_id:pid,source_id:sid,date});reviewOpenV10.delete(sid);}
  else{v.status='requested';v.done_at='';if(!v.requested_at)v.requested_at=nowIso();reviewOpenV10.add(sid);}
  touch(p);render();
};

taskCard=function(t){
  const over=t.status!=='done'&&isOperationalOverdue(t.due),pre=t.status!=='done'&&beforeWorkStart(t.due);
  return `<details class="item ${t.fresh?'taskfresh':(t.status==='done'?'good':(over?'absent':'attn'))}" ${openSets.tasks.has(t.id)?'open':''} ontoggle="taskToggleV11('${t.id}',this.open)"><summary><div class="summary task"><span class="name">${esc(t.title||'Без названия')}</span><span class="snippet">${esc((t.text||'').replace(/\n/g,' ').slice(0,140))}</span><span class="status blue">${esc(taskTypeLabel(t.type))}</span><span class="${over?'status red':'muted'}">${fmtDate(t.due)}${pre?' · до старта':''}</span><span>›</span></div></summary><div class="detail"><div class="grid grid3"><div class="field"><label>Название</label><input value="${esc(t.title)}" oninput="changeTask('${t.id}','title',this.value)"></div><div class="field"><label>Тип</label><select onchange="changeTask('${t.id}','type',this.value,true)">${['general','review','platform','post','product','data','media','quiz'].map(k=>`<option value="${k}" ${t.type===k?'selected':''}>${taskTypeLabel(k)}</option>`).join('')}</select></div><div class="field"><label>Срок</label><input type="date" value="${esc(t.due||'')}" onchange="changeTask('${t.id}','due',this.value)"></div></div><div class="field" style="margin-top:8px"><label>Описание / заметка</label><textarea style="min-height:120px" oninput="changeTask('${t.id}','text',this.value)">${esc(t.text||'')}</textarea></div>${attachmentBlock('task',t)}<div class="detailactions"><button class="btn" onclick="convertTask('${t.id}','post')">Перенести в пост</button><button class="btn" onclick="convertTask('${t.id}','product')">Перенести в товар</button><button class="btn doneV11" onclick="setTaskDoneV11('${t.id}','${t.status==='done'?'open':'done'}')">${t.status==='done'?'Вернуть в работу':'Готово'}</button><button class="btn danger" onclick="archiveRecord('tasks','${t.id}')">В архив</button><button class="btn closeV11" onclick="closeTaskNoEditV11('${t.id}')">Закрыть без редактирования</button><button class="btn save" onclick="saveTaskV10('${t.id}')">Сохранить</button></div></div></details>`;
};

renderTasks=function(){
  let st=sessionStorage.getItem('taskStatus')||'open',q=searchValV11('tasks');
  const inboxCount=state.inbox.filter(x=>x.status!=='processed').length;
  const filters=`<div class="filters">${[['inbox',`Входящие${inboxCount?' · '+inboxCount:''}`],['open','Активные'],['overdue','Просроченные'],['done','Готовые'],['all','Все']].map(([k,l])=>`<button class="chip ${st===k?'active':''}" onclick="sessionStorage.taskStatus='${k}';render()">${l}</button>`).join('')}</div>`;
  const actions=`${searchInputV11('tasks','Поиск задач / входящих')}<button class="btn" onclick="editWorkStartDateV122()">Старт: ${fmtDate(workStartDate())}</button><button class="btn primary" onclick="addTask()">+ Задача</button>`;
  if(st==='inbox'){$('#content').innerHTML=head('Задачи',actions)+filters+renderTaskInboxV12(q);return;}
  let arr=unit().tasks;
  if(st==='open')arr=arr.filter(x=>x.status!=='done');
  if(st==='done')arr=arr.filter(x=>x.status==='done');
  if(st==='overdue')arr=arr.filter(x=>x.status!=='done'&&isOperationalOverdue(x.due));
  if(q)arr=arr.filter(t=>hasQv11(taskSearchTextV11(t),q));
  arr=[...arr].sort((a,b)=>(b.fresh?1:0)-(a.fresh?1:0)||(a.status==='done')-(b.status==='done')||(a.due||'9999').localeCompare(b.due||'9999')||(b.created_at||'').localeCompare(a.created_at||''));
  $('#content').innerHTML=head('Задачи',actions)+filters+(arr.map(taskCard).join('')||'<div class="tile hint">Задач нет.</div>');
};

render();
})();
