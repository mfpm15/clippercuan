/* ClipperCuan — interaksi situs. Vanilla JS, tanpa dependency. */
(() => {
  'use strict';
  const S = window.SITE || {};
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const el = (tag, props = {}, kids = []) => {
    const { dataset, ...rest } = props;
    const n = Object.assign(document.createElement(tag), rest);
    if (dataset) Object.assign(n.dataset, dataset);
    (Array.isArray(kids) ? kids : [kids]).forEach(k => n.append(k));
    return n;
  };
  const rp = n => 'Rp' + Math.round(n).toLocaleString('id-ID');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const safe = fn => { try { return fn(); } catch (e) { console.error('[demo]', e); return null; } };

  /* ---------- config binding ---------- */
  $$('[data-cfg]').forEach(n => { const v = S[n.dataset.cfg]; if (v != null) n.textContent = v; });
  $$('[data-price="now"]').forEach(n => n.textContent = rp(S.price));
  $$('[data-price="original"]').forEach(n => n.textContent = rp(S.priceOriginal));
  $$('[data-community]').forEach(n => { if (S.communityCount) n.textContent = `${S.communityCount} kreator aktif di komunitas`; });
  const linkMap = { telegramUrl: S.telegramUrl, instagramUrl: S.instagramUrl, mail: S.email ? 'mailto:' + S.email : '' };
  $$('[data-link]').forEach(a => { const u = linkMap[a.dataset.link]; if (u) a.href = u; else a.hidden = true; });
  $('#year').textContent = new Date().getFullYear();
  document.title = `${S.brand} — Clipper Unlimited, Sekali Bayar`;

  /* ---------- toast ---------- */
  let toastT;
  const toast = msg => { const t = $('#toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 2600); };

  /* ---------- buy buttons ---------- */
  const configured = S.checkoutUrl && !/username-anda/.test(S.checkoutUrl);
  $$('[data-buy]').forEach(a => {
    a.addEventListener('click', e => {
      const inPricing = a.closest('#harga');
      if (S.trackEndpoint) safe(() => navigator.sendBeacon(S.trackEndpoint, JSON.stringify({ ev: 'buy_click', at: Date.now(), from: a.closest('section,header,div')?.id || 'page' })));
      if (!inPricing && a.getAttribute('href') === '#harga') return; // scroll ke harga dulu
      e.preventDefault();
      if (!configured) { toast('Atur checkoutUrl di config.js untuk mengaktifkan pembelian'); return; }
      window.open(S.checkoutUrl, '_blank', 'noopener');
    });
  });

  /* ---------- promo countdown (reset 00.00 di zona waktu config) ---------- */
  const DAY = 864e5, OFF = (S.promoTzOffsetHours ?? 7) * 36e5;
  const tick = () => {
    const sec = Math.ceil((DAY - ((Date.now() + OFF) % DAY)) / 1000);
    const l = [Math.floor(sec / 3600), Math.floor(sec / 60) % 60, sec % 60].map(v => String(v).padStart(2, '0')).join(':');
    $$('[data-countdown]').forEach(n => n.textContent = l);
  };
  tick(); setInterval(tick, 1000);
  document.addEventListener('visibilitychange', () => !document.hidden && tick());
  if (S.showPromo === false) {
    $('#promoBar').classList.add('off');
    $$('[data-promo-timer],[data-promo-badge]').forEach(n => n.hidden = true);
    $$('[data-price="original"]').forEach(n => n.hidden = true);
  }

  /* ---------- nav: burger, scrollspy, progress, sticky buy ---------- */
  const burger = $('#burger'), drawer = $('#drawer');
  const setDrawer = open => { burger.setAttribute('aria-expanded', open); drawer.hidden = !open; };
  burger.addEventListener('click', () => setDrawer(burger.getAttribute('aria-expanded') !== 'true'));
  $$('a', drawer).forEach(a => a.addEventListener('click', () => setDrawer(false)));
  addEventListener('keydown', e => { if (e.key === 'Escape') setDrawer(false); });

  const links = $$('.nav-links a');
  const spy = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) links.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + e.target.id));
  }), { rootMargin: '-45% 0px -50% 0px' });
  links.forEach(a => { const t = $(a.getAttribute('href')); if (t) spy.observe(t); });

  const prog = $('#progress'), sticky = $('#stickyBuy'), price = $('#harga');
  let ticking = false;
  const onScroll = () => {
    if (ticking) return; ticking = true;
    requestAnimationFrame(() => {
      const h = document.documentElement;
      prog.style.width = (h.scrollTop / (h.scrollHeight - h.clientHeight || 1) * 100) + '%';
      const r = price.getBoundingClientRect();
      sticky.classList.toggle('show', scrollY > 500 && !(r.top < innerHeight && r.bottom > 0));
      ticking = false;
    });
  };
  addEventListener('scroll', onScroll, { passive: true }); onScroll();

  /* ---------- reveal ---------- */
  document.documentElement.classList.remove('no-js');
  const rv = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); rv.unobserve(e.target); } }), { threshold: .08 });
  $$('.reveal').forEach(n => rv.observe(n));

  /* ---------- motion toggle ---------- */
  const mBtn = $('#motionToggle');
  let paused = reduced;
  const applyMotion = () => { document.body.classList.toggle('paused', paused); mBtn.setAttribute('aria-pressed', paused); mBtn.textContent = paused ? '▶ Putar animasi' : 'Ⅱ Jeda animasi'; };
  mBtn.addEventListener('click', () => { paused = !paused; applyMotion(); });
  applyMotion();

  /* ---------- hero simulasi ---------- */
  const isYT = u => { try { const x = new URL(u); return /(^|\.)youtube\.com$|^youtu\.be$/.test(x.hostname) && (x.searchParams.get('v') || x.hostname === 'youtu.be' || /^\/(shorts|live|embed)\//.test(x.pathname)); } catch { return false; } };
  $('#tryForm').addEventListener('submit', e => {
    e.preventDefault();
    const msg = $('#tryMsg'), v = $('#tryUrl').value.trim(), btn = $('button', e.target);
    msg.className = 'try-msg';
    if (!v) { msg.textContent = 'Tempel link video dulu ya.'; msg.classList.add('err'); return; }
    if (!isYT(v)) { msg.textContent = 'Link belum valid. Contoh: https://youtube.com/watch?v=…'; msg.classList.add('err'); return; }
    btn.setAttribute('aria-busy', 'true');
    const steps = ['Mengambil video…', 'Transkripsi audio…', 'Mencari momen viral…', 'Menyusun 12 klip…'];
    let i = 0; msg.textContent = steps[0];
    const t = setInterval(() => {
      i++;
      if (i < steps.length) { msg.textContent = steps[i]; return; }
      clearInterval(t); btn.removeAttribute('aria-busy');
      msg.classList.add('ok'); msg.textContent = '✓ Simulasi selesai: 12 klip siap. Dapatkan aplikasinya untuk memproses video sungguhan.';
      $('#hasil').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
    }, 900);
  });

  /* ---------- generic helpers ---------- */
  const group = (box, sel, cb, attr = 'aria-pressed') => {
    const items = $$(sel, box);
    items.forEach(b => b.addEventListener('click', () => { items.forEach(x => x.setAttribute(attr, x === b)); cb(b, b.dataset); }));
    return items;
  };
  const chips = (list, attr = 'k') => el('div', { className: 'chips' }, list.map(([k, t, on]) => el('button', { className: 'chip', type: 'button', textContent: t, ariaPressed: String(!!on), }, [])).map((b, i) => { b.dataset[attr] = list[i][0]; return b; }));
  const phone = (scene, inner = '') => { const d = el('div', { className: 'phone' }); d.innerHTML = `<div class="screen ${scene}">${inner}</div>`; return d; };
  const lbl = t => el('span', { className: 'lbl', textContent: t });

  /* ---------- reel (hasil) ---------- */
  const NICHES = {
    podcast: { scene: 'scene-podcast', style: 'box', clips: ['Rahasia yang jarang dibahas', 'Kesalahan terbesar founder', 'Ini yang bikin kaget', 'Tips 3 menit', 'Jawaban jujur'] },
    gaming: { scene: 'scene-stream', style: 'wbw', clips: ['Clutch 1 vs 4!', 'Rage quit paling epik', 'Tips rank cepat', 'Momen lucu squad', 'Build tersembunyi'] },
    edu: { scene: 'scene-edu', style: 'font', clips: ['Cara cepat paham ini', '3 kesalahan belajar', 'Rumus yang wajib hafal', 'Trik ingat materi', 'Kenapa ini penting'] }
  };
  const reel = $('#reel');
  const renderReel = key => {
    const n = NICHES[key]; reel.replaceChildren();
    n.clips.slice(0, 4).forEach((t, i) => {
      const p = phone(n.scene, `<div class="score">${96 - i * 4}</div><div class="subs ${n.style === 'font' ? 'subs-serif' : ''}" data-subs="${n.style}">${t.split(' ').slice(0, -1).join(' ')} <em>${t.split(' ').pop()}</em></div><div class="rbar" style="--d:${i}"></div>`);
      const it = el('figure', { className: 'reel-item', style: `margin:0;animation-delay:${i * 80}ms` }, [p, el('figcaption', { className: 'reel-cap', textContent: `KLIP ${String(i + 1).padStart(2, '0')} · SKOR VIRAL ${96 - i * 4}` })]);
      reel.append(it);
    });
  };
  group($('#nicheTabs'), 'button', b => renderReel(b.dataset.niche), 'aria-selected');
  renderReel('podcast');

  /* ---------- feature nav ---------- */
  const fnav = $('#featNav');
  $$('.feat').forEach((f, i) => { const t = $('h3', f).textContent.replace(/\.$/, ''); fnav.append(el('a', { href: '#' + f.id, textContent: String(i + 1).padStart(2, '0') + ' ' + t.split(' ').slice(0, 3).join(' ') })); });

  /* ---------- DEMOS ---------- */
  const D = {};
  const COLORS = [['#4b3a7a', '#1d1633'], ['#9a3d5a', '#2a1020'], ['#2b7a6a', '#0e2723'], ['#b8742b', '#2a1a08'], ['#3a5fbf', '#0f1a3d'], ['#7a2b6a', '#1d0a18'], ['#2b6f9a', '#0b2030'], ['#6a7a2b', '#1c2008']];
  const grad = i => `--c1:${COLORS[i % 8][0]};--c2:${COLORS[i % 8][1]}`;

  D.dashboard = root => {
    root.innerHTML = `<div class="dash"><div class="dash-side"><i class="on"></i><i></i><i></i><i></i></div>
      <div class="dash-main"><div class="dash-vid" aria-label="Preview video"></div>
      <div class="dash-set"><div>Bahasa <b>Auto-detect</b></div><div>Crop <b>Portrait</b></div><div>Caption <b>Box highlight</b></div><div>Judul <b>Preset Bar</b></div></div>
      <div class="dash-clips"></div><div class="dash-prog"><i></i></div><button class="btn btn-sm dash-run" type="button">Render klip terpilih</button></div></div>`;
    const wrap = $('.dash-clips', root), pr = $('.dash-prog i', root), run = $('.dash-run', root);
    const sel = new Set([0]);
    for (let i = 0; i < 5; i++) { const b = el('button', { type: 'button', textContent: `#${i + 1}` }); b.style.cssText = grad(i + 2); b.setAttribute('aria-pressed', i === 0); b.classList.toggle('on', i === 0);
      b.addEventListener('click', () => { sel.has(i) ? sel.delete(i) : sel.add(i); b.classList.toggle('on', sel.has(i)); b.setAttribute('aria-pressed', sel.has(i)); run.textContent = sel.size ? `Render ${sel.size} klip terpilih` : 'Pilih klip dulu'; }); wrap.append(b); }
    run.addEventListener('click', () => {
      if (!sel.size) return toast('Pilih minimal satu klip');
      run.setAttribute('aria-busy', 'true'); let p = 0;
      const t = setInterval(() => { p += 8 + Math.random() * 10; pr.style.width = Math.min(p, 100) + '%'; if (p >= 100) { clearInterval(t); run.removeAttribute('aria-busy'); toast(`✓ ${sel.size} klip selesai dirender (simulasi)`); setTimeout(() => pr.style.width = 0, 1200); } }, 220);
    });
  };

  D.gaming = root => {
    root.innerHTML = `<div class="ba" style="--p:50%"><div class="layer before"><span class="ba-tag">SEBELUM</span><div class="game-full scene-game"></div></div>
      <div class="layer after"><span class="ba-tag">SESUDAH</span><div class="game-split"><div class="face"></div><div class="play"></div></div></div>
      <div class="ba-handle"></div><input type="range" min="0" max="100" value="50" aria-label="Geser perbandingan sebelum dan sesudah"></div>
      <div class="chips"><button class="chip" type="button" data-s="0">Sebelum</button><button class="chip" type="button" data-s="50" aria-pressed="true">Banding</button><button class="chip" type="button" data-s="100">Sesudah</button><button class="chip" type="button" id="gAuto">▶ Putar perbandingan</button></div>`;
    const ba = $('.ba', root), r = $('input', ba); let raf;
    const set = v => { ba.style.setProperty('--p', v + '%'); r.value = v; };
    r.addEventListener('input', () => set(r.value));
    const cs = group(root, '[data-s]', b => { cancelAnimationFrame(raf); set(b.dataset.s); });
    $('#gAuto', root).addEventListener('click', e => {
      cs.forEach(x => x.setAttribute('aria-pressed', false)); let t = 0; cancelAnimationFrame(raf);
      const f = () => { t += .02; set(50 + Math.sin(t) * 48); if (t < Math.PI * 2) raf = requestAnimationFrame(f); else set(50); }; f();
    });
  };

  const LANGS = { auto: ['Auto-detect', 'Bahasa terdeteksi otomatis', 'Deteksi otomatis aktif'], id: ['Indonesia', 'Ini momen yang paling penting', 'Bahasa Indonesia'], en: ['English', 'This is the most important moment', 'Inggris'], ms: ['Melayu', 'Ini detik yang paling penting', 'Melayu'], ar: ['العربية', 'هذه أهم لحظة', 'Arab'], ja: ['日本語', 'これが最も重要な瞬間です', 'Jepang'], ko: ['한국어', '이것이 가장 중요한 순간입니다', 'Korea'], es: ['Español', 'Este es el momento más importante', 'Spanyol'] };
  D.lang = root => {
    root.innerHTML = `<div class="lang"><div class="lang-pick"><label class="lbl" for="lsel">Bahasa transkripsi</label><select id="lsel" class="field">${Object.entries(LANGS).map(([k, v]) => `<option value="${k}">${v[0]}</option>`).join('')}</select>
      <div class="lang-ex" aria-live="polite"><span class="lbl">Contoh hasil caption</span><b id="lEx"></b><span id="lNote"></span></div></div><div id="lPhone"></div></div>`;
    const ph = phone('scene-podcast', '<div class="subs" id="lSub" style="font-size:.75rem"></div>'); $('#lPhone', root).append(ph);
    const upd = k => { const v = LANGS[k]; $('#lEx', root).textContent = v[1]; $('#lNote', root).textContent = v[2]; $('#lSub', root).textContent = v[1]; $('#lEx', root).dir = $('#lSub', root).dir = k === 'ar' ? 'rtl' : 'ltr'; };
    $('#lsel', root).addEventListener('change', e => upd(e.target.value)); upd('auto');
  };

  const SAMPLE = 'Ini momen yang bikin semua orang kaget'.split(' ');
  const mkSubs = (host, words) => { host.replaceChildren(...words.map(w => el('span', { className: 'w', textContent: w + ' ' }))); return $$('.w', host); };
  D.caption = root => {
    const ph = phone('scene-podcast', '<div class="sub-demo" data-hl="box" data-anim="pop" data-font="head"></div>');
    const sub = $('.sub-demo', ph); const ws = mkSubs(sub, SAMPLE); let i = 0;
    setInterval(() => { if (paused || document.hidden) return; ws.forEach(w => w.classList.remove('on')); ws[i % ws.length].classList.add('on'); i++; }, 520);
    ws[0].classList.add('on');
    const row = (label, attr, opts) => { const r = el('div', { className: 'ctl-row' }, [lbl(label)]); opts.forEach(([k, t], j) => { const b = el('button', { className: 'chip', type: 'button', textContent: t }); b.dataset.v = k; b.setAttribute('aria-pressed', sub.dataset[attr] === k); b.onclick = () => { sub.dataset[attr] = k; $$('.chip', r).forEach(x => x.setAttribute('aria-pressed', x === b)); }; r.append(b); }); return r; };
    const sw = el('div', { className: 'ctl-row' }, [lbl('Warna')]); const swb = el('div', { className: 'swatches' });
    ['#ffc933', '#3ddc97', '#ff5d8f', '#6ec1ff', '#ffffff'].forEach((c, j) => { const b = el('button', { className: 'sw', type: 'button', ariaLabel: 'Warna ' + c }); b.style.setProperty('--c', c); b.setAttribute('aria-pressed', j === 0); b.onclick = () => { sub.style.setProperty('--hl', c); $$('.sw', swb).forEach(x => x.setAttribute('aria-pressed', x === b)); }; swb.append(b); }); sw.append(swb);
    root.append(ph, el('div', { className: 'ctl' }, [row('Highlight', 'hl', [['box', 'Box'], ['text', 'Teks']]), row('Animasi', 'anim', [['pop', 'Pop'], ['shake', 'Shake'], ['slide', 'Slide'], ['none', 'Tanpa']]), row('Font', 'font', [['head', 'Modern'], ['serif', 'Serif'], ['bold', 'Impact'], ['mono', 'Mono']]), sw]));
  };

  D.title = root => {
    const ba = el('div', { className: 'ba', style: '--p:50%;width:min(100%,230px)' });
    ba.innerHTML = `<div class="layer before"><span class="ba-tag">TANPA JUDUL</span><div class="screen scene-edu" style="border-radius:0"><div class="subs" style="font-size:.7rem">Cara cepat belajar</div></div></div>
      <div class="layer after"><span class="ba-tag">DENGAN PRESET</span><div class="screen scene-edu" style="border-radius:0"><div class="ttl" data-p="bar">5 Trik Belajar Cepat</div><div class="subs" style="font-size:.7rem">Cara cepat belajar</div></div></div>
      <div class="ba-handle"></div><input type="range" min="0" max="100" value="50" aria-label="Geser perbandingan">`;
    $('input', ba).addEventListener('input', e => ba.style.setProperty('--p', e.target.value + '%'));
    const ttl = $('.ttl', ba);
    const c = chips([['bar', 'Bar', 1], ['outline', 'Outline'], ['neon', 'Neon'], ['clean', 'Clean']]);
    group(c, '.chip', b => ttl.dataset.p = b.dataset.k);
    const inp = el('input', { className: 'field', value: '5 Trik Belajar Cepat', maxLength: 40, ariaLabel: 'Teks judul' });
    const gen = el('button', { className: 'btn btn-sm', type: 'button', textContent: '✦ Generate' });
    const IDEAS = ['Jangan Lakukan Ini!', 'Rahasia yang Jarang Dibahas', '3 Detik yang Mengubah Segalanya', 'Kamu Pasti Salah Paham', 'Ini Alasan Sebenarnya'];
    let gi = 0; gen.onclick = () => { inp.value = IDEAS[gi++ % IDEAS.length]; inp.dispatchEvent(new Event('input')); };
    inp.addEventListener('input', () => ttl.textContent = inp.value || '…');
    root.append(ba, c, el('div', { className: 'ttl-in' }, [inp, gen]));
  };

  D.editor = root => {
    const out = el('div', { className: 'edit-out' }); const words = 'Satu kata bisa mengubah segalanya'.split(' ');
    const ws = el('div', { className: 'words' }); const state = words.map(() => ({ color: '', font: '', size: 1 }));
    const sel = new Set([1]);
    const render = () => { out.replaceChildren(...words.map((w, i) => { const s = state[i]; const sp = el('span', { textContent: w + ' ' }); sp.style.cssText = `color:${s.color || '#fff'};font-family:${s.font || 'inherit'};font-size:${s.size}em;display:inline-block;margin:0 .1em`; return sp; })); $$('.wd', ws).forEach((b, i) => b.classList.toggle('sel', sel.has(i))); };
    words.forEach((w, i) => { const b = el('button', { className: 'wd', type: 'button', textContent: w }); b.onclick = e => { if (e.shiftKey || e.metaKey || e.ctrlKey) sel.has(i) ? sel.delete(i) : sel.add(i); else { sel.clear(); sel.add(i); } render(); }; ws.append(b); });
    const apply = patch => { sel.forEach(i => Object.assign(state[i], patch)); render(); };
    const all = el('button', { className: 'chip', type: 'button', textContent: 'Select all' }); all.onclick = () => { words.forEach((_, i) => sel.add(i)); render(); };
    const reset = el('button', { className: 'chip', type: 'button', textContent: 'Reset' }); reset.onclick = () => { state.forEach(s => Object.assign(s, { color: '', font: '', size: 1 })); render(); };
    const cr = el('div', { className: 'ctl-row' }, [lbl('Warna')]);
    ['#ffc933', '#3ddc97', '#ff5d8f', '#6ec1ff', '#ffffff'].forEach(c => { const b = el('button', { className: 'sw', type: 'button', ariaLabel: 'Warna ' + c }); b.style.setProperty('--c', c); b.onclick = () => apply({ color: c }); cr.append(b); });
    const fr = el('div', { className: 'ctl-row' }, [lbl('Font')]);
    [['Modern', 'inherit'], ['Serif', 'Georgia,serif'], ['Impact', 'Impact,sans-serif'], ['Mono', 'monospace']].forEach(([t, f]) => fr.append(el('button', { className: 'chip', type: 'button', textContent: t, onclick: () => apply({ font: f }) })));
    const sr = el('div', { className: 'ctl-row' }, [lbl('Ukuran'), el('input', { type: 'range', min: .8, max: 2, step: .1, value: 1, ariaLabel: 'Ukuran kata', oninput: e => apply({ size: +e.target.value }) })]);
    root.append(out, ws, el('div', { className: 'ctl' }, [el('div', { className: 'ctl-row' }, [lbl('Pilih'), all, reset]), cr, fr, sr]), el('p', { className: 'note-sm', textContent: 'Klik kata; Shift/Ctrl+klik untuk pilih beberapa.' }));
    render();
  };

  D.watermark = root => {
    const ph = phone('scene-stream', '<div class="wm" data-pos="br"><i></i><span>@namakamu</span></div>'); const wm = $('.wm', ph), tx = $('span', wm), ic = $('i', wm);
    const t = el('input', { className: 'field', value: '@namakamu', maxLength: 24, ariaLabel: 'Teks watermark', oninput: e => tx.textContent = e.target.value });
    const size = el('input', { type: 'range', min: .6, max: 1.6, step: .05, value: 1, ariaLabel: 'Ukuran', oninput: e => wm.style.fontSize = e.target.value * .7 + 'rem' });
    const op = el('input', { type: 'range', min: .2, max: 1, step: .05, value: .8, ariaLabel: 'Transparansi', oninput: e => wm.style.setProperty('--o', e.target.value) });
    const grid = el('div', { className: 'pos-grid' }); const cells = ['tl', '', 'tr', '', 'c', '', 'bl', '', 'br'];
    cells.forEach(p => { const b = el('button', { type: 'button', ariaLabel: 'Posisi ' + p }); if (!p) b.hidden = true; else { b.setAttribute('aria-pressed', p === 'br'); b.onclick = () => { wm.dataset.pos = p; $$('button', grid).forEach(x => x.setAttribute('aria-pressed', x === b)); }; } grid.append(b); });
    const mode = chips([['text', 'Teks', 1], ['logo', 'Logo'], ['both', 'Keduanya']]);
    group(mode, '.chip', b => { ic.style.display = b.dataset.k === 'text' ? 'none' : ''; tx.style.display = b.dataset.k === 'logo' ? 'none' : ''; }); ic.style.display = 'none';
    root.append(ph, el('div', { className: 'ctl' }, [el('div', { className: 'ctl-row' }, [lbl('Jenis'), mode]), el('div', { className: 'ctl-row' }, [lbl('Teks'), t]), el('div', { className: 'ctl-row' }, [lbl('Ukuran'), size]), el('div', { className: 'ctl-row' }, [lbl('Opacity'), op]), el('div', { className: 'ctl-row' }, [lbl('Posisi'), grid])]));
  };

  const HIST = ['Podcast #12 · 8 klip', 'Gaming ranked · 12 klip', 'Webinar UMKM · 6 klip', 'Vlog Bali · 9 klip', 'Interview CEO · 7 klip', 'Kelas Excel · 10 klip', 'Stream malam · 14 klip', 'Review gadget · 5 klip'];
  D.history = root => {
    const g = el('div', { className: 'gal' }); const pv = el('div', { className: 'gal-prev' });
    const show = i => { pv.innerHTML = `<div class="th" style="${grad(i)}"></div><div><b>${HIST[i].split(' · ')[0]}</b><p>${HIST[i].split(' · ')[1]} · dirender kemarin</p></div><button class="btn btn-sm" type="button" style="margin-left:auto">Buka</button>`; $('.btn', pv).onclick = () => toast('Membuka ' + HIST[i].split(' · ')[0] + ' (simulasi)'); $$('button', g).forEach((b, j) => b.classList.toggle('on', j === i)); };
    HIST.forEach((h, i) => { const b = el('button', { type: 'button', ariaLabel: h }, [el('span', { textContent: String(i + 1).padStart(2, '0') })]); b.style.cssText = grad(i); b.onclick = () => show(i); g.append(b); });
    const q = el('input', { className: 'field', placeholder: 'Cari riwayat…', ariaLabel: 'Cari riwayat', oninput: e => { const v = e.target.value.toLowerCase(); $$('button', g).forEach((b, i) => b.hidden = !HIST[i].toLowerCase().includes(v)); } });
    root.append(q, g, pv); show(0);
  };

  D.cliplist = root => {
    const list = el('div', { className: 'cliplist' }); const bar = el('div', { className: 'render-bar' }, [el('i')]);
    const T = ['Kesalahan terbesar founder', 'Rahasia yang jarang dibahas', 'Tips 3 menit', 'Jawaban paling jujur'];
    const btn = el('button', { className: 'btn btn-block', type: 'button' }); let n = 0;
    const upd = () => { n = $$('input[type=checkbox]:checked', list).length; btn.textContent = n ? `Lanjut render ${n} klip` : 'Pilih klip dulu'; $$('.clip-row', list).forEach(r => r.classList.toggle('on', $('input[type=checkbox]', r).checked)); };
    T.forEach((t, i) => { const r = el('div', { className: 'clip-row' }); r.innerHTML = `<input type="checkbox" aria-label="Pilih klip ${i + 1}" ${i < 2 ? 'checked' : ''}><div class="th" style="${grad(i + 1)}"></div><input type="text" value="${t}" aria-label="Judul klip ${i + 1}" maxlength="50"><span class="sc">${95 - i * 5}</span>`; $('input[type=checkbox]', r).onchange = upd; list.append(r); });
    btn.onclick = () => { if (!n) return toast('Pilih minimal satu klip'); btn.setAttribute('aria-busy', 'true'); let p = 0; const t = setInterval(() => { p += 12; $('i', bar).style.width = Math.min(p, 100) + '%'; if (p >= 100) { clearInterval(t); btn.removeAttribute('aria-busy'); toast(`✓ ${n} klip masuk antrean render (simulasi)`); setTimeout(() => $('i', bar).style.width = 0, 1000); } }, 150); };
    root.append(list, bar, btn); upd();
  };

  D.options = root => {
    const ph = phone('scene-podcast', '<div class="ttl" data-p="bar" style="top:14%">Judul klip kamu</div><div class="sub-demo" data-hl="box" data-font="head"><span class="w on">Caption</span> <span class="w">contoh</span></div>');
    const ttl = $('.ttl', ph), sd = $('.sub-demo', ph), scr = $('.screen', ph);
    const mk = (label, list, cb) => { const c = chips(list); group(c, '.chip', b => cb(b.dataset.k)); return el('div', { className: 'ctl-row' }, [lbl(label), c]); };
    root.append(ph, el('div', { className: 'ctl' }, [
      mk('Crop', [['crop', 'Crop pintar', 1], ['split', 'Split screen'], ['blur', 'Blur']], k => { scr.dataset.mode = k; scr.style.filter = k === 'blur' ? 'saturate(.7)' : ''; scr.style.backgroundSize = k === 'split' ? '100% 50%' : ''; }),
      mk('Font', [['head', 'Modern', 1], ['serif', 'Serif'], ['bold', 'Impact']], k => sd.dataset.font = k),
      mk('Judul', [['bar', 'Bar', 1], ['outline', 'Outline'], ['neon', 'Neon']], k => ttl.dataset.p = k),
      el('input', { className: 'field', value: 'Judul klip kamu', maxLength: 36, ariaLabel: 'Teks judul', oninput: e => ttl.textContent = e.target.value || '…' })]));
  };

  D.crop = root => {
    const stage = el('div', { className: 'crop-stage', style: '--x:34%' }); stage.innerHTML = '<div class="actor" style="left:46%"></div><div class="crop-box" tabindex="0" role="slider" aria-label="Posisi crop" aria-valuemin="0" aria-valuemax="68" aria-valuenow="34"></div>';
    const box = $('.crop-box', stage); let x = 34;
    const setX = v => { x = Math.max(0, Math.min(68.36, v)); stage.style.setProperty('--x', x + '%'); box.setAttribute('aria-valuenow', Math.round(x)); upd(); };
    const tl = el('div', { className: 'timeline', title: 'Klik untuk menambah keyframe' }); tl.innerHTML = '<div class="playhead"></div>';
    const kfs = [{ t: 0, x: 10 }, { t: 100, x: 58 }]; let t = 0, playing = false;
    const out = phone('', '<div class="actor2"></div>'); const act = $('.actor2', out); out.style.width = '96px';
    const interp = tt => { const s = [...kfs].sort((a, b) => a.t - b.t); if (tt <= s[0].t) return s[0].x; for (let i = 0; i < s.length - 1; i++) if (tt <= s[i + 1].t) { const k = (tt - s[i].t) / ((s[i + 1].t - s[i].t) || 1); return s[i].x + (s[i + 1].x - s[i].x) * k; } return s.at(-1).x; };
    function upd() { $('.actor', stage).style.left = (20 + t * .6) + '%'; const center = x + 15.8, ax = 50 + ((20 + t * .6 + 7) - center) / 31.64 * 100; act.style.setProperty('--ax', Math.max(5, Math.min(95, ax)) + '%'); }
    const drawKf = () => { $$('.kf', tl).forEach(n => n.remove()); kfs.forEach((k, i) => { const b = el('button', { className: 'kf', type: 'button', ariaLabel: `Keyframe ${i + 1}`, title: 'Klik kanan / Alt+klik untuk hapus' }); b.style.left = k.t + '%'; b.onclick = e => { e.stopPropagation(); if (e.altKey && kfs.length > 1) { kfs.splice(i, 1); drawKf(); return; } seek(k.t); }; b.oncontextmenu = e => { e.preventDefault(); e.stopPropagation(); if (kfs.length > 1) { kfs.splice(i, 1); drawKf(); } }; tl.append(b); }); };
    const seek = tt => { t = tt; tl.style.setProperty('--t', t + '%'); setX(interp(t)); };
    tl.addEventListener('click', e => { const r = tl.getBoundingClientRect(); seek(Math.round((e.clientX - r.left) / r.width * 100)); });
    const addKf = el('button', { className: 'chip', type: 'button', textContent: '◆ Tambah keyframe di sini' });
    addKf.onclick = () => { const e = kfs.find(k => Math.abs(k.t - t) < 2); if (e) e.x = x; else kfs.push({ t, x }); drawKf(); toast('Keyframe disimpan'); };
    const play = el('button', { className: 'chip', type: 'button', textContent: '▶ Putar hasil' }); let raf;
    play.onclick = () => { if (playing) { playing = false; cancelAnimationFrame(raf); play.textContent = '▶ Putar hasil'; return; } playing = true; play.textContent = 'Ⅱ Jeda'; let tt = t >= 100 ? 0 : t; const f = () => { tt += .5; if (tt > 100) { playing = false; play.textContent = '▶ Putar hasil'; return; } seek(tt); raf = requestAnimationFrame(f); }; f(); };
    let drag = false, off = 0;
    box.addEventListener('pointerdown', e => { drag = true; box.setPointerCapture(e.pointerId); const r = stage.getBoundingClientRect(); off = (e.clientX - r.left) / r.width * 100 - x; });
    box.addEventListener('pointermove', e => { if (!drag) return; const r = stage.getBoundingClientRect(); setX((e.clientX - r.left) / r.width * 100 - off); });
    box.addEventListener('pointerup', () => drag = false);
    box.addEventListener('keydown', e => { if (e.key === 'ArrowLeft') { setX(x - 2); e.preventDefault(); } if (e.key === 'ArrowRight') { setX(x + 2); e.preventDefault(); } });
    root.append(el('div', { className: 'crop-out' }, [stage, out]), tl, el('div', { className: 'chips' }, [addKf, play]));
    drawKf(); seek(0);
  };

  D.orient = root => {
    const fr = el('div', { className: 'o-frame', dataset: { o: 'portrait' } }); fr.innerHTML = '<div class="o-bg"></div><div class="o-vid"></div>';
    const lab = el('div', { className: 'o-label', textContent: 'PORTRAIT 9:16' }); const LB = { portrait: 'PORTRAIT 9:16', square: 'SQUARE 1:1', blur: 'PORTRAIT + BLUR BACKGROUND' };
    const c = chips([['portrait', 'Portrait', 1], ['square', 'Square'], ['blur', 'Blur']]); group(c, '.chip', b => { fr.dataset.o = b.dataset.k; lab.textContent = LB[b.dataset.k]; });
    root.append(el('div', { className: 'orient' }, [el('div', { style: 'text-align:center' }, [fr, lab])]), c);
  };

  $$('[data-demo]').forEach(n => { const f = D[n.dataset.demo]; if (f) safe(() => f(n)) ?? 0; });

  /* ---------- perbandingan: tidak ada JS ---------- */

  /* ---------- testimonials ---------- */
  const track = $('#slTrack'), dlg = $('#dlg');
  (S.testimonials || []).forEach((t, i) => {
    const c = el('button', { className: 'tcard', type: 'button', ariaHaspopup: 'dialog' });
    c.innerHTML = `<div style="display:flex;align-items:center"><span class="stars" aria-label="5 bintang">★★★★★</span>${t.sample ? '<span class="samp">Contoh</span>' : ''}</div><q></q><div class="who"><span class="av"></span><div><b></b><small></small></div></div>`;
    $('q', c).textContent = t.text; $('.av', c).textContent = t.name[0]; $('b', c).textContent = t.name; $('small', c).textContent = t.role;
    c.onclick = () => { $('#dlgBody').innerHTML = `<h3 id="dlgTitle"></h3><p class="stars">★★★★★</p><q></q><div class="who"><span class="av"></span><div><b></b><small></small></div></div>`; $('#dlgTitle').textContent = 'Pengalaman ' + t.name; $('#dlgBody q').textContent = t.text; $('#dlgBody .av').textContent = t.name[0]; $('#dlgBody b').textContent = t.name; $('#dlgBody small').textContent = t.role; dlg.showModal(); document.body.classList.add('lock'); };
    track.append(c);
  });
  dlg.addEventListener('close', () => document.body.classList.remove('lock'));
  dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
  const step = d => track.scrollBy({ left: d * (track.firstElementChild?.offsetWidth + 16 || 300), behavior: reduced ? 'auto' : 'smooth' });
  const prev = $('#slPrev'), next = $('#slNext');
  prev.onclick = () => step(-1); next.onclick = () => step(1);
  const edge = () => { prev.disabled = track.scrollLeft < 4; next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 4; };
  track.addEventListener('scroll', edge, { passive: true }); edge(); addEventListener('resize', edge);
  track.addEventListener('keydown', e => { if (e.key === 'ArrowRight') step(1); if (e.key === 'ArrowLeft') step(-1); });

  /* ---------- requirements ---------- */
  const OS = { mac: ['macOS 12 Monterey+', 'Apple Silicon M1+ atau Intel'], win: ['Windows 10 / 11 (64-bit)', 'Intel / AMD 64-bit'] };
  const setOS = k => { $('[data-req=os]').textContent = OS[k][0]; $('[data-req=cpu]').textContent = OS[k][1]; };
  group($('#osTabs'), 'button', b => setOS(b.dataset.os), 'aria-selected');
  setOS(/Win/i.test(navigator.platform) ? (($$('#osTabs button')[1].click()), 'win') : 'mac');

  /* ---------- kalkulator harga ---------- */
  const range = $('#calcRange'), per = $('#calcPer'), days = $('#calcDays'), out = $('#calcOut'), sc = $('#subCost'), sr = $('#subResult');
  const calc = () => {
    const d = +range.value; days.textContent = d; out.textContent = d >= 365 ? '1 tahun' : d + ' hari'; per.textContent = '≈ ' + rp(S.price / d);
    const cost = Math.max(0, +sc.value || 0), months = Math.max(1, Math.round(d / 30)), total = cost * months;
    sr.textContent = total > S.price ? `Dalam ${months} bulan, langganan lain ≈ ${rp(total)}. Kamu hemat ≈ ${rp(total - S.price)}.` : cost ? `Dalam ${months} bulan, langganan ≈ ${rp(total)}. Lifetime lebih hemat jika dipakai lebih lama.` : '';
  };
  range.addEventListener('input', calc); sc.addEventListener('input', calc); calc();

  /* ---------- FAQ ---------- */
  const fl = $('#faqList');
  (S.faq || []).forEach(([q, a], i) => {
    const id = 'faq' + i, item = el('div', { className: 'qa' });
    item.innerHTML = `<h3 style="font-size:inherit;letter-spacing:0"><button class="qa-q" type="button" aria-expanded="false" aria-controls="${id}"><span class="n">${String(i + 1).padStart(2, '0')}</span><span class="t"></span><span class="pm" aria-hidden="true">+</span></button></h3><div class="qa-a" id="${id}" role="region"><div><p></p></div></div>`;
    $('.t', item).textContent = q; $('p', item).textContent = a;
    const b = $('.qa-q', item); b.onclick = () => { const o = !item.classList.contains('open'); $$('.qa.open', fl).forEach(x => { x.classList.remove('open'); $('.qa-q', x).setAttribute('aria-expanded', 'false'); }); if (o) { item.classList.add('open'); b.setAttribute('aria-expanded', 'true'); } };
    fl.append(item);
  });
  const first = $('.qa-q', fl); first && first.click();
})();
