(function(){
 var root=document.documentElement,mq=matchMedia('(prefers-color-scheme:dark)');
 function eff(){return root.getAttribute('data-theme')||(mq.matches?'dark':'light');}
 var b=document.getElementById('themed');
 if(b){
   var sync=function(){b.textContent=eff()==='dark'?'☀':'☾';};   // sun in dark, moon in light
   sync();
   b.addEventListener('click',function(){
     var n=eff()==='dark'?'light':'dark';
     root.setAttribute('data-theme',n);
     try{localStorage.setItem('theme',n);}catch(e){}
     sync();});
   if(mq.addEventListener) mq.addEventListener('change',function(){if(!root.getAttribute('data-theme'))sync();});
 }
 // Play the supplied 16 x 70 ms hover frames once, then restore the still mark.
 // Explicit frame selection avoids GIF looping and works without network reloads.
 var brand=document.querySelector('.brand'),motion=matchMedia('(prefers-reduced-motion:reduce)');
 if(brand && window.CSS && (CSS.supports('mask-image','url("")') || CSS.supports('-webkit-mask-image','url("")'))){
   var mark=brand.querySelector('.brand-mark'),logoTick=0;
   var stopLogo=function(){
     cancelAnimationFrame(logoTick);logoTick=0;
     if(mark)mark.style.removeProperty('--logo-position');
   };
   var playLogo=function(){
     if(!mark || motion.matches || logoTick || document.hidden)return;
     var started=null,last=-1;
     var frame=function(now){
       if(started===null)started=now;
       var n=Math.floor((now-started)/70);
       if(n>=16){stopLogo();return;}
       if(n!==last){mark.style.setProperty('--logo-position',(n*100/15)+'%');last=n;}
       logoTick=requestAnimationFrame(frame);
     };
     logoTick=requestAnimationFrame(frame);
   };
   brand.addEventListener('pointerenter',function(e){if(e.pointerType==='mouse')playLogo();});
   brand.addEventListener('pointerleave',stopLogo);
   brand.addEventListener('focus',function(){if(brand.matches(':focus-visible'))playLogo();});
   brand.addEventListener('blur',stopLogo);
   if(motion.addEventListener)motion.addEventListener('change',stopLogo);
   document.addEventListener('visibilitychange',function(){if(document.hidden)stopLogo();});
   addEventListener('pagehide',stopLogo);
 }
 // Keep reading and download links on the chosen edition; navigation is explicit.
 document.querySelectorAll('.pdf-choice').forEach(function(picker){
   var select=picker.querySelector('select'),controls=picker.querySelector('.pdf-choice-controls');
   var syncEdition=function(){
     var option=select.options[select.selectedIndex];
     picker.querySelector('.pdf-choice-view').href=option.value;
     picker.querySelector('.pdf-choice-download').href=option.getAttribute('data-download');
   };
   select.addEventListener('change',syncEdition);
   addEventListener('pageshow',syncEdition);
   syncEdition();
   controls.hidden=false;
   picker.querySelector('.pdf-choice-fallback').hidden=true;
 });
 var bar=document.getElementById('prog');
 if(bar){
   var pend=false,upd=function(){pend=false;
     var h=document.documentElement,m=h.scrollHeight-h.clientHeight,y=h.scrollTop||document.body.scrollTop;
     bar.style.width=(m>0?(y/m*100):0)+'%';};
   addEventListener('scroll',function(){if(!pend){pend=true;requestAnimationFrame(upd);}},{passive:true});
   addEventListener('resize',upd); upd();
 }
 // Arrived from a search result (?pagefind-highlight=…) → load Pagefind's highlighter,
 // which marks + scrolls to the match inside [data-pagefind-body]. Otherwise pages stay JS-free.
 if(location.search.indexOf('pagefind-highlight=')>=0){
   import('/pagefind/pagefind-highlight.js').then(function(m){
     var P=m&&(m.default||window.PagefindHighlight); if(!P) return;
     new P({highlightParam:'pagefind-highlight'});
     setTimeout(function(){var f=document.querySelector('mark.pagefind-highlight');
       if(f) f.scrollIntoView({block:'center'});},60);   // land on the matched passage
   }).catch(function(){});
 }
})();
