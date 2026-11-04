/* BookCircle · моя полка и обмены */
async function pShelf(q) {
  const page = +q.get('page') || 1; loading();
  const [d, bk] = await Promise.all([api(`/copies/?mine=1&page=${page}&page_size=${PAGE}`).then(list), api('/books/options/')]);
  const books = bk.results;  // все одобренные книги каталога, без пагинации
  app.innerHTML = `<h1 class="h2">Моя полка</h1>
  <form id="add" class="panel p-3 mb-4" novalidate><h2 class="h6">Добавить экземпляр</h2><div class="row g-2">
    <div class="col-md-5"><input class="form-control mb-2" id="bk-filter" placeholder="Найти книгу по названию или автору" aria-label="Поиск книги"><select class="form-select" id="bk-sel" name="book_id"></select></div>
    <div class="col-md-3"><select class="form-select" name="condition">${Object.entries(COND).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></div>
    <div class="col-md-3"><input class="form-control" name="pickup_place" placeholder="Место передачи"></div>
    <div class="col-md-1"><button class="btn btn-pine w-100">+</button></div></div>
    <div class="form-text mt-2">В списке все книги каталога (${books.length}). Нет нужной? <a href="#/submit">Предложите её</a> — после проверки модератором она появится здесь.</div></form>
  ${d.results.length ? `<div class="panel"><ul class="list-group list-group-flush">${d.results.map(c => `
    <li class="list-group-item flex flex-wrap items-center justify-between gap-2">
      <div><a href="#/book/${c.book_id}" class="fw-bold text-reset">${esc(c.book_title)}</a><div class="small text-secondary">${esc(COND[c.condition] || c.condition)} · ${esc(c.pickup_place)}</div></div>
      <div class="flex gap-2 items-center"><span class="badge ${c.is_active ? 'text-bg-success' : 'text-bg-secondary'}">${c.is_active ? 'Доступен' : 'Скрыт'}</span>
      <button class="btn btn-sm btn-outline-secondary" data-tg="${c.id}" data-on="${c.is_active}">${c.is_active ? 'Скрыть' : 'Показать'}</button></div></li>`).join('')}</ul></div>` : empty('Полка пуста', 'Добавьте первую книгу — другие участники смогут её запросить.')}
  ${pager(d.count, page, '/shelf')}`;
  const fill = (term = '') => {
    const t = term.trim().toLowerCase(), sel = $('#bk-sel'), cur = sel.value;
    const items = books.filter(b => !t || (b.title + ' ' + b.author).toLowerCase().includes(t));
    sel.innerHTML = `<option value="">Выберите книгу (${items.length} из ${books.length})</option>` + items.map(b => `<option value="${b.id}" ${String(b.id) === cur ? 'selected' : ''}>${esc(b.title)} — ${esc(b.author)}</option>`).join('');
  };
  fill(); $('#bk-filter').addEventListener('input', e => fill(e.target.value));
  submit($('#add'), async f => { await api('/copies/', {method: 'POST', body: {...f, book_id: +f.book_id || null}}); toast('Экземпляр добавлен'); pShelf(q); });
  app.querySelectorAll('[data-tg]').forEach(b => b.onclick = async () => {
    try { await api(`/copies/${b.dataset.tg}/`, {method: 'PATCH', body: {is_active: b.dataset.on !== 'true'}}); pShelf(q); }
    catch (e) { toast(errText(e), 'danger'); } });
}

async function pLoans(q) {
  const box = q.get('box') || 'incoming', page = +q.get('page') || 1; loading();
  const d = list(await api(`/loans/?box=${box}&page=${page}&page_size=${PAGE}`));
  const role = l => me.username === l.owner ? 'owner' : 'borrower';
  const tel = p => p ? `<a href="tel:${esc(p)}">${esc(p)}</a>` : '<span class="text-secondary">не указан</span>';
  const acts = l => {
    const a = [];
    if (role(l) === 'owner') {
      if (l.status === 'pending') a.push(['accept', 'Принять', 'pine'], ['reject', 'Отклонить', 'outline-secondary']);
      if (l.status === 'accepted') a.push(['hand-over', 'Отметить передачу', 'pine'], ['cancel', 'Отменить', 'outline-secondary']);
      if (l.status === 'handed_over') a.push(['return', 'Отметить возврат', 'pine']);
    } else if (['pending', 'accepted'].includes(l.status)) a.push(['cancel', 'Отменить', 'outline-secondary']);
    return a.map(([k, t, c]) => `<button class="btn btn-sm btn-${c}" data-act="${k}" data-id="${l.id}" data-book="${esc(l.book_title)}">${t}</button>`).join('');
  };
  const due = l => l.status !== 'handed_over' ? '' : l.days_left < 0 ? `<span class="badge text-bg-danger">Просрочено на ${-l.days_left} дн.</span>`
    : l.days_left <= 2 ? `<span class="badge text-bg-warning">Вернуть ${l.days_left === 0 ? 'сегодня' : 'через ' + l.days_left + ' дн.'}</span>` : `<span class="badge bg-body-secondary text-body border">Осталось ${l.days_left} дн.</span>`;
  const tabs = [['incoming', 'Входящие'], ['outgoing', 'Исходящие'], ['active', 'На руках']];
  app.innerHTML = `<h1 class="h2">Обмены</h1>
  <ul class="nav nav-pills mb-3">${tabs.map(([k, t]) => `<li class="nav-item"><a class="nav-link ${box === k ? 'active bg-success' : 'text-success'}" href="#/loans?box=${k}">${t}</a></li>`).join('')}</ul>
  ${d.results.length ? d.results.map(l => {
    const [t, c] = LOAN[l.status] || [l.status, 'secondary'], r = role(l);
    return `<div class="panel p-3 mb-2 flex flex-wrap items-center justify-between gap-2">
      <div><div class="fw-bold">${esc(l.book_title)}</div>
      <div class="small text-secondary">${r === 'owner' ? 'Получатель: ' + esc(l.borrower) : 'Владелец: ' + esc(l.owner)} · вернуть до ${esc(l.requested_return_date || '—')}</div>
      <div class="small">${r === 'owner' ? 'Телефон получателя: ' + tel(l.borrower_phone) : (l.owner_phone ? 'Телефон владельца: ' + tel(l.owner_phone) : 'Телефон владельца появится после принятия запроса, если он указан в профиле.')}</div>
      <span class="badge text-bg-${c}">${t}</span> ${due(l)}</div>
      <div class="flex gap-2">${acts(l)}</div></div>`; }).join('')
    : empty(box === 'incoming' ? 'Входящих запросов нет' : box === 'outgoing' ? 'Вы ещё ничего не запрашивали' : 'Сейчас нет книг на руках', box === 'active' ? 'Здесь отображаются книги, которые переданы и ещё не возвращены, со сроком возврата.' : 'Загляните в каталог и выберите книгу.')}
  ${pager(d.count, page, `/loans?box=${box}`)}`;
  app.querySelectorAll('[data-act]').forEach(b => b.onclick = async () => {
    const ask = {reject: ['Отклонить запрос?', 'Заёмщик увидит, что запрос отклонён.', 'Отклонить'], cancel: ['Отменить обмен?', 'Запрос на «' + b.dataset.book + '» будет отменён.', 'Отменить обмен']}[b.dataset.act];
    if (ask && !await confirmDialog({title: ask[0], text: ask[1], ok: ask[2], danger: true})) return;
    b.disabled = true;
    try { await api(`/loans/${b.dataset.id}/${b.dataset.act}/`, {method: 'POST'}); toast('Готово'); pLoans(q); refreshAlerts(true); }
    catch (e) { toast(errText(e), 'danger'); b.disabled = false; } });
}
