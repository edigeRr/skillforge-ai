document.addEventListener("DOMContentLoaded", () => {
  const { api, heatLevel, heatColor, formatScore } = window.SkillForge;

  const LANGUAGE_LABELS = { python: "Python", java: "Java", cpp: "C++", javascript: "JavaScript" };
  const LEVEL_LABELS = { junior: "Junior", middle: "Middle", senior: "Senior" };

  const interviewId = window.location.pathname.split("/").filter(Boolean).pop();
  const interviewPath = `/interviews/${interviewId}`;

  const $ = (selector) => document.querySelector(selector);
  const views = {
    loading: $("#loading-view"),
    missing: $("#missing-view"),
    question: $("#question-view"),
    result: $("#result-view"),
    summary: $("#summary-view"),
  };
  const banner = $("#form-error");
  const meta = $("#session-meta");
  const answerForm = $("#answer-form");
  const answerField = $("#answer");
  const submitButton = answerForm.querySelector('button[type="submit"]');
  const finishButton = $("#finish-button");
  const nextButton = $("#next-button");
  const idleSubmitLabel = submitButton.textContent;

  let currentQuestion = null;
  let nextQuestion = null;
  let totalQuestions = null;

  function show(name, { focus = true } = {}) {
    for (const [key, view] of Object.entries(views)) {
      view.hidden = key !== name;
    }
    const heading = views[name].querySelector("[data-view-heading]");
    if (focus && heading) heading.focus();
  }

  function showError(message) {
    banner.textContent = message;
    banner.hidden = false;
  }

  function clearError() {
    banner.hidden = true;
    banner.textContent = "";
  }

  function describeError(error) {
    if (error.status === 429) {
      return "Too many requests - wait a minute and try again.";
    }
    if (error.status === undefined) {
      return "Can't reach the server. Check your connection and try again.";
    }
    return "Something went wrong. Please try again.";
  }

  function paintScore(element, score) {
    element.querySelector(".score-value").textContent = formatScore(score);
    const meter = element.querySelector(".score-meter");
    meter.setAttribute("aria-valuenow", String(score));
    meter.setAttribute("aria-valuetext", `${formatScore(score)} out of 10`);
    const fill = element.querySelector(".score-fill");
    fill.style.width = `${Math.min(10, Math.max(0, score)) * 10}%`;
    fill.style.background = heatColor(score);
    element.dataset.heat = String(heatLevel(score));
  }

  function setMeta(interview) {
    const language = LANGUAGE_LABELS[interview.language] || interview.language;
    const level = LEVEL_LABELS[interview.difficulty] || interview.difficulty;
    meta.textContent = `${language} · ${level}`;
  }

  function showQuestion(question) {
    currentQuestion = question;
    $("#question-number").textContent = totalQuestions
      ? `Question ${question.order_index} of ${totalQuestions}`
      : `Question ${question.order_index}`;
    $("#question-topic").textContent = question.topic;
    $("#question-text").textContent = question.question;
    answerField.value = "";
    setBusy(false);
    show("question", { focus: false });
    answerField.focus();
  }

  function showResult(result) {
    paintScore($("#result-score"), result.score);
    $("#result-feedback").textContent = result.feedback;
    nextQuestion = result.next_question;
    nextButton.textContent = nextQuestion ? "Next question" : "See results";
    show("result");
  }

  function summaryItem(question) {
    const item = document.createElement("li");
    item.className = "summary-item card";

    const heading = document.createElement("p");
    heading.className = "summary-topic";
    heading.textContent = `Q${question.order_index} · ${question.topic}`;

    const text = document.createElement("p");
    text.className = "summary-question";
    text.textContent = question.question;

    const answer = document.createElement("p");
    answer.className = "summary-answer";
    answer.textContent = question.answer ?? "Not answered.";

    item.append(heading, text, answer);

    if (question.score !== null && question.score !== undefined) {
      const score = $("#score-template").content.firstElementChild.cloneNode(true);
      paintScore(score, question.score);
      const feedback = document.createElement("p");
      feedback.className = "summary-feedback";
      feedback.textContent = question.feedback;
      item.append(score, feedback);
    } else {
      answer.classList.add("text-muted");
    }
    return item;
  }

  function showSummary(interview) {
    setMeta(interview);
    const overall = $("#summary-score");
    const noScore = $("#summary-no-score");
    if (interview.score === null) {
      overall.hidden = true;
      noScore.hidden = false;
    } else {
      overall.hidden = false;
      noScore.hidden = true;
      paintScore(overall, interview.score);
    }
    $("#summary-list").replaceChildren(...interview.questions.map(summaryItem));
    show("summary");
  }

  function render(interview) {
    setMeta(interview);
    totalQuestions = interview.total_questions ?? null;
    if (interview.status !== "in_progress") {
      showSummary(interview);
      return;
    }
    const open = interview.questions.find((q) => q.answer === null);
    if (!open) {
      views.loading.hidden = true;
      showError("This interview couldn't be loaded. Please reload the page.");
      return;
    }
    showQuestion(open);
  }

  async function load() {
    try {
      render(await api.get(interviewPath));
    } catch (error) {
      if (error.status === 404 || error.status === 422) {
        show("missing");
      } else {
        views.loading.hidden = true;
        showError(describeError(error));
      }
    }
  }

  function setBusy(busy, label = "Scoring...") {
    submitButton.disabled = busy;
    finishButton.disabled = busy;
    answerField.readOnly = busy;
    submitButton.textContent = busy ? label : idleSubmitLabel;
  }

  async function recoverFromConflict(error) {
    if (error.status !== 409) return false;
    await load();
    showError("This interview changed since the page loaded - here is its latest state.");
    return true;
  }

  answerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitButton.disabled) return;

    clearError();
    const answer = answerField.value.trim();
    if (!answer) {
      showError("Write an answer before submitting.");
      answerField.focus();
      return;
    }

    setBusy(true);
    try {
      showResult(
        await api.post(`${interviewPath}/answer`, { question_id: currentQuestion.id, answer }),
      );
    } catch (error) {
      setBusy(false);
      if (!(await recoverFromConflict(error))) showError(describeError(error));
    }
  });

  finishButton.addEventListener("click", async () => {
    if (finishButton.disabled) return;
    if (!window.confirm("Finish now? Questions you haven't answered won't be scored.")) return;

    clearError();
    setBusy(true, "Finishing...");
    try {
      showSummary(await api.post(`${interviewPath}/finish`));
    } catch (error) {
      setBusy(false);
      if (!(await recoverFromConflict(error))) showError(describeError(error));
    }
  });

  nextButton.addEventListener("click", async () => {
    clearError();
    if (nextQuestion) {
      showQuestion(nextQuestion);
      return;
    }
    nextButton.disabled = true;
    try {
      showSummary(await api.get(interviewPath));
    } catch (error) {
      showError(describeError(error));
    } finally {
      nextButton.disabled = false;
    }
  });

  load();
});
