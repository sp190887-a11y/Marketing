// V14.4 WHITE PAPER patch
(function(){
  const oldClean = window.cleanPaperStrong;
  window.cleanPaperStrong = function(c){
    // Keep the previous cleanup first if it exists.
    try{ if(typeof oldClean==='function') oldClean(c); }catch(e){}
    const ctx=c.getContext('2d',{willReadFrequently:true}), W=c.width, H=c.height;
    // The cover has no calendar grid, so clean its entire surface.
    const cut=S.i===0?H:Math.floor(H*0.84);
    const img=ctx.getImageData(0,0,W,cut), d=img.data;
    // Estimate paper white point from bright low-saturation samples.
    const ys=[];
    const step=Math.max(4,Math.floor(Math.min(W,H)/500));
    for(let y=0;y<cut;y+=step){
      for(let x=0;x<W;x+=step){
        const i=(y*W+x)*4, R=d[i],G=d[i+1],B=d[i+2], mx=Math.max(R,G,B),mi=Math.min(R,G,B), sat=mx-mi;
        if(sat<16){ const Y=.2126*R+.7152*G+.0722*B; if(Y>190) ys.push(Y); }
      }
    }
    ys.sort((a,b)=>a-b);
    const wp=ys.length?ys[Math.floor(ys.length*.72)]:242;
    const whiteCut=Math.max(212,wp-24), softCut=Math.max(190,wp-46);
    for(let i=0;i<d.length;i+=4){
      let R=d[i],G=d[i+1],B=d[i+2], mx=Math.max(R,G,B),mi=Math.min(R,G,B), sat=mx-mi;
      const Y=.2126*R+.7152*G+.0722*B;
      // Neutral bright paper / print texture -> pure white.
      if(sat<18 && Y>=whiteCut){ d[i]=d[i+1]=d[i+2]=255; continue; }
      // Very pale neutral shadows -> smoothly push toward white.
      if(sat<18 && Y>softCut){
        const t=(Y-softCut)/Math.max(1,whiteCut-softCut);
        const a=.55+.45*Math.min(1,t);
        d[i]=Math.round(R+(255-R)*a); d[i+1]=Math.round(G+(255-G)*a); d[i+2]=Math.round(B+(255-B)*a); continue;
      }
      // Preserve coloured strokes; give them a small contrast lift without changing hue much.
      if(sat>=18){
        const k=1.08;
        d[i]=Math.max(0,Math.min(255,128+(R-128)*k));
        d[i+1]=Math.max(0,Math.min(255,128+(G-128)*k));
        d[i+2]=Math.max(0,Math.min(255,128+(B-128)*k));
      } else if(Y<softCut){
        // Pencil / dark neutral strokes: mild contrast only.
        const v=Math.max(0,Math.min(255,128+(Y-128)*1.06));
        d[i]=d[i+1]=d[i+2]=Math.round(v);
      }
    }
    ctx.putImageData(img,0,0);
    return c;
  };
  try{
    document.querySelectorAll('.ver').forEach(x=>x.textContent='V14.4 · БЕЛЫЙ ФОН');
    document.querySelectorAll('#review header small').forEach(x=>x.textContent='Проверка кадра · V14.4');
  }catch(e){}
})();
