/* Comportamento das paginas quando abertas dentro de uma aba da moldura (/).
 *
 * - Ctrl+clique ou clique do meio num link do sistema abre em OUTRA aba da
 *   moldura (e nao numa janela solta do navegador).
 * - Links e botoes com data-newtab abrem o destino numa aba nova (ex.: "Filtrar
 *   em nova aba", "Buscar em nova aba"). Fora da moldura, funcionam normalmente.
 * - Avisa a moldura quando a pagina comeca a trocar, para mostrar o "carregando".
 */
(function () {
  'use strict';

  var tabs = null;
  try { if (window.top !== window.self) tabs = window.top.kbTabs || null; } catch (e) { tabs = null; }
  if (!tabs) return;

  function localPath(href) {
    var u = new URL(href, location.href);
    if (u.origin !== location.origin) return null;
    return u.pathname + u.search + u.hash;
  }

  function linkTarget(ev) {
    var a = ev.target.closest('a[href]');
    if (!a || a.hasAttribute('download') || /^(mailto|tel|javascript):/i.test(a.getAttribute('href'))) return null;
    if (/\/download$/.test(new URL(a.href, location.href).pathname)) return null;   // baixar continua baixando
    return localPath(a.href);
  }

  document.addEventListener('click', function (ev) {
    var a = ev.target.closest('a[data-newtab]');
    var path;
    if (a) {
      path = localPath(a.href);
      if (path) { ev.preventDefault(); tabs.open(path); }
      return;
    }
    if (!(ev.ctrlKey || ev.metaKey)) return;
    path = linkTarget(ev);
    if (path) { ev.preventDefault(); tabs.open(path, { background: true }); }
  });

  document.addEventListener('auxclick', function (ev) {
    if (ev.button !== 1) return;
    var path = linkTarget(ev);
    if (path) { ev.preventDefault(); tabs.open(path, { background: true }); }
  });

  // botao de envio com data-newtab: monta a URL do formulario (GET) e abre em aba nova
  document.addEventListener('submit', function (ev) {
    var btn = ev.submitter;
    if (!btn || !btn.hasAttribute('data-newtab')) return;
    var form = ev.target;
    if ((form.method || 'get').toLowerCase() !== 'get') return;
    ev.preventDefault();
    var url = new URL(form.action, location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();
    tabs.open(url.pathname + url.search);
  });

  window.addEventListener('beforeunload', function () {
    try { tabs.loading(window); } catch (e) { /* moldura fechada */ }
  });

  // ------------------------------------------------ "+ Notas" sobre texto selecionado
  // Leva o trecho para o bloco de notas da moldura, com a fonte (titulo + endereco).
  // Numa linha da pseudoplanilha, a fonte aponta a aba e a linha exatas.
  var notes = null;
  try { notes = window.top.kbNotes || null; } catch (e) { notes = null; }
  if (!notes) return;

  var clipBtn = document.createElement('button');
  clipBtn.type = 'button';
  clipBtn.className = 'kb-clip-btn';
  clipBtn.textContent = '+ Notas';
  clipBtn.title = 'Levar o texto selecionado para o bloco de notas (Alt+S)';
  clipBtn.hidden = true;
  document.body.appendChild(clipBtn);

  function selectedText() {
    var s = window.getSelection();
    if (!s || s.isCollapsed) return '';
    var el = s.anchorNode && (s.anchorNode.nodeType === 1 ? s.anchorNode : s.anchorNode.parentElement);
    if (el && el.closest('input, textarea, [contenteditable="true"]')) return '';
    return s.toString().replace(/ /g, ' ').trim();
  }

  function source() {
    var url = new URL(location.href);
    var s = window.getSelection();
    var node = s && s.anchorNode;
    var el = node && (node.nodeType === 1 ? node : node.parentElement);
    var row = el && el.closest('tr[id^="r"]');
    if (row && /^r\d+$/.test(row.id)) {           // linha da pseudoplanilha
      url.searchParams.set('row', row.id.slice(1));
      url.hash = row.id;
    }
    var title = document.title.replace(/\s*·\s*Semantix\s*$/, '');
    if (row) {
      var tab = document.querySelector('.sheet-tab.is-active');
      title += (tab ? ' › aba ' + tab.firstChild.textContent.trim() : '') + ' › linha ' + row.id.slice(1);
    }
    return { title: title, url: url.pathname + url.search + url.hash };
  }

  function send() {
    var text = selectedText();
    if (!text) return;
    var src = source();
    notes.addClip({ text: text, title: src.title, url: src.url });
    clipBtn.hidden = true;
    window.getSelection().removeAllRanges();
  }

  function place() {
    var text = selectedText();
    if (text.length < 2) { clipBtn.hidden = true; return; }
    var range = window.getSelection().getRangeAt(0);
    var rects = range.getClientRects();
    var r = rects.length ? rects[rects.length - 1] : range.getBoundingClientRect();
    clipBtn.hidden = false;
    var x = Math.min(window.innerWidth - clipBtn.offsetWidth - 8, Math.max(8, r.right - clipBtn.offsetWidth / 2));
    var y = r.bottom + 8 + clipBtn.offsetHeight > window.innerHeight ? r.top - clipBtn.offsetHeight - 8 : r.bottom + 8;
    clipBtn.style.left = x + 'px';
    clipBtn.style.top = y + 'px';
  }

  document.addEventListener('mouseup', function (ev) {
    if (ev.target === clipBtn) return;
    setTimeout(place, 0);
  });
  document.addEventListener('keyup', function (ev) { if (ev.shiftKey) place(); });
  document.addEventListener('mousedown', function (ev) { if (ev.target !== clipBtn) clipBtn.hidden = true; });
  window.addEventListener('scroll', function () { clipBtn.hidden = true; }, true);
  clipBtn.addEventListener('mousedown', function (ev) { ev.preventDefault(); });   // nao perde a selecao
  clipBtn.addEventListener('click', send);

  document.addEventListener('keydown', function (ev) {
    if (!ev.altKey) return;
    if (ev.key === 's' || ev.key === 'S') { ev.preventDefault(); send(); }
    if (ev.key === 'n' || ev.key === 'N') { ev.preventDefault(); notes.toggle(); }
  });
})();
