import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM, VirtualConsole } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const apiScript = readStatic("js/api.js");
const guardScript = readStatic("js/guard.js");

const ACCESS_TOKEN_KEY = "skillforge_access_token";
const REFRESH_TOKEN_KEY = "skillforge_refresh_token";
const PROTECTED_PAGES = ["interview", "session", "history", "dashboard"];
const PUBLIC_PAGES = ["index", "register", "login"];

function openPage(t, name, storedTokens = {}) {
  const navigations = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (error) => {
    if (error.message.startsWith("Not implemented: navigation")) {
      navigations.push(error.message);
    } else {
      console.error(error);
    }
  });

  const dom = new JSDOM(readStatic(`${name}.html`), {
    url: `http://localhost:8000/${name}`,
    runScripts: "outside-only",
    virtualConsole,
  });
  const { window } = dom;
  t.after(() => window.close());

  for (const [key, value] of Object.entries(storedTokens)) {
    window.localStorage.setItem(key, value);
  }
  window.eval(apiScript);
  window.eval(guardScript);

  return { document: window.document, navigations };
}

const scriptSources = (scope) =>
  [...scope.querySelectorAll("script[src]")].map((script) => script.getAttribute("src"));

for (const name of PROTECTED_PAGES) {
  test(`${name} sends a visitor without a token away`, (t) => {
    const page = openPage(t, name);

    assert.equal(page.navigations.length, 1);
  });

  test(`${name} stays open for a logged-in user`, (t) => {
    const page = openPage(t, name, {
      [ACCESS_TOKEN_KEY]: "access-123",
      [REFRESH_TOKEN_KEY]: "refresh-456",
    });

    assert.equal(page.navigations.length, 0);
  });

  test(`${name} runs the guard in <head>, right after api.js`, (t) => {
    const { document } = openPage(t, name);

    assert.deepEqual(scriptSources(document.head), ["/static/js/api.js", "/static/js/guard.js"]);
    assert.equal(scriptSources(document).filter((src) => src.endsWith("/api.js")).length, 1);
  });
}

for (const name of PUBLIC_PAGES) {
  test(`${name} does not include the guard`, (t) => {
    const { document } = openPage(t, name);

    assert.equal(scriptSources(document).includes("/static/js/guard.js"), false);
  });
}

test("the guard sends visitors to /login", () => {
  assert.match(guardScript, /const LOGIN_URL = "\/login";/);
  assert.match(guardScript, /window\.location\.replace\(LOGIN_URL\)/);
});
