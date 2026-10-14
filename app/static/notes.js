/* Bloco de notas (painel lateral da moldura de abas).
 *
 * Junta RECORTES trazidos das abas (texto + fonte, para reabrir de onde veio) e
 * um texto livre de ANOTACOES, para cruzar dados de abas diferentes. Salvo no
 * servidor (rotas /notas/api, app/notes.py) automaticamente enquanto se digita.
 *
 * As paginas dentro das abas chamam window.top.kbNotes.addClip(...) quando a
 * pessoa clica em "+ Notas" sobre um texto selecionado (static/in_tab.js).
 */
(function () {
  'use strict';

  var panel = document.getElementById('notes-panel');
  if (!panel) return;
  var API = panel.dataset.api;
  var OPEN_KEY = 'kb.notas.aberto', NOTE_KEY = 'kb.notas.atual';

  var sel = document.getElementById('notes-select');
  var clipsEl = document.getElementById('notes-clips');
  var bodyEl = document.getElementById('notes-body');
  var savedEl = document.getElementById('notes-saved');
  var toggleBtn = document.getElementById('notes-toggle');
  var countEl = document.getElementById('notes-count');

  var notes = [];          // resumo: [{id, title, clips}]
  var note = null;         // nota aberta: {id, title, body, clips: [...], export_url}
  var bodyTimer = null;
  var pending = [];        // recortes que chegaram antes de a nota carregar

  // ------------------------------------------------------------ servidor
  function api(method, path, data) {
    var opts = { method: method, headers: { 'X-KB-Notas': '1' } };
    if (data !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(data);
    }
    return fetch(API + (path || ''), opts).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }
  function store(key, val) { try { localStorage.setItem(key, val); } catch (e) { /* ok */ } }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }

  function setSaved(text) { savedEl.textContent = text; }

  function save(fields) {
    if (!note) return Promise.resolve();
    setSaved('Salvando…');
    return api('PUT', '/' + note.id, fields).then(function (s) {
      setSaved('Salvo');
      var item = notes.filter(function (n) { return n.id === note.id; })[0];
      if (item) { item.title = s.title; item.clips = s.clips; }
      renderSelect();
    }).catch(function () { setSaved('Não salvou — tente de novo'); });
  }

  // ------------------------------------------------------------ desenho
  function esc(s) {
    var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML;
  }

  function renderSelect() {
    sel.innerHTML = notes.map(function (n) {
      return '<option value="' + n.id + '"' + (note && n.id === note.id ? ' selected' : '') + '>'
        + esc(n.title) + (n.clips ? ' (' + n.clips + ')' : '') + '</option>';
    }).join('');
    var total = note ? note.clips.length : 0;
    countEl.textContent = total;
    countEl.hidden = !total;
  }

  function renderClips() {
    document.getElementById('notes-clip-count').textContent = note.clips.length ? '(' + note.clips.length + ')' : '';
    if (!note.clips.length) {
      clipsEl.innerHTML = '<p class="notes-empty">Selecione um texto em qualquer aba e clique em '
        + '<b>+ Notas</b> (ou Alt+S). Ele vem para cá com a fonte, para você juntar com dados de outras abas.</p>';
      return;
    }
    clipsEl.innerHTML = note.clips.map(function (c, i) {
      return '<div class="notes-clip" data-i="' + i + '">'
        + '<button type="button" class="notes-clip__del" data-del="' + i + '" title="Tirar este recorte">×</button>'
        + '<div class="notes-clip__text">' + esc(c.text) + '</div>'
        + '<div class="notes-clip__src">'
        + (c.url ? '<a href="#" data-open="' + i + '" title="Abrir a fonte numa aba nova">' + esc(c.title || c.url) + '</a>'
                 : esc(c.title || ''))
        + (c.at ? ' · ' + esc(c.at) : '') + '</div></div>';
    }).join('');
  }

  function renderNote() {
    bodyEl.value = note.body || '';
    document.getElementById('notes-export').href = note.export_url;
    renderSelect();
    renderClips();
    setSaved('');
  }

  // ------------------------------------------------------------ carregar
  function openNote(id) {
    return api('GET', '/' + id).then(function (n) {
      note = n;
      store(NOTE_KEY, String(n.id));
      renderNote();
      var queued = pending.splice(0);
      queued.forEach(addClip);
    });
  }

  function init() {
    return api('GET').then(function (list) {
      notes = list;
      var want = parseInt(load(NOTE_KEY), 10);
      var first = notes.filter(function (n) { return n.id === want; })[0] || notes[0];
      return openNote(first.id);
    }).catch(function () { setSaved('Não foi possível carregar as notas.'); });
  }

  // ------------------------------------------------------------ painel
  function setOpen(open) {
    panel.hidden = !open;
    toggleBtn.setAttribute('aria-pressed', String(open));
    toggleBtn.classList.toggle('active', open);
    store(OPEN_KEY, open ? '1' : '0');
  }
  function toggle(force) { setOpen(typeof force === 'boolean' ? force : panel.hidden); }

  function addClip(clip) {
    if (!clip || !clip.text || !clip.text.trim()) return;
    if (!note) { pending.push(clip); setOpen(true); return; }
    var now = new Date();
    note.clips.push({
      text: clip.text.trim().slice(0, 5000),
      title: (clip.title || '').slice(0, 200),
      url: clip.url || '',
      at: ('0' + now.getDate()).slice(-2) + '/' + ('0' + (now.getMonth() + 1)).slice(-2) + ' '
        + ('0' + now.getHours()).slice(-2) + ':' + ('0' + now.getMinutes()).slice(-2)
    });
    setOpen(true);
    renderClips();
    renderSelect();
    var last = clipsEl.lastElementChild;
    if (last) { last.classList.add('is-new'); last.scrollIntoView({ block: 'nearest' }); }
    save({ clips: note.clips });
  }

  // ------------------------------------------------------------ eventos
  toggleBtn.addEventListener('click', function () { toggle(); });
  document.getElementById('notes-close').addEventListener('click', function () { setOpen(false); });

  bodyEl.addEventListener('input', function () {
    if (!note) return;
    note.body = bodyEl.value;
    setSaved('…');
    clearTimeout(bodyTimer);
    bodyTimer = setTimeout(function () { save({ body: note.body }); }, 700);
  });

  clipsEl.addEventListener('click', function (ev) {
    var del = ev.target.closest('[data-del]');
    if (del) {
      note.clips.splice(parseInt(del.dataset.del, 10), 1);
      renderClips();
      renderSelect();
      save({ clips: note.clips });
      return;
    }
    var openLink = ev.target.closest('[data-open]');
    if (openLink) {
      ev.preventDefault();
      var c = note.clips[parseInt(openLink.dataset.open, 10)];
      if (c && c.url && window.kbTabs) window.kbTabs.open(c.url, { title: c.title });
    }
  });

  sel.addEventListener('change', function () { openNote(parseInt(sel.value, 10)); });

  document.getElementById('notes-new').addEventListener('click', function () {
    var title = prompt('Nome da nova nota:', 'Nova nota');
    if (title === null) return;
    api('POST', '', { title: title }).then(function (n) {
      notes.unshift({ id: n.id, title: n.title, clips: 0 });
      note = n;
      store(NOTE_KEY, String(n.id));
      renderNote();
      bodyEl.focus();
    });
  });

  document.getElementById('notes-rename').addEventListener('click', function () {
    if (!note) return;
    var title = prompt('Novo nome da nota:', note.title);
    if (title === null || !title.trim()) return;
    note.title = title.trim();
    save({ title: note.title });
  });

  document.getElementById('notes-delete').addEventListener('click', function () {
    if (!note || !confirm('Apagar a nota "' + note.title + '" com todos os recortes?')) return;
    api('DELETE', '/' + note.id).then(function () {
      note = null;
      return init();
    });
  });

  document.getElementById('notes-copy').addEventListener('click', function () {
    if (!note) return;
    var parts = note.clips.map(function (c, i) {
      return '[' + (i + 1) + '] ' + c.text + (c.title ? '\n    fonte: ' + c.title : '');
    });
    if (note.body.trim()) parts.push('\n' + note.body.trim());
    var text = note.title + '\n\n' + parts.join('\n');
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject())
      .then(function () { setSaved('Copiado'); })
      .catch(function () { bodyEl.select(); document.execCommand('copy'); setSaved('Copiado'); });
  });

  document.addEventListener('keydown', function (ev) {
    if (ev.altKey && (ev.key === 'n' || ev.key === 'N')) { ev.preventDefault(); toggle(); }
  });

  // API para as paginas dentro das abas (in_tab.js)
  window.kbNotes = { addClip: addClip, toggle: toggle };

  if (load(OPEN_KEY) === '1') setOpen(true);
  init();
})();
