/* DR. NILESH SHAH'S MARKET ANALYSIS - web version (no build step, plain JavaScript). */
'use strict';

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const SIGNALS = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL'];
const SIG_LABEL = { 'STRONG BUY': 'Strong buy', BUY: 'Buy', HOLD: 'Hold', SELL: 'Sell', 'STRONG SELL': 'Strong sell' };
const SIG_VAR = { 'STRONG BUY': '--sb', BUY: '--buy', HOLD: '--hold', SELL: '--sell', 'STRONG SELL': '--ss' };
const SYMBOL_RE = /^[A-Z0-9][A-Z0-9&_.-]{0,19}$/;
const BATCH = 8;          // stocks per server call
const PARALLEL = 3;       // server calls at once
const PLOTLY_URL = 'https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js';
const NAMES = { rs: 'RS Rating', macd: 'MACD', ma: 'Moving Avg', boll: 'Bollinger', stoch: 'Stochastic', adx: 'ADX',
                vol: 'Volume', mom: 'Momentum', st: 'SuperTrend', vwap: 'VWAP' };

const state = {
  user: null, watchlist: [], results: [], failed: [], tooNew: [], when: null, scanning: false,
  sort: { key: 'symbol', asc: true }, selected: null, flash: new Set(), tab: 'results',
  chart: null, spin: null, settings: loadSettings(),
};

// ============================================================ settings, look, motion

function loadSettings() {
  try { return Object.assign({ theme: null, animations: true, liq: 1 }, JSON.parse(localStorage.getItem('drs-settings') || '{}')); }
  catch (e) { return { theme: null, animations: true, liq: 1 }; }
}
function saveSettings() { try { localStorage.setItem('drs-settings', JSON.stringify(state.settings)); } catch (e) { /* private window */ } }
function currentTheme() {
  return state.settings.theme || 'light';      // the Daylight design unless dark is chosen
}
function motionOn() { return state.settings.animations !== false && !matchMedia('(prefers-reduced-motion: reduce)').matches; }
function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function rgba(hex, a) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function applyTheme(theme, rerender = true) {
  state.settings.theme = theme;
  document.documentElement.dataset.theme = theme;
  saveSettings();
  syncThemeControls();
  if (rerender && state.chart && state.tab === 'charts') redrawChart();
}
function syncThemeControls() {
  const theme = currentTheme();
  $('#theme-btn').textContent = theme === 'dark' ? 'Light' : 'Dark';
  $('#theme-btn').setAttribute('aria-label', theme === 'dark' ? 'Switch to light colours' : 'Switch to dark colours');
  $$('#s-theme button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === theme)));
}
function applyMotion(on) {
  state.settings.animations = on;
  document.documentElement.classList.toggle('still', !on);
  saveSettings();
}

/** step(v) with v going 0 -> 1 (eased) over ms; jumps to the end when motion is off. */
function tween(ms, step, done) {
  if (!motionOn() || ms <= 0) { step(1); if (done) done(); return { cancel() {} }; }
  let cancelled = false; const t0 = performance.now();
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  const tick = (now) => {
    if (cancelled) return;
    const t = Math.min(1, (now - t0) / ms);
    step(ease(t));
    if (t < 1) requestAnimationFrame(tick); else if (done) done();
  };
  requestAnimationFrame(tick);
  return { cancel() { cancelled = true; } };
}
function countUp(el, to, decimals = 0, ms = 1000) {
  tween(ms, (v) => { el.textContent = (to * v).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }); });
}

// ============================================================ formatting

const money = (v) => (v == null ? 'N/A' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const signed = (v, d = 2, suffix = '') => (v == null ? 'N/A' : `${v > 0 ? '+' : ''}${Number(v).toFixed(d)}${suffix}`);
const n1 = (v) => (v == null ? 'N/A' : Number(v).toFixed(1));
const n0 = (v) => (v == null ? 'N/A' : String(Math.round(v)));

function marker(rec, size = 14) {
  const c = `var(${SIG_VAR[rec] || '--hold'})`;
  const s = size;
  const shapes = {
    'STRONG BUY': `<path d="M${s / 2} 0 L${s} ${s * 0.45} L0 ${s * 0.45}Z M${s / 2} ${s * 0.55} L${s} ${s} L0 ${s}Z"/>`,
    BUY: `<path d="M${s / 2} ${s * 0.1} L${s} ${s * 0.85} L0 ${s * 0.85}Z"/>`,
    HOLD: `<rect x="1" y="${s * 0.38}" width="${s - 2}" height="${s * 0.24}" rx="1"/>`,
    SELL: `<path d="M0 ${s * 0.15} L${s} ${s * 0.15} L${s / 2} ${s * 0.9}Z"/>`,
    'STRONG SELL': `<path d="M0 0 L${s} 0 L${s / 2} ${s * 0.45}Z M0 ${s * 0.55} L${s} ${s * 0.55} L${s / 2} ${s}Z"/>`,
  };
  return `<svg width="${s}" height="${s}" viewBox="0 0 ${s} ${s}" style="fill:${c};flex:none" aria-hidden="true">${shapes[rec] || ''}</svg>`;
}

// ============================================================ server calls

class ApiError extends Error { constructor(msg, status) { super(msg); this.status = status; } }

async function api(path, { method, body, allow401 = false } = {}) {
  const opts = { method: method || (body !== undefined ? 'POST' : 'GET'), headers: {}, credentials: 'same-origin' };
  if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(path, opts); }
  catch (e) { throw new ApiError('No connection to the server - check your internet.', 0); }
  let data = null;
  try { data = await res.json(); } catch (e) { /* not JSON */ }
  if (res.status === 401 && !allow401) { showLogin(); throw new ApiError('Please sign in', 401); }
  if (!res.ok) throw new ApiError((data && data.error) || `Server error (${res.status})`, res.status);
  return data;
}

// ============================================================ messages that slide in

function toast(title, msg = '', kind = 'info', ms = 6000) {
  const edge = { info: 'var(--accent)', good: 'var(--buy)', warn: 'var(--warning)', bad: 'var(--sell)' }[kind];
  const el = document.createElement('div');
  el.className = 'toast';
  el.style.setProperty('--edge', edge);
  el.innerHTML = `<b>${esc(title)}</b>${msg ? `<p>${esc(msg)}</p>` : ''}`;
  const close = () => { if (!el.isConnected) return; el.classList.add('out'); setTimeout(() => el.remove(), 220); };
  el.addEventListener('click', close);
  $('#toasts').appendChild(el);
  setTimeout(close, ms);
}

// ============================================================ sign in

let loginMode = 'in';
function setLoginMode(mode) {
  loginMode = mode;
  $('#mode-in').setAttribute('aria-pressed', String(mode === 'in'));
  $('#mode-new').setAttribute('aria-pressed', String(mode === 'new'));
  $('#invite-field').classList.toggle('hidden', mode !== 'new');
  $('#l-invite').required = mode === 'new';
  $('#l-pass').autocomplete = mode === 'new' ? 'new-password' : 'current-password';
  $('#l-submit').textContent = mode === 'new' ? 'Create account' : 'Sign in';
  $('#l-err').textContent = '';
}
function showLogin(message = '') {
  stopSpin();
  $('#app').classList.add('hidden');
  $('#login').classList.remove('hidden');
  $('#l-err').textContent = message;
  setTimeout(() => $('#l-name').focus(), 50);
}
async function submitLogin(e) {
  e.preventDefault();
  const body = { name: $('#l-name').value.trim(), password: $('#l-pass').value };
  if (loginMode === 'new') body.invite = $('#l-invite').value.trim();
  $('#l-submit').disabled = true;
  $('#l-err').textContent = '';
  try {
    await api(loginMode === 'new' ? '/api/signup' : '/api/login', { body, allow401: true });
    $('#l-pass').value = '';
    await boot();
  } catch (err) {
    $('#l-err').textContent = err.message;
  } finally {
    $('#l-submit').disabled = false;
  }
}

// ============================================================ start

async function boot() {
  let me;
  try { me = await api('/api/me', { allow401: true }); }
  catch (err) { showLogin(err.status === 401 ? '' : err.message); return; }
  state.user = me.name;
  $('#login').classList.add('hidden');
  $('#app').classList.remove('hidden');
  $('#who').textContent = me.name;
  const [wl, last] = await Promise.all([api('/api/watchlist'), api('/api/scan/last')]);
  state.watchlist = wl.symbols || [];
  state.results = last.results || [];
  state.when = last.when ? new Date(last.when) : null;
  renderWatchlist();
  renderResults();
  renderSummary(true);
  loadCompanies();
  selectTab(state.watchlist.length ? 'results' : 'watchlist');
  if (!state.watchlist.length) toast('Welcome', "Add your stocks: type the first letters of a company's name above and pick it from the list.", 'info', 8000);
}

// ============================================================ market light (NSE 09:15-15:30, Mon-Fri, Indian time)

function updateMarket() {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false })
    .formatToParts(new Date()).map((p) => [p.type, p.value]));
  const mins = Number(parts.hour) * 60 + Number(parts.minute);
  const open = !['Sat', 'Sun'].includes(parts.weekday) && mins >= 555 && mins <= 930;
  $('#m-dot').classList.toggle('open', open);
  $('#m-text').textContent = open ? 'Market open' : 'Market closed';
}

// ============================================================ tabs with a sliding underline

function selectTab(name) {
  state.tab = name;
  $$('#tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
  $$('section[role=tabpanel]').forEach((p) => { p.hidden = p.id !== `p-${name}`; });
  moveTabLine();
  if (name === 'charts') fillChartSymbols();
}
function moveTabLine() {
  const b = $(`#tabs button[data-tab="${state.tab}"]`);
  if (!b) return;
  const line = $('#tab-line');
  line.style.left = `${b.offsetLeft + 8}px`;
  line.style.width = `${Math.max(b.offsetWidth - 16, 8)}px`;
}

// ============================================================ summary card

function renderSummary(animate = false) {
  const el = $('#summary');
  const rs = state.results;
  if (!rs.length) {
    el.innerHTML = '<div class="empty-sum">Scan your watchlist to see how many stocks are buy, hold or sell.</div>';
    return;
  }
  const counts = Object.fromEntries(SIGNALS.map((k) => [k, rs.filter((r) => r.rec === k).length]));
  const avg = rs.reduce((a, r) => a + r.score, 0) / rs.length;
  el.innerHTML = `
    <div><div class="big num" id="sum-n">${rs.length}</div><div class="sub">stocks scanned</div></div>
    <div><div class="big accent num" id="sum-avg">${avg.toFixed(1)}</div><div class="sub">average score</div></div>
    <div class="dist-box">
      <div class="dist">${SIGNALS.filter((k) => counts[k]).map((k) => `<i data-w="${(counts[k] / rs.length) * 100}" style="background:var(${SIG_VAR[k]})" title="${SIG_LABEL[k]}: ${counts[k]}"></i>`).join('')}</div>
      <div class="legend">${SIGNALS.map((k) => `<span>${marker(k, 11)} ${SIG_LABEL[k]}<b class="num">${counts[k]}</b></span>`).join('')}</div>
    </div>
    <div class="when">${state.when ? `Last scan<br>${esc(state.when.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }))}` : ''}</div>`;
  const bars = $$('.dist i', el);
  if (animate) {
    countUp($('#sum-n', el), rs.length);
    countUp($('#sum-avg', el), avg, 1);
    requestAnimationFrame(() => requestAnimationFrame(() => bars.forEach((b) => { b.style.width = `${b.dataset.w}%`; })));
  } else {
    bars.forEach((b) => { b.style.transition = 'none'; b.style.width = `${b.dataset.w}%`; });
  }
}

// ============================================================ company list (NSE + BSE) and its search

// Each company: [name, nse, bse, bseCode, marketCap, add] - `add` is what goes into the watchlist.
const companies = { list: null, loading: null, names: new Map() };
const keyWords = (text) => text.toLowerCase().replace(/[^a-z0-9& ]+/g, ' ').split(' ').filter(Boolean);

function loadCompanies() {
  if (!companies.loading) {
    companies.loading = fetch('symbols.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((d) => {
      companies.list = d.companies.map((e) => ({ e, nse: e[1].toLowerCase(), bse: e[2].toLowerCase(), words: keyWords(e[0]) }));
      d.companies.forEach((e) => [e[5], e[1], e[2]].forEach((k) => { if (k && !companies.names.has(k)) companies.names.set(k, e[0]); }));
      renderWatchlist();
    }).catch(() => { companies.loading = null; });
  }
  return companies.loading;
}
const companyName = (symbol) => companies.names.get(symbol) || '';

/** Best matches first: exact symbol or code, symbol starts with it, name starts with it, each typed
 *  word starts a word of the name, then anywhere. Among equals, bigger companies first (list order). */
function searchCompanies(query, limit = 8) {
  const q = query.trim().toLowerCase(), words = keyWords(query);
  if (!companies.list || !q || !words.length) return [];
  const compact = q.replace(/ /g, ''), joined = words.join(' ');
  const found = [];
  companies.list.forEach((c, i) => {
    let rank;
    if ([c.nse, c.bse, c.e[3], c.e[5].toLowerCase()].includes(compact)) rank = 0;
    else if (c.nse.startsWith(compact) || c.bse.startsWith(compact)) rank = 1;
    else if (c.words.join(' ').startsWith(joined)) rank = 2;
    else if (words.every((t) => c.words.some((w) => w.startsWith(t)))) rank = 3;
    else if (compact.length >= 3 && (c.nse.includes(compact) || c.bse.includes(compact) || c.words.join('').includes(compact))) rank = 4;
    else return;
    found.push([rank, i, c.e]);
  });
  found.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return found.slice(0, limit).map((f) => f[2]);
}

// ---- the "Add a stock" box: type a name, pick from the list ----

const suggest = { items: [], active: -1, typed: '', timer: null, seq: 0 };

function highlight(name, query) {
  const words = keyWords(query);
  return name.split(/(\s+)/).map((part) => {
    const t = words.find((w) => part.toLowerCase().replace(/[^a-z0-9&]/g, '').startsWith(w));
    if (!t || !part.trim()) return esc(part);
    let n = 0, i = 0;                      // mark the letters that were typed (skipping punctuation)
    while (i < part.length && n < t.length) { if (/[a-z0-9&]/i.test(part[i])) n++; i++; }
    return `<mark>${esc(part.slice(0, i))}</mark>${esc(part.slice(i))}`;
  }).join('');
}

function renderSuggest() {
  const box = $('#add-list'), input = $('#add-input');
  const q = input.value.trim();
  if (q.length < 2) { closeSuggest(); return; }
  const rows = suggest.items.map((e, i) => {
    const have = state.watchlist.includes(e[5]);
    const nse = e[1] ? `<span class="ex"><small>NSE</small><b>${esc(e[1])}</b>${e[5].endsWith('-SM') ? '<i>SME</i>' : ''}</span>` : '<span class="ex none"><small>NSE</small>not listed</span>';
    const bse = e[2] ? `<span class="ex"><small>BSE</small><b>${esc(e[2])}</b>${e[3] ? `<i>${esc(e[3])}</i>` : ''}</span>` : '<span class="ex none"><small>BSE</small>not listed</span>';
    return `<li role="option" id="sg-${i}" data-i="${i}" aria-selected="${i === suggest.active}">
      <div class="s-name">${highlight(e[0], q)}</div>
      <div class="s-ex">${nse}${bse}${have ? '<span class="tag">In your watchlist</span>' : ''}${e.live ? '<span class="tag new">New listing</span>' : ''}</div></li>`;
  });
  const typed = q.toUpperCase().replace(/\.(NS|BO)$/, '');
  let note = '';
  if (!companies.list) note = 'Loading the company list...';
  else if (!rows.length) note = SYMBOL_RE.test(typed) && !q.includes(' ') ? `No company found. Press Enter to add ${esc(typed)} as typed.` : 'No company found. Check the spelling, or type its exchange symbol.';
  box.innerHTML = rows.join('') + (note ? `<li class="note" role="presentation">${note}</li>` : '');
  box.classList.remove('hidden');
  input.setAttribute('aria-expanded', 'true');
  input.setAttribute('aria-activedescendant', suggest.active >= 0 ? `sg-${suggest.active}` : '');
  const act = $(`#sg-${suggest.active}`);
  if (act) act.scrollIntoView({ block: 'nearest' });
}

function closeSuggest() {
  $('#add-list').classList.add('hidden');
  $('#add-input').setAttribute('aria-expanded', 'false');
  suggest.items = []; suggest.active = -1;
}

function updateSuggest() {
  const q = $('#add-input').value.trim();
  suggest.typed = q;
  clearTimeout(suggest.timer);
  suggest.seq++;
  if (q.length < 2) { closeSuggest(); return; }
  const run = () => {
    if (suggest.typed !== q) return;
    suggest.items = searchCompanies(q);
    suggest.active = suggest.items.length ? 0 : -1;
    renderSuggest();
    liveSearch(q);
  };
  if (companies.list) run();
  else { renderSuggest(); loadCompanies().then(run); }
}

/** A company too new for the list (just listed): ask the server, which looks it up on Yahoo Finance. */
function liveSearch(q) {
  if (q.length < 3 || suggest.items.length >= 3) return;
  const seq = ++suggest.seq;
  suggest.timer = setTimeout(async () => {
    let res;
    try { res = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { return; }
    if (seq !== suggest.seq || suggest.typed !== q) return;
    const have = new Set(suggest.items.map((e) => e[5]));
    const extra = (res.companies || []).filter((e) => e[5] && !have.has(e[5])).map((e) => Object.assign(e, { live: true }));
    if (!extra.length) return;
    suggest.items = [...suggest.items, ...extra].slice(0, 10);
    if (suggest.active < 0) suggest.active = 0;
    renderSuggest();
  }, 400);
}

async function chooseCompany(e) {
  const input = $('#add-input');
  if (state.watchlist.includes(e[5])) { toast('Already in your watchlist', `${e[5]}: ${e[0]}`, 'info', 3500); }
  else {
    if (!companies.names.has(e[5])) companies.names.set(e[5], e[0]);
    try { await saveWatchlist([...state.watchlist, e[5]].sort()); toast(`Added ${e[5]}`, e[0], 'good', 3500); }
    catch (err) { toast("Couldn't add", err.message, 'bad'); return; }
  }
  input.value = ''; closeSuggest(); input.focus();
}

async function submitAdd() {
  const input = $('#add-input');
  if (suggest.active >= 0 && suggest.items[suggest.active]) { await chooseCompany(suggest.items[suggest.active]); return; }
  // nothing in the list matched: a symbol typed as it is can still be added (several, with commas)
  const raw = input.value.trim();
  const list = parseSymbols(raw);
  if (!list.length || (!raw.includes(',') && /\s/.test(raw))) {
    toast('Pick a company from the list', 'Type the first letters of its name, or its NSE/BSE symbol.', 'warn', 4000);
    return;
  }
  try { await addSymbols(list); input.value = ''; closeSuggest(); } catch (err) { toast("Couldn't add", err.message, 'bad'); }
}

// ============================================================ watchlist

function renderWatchlist() {
  const box = $('#chips');
  $('#wl-count').textContent = `${state.watchlist.length} ${state.watchlist.length === 1 ? 'stock' : 'stocks'}`;
  if (!state.watchlist.length) {
    box.innerHTML = '<div class="empty" style="grid-column:1/-1">Your watchlist is empty. Add a stock above, or paste many below.</div>';
    return;
  }
  box.innerHTML = state.watchlist.map((s) => `<div class="chip" title="${esc(companyName(s))}"><span>${esc(s)}<small>${esc(companyName(s))}</small></span><button type="button" data-del="${esc(s)}" aria-label="Remove ${esc(s)}">&#x2715;</button></div>`).join('');
}
function parseSymbols(text) {
  return [...new Set(String(text).toUpperCase().split(/[\s,;"'[\]]+/).map((s) => s.replace(/\.(NS|BO)$/, '')).filter((s) => SYMBOL_RE.test(s)))];
}
async function saveWatchlist(list, message) {
  const res = await api('/api/watchlist', { method: 'PUT', body: { symbols: list } });
  state.watchlist = res.symbols;
  renderWatchlist();
  if (message) toast(message, `${state.watchlist.length} stocks in your watchlist.`, 'good', 3500);
}
// ---- the watchlist as a file: save a copy, load one back (the desktop app's own formats) ----

const FILE_HEADINGS = new Set(['SYMBOL', 'SYMBOLS', 'STOCK', 'STOCKS', 'SCRIP', 'SCRIPS', 'TICKER', 'TICKERS', 'NAME', 'WATCHLIST', 'COMPANY']);

/** What "Save watchlist" writes: {name, text, type}. */
function watchlistFile(format) {
  const day = new Date().toLocaleDateString('en-CA');
  const list = [...state.watchlist].sort();
  if (format === 'csv') {
    const cell = (v) => (/[",\r\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
    const rows = [['Symbol', 'Company'], ...list.map((s) => [s, companyName(s)])];
    return { name: `my_watchlist_${day}.csv`, type: 'text/csv', text: '\uFEFF' + rows.map((r) => r.map(cell).join(',')).join('\r\n') + '\r\n' };
  }
  if (format === 'txt') return { name: `my_watchlist_${day}.txt`, type: 'text/plain', text: list.join('\r\n') + '\r\n' };
  return { name: `my_watchlist_${day}.json`, type: 'application/json',
           text: JSON.stringify({ watchlist: list, date: new Date().toISOString(), app: "DR. NILESH SHAH'S Analysis" }, null, 2) };
}

async function saveWatchlistFile() {
  if (!state.watchlist.length) { toast('Nothing to save yet', 'Add stocks to your watchlist first.', 'warn'); return; }
  await loadCompanies();                         // company names for the CSV
  const file = watchlistFile($('#wl-format').value);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([file.text], { type: `${file.type};charset=utf-8` }));
  a.download = file.name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  toast('Watchlist saved', `${file.name} (${state.watchlist.length} stocks) is in your Downloads.`, 'good', 5000);
}

/** The symbols in a saved watchlist file: JSON (the desktop app's or a plain list), CSV (first column) or text. */
function symbolsInFile(name, text) {
  text = text.replace(/^\uFEFF/, '');
  const ext = name.split('.').pop().toLowerCase();
  let items;
  if (ext === 'json') {
    const data = JSON.parse(text);
    items = Array.isArray(data) ? data : (data && Array.isArray(data.watchlist) ? data.watchlist : []);
  } else if (ext === 'csv') {
    items = text.split(/\r?\n/).map((line) => { const m = line.match(/^\s*"((?:[^"]|"")*)"/); return m ? m[1].replace(/""/g, '"') : line.split(',')[0]; });
  } else {
    items = text.split(/\r?\n/);
  }
  const given = items.map((x) => String(x ?? '').trim()).filter(Boolean);
  const symbols = [...new Set(given.map((x) => x.toUpperCase().replace(/\.(NS|BO)$/, '')).filter((s) => SYMBOL_RE.test(s) && !FILE_HEADINGS.has(s)))];
  return { symbols, given: given.filter((x) => !FILE_HEADINGS.has(x.toUpperCase())).length };
}

async function loadWatchlistFile(file) {
  if (file.size > 1024 * 1024) { toast('That file is too big', 'A watchlist file is a few kilobytes - pick the right file.', 'warn'); return; }
  let found;
  try { found = symbolsInFile(file.name, await file.text()); }
  catch (err) { toast("Couldn't read that file", 'It should be a watchlist saved here or by the desktop app (JSON, CSV or text).', 'bad'); return; }
  if (!found.symbols.length) { toast('No stocks found in that file', 'It should list one symbol per line, or be a watchlist saved here or by the desktop app.', 'warn'); return; }
  const fresh = found.symbols.filter((s) => !state.watchlist.includes(s));
  const already = found.symbols.length - fresh.length, skipped = found.given - found.symbols.length;
  const notes = [already ? `${already} already in your watchlist` : '', skipped > 0 ? `${skipped} lines skipped (not symbols)` : ''].filter(Boolean);
  if (!fresh.length) { toast('Nothing new in that file', notes.join('; ') + '.', 'info', 5000); return; }
  const wanted = [...state.watchlist, ...fresh].sort();
  try { await saveWatchlist(wanted); }
  catch (err) { toast("Couldn't load the file", err.message, 'bad'); return; }
  if (state.watchlist.length < wanted.length) notes.push(`${wanted.length - state.watchlist.length} left out: a watchlist holds up to ${state.watchlist.length} stocks`);
  const added = fresh.length - (wanted.length - state.watchlist.length);
  toast(`Added ${added} ${added === 1 ? 'stock' : 'stocks'} from ${file.name}`, notes.join('; ') || `${state.watchlist.length} stocks in your watchlist.`, 'good', 6000);
}

async function addSymbols(list) {
  const fresh = list.filter((s) => !state.watchlist.includes(s));
  if (!fresh.length) { toast('Already in your watchlist', list.join(', '), 'info', 3500); return; }
  await saveWatchlist([...state.watchlist, ...fresh].sort(), fresh.length === 1 ? `Added ${fresh[0]}` : `Added ${fresh.length} stocks`);
}

// ============================================================ scan, in batches

async function scanAll() {
  if (state.scanning) return;
  const symbols = [...state.watchlist];
  if (!symbols.length) { toast('Add stocks first', 'Your watchlist is empty.', 'warn'); selectTab('watchlist'); return; }
  state.scanning = true;
  const btn = $('#scan-btn');
  btn.disabled = true; btn.textContent = 'Scanning...';
  state.results = []; state.failed = []; state.tooNew = []; state.flash.clear();
  selectTab('results');
  renderResults(); renderSummary();
  const batches = [];
  for (let i = 0; i < symbols.length; i += BATCH) batches.push(symbols.slice(i, i + BATCH));
  let done = 0, problem = null;
  const progress = () => {
    $('#prog').style.width = `${(done / symbols.length) * 100}%`;
    $('#status').textContent = `Scanned ${done} of ${symbols.length}...`;
  };
  progress();
  const queue = [...batches];
  const worker = async () => {
    while (queue.length) {
      const batch = queue.shift();
      let res = null;
      for (let attempt = 0; attempt < 2 && !res; attempt++) {
        try { res = await api('/api/scan', { body: { symbols: batch } }); }
        catch (err) {
          if (err.status === 401) throw err;
          problem = err.message;
          if (attempt === 0) await new Promise((r) => setTimeout(r, 1500));
        }
      }
      if (res) {
        state.results.push(...res.results);
        state.failed.push(...res.failed);
        state.tooNew.push(...res.too_new);
      } else {
        state.failed.push(...batch);
      }
      done += batch.length;
      progress();
      renderResults();
    }
  };
  try {
    await Promise.all(Array.from({ length: Math.min(PARALLEL, batches.length) }, worker));
  } catch (err) {
    state.scanning = false; btn.disabled = false; btn.textContent = 'Scan all stocks';
    return;
  }
  state.results.sort((a, b) => a.symbol.localeCompare(b.symbol));
  state.when = new Date();
  const changes = state.results.filter((r) => r.prev_rec && r.prev_rec !== r.rec);
  changes.forEach((r) => state.flash.add(r.symbol));
  renderResults();
  renderSummary(true);
  setTimeout(() => { state.flash.clear(); }, 3000);
  $('#prog').style.width = '100%';
  $('#status').textContent = 'Complete';
  state.scanning = false; btn.disabled = false; btn.textContent = 'Scan all stocks';
  if (state.results.length) {
    api('/api/scan/save', { body: { results: state.results } }).catch((err) => toast("Couldn't save this scan", err.message, 'warn'));
  }
  const lines = [];
  if (state.failed.length) lines.push(`${state.failed.length} failed: ${state.failed.slice(0, 6).join(', ')}${problem && !state.results.length ? ` (${problem})` : ''}`);
  if (state.tooNew.length) lines.push(`${state.tooNew.length} listed under 3 trading days ago: ${state.tooNew.slice(0, 5).join(', ')}`);
  if (changes.length) {
    lines.push(`Signal changes since the last scan (${changes.length}): ` + changes.slice(0, 4).map((r) => `${r.symbol}: ${r.prev_rec} to ${r.rec}`).join('; ')
      + (changes.length > 4 ? `; and ${changes.length - 4} more` : ''));
  }
  toast(`Scan complete: ${state.results.length} stocks`, lines.join('\n') || 'No signal changes since your last scan.',
    state.failed.length ? 'warn' : 'good', changes.length || state.failed.length ? 10000 : 6000);
}

// ============================================================ results table

const COLS = [
  { key: 'mk', label: '', cls: 'mk', nosort: true },
  { key: 'symbol', label: 'Symbol', cls: 'text sym', text: true },
  { key: 'price', label: 'Price', fmt: money },
  { key: 'change', label: 'Change %', fmt: (v) => signed(v, 2, '%') },
  { key: 'rs3', label: 'vs Nifty 3M', get: (r) => (r.rs ? r.rs['3M'] : null), fmt: (v) => signed(v, 1, '%') },
  { key: 'rs_rating', label: 'RS', fmt: n0 },
  { key: 'score', label: 'Score', fmt: n1 },
  { key: 'chg', label: 'Score Chg', get: (r) => (r.prev_score == null ? null : r.score - r.prev_score), fmt: (v) => (v == null ? 'new' : signed(v, 1)) },
  { key: 'rec', label: 'Signal', cls: 'text', text: true },
  { key: 'st_sig', label: 'SuperTrend', cls: 'text', text: true },
  { key: 'vwap_sig', label: 'VWAP', cls: 'text', text: true },
  { key: 'high52', label: '52W High', fmt: money },
  { key: 'low52', label: '52W Low', fmt: money },
  { key: 'liquidity_cr', label: 'Traded/day (Cr)', fmt: (v) => (v == null ? 'N/A' : v < 100 ? Number(v).toFixed(2) : Math.round(v).toLocaleString('en-IN')) },
  { key: 'candle', label: 'Candle', cls: 'text', text: true, get: (r) => (r.hourly ? '1 Hour' : 'Daily') },
];
const colValue = (c, r) => (c.get ? c.get(r) : r[c.key]);
const illiquid = (r) => (r.liquidity_cr ?? 0) < (Number(state.settings.liq) || 0);

/** The stocks the table shows - Find / Show / Hide illiquid applied, in the chosen order. */
function visibleRows() {
  const q = $('#f-q').value.trim().toUpperCase(), rec = $('#f-rec').value, hideLow = $('#f-liq').checked;
  const rows = state.results.filter((r) => (!q || r.symbol.includes(q)) && (rec === 'All' || r.rec === rec) && (!hideLow || !illiquid(r)));
  const col = COLS.find((c) => c.key === state.sort.key) || COLS[1];
  const dir = state.sort.asc ? 1 : -1;
  return rows.sort((a, b) => {
    const x = colValue(col, a), y = colValue(col, b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return (col.text ? String(x).localeCompare(String(y)) : x - y) * dir;
  });
}

function renderResults() {
  const box = $('#results-box');
  $('#f-liq-text').textContent = `Hide illiquid (under Rs ${Number(state.settings.liq) || 0} Cr/day)`;
  if (!state.results.length && !state.failed.length && !state.tooNew.length) {
    box.innerHTML = `<div class="empty">${state.scanning ? 'Scanning...' : 'No scan yet. Click "Scan all stocks".'}</div>`;
    return;
  }
  const q = $('#f-q').value.trim().toUpperCase();
  const rows = visibleRows();
  const head = COLS.map((c) => `<th class="${c.cls || ''}" ${c.nosort ? '' : `data-sort="${c.key}"`} scope="col">${esc(c.label)}${state.sort.key === c.key ? `<span class="arrow">${state.sort.asc ? '&#9650;' : '&#9660;'}</span>` : ''}</th>`).join('');
  const body = rows.map((r, i) => {
    const tint = r.rec.includes('BUY') ? 'tb' : r.rec.includes('SELL') ? 'ts' : i % 2 ? 'zebra' : '';
    const cells = COLS.map((c) => {
      if (c.key === 'mk') return `<td class="mk">${marker(r.rec)}</td>`;
      let v = colValue(c, r);
      let text = c.fmt ? c.fmt(v) : (v ?? '');
      if (c.key === 'liquidity_cr' && illiquid(r)) text = `${text}<span class="low">LOW</span>`;
      else text = esc(text);
      return `<td class="${c.cls || ''} ${c.text ? '' : 'num'}">${text}</td>`;
    }).join('');
    return `<tr class="${tint} ${state.flash.has(r.symbol) ? 'flash' : ''}" data-sym="${esc(r.symbol)}" tabindex="0">${cells}</tr>`;
  }).join('');
  const errs = [...state.failed.map((s) => [s, 'No data / delisted']), ...state.tooNew.map((s) => [s, 'Listed under 3 trading days ago'])]
    .filter(([s]) => !q || s.includes(q))
    .map(([s, why]) => `<tr class="err"><td class="mk"></td><td class="text sym">${esc(s)}</td><td colspan="${COLS.length - 2}" class="text">${esc(why)}</td></tr>`).join('');
  box.innerHTML = `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}${errs}</tbody></table></div>
    <p class="small-note">${rows.length} of ${state.results.length} stocks. Tap a stock for its details. Click a column to sort.</p>`;
}

// ============================================================ stock details

function showDetails(symbol) {
  const r = state.results.find((x) => x.symbol === symbol);
  if (!r) return;
  state.selected = symbol;
  const t = r.targets || {};
  const color = `var(${SIG_VAR[r.rec]})`;
  const rs = r.rs || {};
  const rsHtml = Object.entries(rs).map(([k, v]) => `<span class="${v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : ''}">${esc(k)} ${v == null ? 'N/A' : signed(v, 1, '%')}</span>`).join('');
  const rs3 = rs['3M'];
  const bd = r.breakdown || {};
  const bars = Object.keys(NAMES).filter((k) => k in bd).map((k) => [k, bd[k]]).map(([k, v], i) => {
    const c = v >= 70 ? '--sb' : v >= 50 ? '--buy' : v >= 30 ? '--hold' : '--sell';
    const word = v >= 70 ? 'Strong' : v >= 50 ? 'Good' : v >= 30 ? 'Weak' : 'Bearish';
    return `<div class="r"><span>${esc(NAMES[k] || k)}</span><div class="track"><i data-w="${v}" style="background:var(${c});transition-delay:${i * 45}ms"></i></div><span class="v num">${v}</span><span class="w">${word}</span></div>`;
  }).join('');
  const basis = t.basis || {};
  const why = (k, text) => (basis[k] ? `${text} | ${basis[k].charAt(0).toUpperCase()}${basis[k].slice(1)}` : text);
  const levels = [
    ['Stop loss', t.sl, '--sell', why('sl', t.pos === 'SHORT' ? 'Exit if price rises above' : 'Exit if price falls below')],
    ['Target 1 (conservative)', t.t1, '--buy', why('t1', 'Book partial profits')],
    ['Target 2 (moderate)', t.t2, '--sb', why('t2', 'Main target - book 50%')],
    ['Target 3 (aggressive)', t.t3, '--accent', why('t3', 'Trail stop loss')],
  ];
  const rr = t.rr || 0;
  const rrColor = rr >= 2 ? '--sb' : rr >= 1.5 ? '--success' : rr >= 1 ? '--warning' : '--danger2';
  const quality = rr >= 2 ? 'Excellent' : rr >= 1.5 ? 'Good' : rr >= 1 ? 'Acceptable' : 'Poor';
  const pct = (a) => (t.price > 0 ? `${((a / t.price) * 100).toFixed(1)}% of the price` : '');
  const advice = r.rec.includes('BUY') ? `Enter at ${money(t.price)}, stop-loss ${money(t.sl)}, target ${money(t.t1)} (risk ${pct(t.risk || 0)})`
    : r.rec.includes('SELL') ? `Exit at ${money(t.price)}, stop-loss ${money(t.sl)}, target ${money(t.t1)}`
      : `Support ${money(t.sl)}, resistance ${money(t.t1)} - wait for a breakout`;
  const p = r.patterns || {};
  const sum = p.summary || {};
  const patSection = (title, items, long) => (items && items.length ? `<div class="card pad"><h3>${esc(title)}</h3>${items.map((x) => {
    const sig = String(x.signal || '').toUpperCase();
    const cls = sig === 'BULLISH' ? 'bull' : sig === 'BEARISH' ? 'bear' : 'neutral';
    return `<div class="pattern"><b>${esc(x.name)}</b><span class="badge ${cls}">${esc(sig.charAt(0) + sig.slice(1).toLowerCase())}</span>${long && x.description ? `<div class="desc">${esc(x.description)}</div>` : ''}</div>`;
  }).join('')}</div>` : '');
  const patterns = patSection('Chart patterns', p.chart, true) + patSection('Candlestick patterns', p.candlestick, false) + patSection('Harmonic patterns', p.harmonic, true);

  $('#p-details').innerHTML = `<div class="detail">
    <h2>${esc(r.symbol)} <span class="pill">${marker(r.rec, 12)} ${esc(SIG_LABEL[r.rec])}</span>
      <button class="btn small" type="button" id="d-chart">Price chart</button>
      <button class="btn small" type="button" id="d-pdf" title="Download this stock's analysis as a PDF file">PDF</button>
      ${companyName(r.symbol) ? `<span class="co">${esc(companyName(r.symbol))}</span>` : ''}</h2>
    ${r.hourly ? `<div class="note info">New listing (${esc(r.days)} trading days of history): analysed on 1-hour candles, so the stop-loss and targets sit closer to the price.</div>` : ''}
    ${illiquid(r) ? `<div class="note warn">Low liquidity: only about Rs ${Number(r.liquidity_cr || 0).toFixed(2)} crore traded per day. Price can gap past the stop-loss and orders may not fill.</div>` : ''}
    <div class="card pad head-card">
      ${ringSVG(r.score, color, SIG_LABEL[r.rec])}
      <div class="facts">
        <div class="rec">${esc(r.rec)}</div>
        <div class="line">Price ${money(r.price)}, ${signed(r.change, 2, '%')} on the day</div>
        <div class="rs"><span>RS rating:</span><span class="${r.rs_rating == null ? '' : r.rs_rating >= 90 ? 'up' : r.rs_rating < 50 ? 'down' : ''}">${n0(r.rs_rating)}${r.rs_rating >= 90 ? ' (best: 90 and above)' : ''}</span></div>
        <div class="rs"><span>vs Nifty 50:</span>${rsHtml}</div>
        ${rs3 != null ? `<div class="small-note" style="margin-top:6px">Over 3 months the stock is ${rs3 > 0 ? 'beating' : 'lagging'} the market by ${Math.abs(rs3).toFixed(1)} percentage points.</div>` : ''}
      </div>
    </div>
    <div class="grid2">
      <div class="card pad"><h3>What makes up the score (each part 0 to 100)</h3><div class="bars">${bars}</div></div>
      <div class="card pad"><h3>Score history</h3><div id="spark"><p class="small-note">Builds up as you scan on different days - one point per day.</p></div></div>
    </div>
    <div class="card pad ladder"><h3>Where the stop-loss and targets sit</h3><div id="ladder"></div></div>
    <div class="levels">${levels.map(([k, v, c, w]) => `<div class="card level" style="--edge:var(${c})"><div class="k">${esc(k)}</div><div class="val num">${money(v)}</div><div class="why">${esc(w)}</div></div>`).join('')}</div>
    <div class="grid2">
      <div class="card pad"><h3>Risk-reward</h3>
        <div class="rr">
          <div class="box" style="background:var(--risk-bg);color:var(--risk-fg)"><div class="k">Risk</div><div class="val num">${money(t.risk)}</div><div>${pct(t.risk || 0)}</div></div>
          <div class="arrow">&#8594;</div>
          <div class="box" style="background:var(--reward-bg);color:var(--reward-fg)"><div class="k">Reward</div><div class="val num">${money(t.reward)}</div><div>${pct(t.reward || 0)}</div></div>
        </div>
        <div class="ratio" style="color:var(${rrColor})"><div class="val num">${rr > 0 ? `1 : ${rr.toFixed(2)}` : 'N/A'}</div><b>Quality: ${quality}</b></div>
        <p class="small-note">Risk = from the price to the stop-loss. Reward = from the price to ${t.pos === 'HOLD' ? 'target 1' : 'target 2'}.</p>
      </div>
      <div class="card pad"><h3>Trading advice</h3><p>${esc(advice)}</p>
        <h3 style="margin-top:14px">Patterns</h3>
        <p class="small-note">${sum.total_patterns || 0} found: ${sum.bullish_count || 0} bullish, ${sum.bearish_count || 0} bearish. Overall: ${esc(sum.overall_signal || 'N/A')}</p>
      </div>
    </div>
    ${patterns || '<p class="small-note">No chart or candlestick patterns detected.</p>'}
  </div>`;
  selectTab('details');
  window.scrollTo({ top: $('#tabs').offsetTop - 10, behavior: motionOn() ? 'smooth' : 'auto' });
  $('#d-chart').addEventListener('click', () => { selectTab('charts'); $('#c-sym').value = r.symbol; showPriceChart(); });
  $('#d-pdf').addEventListener('click', (e) => downloadPdf(e.currentTarget, () => buildStockPdf(r), `${r.symbol}_analysis`));

  // grow the bars, sweep the ring, slide the ladder out
  requestAnimationFrame(() => requestAnimationFrame(() => {
    $$('#p-details .track i').forEach((b) => { b.style.width = `${b.dataset.w}%`; });
    const arc = $('#p-details .arc');
    if (arc) arc.style.strokeDashoffset = arc.dataset.target;
  }));
  countUp($('#p-details .ring-num'), r.score, 1, 900);
  drawLadder(t);
  loadSpark(r.symbol);
}

function ringSVG(score, color, label) {
  const c = 2 * Math.PI * 70;
  return `<svg class="ring" viewBox="0 0 168 168" role="img" aria-label="Score ${esc(score)} out of 100">
    <circle class="rt" cx="84" cy="84" r="70"></circle>
    <circle class="arc" cx="84" cy="84" r="70" style="stroke:${color}" stroke-dasharray="${c}" stroke-dashoffset="${c}" data-target="${c * (1 - Math.max(0, Math.min(100, score)) / 100)}"></circle>
    <text class="ring-num num" x="84" y="88" font-size="32" font-weight="700">0.0</text>
    <text x="84" y="114" font-size="12.5" font-weight="700" style="fill:var(--fg2)">${esc(label)}</text></svg>`;
}

function drawLadder(t) {
  const box = $('#ladder');
  if (!box || !t.price) return;
  const pts = [['Stop', t.sl, '--sell'], ['T1', t.t1, '--buy'], ['T2', t.t2, '--sb'], ['T3', t.t3, '--accent']].filter((p) => p[1]);
  const vals = [t.price, ...pts.map((p) => p[1])];
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || t.price * 0.01 || 1;
  const draw = (v) => {
    const w = box.clientWidth || 600, x0 = 40, x1 = w - 40, y = 48;
    const pos = (val) => x0 + ((val - lo) / span) * (x1 - x0);
    const px = pos(t.price);
    const far = [...pts].sort((a, b) => Math.abs(b[1] - t.price) - Math.abs(a[1] - t.price));
    let svg = `<svg viewBox="0 0 ${w} 110" role="img" aria-label="Stop-loss and targets relative to the price"><rect x="${x0 - 6}" y="${y - 3}" width="${x1 - x0 + 12}" height="6" rx="3" style="fill:var(--surface-2)"></rect>`;
    far.forEach(([, val, c]) => { svg += `<line x1="${px}" y1="${y}" x2="${px + (pos(val) - px) * v}" y2="${y}" style="stroke:var(${c})" stroke-width="3"></line>`; });
    [...pts].sort((a, b) => a[1] - b[1]).forEach(([lbl, val, c], i) => {
      const x = px + (pos(val) - px) * v, up = i % 2 === 0;
      svg += `<circle cx="${x}" cy="${y}" r="7" style="fill:var(${c});stroke:var(--surface)" stroke-width="2"></circle>
        <text x="${x}" y="${up ? y - 26 : y + 40}" text-anchor="middle" font-size="12" font-weight="700" style="fill:var(--fg)">${money(val)}</text>
        <text x="${x}" y="${up ? y - 13 : y + 26}" text-anchor="middle" font-size="11" style="fill:var(--fg2)">${lbl}</text>`;
    });
    svg += `<rect x="${px - 2}" y="${y - 13}" width="4" height="26" style="fill:var(--fg)"></rect>
      <text x="${px}" y="${y + 58}" text-anchor="middle" font-size="12" font-weight="700" style="fill:var(--fg)">Price ${money(t.price)}</text></svg>`;
    box.innerHTML = svg;
  };
  draw(0);
  setTimeout(() => tween(800, draw), 80);
  box._redraw = () => draw(1);
}

async function loadSpark(symbol) {
  let data;
  try { data = await api(`/api/history?symbol=${encodeURIComponent(symbol)}`); } catch (e) { return; }
  const pts = data.points || [];
  const box = $('#spark');
  if (!box || pts.length < 2 || state.selected !== symbol) return;
  const w = box.clientWidth || 400, h = 150, l = 30, r = 10, top = 10, bot = 24;
  const x = (i) => l + (i / (pts.length - 1)) * (w - l - r);
  const y = (v) => top + (1 - v / 100) * (h - top - bot);
  const ref = [[75, '--sb'], [60, '--buy'], [45, '--hold'], [30, '--sell']]
    .map(([v, c]) => `<line x1="${l}" x2="${w - r}" y1="${y(v)}" y2="${y(v)}" style="stroke:var(${c})" stroke-dasharray="4 4" stroke-width="1"></line><text x="${l - 6}" y="${y(v) + 4}" text-anchor="end" font-size="10" style="fill:var(--fg3)">${v}</text>`).join('');
  const line = pts.map((p, i) => `${x(i)},${y(p.score)}`).join(' ');
  box.innerHTML = `<svg class="spark" viewBox="0 0 ${w} ${h}" role="img" aria-label="Score history">${ref}
    <polyline points="${line}" fill="none" style="stroke:var(--series0)" stroke-width="2"></polyline>
    ${pts.map((p, i) => `<circle cx="${x(i)}" cy="${y(p.score)}" r="3.5" style="fill:var(--series0)"><title>${esc(p.date)}: ${p.score} (${esc(p.rec)})</title></circle>`).join('')}
    <text x="${l}" y="${h - 6}" font-size="10" style="fill:var(--fg3)">${esc(pts[0].date)}</text>
    <text x="${w - r}" y="${h - 6}" font-size="10" text-anchor="end" style="fill:var(--fg3)">${esc(pts[pts.length - 1].date)}</text></svg>
    <p class="small-note">${pts.length} scan days. Dashed lines: 75 strong buy, 60 buy, 45 hold, 30 sell.</p>`;
}

// ============================================================ charts (Plotly, loaded only when needed)

let plotlyPromise = null;
function loadPlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  if (!plotlyPromise) {
    plotlyPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = PLOTLY_URL; s.async = true;
      s.onload = () => resolve(window.Plotly);
      s.onerror = () => { plotlyPromise = null; reject(new Error("Couldn't load the chart library - check your internet.")); };
      document.head.appendChild(s);
    });
  }
  return plotlyPromise;
}
function chartColors() {
  const k = ['--surface', '--surface-2', '--fg', '--fg2', '--fg3', '--grid', '--chart-fg', '--series0', '--series1', '--series2', '--buy', '--sell', '--hold', '--sb', '--ss', '--line'];
  return Object.fromEntries(k.map((n) => [n.slice(2), cssVar(n)]));
}
function baseLayout(C) {
  return {
    paper_bgcolor: C.surface, plot_bgcolor: C.surface, margin: { l: 56, r: 18, t: 46, b: 40 },
    font: { family: getComputedStyle(document.body).fontFamily, color: C['chart-fg'], size: 12 },
    hoverlabel: { bgcolor: C.surface, bordercolor: C.line, font: { color: C.fg } },
  };
}
const PLOT_CONFIG = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d', 'toggleSpikelines'] };

function fillChartSymbols() {
  const sel = $('#c-sym');
  const syms = [...new Set([...state.results.map((r) => r.symbol), ...state.watchlist])].sort();
  const keep = sel.value || state.selected;
  sel.innerHTML = syms.map((s) => `<option>${esc(s)}</option>`).join('');
  if (keep && syms.includes(keep)) sel.value = keep;
}
function chartPeriod() { return ($('#c-period button[aria-pressed="true"]') || {}).dataset?.p || '6mo'; }

async function showPriceChart(animate = true) {
  const sym = $('#c-sym').value;
  if (!sym) { toast('Pick a stock first', 'Add stocks to your watchlist.', 'warn'); return; }
  const period = chartPeriod();
  stopSpin();
  state.chart = { type: 'price', sym, period };
  const el = $('#chart');
  if (window.Plotly) Plotly.purge(el);
  el.innerHTML = `<div class="empty">Loading ${esc(sym)}...</div>`;
  $('#c-note').textContent = '';
  let P, d;
  try { [P, d] = await Promise.all([loadPlotly(), api(`/api/chart?symbol=${encodeURIComponent(sym)}&period=${period}`)]); }
  catch (err) { el.innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
  if (state.chart?.sym !== sym || state.chart?.type !== 'price') return;
  el.innerHTML = '';
  const C = chartColors();
  const x = d.t, close = d.c;
  const sma = (n) => close.map((_, i) => (i + 1 < n ? null : close.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
  const valid = close.filter((v) => v != null);
  const floor = Math.min(...valid) * 0.98, top = Math.max(...valid) * 1.02;
  const traces = [
    { x, y: x.map(() => floor), type: 'scatter', mode: 'lines', line: { width: 0 }, hoverinfo: 'skip', showlegend: false },
    { x, y: close, type: 'scatter', mode: 'lines', name: 'Close', line: { color: C.series0, width: 2 }, fill: 'tonexty', fillcolor: rgba(C.series0, 0.12) },
  ];
  if (close.length >= 20) traces.push({ x, y: sma(20), type: 'scatter', mode: 'lines', name: 'SMA 20', line: { color: C.series1, width: 1.4 } });
  if (close.length >= 50) traces.push({ x, y: sma(50), type: 'scatter', mode: 'lines', name: 'SMA 50', line: { color: C.series2, width: 1.4 } });
  traces.push({ x, y: d.v.map((v) => (v == null ? null : v / 1e5)), type: 'bar', name: 'Volume (lakh)', yaxis: 'y2', showlegend: false,
                marker: { color: close.map((c, i) => (c >= d.o[i] ? C.buy : C.sell)) }, opacity: 0.95 });
  const layout = Object.assign(baseLayout(C), {
    title: { text: `<b>${esc(sym)}</b>  ${d.hourly ? 'new listing - 1-hour candles' : { '1mo': '1 month', '3mo': '3 months', '6mo': '6 months', '1y': '1 year', '2y': '2 years' }[period]}`, x: 0.01, font: { color: C.fg, size: 15 } },
    showlegend: true, legend: { orientation: 'h', x: 1, xanchor: 'right', y: 1.07, traceorder: 'normal', font: { color: C['chart-fg'] } },
    hovermode: 'x unified', bargap: 0.25,
    xaxis: d.hourly ? { type: 'category', nticks: 8, gridcolor: C.grid, linecolor: C.line, showspikes: false }
      : { type: 'date', rangebreaks: [{ bounds: ['sat', 'mon'] }], gridcolor: C.grid, linecolor: C.line },
    yaxis: { domain: [0.3, 1], range: [floor, top], gridcolor: C.grid, zeroline: false, tickformat: ',.0f' },
    yaxis2: { domain: [0, 0.22], gridcolor: C.grid, zeroline: false, title: { text: 'Volume (lakh)', font: { size: 11 } } },
  });
  await P.react(el, traces, layout, PLOT_CONFIG);
  if (animate && motionOn()) { el.classList.remove('reveal'); void el.offsetWidth; el.classList.add('reveal'); }
  $('#c-note').textContent = 'Prices from Yahoo Finance (can be delayed). Green volume bar = closed above its open.';
}

async function showMarketMap(animate = true) {
  if (!state.results.length) { toast('Scan first', 'The 3D market map shows your scan results.', 'warn'); return; }
  stopSpin();
  state.chart = { type: 'map' };
  const el = $('#chart');
  if (window.Plotly) Plotly.purge(el);
  el.innerHTML = '<div class="empty">Loading the 3D map...</div>';
  let P;
  try { P = await loadPlotly(); } catch (err) { el.innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
  if (state.chart?.type !== 'map') return;
  el.innerHTML = '';
  const C = chartColors();
  const sym = { 'STRONG BUY': 'diamond', BUY: 'circle', HOLD: 'square', SELL: 'x', 'STRONG SELL': 'cross' };
  const col = { 'STRONG BUY': C.sb, BUY: C.buy, HOLD: C.hold, SELL: C.sell, 'STRONG SELL': C.ss };
  const rs3 = (r) => (r.rs && r.rs['3M'] != null ? r.rs['3M'] : 0);
  const rating = (r) => (r.rs_rating != null ? r.rs_rating : 50);
  const traces = [];
  SIGNALS.forEach((rec) => {
    const pts = state.results.filter((r) => r.rec === rec);
    if (!pts.length) return;
    const sx = [], sy = [], sz = [];
    pts.forEach((r) => { sx.push(rating(r), rating(r), null); sy.push(rs3(r), rs3(r), null); sz.push(0, r.score, null); });
    traces.push({ type: 'scatter3d', mode: 'lines', x: sx, y: sy, z: sz, line: { color: col[rec], width: 3 }, hoverinfo: 'skip', showlegend: false });
    traces.push({ type: 'scatter3d', mode: 'markers', name: `${SIG_LABEL[rec]} (${pts.length})`, x: pts.map(rating), y: pts.map(rs3), z: pts.map((r) => r.score),
      text: pts.map((r) => r.symbol), marker: { size: rec.startsWith('STRONG') ? 7 : 5, color: col[rec], symbol: sym[rec], line: { color: C.surface, width: 1 } },
      hovertemplate: '<b>%{text}</b><br>Score %{z:.1f}<br>RS rating %{x:.0f}<br>vs Nifty 3M %{y:+.1f}%<extra></extra>' });
  });
  const ranked = [...state.results].sort((a, b) => a.score - b.score);
  const named = [...ranked.slice(-4), ...ranked.slice(0, 2)];
  traces.push({ type: 'scatter3d', mode: 'text', x: named.map(rating), y: named.map(rs3), z: named.map((r) => r.score + 4), text: named.map((r) => r.symbol),
    textfont: { color: C.fg, size: 11 }, hoverinfo: 'skip', showlegend: false });
  const axis = (title, extra = {}) => Object.assign({ title: { text: title }, gridcolor: C.grid, backgroundcolor: rgba(C['surface-2'], 0.7), showbackground: true, zerolinecolor: C.line, color: C['chart-fg'] }, extra);
  const layout = Object.assign(baseLayout(C), {
    title: { text: `<b>3D market map</b>  ${state.results.length} stocks`, x: 0.01, font: { color: C.fg, size: 15 } },
    margin: { l: 0, r: 0, t: 40, b: 0 }, showlegend: true, legend: { x: 0.01, y: 0.92, font: { color: C['chart-fg'] } },
    scene: {
      xaxis: axis('RS rating', { range: [0, 100] }), yaxis: axis('vs Nifty 50, 3M (%)'), zaxis: axis('Score', { range: [0, 100] }),
      aspectmode: 'manual', aspectratio: { x: 1.5, y: 1.1, z: 0.9 }, dragmode: 'turntable',
      camera: { eye: { x: -1.25, y: -1.1, z: 0.2 } },
    },
  });
  await P.react(el, traces, layout, PLOT_CONFIG);
  $('#c-note').textContent = 'Higher = better score. Right = higher RS rating. Further back = beating the Nifty 50 over 3 months. It turns by itself - touch or drag it to take over.';
  if (!motionOn()) { P.relayout(el, { 'scene.camera.eye': { x: -1.25, y: -1.1, z: 0.7 } }); return; }
  // the camera rises over the map, then the map turns slowly until it's touched
  const spin = { stop: false, angle: Math.atan2(-1.1, -1.25), z: 0.2, last: 0 };
  state.spin = spin;
  const stop = () => { spin.stop = true; };
  ['pointerdown', 'wheel', 'touchstart'].forEach((ev) => el.addEventListener(ev, stop, { once: true, passive: true }));
  const radius = Math.hypot(1.25, 1.1);
  const t0 = performance.now();
  const frame = (now) => {
    if (spin.stop || !el.isConnected || state.chart?.type !== 'map') return;
    if (state.tab === 'charts' && !document.hidden && now - spin.last > 40) {
      spin.last = now;
      const rise = Math.min(1, (now - t0) / 1400);
      spin.z = 0.2 + 0.5 * (1 - Math.pow(1 - rise, 3));
      if (rise >= 1) spin.angle += 0.006;
      P.relayout(el, { 'scene.camera.eye': { x: radius * Math.cos(spin.angle), y: radius * Math.sin(spin.angle), z: spin.z } });
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
function stopSpin() { if (state.spin) state.spin.stop = true; state.spin = null; }
function redrawChart() {
  if (!state.chart) return;
  if (state.chart.type === 'map') showMarketMap(false); else showPriceChart(false);
}

// ============================================================ PDF reports (made in the browser, loaded only when asked for)

const PDF_LIBS = ['https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
                  'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js'];
const PDF = { accent: [26, 79, 230], fg: [10, 16, 28], fg2: [52, 62, 80], fg3: [74, 85, 104], line: [205, 213, 224],
              rec: { 'STRONG BUY': [0, 112, 79], BUY: [0, 147, 106], HOLD: [115, 126, 144], SELL: [229, 64, 46], 'STRONG SELL': [184, 33, 15] },
              tintB: [220, 243, 234], tintS: [253, 231, 229], zebra: [246, 248, 251], left: 30, top: 84, bottom: 56 };
let pdfLoading = null, pdfLogo;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src; s.onload = resolve;
    s.onerror = () => reject(new Error("Couldn't load the PDF tool - check your internet."));
    document.head.appendChild(s);
  });
}
function loadPdfLib() {
  if (!pdfLoading) {
    pdfLoading = loadScript(PDF_LIBS[0]).then(() => loadScript(PDF_LIBS[1])).then(() => window.jspdf.jsPDF)
      .catch((e) => { pdfLoading = null; throw e; });
  }
  return pdfLoading;
}
async function logoForPdf() {
  if (pdfLogo === undefined) {
    try {
      const blob = await (await fetch('logo.png')).blob();
      pdfLogo = await new Promise((resolve, reject) => { const f = new FileReader(); f.onload = () => resolve(f.result); f.onerror = reject; f.readAsDataURL(blob); });
    } catch (e) { pdfLogo = null; }
  }
  return pdfLogo;
}
/** The standard PDF fonts only have Western letters: anything else is dropped. */
const pdfText = (v) => String(v ?? '').replace(/[\u2013\u2014]/g, '-').replace(/[^\x20-\x7E\xA0-\xFF]/g, '');
const pdfMoney = (v) => (v == null ? 'N/A' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const pdfStamp = (d) => d.toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });

async function newPdf() {
  const JsPDF = await loadPdfLib();
  const [logo] = await Promise.all([logoForPdf(), loadCompanies()]);
  const doc = new JsPDF({ unit: 'pt', format: 'a4' });
  doc.drs = { logo, y: PDF.top, W: doc.internal.pageSize.getWidth(), H: doc.internal.pageSize.getHeight() };
  return doc;
}
/** A paragraph, wrapped; starts a new page when it wouldn't fit. */
function pdfPara(doc, text, { size = 9, bold = false, color = PDF.fg2, gap = 6 } = {}) {
  doc.setFont('helvetica', bold ? 'bold' : 'normal'); doc.setFontSize(size); doc.setTextColor(...color);
  const lines = doc.splitTextToSize(pdfText(text), doc.drs.W - 2 * PDF.left);
  const height = lines.length * size * 1.3;
  if (doc.drs.y + height > doc.drs.H - PDF.bottom) { doc.addPage(); doc.drs.y = PDF.top; }
  doc.text(lines, PDF.left, doc.drs.y + size);
  doc.drs.y += height + gap;
}
function pdfTable(doc, head, body, opts = {}) {
  doc.autoTable(Object.assign({
    head: [head], body, startY: doc.drs.y, theme: 'grid',
    margin: { top: PDF.top, bottom: PDF.bottom, left: PDF.left, right: PDF.left },
    styles: { font: 'helvetica', fontSize: 8, cellPadding: 3.5, lineColor: PDF.line, lineWidth: 0.4, textColor: PDF.fg, overflow: 'linebreak' },
    headStyles: { fillColor: PDF.accent, textColor: 255, fontStyle: 'bold' },
  }, opts));
  doc.drs.y = doc.lastAutoTable.finalY + 14;
}
/** The letterhead and the footer, on every page (drawn last, when the page count is known). */
function pdfFinish(doc) {
  const { W, H, logo } = doc.drs;
  const n = doc.getNumberOfPages(), x = logo ? 106 : PDF.left;
  for (let i = 1; i <= n; i++) {
    doc.setPage(i);
    if (logo) { try { doc.addImage(logo, 'PNG', PDF.left, 22, 66, 36); } catch (e) { /* no logo then */ } }
    doc.setFont('helvetica', 'bold'); doc.setFontSize(15); doc.setTextColor(...PDF.accent);
    doc.text("DR. NILESH SHAH'S MARKET ANALYSIS", x, 40);
    doc.setFont('helvetica', 'normal'); doc.setFontSize(8.5); doc.setTextColor(...PDF.fg3);
    doc.text('Technical scanner for NSE and BSE stocks', x, 53);
    doc.setDrawColor(...PDF.accent); doc.setLineWidth(1.5); doc.line(PDF.left, 66, W - PDF.left, 66);
    doc.setDrawColor(...PDF.line); doc.setLineWidth(0.6); doc.line(PDF.left, H - 42, W - PDF.left, H - 42);
    doc.setFontSize(7.5); doc.setTextColor(...PDF.fg3);
    doc.text(pdfText(`Generated ${pdfStamp(new Date())}${state.user ? ` for ${state.user}` : ''}`), PDF.left, H - 30);
    doc.text(`Page ${i} of ${n}`, W - PDF.left, H - 30, { align: 'right' });
    doc.text('For education and information only - not financial advice. Prices from Yahoo Finance and can be delayed.', W / 2, H - 18, { align: 'center' });
  }
  return doc;
}

/** The scan: summary, then every stock the table shows (same filters, same order) with its stop-loss and targets. */
async function buildScanPdf() {
  const rows = visibleRows();
  const doc = await newPdf();
  pdfPara(doc, 'Stock technical analysis report', { size: 15, bold: true, color: PDF.fg, gap: 4 });
  const filters = [];
  if ($('#f-q').value.trim()) filters.push(`symbol contains "${$('#f-q').value.trim().toUpperCase()}"`);
  if ($('#f-rec').value !== 'All') filters.push(`signal ${$('#f-rec').value}`);
  if ($('#f-liq').checked) filters.push(`illiquid stocks (under Rs ${Number(state.settings.liq) || 0} Cr/day) hidden`);
  pdfPara(doc, `Scan of ${state.when ? pdfStamp(state.when) : 'today'}  |  ${rows.length} of ${state.results.length} stocks`
    + (filters.length ? `  |  Showing only: ${filters.join(', ')}` : ''), { size: 9, color: PDF.fg3, gap: 12 });

  const count = (k) => rows.filter((r) => r.rec === k).length;
  const avg = rows.length ? rows.reduce((a, r) => a + r.score, 0) / rows.length : 0;
  pdfTable(doc, ['Stocks', 'Strong buy', 'Buy', 'Hold', 'Sell', 'Strong sell', 'Average score'],
    [[rows.length, ...SIGNALS.map(count), avg.toFixed(1)]],
    { styles: { font: 'helvetica', fontSize: 9, halign: 'center', cellPadding: 5, lineColor: PDF.line, lineWidth: 0.4, textColor: PDF.fg },
      bodyStyles: { fontSize: 14, fontStyle: 'bold' },
      didParseCell: (d) => { if (d.section === 'body' && d.column.index >= 1 && d.column.index <= 5) d.cell.styles.textColor = PDF.rec[SIGNALS[d.column.index - 1]]; } });

  pdfPara(doc, 'Scan results', { size: 11, bold: true, color: PDF.fg, gap: 4 });
  const body = rows.map((r) => {
    const t = r.targets || {};
    return [r.symbol + (r.hourly ? '*' : ''), pdfText(companyName(r.symbol)), pdfMoney(r.price), signed(r.change, 2, '%'), n0(r.rs_rating), n1(r.score),
            SIG_LABEL[r.rec] || r.rec, pdfMoney(t.sl), pdfMoney(t.t1), pdfMoney(t.t2), t.rr ? `1 : ${Number(t.rr).toFixed(2)}` : 'N/A'];
  });
  pdfTable(doc, ['Symbol', 'Company', 'Price', 'Chg %', 'RS', 'Score', 'Signal', 'Stop-loss', 'Target 1', 'Target 2', 'Risk : reward'], body, {
    rowPageBreak: 'avoid',
    styles: { font: 'helvetica', fontSize: 7.2, cellPadding: 3, lineColor: PDF.line, lineWidth: 0.4, textColor: PDF.fg, overflow: 'ellipsize', halign: 'right' },
    headStyles: { fillColor: PDF.accent, textColor: 255, fontStyle: 'bold', halign: 'center', valign: 'middle', overflow: 'linebreak' },
    columnStyles: { 0: { halign: 'left', fontStyle: 'bold', cellWidth: 62 }, 1: { halign: 'left', cellWidth: 118 }, 2: { cellWidth: 46 }, 3: { cellWidth: 36 },
                    4: { cellWidth: 27 }, 5: { cellWidth: 31 }, 6: { halign: 'left', fontStyle: 'bold', cellWidth: 52 }, 7: { cellWidth: 43 },
                    8: { cellWidth: 43 }, 9: { cellWidth: 43 }, 10: { cellWidth: 34 } },
    didParseCell: (d) => {
      if (d.section !== 'body') return;
      const r = rows[d.row.index];
      d.cell.styles.fillColor = r.rec.includes('BUY') ? PDF.tintB : r.rec.includes('SELL') ? PDF.tintS : d.row.index % 2 ? PDF.zebra : [255, 255, 255];
      if (d.column.index === 6) d.cell.styles.textColor = PDF.rec[r.rec] || PDF.fg;
    },
  });

  if (rows.some((r) => r.hourly)) pdfPara(doc, '* New listing (under a month of history): analysed on 1-hour candles, so its stop-loss and targets sit closer to the price.', { size: 8, color: PDF.fg3 });
  const changes = rows.filter((r) => r.prev_rec && r.prev_rec !== r.rec);
  if (changes.length) {
    pdfPara(doc, `Signal changes since the previous scan (${changes.length})`, { size: 10, bold: true, color: PDF.fg, gap: 3 });
    pdfPara(doc, changes.map((r) => `${r.symbol}: ${SIG_LABEL[r.prev_rec] || r.prev_rec} to ${SIG_LABEL[r.rec]} (since ${r.prev_date})`).join(';  '), { size: 8.5 });
  }
  if (state.failed.length || state.tooNew.length) {
    pdfPara(doc, 'Not scored: ' + [state.failed.length ? `${state.failed.join(', ')} (no price data)` : '', state.tooNew.length ? `${state.tooNew.join(', ')} (listed under 3 trading days ago)` : '']
      .filter(Boolean).join(';  '), { size: 8.5, color: PDF.fg3 });
  }
  pdfPara(doc, 'Score: 75-100 strong buy, 60-74 buy, 45-59 hold, 30-44 sell, 0-29 strong sell. The stop-loss sits just beyond the nearest support '
    + '(resistance, for a sell) and the targets at the next resistance levels (supports, for a sell); where a stock has no level within reach, a multiple '
    + 'of its ATR is used. Risk : reward compares the distance to target 2 (target 1 for a hold) with the distance to the stop-loss.', { size: 8, color: PDF.fg3 });
  return pdfFinish(doc);
}

/** One stock: its score and what makes it up, stop-loss and targets, risk-reward, patterns. */
async function buildStockPdf(r) {
  const doc = await newPdf();
  const t = r.targets || {}, name = companyName(r.symbol);
  pdfPara(doc, name ? `${r.symbol}  -  ${name}` : r.symbol, { size: 15, bold: true, color: PDF.fg, gap: 4 });
  pdfPara(doc, `Scan of ${state.when ? pdfStamp(state.when) : 'today'}${r.hourly ? `  |  New listing (${r.days} trading days): analysed on 1-hour candles` : ''}`, { size: 9, color: PDF.fg3, gap: 12 });

  const rs = r.rs || {};
  pdfTable(doc, ['Signal', 'Score', 'Price', 'Change today', 'RS rating', 'vs Nifty 1M', 'vs Nifty 3M', 'vs Nifty 6M'],
    [[SIG_LABEL[r.rec] || r.rec, n1(r.score), pdfMoney(r.price), signed(r.change, 2, '%'), n0(r.rs_rating), ...['1M', '3M', '6M'].map((k) => signed(rs[k], 1, '%'))]],
    { styles: { font: 'helvetica', fontSize: 9, halign: 'center', cellPadding: 5, lineColor: PDF.line, lineWidth: 0.4, textColor: PDF.fg },
      bodyStyles: { fontSize: 12, fontStyle: 'bold' },
      didParseCell: (d) => { if (d.section === 'body' && d.column.index === 0) d.cell.styles.textColor = PDF.rec[r.rec] || PDF.fg; } });
  if (illiquid(r)) pdfPara(doc, `Low liquidity: only about Rs ${Number(r.liquidity_cr || 0).toFixed(2)} crore traded per day. Price can gap past the stop-loss and orders may not fill.`, { size: 8.5, bold: true, color: PDF.rec['STRONG SELL'] });

  pdfPara(doc, 'Stop-loss and targets', { size: 11, bold: true, color: PDF.fg, gap: 4 });
  const basis = t.basis || {};
  const why = (k) => (basis[k] ? basis[k].charAt(0).toUpperCase() + basis[k].slice(1) : '');
  pdfTable(doc, ['Level', 'Price', 'What to do', 'Where it comes from'], [
    ['Stop-loss', pdfMoney(t.sl), t.pos === 'SHORT' ? 'Exit if the price rises above' : 'Exit if the price falls below', pdfText(why('sl'))],
    ['Target 1 (conservative)', pdfMoney(t.t1), 'Book partial profits', pdfText(why('t1'))],
    ['Target 2 (moderate)', pdfMoney(t.t2), 'Main target - book 50%', pdfText(why('t2'))],
    ['Target 3 (aggressive)', pdfMoney(t.t3), 'Trail the stop-loss', pdfText(why('t3'))],
  ], { columnStyles: { 0: { fontStyle: 'bold', cellWidth: 118 }, 1: { halign: 'right', fontStyle: 'bold', cellWidth: 66 }, 2: { cellWidth: 138 } },
       didParseCell: (d) => { if (d.section === 'body' && d.column.index === 0) d.cell.styles.textColor = [PDF.rec.SELL, PDF.rec.BUY, PDF.rec['STRONG BUY'], PDF.accent][d.row.index]; } });
  const rr = t.rr || 0, pct = (a) => (t.price > 0 && a != null ? ` (${((a / t.price) * 100).toFixed(1)}% of the price)` : '');
  pdfPara(doc, `Risk ${pdfMoney(t.risk)}${pct(t.risk)}   |   Reward ${pdfMoney(t.reward)}${pct(t.reward)}   |   Risk : reward ${rr > 0 ? `1 : ${rr.toFixed(2)}` : 'N/A'}`
    + `  -  ${rr >= 2 ? 'excellent' : rr >= 1.5 ? 'good' : rr >= 1 ? 'acceptable' : 'poor'}`, { size: 9.5, bold: true, color: PDF.fg, gap: 3 });
  pdfPara(doc, `Risk = from the price to the stop-loss. Reward = from the price to ${t.pos === 'HOLD' ? 'target 1' : 'target 2'}.`, { size: 8, color: PDF.fg3, gap: 12 });

  pdfPara(doc, 'What makes up the score (each part 0 to 100)', { size: 11, bold: true, color: PDF.fg, gap: 4 });
  const bd = r.breakdown || {};
  pdfTable(doc, ['Indicator', 'Score', 'Reading'], Object.keys(NAMES).filter((k) => k in bd).map((k) => [NAMES[k], bd[k], bd[k] >= 70 ? 'Strong' : bd[k] >= 50 ? 'Good' : bd[k] >= 30 ? 'Weak' : 'Bearish']), {
    tableWidth: 300, columnStyles: { 0: { cellWidth: 130 }, 1: { halign: 'right', fontStyle: 'bold', cellWidth: 60 } },
    didParseCell: (d) => {
      if (d.section !== 'body' || d.column.index !== 2) return;
      const v = d.row.raw[1];
      d.cell.styles.textColor = v >= 70 ? PDF.rec['STRONG BUY'] : v >= 50 ? PDF.rec.BUY : v >= 30 ? PDF.rec.HOLD : PDF.rec.SELL;
      d.cell.styles.fontStyle = 'bold';
    },
  });

  const p = r.patterns || {}, sum = p.summary || {};
  const pats = [['Chart', p.chart], ['Candlestick', p.candlestick], ['Harmonic', p.harmonic]]
    .flatMap(([kind, items]) => (items || []).map((x) => [pdfText(x.name), kind, String(x.signal || '').charAt(0) + String(x.signal || '').slice(1).toLowerCase(), pdfText(x.description || '')]));
  pdfPara(doc, 'Patterns', { size: 11, bold: true, color: PDF.fg, gap: 4 });
  if (pats.length) {
    pdfTable(doc, ['Pattern', 'Type', 'Signal', 'Description'], pats, {
      columnStyles: { 0: { fontStyle: 'bold', cellWidth: 140 }, 1: { cellWidth: 66 }, 2: { cellWidth: 52, fontStyle: 'bold' } },
      didParseCell: (d) => { if (d.section === 'body' && d.column.index === 2) d.cell.styles.textColor = d.cell.raw === 'Bullish' ? PDF.rec.BUY : d.cell.raw === 'Bearish' ? PDF.rec.SELL : PDF.rec.HOLD; },
    });
    pdfPara(doc, `${sum.total_patterns || pats.length} found: ${sum.bullish_count || 0} bullish, ${sum.bearish_count || 0} bearish. Overall: ${sum.overall_signal || 'N/A'}.`, { size: 8.5 });
  } else {
    pdfPara(doc, 'No chart or candlestick patterns detected.', { size: 9 });
  }
  return pdfFinish(doc);
}

/** Make the report and hand it to the browser as a file to save. */
async function downloadPdf(button, build, name) {
  const label = button.textContent;
  button.disabled = true; button.textContent = 'Making PDF...';
  try {
    const doc = await build();
    const day = (state.when || new Date()).toLocaleDateString('en-CA');       // YYYY-MM-DD
    doc.save(`${name}_${day}.pdf`);
    toast('PDF downloaded', `${name}_${day}.pdf is in your Downloads.`, 'good', 5000);
  } catch (err) {
    toast("Couldn't make the PDF", err.message, 'bad');
  } finally {
    button.disabled = false; button.textContent = label;
  }
}

// ============================================================ wiring

function wire() {
  $('#mode-in').addEventListener('click', () => setLoginMode('in'));
  $('#mode-new').addEventListener('click', () => setLoginMode('new'));
  $('#login-form').addEventListener('submit', submitLogin);
  $('#logout-btn').addEventListener('click', async () => {
    try { await api('/api/logout', { body: {} }); } catch (e) { /* signed out anyway */ }
    state.results = []; state.watchlist = []; state.user = null;
    showLogin();
  });
  $('#theme-btn').addEventListener('click', () => applyTheme(currentTheme() === 'dark' ? 'light' : 'dark'));
  $$('#s-theme button').forEach((b) => b.addEventListener('click', () => applyTheme(b.dataset.v)));
  $('#s-anim').addEventListener('change', (e) => applyMotion(e.target.checked));
  $('#s-liq').addEventListener('change', (e) => {
    const v = Math.max(0, Number(e.target.value) || 0);
    state.settings.liq = v; saveSettings(); renderResults();
    toast('Saved', `Stocks trading under Rs ${v} crore a day are flagged LOW.`, 'good', 3000);
  });
  $('#pw-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await api('/api/password', { body: { old: $('#pw-old').value, new: $('#pw-new').value } });
      $('#pw-old').value = ''; $('#pw-new').value = '';
      toast('Password changed', '', 'good', 3500);
    } catch (err) { toast("Password not changed", err.message, 'bad'); }
  });

  $$('#tabs button').forEach((b) => b.addEventListener('click', () => selectTab(b.dataset.tab)));
  window.addEventListener('resize', () => { moveTabLine(); const l = $('#ladder'); if (l && l._redraw) l._redraw(); });

  $('#add-form').addEventListener('submit', (e) => { e.preventDefault(); submitAdd(); });
  const addInput = $('#add-input');
  addInput.addEventListener('input', updateSuggest);
  addInput.addEventListener('focus', () => { loadCompanies(); if (addInput.value.trim().length >= 2) updateSuggest(); });
  addInput.addEventListener('blur', () => setTimeout(closeSuggest, 180));
  addInput.addEventListener('keydown', (e) => {
    const n = suggest.items.length;
    if (e.key === 'ArrowDown' && n) { e.preventDefault(); suggest.active = (suggest.active + 1) % n; renderSuggest(); }
    else if (e.key === 'ArrowUp' && n) { e.preventDefault(); suggest.active = (suggest.active - 1 + n) % n; renderSuggest(); }
    else if (e.key === 'Escape') { closeSuggest(); }
  });
  $('#add-list').addEventListener('pointerdown', (e) => {
    const li = e.target.closest('li[data-i]');
    if (!li) return;
    e.preventDefault();                       // keep the typing box focused
    chooseCompany(suggest.items[Number(li.dataset.i)]);
  });
  $('#bulk-btn').addEventListener('click', async () => {
    const list = parseSymbols($('#bulk').value);
    if (!list.length) { toast('Nothing to add', 'Paste symbols separated by commas, spaces or new lines.', 'warn'); return; }
    try { await addSymbols(list); $('#bulk').value = ''; } catch (err) { toast("Couldn't add", err.message, 'bad'); }
  });
  $('#clear-btn').addEventListener('click', async () => {
    if (!state.watchlist.length || !confirm(`Remove all ${state.watchlist.length} stocks from your watchlist?`)) return;
    try { await saveWatchlist([], 'Watchlist cleared'); } catch (err) { toast("Couldn't clear", err.message, 'bad'); }
  });
  $('#chips').addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-del]');
    if (!b) return;
    try { await saveWatchlist(state.watchlist.filter((s) => s !== b.dataset.del), `Removed ${b.dataset.del}`); }
    catch (err) { toast("Couldn't remove", err.message, 'bad'); }
  });

  $('#wl-save').addEventListener('click', saveWatchlistFile);
  $('#wl-load').addEventListener('click', () => $('#wl-file').click());
  $('#wl-file').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    e.target.value = '';                           // the same file can be picked again
    if (file) await loadWatchlistFile(file);
  });
  try { $('#wl-format').value = localStorage.getItem('drs-wl-format') || 'json'; } catch (err) { /* private window */ }
  $('#wl-format').addEventListener('change', (e) => { try { localStorage.setItem('drs-wl-format', e.target.value); } catch (err) { /* private window */ } });
  $('#scan-btn').addEventListener('click', scanAll);
  $('#pdf-btn').addEventListener('click', (e) => {
    if (!state.results.length) { toast('Scan first', 'The PDF report is made from your scan results.', 'warn'); return; }
    if (!visibleRows().length) { toast('No stocks to report', 'Your Find / Show filters hide every stock - clear them first.', 'warn'); return; }
    downloadPdf(e.currentTarget, buildScanPdf, 'Market_Analysis_scan');
  });
  ['#f-q', '#f-rec', '#f-liq'].forEach((s) => $(s).addEventListener('input', renderResults));
  $('#results-box').addEventListener('click', (e) => {
    const th = e.target.closest('th[data-sort]');
    if (th) {
      const k = th.dataset.sort;
      state.sort = { key: k, asc: state.sort.key === k ? !state.sort.asc : true };
      renderResults();
      return;
    }
    const tr = e.target.closest('tr[data-sym]');
    if (tr) showDetails(tr.dataset.sym);
  });
  $('#results-box').addEventListener('keydown', (e) => {
    const tr = e.target.closest('tr[data-sym]');
    if (tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); showDetails(tr.dataset.sym); }
  });

  $$('#c-period button').forEach((b) => b.addEventListener('click', () => {
    $$('#c-period button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    if (state.chart?.type === 'price') showPriceChart();
  }));
  $('#c-show').addEventListener('click', () => showPriceChart());
  $('#c-map').addEventListener('click', () => showMarketMap());
  $('#c-sym').addEventListener('change', () => { if (state.chart?.type === 'price') showPriceChart(); });
}

function init() {
  wire();
  document.documentElement.dataset.theme = currentTheme();
  syncThemeControls();
  $('#s-anim').checked = state.settings.animations !== false;
  $('#s-liq').value = state.settings.liq;
  setLoginMode('in');
  updateMarket();
  setInterval(updateMarket, 60000);
  boot();
}

init();
