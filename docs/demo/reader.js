(function () {
  var D = JSON.parse(document.getElementById('reader-data').textContent);
  var L = D.lines, i = 0, filt = '', t0 = null, tick = null, log = {};
  var $ = function (id) { return document.getElementById(id); };
  var R = $('reader');
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
  function mmss(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
  function chip(k) { var s = D.speakers[k]; return '<span class="spk c-' + s.color + '">' + esc(k) + ' <small>' + esc(s.ko) + '</small></span>'; }
  function elapsed() { return t0 == null ? 0 : (Date.now() - t0) / 1000; }
  function videoAt() { return D.take + elapsed(); }

  // list view: speaker emphasis
  var btns = document.querySelectorAll('.filters .f');
  btns.forEach(function (b) {
    b.addEventListener('click', function () {
      filt = b.getAttribute('data-f');
      btns.forEach(function (x) { x.classList.toggle('on', x === b); });
      document.querySelectorAll('.line').forEach(function (el) {
        var s = el.getAttribute('data-spk');
        el.classList.toggle('dim', !!filt && s !== filt && s !== 'ALL');
      });
    });
  });

  function line(k, cls) {
    var x = L[k]; if (!x) return '';
    return '<b>' + esc(x.id) + '</b> ' + esc(D.speakers[x.speaker].ko) + ': ' + esc(x.text);
  }
  function render() {
    var x = L[i], sc = D.scenes[x.scene];
    var mine = !filt || x.speaker === filt || x.speaker === 'ALL';
    var cur = $('r-cur');
    cur.className = mine ? '' : 'cue-only';
    cur.innerHTML = chip(x.speaker) + ' <b class="num">' + esc(x.id) + '</b>' +
      '<p class="r-say" lang="en">' + esc(x.text) + '</p>' +
      (x.cue ? '<p class="r-cue">' + esc(x.cue) + '</p>' : '') +
      '<p class="r-res">화면: ' + esc(x.result || '') + '</p>';
    $('r-prev').innerHTML = i > 0 ? '이전 ' + line(i - 1) : '테이크 시작(영상 ' + mmss(D.take) + '), 손으로 입장 4초 뒤 첫 대사';
    $('r-next').innerHTML = i < L.length - 1 ? '다음 ' + line(i + 1) : '끝. 이 뒤로 칸 팝오버와 기록 카드(78~90초)';
    $('r-scene').textContent = '장면 ' + sc.t[0] + '~' + sc.t[1] + '초 ' + sc.title;
    $('r-pos').textContent = (i + 1) + ' / ' + L.length;
    clock();
  }
  function clock() {
    var x = L[i], sc = D.scenes[x.scene], v = videoAt();
    var el = $('r-clock');
    el.textContent = '테이크 ' + mmss(elapsed()) + ' / 영상 ' + mmss(v);
    el.classList.toggle('late', t0 != null && v > sc.t[1]);
  }
  function stamp() {
    if (t0 == null) return;
    var x = L[i], sc = D.scenes[x.scene], v = videoAt();
    log[x.id] = { v: v, late: v > sc.t[1], early: v < sc.t[0] };
    var ol = $('r-log'); ol.innerHTML = '';
    L.forEach(function (y) {
      var g = log[y.id]; if (!g) return;
      var s2 = D.scenes[y.scene];
      var li = document.createElement('li');
      li.textContent = y.id + ' 영상 ' + mmss(g.v) + ' (장면 ' + s2.t[0] + '~' + s2.t[1] + (g.late ? ', 늦음 +' + Math.round(g.v - s2.t[1]) + '초' : g.early ? ', 빠름' : '') + ')';
      if (g.late) li.className = 'late';
      ol.appendChild(li);
    });
  }
  function go(k) { i = Math.max(0, Math.min(L.length - 1, k)); render(); stamp(); }
  function open(k) { R.hidden = false; document.body.style.overflow = 'hidden'; go(k || 0); $('r-fwd').focus(); }
  function close() { R.hidden = true; document.body.style.overflow = ''; var el = document.getElementById('line-' + L[i].id); if (el) el.scrollIntoView({ block: 'center' }); }
  function timer() {
    if (t0 == null) { t0 = Date.now(); tick = setInterval(clock, 250); $('r-timer').textContent = '시계 멈춤'; stamp(); }
    else { clearInterval(tick); tick = null; t0 = null; $('r-timer').textContent = '시계 시작'; clock(); }
  }
  function reset() { if (tick) clearInterval(tick); tick = null; t0 = null; log = {}; $('r-log').innerHTML = ''; $('r-timer').textContent = '시계 시작'; go(0); }

  $('open-reader').addEventListener('click', function () { open(0); });
  document.querySelectorAll('.read-here').forEach(function (b) { b.addEventListener('click', function () { open(+b.getAttribute('data-i')); }); });
  $('r-close').addEventListener('click', close);
  $('r-fwd').addEventListener('click', function () { go(i + 1); });
  $('r-back').addEventListener('click', function () { go(i - 1); });
  $('r-timer').addEventListener('click', timer);
  $('r-reset').addEventListener('click', reset);
  document.addEventListener('keydown', function (e) {
    if (R.hidden) return;
    if (e.key === 'Escape') { close(); }
    else if (e.key === 'ArrowRight' || e.key === 'PageDown' || (e.key === ' ' && e.target.tagName !== 'BUTTON')) { e.preventDefault(); go(i + 1); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); go(i - 1); }
    else if (e.key === 's' || e.key === 'S') { timer(); }
  });
})();
