// Копирует Bootstrap и шрифты (Manrope, Literata; кириллица и латиница) в web/static/web — без CDN.
const fs = require('fs'), path = require('path');
const out = path.join(__dirname, '..', 'web', 'static', 'web');
const pkgDir = name => path.dirname(require.resolve(`${name}/package.json`));

const bs = path.join(pkgDir('bootstrap'), 'dist');
fs.mkdirSync(path.join(out, 'vendor', 'bootstrap'), { recursive: true });
for (const [from, to] of [['css/bootstrap.min.css', 'bootstrap.min.css'], ['js/bootstrap.bundle.min.js', 'bootstrap.bundle.min.js']]) {
  const txt = fs.readFileSync(path.join(bs, from), 'utf8').replace(/\/\*# sourceMappingURL=.*?\*\/|\/\/# sourceMappingURL=.*$/gm, '');
  fs.writeFileSync(path.join(out, 'vendor', 'bootstrap', to), txt);
}
const ranges = {
  cyrillic: 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116',
  latin: 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD',
};
let css = '/* Шрифты Manrope и Literata (SIL OFL) раздаются с нашего сервера */\n';
for (const [pkg, family, weights] of [['manrope', 'Manrope', [400, 500, 700]], ['literata', 'Literata', [500, 700]]]) {
  for (const w of weights) for (const [subset, range] of Object.entries(ranges)) {
    const file = `${pkg}-${subset}-${w}-normal.woff2`, src = path.join(pkgDir(`@fontsource/${pkg}`), 'files', file);
    if (!fs.existsSync(src)) { console.warn('нет файла', file); continue; }
    fs.mkdirSync(path.join(out, 'fonts'), { recursive: true });
    fs.copyFileSync(src, path.join(out, 'fonts', file));
    css += `@font-face{font-family:'${family}';font-style:normal;font-display:swap;font-weight:${w};src:url('../fonts/${file}') format('woff2');unicode-range:${range}}\n`;
  }
}
fs.mkdirSync(path.join(out, 'css'), { recursive: true });
fs.writeFileSync(path.join(out, 'css', 'fonts.css'), css);
console.log('готово');
