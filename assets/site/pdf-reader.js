(function(){
  var lib=window.pdfjsLib, host=document.getElementById('pdfpages'),
      statusEl=document.getElementById('pdfstatus'), url=host.getAttribute('data-url');
  function fail(){ host.innerHTML='<p class="pdferr">यो ब्राउजरमा रिडर चल्न सकेन। <a href="'+url+'">सिधै PDF हेर्नुहोस् / डाउनलोड गर्नुहोस्</a>।</p>'; }
  if(!lib||!('IntersectionObserver' in window)){ fail(); return; }
  lib.GlobalWorkerOptions.workerSrc="__WORKER_URL__";
  function dev(n){ return (''+n).replace(/[0-9]/g,function(d){return '०१२३४५६७८९'.charAt(+d);}); }
  var ZOOM=[0.6,0.75,0.9,1,1.2,1.45,1.75,2.1], zi=3, BASE=760;
  var doc=null, N=0, divs=[], rendered={}, visible={}, aspect='1 / 1.4', rt=0;
  function colW(){ return Math.min(BASE*ZOOM[zi], window.innerWidth-28); }
  function applyW(){ host.style.maxWidth=Math.round(colW())+'px'; }
  function render(pg){
    var div=divs[pg-1]; if(!div||rendered[pg]) return; rendered[pg]=true;
    doc.getPage(pg).then(function(page){
      if(!rendered[pg]) return;
      var dpr=window.devicePixelRatio||1, cssW=div.clientWidth||colW(),
          v1=page.getViewport({scale:1}), vp=page.getViewport({scale:(cssW/v1.width)*dpr}),
          c=document.createElement('canvas');
      c.width=Math.ceil(vp.width); c.height=Math.ceil(vp.height);
      var old=div.querySelector('canvas'); if(old) div.removeChild(old);
      div.style.aspectRatio=''; div.style.minHeight='0'; div.appendChild(c);
      page.render({canvasContext:c.getContext('2d'), viewport:vp});
    }).catch(function(){ rendered[pg]=false; });
  }
  function release(pg){
    var div=divs[pg-1]; rendered[pg]=false;
    if(div){ var c=div.querySelector('canvas'); if(c){ div.removeChild(c); div.style.aspectRatio=aspect; div.style.minHeight=''; } }
  }
  function counter(){ var k=Object.keys(visible).map(Number); if(k.length) statusEl.textContent='पृष्ठ '+dev(Math.min.apply(null,k))+' / '+dev(N); }
  function rezoom(){ applyW(); for(var pg in rendered){ if(rendered[pg]){ rendered[pg]=false; render(+pg); } } }
  var plus=document.getElementById('pdfplus'), minus=document.getElementById('pdfminus');
  plus.addEventListener('click',function(){ if(zi<ZOOM.length-1){zi++; rezoom();} });
  minus.addEventListener('click',function(){ if(zi>0){zi--; rezoom();} });
  window.addEventListener('resize',function(){ clearTimeout(rt); rt=setTimeout(rezoom,200); });
  applyW();
  lib.getDocument({url:url, disableAutoFetch:true, disableStream:false, rangeChunkSize:65536}).promise
    .then(function(pdf){ doc=pdf; N=pdf.numPages; return pdf.getPage(1); })
    .then(function(p1){
      var v=p1.getViewport({scale:1}); aspect=v.width+' / '+v.height;
      var frag=document.createDocumentFragment();
      for(var i=1;i<=N;i++){ var d=document.createElement('div'); d.className='pdfpage'; d.dataset.page=i; d.style.aspectRatio=aspect; frag.appendChild(d); divs.push(d); }
      host.appendChild(frag);
      statusEl.textContent='पृष्ठ १ / '+dev(N);
      var io=new IntersectionObserver(function(es){
        es.forEach(function(e){ var pg=+e.target.dataset.page;
          if(e.isIntersecting){ visible[pg]=true; render(pg); } else { delete visible[pg]; release(pg); } });
        counter();
      }, {rootMargin:'800px 0px'});
      divs.forEach(function(d){ io.observe(d); });
    })
    .catch(fail);
})();