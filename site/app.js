/* Wypad — codzienne okazje na city break. Vanilla ES module, bez procesu budowania. */

const DATA_URL = 'data/deals.json';
const archiveUrl = (date) => `data/archive/${date}.json`;
const BUDGET_MIN = 800;
const BUDGET_MAX = 6000; // pozycja suwaka = „bez limitu”
const ACCENTS = new Set(['ochre', 'coral', 'teal', 'blue', 'rose', 'olive']);
const LS = { filters: 'wypad.filters.v1', saved: 'wypad.saved.v1', hidden: 'wypad.hidden.v1' };

const DAYS = ['nd', 'pn', 'wt', 'śr', 'czw', 'pt', 'sob'];
const MONTHS = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];
const MONTHS_GEN = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];

const DEFAULT_BAGS = {
  small: { short: 'Plecak', phrase: 'plecak', long: 'Każda osoba: mały bagaż pod siedzenie (40×30×20 cm).' },
  cabin10: { short: '10 kg', phrase: 'bagaż 10 kg', long: 'Każda osoba: mały bagaż pod siedzenie + walizka kabinowa 10 kg (Priority).' },
  checked20: { short: 'Plecak + 20 kg', phrase: 'walizka 20 kg', long: 'Każda osoba: mały bagaż pod siedzenie + jedna walizka rejestrowana 20 kg na dwie osoby.' },
};
const bagPhrase = (key) => bagMeta()[key]?.phrase || DEFAULT_BAGS[key]?.phrase || bagMeta()[key]?.short || '';
const SORTS = { best: 'Najlepsze okazje', cheap: 'Najtańsze', soon: 'Najbliższy wylot' };

const main = document.getElementById('main');
const sheet = document.getElementById('filters');
const toastEl = document.querySelector('.toast');

const state = {
  data: null,
  archives: new Map(),
  filters: null,
  saved: readLS(LS.saved, []),
  hidden: readLS(LS.hidden, []),
  boardPrev: [],
  homeScroll: 0,
  view: '',
};

/* ─── Storage (per-viewer conveniences only; the app works without it) ── */
function readLS(key, fallback) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}
function writeLS(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode / blocked storage */ }
}

/* ─── Formatting ─────────────────────────────────────────────────────── */
const nf = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const pln = (n) => `${nf.format(Math.round(n))} zł`;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const safeUrl = (u) => (typeof u === 'string' && /^https:\/\//i.test(u) ? u : null);
const icon = (name, cls = '') => `<svg class="ico ${cls}" aria-hidden="true"><use href="icons/sprite.svg#i-${name}"/></svg>`;

function plural(n, one, few, many) {
  if (n === 1) return one;
  const d = n % 10, dd = n % 100;
  return d >= 2 && d <= 4 && !(dd >= 12 && dd <= 14) ? few : many;
}
const nightsLabel = (n) => `${n} ${plural(n, 'noc', 'noce', 'nocy')}`;

function parseDay(s) {
  const [y, m, d] = s.slice(0, 10).split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}
const dayShort = (s) => { const d = parseDay(s); return `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`; };
const dayLong = (s) => { const d = parseDay(s); return `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS_GEN[d.getUTCMonth()]}`; };
const ddmm = (s) => `${s.slice(8, 10)}.${s.slice(5, 7)}`;
const hhmm = (s) => (s && s.length >= 16 ? s.slice(11, 16) : '');
const arrTime = (leg) => `${leg.arr_estimated ? '~' : ''}${hhmm(leg.arr)}`;   // Wizz Air: arrival estimated
const daysBetween = (a, b) => Math.round((parseDay(b) - parseDay(a)) / 86400000);

function rangeLabel(out, back) {
  const a = parseDay(out), b = parseDay(back);
  if (a.getUTCMonth() === b.getUTCMonth()) return `${a.getUTCDate()}–${b.getUTCDate()} ${MONTHS[b.getUTCMonth()]}`;
  return `${a.getUTCDate()} ${MONTHS[a.getUTCMonth()]} – ${b.getUTCDate()} ${MONTHS[b.getUTCMonth()]}`;
}
function durationLabel(h) {
  if (h == null) return '—';
  const days = Math.floor(h / 24), rest = Math.round(h - days * 24);
  if (!days) return `${rest} h`;
  return `${days} ${plural(days, 'dzień', 'dni', 'dni')}${rest ? ` ${rest} h` : ''}`;
}
const todayISO = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Warsaw' }).format(new Date());
function untilLabel(days) {
  if (days < 0) return 'już minął';
  if (days === 0) return 'dziś';
  if (days === 1) return 'jutro';
  if (days === 2) return 'pojutrze';
  return `za ${days} dni`;
}
function ratingWord(r) {
  if (r >= 9) return 'Znakomity';
  if (r >= 8.5) return 'Świetny';
  if (r >= 8) return 'Bardzo dobry';
  if (r >= 7) return 'Dobry';
  return 'Ocena gości';
}
const fmtRating = (r) => nf1.format(r);
function stampLabel(iso) {
  const d = new Date(iso);
  if (Number.isNaN(+d)) return '';
  const date = new Intl.DateTimeFormat('pl-PL', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Europe/Warsaw' }).format(d);
  const time = new Intl.DateTimeFormat('pl-PL', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Warsaw' }).format(d);
  return `${date}, ${time}`;
}

/* ─── Data ───────────────────────────────────────────────────────────── */
async function fetchJSON(url) {
  const res = await fetch(url, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`HTTP ${res.status} dla ${url}`);
  return res.json();
}
async function loadArchive(date) {
  if (state.data && state.data.date === date) return state.data;
  if (!state.archives.has(date)) {
    state.archives.set(date, fetchJSON(archiveUrl(date)).catch(() => null));
  }
  return state.archives.get(date);
}
const bagMeta = () => ({ ...DEFAULT_BAGS, ...(state.data?.bag_options || {}) });
const total = (deal, bag) => deal.totals?.[bag] ?? deal.totals?.cabin10 ?? 0;
const accentOf = (deal) => (ACCENTS.has(deal.city?.accent) ? deal.city.accent : 'blue');

function defaultFilters(data) {
  const d = data?.defaults || {};
  return {
    origins: d.origins || ['POZ', 'WRO', 'BZG', 'SZZ', 'LCJ'],
    budget: d.budget || 2500,
    nights: d.nights || [2, 3, 4],
    bag: d.bag || 'cabin10',
    weekendOnly: false,
    lastMinuteOnly: false,
    sort: 'best',
  };
}
function initFilters(data) {
  const def = defaultFilters(data);
  const saved = readLS(LS.filters, null);
  const f = { ...def, ...(saved || {}) };
  if (!Array.isArray(f.origins) || !f.origins.length) f.origins = def.origins;
  if (!Array.isArray(f.nights) || !f.nights.length) f.nights = def.nights;
  if (!(f.bag in bagMeta())) f.bag = def.bag;
  if (!(f.sort in SORTS)) f.sort = 'best';
  return f;
}
const saveFilters = () => writeLS(LS.filters, state.filters);

function filtered(deals, f = state.filters) {
  const out = deals.filter((d) =>
    f.origins.includes(d.flight.out.from)
    && f.nights.includes(d.trip.nights)
    && (!f.weekendOnly || d.trip.weekend)
    && (!f.lastMinuteOnly || d.labels.includes('lastminute'))
    && (f.budget >= BUDGET_MAX || total(d, f.bag) <= f.budget)
    && !state.hidden.includes(d.city.key));
  const by = {
    best: (a, b) => b.score - a.score || total(a, f.bag) - total(b, f.bag),
    cheap: (a, b) => total(a, f.bag) - total(b, f.bag),
    soon: (a, b) => a.trip.out_date.localeCompare(b.trip.out_date) || total(a, f.bag) - total(b, f.bag),
  }[f.sort];
  return out.sort(by);
}
function activeFilterCount(f = state.filters) {
  const def = defaultFilters(state.data);
  let n = 0;
  if ([...f.origins].sort().join() !== [...def.origins].sort().join()) n++;
  if (f.budget !== def.budget) n++;
  if ([...f.nights].sort().join() !== [...def.nights].sort().join()) n++;
  if (f.bag !== def.bag) n++;
  if (f.weekendOnly) n++;
  if (f.lastMinuteOnly) n++;
  if (f.sort !== 'best') n++;
  return n;
}

/* ─── Labels ─────────────────────────────────────────────────────────── */
function labelsHTML(deal) {
  const out = [];
  const L = deal.labels || [];
  const origin = state.data?.origins?.[deal.flight.out.from];
  if (deal.price_drop > 0) out.push(`<span class="lbl lbl-drop">${icon('trending-down')}Taniej o ${pln(deal.price_drop)}</span>`);
  if (L.includes('lastminute')) out.push(`<span class="lbl lbl-lastminute">${icon('zap')}Last minute</span>`);
  if (L.includes('promo')) out.push(`<span class="lbl lbl-promo">${icon('tag')}Hit cenowy</span>`);
  if (L.includes('weekend')) out.push(`<span class="lbl lbl-weekend">${icon('calendar')}Weekend</span>`);
  if (deal.flight.out.from === 'POZ') out.push(`<span class="lbl lbl-poz">${icon('map-pin')}Z Poznania</span>`);
  else if (origin) out.push(`<span class="lbl lbl-poz">${icon('map-pin')}Z ${esc(origin.city_gen || origin.city)}</span>`);
  if (L.includes('new')) out.push(`<span class="lbl lbl-new">${icon('sparkles')}Nowa</span>`);
  return out.join('');
}

/* ─── Departure board (signature) ────────────────────────────────────── */
const FLAP_CHARS = 'AĄBCĆDEĘFGHIJKLŁMNŃOÓPRSŚTUWYZŹŻ';
const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function boardName(deal) {
  const name = (deal.city.board || deal.city.name).toUpperCase();
  return name.length > 10 ? name.slice(0, 10) : name;
}
function boardHTML(top, data, count) {
  const rows = top.length
    ? top.map((d, i) => `
      <li><a class="board-row" href="#/o/${encodeURIComponent(d.id)}" aria-label="${esc(d.city.name)}, ${esc(rangeLabel(d.trip.out_date, d.trip.back_date))}, ${esc(pln(total(d, state.filters.bag)))} za 2 osoby">
        <span class="br-city"><span class="flaps" data-row="${i}" data-text="${esc(boardName(d))}" aria-hidden="true"></span>
          <span class="board-sub">${esc(d.flight.out.from)} → ${esc(d.flight.out.to)} · ${esc(d.stay?.name || 'nocleg')}</span></span>
        <span class="br-date num">${ddmm(d.trip.out_date)}<small>${DAYS[parseDay(d.trip.out_date).getUTCDay()]} · ${nightsLabel(d.trip.nights)}</small></span>
        <span class="br-price num">${pln(total(d, state.filters.bag))}</span>
        <span class="br-go">${icon('chevron-right')}</span>
      </a></li>`).join('')
    : `<li><div class="board-row"><span class="br-city"><span class="flaps" data-row="0" data-text="BRAK" aria-hidden="true"></span><span class="board-sub">Brak ofert przy obecnych filtrach</span></span><span class="br-date">—</span></div></li>`;
  return `
  <section class="board" aria-labelledby="board-title">
    <header class="board-head">
      <h1 class="board-title" id="board-title">Odloty <small>top ${Math.min(3, count)}</small></h1>
      <span class="board-meta">${esc(dayLong(data.date))}<br>${count} ${plural(count, 'okazja', 'okazje', 'okazji')}</span>
    </header>
    <div class="board-cols" aria-hidden="true"><span>Wylot</span><span>Kierunek</span><span>2 os.</span><span></span></div>
    <ol class="board-rows">${rows}</ol>
    <p class="board-foot">Cena za 2 osoby: loty w obie strony, ${esc(bagPhrase(state.filters.bag))}${state.filters.bag === 'small' ? '' : ' (szacunek)'} i nocleg na cały pobyt.${top.some((d) => d.flight.two_seats_confirmed === false) ? ' Przy Wizz Air lot to 2 × cena za osobę (szacunek).' : ''}</p>
  </section>`;
}
function runFlaps(root, animate) {
  const els = root.querySelectorAll('.flaps');
  els.forEach((el) => {
    const row = Number(el.dataset.row);
    const target = el.dataset.text;
    const prev = state.boardPrev[row] || '';
    const len = Math.max(target.length, 4);
    const tiles = [];
    for (let i = 0; i < len; i++) {
      const t = document.createElement('span');
      t.className = 'tile';
      const final = target[i] || ' ';
      const start = animate ? (prev[i] || ' ') : final;
      t.textContent = start;
      if (start === ' ') t.classList.add('blank');
      el.appendChild(t);
      tiles.push([t, final, start]);
    }
    state.boardPrev[row] = target;
    if (!animate || reduceMotion()) {
      tiles.forEach(([t, final]) => { t.textContent = final; t.classList.toggle('blank', final === ' '); });
      return;
    }
    tiles.forEach(([t, final, start], i) => {
      if (start === final) return;
      const steps = 4 + Math.floor(Math.random() * 4) + i;
      let n = 0;
      const tick = () => {
        n += 1;
        const ch = n >= steps ? final : FLAP_CHARS[Math.floor(Math.random() * FLAP_CHARS.length)];
        t.textContent = ch;
        t.classList.toggle('blank', ch === ' ');
        t.classList.remove('flip');
        void t.offsetWidth; // restart the flip animation
        t.classList.add('flip');
        if (n < steps) setTimeout(tick, 55 + row * 8);
      };
      setTimeout(tick, 120 + row * 160 + i * 18);
    });
  });
}

/* ─── Ticket card ────────────────────────────────────────────────────── */
function thumbHTML(deal, cls = 'thumb') {
  const img = safeUrl(deal.stay?.image);
  if (img) return `<img class="${cls}" src="${esc(img)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-initial="${esc(deal.city.name[0])}">`;
  return `<div class="${cls} thumb-fallback" aria-hidden="true">${esc(deal.city.name[0])}</div>`;
}
function isSaved(id) { return state.saved.some((s) => s.deal.id === id); }

/* Lot + nocleg = razem. Computed from the same numbers, so the equation always adds up. */
function priceParts(deal, bagKey) {
  const bag = deal.flight.bags?.[bagKey] || {};
  const flight = deal.flight.fare_total + (bag.total || 0);
  const stay = deal.stay?.price_total || 0;
  const perPerson = deal.flight.two_seats_confirmed === false;   // Wizz Air: 2 × price per person, no 2-seat guarantee
  return { flight, stay, total: flight + stay, est: Boolean(bag.estimated) || perPerson, bagEst: Boolean(bag.estimated), perPerson };
}
const approx = (v, est) => `${est ? '<small class="approx">ok.</small>' : ''}${pln(v)}`;
function sumHTML(deal, bagKey, cls = '') {
  const p = priceParts(deal, bagKey);
  const about = p.est ? 'około ' : '';
  const aria = `Lot ${about}${pln(p.flight)} plus nocleg ${pln(p.stay)} równa się ${about}${pln(p.total)} za 2 osoby`;
  return `
  <div class="eq ${cls}" role="group" aria-label="${esc(aria)}">
    <div class="eq-part"><span class="eq-label">Lot</span><span class="eq-val num">${approx(p.flight, p.est)}</span><span class="eq-note">${esc(bagPhrase(bagKey))}${p.bagEst ? ' (szac.)' : ''}${p.perPerson ? ' · 2 × cena za os.' : ''}</span></div>
    <span class="eq-op" aria-hidden="true">+</span>
    <div class="eq-part"><span class="eq-label">Nocleg</span><span class="eq-val num">${pln(p.stay)}</span><span class="eq-note">${deal.stay ? nightsLabel(deal.stay.nights) : ''}</span></div>
    <span class="eq-op" aria-hidden="true">=</span>
    <div class="eq-part eq-total"><span class="eq-label">Razem · 2 os.</span><span class="eq-big num">${approx(p.total, p.est)}</span><span class="eq-note num">${pln(p.total / 2)}/os.</span></div>
  </div>`;
}

function ticketHTML(deal, i, opts = {}) {
  const f = state.filters;
  const out = deal.flight.out, back = deal.flight.back;
  const href = opts.date ? `#/d/${opts.date}/${encodeURIComponent(deal.id)}` : `#/o/${encodeURIComponent(deal.id)}`;
  const stay = deal.stay;
  return `
  <article class="ticket reveal" style="--accent: var(--${accentOf(deal)}); --i:${Math.min(i, 12)}">
    <a class="ticket-link" href="${href}">
      <div class="t-top">
        <div class="t-labels">${opts.kicker || labelsHTML(deal)}</div>
        <div class="t-route">
          <div class="t-apt"><b>${esc(out.from)}</b><span>${esc(out.from_city || out.from_name || '')}</span></div>
          <div class="t-path">${icon('plane')}</div>
          <div class="t-apt t-apt-to"><b>${esc(out.to)}</b><span>${esc(deal.city.name)}${deal.city.via ? ` (${esc(deal.city.via)})` : ''}</span></div>
        </div>
        <div class="t-when"><span>${esc(dayShort(deal.trip.out_date))} → ${esc(dayShort(deal.trip.back_date))}</span><span class="nights">${nightsLabel(deal.trip.nights)}</span></div>
        <div class="t-times num">${hhmm(out.dep)}–${arrTime(out)} · powrót ${hhmm(back.dep)}–${arrTime(back)} · ${esc(deal.flight.carrier)}</div>
      </div>
      <div class="t-perf" aria-hidden="true"></div>
      ${stay ? `
      <div class="t-stay">
        ${thumbHTML(deal)}
        <div>
          <div class="t-stay-kicker">${icon('bed-double', 'ico-sm')}${esc(stay.kind || 'Nocleg')} · ${nightsLabel(stay.nights)}</div>
          <div class="t-stay-name">${esc(stay.name)}</div>
          <div class="t-stay-meta">
            ${stay.rating ? `<span class="score" title="Ocena gości">${fmtRating(stay.rating)}</span><span>${ratingWord(stay.rating)}</span>` : ''}
            ${stay.distance_km != null ? `<span>${nf1.format(stay.distance_km)} km od centrum</span>` : ''}
          </div>
        </div>
      </div>` : ''}
      <div class="t-total">${sumHTML(deal, f.bag)}</div>
    </a>
    <button class="t-save" type="button" data-action="save" data-id="${esc(deal.id)}" data-date="${esc(opts.date || state.data.date)}" aria-pressed="${isSaved(deal.id)}" aria-label="${isSaved(deal.id) ? 'Usuń z zapisanych' : 'Zapisz'}: ${esc(deal.city.name)}">${icon('heart')}</button>
  </article>`;
}

/* ─── Views ──────────────────────────────────────────────────────────── */
function noticeHTML(data) {
  const out = [];
  if (data.sample) {
    out.push(`<p class="notice">${icon('info')}<span><b>Dane przykładowe.</b> Tak będzie wyglądać aplikacja. Pierwsze prawdziwe wyszukiwanie jeszcze się nie odbyło, więc ceny i hotele poniżej są zmyślone.</span></p>`);
  }
  const hourPL = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Europe/Warsaw' }).format(new Date()));
  const staleDays = daysBetween(data.date, todayISO());
  if (!data.sample && (staleDays >= 2 || (staleDays === 1 && hourPL >= 10))) {
    out.push(`<p class="notice">${icon('clock')}<span>Dzisiejsze wyszukiwanie się nie udało albo jeszcze trwa. Pokazuję okazje z ${esc(stampLabel(data.generated_at))}, więc ceny mogły się zmienić.</span></p>`);
  }
  return out.join('');
}
function toolbarHTML() {
  const f = state.filters;
  const n = activeFilterCount();
  const pozOnly = f.origins.length === 1 && f.origins[0] === 'POZ';
  return `
  <div class="toolbar" role="toolbar" aria-label="Szybkie filtry">
    <button class="chip" type="button" data-action="open-filters">${icon('sliders-horizontal')}Filtry${n ? `<span class="chip-count">${n}</span>` : ''}</button>
    <button class="chip" type="button" data-action="toggle" data-key="lastMinuteOnly" aria-pressed="${f.lastMinuteOnly}">${icon('zap')}Last minute</button>
    <button class="chip" type="button" data-action="toggle" data-key="weekendOnly" aria-pressed="${f.weekendOnly}">${icon('calendar')}Weekendy</button>
    <button class="chip" type="button" data-action="toggle-poz" aria-pressed="${pozOnly}">${icon('map-pin')}Tylko z Poznania</button>
    <button class="chip" type="button" data-action="open-filters" data-focus="bag">${icon('luggage')}Bagaż: ${esc(bagMeta()[f.bag]?.short)}</button>
    <button class="chip" type="button" data-action="open-filters" data-focus="budget">${icon('wallet')}${f.budget >= BUDGET_MAX ? 'Bez limitu' : `Do ${pln(f.budget)}`}</button>
  </div>`;
}
function footerHTML(data) {
  const s = data.stats || {};
  const parts = [];
  if (s.flight_options) parts.push(`${nf.format(s.flight_options)} kombinacji lotów`);
  if (s.hotel_searches) parts.push(`${s.hotel_searches} wyszukiwań noclegów`);
  return `
  <footer class="footer">
    <p>Aktualizacja: ${esc(stampLabel(data.generated_at))}${parts.length ? ` · sprawdzono ${parts.join(' i ')}` : ''}.</p>
    <p>Ceny zmieniają się często. Przed zakupem zawsze zobaczysz aktualną cenę u przewoźnika i w serwisie noclegowym. <a href="#/info">Skąd są dane?</a></p>
  </footer>`;
}

function renderHome(opts = {}) {
  const data = state.data;
  const deals = filtered(data.deals);
  const firstVisit = state.view !== 'home-rendered';
  main.innerHTML = `
    <div class="wrap">
      ${noticeHTML(data)}
      ${boardHTML(deals.slice(0, 3), data, deals.length)}
      ${toolbarHTML()}
      <div class="list-head"><h2>Wszystkie okazje</h2><p class="num">${deals.length} z ${data.deals.length}</p></div>
      ${deals.length ? `<div class="tickets">${deals.map((d, i) => ticketHTML(d, i)).join('')}</div>` : emptyHTML(data)}
    </div>
    ${footerHTML(data)}`;
  runFlaps(main, true);
  state.view = 'home-rendered';
  if (opts.restoreScroll) window.scrollTo(0, state.homeScroll);
  else if (!firstVisit && opts.keepScroll) { /* filter change: keep position */ } else window.scrollTo(0, 0);
}
function emptyHTML(data) {
  const f = state.filters;
  const hints = [];
  if (f.budget < BUDGET_MAX) hints.push('podnieś budżet');
  if (f.origins.length < (data.defaults?.origins?.length || 5)) hints.push('dodaj lotniska');
  if (f.weekendOnly || f.lastMinuteOnly) hints.push('wyłącz „Weekendy” lub „Last minute”');
  return `
  <section class="state">
    <h2>Nic w tych filtrach</h2>
    <p>Dziś żadna okazja nie spełnia wszystkich warunków.${hints.length ? ` Spróbuj: ${hints.join(', ')}.` : ''}</p>
    <button class="btn btn-primary" type="button" data-action="reset-filters">Wyczyść filtry</button>
  </section>`;
}

async function renderDeal(date, id) {
  let data = state.data;
  let archived = false;
  if (date && date !== state.data.date) {
    main.innerHTML = `<div class="loading" role="status"><span class="brand-tile spin" aria-hidden="true">W</span><span>Wczytuję ofertę z ${esc(ddmm(date))}…</span></div>`;
    data = await loadArchive(date);
    archived = true;
  }
  let deal = data?.deals?.find((d) => d.id === id);
  let replaced = false;
  if (!deal && date) {
    // A same-day re-run keeps earlier proposals in the day's archive under "replaced".
    const arch = date === state.data.date ? await fetchJSON(archiveUrl(date)).catch(() => null) : data;
    deal = arch?.deals?.find((d) => d.id === id) || arch?.replaced?.find((d) => d.id === id);
    replaced = Boolean(arch?.replaced?.some((d) => d.id === id));
    if (deal) archived = true;
  }
  if (!deal) {
    const snap = state.saved.find((s) => s.deal.id === id && (!date || s.date === date));
    if (snap) { deal = snap.deal; archived = snap.date !== state.data.date; date = snap.date; }
  }
  if (!deal) {
    main.innerHTML = `<div class="wrap"><section class="state"><h2>Ta oferta wygasła</h2><p>Nie mamy już zapisu tej propozycji. Zobacz dzisiejsze okazje, ceny odświeżamy codziennie rano.</p><a class="btn btn-primary" href="#/">Dzisiejsze okazje</a></section></div>`;
    return;
  }
  const f = state.filters;
  const bagKey = f.bag in (deal.flight.bags || {}) ? f.bag : 'cabin10';
  const bags = bagMeta();
  const out = deal.flight.out, back = deal.flight.back;
  const stay = deal.stay;
  const accent = accentOf(deal);
  const flightTotal = deal.flight.fare_total + (deal.flight.bags?.[bagKey]?.total || 0);
  const bagInfo = deal.flight.bags?.[bagKey] || {};
  const days = daysBetween(todayISO(), deal.trip.out_date);   // from today, also for archived proposals
  const w = deal.weather;
  const bookFlight = safeUrl(deal.flight.book_url);
  const compare = safeUrl(deal.flight.compare_url);
  const bookStay = safeUrl(stay?.book_url);
  const dealDate = date || data.date;

  main.innerHTML = `
  <article class="detail" style="--accent: var(--${accent})">
    <nav class="detail-bar" aria-label="Nawigacja oferty">
      <a class="iconbtn" href="#/" data-action="back" aria-label="Wróć do listy">${icon('arrow-left')}</a>
      <div class="right">
        <button class="iconbtn" type="button" data-action="save" data-id="${esc(deal.id)}" data-date="${esc(dealDate)}" aria-pressed="${isSaved(deal.id)}" aria-label="${isSaved(deal.id) ? 'Usuń z zapisanych' : 'Zapisz ofertę'}">${icon('heart')}</button>
        <button class="iconbtn" type="button" data-action="share" data-id="${esc(deal.id)}" data-date="${esc(dealDate)}" aria-label="Udostępnij ofertę">${icon('share-2')}</button>
      </div>
    </nav>

    <header class="d-hero" style="--accent: var(--${accent})">
      <p class="d-eyebrow"><span>${esc(deal.city.country)}</span><span class="dot">●</span><span>${esc(rangeLabel(deal.trip.out_date, deal.trip.back_date))}</span><span class="dot">●</span><span>${nightsLabel(deal.trip.nights)}, 2 osoby</span></p>
      <h1 class="d-city">${esc(deal.city.name)}${deal.city.via ? `<span class="via">Lotnisko ${esc(deal.city.via)}</span>` : ''}</h1>
      ${deal.city.tagline ? `<p class="d-tagline">${esc(deal.city.tagline)}</p>` : ''}
      <div class="d-labels">${labelsHTML(deal)}</div>
      ${archived ? `<p class="notice archived">${icon('clock')}<span>${replaced ? 'Tę propozycję zastąpiło nowsze wyszukiwanie' : `Propozycja z ${esc(dayLong(dealDate))}`}. Ceny mogły się zmienić, sprawdź je przed zakupem.</span></p>` : ''}
      <dl class="facts">
        <div class="fact"><dt>Na miejscu</dt><dd class="num">${deal.trip.on_ground_estimated ? '~' : ''}${esc(durationLabel(deal.trip.on_ground_h))}<small>od lądowania do odlotu${deal.trip.on_ground_estimated ? ' (szacunkowo)' : ''}</small></dd></div>
        <div class="fact"><dt>Wylot</dt><dd>${esc(untilLabel(days))}<small>${esc(dayLong(deal.trip.out_date))}</small></dd></div>
        <div class="fact"><dt>Pogoda</dt><dd class="num">${w ? `${Math.round(w.t_max)}°C` : '—'}<small>${w ? esc(w.text || (w.kind === 'forecast' ? 'prognoza' : 'średnio o tej porze')) : 'brak prognozy'}</small></dd></div>
      </dl>
    </header>

    <section class="d-card" aria-labelledby="h-flight">
      <div class="d-card-head"><h2 id="h-flight">${icon('plane')}Lot</h2><span class="muted">${esc(deal.flight.carrier)} · bez przesiadek</span></div>
      <div class="d-card-body">
        <div class="legs">
          ${legHTML('Tam', out)}
          ${legHTML('Powrót', back)}
        </div>
        ${deal.flight.discount_pct >= 20 && deal.flight.typical_pp ? `<p class="bag-desc">${icon('trending-down')}<span>Ten termin jest o <b>${deal.flight.discount_pct}% tańszy</b> niż typowa cena tej trasy w najbliższych tygodniach (${pln(deal.flight.typical_pp)} za osobę w obie strony).</span></p>` : ''}
        <div class="bags">
          <div class="bags-title">Bagaż w cenie</div>
          <div class="seg" role="radiogroup" aria-label="Wariant bagażu">
            ${Object.keys(deal.flight.bags || {}).map((k) => `
              <label><input type="radio" name="bag" value="${k}" data-action="bag" ${k === bagKey ? 'checked' : ''}>
                <span class="seg-name">${esc(bags[k]?.short || k)}</span>
                <span class="seg-price num">${deal.flight.bags[k].total ? `${deal.flight.bags[k].estimated ? '~' : ''}+${pln(deal.flight.bags[k].total)}` : 'w cenie biletu'}</span></label>`).join('')}
          </div>
          <p class="bag-desc">${icon('luggage')}<span>${esc(bagInfo.note || bags[bagKey]?.long || '')}</span></p>
          ${bagInfo.estimated ? `<p class="fineprint">${esc(bagInfo.basis || 'Cena bagażu jest szacunkiem na podstawie cennika przewoźnika.')} Dokładną kwotę zobaczysz przy zakupie.</p>` : ''}
        </div>
        <ul class="lines num">
          <li><span>Bilety dla 2 osób (${deal.flight.two_seats_confirmed === false ? '2 × cena za osobę z rozkładu' : 'taryfa podstawowa'})</span><span>${deal.flight.two_seats_confirmed === false ? '~' : ''}${pln(deal.flight.fare_total)}</span></li>
          <li><span>Bagaż: ${esc(bags[bagKey]?.short || '')}${bagInfo.estimated ? ' (szacunek)' : ''}</span><span>${bagInfo.total ? `${bagInfo.estimated ? '~' : ''}${pln(bagInfo.total)}` : '0 zł'}</span></li>
          <li class="sum"><span>Lot razem</span><span>${bagInfo.estimated ? '~' : ''}${pln(flightTotal)}</span></li>
        </ul>
        <div class="cta">
          ${bookFlight ? `<a class="btn btn-primary btn-block" href="${esc(bookFlight)}" target="_blank" rel="noopener">${icon('external-link')}Kup lot w ${esc(deal.flight.carrier)}</a>` : ''}
          ${compare ? `<a class="btn btn-ghost btn-block" href="${esc(compare)}" target="_blank" rel="noopener">Porównaj w Google Flights</a>` : ''}
        </div>
        <p class="fineprint">${deal.flight.carrier_code === 'W6' ? 'Link otwiera wyszukiwarkę Wizz Air z tymi datami i lotniskami; sprawdź na stronie, czy ustawiło się 2 dorosłych.' : 'Link otwiera wyszukiwarkę przewoźnika z tymi datami, lotniskami i 2 dorosłymi.'} Bagaż dodajesz w trakcie rezerwacji.</p>
        ${deal.flight.two_seats_confirmed === false ? `<p class="fineprint">${esc(deal.flight.carrier)} podaje w rozkładzie cenę za osobę, więc cena lotu to 2 × cena z rozkładu i nie ma gwarancji, że w tej taryfie zostały 2 miejsca. Godziny przylotu (~) są szacunkowe. Przy zakupie sprawdź, czy przewoźnik nie dolicza opłaty administracyjnej.</p>` : ''}
      </div>
    </section>

    ${stay ? stayHTML(deal, bookStay) : ''}

    <section class="total-card" aria-labelledby="h-total">
      <h2 class="total-label" id="h-total">Cena całkowita za 2 osoby</h2>
      ${sumHTML(deal, bagKey, 'eq-dark')}
      <ul class="lines num">
        <li><span>Loty w obie strony${deal.flight.two_seats_confirmed === false ? ' (2 × cena za os.)' : ''}</span><span>${deal.flight.two_seats_confirmed === false ? '~' : ''}${pln(deal.flight.fare_total)}</span></li>
        <li><span>Bagaż: ${esc(bags[bagKey]?.short || '')}${bagInfo.estimated ? ' (szacunek)' : ''}</span><span>${bagInfo.estimated ? '~' : ''}${pln(bagInfo.total || 0)}</span></li>
        ${stay ? `<li><span>Nocleg, ${nightsLabel(stay.nights)}</span><span>${pln(stay.price_total)}</span></li>` : ''}
        <li class="sum"><span>Razem</span><span>${priceParts(deal, bagKey).est ? '~' : ''}${pln(total(deal, bagKey))}</span></li>
      </ul>
      ${bagInfo.estimated ? `<p class="fineprint">W tym szacowany koszt bagażu: ~${pln(bagInfo.total)}. Loty i nocleg to ceny z wyszukiwarek.</p>` : ''}
      <button class="btn btn-block btn-share" type="button" data-action="share" data-id="${esc(deal.id)}" data-date="${esc(dealDate)}">${icon('share-2')}Wyślij do konsultacji</button>
      <p class="fineprint">Ceny sprawdzone ${esc(stampLabel(deal.checked_at || data.generated_at))}.${stay?.taxes_note ? ` ${esc(stay.taxes_note)}` : ''}</p>
    </section>

    <div class="info-list">
      ${deal.transfer ? `<div class="info-item">${icon('bus')}<div><b>Z lotniska do centrum</b>${esc(deal.transfer)}</div></div>` : ''}
      ${deal.city.why ? `<div class="info-item">${icon('sparkles')}<div><b>Dlaczego warto</b>${esc(deal.city.why)}</div></div>` : ''}
      <div class="info-item">${icon('eye-off')}<div><b>Nie interesuje Cię ${esc(deal.city.name)}?</b><button class="btn btn-ghost" style="margin-top:8px;min-height:40px" type="button" data-action="hide-city" data-key="${esc(deal.city.key)}" data-name="${esc(deal.city.name)}">Nie pokazuj tego kierunku</button></div></div>
    </div>
  </article>`;
  window.scrollTo(0, 0);
}
function legHTML(kicker, leg) {
  const seats = leg.seats_left != null && leg.seats_left > 0 && leg.seats_left <= 5
    ? `<span class="seats">${leg.seats_left === 1 ? 'Ostatnie miejsce' : `Zostały ${leg.seats_left} miejsca`} w tej cenie</span>` : '';
  return `
  <div class="leg">
    <div class="leg-kicker"><span>${kicker} · ${esc(dayShort(leg.dep))}</span>${seats}</div>
    <div class="leg-end"><b class="num">${hhmm(leg.dep)}</b><span>${esc(leg.from)} ${esc(leg.from_name || '')}</span></div>
    <div class="leg-mid">${icon('plane')}${esc(leg.no || '')}${leg.duration_min ? `<br>${Math.floor(leg.duration_min / 60)} h ${leg.duration_min % 60} min` : ''}</div>
    <div class="leg-end to"><b class="num">${arrTime(leg)}</b><span>${esc(leg.to)} ${esc(leg.to_name || '')}</span></div>
  </div>`;
}
function stayHTML(deal, bookStay) {
  const s = deal.stay;
  const perks = [];
  // Only facts the data source states; nothing is assumed.
  if (s.free_cancellation === true) perks.push(`<span class="perk">${icon('check')}Bezpłatne odwołanie</span>`);
  if (s.breakfast === true) perks.push(`<span class="perk">${icon('check')}Śniadanie w cenie</span>`);
  if (s.private_bathroom === true) perks.push(`<span class="perk">${icon('check')}Prywatna łazienka</span>`);
  (s.amenities || []).slice(0, 4).forEach((a) => perks.push(`<span class="perk">${esc(a)}</span>`));
  const alts = (s.alternatives || []).filter((a) => safeUrl(a.book_url));
  const bookingSame = safeUrl(s.booking_url);
  const bookingCity = safeUrl(s.booking_city_url);
  return `
  <section class="d-card" aria-labelledby="h-stay">
    <div class="stay-hero">${thumbHTML(deal, 'stay-img')}</div>
    <div class="d-card-head"><h2 id="h-stay">${icon('bed-double')}Nocleg</h2><span class="muted">${esc(dayShort(s.check_in))} → ${esc(dayShort(s.check_out))}<br>${nightsLabel(s.nights)}, 2 dorosłych</span></div>
    <div class="d-card-body">
      <h3 class="stay-name">${esc(s.name)}</h3>
      <div class="stay-meta">
        ${s.rating ? `<span class="score">${fmtRating(s.rating)}</span><span>${ratingWord(s.rating)}${s.reviews ? ` · ${nf.format(s.reviews)} opinii` : ''}${s.rating_source ? ` · ocena ${esc(s.rating_source)}` : ''}</span>` : ''}
        ${s.stars ? `<span class="stars" aria-label="${s.stars} gwiazdki">${'★'.repeat(s.stars)}</span>` : ''}
        ${s.kind ? `<span>${esc(s.kind)}</span>` : ''}
      </div>
      <div class="stay-meta">${s.distance_km != null ? `<span>${icon('map-pin', 'ico-sm')} ${nf1.format(s.distance_km)} km od centrum${s.area ? ` · ${esc(s.area)}` : ''}</span>` : ''}</div>
      ${perks.length ? `<div class="perks">${perks.join('')}</div>` : ''}
      <ul class="lines num">
        <li><span>${nightsLabel(s.nights)} × ${pln(s.price_night || s.price_total / s.nights)}</span><span>${pln(s.price_total)}</span></li>
        <li class="sum"><span>Nocleg razem (2 os.)</span><span>${pln(s.price_total)}</span></li>
      </ul>
      ${s.taxes_note ? `<p class="fineprint">${esc(s.taxes_note)}</p>` : ''}
      <div class="cta">
        ${bookStay ? `<a class="btn btn-primary btn-block" href="${esc(bookStay)}" target="_blank" rel="noopener">${icon('external-link')}${s.source === 'trivago' ? `Zobacz tę ofertę${s.provider ? ` (${esc(s.provider)})` : ''}` : `Zarezerwuj w ${esc(s.provider || 'serwisie')}`}</a>` : ''}
        ${bookingSame ? `<a class="btn btn-ghost btn-block" href="${esc(bookingSame)}" target="_blank" rel="noopener">Szukaj tego obiektu na Booking.com</a>` : ''}
      </div>
      ${s.source === 'trivago' ? '<p class="fineprint">Pierwszy przycisk otwiera porównywarkę trivago z tymi datami i 2 dorosłymi, a stamtąd przejdziesz do serwisu z tą ofertą. Cena mogła się zmienić od porannego wyszukiwania.</p>' : ''}
      ${bookingCity ? `<p class="fineprint"><a href="${esc(bookingCity)}" target="_blank" rel="noopener">Więcej hoteli z oceną 8+ do 3 km od centrum na Booking.com →</a></p>` : ''}
      ${alts.length ? `
      <div class="alts"><h3>Inne opcje na te same daty</h3>
        ${alts.map((a) => `
        <a class="alt" href="${esc(a.book_url)}" target="_blank" rel="noopener">
          <div><div class="alt-name">${esc(a.name)}</div><div class="alt-meta">${a.rating ? `${fmtRating(a.rating)} · ` : ''}${a.distance_km != null ? `${nf1.format(a.distance_km)} km od centrum · ` : ''}${esc(a.provider || '')}</div></div>
          <div class="alt-price num">${pln(a.price_total)}<small>${a.price_total > s.price_total ? `+${pln(a.price_total - s.price_total)}` : `${pln(a.price_total - s.price_total)}`}</small></div>
        </a>`).join('')}
      </div>` : ''}
    </div>
  </section>`;
}

function renderSaved() {
  const items = [...state.saved].sort((a, b) => a.deal.trip.out_date.localeCompare(b.deal.trip.out_date));
  main.innerHTML = `
  <div class="wrap">
    <div class="list-head" style="margin-top:22px"><h2>Zapisane</h2><p>${items.length} ${plural(items.length, 'oferta', 'oferty', 'ofert')}</p></div>
    ${items.length ? `<div class="tickets">${items.map((s, i) => ticketHTML(s.deal, i, {
      date: s.date,
      kicker: `<span class="lbl lbl-weekend">${icon('heart')}Zapisano ${esc(ddmm(s.date))}</span>${s.date !== state.data.date ? '<span class="lbl lbl-new">Cena z dnia zapisu</span>' : ''}`,
    })).join('')}</div>`
      : `<section class="state"><h2>Nic tu jeszcze nie ma</h2><p>Stuknij serduszko przy ofercie, żeby ją odłożyć na później albo przedyskutować.</p><a class="btn btn-primary" href="#/">Przeglądaj okazje</a></section>`}
  </div>`;
  window.scrollTo(0, 0);
}

function renderInfo() {
  const d = state.data;
  const s = d.stats || {};
  const sources = (s.sources || []).map((x) => `<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.role)}</td><td>${esc(x.status || '')}</td></tr>`).join('');
  main.innerHTML = `
  <div class="prose">
    <h1>Jak to działa</h1>
    <p>Codziennie rano automat przeszukuje tanie loty <b>Ryanair i Wizz Air</b> w obie strony z <b>Poznania</b> i pobliskich lotnisk (Wrocław, Bydgoszcz, Szczecin, Łódź) do miast, które nadają się na city break. Szuka wyjazdów na <b>2–4 noce</b> w ciągu najbliższych <b>8 tygodni</b>.</p>
    <p>Do najlepszych połączeń dobiera nocleg na <b>dokładnie te same daty dla 2 dorosłych</b>: hotel co najmniej 2★ albo apartament (bez hosteli), z oceną gości co najmniej 8/10, zwykle do 3 km od centrum (jeśli tak blisko nic nie spełnia kryteriów, do 5 km). Odległość zawsze widać przy ofercie. Z tych obiektów wybiera najtańszy.</p>
    <h2>Co jest w cenie</h2>
    <ul>
      <li><b>Loty w obie strony dla 2 osób</b>, według cen z wyszukiwarki przewoźnika.</li>
      <li><b>Bagaż</b> w wybranym wariancie: sam plecak (w cenie biletu), walizka kabinowa 10 kg dla każdej osoby albo jedna wspólna walizka rejestrowana 20 kg. Cenę bagażu <b>szacujemy</b> ze środka oficjalnego cennika przewoźnika (Ryanair lub Wizz Air) i kursu euro z NBP, bo przewoźnicy nie podają jej bez rozpoczęcia rezerwacji. Wizz Air podaje w rozkładzie cenę za osobę, więc przy jego lotach cena dla 2 osób też jest szacunkiem. Dokładną kwotę zobaczysz przy zakupie.</li>
      <li><b>Nocleg na cały pobyt</b> dla 2 osób.</li>
    </ul>
    <p>Nie wliczamy dojazdu na lotnisko ani z lotniska do centrum. Przy każdej ofercie jest podpowiedź, jak dojechać.</p>
    <h2>Skąd są dane</h2>
    ${sources ? `<table class="src-table"><thead><tr><th>Źródło</th><th>Do czego</th><th>Dziś</th></tr></thead><tbody>${sources}</tbody></table>` : '<p>Lista źródeł pojawi się po pierwszym wyszukiwaniu.</p>'}
    <p>Ceny zmieniają się nawet kilka razy dziennie. Kiedy klikniesz „Kup lot” albo „Zarezerwuj”, zobaczysz aktualną cenę u przewoźnika lub w serwisie noclegowym.</p>
    <h2>Udostępnianie</h2>
    <p>„Wyślij do konsultacji” otwiera systemowe udostępnianie (iMessage, WhatsApp, Messenger, e-mail). Odbiorca zobaczy tę samą propozycję bez logowania, także gdy jutro pojawią się nowe okazje.</p>
    <h2>Na telefonie</h2>
    <p>Na iPhonie otwórz stronę w Safari, stuknij <b>Udostępnij → Do ekranu początkowego</b>. Wypad będzie działał jak aplikacja, także offline z ostatnio pobranymi okazjami.</p>
    <p class="muted" style="margin-top:24px">Ostatnia aktualizacja: ${esc(stampLabel(d.generated_at))}.</p>
  </div>`;
  window.scrollTo(0, 0);
}

/* ─── Filters sheet ──────────────────────────────────────────────────── */
function filtersBodyHTML() {
  const f = state.filters;
  const data = state.data;
  const origins = (data.defaults?.origins || Object.keys(data.origins || {}));
  const bags = bagMeta();
  const budgetLabel = f.budget >= BUDGET_MAX ? 'bez limitu' : pln(f.budget);
  return `
  <div class="fgroup"><div class="flabel">Lotniska wylotu</div>
    <div class="toggles">${origins.map((code) => {
      const o = data.origins?.[code] || { city: code };
      return `<label class="toggle"><input type="checkbox" name="origins" value="${esc(code)}" ${f.origins.includes(code) ? 'checked' : ''}><span>${esc(o.city)} <small>${esc(code)}${o.drive ? ` · ${esc(o.drive)}` : ''}</small></span></label>`;
    }).join('')}</div>
  </div>
  <div class="fgroup" id="fg-budget"><div class="flabel"><label for="budget">Budżet na 2 osoby</label><output id="budget-out" for="budget">${budgetLabel}</output></div>
    <input class="range" id="budget" name="budget" type="range" min="${BUDGET_MIN}" max="${BUDGET_MAX}" step="100" value="${Math.min(f.budget, BUDGET_MAX)}" aria-describedby="budget-scale">
    <div class="range-scale" id="budget-scale"><span>${pln(BUDGET_MIN)}</span><span>bez limitu</span></div>
  </div>
  <div class="fgroup"><div class="flabel">Liczba nocy</div>
    <div class="toggles">${[2, 3, 4].map((n) => `<label class="toggle"><input type="checkbox" name="nights" value="${n}" ${f.nights.includes(n) ? 'checked' : ''}><span>${nightsLabel(n)}</span></label>`).join('')}</div>
  </div>
  <div class="fgroup" id="fg-bag"><div class="flabel">Bagaż w cenie</div>
    <div class="toggles">${Object.keys(bags).map((k) => `<label class="toggle"><input type="radio" name="bag" value="${k}" ${f.bag === k ? 'checked' : ''}><span>${esc(bags[k].short)}</span></label>`).join('')}</div>
    <p class="fineprint">${esc(bags[f.bag]?.long || '')}</p>
  </div>
  <div class="fgroup">
    <label class="switch-row"><span>Tylko weekendy<small>Wylot czw.–sob., powrót nd. lub pn.</small></span><input class="switch" type="checkbox" name="weekendOnly" ${f.weekendOnly ? 'checked' : ''}></label>
    <label class="switch-row"><span>Tylko last minute<small>Wylot w ciągu ${state.data.defaults?.last_minute_days || 21} dni</small></span><input class="switch" type="checkbox" name="lastMinuteOnly" ${f.lastMinuteOnly ? 'checked' : ''}></label>
  </div>
  <div class="fgroup"><div class="flabel">Kolejność</div>
    <div class="toggles">${Object.entries(SORTS).map(([k, v]) => `<label class="toggle"><input type="radio" name="sort" value="${k}" ${f.sort === k ? 'checked' : ''}><span>${v}</span></label>`).join('')}</div>
  </div>
  <div class="fgroup"><div class="flabel">Ukryte kierunki</div>
    ${state.hidden.length ? `<div class="hidden-list">${state.hidden.map((k) => `<button type="button" data-action="unhide-city" data-key="${esc(k)}">${icon('undo-2', 'ico-sm')}${esc(cityNameByKey(k))}</button>`).join('')}</div>` : '<p class="muted">Brak. Kierunek ukryjesz na karcie oferty.</p>'}
  </div>`;
}
function cityNameByKey(key) {
  const d = state.data.deals.find((x) => x.city.key === key);
  return d ? d.city.name : key;
}
function openFilters(focus) {
  sheet.querySelector('[data-filters-body]').innerHTML = filtersBodyHTML();
  updateApplyLabel();
  if (typeof sheet.showModal === 'function') sheet.showModal(); else sheet.setAttribute('open', '');
  if (focus) sheet.querySelector(`#fg-${focus}`)?.scrollIntoView({ block: 'center' });
}
function updateApplyLabel() {
  const n = filtered(state.data.deals).length;
  sheet.querySelector('[data-apply-label]').textContent = n ? `Pokaż ${n} ${plural(n, 'ofertę', 'oferty', 'ofert')}` : 'Brak ofert — zmień filtry';
}
sheet.addEventListener('input', (e) => {
  const el = e.target;
  const f = state.filters;
  if (el.name === 'origins' || el.name === 'nights') {
    const vals = [...sheet.querySelectorAll(`input[name="${el.name}"]:checked`)].map((i) => (el.name === 'nights' ? Number(i.value) : i.value));
    if (!vals.length) { el.checked = true; toast(el.name === 'origins' ? 'Zostaw przynajmniej jedno lotnisko' : 'Zostaw przynajmniej jedną opcję'); return; }
    f[el.name] = vals;
  } else if (el.name === 'budget') {
    f.budget = Number(el.value);
    sheet.querySelector('#budget-out').textContent = f.budget >= BUDGET_MAX ? 'bez limitu' : pln(f.budget);
  } else if (el.name === 'bag' || el.name === 'sort') {
    f[el.name] = el.value;
    if (el.name === 'bag') sheet.querySelector('#fg-bag .fineprint').textContent = bagMeta()[f.bag]?.long || '';
  } else if (el.name === 'weekendOnly' || el.name === 'lastMinuteOnly') {
    f[el.name] = el.checked;
  }
  saveFilters();
  updateApplyLabel();
});
sheet.addEventListener('close', () => { if (currentRoute().name === 'home') renderHome({ keepScroll: true }); });
sheet.addEventListener('click', (e) => { if (e.target === sheet) sheet.close(); });

/* ─── Saving, hiding, sharing ────────────────────────────────────────── */
async function findDeal(id, date) {
  if (!date || date === state.data.date) {
    const d = state.data.deals.find((x) => x.id === id);
    if (d) return d;
  }
  const arch = date ? await loadArchive(date) : null;
  return arch?.deals?.find((x) => x.id === id) || state.saved.find((s) => s.deal.id === id)?.deal || null;
}
async function toggleSave(btn) {
  const { id, date } = btn.dataset;
  const idx = state.saved.findIndex((s) => s.deal.id === id);
  if (idx >= 0) {
    state.saved.splice(idx, 1);
    toast('Usunięto z zapisanych');
  } else {
    const deal = await findDeal(id, date);
    if (!deal) return;
    state.saved.push({ date: date || state.data.date, savedAt: new Date().toISOString(), deal });
    toast('Zapisano, znajdziesz ją w „Zapisane”');
  }
  writeLS(LS.saved, state.saved);
  const pressed = isSaved(id);
  document.querySelectorAll(`[data-action="save"][data-id="${CSS.escape(id)}"]`).forEach((b) => b.setAttribute('aria-pressed', String(pressed)));
  updateSavedCount();
  if (currentRoute().name === 'saved') renderSaved();
}
function updateSavedCount() {
  const el = document.querySelector('[data-saved-count]');
  el.hidden = !state.saved.length;
  el.textContent = state.saved.length;
}
function shareLink(deal, date) {
  if (deal.share_path) return new URL(deal.share_path, document.baseURI).href;
  return new URL(`#/d/${date}/${encodeURIComponent(deal.id)}`, document.baseURI).href;
}
function shareText(deal) {
  const bagKey = state.filters.bag;
  const s = deal.stay;
  const origin = state.data?.origins?.[deal.flight.out.from];
  const p = priceParts(deal, bagKey);
  const estimated = p.est;
  const lines = [
    `${deal.city.name}, ${rangeLabel(deal.trip.out_date, deal.trip.back_date)} (${nightsLabel(deal.trip.nights)})`,
    `Lot ${deal.flight.carrier} z ${origin?.city_gen || deal.flight.out.from}, ${bagPhrase(bagKey)}${p.bagEst ? ' (szacunek)' : ''}${p.perPerson ? ', 2 × cena za osobę' : ''}: ${estimated ? 'ok. ' : ''}${pln(p.flight)}`,
    s ? `+ nocleg ${s.name}${s.rating ? ` (${fmtRating(s.rating)}/10)` : ''}: ${pln(s.price_total)}` : '',
    `= ${estimated ? 'ok. ' : ''}${pln(priceParts(deal, bagKey).total)} za 2 osoby`,
    'Co myślisz?',
  ];
  return lines.filter(Boolean).join('\n');
}
async function share(btn) {
  const { id, date } = btn.dataset;
  const deal = await findDeal(id, date);
  if (!deal) return;
  const url = shareLink(deal, date || state.data.date);
  const text = shareText(deal);
  if (navigator.share) {
    try { await navigator.share({ title: `Wypad: ${deal.city.name}`, text, url }); return; } catch (e) { if (e.name === 'AbortError') return; }
  }
  try {
    await navigator.clipboard.writeText(`${text}\n${url}`);
    toast('Skopiowano opis i link. Wklej go w wiadomości.');
  } catch {
    window.prompt('Skopiuj link do oferty:', url);
  }
}
function hideCity(btn) {
  const { key, name } = btn.dataset;
  if (!state.hidden.includes(key)) state.hidden.push(key);
  writeLS(LS.hidden, state.hidden);
  toast(`${name} nie będzie się pokazywać. Przywrócisz w filtrach.`);
  location.hash = '#/';
}
function unhideCity(btn) {
  state.hidden = state.hidden.filter((k) => k !== btn.dataset.key);
  writeLS(LS.hidden, state.hidden);
  btn.remove();
  updateApplyLabel();
}

let toastTimer;
function toast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 2800);
}

/* ─── Events ─────────────────────────────────────────────────────────── */
document.addEventListener('error', (e) => {
  const img = e.target;
  if (!(img instanceof HTMLImageElement) || img.dataset.initial === undefined) return;
  const div = document.createElement('div');
  div.className = `${img.className} thumb-fallback`;
  div.textContent = img.dataset.initial;
  img.replaceWith(div);
}, true);

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el) return;
  const a = el.dataset.action;
  const f = state.filters;
  if (a === 'open-filters') openFilters(el.dataset.focus);
  else if (a === 'toggle') { f[el.dataset.key] = !f[el.dataset.key]; saveFilters(); renderHome({ keepScroll: true }); }
  else if (a === 'toggle-poz') {
    const pozOnly = f.origins.length === 1 && f.origins[0] === 'POZ';
    f.origins = pozOnly ? defaultFilters(state.data).origins : ['POZ'];
    saveFilters(); renderHome({ keepScroll: true });
  } else if (a === 'save') { e.preventDefault(); toggleSave(el); }
  else if (a === 'share') { e.preventDefault(); share(el); }
  else if (a === 'hide-city') hideCity(el);
  else if (a === 'unhide-city') unhideCity(el);
  else if (a === 'reset-filters') {
    state.filters = defaultFilters(state.data); saveFilters();
    if (sheet.open) { sheet.querySelector('[data-filters-body]').innerHTML = filtersBodyHTML(); updateApplyLabel(); } else renderHome({ keepScroll: true });
  } else if (a === 'back' && history.length > 1 && state.cameFromHome) { e.preventDefault(); history.back(); }
});
document.addEventListener('change', (e) => {
  if (e.target.matches('input[data-action="bag"]')) {
    state.filters.bag = e.target.value;
    saveFilters();
    const r = currentRoute();
    renderDeal(r.date, r.id).then(() => {
      const el = main.querySelector(`input[data-action="bag"][value="${CSS.escape(state.filters.bag)}"]`);
      el?.focus({ preventScroll: true });
      el?.closest('.bags')?.scrollIntoView({ block: 'center' });
    });
  }
});

/* ─── Router ─────────────────────────────────────────────────────────── */
function currentRoute() {
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent);
  if (parts[0] === 'o' && parts[1]) return { name: 'deal', id: parts[1], date: null };
  if (parts[0] === 'd' && parts[2]) return { name: 'deal', id: parts[2], date: parts[1] };
  if (parts[0] === 'zapisane') return { name: 'saved' };
  if (parts[0] === 'info') return { name: 'info' };
  return { name: 'home' };
}
let lastRoute = null;
function route() {
  const r = currentRoute();
  if (lastRoute?.name === 'home' && r.name !== 'home') state.homeScroll = window.scrollY;
  state.cameFromHome = lastRoute?.name === 'home' && r.name === 'deal';
  document.querySelectorAll('[data-nav]').forEach((a) => a.toggleAttribute('aria-current', a.dataset.nav === r.name));
  document.querySelectorAll('[data-nav]').forEach((a) => { if (a.dataset.nav === r.name) a.setAttribute('aria-current', 'page'); });
  const wasDeal = lastRoute?.name === 'deal';
  lastRoute = r;
  if (r.name === 'deal') renderDeal(r.date, r.id);
  else if (r.name === 'saved') renderSaved();
  else if (r.name === 'info') renderInfo();
  else renderHome({ restoreScroll: wasDeal });
  main.focus({ preventScroll: true });
  document.title = r.name === 'home' ? 'Wypad — okazje na city break' : `Wypad — ${r.name === 'saved' ? 'zapisane' : r.name === 'info' ? 'jak to działa' : 'oferta'}`;
}

async function boot() {
  try {
    state.data = await fetchJSON(DATA_URL);
  } catch (err) {
    main.innerHTML = `<div class="wrap"><section class="state"><h2>Nie udało się wczytać okazji</h2><p>Sprawdź połączenie z internetem i odśwież stronę. Szczegóły: ${esc(err.message)}</p><button class="btn btn-primary" type="button" onclick="location.reload()">Odśwież</button></section></div>`;
    return;
  }
  state.filters = initFilters(state.data);
  updateSavedCount();
  window.addEventListener('hashchange', route);
  route();
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}
boot();
