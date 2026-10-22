document.addEventListener("DOMContentLoaded", () => {
  const { api, paintScore } = window.SkillForge;

  const PAGE_SIZE = 10;
  const FILTERS = ["language", "difficulty", "status"];
  const LANGUAGE_LABELS = { python: "Python", java: "Java", cpp: "C++", javascript: "JavaScript" };
  const LEVEL_LABELS = { junior: "Junior", middle: "Middle", senior: "Senior" };
  const STATUS_LABELS = {
    in_progress: "In progress",
    completed: "Completed",
    abandoned: "Abandoned",
  };
  const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

  const $ = (selector) => document.querySelector(selector);
  const filtersForm = $("#history-filters");
  const list = $("#history-list");
  const loading = $("#history-loading");
  const emptyState = $("#history-empty");
  const noMatchState = $("#history-no-match");
  const pagination = $("#pagination");
  const prevButton = $("#prev-page");
  const nextButton = $("#next-page");
  const pageStatus = $("#page-status");
  const banner = $("#form-error");

  let state = readStateFromUrl();
  let latestRequest = 0;

  function allowedValues(name) {
    return [...filtersForm.elements[name].options].map((option) => option.value).filter(Boolean);
  }

  function readStateFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const next = { page: Math.max(1, Number.parseInt(params.get("page"), 10) || 1) };
    for (const name of FILTERS) {
      const value = params.get(name) || "";
      next[name] = allowedValues(name).includes(value) ? value : "";
    }
    return next;
  }

  function writeStateToUrl() {
    const params = new URLSearchParams();
    for (const name of FILTERS) {
      if (state[name]) params.set(name, state[name]);
    }
    if (state.page > 1) params.set("page", String(state.page));
    const query = params.toString();
    window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  }

  function hasFilters() {
    return FILTERS.some((name) => state[name]);
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

  function historyItem(interview) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.className = "history-item card";
    link.href = `/interview/${interview.id}`;

    const main = document.createElement("div");
    main.className = "history-main";
    const title = document.createElement("p");
    title.className = "history-title";
    title.textContent = `${LANGUAGE_LABELS[interview.language] || interview.language} · ${
      LEVEL_LABELS[interview.difficulty] || interview.difficulty
    }`;
    const date = document.createElement("time");
    date.className = "history-date";
    date.dateTime = interview.created_at;
    date.textContent = dateFormat.format(new Date(interview.created_at));
    main.append(title, date);

    const result = document.createElement("div");
    result.className = "history-result";
    if (interview.score !== null && interview.score !== undefined) {
      const score = $("#score-template").content.firstElementChild.cloneNode(true);
      paintScore(score, interview.score);
      result.append(score);
    } else {
      const status = document.createElement("span");
      status.className = `history-status status-${interview.status}`;
      status.textContent =
        interview.status === "in_progress"
          ? "In progress · Continue"
          : `${STATUS_LABELS[interview.status] || interview.status} · No score`;
      result.append(status);
    }

    link.append(main, result);
    item.append(link);
    return item;
  }

  function render(data) {
    list.replaceChildren(...data.items.map(historyItem));
    emptyState.hidden = !(data.total === 0 && !hasFilters());
    noMatchState.hidden = !(data.total === 0 && hasFilters());

    const pages = Math.max(1, Math.ceil(data.total / data.page_size));
    pagination.hidden = pages <= 1;
    pageStatus.textContent = `Page ${data.page} of ${pages}`;
    prevButton.disabled = data.page <= 1;
    nextButton.disabled = data.page >= pages;
  }

  async function load() {
    const requestId = ++latestRequest;
    banner.hidden = true;
    list.setAttribute("aria-busy", "true");

    const params = new URLSearchParams({ page: String(state.page), page_size: String(PAGE_SIZE) });
    for (const name of FILTERS) {
      if (state[name]) params.set(name, state[name]);
    }

    try {
      const data = await api.get(`/interviews?${params}`);
      if (requestId !== latestRequest) return;
      const pages = Math.max(1, Math.ceil(data.total / data.page_size));
      if (data.total > 0 && state.page > pages) {
        state = { ...state, page: pages };
        writeStateToUrl();
        await load();
        return;
      }
      render(data);
    } catch (error) {
      if (requestId !== latestRequest) return;
      banner.textContent = describeError(error);
      banner.hidden = false;
    } finally {
      if (requestId === latestRequest) {
        loading.hidden = true;
        list.removeAttribute("aria-busy");
      }
    }
  }

  function goTo(nextState) {
    state = nextState;
    writeStateToUrl();
    load();
  }

  for (const name of FILTERS) {
    filtersForm.elements[name].value = state[name];
  }

  filtersForm.addEventListener("change", () => {
    const next = { page: 1 };
    for (const name of FILTERS) next[name] = filtersForm.elements[name].value;
    goTo(next);
  });

  filtersForm.addEventListener("submit", (event) => event.preventDefault());

  $("#clear-filters").addEventListener("click", () => {
    filtersForm.reset();
    goTo({ page: 1, language: "", difficulty: "", status: "" });
  });

  prevButton.addEventListener("click", () => goTo({ ...state, page: state.page - 1 }));
  nextButton.addEventListener("click", () => goTo({ ...state, page: state.page + 1 }));

  goTo(state);
});
