/* BookCircle · каталог, страница книги, предложение книг */
/* ===================== СТРАНИЦЫ ===================== */
const bookCard = (b, reason) => `
    <a href="#/book/${b.id}" class="card-book p-2 text-decoration-none text-reset block">
      ${cover(b)}<div class="p-2"><div class="fw-bold">${esc(b.title)}</div><div class="small text-secondary">${esc(b.author)} · ${esc(b.genre)}</div>
      <div class="mt-1">${stars(b.avg_rating)}</div>
      <span class="badge ${b.available_copies ? 'text-bg-success' : 'text-bg-secondary'} mt-1">${b.available_copies ? 'Доступно: ' + b.available_copies : 'Нет свободных'}</span>
      ${reason ? `<div class="small text-success mt-1">${esc(reason)}</div>` : ''}</div></a>`;

async function pCatalog(q) {
  const page = +q.get('page') || 1, s = q.get('search') || '', g = q.get('genre') || '';
  loading();
  const plain = page === 1 && !s && !g;
  const [d, gen, rec, stat] = await Promise.all([
    api(`/books/?search=${encodeURIComponent(s)}&genre=${encodeURIComponent(g)}&page=${page}&page_size=${PAGE}`).then(list),
    api('/genres/'),
    me && plain ? api('/recommendations/').catch(() => null) : null,
    !me && plain ? api('/stats/public/').catch(() => null) : null,
  ]);
  const genres = ['', ...gen.results];
  const hero = stat ? `<section class="hero mb-4"><h1 class="display-6 brand mb-2">Общая библиотека вашего сообщества</h1>
    <p class="lead mb-3" style="max-width:55ch">Обменивайтесь книгами с соседями и коллегами, обсуждайте прочитанное на встречах и ставьте себе цели чтения.</p>
    <div class="flex flex-wrap gap-2 mb-3"><a class="btn btn-pine btn-lg" href="#/register">Присоединиться</a><a class="btn btn-outline-secondary btn-lg" href="#/login">Войти</a></div>
    <div class="hero-stats mb-3"><strong>${stat.books}</strong> книг · <strong>${stat.members}</strong> участников · <strong>${stat.exchanges}</strong> обменов · <strong>${stat.reviews}</strong> отзывов</div>
    <div class="grid md:grid-cols-3 gap-3 hero-points"><div><strong>Обмен без хлопот</strong><br><span class="small text-secondary">Запрос, договорённость о передаче, напоминания о сроках возврата.</span></div>
    <div><strong>Книжные встречи</strong><br><span class="small text-secondary">Назначайте встречи по книге, записывайтесь и обсуждайте вместе.</span></div>
    <div><strong>Цели и рекомендации</strong><br><span class="small text-secondary">Годовые и месячные цели чтения, подборки по любимым жанрам.</span></div></div></section>` : '';
  app.innerHTML = `${hero}
  <h1 class="h2 mb-1">Каталог книг</h1><p class="text-secondary">Найдите книгу и запросите её у соседа по клубу.</p>
  <form class="flex flex-wrap gap-2 mb-4" id="f">
    <input class="form-control" style="max-width:340px" name="search" placeholder="Название или автор" value="${esc(s)}" aria-label="Поиск">
    <select class="form-select" style="max-width:200px" name="genre" aria-label="Жанр">${genres.map(x => `<option value="${esc(x)}" ${x === g ? 'selected' : ''}>${esc(x) || 'Все жанры'}</option>`).join('')}</select>
    <button class="btn btn-pine">Найти</button></form>
  ${rec && rec.results.length ? `<div class="mb-4"><h2 class="h5 mb-1">Рекомендуем вам</h2><p class="small text-secondary">${rec.genres.length ? 'По вашим жанрам: ' + rec.genres.map(x => esc(x.genre)).join(', ') + '.' : 'Пока мало данных о ваших вкусах — вот что популярно в клубе. Отмечайте прочитанное и ставьте оценки, и подборка станет точнее.'}</p><div class="grid grid-cols-2 md:grid-cols-4 gap-4">${rec.results.slice(0, 4).map(b => bookCard(b, b.reason)).join('')}</div></div><h2 class="h5">Все книги</h2>` : ''}
  ${d.results.length ? `<div class="grid grid-cols-2 md:grid-cols-4 gap-4">${d.results.map(b => bookCard(b)).join('')}</div>`
    : (s || g ? empty('Ничего не найдено', 'Измените запрос или сбросьте жанр.') : empty('Каталог пока пуст', 'Предложите первую книгу — после проверки модератором она появится здесь.'))}
  ${pager(d.count, page, `/?search=${encodeURIComponent(s)}&genre=${encodeURIComponent(g)}`)}`;
  $('#f').addEventListener('submit', e => { e.preventDefault(); const f = new FormData(e.target); go(`/?search=${encodeURIComponent(f.get('search'))}&genre=${encodeURIComponent(f.get('genre'))}`); });
}

async function pBook(id) {
  loading();
  // каждое приложение отвечает за свои данные книги: каталог, экземпляры, отзывы, чтение, встречи
  const [b, cp, rv, rd, mtd, gen] = await Promise.all([
    api(`/books/${id}/`),
    api(`/books/${id}/copies/`).catch(() => ({results: []})),
    api(`/books/${id}/reviews/`).catch(() => ({results: [], my_review: null})),
    me ? api(`/reading/${id}/`).catch(() => ({status: null})) : {status: null},
    me ? api(`/meetings/?book=${id}&page_size=5`).catch(() => null) : null,
    me ? api('/genres/').catch(() => ({results: []})) : {results: []},
  ]);
  const copies = cp.results, reviews = rv.results, mts = mtd?.results || [];
  b.my_review = rv.my_review; b.my_reading = rd.status;
  const today = new Date().toISOString().slice(0, 10);
  const open = b.is_mine && ['pending', 'rejected'].includes(b.status), direct = me && (isMod() || open);
  const ST = {pending: ['warning', 'На модерации'], rejected: ['danger', 'Отклонена'], hidden: ['secondary', 'Скрыта']};
  const banner = {pending: ['warning', 'Книга на модерации: пока она видна только вам и модераторам.'],
    rejected: ['danger', 'Книга отклонена модератором' + (b.reject_reason ? ': ' + b.reject_reason : '') + '. Исправьте данные — после сохранения она снова уйдёт на модерацию.'],
    hidden: ['secondary', 'Книга скрыта и не показывается в каталоге.']}[b.status];
  const actions = me ? `<div class="flex flex-wrap gap-2 mt-3">
    ${direct ? '<button class="btn btn-sm btn-outline-secondary" data-bk="edit">Редактировать</button>' : (b.status === 'approved' ? '<button class="btn btn-sm btn-outline-secondary" data-bk="edit">Предложить правку</button>' : '')}
    ${isMod() && b.status === 'approved' ? '<button class="btn btn-sm btn-outline-secondary" data-bk="hide">Скрыть из каталога</button>' : ''}
    ${isMod() && b.status === 'hidden' ? '<button class="btn btn-sm btn-outline-success" data-bk="unhide">Вернуть в каталог</button>' : ''}
    ${isAdmin() || open ? '<button class="btn btn-sm btn-outline-danger" data-bk="delete">Удалить книгу</button>' : ''}</div>` : '';
  app.innerHTML = `
  ${banner ? `<div class="alert alert-${banner[0]}">${esc(banner[1])}</div>` : ''}
  <div class="grid md:grid-cols-[220px_1fr] gap-6">
    <div>${cover(b)}</div>
    <div><h1 class="h2 mb-0">${esc(b.title)} ${ST[b.status] ? `<span class="badge text-bg-${ST[b.status][0]} fs-6 align-middle">${ST[b.status][1]}</span>` : ''}</h1>
      <div class="text-secondary mb-2">${esc(b.author)} · ${esc(b.genre)}</div>
      <div class="mb-3">${stars(b.avg_rating)} <span class="badge bg-body-secondary text-body border ms-2">Прочитали в этом месяце: ${b.read_this_month ?? 0}</span></div>
      <p style="max-width:65ch">${esc(b.description)}</p>
      ${me && b.status === 'approved' ? `<div class="flex items-center gap-2"><label class="small text-secondary" for="rs">Мой статус:</label>
        <select id="rs" class="form-select form-select-sm" style="width:auto"><option value="">—</option>${Object.entries(READ).map(([k, v]) => `<option value="${k}" ${b.my_reading === k ? 'selected' : ''}>${v}</option>`).join('')}</select></div>` : ''}
      ${actions}
    </div></div>
  <h2 class="h4 mt-5">Экземпляры</h2>
  ${copies.length ? `<div class="panel"><ul class="list-group list-group-flush">${copies.map(c => `
    <li class="list-group-item flex flex-wrap items-center justify-between gap-2">
      <div><strong>${esc(c.owner)}</strong> · ${esc(COND[c.condition] || c.condition)}<div class="small text-secondary">Место передачи: ${esc(c.pickup_place)}</div></div>
      ${c.is_available ? (me && me.username !== c.owner ? `<button class="btn btn-sm btn-pine" data-req="${c.id}">Запросить</button>` : '<span class="badge text-bg-success">Доступно</span>') : '<span class="badge text-bg-secondary">Занято</span>'}
    </li>`).join('')}</ul></div>` : empty('Пока нет экземпляров', 'Добавьте свой на странице «Моя полка».')}
  ${mts.length ? `<h2 class="h4 mt-5">Встречи по этой книге</h2><div class="panel"><ul class="list-group list-group-flush">${mts.map(m => `<li class="list-group-item flex flex-wrap items-center justify-between gap-2"><div><strong>${esc(m.title)}</strong><div class="small text-secondary">${esc(fmtDt(m.starts_at))} · ${esc(m.place)}</div></div><a class="btn btn-sm btn-outline-success" href="#/meetings">Подробнее</a></li>`).join('')}</ul></div>` : ''}
  <h2 class="h4 mt-5">Отзывы</h2>
  ${reviews.length ? reviews.map(r => `<div class="panel p-3 mb-2 ${r.is_mine ? 'border-success' : ''}"><div class="flex justify-between items-center gap-2"><strong>${esc(r.user)}${r.is_mine ? ' <span class="badge text-bg-success">Ваш отзыв</span>' : ''}</strong>
      <span class="flex items-center gap-2">${starsHtml(r.score)}<small class="text-secondary">${fmtScore(r.score)}</small>
      ${r.is_mine ? '<button class="btn btn-sm btn-outline-secondary" data-edit-review>Изменить</button><button class="btn btn-sm btn-outline-danger" data-del-review="mine" data-own="1">Удалить</button>' : (isAdmin() ? `<button class="btn btn-sm btn-outline-danger" data-del-review="${r.id}" data-own="0">Удалить</button>` : '')}</span></div>
      <div>${esc(r.text)}</div></div>`).join('') : empty('Отзывов пока нет')}
  ${b.my_review?.is_hidden ? '<div class="alert alert-warning">Ваш отзыв скрыт модератором. Вы можете его изменить или удалить, но он останется скрытым, пока модератор его не вернёт.</div>' : ''}
  ${me && b.status === 'approved' ? `<form id="rv" class="panel p-3 mt-3" novalidate><h3 class="h6">${b.my_review ? 'Редактирование вашего отзыва' : 'Оставить отзыв'}</h3>
    <div class="mb-2">${starInput('score', b.my_review?.score)}</div>
    <textarea class="form-control" name="text" rows="2" placeholder="Что вы думаете о книге?">${esc(b.my_review?.text || '')}</textarea>
    <button class="btn btn-pine mt-2">${b.my_review ? 'Сохранить изменения' : 'Опубликовать отзыв'}</button>
    ${b.my_review ? '<button type="button" class="btn btn-outline-danger mt-2 ms-2" data-del-review="mine" data-own="1">Удалить отзыв</button>' : ''}</form>` : (!me ? '<p class="mt-3"><a href="#/login">Войдите</a>, чтобы запросить книгу или оставить отзыв.</p>' : '')}
  <div class="modal fade" id="rq"><div class="modal-dialog"><form class="modal-content" id="rqf" novalidate><div class="modal-header"><h5 class="modal-title">Запрос книги</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body"><label class="form-label">Когда вернёте?</label><input type="date" class="form-control mb-3" name="requested_return_date" min="${today}">
      <label class="form-label">Ваш телефон для связи</label><input type="tel" class="form-control" name="phone" value="${esc(me?.phone || '')}" placeholder="+996 555 123 456">
      <div class="form-text">Номер увидит только владелец книги — чтобы договориться о передаче.</div></div>
    <div class="modal-footer"><button class="btn btn-pine">Отправить запрос</button></div></form></div></div>
  ${me ? `<div class="modal fade" id="be"><div class="modal-dialog"><form class="modal-content" id="bef" novalidate><div class="modal-header"><h5 class="modal-title">${direct ? 'Редактировать книгу' : 'Предложить правку'}</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body">${direct ? '' : '<p class="small text-secondary">Правка вступит в силу после проверки модератором.</p>'}
      <label class="form-label">Название</label><input class="form-control mb-2" name="title" value="${esc(b.title)}">
      <label class="form-label">Автор</label><input class="form-control mb-2" name="author" value="${esc(b.author)}">
      <label class="form-label">Жанр</label><input class="form-control mb-2" name="genre" list="gl2" value="${esc(b.genre)}" autocomplete="off"><datalist id="gl2">${gen.results.map(x => `<option value="${esc(x)}">`).join('')}</datalist>
      <label class="form-label">URL обложки</label><input class="form-control mb-2" name="cover" value="${esc(b.cover)}">
      <label class="form-label">Описание</label><textarea class="form-control" name="description" rows="4">${esc(b.description)}</textarea></div>
    <div class="modal-footer"><button class="btn btn-pine">${direct ? 'Сохранить' : 'Отправить на проверку'}</button></div></form></div></div>` : ''}`;
  initStarInput(app);
  let copyId = null; const modal = bootstrap.Modal.getOrCreateInstance($('#rq')), em = $('#be') ? bootstrap.Modal.getOrCreateInstance($('#be')) : null;
  app.querySelectorAll('[data-req]').forEach(x => x.onclick = () => { copyId = x.dataset.req; modal.show(); });
  $('#rs')?.addEventListener('change', async e => { if (!e.target.value) return; try { await api(`/reading/${id}/`, {method: 'PUT', body: {status: e.target.value}}); toast('Статус сохранён'); } catch (er) { toast(errText(er), 'danger'); } });
  submit($('#rqf'), async d => { await api(`/copies/${copyId}/loans/`, {method: 'POST', body: d}); modal.hide(); toast('Запрос отправлен владельцу'); pBook(id); });
  app.querySelectorAll('[data-bk]').forEach(x => x.onclick = async () => {
    const act = x.dataset.bk;
    if (act === 'edit') return em.show();
    if (act === 'hide' || act === 'unhide') {
      try { await api(`/books/${id}/${act}/`, {method: 'POST'}); toast(act === 'hide' ? 'Книга скрыта из каталога' : 'Книга возвращена в каталог'); pBook(id); } catch (e) { toast(errText(e), 'danger'); }
      return;
    }
    if (!await confirmDialog({title: 'Удалить книгу?', danger: true, ok: 'Удалить',
      text: isAdmin() ? 'Будут удалены сама книга, её экземпляры, отзывы, отметки о чтении и история обменов. Это действие нельзя отменить.' : 'Предложенная вами книга будет удалена.'})) return;
    try { await api(`/books/${id}/`, {method: 'DELETE'}); toast('Книга удалена'); go('/'); } catch (e) { toast(errText(e), 'danger'); }
  });
  if ($('#bef')) submit($('#bef'), async f => {
    if (direct) { await api(`/books/${id}/`, {method: 'PATCH', body: f}); toast(open ? 'Сохранено. Книга отправлена на повторную проверку' : 'Книга обновлена'); }
    else { await api(`/books/${id}/edits/`, {method: 'POST', body: f}); toast('Правка отправлена на модерацию'); }
    em.hide(); pBook(id);
  });
  app.querySelectorAll('[data-edit-review]').forEach(x => x.onclick = () => { const f = $('#rv'); f.scrollIntoView({behavior: 'smooth', block: 'center'}); f.elements.text.focus(); f.classList.add('border-success'); });
  app.querySelectorAll('[data-del-review]').forEach(x => x.onclick = async () => {
    const own = x.dataset.own === '1';
    if (!await confirmDialog({title: own ? 'Удалить ваш отзыв?' : 'Удалить отзыв пользователя?', text: 'Отзыв будет удалён безвозвратно, рейтинг книги пересчитается.', ok: 'Удалить', danger: true})) return;
    try { await api(own ? `/books/${id}/review/` : `/reviews/${x.dataset.delReview}/`, {method: 'DELETE'}); toast('Отзыв удалён'); pBook(id); } catch (e) { toast(errText(e), 'danger'); }
  });
  if ($('#rv')) submit($('#rv'), async d => { await api(`/books/${id}/review/`, {method: 'PUT', body: {score: d.score ? +d.score : null, text: d.text}}); toast(b.my_review ? 'Отзыв обновлён' : 'Отзыв опубликован'); pBook(id); });
}

const BST = {pending: ['warning', 'На модерации'], approved: ['success', 'Опубликована'], rejected: ['danger', 'Отклонена'], hidden: ['secondary', 'Скрыта']};

async function pSubmit(q) {
  loading();
  const [gen, sub] = await Promise.all([api('/genres/'), api('/submissions/')]);
  app.innerHTML = `<h1 class="h2">Предложить книгу</h1>
  <p class="text-secondary">${isMod() ? 'Книги модераторов публикуются сразу.' : 'Новая книга появится в каталоге после проверки модератором. Исправить данные существующей книги можно на её странице — кнопка «Предложить правку».'}</p>
  <form id="sf" class="panel p-3 mb-4" novalidate><div class="row g-2">
    <div class="col-md-5"><input class="form-control" name="title" placeholder="Название"></div>
    <div class="col-md-4"><input class="form-control" name="author" placeholder="Автор"></div>
    <div class="col-md-3"><input class="form-control" name="genre" list="gl3" placeholder="Жанр" autocomplete="off"><datalist id="gl3">${gen.results.map(x => `<option value="${esc(x)}">`).join('')}</datalist></div>
    <div class="col-12"><input class="form-control" name="cover" placeholder="URL обложки (необязательно)"></div>
    <div class="col-12"><textarea class="form-control" name="description" rows="3" placeholder="Описание"></textarea></div></div>
    <button class="btn btn-pine mt-2">${isMod() ? 'Добавить книгу' : 'Отправить на модерацию'}</button></form>
  <h2 class="h5">Мои предложения</h2>
  ${sub.books.length ? sub.books.map(b => `<div class="panel p-3 mb-2 flex flex-wrap items-center justify-between gap-2"><div>
      <div class="fw-bold">${b.status === 'hidden' ? esc(b.title) : `<a class="text-reset" href="#/book/${b.id}">${esc(b.title)}</a>`} <span class="badge text-bg-${BST[b.status][0]}">${BST[b.status][1]}</span></div>
      <div class="small text-secondary">${esc(b.author)} · ${esc(b.genre)}</div>
      ${b.status === 'rejected' && b.reject_reason ? `<div class="small text-danger">Причина: ${esc(b.reject_reason)}</div>` : ''}</div>
      ${['pending', 'rejected'].includes(b.status) ? `<button class="btn btn-sm btn-outline-danger" data-del="${b.id}" data-t="${esc(b.title)}">Удалить</button>` : ''}</div>`).join('') : empty('Вы пока ничего не предлагали')}
  ${sub.edits.length ? `<h2 class="h5 mt-4">Мои правки</h2>${sub.edits.map(e => `<div class="panel p-3 mb-2"><div class="fw-bold"><a class="text-reset" href="#/book/${e.book_id}">${esc(e.book_title)}</a> <span class="badge text-bg-${BST[e.status][0]}">${BST[e.status][1]}</span></div>
      ${e.status === 'rejected' && e.reject_reason ? `<div class="small text-danger">Причина: ${esc(e.reject_reason)}</div>` : ''}</div>`).join('')}` : ''}`;
  submit($('#sf'), async f => {
    const r = await api('/books/', {method: 'POST', body: f});
    toast(r.status === 'approved' ? 'Книга добавлена в каталог' : 'Книга отправлена на модерацию'); pSubmit(q);
  });
  app.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => {
    if (!await confirmDialog({title: 'Удалить предложенную книгу?', text: `«${b.dataset.t}» будет удалена без возможности восстановления.`, ok: 'Удалить', danger: true})) return;
    try { await api(`/books/${b.dataset.del}/`, {method: 'DELETE'}); toast('Удалено'); pSubmit(q); } catch (e) { toast(errText(e), 'danger'); } });
}
