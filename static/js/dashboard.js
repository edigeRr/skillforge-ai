document.addEventListener("DOMContentLoaded", () => {
  const { api, paintScore } = window.SkillForge;

  const $ = (selector) => document.querySelector(selector);
  const banner = $("#form-error");
  const loading = $("#dashboard-loading");
  const emptyState = $("#dashboard-empty");
  const stats = $("#dashboard-stats");

  function describeError(error) {
    if (error.status === 429) {
      return "Too many requests - wait a minute and try again.";
    }
    if (error.status === undefined) {
      return "Can't reach the server. Check your connection and try again.";
    }
    return "Something went wrong. Please try again.";
  }

  function topicItem(topic) {
    const item = document.createElement("li");
    item.className = "topic-item";
    const name = document.createElement("span");
    name.className = "topic-name";
    name.textContent = topic.topic;
    const score = $("#score-template").content.firstElementChild.cloneNode(true);
    score.querySelector(".score-meter").setAttribute("aria-label", `${topic.topic} average`);
    paintScore(score, topic.average_score);
    item.append(name, score);
    return item;
  }

  function fillTopics(listSelector, noteSelector, topics) {
    $(listSelector).replaceChildren(...topics.map(topicItem));
    $(noteSelector).hidden = topics.length > 0;
  }

  function render(data) {
    if (data.total_interviews === 0) {
      emptyState.hidden = false;
      return;
    }

    $("#total-interviews").textContent = String(data.total_interviews);
    const average = $("#average-score");
    if (data.average_score === null) {
      average.hidden = true;
      $("#average-none").hidden = false;
    } else {
      paintScore(average, data.average_score);
    }

    fillTopics("#best-topics", "#best-none", data.best_topics);
    fillTopics("#weak-topics", "#weak-none", data.weak_topics);
    stats.hidden = false;
  }

  async function greet() {
    const profile = await api.get("/profile/me").catch(() => null);
    if (!profile) return;
    const greeting = $("#greeting");
    greeting.textContent = `Welcome back, ${profile.name}.`;
    greeting.hidden = false;
  }

  async function load() {
    try {
      render(await api.get("/dashboard/stats"));
    } catch (error) {
      banner.textContent = describeError(error);
      banner.hidden = false;
    } finally {
      loading.hidden = true;
    }
  }

  greet();
  load();
});
