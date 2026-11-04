/* BookCircle · маршрутизатор и запуск (подключается последним) */
const errPage = (c, t, s) => app.innerHTML = `<div class="text-center py-5"><div class="display-1 brand">${c}</div><h1 class="h4">${t}</h1><p class="text-secondary">${s}</p><a class="btn btn-pine" href="#/">В каталог</a></div>`;

/* ===================== РОУТЕР ===================== */
const needAuth = ['/shelf', '/loans', '/meetings', '/reading', '/submit', '/notifications', '/profile', '/moderation', '/stats'];

async function route() {
  rid++;
  const [path, qs] = (location.hash.slice(1) || '/').split('?'); const q = new URLSearchParams(qs || '');
  renderNav();
  if (me) refreshAlerts();
  if (needAuth.includes(path) && !me) return go('/login');
  if ((path === '/moderation' || path === '/stats') && !isMod()) return errPage(403, 'Нет доступа', 'Этот раздел доступен только модераторам.');
  try {
    let m;
    if (path === '/') await pCatalog(q);
    else if ((m = path.match(/^\/book\/(\d+)$/))) await pBook(m[1]);
    else if (path === '/shelf') await pShelf(q);
    else if (path === '/loans') await pLoans(q);
    else if (path === '/meetings') await pMeetings(q);
    else if (path === '/submit') await pSubmit(q);
    else if (path === '/reading') await pReading();
    else if (path === '/moderation') await pModeration(q);
    else if (path === '/login' || path === '/register') pAuth(path.slice(1));
    else if (path === '/forgot') pForgot();
    else if (path === '/reset') pReset(q);
    else if (path === '/notifications') await pNotifications(q);
    else if (path === '/stats') await pStats();
    else if (path === '/profile') await pProfile();
    else errPage(404, 'Страница не найдена', 'Проверьте адрес или вернитесь в каталог.');
  } catch (e) {
    if (e.status === 401) { localStorage.removeItem('bc_token'); me = null; return go('/login'); }
    if (e.status === 403) return errPage(403, 'Нет доступа', errText(e));
    if (e.status === 404) return errPage(404, 'Не найдено', errText(e));
    app.innerHTML = `<div class="alert alert-danger">${esc(errText(e))}</div>`;
  }
}

window.addEventListener('hashchange', route);

(async () => {
  if (localStorage.getItem('bc_token')) { try { me = await api('/auth/me/'); } catch { localStorage.removeItem('bc_token'); } }
  route();
})();
