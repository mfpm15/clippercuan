/* ClipperCuan Studio — UI lokal. Vanilla JS. */
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const view = $('#view');
let INFO = null, SETTINGS = null, pollT = null;

/* ---------------- util ---------------- */
async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.body && !(o.body instanceof FormData)) { o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(o.body); }
  const r = await fetch(path, o);
  const isJson = (r.headers.get('content-type') || '').includes('json');
  const data = isJson ? await r.json() : await r.text();
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`);
  return data;
}
let toastT;
function toast(msg, bad = false) { const t = $('#toast'); t.textContent = msg; t.classList.toggle('bad', bad); t.classList.add('show'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), bad ? 6000 : 2800); }
const fmt = s => { s = Math.max(0, +s || 0); return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`; };
const tpl = id => document.importNode($('#' + id).content, true);
const store = { get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} } };
const merge = (a, b) => { const o = structuredClone(a); for (const [k, v] of Object.entries(b || {})) o[k] = v && typeof v === 'object' && !Array.isArray(v) && o[k] && typeof o[k] === 'object' ? merge(o[k], v) : v; return o; };
function chipGroup(box, val, cb, attr = 'v') { $$('button', box).forEach(b => { b.type = 'button'; b.classList.toggle('on', b.dataset[attr] === val); b.onclick = () => { $$('button', box).forEach(x => x.classList.toggle('on', x === b)); cb(b.dataset[attr]); }; }); }

/* ---------------- router ---------------- */
async function route() {
  clearInterval(pollT);
  const h = location.hash.replace(/^#\/?/, '') || 'new';
  const [page, id] = h.split('/');
  $$('.side nav a').forEach(a => a.classList.toggle('on', a.dataset.nav === page));
  if (!INFO) { INFO = await api('/api/info'); SETTINGS = await api('/api/settings'); $('#sideFoot').textContent = 'Data: ' + INFO.data_dir; }
  if (page === 'p' && id) return pageProject(id);
  if (page === 'history') return pageHistory();
  if (page === 'settings') return pageSettings();
  return pageNew();
}
addEventListener('hashchange', route);

/* ================= PROYEK BARU ================= */
function pageNew() {
  view.replaceChildren(tpl('tpl-new'));
  const cfg = merge(INFO.defaults, store.get('lastSettings', {}));
  let srcMode = 'link', upload = null;

  chipGroup($('#srcTabs'), 'link', m => { srcMode = m; $('#srcLink').hidden = m !== 'link'; $('#srcFile').hidden = m !== 'file'; }, 'src');

  // file upload
  const drop = $('#drop'), fileIn = $('#file');
  const doUpload = f => {
    if (!f) return;
    $('#fileName').textContent = f.name + ' · ' + (f.size / 1048576).toFixed(1) + ' MB';
    const bar = $('#upBar'); bar.hidden = false; upload = null; $('#start').disabled = true;
    const fd = new FormData(); fd.append('file', f);
    const x = new XMLHttpRequest(); x.open('POST', '/api/upload');
    x.upload.onprogress = e => { if (e.lengthComputable) $('i', bar).style.width = (e.loaded / e.total * 100) + '%'; };
    x.onload = () => { $('#start').disabled = false; if (x.status === 200) { upload = JSON.parse(x.responseText); toast('File siap'); } else toast('Upload gagal: ' + x.responseText, true); };
    x.onerror = () => { $('#start').disabled = false; toast('Upload gagal', true); };
    x.send(fd);
  };
  fileIn.onchange = () => doUpload(fileIn.files[0]);
  ['dragenter', 'dragover'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', ev => doUpload(ev.dataTransfer.files[0]));

  // klip
  ['clip_count', 'min_sec', 'max_sec', 'language', 'model'].forEach(k => $('#' + k).value = cfg[k]);
  $('#translate_en').checked = !!cfg.translate_en;
  const llmOn = SETTINGS.llm.enabled && SETTINGS.llm.model_moments;
  $('#llmRow').hidden = !llmOn; $('#llmModel').textContent = SETTINGS.llm.model_moments;
  $('#use_llm').checked = cfg.use_llm !== false;

  // layout
  let layout = cfg.layout;
  const syncLayout = () => { $('#smartRow').hidden = !['portrait', 'square'].includes(layout); $('#splitRow').hidden = layout !== 'split'; };
  chipGroup($('#layouts'), layout, l => { layout = l; syncLayout(); }, 'l'); syncLayout();
  $('#smart_crop').checked = cfg.smart_crop;
  let facePos = store.get('facePos', 'br');
  chipGroup($('#facePos'), facePos, v => facePos = v, 'f');
  $('#faceSize').value = Math.round(cfg.split.face[2] * 100);
  $('#faceRatio').value = Math.round(cfg.split.face_ratio * 100);

  // caption
  const cap = cfg.caption;
  $('#cap_font').innerHTML = INFO.fonts.map(f => `<option>${f}</option>`).join('');
  let capStyle = cap.style;
  const capCard = $('#capCard');
  $('#cap_enabled').checked = cap.enabled; capCard.classList.toggle('off', !cap.enabled);
  $('#cap_enabled').onchange = e => capCard.classList.toggle('off', !e.target.checked);
  $('#cap_font').value = cap.font; $('#cap_position').value = cap.position; $('#cap_color').value = cap.color; $('#cap_highlight').value = cap.highlight;
  $('#cap_wpl').value = cap.words_per_line; $('#cap_size').value = cap.size; $('#cap_upper').checked = cap.uppercase; $('#cap_pop').checked = cap.animation === 'pop';
  const pv = () => {
    const p = $('#capPreview'), hl = $('#cap_highlight').value, col = $('#cap_color').value;
    p.style.textTransform = $('#cap_upper').checked ? 'uppercase' : 'none';
    p.style.fontFamily = $('#cap_font').value.includes('Georgia') ? 'Georgia,serif' : 'inherit';
    $$('.pv-w', p).forEach(w => { const on = w.classList.contains('on'); w.style.color = on ? (capStyle === 'box' ? '#000' : hl) : col; w.style.background = on && capStyle === 'box' ? hl : 'transparent'; w.hidden = capStyle === 'wbw' && !on; });
  };
  chipGroup($('#capStyle'), capStyle, v => { capStyle = v; pv(); });
  ['cap_color', 'cap_highlight', 'cap_upper', 'cap_font'].forEach(k => $('#' + k).addEventListener('input', pv)); pv();

  // judul & watermark
  let ttlPreset = cfg.title.preset, wmPos = cfg.watermark.position, wmImage = '';
  $('#ttl_enabled').checked = cfg.title.enabled; $('#ttl_duration').value = cfg.title.duration;
  chipGroup($('#ttlPreset'), ttlPreset, v => ttlPreset = v);
  $('#wm_enabled').checked = cfg.watermark.enabled; $('#wm_text').value = cfg.watermark.text; $('#wm_opacity').value = Math.round(cfg.watermark.opacity * 100);
  chipGroup($('#wmPos'), wmPos, v => wmPos = v);
  $('#wm_file').onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append('file', f);
    try { const r = await api('/api/upload', { method: 'POST', body: fd }); wmImage = r.path; $('#wm_enabled').checked = true; toast('Logo watermark siap'); } catch (err) { toast(err.message, true); }
  };

  $('#start').onclick = async () => {
    let source = '';
    if (srcMode === 'link') { source = $('#url').value.trim(); if (!/^https?:\/\//i.test(source)) return toast('Tempel link video yang valid (diawali https://)', true); }
    else { if (!upload) return toast('Pilih file video dulu', true); source = upload.id; }
    const min = +$('#min_sec').value, max = +$('#max_sec').value;
    if (min >= max) return toast('Durasi minimum harus lebih kecil dari maksimum', true);
    const fs = +$('#faceSize').value / 100, pos = { tl: [0, 0], tr: [1 - fs, 0], bl: [0, 1 - fs], br: [1 - fs, 1 - fs] }[facePos];
    const settings = {
      clip_count: +$('#clip_count').value, min_sec: min, max_sec: max, language: $('#language').value, model: $('#model').value,
      translate_en: $('#translate_en').checked, use_llm: $('#use_llm').checked, layout, smart_crop: $('#smart_crop').checked,
      split: { face: [pos[0], pos[1], fs, fs], game: [0, 0, 1, 1], face_ratio: +$('#faceRatio').value / 100 },
      caption: { enabled: $('#cap_enabled').checked, style: capStyle, font: $('#cap_font').value, size: +$('#cap_size').value, color: $('#cap_color').value, highlight: $('#cap_highlight').value, uppercase: $('#cap_upper').checked, words_per_line: +$('#cap_wpl').value, position: $('#cap_position').value, animation: $('#cap_pop').checked ? 'pop' : 'none' },
      title: { enabled: $('#ttl_enabled').checked, preset: ttlPreset, duration: +$('#ttl_duration').value, size: cfg.title.size },
      watermark: { enabled: $('#wm_enabled').checked, text: $('#wm_text').value, image: wmImage, position: wmPos, opacity: +$('#wm_opacity').value / 100, size: cfg.watermark.size },
    };
    store.set('lastSettings', { ...settings, watermark: { ...settings.watermark, image: '' } }); store.set('facePos', facePos);
    $('#start').disabled = true;
    try { const p = await api('/api/projects', { method: 'POST', body: { source, settings } }); location.hash = '#/p/' + p.id; }
    catch (e) { toast(e.message, true); $('#start').disabled = false; }
  };
}

/* ================= PROYEK ================= */
async function pageProject(pid) {
  view.replaceChildren(tpl('tpl-project'));
  const cards = new Map();
  $('#pFolder').onclick = () => api(`/api/projects/${pid}/open-folder`, { method: 'POST' }).then(r => toast('Folder: ' + r.path)).catch(e => toast(e.message, true));
  $('#pCancel').onclick = () => api(`/api/projects/${pid}/cancel`, { method: 'POST' }).then(() => toast('Membatalkan…'));
  $('#pRetry').onclick = () => api(`/api/projects/${pid}/retry`, { method: 'POST' }).then(load);
  let P = null;
  $('#pStyleAll').onclick = () => styleDialog(P, load);

  async function load() {
    try { P = await api('/api/projects/' + pid); } catch (e) { view.innerHTML = `<section class="page"><div class="empty">${e.message}</div></section>`; clearInterval(pollT); return; }
    $('#pTitle').textContent = P.title; $('#pSource').textContent = P.source.includes('/uploads/') ? 'File unggahan' : P.source;
    const st = $('#pStatus'); st.className = 'card status ' + P.status;
    $('#pMsg').textContent = P.message; $('#pPct').textContent = Math.round(P.progress * 100) + '%'; $('#pBar').style.width = P.progress * 100 + '%';
    $('#pCancel').hidden = !['queued', 'running'].includes(P.status);
    $('#pRetry').hidden = !['error', 'cancelled'].includes(P.status);
    $('#pWarn').hidden = !P.llm_warning; $('#pWarn').textContent = P.llm_warning || '';
    $('#pErr').hidden = !P.error; if (P.error) $('#pErr pre').textContent = P.error;
    $('#pTools').hidden = !P.clips.length;
    if (P.media) $('#pMeta').textContent = `${P.clips.length} klip · sumber ${fmt(P.media.duration)} · ${P.media.width}×${P.media.height}` + (P.language ? ` · bahasa: ${P.language}` : '') + (P.engine ? ` · pemilih: ${P.engine}` : '');
    for (const c of P.clips) { if (!cards.has(c.id)) { const n = clipCard(P, c, load); cards.set(c.id, n); $('#pClips').append(n.el); } cards.get(c.id).update(P, c); }
    const busy = ['queued', 'running'].includes(P.status) || P.clips.some(c => ['queued', 'rendering'].includes(c.status));
    clearInterval(pollT); if (busy) pollT = setInterval(load, 1500);
  }
  await load();
}

function clipCard(P0, c0, reload) {
  const el = tpl('tpl-clip').firstElementChild;
  const vid = $('video', el);
  let C = c0, P = P0, ver = null, dirty = false;
  ['.c-title', '.c-start', '.c-end'].forEach(s => $(s, el).addEventListener('input', () => dirty = true));
  const llmOn = SETTINGS.llm.enabled && (SETTINGS.llm.model_titles || SETTINGS.llm.model_moments);
  $('.c-ai', el).hidden = !llmOn;
  $('.c-ai', el).onclick = async () => {
    const b = $('.c-ai', el); b.disabled = true;
    try { const r = await api(`/api/projects/${P.id}/clips/${C.id}/ai?kind=titles`, { method: 'POST' }); const box = $('.ai-list', el); box.hidden = false; box.replaceChildren(...r.titles.map(t => { const x = document.createElement('button'); x.type = 'button'; x.textContent = t; x.onclick = () => { $('.c-title', el).value = t; dirty = true; box.hidden = true; }; return x; })); }
    catch (e) { toast(e.message, true); } finally { b.disabled = false; }
  };
  const patch = async changes => {
    try { await api(`/api/projects/${P.id}/clips/${C.id}`, { method: 'PATCH', body: { changes } }); dirty = false; toast('Render ulang dimulai'); reload(); }
    catch (e) { toast(e.message, true); }
  };
  $('.c-save', el).onclick = () => {
    const ch = { title: $('.c-title', el).value };
    const s = +$('.c-start', el).value, e = +$('.c-end', el).value;
    if (s !== C.start || e !== C.end) { if (e - s < 1) return toast('Durasi minimal 1 detik', true); ch.start = s; ch.end = e; }
    patch(ch);
  };
  $('.c-layout', el).onchange = e => patch({ overrides: { layout: e.target.value || P.settings.layout } });
  $('.c-words', el).onclick = () => wordsDialog(C, words => patch({ words }));
  $('.c-crop', el).onclick = () => cropDialog(P, C, keys => patch({ crop_keys: keys }));
  return {
    el,
    update(p, c) {
      P = p; C = c;
      $('.cid', el).textContent = c.id.replace('clip_', 'Klip ');
      $('.score', el).textContent = '★ ' + c.score;
      $('.dur', el).textContent = `${fmt(c.start)}–${fmt(c.end)} · ${Math.round(c.end - c.start)} dtk`;
      if (!dirty && document.activeElement?.closest('.clip') !== el) { $('.c-title', el).value = c.title || ''; $('.c-start', el).value = c.start; $('.c-end', el).value = c.end; }
      $('.reason', el).textContent = c.reason ? 'AI: ' + c.reason + (c.hashtags?.length ? '  ' + c.hashtags.join(' ') : '') : '';
      const busy = ['queued', 'rendering'].includes(c.status);
      $('.busy', el).hidden = !busy; $('.busy b', el).textContent = c.status === 'queued' ? 'Antre…' : 'Merender…';
      $('.err', el).hidden = c.status !== 'error'; $('.err', el).textContent = c.error || 'Render gagal';
      const lay = (c.overrides && c.overrides.layout) || P.settings.layout;
      $('.c-layout', el).value = c.overrides && c.overrides.layout ? c.overrides.layout : '';
      $('.c-crop', el).hidden = !['portrait', 'square'].includes(lay);
      const ok = c.status === 'done' && c.file;
      ['.c-dl', '.c-words', '.c-crop', '.c-save'].forEach(s => $(s, el).toggleAttribute('disabled', !ok && s !== '.c-save'));
      if (ok && c.version !== ver) {
        ver = c.version;
        const u = `/files/${P.id}/${c.file}?v=${c.version}`;
        vid.src = u; vid.poster = `/files/${P.id}/${c.thumb}?v=${c.version}`;
        $('.c-dl', el).href = u; $('.c-dl', el).download = `${(c.title || c.id).replace(/[\\/:*?"<>|]+/g, '').slice(0, 60)}.mp4`;
      }
    },
  };
}

/* ---------------- dialog: edit kata caption ---------------- */
function openDlg(build) { const d = $('#dlg'), b = $('#dlgBody'); b.replaceChildren(); build(b, () => d.close()); d.showModal(); }
function wordsDialog(C, onSave) {
  openDlg((b, close) => {
    b.innerHTML = '<h2>Edit caption</h2><p class="muted">Perbaiki ejaan per kata. Kosongkan kotak untuk menghapus kata. Waktu kata tetap mengikuti suara.</p><div class="words"></div><div class="acts"><button class="btn" id="wSave">Simpan &amp; render</button></div>';
    const box = $('.words', b);
    (C.words || []).forEach(w => { const i = document.createElement('input'); i.value = w.w; i.title = `${w.s.toFixed(2)}–${w.e.toFixed(2)} dtk`; box.append(i); });
    if (!C.words?.length) box.innerHTML = '<p class="muted">Klip ini tidak punya kata terdeteksi.</p>';
    $('#wSave', b).onclick = () => { const ins = $$('input', box); onSave(C.words.map((w, i) => ({ ...w, w: ins[i].value.trim() })).filter(w => w.w)); close(); };
  });
}

/* ---------------- dialog: smart crop keyframe ---------------- */
function cropDialog(P, C, onSave) {
  const m = P.media, lay = (C.overrides && C.overrides.layout) || P.settings.layout;
  const target = lay === 'square' ? 1 : 9 / 16;
  const wFrac = Math.min(m.height * target / m.width, 1);
  const dur = C.end - C.start;
  let keys = (C.crop_keys && C.crop_keys.length ? C.crop_keys : [[0, 0.5]]).map(k => [...k]);
  let t = 0;
  openDlg((b, close) => {
    b.innerHTML = `<h2>Atur crop & keyframe</h2><p class="muted">Geser kotak kuning untuk memilih area. Klik timeline untuk pindah waktu, lalu "Simpan keyframe". Klik kanan keyframe untuk menghapus.</p>
      <div class="crop-wrap"><img alt="Frame video"><div class="crop-box"></div></div>
      <div class="tl"><div class="ph"></div></div><div class="muted" id="cT"></div>
      <div class="acts" style="margin-top:12px"><button class="btn ghost" id="kAdd">◆ Simpan keyframe di sini</button><button class="btn ghost" id="kAuto">Auto (ikuti wajah)</button><button class="btn ghost" id="kCenter">Reset ke tengah</button><button class="btn" id="kSave">Simpan &amp; render</button></div>`;
    const img = $('img', b), box = $('.crop-box', b), wrap = $('.crop-wrap', b), tl = $('.tl', b);
    box.style.width = wFrac * 100 + '%';
    const interp = tt => { const s = [...keys].sort((a, b) => a[0] - b[0]); if (tt <= s[0][0]) return s[0][1]; for (let i = 0; i < s.length - 1; i++) if (tt <= s[i + 1][0]) { const k = (tt - s[i][0]) / ((s[i + 1][0] - s[i][0]) || 1); return s[i][1] + (s[i + 1][1] - s[i][1]) * k; } return s.at(-1)[1]; };
    let cx = interp(0);
    const place = () => { const left = Math.max(0, Math.min(1 - wFrac, cx - wFrac / 2)); box.style.left = left * 100 + '%'; };
    const draw = () => { $$('.kf', tl).forEach(n => n.remove()); keys.forEach((k, i) => { const d = document.createElement('button'); d.type = 'button'; d.className = 'kf' + (Math.abs(k[0] - t) < .3 ? ' cur' : ''); d.style.left = (k[0] / dur * 100) + '%'; d.title = `${k[0].toFixed(1)} dtk`; d.onclick = e => { e.stopPropagation(); seek(k[0]); }; d.oncontextmenu = e => { e.preventDefault(); e.stopPropagation(); if (keys.length > 1) { keys.splice(i, 1); draw(); } }; tl.append(d); }); $('.ph', tl).style.left = (t / dur * 100) + '%'; $('#cT', b).textContent = `Waktu: ${t.toFixed(1)} / ${dur.toFixed(1)} dtk · ${keys.length} keyframe`; };
    const seek = tt => { t = Math.max(0, Math.min(dur, Math.round(tt * 2) / 2)); img.src = `/api/projects/${P.id}/frame?t=${(C.start + t).toFixed(1)}`; cx = interp(t); place(); draw(); };
    tl.onclick = e => { const r = tl.getBoundingClientRect(); seek((e.clientX - r.left) / r.width * dur); };
    let drag = null;
    box.onpointerdown = e => { box.setPointerCapture(e.pointerId); drag = { x: e.clientX, cx }; };
    box.onpointermove = e => { if (!drag) return; cx = Math.max(wFrac / 2, Math.min(1 - wFrac / 2, drag.cx + (e.clientX - drag.x) / wrap.clientWidth)); place(); };
    box.onpointerup = () => drag = null;
    $('#kAdd', b).onclick = () => { const ex = keys.find(k => Math.abs(k[0] - t) < .3); if (ex) ex[1] = cx; else keys.push([t, cx]); keys.sort((a, b) => a[0] - b[0]); draw(); toast('Keyframe disimpan'); };
    $('#kCenter', b).onclick = () => { keys = [[0, 0.5]]; seek(t); };
    $('#kAuto', b).onclick = () => { onSave(null); close(); };
    $('#kSave', b).onclick = () => { onSave(keys.map(k => [+k[0].toFixed(2), +k[1].toFixed(4)])); close(); };
    seek(0);
  });
}

/* ---------------- dialog: gaya semua klip ---------------- */
function styleDialog(P, reload) {
  const s = P.settings;
  openDlg((b, close) => {
    b.innerHTML = `<h2>Ubah gaya semua klip</h2><p class="muted">Semua klip dirender ulang dengan gaya ini. Judul &amp; potongan yang sudah kamu edit tetap dipertahankan.</p>
      <div class="row2"><label>Format<select class="in" id="sLay"><option value="portrait">Portrait</option><option value="square">Square</option><option value="blur">Blur</option><option value="split">Split gaming</option><option value="landscape">Landscape</option></select></label>
      <label>Gaya caption<select class="in" id="sCap"><option value="box">Box highlight</option><option value="wbw">Word by word</option><option value="karaoke">Karaoke</option><option value="clean">Clean</option></select></label></div>
      <div class="row2"><label>Font<select class="in" id="sFont">${INFO.fonts.map(f => `<option>${f}</option>`).join('')}</select></label>
      <label>Preset judul<select class="in" id="sTtl"><option value="bar">Bar</option><option value="outline">Outline</option><option value="neon">Neon</option><option value="clean">Clean</option></select></label></div>
      <div class="row3"><label>Warna teks<input type="color" class="in color" id="sCol"></label><label>Warna sorotan<input type="color" class="in color" id="sHl"></label><label>Ukuran<input type="number" class="in" id="sSize" min="40" max="140"></label></div>
      <label class="check"><input type="checkbox" id="sCapOn"> Tampilkan caption</label><label class="check"><input type="checkbox" id="sTtlOn"> Tampilkan judul</label>
      <label class="check"><input type="checkbox" id="sWmOn"> Watermark teks: <input class="in" id="sWm" style="max-width:220px"></label>
      <div class="acts"><button class="btn" id="sGo">Render ulang semua</button></div>`;
    $('#sLay', b).value = s.layout; $('#sCap', b).value = s.caption.style; $('#sFont', b).value = s.caption.font; $('#sTtl', b).value = s.title.preset;
    $('#sCol', b).value = s.caption.color; $('#sHl', b).value = s.caption.highlight; $('#sSize', b).value = s.caption.size;
    $('#sCapOn', b).checked = s.caption.enabled; $('#sTtlOn', b).checked = s.title.enabled; $('#sWmOn', b).checked = s.watermark.enabled; $('#sWm', b).value = s.watermark.text;
    $('#sGo', b).onclick = async () => {
      const ns = { caption: { style: $('#sCap', b).value, font: $('#sFont', b).value, color: $('#sCol', b).value, highlight: $('#sHl', b).value, size: +$('#sSize', b).value, enabled: $('#sCapOn', b).checked },
        title: { preset: $('#sTtl', b).value, enabled: $('#sTtlOn', b).checked }, watermark: { enabled: $('#sWmOn', b).checked, text: $('#sWm', b).value } };
      if ($('#sLay', b).value !== s.layout) ns.layout = $('#sLay', b).value;
      try { await api(`/api/projects/${P.id}/rerender`, { method: 'POST', body: { settings: ns } }); close(); toast('Render ulang semua klip…'); reload(); } catch (e) { toast(e.message, true); }
    };
  });
}

/* ================= RIWAYAT ================= */
async function pageHistory() {
  view.innerHTML = '<section class="page"><header class="page-h proj-h"><div><h1>Riwayat</h1><p>Semua proyek yang pernah kamu buat.</p></div><input class="in" id="hq" placeholder="Cari judul…" style="max-width:260px"></header><div class="hist" id="hl"></div></section>';
  const list = await api('/api/projects');
  const hl = $('#hl');
  const draw = q => {
    const items = list.filter(p => (p.title || '').toLowerCase().includes(q));
    if (!items.length) { hl.innerHTML = '<div class="empty">Belum ada proyek. <a href="#/new" style="color:var(--acc)">Buat proyek baru →</a></div>'; return; }
    hl.replaceChildren(...items.map(p => {
      const a = document.createElement('a'); a.className = 'hcard'; a.href = '#/p/' + p.id;
      a.innerHTML = `<div class="hthumb"></div><div class="hbody"><b></b><div class="hrow"><span class="tag ${p.status}">${p.status}</span><span>${p.clips} klip</span><button class="del" title="Hapus">🗑</button></div><span class="muted" style="font-size:12px">${new Date(p.created * 1000).toLocaleString('id-ID')}</span></div>`;
      $('b', a).textContent = p.title || p.id;
      if (p.thumb) $('.hthumb', a).style.backgroundImage = `url('/files/${p.id}/${p.thumb}')`;
      $('.del', a).onclick = async e => { e.preventDefault(); if (!confirm('Hapus proyek ini beserta semua klipnya?')) return; await api('/api/projects/' + p.id, { method: 'DELETE' }); list.splice(list.indexOf(p), 1); draw($('#hq').value.toLowerCase()); };
      return a;
    }));
  };
  $('#hq').oninput = e => draw(e.target.value.toLowerCase()); draw('');
}

/* ================= PENGATURAN ================= */
async function pageSettings() {
  SETTINGS = await api('/api/settings');
  const L = SETTINGS.llm;
  view.innerHTML = `<section class="page"><header class="page-h"><h1>Pengaturan</h1><p>Opsional. Aplikasi tetap berjalan penuh tanpa AI eksternal.</p></header>
    <div class="card"><h3>AI router (9router / kompatibel OpenAI) <label class="sw"><input type="checkbox" id="lOn"><span></span></label></h3>
      <p class="hint">Dipakai untuk memilih momen terbaik dan membuat judul. Transkripsi tetap memakai Whisper lokal.</p>
      <div class="row2"><label>Base URL<input class="in" id="lUrl" placeholder="http://localhost:20128/v1"></label><label>API key<input class="in" id="lKey" type="password" placeholder="sk-…"></label></div>
      <div class="acts" style="margin-bottom:14px"><button class="btn ghost" id="lTest">Tes koneksi &amp; ambil model</button><span class="muted" id="lMsg"></span></div>
      <div class="row2"><label>Model pemilih momen (pintar)<input class="in" id="lM1" list="lModels" placeholder="mis. claude-sonnet / gpt thinker"></label><label>Model judul &amp; caption (cepat)<input class="in" id="lM2" list="lModels" placeholder="mis. haiku / gemini flash"></label></div>
      <datalist id="lModels"></datalist>
      <label>Temperature <input type="range" id="lTemp" min="0" max="100"></label>
      <button class="btn" id="lSave">Simpan</button></div>
    <div class="card"><h3>Info</h3><p class="muted">Versi ${INFO.version}<br>Folder data &amp; hasil: <b>${INFO.data_dir}</b></p></div></section>`;
  $('#lOn').checked = L.enabled; $('#lUrl').value = L.base_url; $('#lKey').value = L.api_key; $('#lM1').value = L.model_moments; $('#lM2').value = L.model_titles; $('#lTemp').value = Math.round(L.temperature * 100);
  const form = () => ({ llm: { enabled: $('#lOn').checked, base_url: $('#lUrl').value.trim(), api_key: $('#lKey').value, model_moments: $('#lM1').value.trim(), model_titles: $('#lM2').value.trim(), temperature: +$('#lTemp').value / 100 } });
  $('#lTest').onclick = async () => {
    $('#lMsg').textContent = 'Menghubungi…';
    try { const r = await api('/api/llm/models', { method: 'POST', body: { settings: form() } }); $('#lModels').innerHTML = r.models.map(m => `<option value="${m.replace(/"/g, '&quot;')}">`).join(''); $('#lMsg').textContent = `✓ Terhubung · ${r.models.length} model tersedia (klik kolom model untuk memilih)`; }
    catch (e) { $('#lMsg').textContent = '✗ ' + e.message; }
  };
  $('#lSave').onclick = async () => {
    const f = form();
    if (f.llm.enabled && !f.llm.model_moments) return toast('Isi model pemilih momen dulu', true);
    SETTINGS = await api('/api/settings', { method: 'POST', body: { settings: f } }); $('#lKey').value = SETTINGS.llm.api_key; toast('Pengaturan disimpan');
  };
}

route().catch(e => { view.innerHTML = `<section class="page"><div class="empty">Gagal memuat: ${e.message}</div></section>`; });
