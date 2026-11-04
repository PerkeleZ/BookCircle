/* BookCircle · вход, регистрация, профиль, Google */
function pAuth(mode) {
  const reg = mode === 'register';
  app.innerHTML = `<div class="mx-auto" style="max-width:420px"><h1 class="h2">${reg ? 'Регистрация' : 'Вход'}</h1>
  <form id="af" class="panel p-4" novalidate>
    <label class="form-label">Логин</label><input class="form-control mb-3" name="username" autocomplete="username">
    ${reg ? '<label class="form-label">Email</label><input class="form-control mb-3" name="email" type="email">' : ''}
    <label class="form-label">Пароль</label><input class="form-control mb-3" name="password" type="password" autocomplete="${reg ? 'new' : 'current'}-password">
    ${reg ? '' : '<div class="text-end mb-3"><a class="small" href="#/forgot">Забыли пароль?</a></div>'}
    <button class="btn btn-pine w-100">${reg ? 'Создать аккаунт' : 'Войти'}</button></form>
  <div id="gwrap" class="mt-3 text-center" hidden><div class="small text-secondary mb-2">или</div><div id="gbtn" class="flex justify-center"></div></div>
  <p class="mt-3 small">${reg ? 'Уже есть аккаунт? <a href="#/login">Войти</a>' : 'Нет аккаунта? <a href="#/register">Зарегистрироваться</a>'}</p></div>`;
  submit($('#af'), async f => {
    const d = await api(reg ? '/auth/register/' : '/auth/login/', {method: 'POST', body: f});
    localStorage.setItem('bc_token', d.token); me = await api('/auth/me/'); renderNav(); toast('Добро пожаловать!'); go('/');
  });
  googleButton('#gbtn', '#gwrap', async cred => {
    try {
      const d = await api('/auth/google/', {method: 'POST', body: {credential: cred}});
      localStorage.setItem('bc_token', d.token); me = await api('/auth/me/'); renderNav(); toast('Добро пожаловать!'); go('/');
    } catch (e) { toast(errText(e), 'danger'); }
  });
}

/* ---- Google Identity Services: кнопка входа/привязки ---- */
let gReady = null, gHandler = null;

async function googleButton(sel, wrap, handler) {
  try {
    if (!gReady) gReady = (async () => {
      const cfg = await api('/auth/google/config/');
      if (!cfg.client_id) return false;
      await new Promise((ok, no) => { const s = document.createElement('script'); s.src = 'https://accounts.google.com/gsi/client'; s.onload = ok; s.onerror = no; document.head.appendChild(s); });
      google.accounts.id.initialize({client_id: cfg.client_id, callback: r => gHandler && gHandler(r.credential)});
      return true;
    })();
    if (!(await gReady)) return false;
    const el = $(sel); if (!el) return false;  // страница могла смениться, пока грузился скрипт
    gHandler = handler; if (wrap) $(wrap).hidden = false;
    google.accounts.id.renderButton(el, {theme: 'outline', size: 'large', text: 'continue_with', width: 300, locale: 'ru'});
    return true;
  } catch { gReady = null; return false; }
}

function pForgot() {
  app.innerHTML = `<div class="mx-auto" style="max-width:420px"><h1 class="h2">Восстановление пароля</h1>
  <form id="ff" class="panel p-4" novalidate><p class="text-secondary small">Укажите email, с которым вы регистрировались. В режиме разработки письмо с кодом печатается в терминале, где запущен сервер: почта и Gmail не используются.</p>
    <label class="form-label">Email</label><input class="form-control mb-3" name="email" type="email" autocomplete="email">
    <button class="btn btn-pine w-100">Отправить код</button></form>
  <p class="mt-3 small"><a href="#/login">Вернуться ко входу</a> · <a href="#/reset">У меня уже есть код</a></p></div>`;
  submit($('#ff'), async f => {
    const d = await api('/auth/password-reset/', {method: 'POST', body: f});
    toast(d.detail); go('/reset?email=' + encodeURIComponent(f.email));
  });
}

function pReset(q) {
  app.innerHTML = `<div class="mx-auto" style="max-width:420px"><h1 class="h2">Новый пароль</h1>
  <form id="rf" class="panel p-4" novalidate>
    <label class="form-label">Email</label><input class="form-control mb-3" name="email" type="email" value="${esc(q.get('email') || '')}">
    <label class="form-label">Код из письма</label><input class="form-control mb-3" name="code" inputmode="numeric" maxlength="6" autocomplete="one-time-code" value="${esc(q.get('code') || '')}" placeholder="6 цифр">
    <label class="form-label">Новый пароль</label><input class="form-control mb-3" name="password" type="password" autocomplete="new-password">
    <label class="form-label">Повторите пароль</label><input class="form-control mb-3" name="password2" type="password" autocomplete="new-password">
    <button class="btn btn-pine w-100">Сохранить пароль</button></form>
  <p class="mt-3 small">Код действует 10 минут. <a href="#/forgot">Отправить новый код</a></p></div>`;
  submit($('#rf'), async f => {
    if (f.password !== f.password2) throw {status: 400, data: {password2: 'Пароли не совпадают.'}};
    await api('/auth/password-reset/confirm/', {method: 'POST', body: {email: f.email, code: f.code.trim(), password: f.password}});
    toast('Пароль изменён. Войдите с новым паролем.'); go('/login');
  });
}

async function pProfile() {
  loading(); me = await api('/auth/me/');
  app.innerHTML = `<div class="mx-auto" style="max-width:480px"><h1 class="h2">Профиль</h1>
  <form id="pf" class="panel p-4"><label class="form-label">Логин</label><input class="form-control mb-3" value="${esc(me.username)}" disabled>
    <label class="form-label">Email</label><input class="form-control mb-3" name="email" type="email" value="${esc(me.email)}">
    <label class="form-label">Телефон</label><input class="form-control mb-1" name="phone" type="tel" value="${esc(me.phone || '')}" placeholder="+996 555 123 456"><div class="form-text mb-3">Нужен, чтобы владелец мог связаться с вами при получении книги (виден только участнику обмена).</div>
    <label class="form-label">О себе</label><textarea class="form-control mb-3" name="bio" rows="3">${esc(me.bio)}</textarea>
    <div class="form-check mb-3"><input class="form-check-input" type="checkbox" name="notify_email" id="ne" ${me.notify_email ? 'checked' : ''}><label class="form-check-label" for="ne">Дублировать уведомления на email</label></div>
    <div class="small text-secondary mb-3">Роль: ${esc(me.role)}</div><button class="btn btn-pine">Сохранить профиль</button></form>
  <div class="panel p-4 mt-3"><h2 class="h5">Google-аккаунт</h2>
    ${me.google_email
      ? `<p class="mb-2">Привязан: <strong>${esc(me.google_email)}</strong></p>${me.has_password ? '' : '<p class="small text-secondary">Пароль не задан: чтобы отвязать Google, сначала задайте пароль через «Забыли пароль?» на странице входа.</p>'}<button class="btn btn-sm btn-outline-danger" id="gun">Отвязать</button>`
      : `<p class="small text-secondary">Привяжите Google, чтобы входить на сайт одним нажатием.</p><div id="gbtn2"></div><div id="gnote" class="small text-secondary" hidden>Вход через Google не настроен на сервере (GOOGLE_CLIENT_ID).</div>`}
  </div>
  <div class="panel p-4 mt-3"><h2 class="h5">Ваши данные</h2><p class="small text-secondary">Скачайте копию своих данных или удалите аккаунт. Подробнее — в <a href="/legal/privacy/">политике конфиденциальности</a>.</p>
    <button class="btn btn-sm btn-outline-secondary" id="exp">Скачать мои данные</button> <button class="btn btn-sm btn-outline-danger" id="del">Удалить аккаунт</button></div></div>
  <div class="modal fade" id="erm" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><form class="modal-content" id="erf" novalidate>
    <div class="modal-header"><h5 class="modal-title">Удалить аккаунт?</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button></div>
    <div class="modal-body"><p>Профиль, отзывы, отметки чтения, цели и уведомления будут стёрты. История обменов у других участников останется с обезличенным именем. Действие нельзя отменить.</p>
      <label class="form-label">Введите свой логин (${esc(me.username)}) для подтверждения</label><input class="form-control mb-2" name="confirm" autocomplete="off">
      ${me.has_password ? '<label class="form-label">Пароль</label><input class="form-control" type="password" name="password" autocomplete="current-password">' : ''}</div>
    <div class="modal-footer"><button class="btn btn-danger">Удалить навсегда</button></div></form></div></div>`;
  submit($('#pf'), async f => { me = await api('/auth/me/', {method: 'PATCH', body: {...f, notify_email: $('#pf').elements.notify_email.checked}}); toast('Профиль обновлён'); });
  $('#exp').onclick = async () => {  // право на переносимость данных
    try {
      const d = await api('/privacy/export/'), a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], {type: 'application/json'})); a.download = `bookcircle-data-${me.username}.json`; a.click(); URL.revokeObjectURL(a.href);
    } catch (e) { toast(errText(e), 'danger'); }
  };
  const erm = bootstrap.Modal.getOrCreateInstance($('#erm'));
  $('#del').onclick = () => erm.show();
  submit($('#erf'), async f => {  // право на удаление данных
    await api('/privacy/erase/', {method: 'POST', body: f}); erm.hide();
    localStorage.removeItem('bc_token'); me = null; alertState = {count: 0, overdue: 0, results: []}; unread = 0; renderAlerts(); renderNav(); go('/'); toast('Аккаунт удалён. Ваши данные стёрты.');
  });
  if (me.google_email) $('#gun').onclick = async () => {
    try { await api('/auth/google/unlink/', {method: 'POST'}); toast('Google отвязан'); pProfile(); }
    catch (e) { toast(errText(e), 'danger'); }
  };
  else googleButton('#gbtn2', null, async cred => {
    try { await api('/auth/google/link/', {method: 'POST', body: {credential: cred}}); toast('Google-аккаунт привязан'); pProfile(); }
    catch (e) { toast(errText(e), 'danger'); }
  }).then(ok => { if (!ok && $('#gnote')) $('#gnote').hidden = false; });
}
