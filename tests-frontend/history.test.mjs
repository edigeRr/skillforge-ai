import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM, VirtualConsole } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const historyHtml = readStatic("history.html");
const apiScript = readStatic("js/api.js");
const guardScript = readStatic("js/guard.js");
const heatScript = readStatic("js/heat.js");
const historyScript = readStatic("js/history.js");

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function summary(index, overrides = {}) {
  return {
    id: `interview-${index}`,
    language: "python",
    difficulty: "middle",
    status: "completed",
    score: 7.5,
    created_at: "2026-10-22T10:00:00Z",
    finished_at: "2026-10-22T10:20:00Z",
    ...overrides,
  };
}

function pageOf(items, { page = 1, page_size = 10, total = items.length } = {}) {
  return jsonResponse(200, { items, page, page_size, total });
}

async function openHistoryPage(t, respond, { search = "" } = {}) {
  const requests = [];

  async function fetchImpl(url) {
    const parsed = new URL(url, "http://localhost:8000");
    assert.equal(parsed.pathname, "/api/v1/interviews");
    const params = Object.fromEntries(parsed.searchParams);
    requests.push(params);
    return respond(params, requests.length);
  }

  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (error) => console.error(error));

  const dom = new JSDOM(historyHtml, {
    url: `http://localhost:8000/history${search}`,
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
  window.eval(heatScript);
  window.eval(historyScript);

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
    items: () => [...document.querySelectorAll("#history-list > li")],
    shown: (selector) => !$(selector).hidden,
    choose(name, value) {
      const select = $(`#filter-${name}`);
      select.value = value;
      select.dispatchEvent(new window.Event("change", { bubbles: true }));
    },
  };
  await waitFor(() => !page.$("#history-list").hasAttribute("aria-busy"), "the first load");
  return page;
}

async function waitFor(condition, description) {
  const deadline = Date.now() + 2000;
  while (!condition()) {
    if (Date.now() > deadline) assert.fail(`timed out waiting for ${description}`);
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
}

const settled = (page, count) => () =>
  page.requests.length >= count && !page.$("#history-list").hasAttribute("aria-busy");

test("loads the first page and links every interview to its session page", async (t) => {
  const page = await openHistoryPage(t, () =>
    pageOf([summary(1, { language: "cpp", difficulty: "senior" }), summary(2)]),
  );

  assert.deepEqual(page.requests, [{ page: "1", page_size: "10" }]);
  const [first] = page.items();
  assert.equal(first.querySelector("a").getAttribute("href"), "/interview/interview-1");
  assert.equal(first.querySelector(".history-title").textContent, "C++ · Senior");
  assert.equal(first.querySelector("time").getAttribute("datetime"), "2026-10-22T10:00:00Z");
  assert.match(first.querySelector("time").textContent, /2026/);
  assert.equal(page.shown("#history-loading"), false);
  assert.equal(page.shown("#pagination"), false);
});

test("shows a score on the heat scale, or the status when there is no score", async (t) => {
  const page = await openHistoryPage(t, () =>
    pageOf([
      summary(1, { score: 9.2 }),
      summary(2, { status: "in_progress", score: null, finished_at: null }),
      summary(3, { score: null }),
    ]),
  );
  const [scored, open, unscored] = page.items();

  assert.equal(scored.querySelector(".score-value").textContent, "9.2");
  assert.equal(scored.querySelector(".score").dataset.heat, "8");
  assert.equal(open.querySelector(".history-status").textContent, "In progress · Continue");
  assert.equal(open.querySelector(".score"), null);
  assert.equal(unscored.querySelector(".history-status").textContent, "Completed · No score");
});

test("invites a first interview when there is no history at all", async (t) => {
  const page = await openHistoryPage(t, () => pageOf([]));

  assert.equal(page.shown("#history-empty"), true);
  assert.equal(page.shown("#history-no-match"), false);
  assert.equal(page.items().length, 0);
});

test("filters reset to page 1 and show up in the address bar", async (t) => {
  const page = await openHistoryPage(t, (params) =>
    pageOf([summary(1)], { page: Number(params.page), total: 30 }),
  );
  page.$("#next-page").click();
  await waitFor(settled(page, 2), "page 2");

  page.choose("language", "java");
  await waitFor(settled(page, 3), "the filtered list");

  assert.deepEqual(page.requests.at(-1), { page: "1", page_size: "10", language: "java" });
  assert.equal(page.window.location.search, "?language=java");
});

test("offers to clear filters that match nothing", async (t) => {
  const page = await openHistoryPage(
    t,
    (params) => (params.status ? pageOf([]) : pageOf([summary(1)])),
    { search: "?status=abandoned" },
  );

  assert.equal(page.shown("#history-no-match"), true);
  assert.equal(page.shown("#history-empty"), false);

  page.$("#clear-filters").click();
  await waitFor(settled(page, 2), "the unfiltered list");

  assert.deepEqual(page.requests.at(-1), { page: "1", page_size: "10" });
  assert.equal(page.$("#filter-status").value, "");
  assert.equal(page.window.location.search, "");
  assert.equal(page.items().length, 1);
});

test("pages through the list with Previous and Next", async (t) => {
  const page = await openHistoryPage(t, (params) =>
    pageOf([summary(Number(params.page))], { page: Number(params.page), total: 25 }),
  );

  assert.equal(page.shown("#pagination"), true);
  assert.equal(page.$("#page-status").textContent, "Page 1 of 3");
  assert.equal(page.$("#prev-page").disabled, true);

  page.$("#next-page").click();
  await waitFor(settled(page, 2), "page 2");
  assert.equal(page.requests.at(-1).page, "2");
  assert.equal(page.window.location.search, "?page=2");
  assert.equal(page.$("#prev-page").disabled, false);

  page.$("#next-page").click();
  await waitFor(settled(page, 3), "page 3");
  assert.equal(page.$("#page-status").textContent, "Page 3 of 3");
  assert.equal(page.$("#next-page").disabled, true);
});

test("restores filters and page from the address bar", async (t) => {
  const page = await openHistoryPage(t, () => pageOf([summary(1)], { page: 2, total: 15 }), {
    search: "?language=java&status=completed&page=2",
  });

  assert.deepEqual(page.requests[0], {
    page: "2",
    page_size: "10",
    language: "java",
    status: "completed",
  });
  assert.equal(page.$("#filter-language").value, "java");
  assert.equal(page.$("#filter-status").value, "completed");
});

test("drops values from the address bar that the API would reject", async (t) => {
  const page = await openHistoryPage(t, () => pageOf([summary(1)]), {
    search: "?language=rust&difficulty=expert&page=-3",
  });

  assert.deepEqual(page.requests[0], { page: "1", page_size: "10" });
  assert.equal(page.window.location.search, "");
});

test("falls back to the last page when the address asks for one past the end", async (t) => {
  const page = await openHistoryPage(
    t,
    (params) =>
      pageOf(Number(params.page) === 2 ? [summary(11)] : [], {
        page: Number(params.page),
        total: 11,
      }),
    { search: "?page=9" },
  );
  await waitFor(settled(page, 2), "the last page");

  assert.equal(page.requests.at(-1).page, "2");
  assert.equal(page.window.location.search, "?page=2");
  assert.equal(page.items().length, 1);
  assert.equal(page.shown("#history-empty"), false);
});

const FAILURES = [
  {
    name: "rate limiting",
    respond: () => jsonResponse(429, { detail: "Too many requests", error_code: "RATE_LIMITED" }),
    message: /too many requests/i,
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
  test(`explains ${failure.name} instead of showing an empty history`, async (t) => {
    const page = await openHistoryPage(t, failure.respond);

    assert.match(page.$("#form-error").textContent, failure.message);
    assert.equal(page.shown("#form-error"), true);
    assert.equal(page.shown("#history-loading"), false);
    assert.equal(page.shown("#history-empty"), false);
  });
}

test("ignores an older response that arrives after a newer one", async (t) => {
  let releaseFirst;
  const page = await openHistoryPage(t, (params, count) => {
    if (count === 2) {
      return new Promise((resolve) => {
        releaseFirst = () => resolve(pageOf([summary("slow", { language: "java" })]));
      });
    }
    return pageOf([summary(count, { language: params.language || "python" })]);
  });

  page.choose("language", "java");
  page.choose("language", "cpp");
  await waitFor(
    () => page.requests.length === 3 && page.items()[0]?.textContent.includes("C++"),
    "the cpp list",
  );

  releaseFirst();
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.match(page.items()[0].querySelector(".history-title").textContent, /^C\+\+/);
});
