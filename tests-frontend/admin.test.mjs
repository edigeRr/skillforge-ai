import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM, VirtualConsole } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const adminHtml = readStatic("admin.html");
const apiScript = readStatic("js/api.js");
const guardScript = readStatic("js/guard.js");
const adminScript = readStatic("js/admin.js");

const ME = "user-me";

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function account(id, overrides = {}) {
  return {
    id,
    email: `${id}@example.com`,
    name: `Name ${id}`,
    role: "user",
    created_at: "2026-10-22T10:00:00Z",
    ...overrides,
  };
}

function apiError(status, errorCode, detail = "Request failed.") {
  return jsonResponse(status, { detail, error_code: errorCode });
}

function pageOf(items, { page = 1, page_size = 20, total = items.length } = {}) {
  return jsonResponse(200, { items, page, page_size, total });
}

const defaultAccounts = () => [account("user-2"), account(ME, { role: "admin" })];

async function openAdminPage(t, routes = {}) {
  const requests = [];

  async function fetchImpl(url, options = {}) {
    const parsed = new URL(url, "http://localhost:8000");
    const method = options.method || "GET";
    const body = options.body ? JSON.parse(options.body) : undefined;
    const query = Object.fromEntries(parsed.searchParams);
    const request = { method, path: parsed.pathname, query, body };
    requests.push(request);

    if (method === "GET" && parsed.pathname === "/api/v1/profile/me") {
      return (routes.me || (() => jsonResponse(200, account(ME, { role: "admin" }))))(request);
    }
    if (method === "GET" && parsed.pathname === "/api/v1/admin/users") {
      return (routes.list || (() => pageOf(defaultAccounts())))(request);
    }
    if (method === "POST" && parsed.pathname === "/api/v1/admin/users") {
      return routes.create(request);
    }
    if (method === "PATCH") {
      return routes.patch(request);
    }
    assert.fail(`unexpected request ${method} ${parsed.pathname}`);
  }

  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (error) => console.error(error));

  const dom = new JSDOM(adminHtml, {
    url: "http://localhost:8000/admin",
    runScripts: "outside-only",
    virtualConsole,
  });
  const { window } = dom;
  t.after(() => window.close());

  window.localStorage.setItem("skillforge_access_token", "access-123");
  window.localStorage.setItem("skillforge_refresh_token", "refresh-456");
  window.fetch = fetchImpl;
  window.eval(apiScript);
  window.eval(guardScript);
  window.eval(adminScript);

  if (window.document.readyState === "loading") {
    await new Promise((resolve) => {
      window.document.addEventListener("DOMContentLoaded", resolve, { once: true });
    });
  }

  const { document } = window;
  const $ = (selector) => document.querySelector(selector);
  const page = {
    window,
    requests,
    $,
    shown: (selector) => !$(selector).hidden,
    cards: () => [...document.querySelectorAll("#admin-users > li")],
    card: (id) => $(`#admin-users > li[data-user-id="${id}"]`),
    listRequests: () =>
      requests.filter((r) => r.path === "/api/v1/admin/users" && r.method === "GET"),
    pick(id, role) {
      const select = page.card(id).querySelector("select");
      select.value = role;
      select.dispatchEvent(new window.Event("change", { bubbles: true }));
    },
    fill(values) {
      for (const [name, value] of Object.entries(values)) {
        $(`#new-${name}`).value = value;
      }
    },
    submit() {
      const event = new window.Event("submit", { bubbles: true, cancelable: true });
      $("#create-form").dispatchEvent(event);
    },
  };
  await waitFor(() => !page.shown("#admin-loading"), "the first load");
  return page;
}

async function waitFor(condition, description) {
  const deadline = Date.now() + 2000;
  while (!condition()) {
    if (Date.now() > deadline) assert.fail(`timed out waiting for ${description}`);
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
}

test("lists accounts and gives every other account a role picker", async (t) => {
  const page = await openAdminPage(t);

  assert.deepEqual(page.listRequests()[0].query, { page: "1", page_size: "20" });
  assert.equal(page.shown("#admin-content"), true);
  assert.equal(page.shown("#admin-denied"), false);
  assert.equal(page.cards().length, 2);

  const other = page.card("user-2");
  assert.equal(other.querySelector(".admin-user-name").textContent, "Name user-2");
  const meta = other.querySelector(".admin-user-meta").textContent;
  assert.match(meta, /^user-2@example\.com · joined /);
  const select = other.querySelector("select");
  assert.equal(select.value, "user");
  assert.equal(select.getAttribute("aria-label"), "Role for user-2@example.com");
  assert.equal(other.querySelector("button").disabled, true);

  const mine = page.card(ME);
  assert.equal(mine.querySelector("select"), null);
  assert.equal(mine.querySelector(".admin-role-fixed").textContent, "Admin · you");
  assert.equal(page.shown("#pagination"), false);
});

test("shows the not-for-you message to accounts without the admin role", async (t) => {
  const page = await openAdminPage(t, {
    list: () => apiError(403, "ADMIN_REQUIRED"),
  });

  assert.equal(page.shown("#admin-denied"), true);
  assert.equal(page.shown("#admin-content"), false);
  assert.equal(page.shown("#form-error"), false);
});

test("saves a changed role and confirms it", async (t) => {
  const page = await openAdminPage(t, {
    patch: ({ body }) => jsonResponse(200, account("user-2", { role: body.role })),
  });
  const save = page.card("user-2").querySelector("button");

  page.pick("user-2", "admin");
  assert.equal(save.disabled, false);
  page.pick("user-2", "user");
  assert.equal(save.disabled, true);

  page.pick("user-2", "admin");
  save.click();
  await waitFor(() => page.$("#admin-status").textContent !== "", "the confirmation");

  const patch = page.requests.find((r) => r.method === "PATCH");
  assert.equal(patch.path, "/api/v1/admin/users/user-2/role");
  assert.deepEqual(patch.body, { role: "admin" });
  assert.equal(page.$("#admin-status").textContent, "user-2@example.com is now Admin.");
  assert.equal(save.disabled, true);
  assert.equal(save.textContent, "Save");
});

test("puts the old role back when saving fails", async (t) => {
  const page = await openAdminPage(t, {
    patch: () => apiError(429, "TOO_MANY_ATTEMPTS"),
  });
  const select = page.card("user-2").querySelector("select");

  page.pick("user-2", "admin");
  page.card("user-2").querySelector("button").click();
  await waitFor(() => page.shown("#form-error"), "the error");

  assert.equal(
    page.$("#form-error").textContent,
    "Too many requests - wait a minute and try again.",
  );
  assert.equal(select.value, "user");
  assert.equal(select.disabled, false);
});

test("reloads the list when the account was deleted meanwhile", async (t) => {
  const page = await openAdminPage(t, {
    patch: () => apiError(404, "USER_NOT_FOUND"),
  });

  page.pick("user-2", "admin");
  page.card("user-2").querySelector("button").click();
  await waitFor(() => page.listRequests().length === 2, "the reload");

  assert.equal(page.$("#form-error").textContent, "That account no longer exists.");
});

test("creates an account, clears the form and reloads the first page", async (t) => {
  const page = await openAdminPage(t, {
    create: ({ body }) =>
      jsonResponse(201, account("user-3", { email: body.email, role: body.role })),
  });

  page.fill({
    name: "  Nia New ",
    email: " nia@example.com ",
    password: "Str0ngPass1",
    role: "admin",
  });
  page.submit();
  await waitFor(() => page.listRequests().length === 2, "the reload");

  const create = page.requests.find((r) => r.method === "POST");
  assert.deepEqual(create.body, {
    name: "Nia New",
    email: "nia@example.com",
    password: "Str0ngPass1",
    role: "admin",
  });
  assert.equal(page.$("#admin-status").textContent, "Created nia@example.com as Admin.");
  assert.equal(page.$("#new-email").value, "");
  assert.equal(page.$("#new-role").value, "user");
  assert.equal(page.listRequests()[1].query.page, "1");
});

test("marks the email field when the address is taken", async (t) => {
  const page = await openAdminPage(t, {
    create: () => apiError(409, "EMAIL_ALREADY_EXISTS"),
  });

  page.fill({ name: "Dup", email: "user-2@example.com", password: "Str0ngPass1" });
  page.submit();
  await waitFor(() => page.shown("#create-error"), "the error");

  assert.equal(
    page.$("#create-error").textContent,
    "An account with that email already exists.",
  );
  assert.equal(page.$("#new-email").getAttribute("aria-invalid"), "true");
  assert.equal(page.$("#create-form button[type=submit]").disabled, false);
  assert.equal(page.$("#new-email").value, "user-2@example.com");
});

test("marks the field the API rejects", async (t) => {
  const page = await openAdminPage(t, {
    create: () =>
      jsonResponse(422, { detail: [{ loc: ["body", "password"], msg: "needs a digit" }] }),
  });

  page.fill({ name: "Nia", email: "nia@example.com", password: "onlyletters" });
  page.submit();
  await waitFor(() => page.shown("#create-error"), "the error");

  assert.match(page.$("#create-error").textContent, /^A password needs 8\+ characters/);
  assert.equal(page.$("#new-password").getAttribute("aria-invalid"), "true");
  assert.equal(page.$("#new-email").hasAttribute("aria-invalid"), false);
});

test("pages through accounts", async (t) => {
  const page = await openAdminPage(t, {
    list: ({ query }) =>
      pageOf([account(`user-p${query.page}`)], { page: Number(query.page), total: 25 }),
  });

  assert.equal(page.shown("#pagination"), true);
  assert.equal(page.$("#page-status").textContent, "Page 1 of 2");
  assert.equal(page.$("#prev-page").disabled, true);

  page.$("#next-page").click();
  await waitFor(() => page.$("#page-status").textContent === "Page 2 of 2", "page 2");

  assert.equal(page.listRequests()[1].query.page, "2");
  assert.equal(page.$("#next-page").disabled, true);
  assert.ok(page.card("user-p2"));
});
