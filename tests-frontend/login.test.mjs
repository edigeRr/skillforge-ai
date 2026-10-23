import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM, VirtualConsole } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const loginHtml = readStatic("login.html");
const apiScript = readStatic("js/api.js");
const loginScript = readStatic("js/login.js");

const LOGIN_URL = "/api/v1/auth/login";
const ACCESS_TOKEN_KEY = "skillforge_access_token";
const REFRESH_TOKEN_KEY = "skillforge_refresh_token";

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const tokens = () =>
  jsonResponse(200, {
    access_token: "access-123",
    refresh_token: "refresh-456",
    token_type: "bearer",
    expires_in: 1800,
  });
const wrongCredentials = () =>
  jsonResponse(401, { detail: "Invalid email or password.", error_code: "INVALID_CREDENTIALS" });

async function openLoginPage(t, routes) {
  const calls = [];
  const navigations = [];

  async function fetchImpl(url, init = {}) {
    calls.push({ url, method: init.method, body: init.body ? JSON.parse(init.body) : undefined });
    assert.ok(routes[url], `unexpected request to ${url}`);
    return routes[url]();
  }

  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (error) => {
    if (error.message.startsWith("Not implemented: navigation")) {
      navigations.push(error.message);
    } else {
      console.error(error);
    }
  });

  const dom = new JSDOM(loginHtml, {
    url: "http://localhost:8000/login",
    runScripts: "outside-only",
    virtualConsole,
  });
  const { window } = dom;
  t.after(() => window.close());

  window.fetch = fetchImpl;
  window.eval(apiScript);
  window.eval(loginScript);

  if (window.document.readyState === "loading") {
    await new Promise((resolve) => {
      window.document.addEventListener("DOMContentLoaded", resolve, { once: true });
    });
  }

  const { document } = window;
  return {
    window,
    calls,
    navigations,
    form: document.querySelector("#login-form"),
    banner: document.querySelector("#form-error"),
    button: document.querySelector('button[type="submit"]'),
    fields: {
      email: document.querySelector("#email"),
      password: document.querySelector("#password"),
    },
  };
}

function fill(page, { email = "ada@example.com", password = "Str0ngPass1" } = {}) {
  page.fields.email.value = email;
  page.fields.password.value = password;
}

function submit(page) {
  page.form.requestSubmit();
}

async function waitFor(condition, description) {
  const deadline = Date.now() + 2000;
  while (!condition()) {
    if (Date.now() > deadline) assert.fail(`timed out waiting for ${description}`);
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
}

const bannerShown = (page) => !page.banner.hidden;
const storedAccessToken = (page) => page.window.localStorage.getItem(ACCESS_TOKEN_KEY);

test("logs in, stores the tokens and leaves the page", async (t) => {
  const page = await openLoginPage(t, { [LOGIN_URL]: tokens });
  fill(page, { email: "  ada@example.com  " });

  submit(page);
  await waitFor(() => page.navigations.length === 1, "the redirect after log-in");

  assert.deepEqual(page.calls, [
    {
      url: LOGIN_URL,
      method: "POST",
      body: { email: "ada@example.com", password: "Str0ngPass1" },
    },
  ]);
  assert.equal(storedAccessToken(page), "access-123");
  assert.equal(page.window.localStorage.getItem(REFRESH_TOKEN_KEY), "refresh-456");
  assert.equal(page.banner.hidden, true);
});

test("does not try to refresh a token when the credentials are wrong", async (t) => {
  const page = await openLoginPage(t, { [LOGIN_URL]: wrongCredentials });
  page.window.localStorage.setItem(REFRESH_TOKEN_KEY, "stale-refresh");
  fill(page);

  submit(page);
  await waitFor(() => bannerShown(page), "the error banner");

  assert.equal(page.calls.length, 1);
  assert.equal(page.navigations.length, 0);
});

const FAILURES = [
  { name: "wrong credentials", respond: wrongCredentials, message: /^Incorrect email or password\.$/ },
  {
    name: "an email the API rejects",
    respond: () =>
      jsonResponse(422, { detail: [{ loc: ["body", "email"], msg: "not a valid email" }] }),
    message: /^That email address doesn't look right/,
  },
  {
    name: "rate limiting",
    respond: () =>
      jsonResponse(429, { detail: "Too many attempts", error_code: "TOO_MANY_ATTEMPTS" }),
    message: /too many attempts/i,
  },
  {
    name: "server errors",
    respond: () => jsonResponse(500, { detail: "boom", error_code: "INTERNAL_ERROR" }),
    message: /something went wrong/i,
  },
  {
    name: "a network failure",
    respond: () => Promise.reject(new TypeError("Failed to fetch")),
    message: /can't reach the server/i,
  },
];

for (const failure of FAILURES) {
  test(`shows a clear message for ${failure.name} and lets the user retry`, async (t) => {
    const page = await openLoginPage(t, { [LOGIN_URL]: failure.respond });
    fill(page);

    submit(page);
    await waitFor(() => bannerShown(page), "the error banner");

    assert.match(page.banner.textContent, failure.message);
    assert.equal(page.calls.length, 1);
    assert.equal(page.button.disabled, false);
    assert.equal(page.button.textContent, "Log in");
    assert.equal(storedAccessToken(page), null);
    assert.equal(page.navigations.length, 0);
  });
}

test("hides the old error when the user tries again", async (t) => {
  let respond = wrongCredentials;
  const page = await openLoginPage(t, { [LOGIN_URL]: () => respond() });
  fill(page);
  submit(page);
  await waitFor(() => bannerShown(page), "the error banner");

  respond = tokens;
  submit(page);
  await waitFor(() => page.navigations.length === 1, "the redirect after log-in");

  assert.equal(page.banner.hidden, true);
  assert.equal(page.banner.textContent, "");
});

test("locks the button while the request is in flight and ignores a second submit", async (t) => {
  let finishLogin;
  const page = await openLoginPage(t, {
    [LOGIN_URL]: () =>
      new Promise((resolve) => {
        finishLogin = resolve;
      }),
  });
  fill(page);

  submit(page);
  await waitFor(() => page.button.disabled, "the button to lock");
  assert.equal(page.button.textContent, "Logging in...");

  page.form.dispatchEvent(new page.window.Event("submit", { bubbles: true, cancelable: true }));
  assert.equal(page.calls.length, 1);

  finishLogin(wrongCredentials());
  await waitFor(() => bannerShown(page), "the error banner");
  assert.equal(page.button.disabled, false);
  assert.equal(page.button.textContent, "Log in");
});

test("native validation stops empty input before any request is made", async (t) => {
  const page = await openLoginPage(t, {});

  submit(page);
  assert.equal(page.form.noValidate, false);
  assert.equal(page.calls.length, 0);

  fill(page, { email: "not-an-email" });
  submit(page);
  assert.equal(page.fields.email.validity.typeMismatch, true);
  assert.equal(page.calls.length, 0);
});

test("fields let the browser fill in saved credentials", async (t) => {
  const page = await openLoginPage(t, {});

  assert.equal(page.fields.email.type, "email");
  assert.equal(page.fields.email.autocomplete, "email");
  assert.equal(page.fields.password.type, "password");
  assert.equal(page.fields.password.autocomplete, "current-password");
});
