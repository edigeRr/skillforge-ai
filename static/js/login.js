document.addEventListener("DOMContentLoaded", () => {
  const { api, setTokens } = window.SkillForge;

  const AFTER_LOGIN_URL = "/";

  const form = document.querySelector("#login-form");
  const banner = document.querySelector("#form-error");
  const submitButton = form.querySelector('button[type="submit"]');
  const idleLabel = submitButton.textContent;

  function describeLoginError(error) {
    if (error.errorCode === "INVALID_CREDENTIALS") {
      return "Incorrect email or password.";
    }
    if (error.status === 429) {
      return "Too many attempts - wait a minute and try again.";
    }
    if (error.status === undefined) {
      return "Can't reach the server. Check your connection and try again.";
    }
    return "Something went wrong. Please try again.";
  }

  function showError(message) {
    banner.textContent = message;
    banner.hidden = false;
  }

  function clearErrors() {
    banner.hidden = true;
    banner.textContent = "";
  }

  function setBusy(busy) {
    submitButton.disabled = busy;
    submitButton.textContent = busy ? "Logging in..." : idleLabel;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitButton.disabled) return;

    clearErrors();
    setBusy(true);

    const credentials = {
      email: document.getElementById("email").value.trim(),
      password: document.getElementById("password").value,
    };

    try {
      setTokens(await api.post("/auth/login", credentials, { auth: false }));
    } catch (error) {
      showError(describeLoginError(error));
      setBusy(false);
      return;
    }

    window.location.href = AFTER_LOGIN_URL;
  });
});
