/**
 * Thin client for the SkillForge AI API. Stores tokens in localStorage
 * (convenient for a demo you might revisit later; a stricter production
 * setup would use an HttpOnly cookie instead) and automatically retries
 * once with a refreshed access token on a 401 before giving up.
 */
(() => {
  const API_BASE = "/api/v1";
  const TOKEN_KEY = "skillforge_access_token";
  const REFRESH_KEY = "skillforge_refresh_token";

  function getAccessToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getRefreshToken() {
    return localStorage.getItem(REFRESH_KEY);
  }

  function setTokens({ access_token, refresh_token }) {
    localStorage.setItem(TOKEN_KEY, access_token);
    localStorage.setItem(REFRESH_KEY, refresh_token);
  }

  function clearTokens() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }

  function isLoggedIn() {
    return Boolean(getAccessToken());
  }

  /**
   * The role claim from the access token, or null. Only a display hint (which
   * nav links to show): the server checks the real role on every request.
   */
  function getRole() {
    const token = getAccessToken();
    if (!token) return null;
    try {
      const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      return JSON.parse(atob(payload.padEnd(Math.ceil(payload.length / 4) * 4, "="))).role ?? null;
    } catch {
      return null;
    }
  }

  /** Body fields a 422 names, e.g. ["email"] for loc ["body", "email"]. */
  function invalidFields(detail) {
    if (!Array.isArray(detail)) return [];
    return detail
      .map((item) => (item?.loc?.[0] === "body" ? item.loc[1] : undefined))
      .filter((field) => typeof field === "string");
  }

  class ApiError extends Error {
    constructor(status, errorCode, detail) {
      super(typeof detail === "string" ? detail : errorCode || `Request failed (${status})`);
      this.status = status;
      this.errorCode = errorCode;
      this.fields = invalidFields(detail);
    }
  }

  async function tryRefresh() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) return false;
      setTokens(await response.json());
      return true;
    } catch {
      return false;
    }
  }

  async function request(path, { method = "GET", body, auth = true, retry = true } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (auth) {
      const token = getAccessToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401 && auth && retry && getRefreshToken()) {
      const refreshed = await tryRefresh();
      if (refreshed) {
        return request(path, { method, body, auth, retry: false });
      }
      clearTokens();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new ApiError(401, "UNAUTHORIZED", "Session expired - please log in again.");
    }

    if (response.status === 204) {
      return null;
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new ApiError(response.status, data.error_code, data.detail);
    }

    return data;
  }

  const api = {
    get: (path) => request(path, { method: "GET" }),
    post: (path, body, opts = {}) => request(path, { method: "POST", body, ...opts }),
    put: (path, body) => request(path, { method: "PUT", body }),
    patch: (path, body) => request(path, { method: "PATCH", body }),
  };

  window.SkillForge = {
    api,
    ApiError,
    getAccessToken,
    getRefreshToken,
    setTokens,
    clearTokens,
    isLoggedIn,
    getRole,
  };
})();
