const {open, api, tokenOf, sleep, check, fails} = require('./ui.js');
(async () => {
  // ---------- гость ----------
  let {w} = await open(null, null, '/');
  check('гость видит лендинг со статистикой и кнопкой «Присоединиться»', /Общая библиотека/.test(w.text()) && /Присоединиться/.test(w.text()) && /15<\/strong> книг/.test(w.$('.hero-stats').innerHTML));
  check('в подвале есть ссылки на условия, конфиденциальность и API', ['/legal/terms/', '/legal/privacy/', '/api/docs/'].every(h => w.$(`footer a[href="${h}"]`)));

  // ---------- участник ----------
  ({w} = await open('aida', 'pass12345', '/book/1'));
  check('страница книги собирается из 5 источников (каталог, экземпляры, отзывы, чтение, встречи)', /Экземпляры/.test(w.text()) && /Отзывы/.test(w.text()) && !!w.$('#rs'));
  w.$('.half[data-v="3.5"]').click();
  check('клик по левой половине 4-й звезды ставит 3.5', w.$('input[name=score]').value === '3.5' && /3,5 из 5/.test(w.$('[data-val]').textContent));
  w.$('#rv textarea').value = 'Хорошая повесть'; w.$('#rv').requestSubmit(); await sleep(1100);
  check('отзыв опубликован: «Ваш отзыв», 3,5', /Ваш отзыв/.test(w.text()) && /3,5/.test(w.text()), w.text().slice(0, 200));
  w.$('.half[data-v="4.5"]').click(); w.$('#rv').requestSubmit(); await sleep(1100);
  check('редактирование: оценка 4,5, дубликата нет', /4,5/.test(w.text()) && w.$$('[data-edit-review]').length === 1);
  w.$('[data-del-review][data-own="1"]').click(); await sleep(500);
  check('перед удалением отзыва — окно подтверждения', w.$('#cm').classList.contains('show') && /Удалить ваш отзыв/.test(w.$('#cm-title').textContent));
  w.$('#cm .btn-outline-secondary').click(); await sleep(500);
  check('«Отмена» не удаляет', w.$$('[data-edit-review]').length === 1);
  w.$('[data-del-review][data-own="1"]').click(); await sleep(500); w.$('#cm-ok').click(); await sleep(1300);
  check('после подтверждения отзыв удалён', !w.$('[data-edit-review]'));
  w.$('#theme-btn').click();
  check('тёмная тема переключается и запоминается', w.document.documentElement.getAttribute('data-theme') === 'dark' && w.localStorage.getItem('bc_theme') === 'dark');
  w.$('#theme-btn').click();
  await w.go('/shelf');
  w.$('#bk-filter').value = 'кинг'; w.$('#bk-filter').dispatchEvent(new w.Event('input'));
  check('«Моя полка»: все 15 книг каталога, поиск по списку', w.$$('#bk-sel option').length - 1 === 2 && /15 книг|\(15\)/.test(w.$('.form-text').textContent) || /\(2 из 15\)/.test(w.$('#bk-sel option').textContent), w.$('#bk-sel option').textContent);
  await w.go('/submit');
  w.$('#sf [name=title]').value = 'Мартин Иден'; w.$('#sf [name=author]').value = 'Джек Лондон'; w.$('#sf [name=genre]').value = 'Роман'; w.$('#sf').requestSubmit(); await sleep(1100);
  check('предложенная книга уходит на модерацию', /Мартин Иден/.test(w.text()) && /На модерации/.test(w.text()));
  check('в шапке колокольчик с числом непрочитанных', /Уведомления: [1-9]/.test(w.$('#auth-box a[href="#/notifications"]').getAttribute('aria-label')), w.$('#auth-box').innerHTML.slice(0, 200));
  check('баннер предупреждает о просрочке', /Просрочен возврат/.test(w.$('#alerts').textContent));
  await w.go('/notifications');
  check('уведомления: список с непрочитанными', w.$$('.notif.unread').length >= 1 && !!w.$('#readall'));
  w.$('#readall').click(); await sleep(1200);
  check('«Отметить все» очищает значок', !/Уведомления: [1-9]/.test(w.$('#auth-box a[href="#/notifications"]').getAttribute('aria-label')) && w.$$('.notif.unread').length === 0);
  await w.go('/profile');
  check('в профиле: уведомления на email, экспорт и удаление', !!w.$('#ne') && !!w.$('#exp') && !!w.$('#del'));
  w.$('#logout').click(); await sleep(500);
  check('выход открывает окно подтверждения', w.$('#cm').classList.contains('show') && /Выйти из аккаунта/.test(w.$('#cm-title').textContent));
  w.$('#cm .btn-outline-secondary').click(); await sleep(500);
  check('«Отмена» оставляет в аккаунте', !!w.$('#logout'));
  w.$('#logout').click(); await sleep(500); w.$('#cm-ok').click(); await sleep(900);
  check('подтверждение выхода работает', !w.$('#logout') && /Войти/.test(w.$('#auth-box').textContent));
  check('JS-ошибок нет (участник)', w.errors.length === 0, w.errors.join('; '));

  // ---------- удаление аккаунта через интерфейс ----------
  await api('/auth/register/', null, 'POST', {username: 'tempuser', email: 'temp@example.com', password: 'Strong-pass-4711'});
  ({w} = await open('tempuser', 'Strong-pass-4711', '/profile'));
  w.$('#del').click(); await sleep(500);
  check('удаление аккаунта: открыто окно с подтверждением логином и паролем', w.$('#erm').classList.contains('show') && !!w.$('#erf [name=password]'));
  w.$('#erf [name=confirm]').value = 'wrong'; w.$('#erf [name=password]').value = 'Strong-pass-4711'; w.$('#erf').requestSubmit(); await sleep(900);
  check('неверное подтверждение показывает ошибку у поля', !!w.$('#erf .invalid-feedback'));
  w.$('#erf [name=confirm]').value = 'tempuser'; w.$('#erf').requestSubmit(); await sleep(1300);
  check('аккаунт удалён: выход и повторный вход невозможен', !w.$('#logout') && (await api('/auth/login/', null, 'POST', {username: 'tempuser', password: 'Strong-pass-4711'})).status === 400);

  // ---------- модератор ----------
  const mod = await tokenOf('moder', 'moder12345');
  ({w} = await open('moder', 'moder12345', '/moderation?tab=books'));
  const before = (await api('/moderation/books/', mod)).data.count;
  w.$$('[data-mb="reject"]')[0].click(); await sleep(500);
  check('отклонение запрашивает причину в окне сайта', w.$('#cm').classList.contains('show') && !!w.$('#cm-input'));
  w.$('#cm-input').value = 'Нужна обложка'; w.$('#cm-ok').click(); await sleep(1300);
  check('книга отклонена, очередь уменьшилась', (await api('/moderation/books/', mod)).data.count === before - 1);
  const nurlan = await tokenOf('nurlan', 'pass12345');
  check('автор получил уведомление с причиной', (await api('/notifications/', nurlan)).data.results.some(n => n.kind === 'book_rejected' && n.body === 'Нужна обложка'));
  await w.go('/moderation?tab=edits');
  check('правка показана «было → стало»', /→/.test(w.text()));
  w.$('[data-me="approve"]').click(); await sleep(1100);
  check('правка применена', (await api('/moderation/edits/', mod)).data.count === 0);
  await w.go('/moderation?tab=reviews');
  check('модератор не видит удаление рецензий', !w.$('[data-rd]') && !!w.$('[data-h]'));
  await w.go('/stats');
  check('аналитика: карточки и графики', w.$$('.panel .display-6').length >= 8 && w.$$('.bars').length === 2 && /Новые участники/.test(w.text()));
  check('JS-ошибок нет (модератор)', w.errors.length === 0, w.errors.join('; '));

  // ---------- администратор ----------
  ({w} = await open('admin', 'admin12345', '/book/1'));
  const n0 = w.$$('[data-del-review]').length;
  check('админ видит удаление чужих отзывов', n0 >= 1, String(n0));
  w.$('[data-del-review]').click(); await sleep(500);
  check('удаление — через окно подтверждения', w.$('#cm').classList.contains('show') && /пользователя/.test(w.$('#cm-title').textContent));
  w.$('#cm-ok').click(); await sleep(1300);
  check('отзыв удалён', w.$$('[data-del-review]').length === n0 - 1);
  check('у админа «Удалить книгу» и «Скрыть из каталога»', !!w.$('[data-bk="delete"]') && !!w.$('[data-bk="hide"]'));
  check('JS-ошибок нет (админ)', w.errors.length === 0, w.errors.join('; '));
  console.log(fails() ? `\nПровалено: ${fails()}` : '\nВсе проверки пройдены');
  process.exit(fails() ? 1 : 0);
})().catch(e => { console.error('FAIL', e); process.exit(1); });
