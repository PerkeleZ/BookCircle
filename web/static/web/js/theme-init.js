(function () {  // тема выбирается до отрисовки страницы, чтобы не было «мигания»
  var t = localStorage.getItem("bc_theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", t);
  document.documentElement.setAttribute("data-bs-theme", t);
})();
