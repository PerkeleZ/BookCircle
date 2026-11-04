/* BookCircle · уведомления */

async function pNotifications(q) {
  const page = +q.get('page') || 1; loading();
  const d = list(await api(`/notifications/?page=${page}&page_size=15`));
  app.innerHTML = `<div class="flex flex-wrap items-center justify-between gap-2 mb-3"><h1 class="h2 mb-0">Уведомления</h1>${d.results.some(n => !n.is_read) ? '<button class="btn btn-sm btn-outline-secondary" id="readall">Отметить все прочитанными</button>' : ''}</div>
  ${d.results.length ? `<div class="panel"><ul class="list-group list-group-flush">${d.results.map(n => `<li class="list-group-item notif ${n.is_read ? '' : 'unread'}"><a class="text-reset text-decoration-none d-block" href="${esc(n.link || '#/notifications')}" data-nid="${n.id}">
      <div class="flex justify-between gap-2"><strong>${esc(n.title)}</strong><small class="text-secondary">${esc(fmtDt(n.created_at))}</small></div><div class="small text-secondary">${esc(n.body)}</div></a></li>`).join('')}</ul></div>`
    : empty('Уведомлений нет', 'Здесь появятся запросы на книги, решения модераторов и напоминания о сроках.')}
  ${pager(d.count, page, '/notifications')}`;
  $('#readall')?.addEventListener('click', async () => { try { await api('/notifications/read/', {method: 'POST', body: {all: true}}); unread = 0; renderNav(); pNotifications(q); } catch (e) { toast(errText(e), 'danger'); } });
  app.querySelectorAll('[data-nid]').forEach(a => a.addEventListener('click', () => {
    alertsAt = 0;  // после перехода счётчик обновится сразу
    api('/notifications/read/', {method: 'POST', body: {ids: [+a.dataset.nid]}}).catch(() => {});
  }));
}
