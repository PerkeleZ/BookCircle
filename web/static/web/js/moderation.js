/* BookCircle · модерация */
async function pModeration(q) {
  const tab = q.get('tab') || 'books', page = +q.get('page') || 1; loading();
  const tabs = [['books', 'Новые книги'], ['edits', 'Правки'], ['reviews', 'Рецензии']];
  const url = {books: '/moderation/books/', edits: '/moderation/edits/', reviews: '/reviews/?moderation=1'}[tab];
  const d = list(await api(`${url}${url.includes('?') ? '&' : '?'}page=${page}&page_size=${PAGE}`));
  const btns = (kind, id) => `<div class="flex gap-2"><button class="btn btn-sm btn-pine" data-${kind}="approve" data-id="${id}">Одобрить</button><button class="btn btn-sm btn-outline-danger" data-${kind}="reject" data-id="${id}">Отклонить</button></div>`;
  const FN = {title: 'Название', author: 'Автор', genre: 'Жанр', description: 'Описание', cover: 'Обложка'};
  const body = {
    books: () => d.results.length ? d.results.map(b => `<div class="panel p-3 mb-2 flex flex-wrap items-start justify-between gap-2"><div style="max-width:60ch">
        <div class="fw-bold">${esc(b.title)} <span class="text-secondary fw-normal">— ${esc(b.author)}</span></div><div class="small text-secondary">${esc(b.genre)} · предложил(а): ${esc(b.created_by || '—')}</div>
        <div class="mt-1">${esc(b.description) || '<span class="text-secondary">Описание не указано</span>'}</div>${b.cover ? `<div class="small mt-1"><a href="${esc(b.cover)}" target="_blank" rel="noopener">Обложка</a></div>` : ''}</div>${btns('mb', b.id)}</div>`).join('')
      : empty('Очередь пуста', 'Новых книг на модерации нет.'),
    edits: () => d.results.length ? d.results.map(e => `<div class="panel p-3 mb-2 flex flex-wrap items-start justify-between gap-2"><div style="max-width:70ch">
        <div class="fw-bold"><a class="text-reset" href="#/book/${e.book_id}">${esc(e.book_title)}</a> <span class="text-secondary fw-normal">· правка от ${esc(e.proposed_by || '—')}</span></div>
        ${Object.keys(FN).filter(f => (e[f] || '') !== (e.current[f] || '')).map(f => `<div class="small mt-1"><strong>${FN[f]}:</strong> <span class="text-decoration-line-through text-secondary">${esc(e.current[f]) || '—'}</span> → ${esc(e[f]) || '—'}</div>`).join('')}</div>${btns('me', e.id)}</div>`).join('')
      : empty('Правок на проверке нет'),
    reviews: () => d.results.length ? d.results.map(r => `<div class="panel p-3 mb-2 flex flex-wrap items-center justify-between gap-2">
        <div><strong>${esc(r.user)}</strong> о «${esc(r.book_title)}» ${starsHtml(r.score)} <small class="text-secondary">${fmtScore(r.score)}</small><div class="${r.is_hidden ? 'text-decoration-line-through text-secondary' : ''}">${esc(r.text)}</div></div>
        <div class="flex gap-2"><button class="btn btn-sm ${r.is_hidden ? 'btn-outline-success' : 'btn-outline-secondary'}" data-h="${r.id}" data-v="${r.is_hidden}">${r.is_hidden ? 'Показать' : 'Скрыть'}</button>
        ${isAdmin() ? `<button class="btn btn-sm btn-outline-danger" data-rd="${r.id}">Удалить</button>` : ''}</div></div>`).join('') : empty('Рецензий пока нет'),
  }[tab]();
  app.innerHTML = `<div class="flex flex-wrap items-center justify-between gap-2 mb-3"><h1 class="h2 mb-0">Модерация</h1><a class="btn btn-pine" href="#/submit">Добавить книгу</a></div>
  <ul class="nav nav-pills mb-3">${tabs.map(([k, t]) => `<li class="nav-item"><a class="nav-link ${tab === k ? 'active bg-success' : 'text-success'}" href="#/moderation?tab=${k}">${t}</a></li>`).join('')}</ul>
  ${body}${pager(d.count, page, `/moderation?tab=${tab}`)}`;
  const decide = (sel, base, ok1, no1, askTitle) => app.querySelectorAll(sel).forEach(b => b.onclick = async () => {
    const act = b.dataset[sel.slice(6, 8)]; let reason = '';
    if (act === 'reject') { const r = await confirmDialog({title: askTitle, text: 'Укажите причину — автор увидит её на странице «Предложить книгу».', ok: 'Отклонить', danger: true, input: 'Причина (необязательно)'}); if (!r) return; reason = r.value; }
    try { await api(`${base}/${b.dataset.id}/${act}/`, {method: 'POST', body: {reason}}); toast(act === 'approve' ? ok1 : no1); pModeration(q); } catch (e) { toast(errText(e), 'danger'); } });
  decide('[data-mb]', '/moderation/books', 'Книга опубликована', 'Книга отклонена', 'Отклонить книгу?');
  decide('[data-me]', '/moderation/edits', 'Правка применена', 'Правка отклонена', 'Отклонить правку?');
  app.querySelectorAll('[data-h]').forEach(b => b.onclick = async () => {
    try { await api(`/reviews/${b.dataset.h}/`, {method: 'PATCH', body: {is_hidden: b.dataset.v !== 'true'}}); pModeration(q); } catch (e) { toast(errText(e), 'danger'); } });
  app.querySelectorAll('[data-rd]').forEach(b => b.onclick = async () => {
    if (!await confirmDialog({title: 'Удалить рецензию?', text: 'Рецензия будет удалена безвозвратно, рейтинг книги пересчитается.', ok: 'Удалить', danger: true})) return;
    try { await api(`/reviews/${b.dataset.rd}/`, {method: 'DELETE'}); toast('Рецензия удалена'); pModeration(q); } catch (e) { toast(errText(e), 'danger'); } });
}
