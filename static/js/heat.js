/**
 * Maps a 0-10 score onto the heat scale in style.css (--heat-0 ... --heat-10):
 * the higher the score, the hotter the metal. Include this after api.js.
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

  Object.assign(window.SkillForge, { heatLevel, heatColor, formatScore });
})();
