/* BookCircle · чтение и цели */
const goalCard = (label, g, p) => `<div class="panel p-3 h-100"><div class="flex justify-between items-center"><strong>${label}</strong>${g ? `<button class="btn btn-sm btn-link text-danger p-0" data-goal-del="${p}">Удалить</button>` : ''}</div>${g
  ? `<div class="progress my-2" role="progressbar" aria-valuenow="${g.percent}" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar bg-success" style="width:${g.percent}%">${g.percent}%</div></div><div class="small">${g.done} из ${g.target} книг${g.achieved ? ' — цель достигнута!' : ', осталось ' + g.left}</div>`
  : '<div class="small text-secondary mt-2">Цель не задана</div>'}</div>`;

async function pReading() {
  loading();
  const [d, goals] = await Promise.all([api('/reading/'), api('/goals/')]); const items = d.results || d.items || d;
  const cnt = k => items.filter(i => i.status === k).length;
  app.innerHTML = `<h1 class="h2">Моё чтение</h1>
  <div class="grid grid-cols-3 gap-3 mb-4">${Object.entries(READ).map(([k, v]) => `<div class="panel p-3 text-center"><div class="h3 mb-0">${cnt(k)}</div><div class="small text-secondary">${v}</div></div>`).join('')}</div>
  <h2 class="h5">Цели чтения</h2>
  <div class="grid md:grid-cols-2 gap-3 mb-3">${goalCard('На этот год', goals.year, 'year')}${goalCard('На этот месяц', goals.month, 'month')}</div>
  <form id="gf" class="flex flex-wrap gap-2 items-center mb-4" novalidate><select class="form-select" style="width:auto" name="period" aria-label="Период"><option value="year">На год</option><option value="month">На месяц</option></select><input class="form-control" style="width:120px" type="number" name="target" min="1" max="365" placeholder="Книг"><button class="btn btn-pine">Поставить цель</button></form>
  ${d.finished_this_month !== undefined ? `<p class="text-secondary">Прочитано в этом месяце: <strong>${d.finished_this_month}</strong></p>` : ''}
  ${items.length ? `<div class="panel"><ul class="list-group list-group-flush">${items.map(i => `
    <li class="list-group-item flex flex-wrap items-center justify-between gap-2">
      <div><a href="#/book/${i.book_id}" class="fw-bold text-reset">${esc(i.book_title)}</a>${i.finished_at ? `<div class="small text-secondary">Завершено: ${esc(i.finished_at)}</div>` : ''}</div>
      <select class="form-select form-select-sm" style="width:auto" data-b="${i.book_id}" aria-label="Статус">${Object.entries(READ).map(([k, v]) => `<option value="${k}" ${i.status === k ? 'selected' : ''}>${v}</option>`).join('')}</select></li>`).join('')}</ul></div>`
    : empty('Список пуст', 'Откройте страницу книги и выберите статус чтения.')}`;
  submit($('#gf'), async f => { await api('/goals/', {method: 'PUT', body: {period: f.period, target: +f.target || null}}); toast('Цель сохранена'); pReading(); });
  app.querySelectorAll('[data-goal-del]').forEach(b => b.onclick = async () => { if (!await confirmDialog({title: 'Удалить цель?', text: 'Прогресс по этой цели перестанет отображаться.', ok: 'Удалить', danger: true})) return; try { await api(`/goals/${b.dataset.goalDel}/`, {method: 'DELETE'}); pReading(); } catch (e) { toast(errText(e), 'danger'); } });
  app.querySelectorAll('[data-b]').forEach(s => s.onchange = async () => {
    try { await api(`/reading/${s.dataset.b}/`, {method: 'PUT', body: {status: s.value}}); toast('Статус обновлён'); pReading(); }
    catch (e) { toast(errText(e), 'danger'); } });
}
