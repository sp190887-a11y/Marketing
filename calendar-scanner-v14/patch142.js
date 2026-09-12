// V14.2 marker V2 patch: large solid ID dots, code = page index + 1.
decodePageId=function(c){
  let m=mm(),ctx=c.getContext('2d',{willReadFrequently:true}),sx=c.width/m.w,sy=c.height/m.h,
      defs=[[10,15,1,1],[m.w-10,15,-1,1],[m.w-10,m.h-10,-1,-1],[10,m.h-10,1,-1]],
      pos=[1.8,4.2,6.6,9.0],weights=[8,4,2,1],bitVotes=[0,0,0,0],vals=[];
  for(let [vx,vy,dx,dy] of defs){
    let ex=(vx+dx*3.2)*sx,ey=(vy+dy*3.2)*sy,best={Y:1e9,x:ex,y:ey},range=1.25,step=.12,rr=.34*(sx+sy)/2;
    for(let oy=-range;oy<=range;oy+=step)for(let ox=-range;ox<=range;ox+=step){
      let x=ex+ox*sx,y=ey+oy*sy,Y=patchLum(ctx,x,y,rr);
      if(Y<best.Y)best={Y,x,y};
    }
    let offx=best.x-ex,offy=best.y-ey,
        ws=[[3.2,5.1],[6.0,3.2],[10.8,6.7]].map(([u,v])=>patchLum(ctx,(vx+dx*u)*sx+offx,(vy+dy*v)*sy+offy,rr)).sort((a,b)=>a-b),
        white=ws[1],thr=best.Y+.55*(white-best.Y),code=0,bits=[],lum=[];
    for(let i=0;i<4;i++){
      let x=(vx+dx*pos[i])*sx+offx,y=(vy+dy*6.7)*sy+offy,Y=patchLum(ctx,x,y,rr),one=Y<thr;
      bits.push(one?1:0);lum.push(Math.round(Y));bitVotes[i]+=one?1:0;if(one)code+=weights[i];
    }
    vals.push({code,bits,lum,dark:Math.round(best.Y),white:Math.round(white),thr:Math.round(thr),offset:[+(offx/sx).toFixed(2),+(offy/sy).toFixed(2)]});
  }
  let code=0,strong=0;
  for(let i=0;i<4;i++){if(bitVotes[i]>=3){code+=weights[i];strong++}else if(bitVotes[i]<=1)strong++;}
  let pageId=code-1,confident=strong===4&&pageId>=0&&pageId<=12,
      cornerPages=vals.map(v=>v.code>=1&&v.code<=13?v.code-1:-1),same=cornerPages.filter(x=>x===pageId).length;
  return{id:pageId,votes:same,all:cornerPages,levels:vals.map(v=>v.lum),bitVotes,confident};
};

erase=function(c){
  let m=mm(),ctx=c.getContext('2d',{willReadFrequently:true}),W=c.width,H=c.height,mmx=W/m.w,mmy=H/m.h,
      boxes=[[8.3,13.3,13,10.8],[m.w-21.3,13.3,13,10.8],[m.w-21.3,m.h-19.1,13,10.8],[8.3,m.h-19.1,13,10.8]];
  for(let [xx,yy,ww,hh] of boxes){
    let x=Math.max(0,Math.round(xx*mmx)),y=Math.max(0,Math.round(yy*mmy)),w=Math.min(W-x,Math.round(ww*mmx)),h=Math.min(H-y,Math.round(hh*mmy)),pad=Math.round(4*Math.min(mmx,mmy)),sx0=Math.max(0,x-pad),sy0=Math.max(0,y-pad),sw=Math.min(W-sx0,w+pad*2),sh=Math.min(H-sy0,h+pad*2),im=ctx.getImageData(sx0,sy0,sw,sh).data,rs=0,gs=0,bs=0,n=0;
    for(let py=0;py<sh;py+=5)for(let px=0;px<sw;px+=5){
      if(px>pad&&px<pad+w&&py>pad&&py<pad+h)continue;
      let i=(py*sw+px)*4,R=im[i],G=im[i+1],B=im[i+2],mx=Math.max(R,G,B),mi=Math.min(R,G,B),Y=.2126*R+.7152*G+.0722*B;
      if(Y>155&&mx-mi<45){rs+=R;gs+=G;bs+=B;n++;}
    }
    let R=n?Math.round(rs/n):242,G=n?Math.round(gs/n):242,B=n?Math.round(bs/n):240;
    ctx.fillStyle=`rgb(${R},${G},${B})`;ctx.fillRect(x,y,w,h);
  }
};
