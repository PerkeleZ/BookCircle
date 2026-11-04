// Tailwind используется только для раскладки (flex/grid/gap); компоненты — Bootstrap, поэтому лишние плагины отключены.
module.exports = {
  content: ['../web/static/web/js/**/*.js', '../web/templates/web/**/*.html'],
  corePlugins: { preflight: false, container: false, visibility: false },
};
