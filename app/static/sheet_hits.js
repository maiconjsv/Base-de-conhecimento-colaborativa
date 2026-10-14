/* Abas dos resultados de planilha (_sheet_rows.html).
 *
 * O HTML dos resultados chega por fetch/innerHTML (busca, Pesquisas, Perguntar),
 * entao a troca de aba e feita por delegacao de clique no documento inteiro.
 * Setas esquerda/direita trocam de aba quando o foco esta numa delas.
 */
(function () {
  'use strict';

  function select(tab) {
    var box = tab.closest('[data-sheet-hits]');
    if (!box) return;
    var idx = tab.dataset.idx;
    box.querySelectorAll('.sheet-hits__tab').forEach(function (t) {
      var on = t.dataset.idx === idx;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    box.querySelectorAll('.sheet-hits__panel').forEach(function (p) {
      p.hidden = p.dataset.idx !== idx;
    });
  }

  document.addEventListener('click', function (ev) {
    var tab = ev.target.closest('.sheet-hits__tab');
    if (tab) { ev.preventDefault(); ev.stopPropagation(); select(tab); }
  });

  document.addEventListener('keydown', function (ev) {
    var tab = ev.target.closest && ev.target.closest('.sheet-hits__tab');
    if (!tab || (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft')) return;
    var tabs = Array.prototype.slice.call(tab.parentNode.querySelectorAll('.sheet-hits__tab'));
    var i = tabs.indexOf(tab) + (ev.key === 'ArrowRight' ? 1 : -1);
    var next = tabs[(i + tabs.length) % tabs.length];
    next.focus();
    select(next);
    ev.preventDefault();
  });
})();
