/* Tela "Pesquisas": varias pesquisas em abas + cruzamento entre abas.
 *
 * Cada aba de pesquisa consulta /pesquisas/api; a aba de cruzamento manda as
 * pesquisas escolhidas para /pesquisas/cruzar, que combina os resultados no
 * servidor (em todas / em qualquer / so em uma). Cada aba tem uma cor, e as
 * palavras marcadas nos trechos ganham a cor da aba cujo termo elas casam.
 *
 * As abas (tipo, pesquisa, cor) ficam no localStorage deste navegador, so por
 * conveniencia: se nao der para gravar, a tela funciona igual.
 */
(function () {
  'use strict';

  var root = document.getElementById('ws');
  if (!root) return;

  var API = root.dataset.api;
  var CROSS = root.dataset.cross;
  var HITS = root.dataset.hits;
  var STORE_KEY = 'kb.pesquisas.v1';
  var MAX_TABS = 10;
  var N_COLORS = 6;

  var tabsEl = document.getElementById('ws-tabs');
  var panel = document.getElementById('ws-panel');

  // ------------------------------------------------------------------ estado
  var state = load() || { seq: 0, active: null, tabs: [] };
  var cache = {};  // id da aba -> {key, data, items, loading, error}

  function load() {
    try {
      var s = JSON.parse(localStorage.getItem(STORE_KEY));
      return s && Array.isArray(s.tabs) ? s : null;
    } catch (e) { return null; }
  }
  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* sem storage */ }
  }

  function byId(id) {
    for (var i = 0; i < state.tabs.length; i++) if (state.tabs[i].id === id) return state.tabs[i];
    return null;
  }
  function searchTabs() {
    return state.tabs.filter(function (t) { return t.type === 'search' && t.q; });
  }
  function nextColor() {
    var used = state.tabs.filter(function (t) { return t.type === 'search'; })
                         .map(function (t) { return t.color; });
    for (var c = 0; c < N_COLORS; c++) if (used.indexOf(c) < 0) return c;
    return state.seq % N_COLORS;
  }

  function addSearch(q) {
    if (state.tabs.length >= MAX_TABS) { alert('Limite de ' + MAX_TABS + ' abas. Feche alguma para abrir outra.'); return; }
    var tab = { id: 't' + (++state.seq), type: 'search', q: q || '', color: nextColor() };
    state.tabs.push(tab);
    activate(tab.id);
  }
  function addCross() {
    if (state.tabs.length >= MAX_TABS) { alert('Limite de ' + MAX_TABS + ' abas. Feche alguma para abrir outra.'); return; }
    var sources = searchTabs().slice(0, 2).map(function (t) { return t.id; });
    var tab = { id: 't' + (++state.seq), type: 'cross', sources: sources, op: 'and', base: sources[0] || null };
    state.tabs.push(tab);
    activate(tab.id);
  }
  function closeTab(id) {
    var idx = state.tabs.findIndex(function (t) { return t.id === id; });
    if (idx < 0) return;
    state.tabs.splice(idx, 1);
    delete cache[id];
    state.tabs.forEach(function (t) {     // cruzamentos deixam de usar a aba fechada
      if (t.type !== 'cross') return;
      t.sources = t.sources.filter(function (s) { return s !== id; });
      if (t.base === id) t.base = t.sources[0] || null;
      delete cache[t.id];
    });
    if (state.active === id) {
      var next = state.tabs[Math.min(idx, state.tabs.length - 1)];
      state.active = next ? next.id : null;
    }
    if (!state.tabs.length) { addSearch(''); return; }
    save(); render();
  }
  function activate(id) { state.active = id; save(); render(); }

  // ------------------------------------------------------------- utilidades
  function esc(s) {
    var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML;
  }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function fold(s) {
    return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }
  function tokens(q) { return (fold(q).match(/[\p{L}\p{N}]+/gu) || []); }

  // pinta cada <mark> com a cor da aba cujo termo ele casa (mesmo criterio
  // do servidor: inicio da palavra, sem acento, sem maiuscula)
  function colorMarks(container, groups) {
    container.querySelectorAll('mark').forEach(function (m) {
      var word = fold(m.textContent);
      for (var i = 0; i < groups.length; i++) {
        var g = groups[i];
        if (g.tokens.some(function (t) { return word.indexOf(t) === 0; })) {
          m.className = 'mk mk-' + g.color;
          return;
        }
      }
    });
  }
  function groupsFor(tabs) {
    return tabs.map(function (t) { return { color: t.color, tokens: tokens(t.q) }; });
  }

  function crossSources(tab) {
    return tab.sources.map(byId).filter(function (t) { return t && t.type === 'search' && t.q; });
  }
  var OP_SYMBOL = { and: ' ∩ ', or: ' ∪ ', not: ' − ' };
  function crossLabel(tab) {
    var src = crossSources(tab);
    if (src.length < 2) return 'Cruzamento';
    if (tab.op === 'not') {
      var base = byId(tab.base) || src[0];
      var rest = src.filter(function (t) { return t.id !== base.id; });
      return [base].concat(rest).map(function (t) { return t.q; }).join(OP_SYMBOL.not);
    }
    return src.map(function (t) { return t.q; }).join(OP_SYMBOL[tab.op]);
  }

  // ------------------------------------------------------------------ abas
  function renderTabs() {
    tabsEl.innerHTML = state.tabs.map(function (t) {
      var c = cache[t.id];
      var count = c && c.data && !c.loading ? '<span class="ws-tab__n">' + c.data.total + '</span>' : '';
      var label, dot;
      if (t.type === 'search') {
        label = t.q || 'Nova pesquisa';
        dot = '<span class="ws-dot ws-dot--' + t.color + '"></span>';
      } else {
        label = crossLabel(t);
        dot = '<span class="ws-tab__cross" aria-hidden="true">⋂</span>';
      }
      var active = t.id === state.active;
      return '<div class="ws-tab' + (active ? ' is-active' : '') + (t.type === 'cross' ? ' ws-tab--cross' : '') + '">'
        + '<button type="button" class="ws-tab__main" role="tab" aria-selected="' + active + '" data-tab="' + t.id + '"'
        + ' title="' + esc(label) + '">' + dot + '<span class="ws-tab__label">' + esc(label) + '</span>' + count + '</button>'
        + '<button type="button" class="ws-tab__close" data-close="' + t.id + '" aria-label="Fechar aba ' + esc(label) + '">×</button>'
        + '</div>';
    }).join('');
  }

  tabsEl.addEventListener('click', function (ev) {
    var close = ev.target.closest('[data-close]');
    if (close) { closeTab(close.dataset.close); return; }
    var tab = ev.target.closest('[data-tab]');
    if (tab) activate(tab.dataset.tab);
  });
  tabsEl.addEventListener('auxclick', function (ev) {   // clique do meio fecha, como no navegador
    var tab = ev.target.closest('[data-tab]');
    if (tab && ev.button === 1) closeTab(tab.dataset.tab);
  });
  document.getElementById('ws-new').addEventListener('click', function () { addSearch(''); });
  document.getElementById('ws-new-cross').addEventListener('click', addCross);

  // ----------------------------------------------------------------- painel
  function render() {
    renderTabs();
    var tab = byId(state.active);
    if (!tab) { panel.innerHTML = ''; return; }
    panel.dataset.tab = tab.id;
    if (tab.type === 'search') renderSearch(tab); else renderCross(tab);
  }

  // ----- aba de pesquisa
  function renderSearch(tab) {
    panel.innerHTML =
      '<form class="ws-form" data-role="search-form">'
      + '<span class="ws-dot ws-dot--' + tab.color + ' ws-dot--lg"></span>'
      + '<input class="form-control" name="q" type="search" placeholder="Palavras-chave desta aba…" value="' + esc(tab.q) + '">'
      + '<button class="btn btn-primary px-4" type="submit">Buscar</button>'
      + '</form>'
      + '<div class="ws-results" data-role="results"></div>';
    var input = panel.querySelector('input');
    if (!tab.q) input.focus();
    if (tab.q) fetchSearch(tab, 1); else showHint();

    function showHint() {
      panel.querySelector('[data-role=results]').innerHTML =
        '<p class="text-muted mb-0">Digite o que procura. Cada aba guarda uma pesquisa; abra outras com '
        + '<strong>+ Pesquisa</strong> e compare ou cruze os resultados.</p>';
    }
  }

  function fetchSearch(tab, page) {
    var key = tab.q;
    var c = cache[tab.id];
    if (page === 1 && c && c.key === key && c.data) { paintSearch(tab); return; }
    if (page === 1) cache[tab.id] = c = { key: key, items: [], data: null, loading: true };
    c.loading = true;
    paintSearch(tab);
    fetch(API + '?q=' + encodeURIComponent(key) + '&page=' + page)
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (data) {
        if (cache[tab.id] !== c) return;        // aba mudou de pesquisa nesse meio tempo
        c.data = data; c.items = c.items.concat(data.items); c.loading = false; c.error = false;
        renderTabs();
        if (state.active === tab.id) paintSearch(tab);
      })
      .catch(function () {
        c.loading = false; c.error = true;
        if (state.active === tab.id) paintSearch(tab);
      });
  }

  function paintSearch(tab) {
    var box = panel.querySelector('[data-role=results]');
    var c = cache[tab.id];
    if (!box || !c) return;
    if (c.error) { box.innerHTML = '<p class="text-danger">Não foi possível pesquisar. Tente de novo.</p>'; return; }
    if (!c.data) { box.innerHTML = '<p class="text-muted">Pesquisando…</p>'; return; }
    var d = c.data;
    var html = '<p class="ws-summary">' + (d.total
      ? plural(d.total, 'documento', 'documentos') + ' para <strong>' + esc(d.query) + '</strong>'
      : 'Nada encontrado para <strong>' + esc(d.query) + '</strong>. Tente outras palavras.') + '</p>';
    html += c.items.map(function (it) { return resultHtml(it, tab.q); }).join('');
    if (d.page < d.pages) {
      html += '<button type="button" class="btn btn-sm btn-outline-secondary" data-more="1"'
            + (c.loading ? ' disabled' : '') + '>' + (c.loading ? 'Carregando…' : 'Mostrar mais') + '</button>';
    }
    box.innerHTML = html;
    colorMarks(box, groupsFor([tab]));
  }

  // ----- aba de cruzamento
  function renderCross(tab) {
    var all = searchTabs();
    if (all.length < 2) {
      panel.innerHTML = '<div class="ws-empty"><p class="mb-2">Para cruzar, abra ao menos <strong>duas abas de pesquisa</strong> '
        + 'com palavras-chave. Exemplo: uma aba com <em>vpn</em> e outra com <em>senha</em>.</p>'
        + '<button type="button" class="btn btn-sm btn-primary" data-role="new-search">+ Pesquisa</button></div>';
      return;
    }
    var chosen = crossSources(tab);
    var chips = all.map(function (t) {
      var on = tab.sources.indexOf(t.id) >= 0;
      return '<label class="ws-chip' + (on ? ' is-on' : '') + '">'
        + '<input type="checkbox" data-source="' + t.id + '"' + (on ? ' checked' : '') + '>'
        + '<span class="ws-dot ws-dot--' + t.color + '"></span>' + esc(t.q) + '</label>';
    }).join('');
    var baseOptions = chosen.map(function (t) {
      return '<option value="' + t.id + '"' + (t.id === tab.base ? ' selected' : '') + '>' + esc(t.q) + '</option>';
    }).join('');
    function op(value, label, help) {
      return '<label class="ws-op' + (tab.op === value ? ' is-on' : '') + '" title="' + esc(help) + '">'
        + '<input type="radio" name="op" value="' + value + '"' + (tab.op === value ? ' checked' : '') + '>' + label + '</label>';
    }
    panel.innerHTML =
      '<div class="ws-cross">'
      + '<div class="ws-cross__row"><span class="ws-cross__label">Cruzar</span><div class="ws-chips">' + chips + '</div></div>'
      + '<div class="ws-cross__row"><span class="ws-cross__label">Mostrar</span><div class="ws-ops">'
      + op('and', 'Em todas', 'Documentos que aparecem em todas as pesquisas marcadas')
      + op('or', 'Em qualquer uma', 'Documentos que aparecem em pelo menos uma; os que estão em mais pesquisas vêm primeiro')
      + op('not', 'Só em…', 'Documentos de uma pesquisa que não aparecem nas outras')
      + (tab.op === 'not' && chosen.length ? '<select class="form-select form-select-sm ws-base" data-role="base">' + baseOptions + '</select>'
          + '<span class="small text-muted">e em nenhuma outra</span>' : '')
      + '</div></div>'
      + '<p class="ws-sentence">' + crossSentence(tab, chosen) + '</p>'
      + '</div>'
      + '<div class="ws-results" data-role="results"></div>';
    if (chosen.length >= 2) fetchCross(tab, 1);
    else panel.querySelector('[data-role=results]').innerHTML =
      '<p class="text-muted mb-0">Marque ao menos duas pesquisas acima.</p>';
  }

  function crossSentence(tab, chosen) {
    if (chosen.length < 2) return '';
    function q(t) { return '<span class="ws-q ws-q--' + t.color + '">' + esc(t.q) + '</span>'; }
    if (tab.op === 'and') return 'Documentos que citam ' + chosen.map(q).join(' <strong>e</strong> ') + '.';
    if (tab.op === 'or') return 'Documentos que citam ' + chosen.map(q).join(' <strong>ou</strong> ')
      + '. Os que aparecem em mais pesquisas vêm primeiro.';
    var base = byId(tab.base) || chosen[0];
    var rest = chosen.filter(function (t) { return t.id !== base.id; });
    return 'Documentos que citam ' + q(base) + ' mas <strong>não</strong> ' + rest.map(q).join(' nem ') + '.';
  }

  function crossKey(tab, chosen) {
    return tab.op + '|' + (tab.op === 'not' ? tab.base : '') + '|' + chosen.map(function (t) { return t.id + ':' + t.q; }).join('|');
  }

  function fetchCross(tab, page) {
    var chosen = crossSources(tab);
    var key = crossKey(tab, chosen);
    var c = cache[tab.id];
    if (page === 1 && c && c.key === key && c.data) { paintCross(tab); return; }
    if (page === 1) cache[tab.id] = c = { key: key, items: [], data: null, loading: true };
    c.loading = true;
    paintCross(tab);
    var base = Math.max(0, chosen.findIndex(function (t) { return t.id === tab.base; }));
    var qs = chosen.map(function (t) { return 'q=' + encodeURIComponent(t.q); }).join('&')
           + '&op=' + tab.op + '&base=' + base + '&page=' + page;
    fetch(CROSS + '?' + qs)
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (data) {
        if (cache[tab.id] !== c) return;
        c.data = data; c.items = c.items.concat(data.items); c.loading = false; c.error = false;
        c.sources = chosen;
        renderTabs();
        if (state.active === tab.id) paintCross(tab);
      })
      .catch(function () {
        c.loading = false; c.error = true;
        if (state.active === tab.id) paintCross(tab);
      });
  }

  function paintCross(tab) {
    var box = panel.querySelector('[data-role=results]');
    var c = cache[tab.id];
    if (!box || !c) return;
    if (c.error) { box.innerHTML = '<p class="text-danger">Não foi possível cruzar. Tente de novo.</p>'; return; }
    if (!c.data) { box.innerHTML = '<p class="text-muted">Cruzando…</p>'; return; }
    var d = c.data, src = c.sources;
    var html = '<p class="ws-summary">' + (d.total
      ? plural(d.total, 'documento', 'documentos') + ' no cruzamento'
      : 'Nenhum documento atende a esse cruzamento.') + '</p>';
    var allQ = src.map(function (t) { return t.q; }).join(' ');
    html += c.items.map(function (it) {
      var badges = src.map(function (t, i) {
        return it.matches[i]
          ? '<span class="ws-q ws-q--' + t.color + '" title="' + plural(it.hits[i], 'ocorrência', 'ocorrências') + '">'
            + esc(t.q) + ' <b>' + it.hits[i] + '</b></span>'
          : '<span class="ws-q ws-q--off" title="Não aparece neste documento">' + esc(t.q) + '</span>';
      }).join('');
      return resultHtml(it, allQ, badges);
    }).join('');
    if (d.page < d.pages) {
      html += '<button type="button" class="btn btn-sm btn-outline-secondary" data-more="1"'
            + (c.loading ? ' disabled' : '') + '>' + (c.loading ? 'Carregando…' : 'Mostrar mais') + '</button>';
    }
    box.innerHTML = html;
    colorMarks(box, groupsFor(src));
  }

  // ----- resultado (comum as duas abas): cabecalho + ocorrencias sob demanda
  function resultHtml(it, hitsQuery, badges) {
    var tags = (it.tags || []).map(function (t) { return '<span class="badge text-bg-secondary">' + esc(t) + '</span>'; }).join('');
    var count = it.hit_count ? '<span class="search-result__count">' + plural(it.hit_count, 'ocorrência', 'ocorrências') + '</span>' : '';
    return '<div class="search-result card mb-2" data-doc="' + it.doc_id + '" data-q="' + esc(hitsQuery) + '">'
      + '<button type="button" class="search-result__head" aria-expanded="false">'
      + '<span class="search-result__caret" aria-hidden="true"></span>'
      + '<span class="search-result__info">'
      + '<span class="doc-item__title">' + esc(it.title) + '</span>'
      + '<span class="doc-item__meta">' + esc(it.filename) + ' · ' + esc(it.date) + ' ' + tags + '</span>'
      + (badges ? '<span class="ws-badges">' + badges + '</span>' : '')
      + (it.snippet ? '<span class="search-snippet">' + it.snippet + '</span>' : '')   // ja vem escapado + <mark>
      + '</span>' + count + '</button>'
      + '<div class="search-result__body" hidden>'
      + '<div class="search-result__hits" data-loaded="0"><span class="text-muted small">Carregando ocorrências…</span></div>'
      + '<div class="search-result__actions">'
      + '<a class="btn btn-sm btn-primary" href="' + esc(it.url) + '">Abrir documento</a>'
      + '</div></div></div>';
  }

  function hitsHtml(data) {
    if (!data.count) {
      return '<p class="text-muted small mb-0">' + (data.extraction_ok === false
        ? 'Este arquivo não teve o texto extraído, então não dá para localizar os termos dentro dele.'
        : 'Os termos casaram pelo índice, mas não aparecem como palavra inteira no texto.') + '</p>';
    }
    var html = '';
    if (data.tables_html) {
      html += '<div class="hit-group"><div class="hit-group__label">Linhas da planilha</div>' + data.tables_html + '</div>';
    }
    data.groups.forEach(function (g) {
      html += '<div class="hit-group"><div class="hit-group__label">' + esc(g.label);
      if (g.total > g.shown) html += ' <span class="text-muted">(' + g.shown + ' de ' + g.total + ')</span>';
      html += '</div>';
      g.snippets.forEach(function (s) { html += '<p class="hit-line">' + s + '</p>'; });
      html += '</div>';
    });
    return html;
  }

  function currentGroups() {
    var tab = byId(state.active);
    if (!tab) return [];
    if (tab.type === 'search') return groupsFor([tab]);
    var c = cache[tab.id];
    return groupsFor(c && c.sources ? c.sources : crossSources(tab));
  }

  // ----------------------------------------------------- eventos do painel
  panel.addEventListener('submit', function (ev) {
    var form = ev.target.closest('[data-role=search-form]');
    if (!form) return;
    ev.preventDefault();
    var tab = byId(state.active);
    var q = form.q.value.trim();
    if (!tab || !q) return;
    tab.q = q;
    // cruzamentos que usam esta aba precisam refazer a consulta
    state.tabs.forEach(function (t) { if (t.type === 'cross' && t.sources.indexOf(tab.id) >= 0) delete cache[t.id]; });
    save();
    renderTabs();
    fetchSearch(tab, 1);
  });

  panel.addEventListener('change', function (ev) {
    var tab = byId(state.active);
    if (!tab || tab.type !== 'cross') return;
    var t = ev.target;
    if (t.dataset.source) {
      var id = t.dataset.source;
      if (t.checked && tab.sources.indexOf(id) < 0) tab.sources.push(id);
      if (!t.checked) tab.sources = tab.sources.filter(function (s) { return s !== id; });
      if (tab.sources.indexOf(tab.base) < 0) tab.base = tab.sources[0] || null;
    } else if (t.name === 'op') {
      tab.op = t.value;
      if (!tab.base) tab.base = tab.sources[0] || null;
    } else if (t.dataset.role === 'base') {
      tab.base = t.value;
    } else {
      return;
    }
    save();
    render();
  });

  panel.addEventListener('click', function (ev) {
    if (ev.target.closest('[data-role=new-search]')) { addSearch(''); return; }

    var more = ev.target.closest('[data-more]');
    if (more) {
      var tab = byId(state.active), c = cache[tab.id];
      if (!c || !c.data || c.loading) return;
      if (tab.type === 'search') fetchSearch(tab, c.data.page + 1); else fetchCross(tab, c.data.page + 1);
      return;
    }

    var head = ev.target.closest('.search-result__head');
    if (!head) return;
    var card = head.closest('.search-result');
    var body = card.querySelector('.search-result__body');
    var box = card.querySelector('.search-result__hits');
    var open = head.getAttribute('aria-expanded') === 'true';
    head.setAttribute('aria-expanded', String(!open));
    body.hidden = open;
    if (open || box.dataset.loaded === '1') return;
    box.dataset.loaded = '1';
    var groups = currentGroups();
    fetch(HITS + encodeURIComponent(card.dataset.doc) + '?q=' + encodeURIComponent(card.dataset.q))
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (data) { box.innerHTML = hitsHtml(data); colorMarks(box, groups); })
      .catch(function () {
        box.dataset.loaded = '0';
        box.innerHTML = '<span class="text-danger small">Não foi possível carregar as ocorrências. Tente de novo.</span>';
      });
  });

  // ------------------------------------------------------------- inicio
  // ?q=… (vindo da busca) abre essa pesquisa numa aba, reaproveitando se ja existir
  var add = (root.dataset.add || '').trim();
  if (add) {
    var existing = state.tabs.filter(function (t) { return t.type === 'search' && t.q === add; })[0];
    if (existing) state.active = existing.id;
    else if (state.tabs.length < MAX_TABS) {
      var blank = state.tabs.filter(function (t) { return t.type === 'search' && !t.q; })[0];
      if (blank) { blank.q = add; state.active = blank.id; }
      else { state.tabs.push({ id: 't' + (++state.seq), type: 'search', q: add, color: nextColor() }); state.active = 't' + state.seq; }
    }
    try { history.replaceState(null, '', location.pathname); } catch (e) { /* ok */ }
  }
  if (!state.tabs.length) addSearch('');
  else { if (!byId(state.active)) state.active = state.tabs[0].id; save(); render(); }
})();
