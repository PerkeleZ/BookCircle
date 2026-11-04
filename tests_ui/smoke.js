const {open, check, fails} = require('./ui.js');
(async () => {
  const routes = ['/', '/book/1', '/shelf', '/loans?box=incoming', '/loans?box=outgoing', '/loans?box=active', '/meetings', '/reading', '/submit', '/notifications', '/profile', '/moderation?tab=books', '/moderation?tab=edits', '/moderation?tab=reviews', '/stats', '/nope'];
  const {srcs} = await open(null, null, null);
  check('страница подключает 12 локальных скриптов (без CDN)', srcs.length === 12 && srcs.every(s => s.startsWith('/static/')), String(srcs));
  for (const [u, p] of [['aida', 'pass12345'], ['moder', 'moder12345'], ['admin', 'admin12345'], [null]]) {
    const {w} = await open(u, p, null); const errs = [];
    for (const r of (u ? routes : ['/', '/book/1', '/login', '/stats', '/shelf'])) {
      await w.go(r); const danger = w.$$('#app .alert-danger').map(a => a.textContent.trim().slice(0, 80));
      const blank = w.text().trim().length < 20;
      const expectedDenied = (r === '/stats' && (!u || u === 'aida')) || r === '/nope' || (r.startsWith('/moderation') && u === 'aida');
      console.log(`${(u || 'гость').padEnd(6)} ${r.padEnd(26)} ${danger.length ? 'ERR ' + danger : blank ? 'ПУСТО' : 'ok'} | ${w.text().slice(0, 70)}`);
      if (danger.length || blank) errs.push(r);
    }
    check(`${u || 'гость'}: страницы открываются без ошибок`, errs.length === 0, errs.join(', '));
    check(`${u || 'гость'}: нет ошибок JS`, w.errors.length === 0, w.errors.join('; '));
  }
  process.exit(fails() ? 1 : 0);
})().catch(e => { console.error('FAIL', e); process.exit(1); });
