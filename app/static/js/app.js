// Unitory · top-bar clock + tiny enhancements.
(function () {
  function pad(n) { return String(n).padStart(2, "0"); }

  function tick() {
    const el = document.getElementById("clock");
    if (!el) return;
    const d = new Date();
    const hh = pad(d.getUTCHours());
    const mm = pad(d.getUTCMinutes());
    const ss = pad(d.getUTCSeconds());
    el.textContent = `${hh}:${mm}:${ss} UTC`;
  }

  function stamp() {
    // Stable session-batch id so the page header shows something
    // manifest-y. Not security-relevant; cosmetic.
    const el = document.getElementById("batch-id");
    if (!el) return;
    const seed = Math.floor(Math.random() * 0xffffff)
      .toString(16)
      .toUpperCase()
      .padStart(6, "0");
    el.textContent = `BATCH-${seed}`;
  }

  document.addEventListener("DOMContentLoaded", () => {
    tick();
    stamp();
    setInterval(tick, 1000);
  });
})();
