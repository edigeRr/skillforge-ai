/**
 * Types out a sample interview question in the hero, like the moment the
 * question actually appears mid-interview. Runs once on load; respects
 * prefers-reduced-motion by just showing the full text immediately.
 */
document.addEventListener("DOMContentLoaded", () => {
  const el = document.querySelector("[data-hero-typewriter]");
  if (!el) return;

  const text = el.dataset.heroTypewriter;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reduceMotion) {
    el.textContent = text;
    return;
  }

  el.textContent = "";
  const cursor = document.createElement("span");
  cursor.className = "hero-cursor";
  cursor.setAttribute("aria-hidden", "true");
  el.after(cursor);

  let i = 0;
  const speed = 28;

  function tick() {
    if (i <= text.length) {
      el.textContent = text.slice(0, i);
      i += 1;
      setTimeout(tick, speed);
    }
  }

  tick();
});
