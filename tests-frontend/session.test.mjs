import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { JSDOM, VirtualConsole } from "jsdom";

const staticDir = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const readStatic = (relativePath) => readFileSync(join(staticDir, relativePath), "utf8");

const sessionHtml = readStatic("session.html");
const apiScript = readStatic("js/api.js");
const guardScript = readStatic("js/guard.js");
const heatScript = readStatic("js/heat.js");
const sessionScript = readStatic("js/session.js");

const INTERVIEW_ID = "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b";
const DETAIL_URL = `/api/v1/interviews/${INTERVIEW_ID}`;
const ANSWER_URL = `${DETAIL_URL}/answer`;
const FINISH_URL = `${DETAIL_URL}/finish`;

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function question(index, overrides = {}) {
  return {
    id: `q${index + 1}`,
    order_index: index,
    topic: `topic-${index + 1}`,
    question: `Question text ${index + 1}?`,
    answer: null,
    feedback: null,
    score: null,
    ...overrides,
  };
}

function interview(overrides = {}) {
  return {
    id: INTERVIEW_ID,
    language: "python",
    difficulty: "middle",
    status: "in_progress",
    score: null,
    created_at: "2026-10-22T10:00:00Z",
    finished_at: null,
    questions: [
      question(0, { answer: "Earlier answer", feedback: "Fine.", score: 5 }),
      question(1),
    ],
    ...overrides,
  };
}

const completedInterview = (overrides = {}) =>
  interview({
    status: "completed",
    score: 6.5,
    finished_at: "2026-10-22T10:20:00Z",
    questions: [
      question(0, { answer: "First answer", feedback: "Fine.", score: 5 }),
      question(1, { answer: "<img src=x onerror=alert(1)>", feedback: "Great.", score: 8 }),
      question(2),
    ],
    ...overrides,
  });

const scored = (overrides = {}) =>
  jsonResponse(200, {
    feedback: "Solid, well-developed answer.",
    score: 7.5,
    next_question: { id: "q3", order_index: 2, topic: "topic-3", question: "Question text 3?" },
    interview_status: "in_progress",
    ...overrides,
  });

async function openSessionPage(t, routes, { confirm = () => true } = {}) {
  const calls = [];
  const navigations = [];

  async function fetchImpl(url, init = {}) {
    calls.push({ url, method: init.method, body: init.body ? JSON.parse(init.body) : undefined });
    const route = routes[`${init.method} ${url}`];
    assert.ok(route, `unexpected request to ${init.method} ${url}`);
    return route();
  }

  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (error) => {
    if (error.message.startsWith("Not implemented: navigation")) {
      navigations.push(error.message);
    } else {
      console.error(error);
    }
  });

  const dom = new JSDOM(sessionHtml, {
    url: `http://localhost:8000/interview/${INTERVIEW_ID}`,
    runScripts: "outside-only",
    virtualConsole,
  });
  const { window } = dom;
  t.after(() => window.close());

  window.localStorage.setItem("skillforge_access_token", "access-123");
  window.localStorage.setItem("skillforge_refresh_token", "refresh-456");
  window.fetch = fetchImpl;
  window.confirm = confirm;
  window.eval(apiScript);
  window.eval(guardScript);
  window.eval(heatScript);
  window.eval(sessionScript);

  if (window.document.readyState === "loading") {
    await new Promise((resolve) => {
      window.document.addEventListener("DOMContentLoaded", resolve, { once: true });
    });
  }

  const { document } = window;
  const $ = (selector) => document.querySelector(selector);
  return {
    window,
    document,
    calls,
    navigations,
    $,
    visible: (id) => !$(`#${id}`).hidden,
    banner: $("#form-error"),
    form: $("#answer-form"),
    answer: $("#answer"),
    submitButton: $('#answer-form button[type="submit"]'),
    finishButton: $("#finish-button"),
    nextButton: $("#next-button"),
  };
}

async function waitFor(condition, description) {
  const deadline = Date.now() + 2000;
  while (!condition()) {
    if (Date.now() > deadline) assert.fail(`timed out waiting for ${description}`);
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
}

const bannerShown = (page) => !page.banner.hidden;

async function openOnQuestion(t, extraRoutes = {}, options) {
  const page = await openSessionPage(
    t,
    { [`GET ${DETAIL_URL}`]: () => jsonResponse(200, interview()), ...extraRoutes },
    options,
  );
  await waitFor(() => page.visible("question-view"), "the question");
  return page;
}

function answerWith(page, text) {
  page.answer.value = text;
  page.form.requestSubmit();
}

test("opens on the first unanswered question of an interview in progress", async (t) => {
  const page = await openOnQuestion(t);

  assert.equal(page.$("#session-meta").textContent, "Python · Middle");
  assert.equal(page.$("#question-number").textContent, "Question 2");
  assert.equal(page.$("#question-topic").textContent, "topic-2");
  assert.equal(page.$("#question-text").textContent, "Question text 2?");
  assert.equal(page.visible("loading-view"), false);
  assert.equal(page.document.activeElement, page.answer);
});

test("sends the trimmed answer and shows the score on the heat scale", async (t) => {
  const page = await openOnQuestion(t, { [`POST ${ANSWER_URL}`]: () => scored() });

  answerWith(page, "  Threads share the GIL.  ");
  await waitFor(() => page.visible("result-view"), "the result");

  assert.deepEqual(page.calls.at(-1).body, { question_id: "q2", answer: "Threads share the GIL." });
  const score = page.$("#result-score");
  assert.equal(score.querySelector(".score-value").textContent, "7.5");
  assert.equal(score.dataset.heat, "6");
  assert.equal(score.querySelector(".score-fill").style.background, "var(--heat-6)");
  assert.equal(score.querySelector(".score-fill").style.width, "75%");
  assert.equal(score.querySelector(".score-meter").getAttribute("aria-valuenow"), "7.5");
  assert.equal(page.$("#result-feedback").textContent, "Solid, well-developed answer.");
  assert.equal(page.nextButton.textContent, "Next question");
  assert.equal(page.document.activeElement, page.$("#result-view h1"));
});

test("moves on to the next question with an empty answer box", async (t) => {
  const page = await openOnQuestion(t, { [`POST ${ANSWER_URL}`]: () => scored() });
  answerWith(page, "An answer");
  await waitFor(() => page.visible("result-view"), "the result");

  page.nextButton.click();

  assert.equal(page.visible("question-view"), true);
  assert.equal(page.$("#question-number").textContent, "Question 3");
  assert.equal(page.$("#question-text").textContent, "Question text 3?");
  assert.equal(page.answer.value, "");
  assert.equal(page.submitButton.disabled, false);
});

test("after the last answer, loads the finished interview and shows the summary", async (t) => {
  const page = await openOnQuestion(t, {
    [`POST ${ANSWER_URL}`]: () => scored({ next_question: null, interview_status: "completed" }),
  });
  answerWith(page, "Final answer");
  await waitFor(() => page.visible("result-view"), "the result");
  assert.equal(page.nextButton.textContent, "See results");

  page.window.fetch = async (url, init = {}) => {
    page.calls.push({ url, method: init.method });
    return jsonResponse(200, completedInterview());
  };
  page.nextButton.click();
  await waitFor(() => page.visible("summary-view"), "the summary");

  assert.deepEqual(page.calls.at(-1), { url: DETAIL_URL, method: "GET" });
  assert.equal(page.$("#summary-score .score-value").textContent, "6.5");
  assert.equal(page.$("#summary-list").children.length, 3);
});

test("opens a finished interview straight on its summary, rendering answers as text", async (t) => {
  const page = await openSessionPage(t, {
    [`GET ${DETAIL_URL}`]: () => jsonResponse(200, completedInterview()),
  });
  await waitFor(() => page.visible("summary-view"), "the summary");

  const items = [...page.$("#summary-list").children];
  assert.equal(items[0].querySelector(".summary-topic").textContent, "Q1 · topic-1");
  assert.equal(items[1].querySelector(".summary-answer").textContent, "<img src=x onerror=alert(1)>");
  assert.equal(page.$("#summary-list img"), null);
  assert.equal(items[1].querySelector(".score").dataset.heat, "8");
  assert.equal(items[1].querySelector(".summary-feedback").textContent, "Great.");
  assert.equal(items[2].querySelector(".summary-answer").textContent, "Not answered.");
  assert.equal(items[2].querySelector(".score"), null);
  assert.equal(page.$("#summary-no-score").hidden, true);
});

test("says so when nothing was scored", async (t) => {
  const page = await openSessionPage(t, {
    [`GET ${DETAIL_URL}`]: () =>
      jsonResponse(200, completedInterview({ score: null, questions: [question(0)] })),
  });
  await waitFor(() => page.visible("summary-view"), "the summary");

  assert.equal(page.$("#summary-score").hidden, true);
  assert.equal(page.$("#summary-no-score").hidden, false);
});

test("shows a not-found view for an interview that isn't the user's", async (t) => {
  const page = await openSessionPage(t, {
    [`GET ${DETAIL_URL}`]: () =>
      jsonResponse(404, { detail: "Interview not found.", error_code: "NOT_FOUND" }),
  });
  await waitFor(() => page.visible("missing-view"), "the not-found view");

  assert.equal(page.visible("loading-view"), false);
  assert.equal(page.$('#missing-view a[href="/interview"]') !== null, true);
});

test("explains a failed load instead of spinning forever", async (t) => {
  const page = await openSessionPage(t, {
    [`GET ${DETAIL_URL}`]: () => Promise.reject(new TypeError("Failed to fetch")),
  });
  await waitFor(() => bannerShown(page), "the error banner");

  assert.match(page.banner.textContent, /can't reach the server/i);
  assert.equal(page.visible("loading-view"), false);
});

test("refuses a blank answer without sending it", async (t) => {
  const page = await openOnQuestion(t);

  answerWith(page, "   \n  ");

  assert.match(page.banner.textContent, /write an answer/i);
  assert.equal(page.calls.length, 1);
  assert.equal(page.document.activeElement, page.answer);
});

test("reloads the interview when the server says it has moved on", async (t) => {
  let loads = 0;
  const page = await openSessionPage(t, {
    [`GET ${DETAIL_URL}`]: () => {
      loads += 1;
      return jsonResponse(200, loads === 1 ? interview() : completedInterview());
    },
    [`POST ${ANSWER_URL}`]: () =>
      jsonResponse(409, {
        detail: "This interview is no longer in progress.",
        error_code: "INTERVIEW_NOT_IN_PROGRESS",
      }),
  });
  await waitFor(() => page.visible("question-view"), "the question");

  answerWith(page, "Too late");
  await waitFor(() => page.visible("summary-view"), "the summary");

  assert.equal(loads, 2);
  assert.match(page.banner.textContent, /changed since the page loaded/i);
});

test("finishes early after confirmation and shows the summary", async (t) => {
  let asked = "";
  const page = await openOnQuestion(
    t,
    { [`POST ${FINISH_URL}`]: () => jsonResponse(200, completedInterview()) },
    {
      confirm: (message) => {
        asked = message;
        return true;
      },
    },
  );

  page.finishButton.click();
  await waitFor(() => page.visible("summary-view"), "the summary");

  assert.match(asked, /won't be scored/);
  assert.deepEqual(page.calls.at(-1), { url: FINISH_URL, method: "POST", body: undefined });
});

test("stays on the question when the user cancels finishing early", async (t) => {
  const page = await openOnQuestion(t, {}, { confirm: () => false });

  page.finishButton.click();

  assert.equal(page.calls.length, 1);
  assert.equal(page.visible("question-view"), true);
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
  test(`keeps the answer and explains ${failure.name}`, async (t) => {
    const page = await openOnQuestion(t, { [`POST ${ANSWER_URL}`]: failure.respond });

    answerWith(page, "My careful answer");
    await waitFor(() => bannerShown(page), "the error banner");

    assert.match(page.banner.textContent, failure.message);
    assert.equal(page.answer.value, "My careful answer");
    assert.equal(page.answer.readOnly, false);
    assert.equal(page.submitButton.disabled, false);
    assert.equal(page.submitButton.textContent, "Submit answer");
    assert.equal(page.visible("question-view"), true);
  });
}

test("locks the form while an answer is being scored and ignores a second submit", async (t) => {
  let finishScoring;
  const page = await openOnQuestion(t, {
    [`POST ${ANSWER_URL}`]: () =>
      new Promise((resolve) => {
        finishScoring = resolve;
      }),
  });

  answerWith(page, "An answer");
  await waitFor(() => page.submitButton.disabled, "the button to lock");
  assert.equal(page.submitButton.textContent, "Scoring...");
  assert.equal(page.finishButton.disabled, true);
  assert.equal(page.answer.readOnly, true);

  page.form.dispatchEvent(new page.window.Event("submit", { bubbles: true, cancelable: true }));
  assert.equal(page.calls.filter((call) => call.method === "POST").length, 1);

  finishScoring(scored());
  await waitFor(() => page.visible("result-view"), "the result");
});

test("heat levels step every two points and stay within 0-10", async (t) => {
  const page = await openSessionPage(t, {
    [`GET ${DETAIL_URL}`]: () => jsonResponse(200, interview()),
  });
  const { heatLevel, heatColor, formatScore } = page.window.SkillForge;

  assert.deepEqual(
    [-1, 0, 1.9, 2, 5.5, 7.99, 8, 9.9, 10, 12].map(heatLevel),
    [0, 0, 0, 2, 4, 6, 8, 8, 10, 10],
  );
  assert.equal(heatColor(10), "var(--heat-10)");
  assert.equal(formatScore(7), "7.0");
});
