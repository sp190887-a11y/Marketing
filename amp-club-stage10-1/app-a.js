const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const money=n=>new Intl.NumberFormat('ru-RU').format(n)+' ₽';
const am=n=>new Intl.NumberFormat('ru-RU').format(n)+' АМ';
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const today='2026-09-14';
const seed={
 customer:{id:'c1',name:'Сергей Сергеевич',phone:'9991234567',crm:'1001',birth:'1987-08-19',gender:'male',discount:5,balance:1250,turnover:48600,remainder:50},
 customers:[
  {id:'c1',name:'Сергей Сергеевич',phone:'9991234567',crm:'1001',birth:'1987-08-19',gender:'male',discount:5,balance:1250,turnover:48600,remainder:50},
  {id:'c2',name:'Анна Крылова',phone:'9205551122',crm:'1047',birth:'1992-09-14',gender:'female',discount:7,balance:2140,turnover:72400,remainder:20},
  {id:'c3',name:'Иван Петров',phone:'9037770044',crm:'1112',birth:'1985-01-25',gender:'male',discount:3,balance:420,turnover:17800,remainder:0}
 ],
 orders:[
  {id:'o1',customer:'c1',number:'A-15382',date:'12.09.2026',title:'Визитки + наклейки',sum:9550,paid:9073,discount:5,earned:95,status:'Готов'},
  {id:'o2',customer:'c1',number:'A-15404',date:'13.09.2026',title:'Печать открыток',sum:450,paid:428,discount:5,earned:5,status:'В работе'},
  {id:'o3',customer:'c2',number:'A-15390',date:'12.09.2026',title:'Меню для кафе',sum:12500,paid:11625,discount:7,earned:125,status:'Выдан'}
 ],
 ledger:[
  {id:'l1',customer:'c1',date:'13.09.2026 16:10',type:'Заказ',reason:'Заказ A-15404',amount:5,balance:1250},
  {id:'l2',customer:'c1',date:'12.09.2026 12:40',type:'Заказ',reason:'Заказ A-15382',amount:95,balance:1245},
  {id:'l3',customer:'c1',date:'11.09.2026 18:05',type:'Соцсеть',reason:'Подписка Telegram',amount:150,balance:1150},
  {id:'l4',customer:'c1',date:'10.09.2026 10:15',type:'За АМ',reason:'Стикеры',amount:-800,balance:1000},
  {id:'l5',customer:'c2',date:'12.09.2026 14:15',type:'Заказ',reason:'Заказ A-15390',amount:125,balance:2140}
 ],
 rewards:[
  {id:'r1',title:'Стикеры',category:'Мерч',desc:'Фирменный набор стикеров',price:800,stock:23,limit:2,sort:1,fulfill:'В офисе',active:true,emoji:'✨',main:'',media:[],minDiscount:0,gender:'any',birthday:false,from:'',to:'',lockedVisible:true},
  {id:'r2',title:'Кружка',category:'Мерч',desc:'Белая кружка Амплитуда',price:1500,stock:8,limit:1,sort:2,fulfill:'В офисе',active:true,emoji:'☕',main:'',media:[],minDiscount:5,gender:'any',birthday:false,from:'',to:'',lockedVisible:true},
  {id:'r3',title:'Сюрприз-мини',category:'Сюрпризы',desc:'Небольшой сюрприз от команды',price:500,stock:40,limit:3,sort:3,fulfill:'В офисе',active:true,emoji:'🎁',main:'',media:[],minDiscount:0,gender:'any',birthday:false,from:'',to:'',lockedVisible:true},
  {id:'r4',title:'Подарок на день рождения',category:'Сюрпризы',desc:'Доступен только имениннику',price:300,stock:15,limit:1,sort:4,fulfill:'В офисе',active:true,emoji:'🎂',main:'',media:[],minDiscount:0,gender:'any',birthday:true,from:'',to:'',lockedVisible:true},
  {id:'r5',title:'Футболка',category:'Мерч',desc:'Фирменная футболка',price:3500,stock:6,limit:1,sort:5,fulfill:'В офисе',active:true,emoji:'👕',main:'',media:[],minDiscount:5,gender:'male',birthday:false,from:'',to:'',lockedVisible:true}
 ],
 promotions:[
  {id:'p1',title:'Подписка VK',text:'Подпишитесь на основную группу',reward:'+100 АМ',kind:'Постоянные'},
  {id:'p2',title:'Telegram',text:'Подписка на канал Амплитуды',reward:'+150 АМ',kind:'Постоянные'},
  {id:'p3',title:'MAX',text:'Подписка на канал MAX',reward:'+200 АМ',kind:'Постоянные'},
  {id:'p4',title:'День рождения',text:'Специальный бонус в день рождения',reward:'+300 АМ',kind:'События'},
  {id:'p5',title:'Осенний бонус',text:'Дополнительные АМ за сезонные активности',reward:'+50 АМ',kind:'Сезонные'}
 ],
 events:[{id:'e1',title:'День рождения',trigger:'birthday',action:'+300 АМ',active:true},{id:'e2',title:'Первый вход',trigger:'first_login',action:'Подарок: Стикеры',active:true}],
 gifts:[{id:'g1',title:'Сюрприз-мини',audience:'Все участники',status:'Активен'},{id:'g2',title:'Подарок имениннику',audience:'День рождения',status:'Активен'}],
 channels:[
  {id:'ch1',name:'VK — Амплитуда',type:'VK',link:'vk.com/amplitudann',bonus:100,active:true,primary:true},
  {id:'ch2',name:'Telegram @AmplitudAm',type:'Telegram',link:'t.me/AmplitudAm',bonus:150,active:true,primary:false},
  {id:'ch3',name:'MAX',type:'MAX',link:'max.ru/amplituda',bonus:200,active:true,primary:false},
  {id:'ch4',name:'YouTube',type:'YouTube',link:'youtube.com/@amplituda',bonus:0,active:false,primary:false}
 ],
 redemptions:[]
};
