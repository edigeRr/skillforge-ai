/**
 * Maps a 0-10 score onto the heat scale in style.css (--heat-0 ... --heat-10):
 * the higher the score, the hotter the metal. paintScore fills in a .score
 * block (see score.css). Include this after api.js.
 */
(() => {
  function heatLevel(score) {
    const clamped = Math.min(10, Math.max(0, Number(score) || 0));
    return Math.floor(clamped / 2) * 2;
  }

  function heatColor(score) {
    return `var(--heat-${heatLevel(score)})`;
  }

  function formatScore(score) {
    return Number(score).toFixed(1);
  }

  function paintScore(element, score) {
    element.querySelector(".score-value").textContent = formatScore(score);
    const meter = element.querySelector(".score-meter");
    meter.setAttribute("aria-valuenow", String(score));
    meter.setAttribute("aria-valuetext", `${formatScore(score)} out of 10`);
    const fill = element.querySelector(".score-fill");
    fill.style.width = `${Math.min(10, Math.max(0, score)) * 10}%`;
    fill.style.background = heatColor(score);
    element.dataset.heat = String(heatLevel(score));
  }

  Object.assign(window.SkillForge, { heatLevel, heatColor, formatScore, paintScore });
})();
