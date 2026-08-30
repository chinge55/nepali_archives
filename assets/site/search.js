(function(){
 var q=document.getElementById('q'),R=document.getElementById('results'),
     H=document.getElementById('hint'),FT=document.getElementById('ft'),
     BASE=(R&&R.getAttribute('data-base'))||(FT&&FT.getAttribute('data-base'))||'';
 // Scoped mode (author/collection/genre pages): tier-1 filters the on-page works
 // list, tier-2 passes a Pagefind filter. Home (no scope attrs) keeps the global behavior.
 var SCOPE=null;
 if(FT){var sa=FT.getAttribute('data-scope-author'),sc=FT.getAttribute('data-scope-collection'),
   sg=FT.getAttribute('data-scope-genre');
   if(sa||sc||sg){SCOPE={};if(sa)SCOPE.author=sa;if(sc)SCOPE.collection=sc;if(sg)SCOPE.genre=sg;}}
 var idx=null,loading=false;
 function norm(s){return (s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();}
 function isDev(s){return /[\u0900-\u097f]/.test(s);}

 // Levenshtein distance, bounded: returns >max as soon as the best path exceeds max.
 function lev(a,b,max){
   var la=a.length,lb=b.length;
   if(Math.abs(la-lb)>max) return max+1;
   var prev=[],cur=[],i,j;
   for(j=0;j<=lb;j++) prev[j]=j;
   for(i=1;i<=la;i++){
     cur[0]=i; var rb=i;
     for(j=1;j<=lb;j++){
       var c=a.charCodeAt(i-1)===b.charCodeAt(j-1)?0:1;
       var v=prev[j-1]+c; var d=prev[j]+1; if(d<v)v=d; d=cur[j-1]+1; if(d<v)v=d;
       cur[j]=v; if(v<rb)rb=v;
     }
     if(rb>max) return max+1;
     var t=prev;prev=cur;cur=t;
   }
   return prev[lb];
 }
 function tol(n){return n<=5?1:(n<=9?2:3);}
 // fuzzy similarity of ONE query token to ONE field token (0 = no match)
 function tokenSim(a,b){
   if(a===b) return 64;
   if(b.lastIndexOf(a,0)===0) return 60;         // query token is a prefix (sund->sundari)
   if(b.indexOf(a)>=0) return 54;                // substring
   if(a.length<3) return 0;                      // no fuzzy on 1-2 char tokens
   var t=tol(a.length),d=lev(a,b,t);
   if(d<=t) return 56-d*14;                      // whole-token typo (pagl~pagal)
   if(b.length>a.length){                        // typo of just the word's start (ranks lower)
     d=lev(a,b.slice(0,a.length),t);
     if(d<=t) return 48-d*14;
   }
   return 0;
 }
 // every query token must match some field token within tolerance
 function tokScore(q,f){
   var qt=q.split(' ').filter(Boolean),ft=f.split(' ').filter(Boolean),a,b,tot=0;
   if(!qt.length||!ft.length) return 0;
   for(a=0;a<qt.length;a++){ var best=0;
     for(b=0;b<ft.length;b++){var s=tokenSim(qt[a],ft[b]); if(s>best)best=s;}
     if(!best) return 0; tot+=best; }
   return tot/qt.length;                          // 0..64; always below a real substring (72+)
 }
 function scoreField(q,f){
   if(!q||!f) return 0;
   if(f===q) return 100;                          // exact
   if(f.lastIndexOf(q,0)===0) return 92;          // whole-query prefix
   if((' '+f).indexOf(' '+q)>=0) return 86;       // query starts a word
   if(f.indexOf(q)>=0) return 72;                 // substring anywhere
   if(q.length<3 && q.indexOf(' ')<0) return 0;   // tiny single token: substring only
   return tokScore(q,f);                          // typo-tolerant fallback
 }
 function score(w,qn,qraw){
   var s=scoreField(qraw,w.t||'');               // Devanagari (raw)
   var a=scoreField(qn,w._r); if(a>s)s=a;
   a=scoreField(qn,w._s); if(a>s)s=a;
   a=scoreField(qn,w._c)-8; if(a>s)s=a;           // collection ranks a touch lower
   a=scoreField(qn,w._a)-6; if(a>s)s=a;           // author name
   return s;
 }
 function load(cb){ if(idx){cb();return;} if(loading)return; loading=true;
   fetch(BASE+'search-index.json').then(function(r){return r.json();}).then(function(d){
     idx=d.works; for(var k=0;k<idx.length;k++){var w=idx[k];
       w._r=norm(w.r); w._s=norm(w.s); w._c=norm(w.c); w._a=norm(w.a);}    // precompute once
     cb();});}
 var G=__GENRE_MAP__;
 function dev(n){return String(n).replace(/[0-9]/g,function(d){return '\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f'[d];});}
 function renderWorks(list){
   var rows=list.slice(0,60).map(function(w){
     var sub=[w.a,w.c].filter(Boolean).join(' \u00b7 ');
     var wm=(w.g&&G[w.g]?'<span class="chip g-'+w.g+'">'+G[w.g]+'</span>':'')+
            '<span class=rt>'+(w.m?'~'+dev(w.m)+' \u092e\u093f\u0928\u0947\u091f':'\u091b\u094b\u091f\u094b')+'</span>'+
            (w.f?'<span class=scan>\ud83d\udcd6</span>':'');
     return '<li><a class=row-link href="'+BASE+w.p+'"><span class=wmeta>'+wm+'</span>'+w.t+(w.r?' <span class=r>'+w.r+'</span>':'')+
            (sub?'<span class=snip>'+sub+'</span>':'')+'</a></li>';}).join('');
   R.innerHTML=rows;
   H.textContent=list.length+' शीर्षक';
 }

 // ---- scoped tier-1: live-filter the works list already on the page ----
 var LIS=null;
 function domFilter(qn,qraw){
   if(!LIS) LIS=[].map.call(document.querySelectorAll('ul.works li'),function(li){
     return {li:li,t:li.textContent||'',n:norm(li.textContent||'')};});
   var shown=0;
   LIS.forEach(function(o){
     var hit=!qn||(qraw&&o.t.indexOf(qraw)>=0)||scoreField(qn,o.n)>0;
     o.li.style.display=hit?'':'none'; if(hit)shown++;
   });
   [].forEach.call(document.querySelectorAll('.group'),function(g){   // hide emptied genre groups
     g.style.display=g.querySelector('ul.works li:not([style*="none"])')?'':'none';
   });
   H.textContent=qn?(shown+' कृति मिल्यो'):'';
 }

 // ---- tier-2: full-text via Pagefind, bridged from roman when needed ----
 var pfP=null;
 function pagefind(){ if(pfP) return pfP;
   pfP=import(new URL(BASE+'pagefind/pagefind.js',location.href).href).catch(function(){return null;});
   return pfP; }
 var shard={};
 function getShard(L){ if(shard[L]) return shard[L];
   shard[L]=fetch(BASE+'searchroman/'+L+'.json').then(function(r){return r.ok?r.json():{};},function(){return {};});
   return shard[L]; }
 // xnorm(): the /type/ tool's normalization contract (pipeline translit_keys
 // .normalize / assets/type/engine.js — keep all three in sync). Shard keys are
 // built with the same fold, so naam/nam, chha/cha/xa, shabda/sabda hit exactly.
 var XSUB={ksh:'kC',chh:'C',ch:'C',gy:'J',sh:'s',ph:'P',ee:'i',oo:'u',c:'C',x:'C',f:'P',z:'j',w:'b',v:'b',q:'k'};
 var XRE=/ksh|chh|ch|gy|sh|ph|ee|oo|[cxfzwvq]/g;
 function xnorm(w){
   w=w.toLowerCase().replace(/[^a-z]/g,'').replace(XRE,function(m){return XSUB[m];});
   var o='',i;
   for(i=0;i<w.length;i++) if(w.charAt(i)!==o.charAt(o.length-1)) o+=w.charAt(i);
   if(o.length>1&&o.charAt(o.length-1)==='a') o=o.slice(0,-1);
   return o;
 }
 // roman token -> up to 6 Devanagari candidates (exact > prefix > fuzzy),
 // all matched on normalized keys
 function bridge(tok){ var key=xnorm(tok), L=key.charAt(0).toLowerCase();
   if(!/[a-z]/.test(L)) return Promise.resolve([]);
   return getShard(L).then(function(map){
     if(map[key]) return map[key].slice(0,6);
     var keys=Object.keys(map),i,pre=[];
     for(i=0;i<keys.length;i++) if(keys[i].lastIndexOf(key,0)===0) pre.push(keys[i]);
     if(pre.length){ pre.sort(function(a,b){return a.length-b.length;});
       var out=[]; for(i=0;i<pre.length&&out.length<6;i++) out=out.concat(map[pre[i]]); return out.slice(0,6); }
     if(key.length>=3){ var t=tol(key.length),best=99,bk=null;
       for(i=0;i<keys.length;i++){ var d=lev(key,keys[i],t); if(d<best){best=d;bk=keys[i];} }
       if(bk&&best<=t) return map[bk].slice(0,6); }
     return [];
   });
 }
 // raw query -> array of Pagefind query strings
 function buildQueries(qraw){
   if(isDev(qraw)) return Promise.resolve([qraw]);
   var toks=norm(qraw).split(' ').filter(Boolean);
   if(!toks.length) return Promise.resolve([]);
   return Promise.all(toks.map(bridge)).then(function(per){
     if(toks.length===1) return per[0].slice(0,4);             // OR each candidate
     return [per.map(function(c){return c[0]||'';}).filter(Boolean).join(' ')]; // best-per-token, AND
   });
 }
 var ftSeq=0;
 function fullText(qraw){
   var my=++ftSeq;
   if(!isDev(qraw) && norm(qraw).length<2){FT.innerHTML='';return;}
   FT.innerHTML='<p class=ftmsg>पाठभित्र खोज्दै…</p>';
   Promise.all([pagefind(),buildQueries(qraw)]).then(function(a){
     var pf=a[0],qs=a[1]; if(my!==ftSeq)return; if(!pf){FT.innerHTML='';return;}
     if(!qs.length){FT.innerHTML='<p class=ftmsg>पाठभित्र केही फेला परेन।</p>';return;}
     var opts=SCOPE?{filters:SCOPE}:undefined;
     Promise.all(qs.map(function(s){return pf.search(s,opts);})).then(function(arr){
       if(my!==ftSeq) return;
       var seen={},merged=[];
       arr.forEach(function(res){ if(res&&res.results) res.results.forEach(function(r){
         if(!seen[r.id]){seen[r.id]=1;merged.push(r);} }); });
       Promise.all(merged.slice(0,10).map(function(r){return r.data();})).then(function(ds){
         if(my!==ftSeq) return; renderFT(ds);
       });
     });
   });
 }
 // append ?pagefind-highlight=… using the SURFACE words Pagefind marked in the excerpt
 // (the real on-page forms — not the stemmed query), so the work page can scroll+highlight.
 function hlUrl(url,excerpt){
   var seen={},m,re=/<mark>([\s\S]*?)<\/mark>/g;
   while((m=re.exec(excerpt))){
     var w=m[1].replace(/<[^>]*>/g,'').replace(/[^\u0900-\u097f ]/g,' ').trim();
     w.split(/\s+/).forEach(function(t){if(t)seen[t]=1;});
   }
   var ks=Object.keys(seen).slice(0,6);
   if(!ks.length) return url;
   var qp=ks.map(function(t){return 'pagefind-highlight='+encodeURIComponent(t);}).join('&');
   return url+(url.indexOf('?')<0?'?':'&')+qp;
 }
 function renderFT(ds){
   if(!ds||!ds.length){FT.innerHTML='<p class=ftmsg>पाठभित्र केही फेला परेन।</p>';return;}
   var h='<h2 class=fthead>पाठभित्र खोजी</h2><ul class=ftlist>';
   ds.forEach(function(d){
     var t=(d.meta&&d.meta.title)||d.url;
     h+='<li><a class=ftlink href="'+hlUrl(d.url,d.excerpt)+'"><span class=fttitle>'+t+'</span><p class=ex>'+d.excerpt+'</p></a></li>';
   });
   FT.innerHTML=h+'</ul>';
 }

 var ftTimer=null;
 function search(){
   var qraw=q.value.trim(),qn=norm(qraw);
   if(!qn){
     if(SCOPE){domFilter('','');}else{R.innerHTML='';H.textContent=idx?(idx.length+' कृति'):'';}
     FT.innerHTML=''; return;
   }
   if(SCOPE){
     domFilter(qn,qraw);                          // tier-1: narrow the visible list
   }else{
     load(function(){
       var hit=[],k;
       for(k=0;k<idx.length;k++){var sc=score(idx[k],qn,qraw); if(sc>0)hit.push([sc,idx[k]]);}
       hit.sort(function(a,b){return b[0]-a[0];});
       renderWorks(hit.map(function(x){return x[1];}));
     });
   }
   if(ftTimer)clearTimeout(ftTimer);
   ftTimer=setTimeout(function(){fullText(qraw);},250);
 }
 q.addEventListener('input',search);
 q.addEventListener('focus',function(){if(SCOPE)return;load(function(){if(!q.value)H.textContent=idx.length+' कृति';});});
 // deep link: /?q=term (e.g. a word clicked on the stats page) runs the search on load
 var dl=location.search.match(/[?&]q=([^&]*)/);
 if(dl){ try{q.value=decodeURIComponent(dl[1].replace(/\+/g,' '));}catch(e){} q.focus(); search(); }
})();
