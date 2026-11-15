(function () {
  var C = JSON.parse(document.getElementById('cue-data').textContent).cues;
  var END = C[C.length - 1].t[1];
  var $ = function (id) { return document.getElementById(id); };
  var R = $('reader'), pos = 0, base = null, tick = null;
  function mmss(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
  function slot(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML.replace(/\{([A-Z]+)\}/g, '<mark class="slot">$1</mark>'); }
  function now() { return base == null ? pos : Math.min(END, (Date.now() - base) / 1000); }
  function at(t) { for (var i = 0; i < C.length; i++) { if (t < C[i].t[1]) return i; } return C.length - 1; }
  function nextVo(i) { for (var k = i + 1; k < C.length; k++) { if (C[k].kind === 'vo') return k; } return -1; }

  function render() {
    var t = now(), i = at(t), c = C[i], n = nextVo(i);
    $('r-clock').textContent = mmss(t) + ' / ' + mmss(END);
    $('r-scene').textContent = c.t[0] + '~' + c.t[1] + '초 ' + c.scene;
    $('r-fill').style.width = ((t - c.t[0]) / (c.t[1] - c.t[0]) * 100).toFixed(1) + '%';
    R.classList.toggle('is-vo', c.kind === 'vo');
    if (c.kind === 'vo') {
      $('r-state').textContent = '읽기, 남은 ' + Math.ceil(c.t[1] - t) + '초';
      $('r-cur').innerHTML = slot(c.en);
      $('r-ko').innerHTML = slot(c.ko);
    } else {
      $('r-state').textContent = '쉬기. 자막만: ' + c.en;
      $('r-cur').innerHTML = n >= 0 ? slot(C[n].en) : '';
      $('r-ko').textContent = n >= 0 ? C[n].t[0] + '초에 읽을 문장, ' + Math.ceil(C[n].t[0] - t) + '초 뒤' : '';
    }
    $('r-next').innerHTML = c.kind === 'vo' && n >= 0 ? '다음 읽기 ' + C[n].t[0] + '초: ' + slot(C[n].en) : '';
    if (base != null && t >= END) stop();
  }
  function start() { base = Date.now() - pos * 1000; tick = setInterval(render, 100); $('r-play').textContent = '멈춤'; render(); }
  function stop() { pos = now(); base = null; if (tick) clearInterval(tick); tick = null; $('r-play').textContent = pos >= END ? '다시' : '시작'; render(); }
  function toggle() { if (base == null) { if (pos >= END) pos = 0; start(); } else stop(); }
  function seek(t) { var run = base != null; if (run) stop(); pos = Math.max(0, Math.min(END, t)); if (run) start(); else render(); }
  function jump(dir) {
    var i = at(now()), k = i + dir;
    while (k >= 0 && k < C.length && C[k].kind !== 'vo') k += dir;
    if (k >= 0 && k < C.length) seek(C[k].t[0]); else if (dir < 0) seek(0);
  }
  function open(t) { R.hidden = false; document.body.style.overflow = 'hidden'; seek(t || 0); $('r-play').focus(); }
  function close() { stop(); R.hidden = true; document.body.style.overflow = ''; }

  $('open-reader').addEventListener('click', function () { open(0); });
  document.querySelectorAll('.read-here').forEach(function (b) { b.addEventListener('click', function () { open(C[+b.getAttribute('data-i')].t[0]); }); });
  document.querySelectorAll('.copy').forEach(function (b) {
    b.addEventListener('click', function () {
      var txt = b.getAttribute('data-text');
      var done = function () { b.textContent = '복사됨'; setTimeout(function () { b.textContent = '자막 복사'; }, 1200); };
      var fallback = function () {
        var p = b.parentNode.querySelector('.en'), r = document.createRange(); r.selectNodeContents(p);
        var s = window.getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = '선택됨, 복사하세요';
      };
      try { navigator.clipboard.writeText(txt).then(done, fallback); } catch (e) { fallback(); }
    });
  });
  $('r-close').addEventListener('click', close);
  $('r-play').addEventListener('click', toggle);
  $('r-fwd').addEventListener('click', function () { jump(1); });
  $('r-back').addEventListener('click', function () { jump(-1); });
  $('r-reset').addEventListener('click', function () { seek(0); });
  document.addEventListener('keydown', function (e) {
    if (R.hidden) return;
    if (e.key === 'Escape') close();
    else if (e.key === ' ' && e.target.tagName !== 'BUTTON') { e.preventDefault(); toggle(); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); jump(1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); jump(-1); }
  });
})();
