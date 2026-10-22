import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM, VirtualConsole } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const interviewHtml = readStatic("interview.html");
const apiScript = readStatic("js/api.js");
const guardScript = readStatic("js/guard.js");
const interviewScript = readStatic("js/interview.js");

const START_URL = "/api/v1/interviews";
const IN_PROGRESS_URL = "/api/v1/interviews?status=in_progress&page_size=1";
const ACCESS_TOKEN_KEY = "skillforge_access_token";
const REFRESH_TOKEN_KEY = "skillforge_refresh_token";
const OPEN_INTERVIEW_ID = "9c1f4e2a-7b3d-4c5e-8f6a-0b1c2d3e4f5a";

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const started = () =>
  jsonResponse(201, {
    id: "new-interview-1",
    language: "python",
    difficulty: "middle",
    status: "in_progress",
    current_question: { id: "q1", order_index: 1, topic: "gil", question: "Explain the GIL." },
  });
const alreadyInProgress = () =>
  jsonResponse(409, {
    detail: "You already have an interview in progress.",
    error_code: "INTERVIEW_ALREADY_IN_PROGRESS",
  });
const openInterviewList = () =>
  jsonResponse(200, {
    items: [
      {
        id: OPEN_INTERVIEW_ID,
        language: "java",
        difficulty: "senior",
        status: "in_progress",
        score: null,
        created_at: "2026-10-22T10:00:00Z",
        finished_at: null,
      },
    ],
    page: 1,
    page_size: 1,
    total: 1,
  });

async function openInterviewPage(t, routes) {
  const calls = [];
  const navigations = [];

  async function fetchImpl(url, init = {}) {
    calls.push({
      url,
      method: init.method,
      authorization: init.headers?.Authorization,
      body: init.body ? JSON.parse(init.body) : undefined,
    });
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

  const dom = new JSDOM(interviewHtml, {
    url: "http://localhost:8000/interview",
    runScripts: "outside-only",
    virtualConsole,
  });
  const { window } = dom;
  t.after(() => window.close());

  window.localStorage.setItem(ACCESS_TOKEN_KEY, "access-123");
  window.localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-456");
  window.fetch = fetchImpl;
  window.eval(apiScript);
  window.eval(guardScript);
  window.eval(interviewScript);

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
    form: document.querySelector("#start-form"),
    banner: document.querySelector("#form-error"),
    resumeNotice: document.querySelector("#resume-notice"),
    resumeLink: document.querySelector("#resume-link"),
    button: document.querySelector('button[type="submit"]'),
  };
}

function choose(page, { language = "python", difficulty = "middle" } = {}) {
  page.form.querySelector(`input[name="language"][value="${language}"]`).click();
  page.form.querySelector(`input[name="difficulty"][value="${difficulty}"]`).click();
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
const resumeShown = (page) => !page.resumeNotice.hidden;

test("starts an interview with the chosen language and level and leaves the page", async (t) => {
  const page = await openInterviewPage(t, { [START_URL]: started });
  choose(page, { language: "cpp", difficulty: "senior" });

  submit(page);
  await waitFor(() => page.navigations.length === 1, "the redirect to the session");

  assert.deepEqual(page.calls, [
    {
      url: START_URL,
      method: "POST",
      authorization: "Bearer access-123",
      body: { language: "cpp", difficulty: "senior" },
    },
  ]);
  assert.equal(page.banner.hidden, true);
  assert.equal(page.resumeNotice.hidden, true);
});

test("offers to continue the interview that is already in progress", async (t) => {
  const page = await openInterviewPage(t, {
    [START_URL]: alreadyInProgress,
    [IN_PROGRESS_URL]: openInterviewList,
  });
  choose(page);

  submit(page);
  await waitFor(() => resumeShown(page), "the resume notice");

  assert.equal(page.resumeLink.getAttribute("href"), `/interview/${OPEN_INTERVIEW_ID}`);
  assert.equal(page.window.document.activeElement, page.resumeLink);
  assert.deepEqual(
    page.calls.map((call) => [call.method, call.url]),
    [
      ["POST", START_URL],
      ["GET", IN_PROGRESS_URL],
    ],
  );
  assert.equal(page.banner.hidden, true);
  assert.equal(page.button.disabled, false);
  assert.equal(page.navigations.length, 0);
});

test("explains the conflict when the open interview cannot be loaded", async (t) => {
  const page = await openInterviewPage(t, {
    [START_URL]: alreadyInProgress,
    [IN_PROGRESS_URL]: () => Promise.reject(new TypeError("Failed to fetch")),
  });
  choose(page);

  submit(page);
  await waitFor(() => bannerShown(page), "the error banner");

  assert.match(page.banner.textContent, /already have an interview in progress/i);
  assert.equal(page.resumeNotice.hidden, true);
  assert.equal(page.button.disabled, false);
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
  test(`shows a clear message for ${failure.name} and lets the user retry`, async (t) => {
    const page = await openInterviewPage(t, { [START_URL]: failure.respond });
    choose(page);

    submit(page);
    await waitFor(() => bannerShown(page), "the error banner");

    assert.match(page.banner.textContent, failure.message);
    assert.equal(page.calls.length, 1);
    assert.equal(page.button.disabled, false);
    assert.equal(page.button.textContent, "Start interview");
    assert.equal(page.navigations.length, 0);
  });
}

test("hides the resume notice when the user tries again", async (t) => {
  let respond = alreadyInProgress;
  const page = await openInterviewPage(t, {
    [START_URL]: () => respond(),
    [IN_PROGRESS_URL]: openInterviewList,
  });
  choose(page);
  submit(page);
  await waitFor(() => resumeShown(page), "the resume notice");

  respond = started;
  submit(page);
  await waitFor(() => page.navigations.length === 1, "the redirect to the session");

  assert.equal(page.resumeNotice.hidden, true);
});

test("locks the button while the request is in flight and ignores a second submit", async (t) => {
  let finishStart;
  const page = await openInterviewPage(t, {
    [START_URL]: () =>
      new Promise((resolve) => {
        finishStart = resolve;
      }),
  });
  choose(page);

  submit(page);
  await waitFor(() => page.button.disabled, "the button to lock");
  assert.equal(page.button.textContent, "Starting...");

  page.form.dispatchEvent(new page.window.Event("submit", { bubbles: true, cancelable: true }));
  assert.equal(page.calls.length, 1);

  finishStart(jsonResponse(500, { detail: "boom" }));
  await waitFor(() => bannerShown(page), "the error banner");
  assert.equal(page.button.disabled, false);
  assert.equal(page.button.textContent, "Start interview");
});

test("native validation asks for both a language and a level before any request", async (t) => {
  const page = await openInterviewPage(t, {});

  submit(page);
  assert.equal(page.calls.length, 0);

  page.form.querySelector('input[name="language"][value="python"]').click();
  submit(page);
  assert.equal(page.calls.length, 0);
  assert.equal(page.form.elements.difficulty[0].validity.valueMissing, true);
});

test("offers exactly the languages and levels the API accepts", async (t) => {
  const page = await openInterviewPage(t, {});
  const values = (name) =>
    [...page.form.querySelectorAll(`input[name="${name}"]`)].map((input) => input.value);

  assert.deepEqual(values("language"), ["python", "java", "cpp", "javascript"]);
  assert.deepEqual(values("difficulty"), ["junior", "middle", "senior"]);
});
