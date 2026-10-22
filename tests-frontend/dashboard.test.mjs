import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM, VirtualConsole } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const dashboardHtml = readStatic("dashboard.html");
const apiScript = readStatic("js/api.js");
const guardScript = readStatic("js/guard.js");
const heatScript = readStatic("js/heat.js");
const dashboardScript = readStatic("js/dashboard.js");

const STATS_URL = "/api/v1/dashboard/stats";
const PROFILE_URL = "/api/v1/profile/me";

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const profile = () =>
  jsonResponse(200, {
    id: "u1",
    email: "ada@example.com",
    name: "Ada",
    created_at: "2026-10-22T10:00:00Z",
  });

function stats(overrides = {}) {
  return () =>
    jsonResponse(200, {
      total_interviews: 12,
      average_score: 6.8,
      best_topics: [
        { topic: "arrays", average_score: 8.9 },
        { topic: "recursion", average_score: 7.1 },
      ],
      weak_topics: [
        { topic: "concurrency", average_score: 3.2 },
        { topic: "generators", average_score: 4.5 },
      ],
      ...overrides,
    });
}

async function openDashboard(t, routes) {
  const requests = [];

  async function fetchImpl(url) {
    requests.push(url);
    assert.ok(routes[url], `unexpected request to ${url}`);
    return routes[url]();
  }

  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (error) => console.error(error));

  const dom = new JSDOM(dashboardHtml, {
    url: "http://localhost:8000/dashboard",
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
  window.eval(dashboardScript);

  if (window.document.readyState === "loading") {
    await new Promise((resolve) => {
      window.document.addEventListener("DOMContentLoaded", resolve, { once: true });
    });
  }

  const { document } = window;
  const $ = (selector) => document.querySelector(selector);
  const page = {
    requests,
    $,
    shown: (selector) => !$(selector).hidden,
    topics: (listId) =>
      [...document.querySelectorAll(`#${listId} .topic-item`)].map((item) => [
        item.querySelector(".topic-name").textContent,
        item.querySelector(".score-value").textContent,
      ]),
  };
  await waitFor(() => !page.shown("#dashboard-loading"), "the stats to load");
  return page;
}

async function waitFor(condition, description) {
  const deadline = Date.now() + 2000;
  while (!condition()) {
    if (Date.now() > deadline) assert.fail(`timed out waiting for ${description}`);
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
}

test("shows the totals, the average on the heat scale and both topic lists", async (t) => {
  const page = await openDashboard(t, { [STATS_URL]: stats(), [PROFILE_URL]: profile });

  assert.equal(page.shown("#dashboard-stats"), true);
  assert.equal(page.$("#total-interviews").textContent, "12");
  assert.equal(page.$("#average-score .score-value").textContent, "6.8");
  assert.equal(page.$("#average-score").dataset.heat, "6");
  assert.deepEqual(page.topics("best-topics"), [
    ["arrays", "8.9"],
    ["recursion", "7.1"],
  ]);
  assert.deepEqual(page.topics("weak-topics"), [
    ["concurrency", "3.2"],
    ["generators", "4.5"],
  ]);
  assert.equal(page.shown("#best-none"), false);
  assert.equal(page.shown("#weak-none"), false);
  assert.equal(page.shown("#dashboard-empty"), false);
});

test("greets the user by name", async (t) => {
  const page = await openDashboard(t, { [STATS_URL]: stats(), [PROFILE_URL]: profile });
  await waitFor(() => page.shown("#greeting"), "the greeting");

  assert.equal(page.$("#greeting").textContent, "Welcome back, Ada.");
});

test("still shows the stats when the profile can't be loaded", async (t) => {
  const page = await openDashboard(t, {
    [STATS_URL]: stats(),
    [PROFILE_URL]: () => jsonResponse(500, { detail: "boom" }),
  });

  assert.equal(page.shown("#dashboard-stats"), true);
  assert.equal(page.shown("#greeting"), false);
  assert.equal(page.shown("#form-error"), false);
});

test("does not list a topic as both strongest and weakest", async (t) => {
  const page = await openDashboard(t, {
    [STATS_URL]: stats({
      best_topics: [
        { topic: "arrays", average_score: 8 },
        { topic: "memory", average_score: 5 },
      ],
      weak_topics: [
        { topic: "memory", average_score: 5 },
        { topic: "arrays", average_score: 8 },
      ],
    }),
    [PROFILE_URL]: profile,
  });

  assert.deepEqual(page.topics("best-topics"), [
    ["arrays", "8.0"],
    ["memory", "5.0"],
  ]);
  assert.deepEqual(page.topics("weak-topics"), []);
  assert.equal(page.shown("#weak-none"), true);
});

test("explains empty topic lists instead of leaving blank cards", async (t) => {
  const page = await openDashboard(t, {
    [STATS_URL]: stats({ best_topics: [], weak_topics: [] }),
    [PROFILE_URL]: profile,
  });

  assert.equal(page.shown("#best-none"), true);
  assert.equal(page.shown("#weak-none"), true);
});

test("says so when finished interviews have no score", async (t) => {
  const page = await openDashboard(t, {
    [STATS_URL]: stats({
      total_interviews: 1,
      average_score: null,
      best_topics: [],
      weak_topics: [],
    }),
    [PROFILE_URL]: profile,
  });

  assert.equal(page.$("#average-score").hidden, true);
  assert.equal(page.shown("#average-none"), true);
});

test("invites a first interview when nothing is finished yet", async (t) => {
  const page = await openDashboard(t, {
    [STATS_URL]: stats({
      total_interviews: 0,
      average_score: null,
      best_topics: [],
      weak_topics: [],
    }),
    [PROFILE_URL]: profile,
  });

  assert.equal(page.shown("#dashboard-empty"), true);
  assert.equal(page.shown("#dashboard-stats"), false);
  assert.ok(page.$('#dashboard-empty a[href="/interview"]'));
});

test("renders topic names as text, not HTML", async (t) => {
  const page = await openDashboard(t, {
    [STATS_URL]: stats({ best_topics: [{ topic: "<b>bold</b>", average_score: 9 }] }),
    [PROFILE_URL]: profile,
  });

  assert.deepEqual(page.topics("best-topics"), [["<b>bold</b>", "9.0"]]);
  assert.equal(page.$("#best-topics b"), null);
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
  test(`explains ${failure.name} instead of showing empty stats`, async (t) => {
    const page = await openDashboard(t, { [STATS_URL]: failure.respond, [PROFILE_URL]: profile });

    assert.match(page.$("#form-error").textContent, failure.message);
    assert.equal(page.shown("#dashboard-stats"), false);
    assert.equal(page.shown("#dashboard-empty"), false);
  });
}
