/**
 * Shared across every page: toggles [data-auth] elements based on login
 * state, and wires up any [data-action="logout"] control. Include this
 * after api.js.
 */
document.addEventListener("DOMContentLoaded", () => {
  const { isLoggedIn, clearTokens, getRefreshToken, api } = window.SkillForge;

  const loggedOutEls = document.querySelectorAll("[data-auth='logged-out']");
  const loggedInEls = document.querySelectorAll("[data-auth='logged-in']");

  function syncAuthUI() {
    // Explicit values in both branches - relying on an empty string to
    // "fall back to the CSS default" was unreliable once .btn's own
    // `display: inline-flex` was in the mix.
    const authed = isLoggedIn();
    loggedOutEls.forEach((el) => (el.style.display = authed ? "none" : "inline-flex"));
    loggedInEls.forEach((el) => (el.style.display = authed ? "inline-flex" : "none"));
  }

  syncAuthUI();

  const logoutBtn = document.querySelector("[data-action='logout']");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      const refreshToken = getRefreshToken();
      try {
        if (refreshToken) {
          await api.post("/auth/logout", { refresh_token: refreshToken });
        }
      } catch {
        // best-effort: clear local state regardless of whether the call succeeded
      } finally {
        clearTokens();
        window.location.href = "/";
      }
    });
  }
});
