/* BookCircle · книжные встречи */
function meetingActions(m) {
  if (m.is_cancelled || m.is_past) return '';
  const b = (act, t, c) => `<button class="btn btn-sm btn-${c}" data-m="${act}" data-id="${m.id}">${t}</button>`;
  let h = '';
  if (m.is_organizer || isMod()) h += b('cancel', 'Отменить встречу', 'outline-danger');
  if (m.is_joined && !m.is_organizer) h += b('leave', 'Не пойду', 'outline-secondary');
  if (!m.is_joined && !m.is_full) h += b('join', 'Пойду', 'pine');
  return h;
}

async function pMeetings(q) {
  const when = q.get('when') || 'upcoming', page = +q.get('page') || 1; loading();
  const [d, books] = await Promise.all([api(`/meetings/?when=${when}&page=${page}&page_size=${PAGE}`).then(list), api('/books/options/')]);
  const tabs = [['upcoming', 'Предстоящие'], ['mine', 'Мои'], ['past', 'Прошедшие']];
  app.innerHTML = `<div class="flex flex-wrap items-center justify-between gap-2 mb-3"><h1 class="h2 mb-0">Книжные встречи</h1>
    <button class="btn btn-pine" data-bs-toggle="collapse" data-bs-target="#mf">Назначить встречу</button></div>
  <form id="mf" class="panel p-3 mb-4 collapse" novalidate><div class="row g-2">
    <div class="col-md-6"><input class="form-control" name="title" placeholder="Название встречи"></div>
    <div class="col-md-6"><select class="form-select" name="book_id"><option value="">Книга (необязательно)</option>${books.results.map(b => `<option value="${b.id}">${esc(b.title)} — ${esc(b.author)}</option>`).join('')}</select></div>
    <div class="col-md-4"><input class="form-control" type="datetime-local" name="starts_at" aria-label="Дата и время"></div>
    <div class="col-md-5"><input class="form-control" name="place" placeholder="Место"></div>
    <div class="col-md-3"><input class="form-control" type="number" min="1" name="capacity" placeholder="Мест (необязательно)"></div>
    <div class="col-12"><textarea class="form-control" name="description" rows="2" placeholder="О чём поговорим"></textarea></div></div>
    <button class="btn btn-pine mt-2">Создать встречу</button></form>
  <ul class="nav nav-pills mb-3">${tabs.map(([k, t]) => `<li class="nav-item"><a class="nav-link ${when === k ? 'active bg-success' : 'text-success'}" href="#/meetings?when=${k}">${t}</a></li>`).join('')}</ul>
  ${d.results.length ? d.results.map(m => `<div class="panel p-3 mb-2">
    <div class="flex flex-wrap items-start justify-between gap-2"><div>
      <div class="fw-bold">${esc(m.title)} ${m.is_cancelled ? '<span class="badge text-bg-danger">Отменена</span>' : ''}${m.is_organizer ? ' <span class="badge text-bg-info">Вы организатор</span>' : (m.is_joined ? ' <span class="badge text-bg-success">Вы участвуете</span>' : '')}${m.is_full && !m.is_joined && !m.is_past ? ' <span class="badge text-bg-secondary">Мест нет</span>' : ''}</div>
      <div class="small text-secondary">${esc(fmtDt(m.starts_at))} · ${esc(m.place)}${m.book_id ? ` · <a href="#/book/${m.book_id}">${esc(m.book_title)}</a>` : ''}</div>
      <div class="small">Организатор: ${esc(m.organizer)} · Участников: ${m.participants_count}${m.capacity ? ' из ' + m.capacity : ''}</div></div>
    <div class="flex gap-2">${meetingActions(m)}</div></div>
    ${m.description ? `<div class="mt-2">${esc(m.description)}</div>` : ''}</div>`).join('')
    : empty(when === 'mine' ? 'Вы пока не записаны ни на одну встречу' : when === 'past' ? 'Прошедших встреч нет' : 'Предстоящих встреч нет', 'Назначьте встречу сами — кнопка выше.')}
  ${pager(d.count, page, `/meetings?when=${when}`)}`;
  submit($('#mf'), async f => {
    await api('/meetings/', {method: 'POST', body: {title: f.title, description: f.description, place: f.place,
      starts_at: f.starts_at ? new Date(f.starts_at).toISOString() : '', book_id: +f.book_id || null, capacity: f.capacity ? +f.capacity : null}});
    toast('Встреча создана');
    const t = '#/meetings?when=upcoming'; if (location.hash === t) pMeetings(new URLSearchParams('when=upcoming')); else location.hash = t;
  });
  app.querySelectorAll('[data-m]').forEach(b => b.onclick = async () => {
    if (b.dataset.m === 'cancel' && !await confirmDialog({title: 'Отменить встречу?', text: 'Встреча будет отменена для всех участников.', ok: 'Отменить встречу', danger: true})) return;
    b.disabled = true;
    try { await api(`/meetings/${b.dataset.id}/${b.dataset.m}/`, {method: 'POST'}); toast('Готово'); pMeetings(q); }
    catch (e) { toast(errText(e), 'danger'); b.disabled = false; } });
}
