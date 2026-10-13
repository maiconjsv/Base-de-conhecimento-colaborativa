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
})();
