// Unitory · sidebar toggle + active nav link.
(function () {
  function initSidebarToggle() {
    const btn = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("sidebar");
    if (!btn || !sidebar) return;
    btn.addEventListener("click", () => {
      sidebar.classList.toggle("is-open");
      document.body.classList.toggle("has-sidebar-open", sidebar.classList.contains("is-open"));
    });
    document.body.addEventListener("click", (e) => {
      if (!sidebar.classList.contains("is-open")) return;
      if (sidebar.contains(e.target) || btn.contains(e.target)) return;
      sidebar.classList.remove("is-open");
      document.body.classList.remove("has-sidebar-open");
    });
  }

  function highlightActiveNav() {
    const path = window.location.pathname;
    document.querySelectorAll(".sidebar-nav .nav-link").forEach((link) => {
      const href = link.getAttribute("href");
      if (!href) return;
      const active = href === "/" ? path === "/" : path.startsWith(href);
      link.classList.toggle("active", active);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initSidebarToggle();
    highlightActiveNav();
  });
})();
