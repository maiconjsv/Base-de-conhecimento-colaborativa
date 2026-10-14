/* Modo claro/escuro.
 *
 * O tema inicial e aplicado por um script no <head> do base.html (antes de
 * pintar). Aqui: o botao do menu alterna e salva a escolha; as outras paginas
 * abertas (as abas da moldura sao iframes do mesmo site) recebem o evento
 * "storage" e trocam juntas. Sem escolha salva, acompanha o tema do Windows.
 */
(function () {
  'use strict';

  var KEY = 'kb.tema';
  var media = window.matchMedia ? matchMedia('(prefers-color-scheme: dark)') : null;

  function saved() {
    try { var t = localStorage.getItem(KEY); return t === 'dark' || t === 'light' ? t : null; } catch (e) { return null; }
  }
  function apply(t) {
    document.documentElement.setAttribute('data-theme', t);
    document.documentElement.setAttribute('data-bs-theme', t);
  }
  function current() { return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'; }
  function system() { return media && media.matches ? 'dark' : 'light'; }

  var btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', function () {
      var next = current() === 'dark' ? 'light' : 'dark';
      apply(next);
      try { localStorage.setItem(KEY, next); } catch (e) { /* so nesta pagina */ }
    });
  }

  // outra pagina/aba mudou o tema
  window.addEventListener('storage', function (ev) {
    if (ev.key === KEY) apply(saved() || system());
  });

  // sem escolha salva, acompanha o Windows
  if (media && media.addEventListener) {
    media.addEventListener('change', function () { if (!saved()) apply(system()); });
  }
})();
