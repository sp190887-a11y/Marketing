// V14.5 ROBUST DATE MARK patch
(function(){
  function median(a){if(!a.length)return 0;let b=[...a].sort((x,y)=>x-y),n=b.length;return n%2?b[(n-1)/2]:(b[n/2-1]+b[n/2])/2}
  function stats(a){let m=median(a),mad=median(a.map(v=>Math.abs(v-m)));return{m,mad:Math.max(mad,.0025)}}
  window.marked=function(c,mn){
    if(!mn)return[];
    const s=smallPage(c),g=gridGeo(s,mn),ctx=s.getContext('2d',{willReadFrequently:true}),im=ctx.getImageData(0,0,s.width,s.height),d=im.data,W=s.width,H=s.height,rows=[];
    function px(x,y){x=Math.max(0,Math.min(W-1,x|0));y=Math.max(0,Math.min(H-1,y|0));let i=(y*W+x)*4,R=d[i],G=d[i+1],B=d[i+2],mx=Math.max(R,G,B),mi=Math.min(R,G,B);return{Y:.2126*R+.7152*G+.0722*B,sat:mx-mi,R,G,B}}
    for(let day=1;day<=g.days;day++){
      const k=g.start+day-1,r=Math.floor(k/7),col=k%7,x0=g.gx0+col*g.cw,y0=g.top+g.head+r*g.ch;
      // The printed date number is in the upper-left part of every cell. A hand circle/check around the date creates extra ink in this annulus.
      const cx=x0+g.cw*.085,cy=y0+g.ch*.29,ro=g.ch*.62,ri=g.ch*.17;
      const xa=Math.max(0,Math.floor(cx-ro)),xb=Math.min(W-1,Math.ceil(cx+ro)),ya=Math.max(0,Math.floor(cy-ro)),yb=Math.min(H-1,Math.ceil(cy+ro));
      let samples=[],ring=[];
      for(let y=ya;y<=yb;y+=2)for(let x=xa;x<=xb;x+=2){let q=px(x,y),dist=Math.hypot(x-cx,y-cy);if(dist<ro&&q.sat<28)samples.push(q.Y);if(dist>=ri&&dist<=ro)ring.push(q)}
      samples.sort((a,b)=>a-b);let bg=samples.length?samples[Math.floor(samples.length*.78)]:238,ink=0,tot=0,color=0;
      for(let q of ring){tot++;let dark=q.Y<bg-38,colored=q.sat>28&&q.Y<226;if(dark||colored)ink++;if(colored)color++}
      rows.push({day,col,ring:ink/Math.max(1,tot),color:color/Math.max(1,tot),bg});
    }
    const wd=rows.filter(v=>v.col<5),we=rows.filter(v=>v.col>=5),swd=stats(wd.map(v=>v.ring)),swe=stats(we.map(v=>v.ring)),cwd=stats(wd.map(v=>v.color)),cwe=stats(we.map(v=>v.color));
    let out=[];
    for(let v of rows){let sr=v.col<5?swd:swe,sc=v.col<5?cwd:cwe,z=(v.ring-sr.m)/(1.4826*sr.mad),zc=(v.color-sc.m)/(1.4826*sc.mad),ringStrong=(z>=2.8&&v.ring>=sr.m+.028)||(v.ring>=sr.m+.055),colorStrong=(zc>=3.0&&v.color>=sc.m+.018);if(ringStrong||colorStrong)out.push(v)}
    // A large circle can spill into a neighbouring cell. Prefer the cell where the mark is actually centred around its own printed number.
    out=out.filter(v=>!out.some(n=>n.day!==v.day&&Math.abs(n.day-v.day)===1&&n.col!==0&&v.col!==0&&n.ring>v.ring*1.75));
    window.__lastDateDetect={month:mn,rows,found:out.map(v=>v.day)};
    return out.sort((a,b)=>a.day-b.day).slice(0,12).map(v=>v.day);
  };
  try{document.querySelectorAll('.ver').forEach(x=>x.textContent='V14.5 · ДАТЫ');document.querySelectorAll('#review header small').forEach(x=>x.textContent='Проверка кадра · V14.5')}catch(e){}
})();

