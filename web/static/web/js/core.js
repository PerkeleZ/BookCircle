/* BookCircle · ядро: настройки, API-клиент, окна, тема, шапка, предупреждения */

/* ===================== НАСТРОЙКИ ===================== */
const API = window.BOOKCIRCLE_API || (location.protocol === 'file:' ? 'http://127.0.0.1:8000/api' : '/api');  // сайт и API на одном адресе (Django / Docker)

const PAGE = 8;                            // элементов на странице

/* ===================== УТИЛИТЫ ===================== */
const $ = (s, r = document) => r.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const app = $('#app');

let me = null;

let alertState = {count: 0, overdue: 0, results: []};
let unread = 0, alertsAt = 0;  // непрочитанные уведомления; время последнего опроса

let rid = 0;  // номер текущей навигации: ответы устаревших страниц не должны затирать новую

const LOAN = {pending:['Ожидает','warning'],accepted:['Принята','info'],rejected:['Отклонена','secondary'],cancelled:['Отменена','secondary'],handed_over:['Передана','primary'],returned:['Возвращена','success']};

const READ = {want:'Хочу прочитать',reading:'Читаю',done:'Прочитал'};

const COND = {new:'Новое',good:'Хорошее',fair:'Среднее',worn:'Потрёпанное'};

function toast(msg, type = 'success') {
  const t = $('#toast');
  t.innerHTML = `<div class="alert alert-${type} shadow-sm">${esc(msg)}</div>`;
  clearTimeout(toast.h); toast.h = setTimeout(() => t.innerHTML = '', 3500);
}

async function api(path, {method = 'GET', body} = {}) {
  const h = {'Content-Type': 'application/json'};
  const tk = localStorage.getItem('bc_token');
  if (tk && !/^\/auth\/(login|register|password-reset|google\/$|google\/config)/.test(path)) h.Authorization = 'Token ' + tk;  // устаревший токен не должен мешать входу
  const r0 = rid, stale = () => r0 !== rid && !path.startsWith('/auth/');
  let r;
  try { r = await fetch(API + path, {method, headers: h, body: body ? JSON.stringify(body) : undefined}); }
  catch { if (stale()) return new Promise(() => {}); throw {status: 0, data: {detail: 'Сервер недоступен. Проверьте, что Django запущен и адрес API указан верно.'}}; }
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  if (stale()) return new Promise(() => {});  // пользователь уже ушёл на другую страницу
  if (!r.ok) throw {status: r.status, data};
  return data;
}

const errText = e => e?.data?.detail || e?.data?.error || 'Не удалось выполнить действие. Попробуйте ещё раз.';

function fieldErrors(form, e) {
  form.querySelectorAll('.invalid-feedback').forEach(x => x.remove());
  form.querySelectorAll('.is-invalid').forEach(x => x.classList.remove('is-invalid'));
  const d = e?.data || {}; let shown = false;
  for (const [k, v] of Object.entries(d)) {
    const inp = form.elements[k]; if (!inp) continue;
    inp.classList.add('is-invalid');
    const div = document.createElement('div'); div.className = 'invalid-feedback';
    div.textContent = [].concat(v).join(' '); inp.after(div); shown = true;
  }
  if (!shown) toast(errText(e), 'danger');
}

async function submit(form, fn) {
  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    const btn = form.querySelector('button:not([type=button]):not(.btn-close)'); if (btn) btn.disabled = true;
    try { await fn(Object.fromEntries(new FormData(form))); }
    catch (e) { if (e.status === 401) return go('/login'); fieldErrors(form, e); }
    if (btn) btn.disabled = false;
  });
}

const loading = () => { cleanupModals(); return app.innerHTML = '<div class="spinner-wrap"><div class="spinner-border text-success"></div><div class="mt-2">Загрузка…</div></div>'; };

const empty = (t, s = '') => `<div class="panel p-5 text-center"><h3 class="h5">${t}</h3><p class="text-secondary mb-0">${s}</p></div>`;

const fmtScore = n => String(Math.round(Number(n) * 10) / 10).replace('.', ',');  // 3.5 -> «3,5»

const starsHtml = n => { const r = Math.round(Number(n) * 2) / 2; return `<span class="stars" role="img" aria-label="Оценка ${fmtScore(n)} из 5">${[1, 2, 3, 4, 5].map(i => `<span class="st" style="--f:${r >= i ? 100 : r >= i - 0.5 ? 50 : 0}%">★</span>`).join('')}</span>`; };

const stars = n => n ? `${starsHtml(n)} <small class="text-secondary">${fmtScore(n)}</small>` : '<small class="text-secondary">Нет оценок</small>';

const starInput = (name, value) => `<div class="star-input" data-star><input type="hidden" name="${name}" value="${value || ''}"><span class="stars">${[1, 2, 3, 4, 5].map(i => `<span class="st-slot"><span class="st" style="--f:0%">★</span><button type="button" class="half l" data-v="${i - 0.5}" aria-label="${fmtScore(i - 0.5)} из 5"></button><button type="button" class="half r" data-v="${i}" aria-label="${i} из 5"></button></span>`).join('')}</span><span class="small text-secondary ms-2" data-val></span></div>`;

function initStarInput(root) {
  root.querySelectorAll('[data-star]').forEach(w => {
    const inp = w.querySelector('input');
    const paint = v => { w.querySelectorAll('.st').forEach((el, i) => el.style.setProperty('--f', (v >= i + 1 ? 100 : v >= i + 0.5 ? 50 : 0) + '%')); w.querySelector('[data-val]').textContent = v ? fmtScore(v) + ' из 5' : 'выберите оценку'; };
    paint(+inp.value || 0);
    w.querySelectorAll('.half').forEach(b => { b.onclick = () => { inp.value = b.dataset.v; paint(+b.dataset.v); }; b.onmouseenter = () => paint(+b.dataset.v); b.onmouseleave = () => paint(+inp.value || 0); });
  });
}

const cover = b => b.cover ? `<img class="cover w-100" src="${esc(b.cover)}" alt="Обложка «${esc(b.title)}»" loading="lazy">` : `<div class="cover cover-ph w-100">${esc(b.title)}</div>`;

const go = p => location.hash = '#' + p;

const list = d => Array.isArray(d) ? {results: d, count: d.length} : d;

function pager(count, page, base) {
  const n = Math.ceil(count / PAGE); if (n < 2) return '';
  return `<nav class="mt-4"><ul class="pagination justify-content-center">${Array.from({length: n}, (_, i) =>
    `<li class="page-item ${i + 1 === page ? 'active' : ''}"><a class="page-link" href="#${base}${base.includes('?') ? '&' : '?'}page=${i + 1}">${i + 1}</a></li>`).join('')}</ul></nav>`;
}

const isMod = () => me && ['moderator', 'admin'].includes(me.role);

const isAdmin = () => me && me.role === 'admin';

function cleanupModals() {  // «залипший» фон, если окно закрылось одновременно с перерисовкой страницы
  setTimeout(() => { if (!document.querySelector('.modal.show')) { document.querySelectorAll('.modal-backdrop').forEach(e => e.remove()); document.body.classList.remove('modal-open'); document.body.style.removeProperty('padding-right'); } }, 450);
}

/* Окно подтверждения в стиле сайта. Возвращает null (отмена) или {value} (подтверждено; value — текст из поля, если оно есть). */
function confirmDialog({title = 'Подтвердите действие', text = '', ok = 'Подтвердить', danger = false, input = ''}) {
  return new Promise(resolve => {
    const el = $('#cm'), m = bootstrap.Modal.getOrCreateInstance(el); let done = false;
    $('#cm-title').textContent = title;
    $('#cm-body').innerHTML = `<p class="mb-0">${esc(text)}</p>${input ? `<label class="form-label mt-3" for="cm-input">${esc(input)}</label><textarea class="form-control" id="cm-input" rows="2" maxlength="300"></textarea>` : ''}`;
    const okb = $('#cm-ok'); okb.textContent = ok; okb.className = 'btn ' + (danger ? 'btn-danger' : 'btn-pine');
    const finish = v => { if (!done) { done = true; resolve(v); } };
    okb.onclick = () => { finish({value: input ? $('#cm-input').value : ''}); m.hide(); };
    el.addEventListener('hidden.bs.modal', () => finish(null), {once: true});
    m.show();
  });
}

function toggleTheme() {
  const t = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', t); document.documentElement.setAttribute('data-bs-theme', t);
  localStorage.setItem('bc_theme', t); renderNav();
}

/* Отслеживание аренды: предупреждения о просроченных и скоро истекающих сроках (получателю и владельцу) */
function renderAlerts() {
  const box = $('#alerts'); if (!box) return;
  if (!me || !alertState.count) { box.innerHTML = ''; return; }
  const items = alertState.results.slice(0, 4).map(a => {
    const t = esc(a.book_title), who = esc(a.other), n = Math.abs(a.days_left);
    const tel = a.other_phone ? ` Телефон: <a href="tel:${esc(a.other_phone)}">${esc(a.other_phone)}</a>.` : '';
    const when = a.days_left === 0 ? 'сегодня' : `через ${n} дн.`;
    if (a.overdue) return a.role === 'borrower'
      ? `<div class="alert alert-danger mb-2"><strong>Просрочен возврат «${t}»</strong> — верните книгу владельцу ${who}, просрочка ${n} дн.${tel}</div>`
      : `<div class="alert alert-danger mb-2"><strong>«${t}» не возвращена вовремя</strong> — ${who} задерживает книгу уже ${n} дн.${tel}</div>`;
    return a.role === 'borrower'
      ? `<div class="alert alert-warning mb-2">Срок возврата «${t}» — ${when}. Верните книгу владельцу ${who}.${tel}</div>`
      : `<div class="alert alert-warning mb-2">${who} должен вернуть «${t}» ${when}.${tel}</div>`;
  }).join('');
  const more = alertState.count > 4 ? ` (и ещё ${alertState.count - 4})` : '';
  box.innerHTML = items + `<div class="small mb-2"><a href="#/loans?box=active">Все книги на руках${more}</a></div>`;
}

async function refreshAlerts(force = false) {
  if (!me) { alertState = {count: 0, overdue: 0, results: []}; unread = 0; return renderAlerts(); }
  if (!force && Date.now() - alertsAt < 30000) return;  // опрос сервера не чаще раза в 30 секунд
  alertsAt = Date.now();
  try { const [a, n] = await Promise.all([api('/alerts/'), api('/notifications/unread-count/')]); alertState = a; unread = n.count; } catch { return; }
  renderAlerts(); renderNav();
}

/* ===================== ШАПКА ===================== */
const BELL = '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2zm.995-14.901a1 1 0 1 0-1.99 0A5.002 5.002 0 0 0 3 6c0 1.098-.5 6-2 7h14c-1.5-1-2-5.902-2-7 0-2.42-1.72-4.44-4.005-4.901z"/></svg>';
function renderNav() {
  const links = [['/', 'Каталог']];
  if (me) links.push(['/shelf', 'Моя полка'], ['/loans', 'Обмены'], ['/meetings', 'Встречи'], ['/reading', 'Моё чтение'], ['/submit', 'Предложить книгу']);
  if (isMod()) links.push(['/moderation', 'Модерация'], ['/stats', 'Аналитика']);
  const cur = location.hash.slice(1) || '/';
  const badge = h => h !== '/loans' ? '' : alertState.overdue ? ` <span class="badge text-bg-danger">${alertState.overdue}</span>` : alertState.count ? ' <span class="badge text-bg-warning">!</span>' : '';
  $('#menu').innerHTML = links.map(([h, t]) => `<li class="nav-item"><a class="nav-link ${cur.split('?')[0] === h ? 'active' : ''}" href="#${h}">${t}${badge(h)}</a></li>`).join('');
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  $('#auth-box').innerHTML = `<button class="btn btn-sm btn-outline-light" id="theme-btn" aria-label="Переключить тему" title="${dark ? 'Светлая тема' : 'Тёмная тема'}">${dark ? '☀' : '☾'}</button>` + (me
    ? `<a class="btn btn-sm btn-outline-light" href="#/notifications" aria-label="Уведомления: ${unread}" title="Уведомления">${BELL}${unread ? ` <span class="badge text-bg-danger">${unread > 99 ? '99+' : unread}</span>` : ''}</a><a class="btn btn-sm btn-outline-light" href="#/profile">${esc(me.username)}</a><button class="btn btn-sm btn-pine" id="logout">Выйти</button>`
    : `<a class="btn btn-sm btn-outline-light" href="#/login">Войти</a><a class="btn btn-sm btn-pine" href="#/register">Регистрация</a>`);
  $('#theme-btn').onclick = toggleTheme;
  $('#logout')?.addEventListener('click', async () => {
    if (!await confirmDialog({title: 'Выйти из аккаунта?', text: 'Чтобы вернуться, нужно будет войти снова.', ok: 'Выйти'})) return;
    try { await api('/auth/logout/', {method: 'POST'}); } catch {}
    localStorage.removeItem('bc_token'); me = null; alertState = {count: 0, overdue: 0, results: []}; unread = 0; renderAlerts();
    go('/'); renderNav(); toast('Вы вышли из аккаунта');
  });
}

const fmtDt = s => new Date(s).toLocaleString('ru-RU', {dateStyle: 'long', timeStyle: 'short'});
