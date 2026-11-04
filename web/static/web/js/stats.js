/* BookCircle · аналитика для модераторов */

async function pStats() {
  loading(); const d = await api('/stats/');
  const card = (t, v, s = '') => `<div class="panel p-3 h-100"><div class="small text-secondary">${t}</div><div class="display-6 fw-bold">${v}</div><div class="small text-secondary">${s}</div></div>`;
  const bars = (series, label) => { const max = Math.max(1, ...series.map(x => x.count)); return `<div class="panel p-3 h-100"><strong>${label}</strong><div class="bars mt-3">${series.map(x => `<div class="bar-col" title="Неделя с ${esc(x.week)}: ${x.count}"><div class="bar-wrap"><div class="bar" style="height:${Math.round(x.count / max * 100)}%"></div></div><div class="bar-n">${x.count}</div><div class="bar-l">${esc(x.week.slice(5))}</div></div>`).join('')}</div></div>`; };
  app.innerHTML = `<h1 class="h2">Аналитика</h1><p class="text-secondary">Показатели платформы; данные обновляются раз в минуту.</p>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">${card('Участники', d.users.total, `+${d.users.new_7d} за 7 дней`)}${card('Книги в каталоге', d.books.approved, `на модерации: ${d.books.pending}, правок: ${d.books.edits_pending}`)}${card('Книги на руках', d.loans.on_hand, `просрочено: ${d.loans.overdue}`)}${card('Обменов завершено', d.loans.returned_total, `запросов за 30 дней: ${d.loans.requested_30d}`)}</div>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">${card('Экземпляры на полках', d.copies.active, `всего: ${d.copies.total}`)}${card('Предстоящие встречи', d.meetings_upcoming)}${card('Отзывы', d.reviews_total)}${card('Скрытые книги', d.books.hidden)}</div>
  <div class="grid md:grid-cols-2 gap-3">${bars(d.series.new_users, 'Новые участники по неделям')}${bars(d.series.loans, 'Запросы на книги по неделям')}</div>`;
}
