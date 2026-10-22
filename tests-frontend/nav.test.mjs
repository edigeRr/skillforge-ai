import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const apiScript = readStatic("js/api.js");
const navScript = readStatic("js/nav.js");
const pagesWithNav = readdirSync(staticDir).filter(
  (name) => name.endsWith(".html") && readStatic(name).includes('class="site-nav"'),
);

const base64url = (data) => Buffer.from(JSON.stringify(data)).toString("base64url");
const tokenWithRole = (role) =>
  `${base64url({ alg: "HS256" })}.${base64url({ sub: "user-1", role, type: "access" })}.sig`;

async function openPage(t, accessToken) {
  const dom = new JSDOM(readStatic("404.html"), {
    url: "http://localhost:8000/somewhere",
    runScripts: "outside-only",
  });
  const { window } = dom;
  t.after(() => window.close());

  if (accessToken) {
    window.localStorage.setItem("skillforge_access_token", accessToken);
    window.localStorage.setItem("skillforge_refresh_token", "refresh-456");
  }
  window.eval(apiScript);
  window.eval(navScript);

  if (window.document.readyState === "loading") {
    await new Promise((resolve) => {
      window.document.addEventListener("DOMContentLoaded", resolve, { once: true });
    });
  }
  return window;
}

const adminLink = (window) => window.document.querySelector('a[data-auth="admin"]');

test("every page with a nav has an Admin link that starts hidden", () => {
  assert.ok(pagesWithNav.length >= 9);
  for (const name of pagesWithNav) {
    const { document } = new JSDOM(readStatic(name)).window;
    const link = document.querySelector('.nav-links a[data-auth="admin"]');
    assert.ok(link, `${name} has no Admin link`);
    assert.equal(link.getAttribute("href"), "/admin", name);
    assert.equal(link.hidden, true, `${name} shows the Admin link before nav.js runs`);
  }
});

test("shows the Admin link when the access token says admin", async (t) => {
  const window = await openPage(t, tokenWithRole("admin"));

  assert.equal(window.SkillForge.getRole(), "admin");
  assert.equal(adminLink(window).hidden, false);
});

test("keeps the Admin link hidden for other roles", async (t) => {
  const window = await openPage(t, tokenWithRole("user"));

  assert.equal(window.SkillForge.getRole(), "user");
  assert.equal(adminLink(window).hidden, true);
});

test("keeps the Admin link hidden when the token can't be read", async (t) => {
  const window = await openPage(t, "not-a-jwt");

  assert.equal(window.SkillForge.getRole(), null);
  assert.equal(adminLink(window).hidden, true);
});

test("keeps the Admin link hidden when logged out", async (t) => {
  const window = await openPage(t, null);

  assert.equal(window.SkillForge.getRole(), null);
  assert.equal(adminLink(window).hidden, true);
});
