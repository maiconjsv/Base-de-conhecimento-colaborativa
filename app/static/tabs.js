/* Moldura com abas de navegador (pagina "/").
 *
 * Cada aba e um <iframe> com uma pagina do sistema, entao cada pesquisa,
 * documento ou planilha aberta e totalmente independente (filtro, rolagem,
 * resultados expandidos). As abas escondidas continuam vivas.
 *
 * - "+" abre uma aba nova na lista de documentos recentes.
 * - A busca do menu abre o resultado numa ABA NOVA; os botoes do menu
 *   (Pesquisas, Perguntar, Enviar) navegam na aba atual. Ctrl+clique ou clique
 *   do meio abrem em outra aba (aqui e dentro das paginas, via in_tab.js).
 * - Titulo e endereco de cada aba acompanham a pagina aberta; a lista de abas
 *   fica no localStorage e volta ao reabrir o programa.
 */
(function () {
  'use strict';

  var tabsEl = document.getElementById('tabs');
  var frames = document.getElementById('frames');
  var HOME = frames.dataset.home;
  var SEARCH = frames.dataset.search;
  var SHELL = frames.dataset.shell;
  var STORE_KEY = 'kb.abas.v1';
  var MAX_TABS = 20;

  var state = { seq: 0, active: null, tabs: [] };   // tabs: [{id, url, title}]
  var loading = {};                                  // id -> true enquanto carrega

  // ------------------------------------------------------------ persistencia
  function save() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({
        seq: state.seq, active: state.active,
        tabs: state.tabs.map(function (t) { return { id: t.id, url: t.url, title: t.title }; })
      }));
    } catch (e) { /* sem storage: as abas so nao voltam ao reabrir */ }
  }
  function restore() {
    try {
      var s = JSON.parse(localStorage.getItem(STORE_KEY));
      if (s && Array.isArray(s.tabs)) return s;
    } catch (e) { /* ignora */ }
    return null;
  }

  // so caminhos do proprio sistema; nunca a propria moldura
  function safeUrl(url) {
    if (typeof url !== 'string' || url.charAt(0) !== '/' || url.charAt(1) === '/') return HOME;
    var path = url.split(/[?#]/)[0];
    return path === SHELL ? HOME : url;
  }

  // ------------------------------------------------------------ abas
  function byId(id) {
    for (var i = 0; i < state.tabs.length; i++) if (state.tabs[i].id === id) return state.tabs[i];
    return null;
  }
  function frameOf(id) { return frames.querySelector('iframe[data-tab="' + id + '"]'); }

  function makeFrame(tab) {
    var f = document.createElement('iframe');
    f.className = 'tabframe';
    f.dataset.tab = tab.id;
    f.title = tab.title || 'Aba';
    f.addEventListener('load', function () { onFrameLoad(tab.id, f); });
    loading[tab.id] = true;
    f.src = tab.url;
    frames.appendChild(f);
    return f;
  }

  function onFrameLoad(id, f) {
    var tab = byId(id);
    if (!tab) return;
    delete loading[id];
    try {
      var loc = f.contentWindow.location;
      tab.url = safeUrl(loc.pathname + loc.search + loc.hash);
      tab.title = (f.contentDocument.title || '').replace(/\s*·\s*Semantix\s*$/, '') || tab.title;
    } catch (e) { /* pagina de outro dominio: mantem o que tinha */ }
    f.title = tab.title || 'Aba';
    save();
    render();
  }

  function open(url, opts) {
    opts = opts || {};
    if (state.tabs.length >= MAX_TABS) {
      alert('Limite de ' + MAX_TABS + ' abas. Feche alguma para abrir outra.');
      return null;
    }
    var tab = { id: 'a' + (++state.seq), url: safeUrl(url || HOME), title: opts.title || 'Carregando…' };
    // como no navegador: a aba nova entra logo depois da atual
    var at = state.tabs.findIndex(function (t) { return t.id === state.active; });
    state.tabs.splice(at < 0 ? state.tabs.length : at + 1, 0, tab);
    makeFrame(tab);
    if (!opts.background || !state.active) state.active = tab.id;
    save();
    render();
    return tab;
  }

  function navigate(url) {
    var tab = byId(state.active);
    if (!tab) { open(url); return; }
    tab.url = safeUrl(url);
    loading[tab.id] = true;
    frameOf(tab.id).src = tab.url;
    render();
  }

  function activate(id) {
    if (!byId(id)) return;
    state.active = id;
    save();
    render();
    var f = frameOf(id);
    try { f.contentWindow.focus(); } catch (e) { /* ok */ }
  }

  function close(id) {
    var idx = state.tabs.findIndex(function (t) { return t.id === id; });
    if (idx < 0) return;
    state.tabs.splice(idx, 1);
    var f = frameOf(id);
    if (f) f.remove();
    delete loading[id];
    if (state.active === id) {
      var next = state.tabs[Math.min(idx, state.tabs.length - 1)];
      state.active = next ? next.id : null;
    }
    if (!state.tabs.length) { open(HOME); return; }
    save();
    render();
  }

  function render() {
    tabsEl.innerHTML = state.tabs.map(function (t) {
      var on = t.id === state.active;
      var title = t.title || 'Aba';
      var icon = loading[t.id]
        ? '<span class="btab__spin" aria-hidden="true"></span>'
        : '<span class="btab__icon" aria-hidden="true"></span>';
      return '<div class="btab' + (on ? ' is-active' : '') + '">'
        + '<button type="button" class="btab__main" role="tab" aria-selected="' + on + '" data-tab="' + t.id + '"'
        + ' title="' + esc(title) + '">' + icon + '<span class="btab__title">' + esc(title) + '</span></button>'
        + '<button type="button" class="btab__close" data-close="' + t.id + '" aria-label="Fechar aba ' + esc(title) + '">×</button>'
        + '</div>';
    }).join('');
    frames.querySelectorAll('iframe').forEach(function (f) {
      f.classList.toggle('is-active', f.dataset.tab === state.active);
    });
    var act = byId(state.active);
    document.title = (act && act.title ? act.title + ' · ' : '') + 'Base de Conhecimento · Semantix';
  }

  function esc(s) {
    var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML;
  }

  // ------------------------------------------------------------ eventos
  tabsEl.addEventListener('click', function (ev) {
    var c = ev.target.closest('[data-close]');
    if (c) { close(c.dataset.close); return; }
    var t = ev.target.closest('[data-tab]');
    if (t) activate(t.dataset.tab);
  });
  tabsEl.addEventListener('auxclick', function (ev) {      // clique do meio fecha
    var t = ev.target.closest('[data-tab]');
    if (t && ev.button === 1) { ev.preventDefault(); close(t.dataset.tab); }
  });
  tabsEl.addEventListener('mousedown', function (ev) {     // evita o "autoscroll" do botao do meio
    if (ev.button === 1) ev.preventDefault();
  });
  document.getElementById('tab-add').addEventListener('click', function () { open(HOME); });

  // menu do topo: busca abre aba nova; botoes navegam na aba atual
  var navSearch = document.querySelector('.site-nav [data-newtab-form]');
  if (navSearch) {
    navSearch.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var q = navSearch.q.value.trim();
      if (!q) return;
      open(SEARCH + '?q=' + encodeURIComponent(q), { title: q });
      navSearch.q.value = '';
    });
  }
  document.querySelectorAll('.site-nav a[href]').forEach(function (a) {
    var url = new URL(a.href, location.href);
    if (url.origin !== location.origin || /\/logout$/.test(url.pathname)) return;   // "Sair" sai de verdade
    var target = url.pathname === SHELL ? HOME : url.pathname + url.search;
    function go(ev, newTab) {
      ev.preventDefault();
      if (newTab) open(target, { background: true }); else navigate(target);
    }
    a.addEventListener('click', function (ev) { go(ev, ev.ctrlKey || ev.metaKey); });
    a.addEventListener('auxclick', function (ev) { if (ev.button === 1) go(ev, true); });
  });

  // API para as paginas dentro das abas (in_tab.js)
  window.kbTabs = {
    open: open,
    navigate: navigate,
    loading: function (win) {
      frames.querySelectorAll('iframe').forEach(function (f) {
        if (f.contentWindow !== win) return;
        var id = f.dataset.tab;
        loading[id] = true;
        render();
        // download (ex.: "Baixar") dispara a saida da pagina mas nao troca de
        // pagina, entao nao ha "load": confere depois e limpa o indicador
        setTimeout(function () {
          try {
            if (loading[id] && f.contentWindow === win && f.contentDocument.readyState === 'complete') {
              delete loading[id];
              render();
            }
          } catch (e) { /* trocou de pagina: o load cuida */ }
        }, 2500);
      });
    }
  };

  // ------------------------------------------------------------ inicio
  var saved = restore();
  if (saved && saved.tabs.length) {
    state.seq = saved.seq || 0;
    state.tabs = saved.tabs.slice(0, MAX_TABS).map(function (t) {
      return { id: t.id, url: safeUrl(t.url), title: t.title || 'Aba' };
    });
    state.active = byId(saved.active) ? saved.active : state.tabs[0].id;
    state.tabs.forEach(makeFrame);
    render();
  } else {
    open(HOME);
  }
  // /?abrir=/caminho abre esse caminho numa aba (ex.: vindo de uma pagina fora da moldura)
  var abrir = new URLSearchParams(location.search).get('abrir');
  if (abrir) {
    open(abrir);
    try { history.replaceState(null, '', SHELL); } catch (e) { /* ok */ }
  }
})();
