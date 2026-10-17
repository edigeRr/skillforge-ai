document.addEventListener("DOMContentLoaded", () => {
  const { api, setTokens } = window.SkillForge;

  const AFTER_REGISTER_URL = "/";

  const form = document.querySelector("#register-form");
  const banner = document.querySelector("#form-error");
  const submitButton = form.querySelector('button[type="submit"]');
  const idleLabel = submitButton.textContent;

  function describeRegisterError(error) {
    if (error.errorCode === "EMAIL_ALREADY_EXISTS") {
      return {
        message: "An account with that email already exists - try logging in instead.",
        fieldId: "email",
      };
    }
    if (error.status === 422) {
      return {
        message:
          "Please check your details. A password needs 8+ characters with at least one letter and one digit.",
      };
    }
    if (error.status === 429) {
      return { message: "Too many attempts - wait a minute and try again." };
    }
    if (error.status === undefined) {
      return { message: "Can't reach the server. Check your connection and try again." };
    }
    return { message: "Something went wrong. Please try again." };
  }

  function showError({ message, fieldId }) {
    banner.textContent = message;
    banner.hidden = false;
    if (fieldId) {
      const field = document.getElementById(fieldId);
      field.classList.add("is-invalid");
      field.setAttribute("aria-invalid", "true");
      field.focus();
    }
  }

  function clearInvalid(field) {
    field.classList.remove("is-invalid");
    field.removeAttribute("aria-invalid");
  }

  function clearErrors() {
    banner.hidden = true;
    banner.textContent = "";
    form.querySelectorAll(".is-invalid").forEach(clearInvalid);
  }

  function setBusy(busy) {
    submitButton.disabled = busy;
    submitButton.textContent = busy ? "Creating account..." : idleLabel;
  }

  form.addEventListener("input", (event) => clearInvalid(event.target));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitButton.disabled) return;

    clearErrors();
    setBusy(true);

    const name = document.getElementById("name").value.trim();
    const credentials = {
      email: document.getElementById("email").value.trim(),
      password: document.getElementById("password").value,
    };

    try {
      await api.post("/auth/register", { ...credentials, name }, { auth: false });
    } catch (error) {
      showError(describeRegisterError(error));
      setBusy(false);
      return;
    }

    try {
      setTokens(await api.post("/auth/login", credentials, { auth: false }));
    } catch {
      showError({ message: "Your account was created, but signing you in failed. Please log in." });
      setBusy(false);
      return;
    }

    window.location.href = AFTER_REGISTER_URL;
  });
});
