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
