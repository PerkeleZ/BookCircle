const {JSDOM} = require('jsdom');
const BASE = process.env.BASE_URL || 'http://127.0.0.1:8140';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const J = {'Content-Type': 'application/json'};
async function api(path, tok, method = 'GET', body) { const r = await fetch(BASE + '/api' + path, {method, headers: tok ? {...J, Authorization: 'Token ' + tok} : J, body: body && JSON.stringify(body)}); return {status: r.status, data: r.status === 204 ? null : await r.json().catch(() => null)}; }
const tokenOf = async (u, p) => (await api('/auth/login/', null, 'POST', {username: u, password: p})).data.token;
async function open(user, pass, hash) {
  const html = await (await fetch(BASE + '/')).text();
  const srcs = [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);
  const code = []; for (const s of srcs) code.push([s, await (await fetch(BASE + s)).text()]);
  const dom = new JSDOM(html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<link[^>]*>/g, ''), {url: BASE + '/', runScripts: 'dangerously', pretendToBeVisual: true});
  const w = dom.window; w.errors = [];
  w.fetch = (u, o) => fetch(new URL(u, BASE + '/'), o);
  w.addEventListener('error', e => w.errors.push(e.message)); w.addEventListener('unhandledrejection', e => w.errors.push(String(e.reason && e.reason.message || e.reason)));
  w.Element.prototype.scrollIntoView = () => {};
  w.matchMedia = () => ({matches: false});  // в jsdom нет matchMedia
  if (user) w.localStorage.setItem('bc_token', await tokenOf(user, pass));
  for (const [s, c] of code) { const el = w.document.createElement('script'); el.textContent = c; w.document.head.appendChild(el); }  // как <script> в браузере: общее глобальное пространство имён
  await sleep(900);
  if (hash) { w.location.hash = '#' + hash; await sleep(900); }
  w.$ = s => w.document.querySelector(s); w.$$ = s => [...w.document.querySelectorAll(s)];
  w.text = () => w.$('#app').textContent.replace(/\s+/g, ' ');
  w.go = async h => { w.location.hash = '#' + h; await sleep(900); };
  return {w, srcs};
}
let fails = 0; const check = (name, ok, info = '') => { console.log((ok ? 'PASS' : 'FAIL') + '  ' + name + (ok ? '' : '   ' + info)); if (!ok) fails++; };
module.exports = {open, api, tokenOf, sleep, check, BASE, fails: () => fails};
