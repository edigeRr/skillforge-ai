import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM, VirtualConsole } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const registerHtml = readStatic("register.html");
const apiScript = readStatic("js/api.js");
const registerScript = readStatic("js/register.js");

const REGISTER_URL = "/api/v1/auth/register";
const LOGIN_URL = "/api/v1/auth/login";
const ACCESS_TOKEN_KEY = "skillforge_access_token";
const REFRESH_TOKEN_KEY = "skillforge_refresh_token";

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const createdUser = () => jsonResponse(201, { id: "u1", email: "ada@example.com", name: "Ada" });
const tokens = () =>
  jsonResponse(200, {
    access_token: "access-123",
    refresh_token: "refresh-456",
    token_type: "bearer",
    expires_in: 1800,
  });
const duplicateEmail = () =>
  jsonResponse(409, { detail: "Email already registered", error_code: "EMAIL_ALREADY_EXISTS" });
const serverError = () => jsonResponse(500, { detail: "boom", error_code: "INTERNAL_ERROR" });

async function openRegisterPage(t, routes) {
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

  const dom = new JSDOM(registerHtml, {
    url: "http://localhost:8000/register",
    runScripts: "outside-only",
    virtualConsole,
  });
  const { window } = dom;
  t.after(() => window.close());

  window.fetch = fetchImpl;
  window.eval(apiScript);
  window.eval(registerScript);

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
    form: document.querySelector("#register-form"),
    banner: document.querySelector("#form-error"),
    button: document.querySelector('button[type="submit"]'),
    fields: {
      name: document.querySelector("#name"),
      email: document.querySelector("#email"),
      password: document.querySelector("#password"),
    },
  };
}

function fill(page, { name = "Ada Lovelace", email = "ada@example.com", password = "Str0ngPass1" } = {}) {
  page.fields.name.value = name;
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

test("creates the account, logs in, stores the tokens and leaves the page", async (t) => {
  const page = await openRegisterPage(t, { [REGISTER_URL]: createdUser, [LOGIN_URL]: tokens });
  fill(page, { name: "  Ada Lovelace  " });

  submit(page);
  await waitFor(() => page.navigations.length === 1, "the redirect after sign-up");

  assert.deepEqual(page.calls, [
    {
      url: REGISTER_URL,
      method: "POST",
      body: { email: "ada@example.com", password: "Str0ngPass1", name: "Ada Lovelace" },
    },
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

test("explains a duplicate email, marks the field and does not try to log in", async (t) => {
  const page = await openRegisterPage(t, { [REGISTER_URL]: duplicateEmail });
  fill(page);

  submit(page);
  await waitFor(() => bannerShown(page), "the error banner");

  assert.match(page.banner.textContent, /already exists/i);
  assert.equal(page.calls.length, 1);
  assert.ok(page.fields.email.classList.contains("is-invalid"));
  assert.equal(page.fields.email.getAttribute("aria-invalid"), "true");
  assert.equal(page.window.document.activeElement, page.fields.email);
  assert.equal(page.button.disabled, false);
  assert.equal(page.button.textContent, "Create account");
  assert.equal(storedAccessToken(page), null);
  assert.equal(page.navigations.length, 0);
});

test("clears the invalid mark as soon as the user edits the field", async (t) => {
  const page = await openRegisterPage(t, { [REGISTER_URL]: duplicateEmail });
  fill(page);
  submit(page);
  await waitFor(() => bannerShown(page), "the error banner");

  page.fields.email.dispatchEvent(new page.window.Event("input", { bubbles: true }));

  assert.equal(page.fields.email.classList.contains("is-invalid"), false);
  assert.equal(page.fields.email.hasAttribute("aria-invalid"), false);
});

const fieldRejected = (...fields) => () =>
  jsonResponse(422, { detail: fields.map((field) => ({ loc: ["body", field], msg: "bad" })) });

const FIELD_ERRORS = [
  { field: "email", message: /^That email address doesn't look right/ },
  { field: "password", message: /^A password needs 8\+ characters/ },
  { field: "name", message: /^Please enter your name\.$/ },
];

for (const { field, message } of FIELD_ERRORS) {
  test(`marks the ${field} field when the API rejects it`, async (t) => {
    const page = await openRegisterPage(t, { [REGISTER_URL]: fieldRejected(field) });
    fill(page);

    submit(page);
    await waitFor(() => bannerShown(page), "the error banner");

    assert.match(page.banner.textContent, message);
    assert.equal(page.fields[field].getAttribute("aria-invalid"), "true");
    assert.equal(page.window.document.activeElement, page.fields[field]);
    for (const other of Object.keys(page.fields).filter((name) => name !== field)) {
      assert.equal(page.fields[other].hasAttribute("aria-invalid"), false, other);
    }
  });
}

test("marks the first rejected field in form order", async (t) => {
  const page = await openRegisterPage(t, { [REGISTER_URL]: fieldRejected("password", "email") });
  fill(page);

  submit(page);
  await waitFor(() => bannerShown(page), "the error banner");

  assert.equal(page.fields.email.getAttribute("aria-invalid"), "true");
  assert.equal(page.fields.password.hasAttribute("aria-invalid"), false);
});

const FAILURES = [
  {
    name: "validation errors",
    respond: () => jsonResponse(422, { detail: [{ loc: ["body"], msg: "invalid JSON" }] }),
    message: /^Please check your details/,
  },
  {
    name: "rate limiting",
    respond: () =>
      jsonResponse(429, { detail: "Too many attempts", error_code: "TOO_MANY_ATTEMPTS" }),
    message: /too many attempts/i,
  },
  { name: "server errors", respond: serverError, message: /something went wrong/i },
  {
    name: "a network failure",
    respond: () => Promise.reject(new TypeError("Failed to fetch")),
    message: /can't reach the server/i,
  },
];

for (const failure of FAILURES) {
  test(`shows a clear message for ${failure.name} and lets the user retry`, async (t) => {
    const page = await openRegisterPage(t, { [REGISTER_URL]: failure.respond });
    fill(page);

    submit(page);
    await waitFor(() => bannerShown(page), "the error banner");

    assert.match(page.banner.textContent, failure.message);
    assert.equal(page.calls.length, 1);
    assert.equal(page.button.disabled, false);
    assert.equal(storedAccessToken(page), null);
    assert.equal(page.navigations.length, 0);
  });
}

test("says the account exists when only the automatic log-in fails", async (t) => {
  const page = await openRegisterPage(t, { [REGISTER_URL]: createdUser, [LOGIN_URL]: serverError });
  fill(page);

  submit(page);
  await waitFor(() => bannerShown(page), "the error banner");

  assert.match(page.banner.textContent, /account was created/i);
  assert.equal(page.calls.length, 2);
  assert.equal(page.button.disabled, false);
  assert.equal(storedAccessToken(page), null);
  assert.equal(page.navigations.length, 0);
});

test("locks the button while the request is in flight and ignores a second submit", async (t) => {
  let finishRegister;
  const page = await openRegisterPage(t, {
    [REGISTER_URL]: () =>
      new Promise((resolve) => {
        finishRegister = resolve;
      }),
  });
  fill(page);

  submit(page);
  await waitFor(() => page.button.disabled, "the button to lock");
  assert.equal(page.button.textContent, "Creating account...");

  page.form.dispatchEvent(new page.window.Event("submit", { bubbles: true, cancelable: true }));
  assert.equal(page.calls.length, 1);

  finishRegister(duplicateEmail());
  await waitFor(() => bannerShown(page), "the error banner");
  assert.equal(page.button.disabled, false);
  assert.equal(page.button.textContent, "Create account");
});

test("native validation stops empty and blank input before any request is made", async (t) => {
  const page = await openRegisterPage(t, {});

  submit(page);
  assert.equal(page.form.noValidate, false);
  assert.equal(page.calls.length, 0);

  fill(page, { name: "   " });
  submit(page);
  assert.equal(page.fields.name.validity.patternMismatch, true);
  assert.equal(page.calls.length, 0);
});

test("field limits match the API schema", async (t) => {
  const page = await openRegisterPage(t, {});

  assert.equal(page.fields.password.minLength, 8);
  assert.equal(page.fields.password.maxLength, 72);
  assert.equal(page.fields.name.maxLength, 100);
  assert.equal(page.fields.email.type, "email");
  assert.equal(page.fields.password.autocomplete, "new-password");
});
