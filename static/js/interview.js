document.addEventListener("DOMContentLoaded", () => {
  const { api } = window.SkillForge;

  const sessionUrl = (interviewId) => `/interview/${interviewId}`;

  const form = document.querySelector("#start-form");
  const banner = document.querySelector("#form-error");
  const resumeNotice = document.querySelector("#resume-notice");
  const resumeLink = document.querySelector("#resume-link");
  const submitButton = form.querySelector('button[type="submit"]');
  const idleLabel = submitButton.textContent;

  function describeStartError(error) {
    if (error.status === 429) {
      return "Too many requests - wait a minute and try again.";
    }
    if (error.status === undefined) {
      return "Can't reach the server. Check your connection and try again.";
    }
    return "Something went wrong. Please try again.";
  }

  async function findInterviewInProgress() {
    try {
      const page = await api.get("/interviews?status=in_progress&page_size=1");
      return page.items[0] || null;
    } catch {
      return null;
    }
  }

  async function offerToResume() {
    const interview = await findInterviewInProgress();
    if (!interview) {
      showError("You already have an interview in progress, but it couldn't be loaded. Please try again.");
      return;
    }
    resumeLink.href = sessionUrl(interview.id);
    resumeNotice.hidden = false;
    resumeLink.focus();
  }

  function showError(message) {
    banner.textContent = message;
    banner.hidden = false;
  }

  function clearMessages() {
    banner.hidden = true;
    banner.textContent = "";
    resumeNotice.hidden = true;
  }

  function setBusy(busy) {
    submitButton.disabled = busy;
    submitButton.textContent = busy ? "Starting..." : idleLabel;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitButton.disabled) return;

    clearMessages();
    setBusy(true);

    const choice = {
      language: form.elements.language.value,
      difficulty: form.elements.difficulty.value,
    };

    let interview;
    try {
      interview = await api.post("/interviews", choice);
    } catch (error) {
      if (error.errorCode === "INTERVIEW_ALREADY_IN_PROGRESS") {
        await offerToResume();
      } else {
        showError(describeStartError(error));
      }
      setBusy(false);
      return;
    }

    window.location.href = sessionUrl(interview.id);
  });
});
