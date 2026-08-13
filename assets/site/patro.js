
(function(){
  var grid=document.getElementById('zg');if(!grid)return;
  var tiles=[].slice.call(grid.querySelectorAll('.zt'));
  var cards={};[].forEach.call(document.querySelectorAll('.pt-card[data-rashi]'),
    function(c){cards[c.getAttribute('data-rashi')]=c;});
  var hint=document.getElementById('pthint');
  function show(r){
    tiles.forEach(function(t){
      t.setAttribute('aria-pressed',String(t.getAttribute('data-rashi')===r));});
    for(var k in cards)cards[k].style.display=(k===r)?'block':'none';
    if(hint)hint.className='pt-hint'+(r?' off':'');
  }
  grid.addEventListener('click',function(e){
    var t=e.target.closest('.zt');if(!t)return;
    var r=t.getAttribute('data-rashi');
    if(t.getAttribute('aria-pressed')==='true'){
      show(null);
      try{localStorage.removeItem('patroRashi');}catch(_){}
    }else{
      show(r);
      try{localStorage.setItem('patroRashi',r);}catch(_){}
    }
  });
  var saved=null;try{saved=localStorage.getItem('patroRashi');}catch(_){}
  show(saved&&cards[saved]?saved:null);
})();
