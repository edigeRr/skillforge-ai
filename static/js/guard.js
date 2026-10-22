/**
 * Sends logged-out visitors to /login before a members-only page renders.
 * Include this in <head>, right after api.js.
 */
(() => {
  const LOGIN_URL = "/login";

  if (!window.SkillForge.isLoggedIn()) {
    window.location.replace(LOGIN_URL);
  }
})();
