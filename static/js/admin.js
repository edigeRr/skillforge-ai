document.addEventListener("DOMContentLoaded", () => {
  const { api } = window.SkillForge;

  const PAGE_SIZE = 20;
  const ROLE_LABELS = { user: "User", admin: "Admin" };
  const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

  const $ = (selector) => document.querySelector(selector);
  const loading = $("#admin-loading");
  const denied = $("#admin-denied");
  const content = $("#admin-content");
  const banner = $("#form-error");
  const status = $("#admin-status");
  const list = $("#admin-users");
  const pagination = $("#pagination");
  const prevButton = $("#prev-page");
  const nextButton = $("#next-page");
  const pageStatus = $("#page-status");
  const createForm = $("#create-form");
  const createError = $("#create-error");
  const createButton = createForm.querySelector('button[type="submit"]');
  const createLabel = createButton.textContent;

  let page = 1;
  let myId = null;
  let latestRequest = 0;

  function roleLabel(role) {
    return ROLE_LABELS[role] || role;
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

  function showDenied() {
    loading.hidden = true;
    content.hidden = true;
    banner.hidden = true;
    denied.hidden = false;
  }

  function roleControls(user) {
    const controls = document.createElement("div");
    controls.className = "admin-role";

    if (user.id === myId) {
      const fixed = document.createElement("span");
      fixed.className = "admin-role-fixed";
      fixed.textContent = `${roleLabel(user.role)} · you`;
      controls.append(fixed);
      return controls;
    }

    const select = document.createElement("select");
    select.className = "form-input";
    select.setAttribute("aria-label", `Role for ${user.email}`);
    for (const [value, label] of Object.entries(ROLE_LABELS)) {
      select.append(new Option(label, value, false, value === user.role));
    }

    const save = document.createElement("button");
    save.type = "button";
    save.className = "btn btn-secondary";
    save.textContent = "Save";
    save.disabled = true;

    let savedRole = user.role;
    select.addEventListener("change", () => {
      save.disabled = select.value === savedRole;
    });

    save.addEventListener("click", async () => {
      const role = select.value;
      save.disabled = true;
      select.disabled = true;
      save.textContent = "Saving...";
      status.textContent = "";
      banner.hidden = true;
      try {
        const updated = await api.patch(`/admin/users/${user.id}/role`, { role });
        savedRole = updated.role;
        status.textContent = `${updated.email} is now ${roleLabel(updated.role)}.`;
      } catch (error) {
        if (error.status === 403) {
          showDenied();
          return;
        }
        if (error.status === 404) {
          banner.textContent = "That account no longer exists.";
          banner.hidden = false;
          load();
          return;
        }
        select.value = savedRole;
        banner.textContent = describeError(error);
        banner.hidden = false;
      } finally {
        save.textContent = "Save";
        select.disabled = false;
        save.disabled = select.value === savedRole;
      }
    });

    controls.append(select, save);
    return controls;
  }

  function userItem(user) {
    const item = document.createElement("li");
    item.className = "admin-user card";
    item.dataset.userId = user.id;

    const main = document.createElement("div");
    main.className = "admin-user-main";
    const name = document.createElement("p");
    name.className = "admin-user-name";
    name.textContent = user.name;
    const meta = document.createElement("p");
    meta.className = "admin-user-meta";
    const joined = document.createElement("time");
    joined.dateTime = user.created_at;
    joined.textContent = dateFormat.format(new Date(user.created_at));
    meta.append(`${user.email} · joined `, joined);
    main.append(name, meta);

    item.append(main, roleControls(user));
    return item;
  }

  function render(data) {
    list.replaceChildren(...data.items.map(userItem));
    const pages = Math.max(1, Math.ceil(data.total / data.page_size));
    pagination.hidden = pages <= 1;
    pageStatus.textContent = `Page ${data.page} of ${pages}`;
    prevButton.disabled = data.page <= 1;
    nextButton.disabled = data.page >= pages;
  }

  async function load() {
    const requestId = ++latestRequest;
    list.setAttribute("aria-busy", "true");
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });

    try {
      const [me, data] = await Promise.all([
        myId === null ? api.get("/profile/me") : Promise.resolve({ id: myId }),
        api.get(`/admin/users?${params}`),
      ]);
      if (requestId !== latestRequest) return;
      myId = me.id;
      const pages = Math.max(1, Math.ceil(data.total / data.page_size));
      if (data.total > 0 && page > pages) {
        page = pages;
        await load();
        return;
      }
      render(data);
      content.hidden = false;
    } catch (error) {
      if (requestId !== latestRequest) return;
      if (error.status === 403) {
        showDenied();
        return;
      }
      banner.textContent = describeError(error);
      banner.hidden = false;
    } finally {
      if (requestId === latestRequest) {
        loading.hidden = true;
        list.removeAttribute("aria-busy");
      }
    }
  }

  function describeCreateError(error) {
    if (error.errorCode === "EMAIL_ALREADY_EXISTS") {
      return { message: "An account with that email already exists.", fieldId: "new-email" };
    }
    if (error.status === 422) {
      return {
        message:
          "Please check the details. A password needs 8+ characters with at least one letter and one digit.",
      };
    }
    return { message: describeError(error) };
  }

  function clearInvalid(field) {
    field.classList.remove("is-invalid");
    field.removeAttribute("aria-invalid");
  }

  createForm.addEventListener("input", (event) => clearInvalid(event.target));

  createForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (createButton.disabled) return;

    createError.hidden = true;
    createForm.querySelectorAll(".is-invalid").forEach(clearInvalid);
    status.textContent = "";
    createButton.disabled = true;
    createButton.textContent = "Creating...";

    const payload = {
      name: $("#new-name").value.trim(),
      email: $("#new-email").value.trim(),
      password: $("#new-password").value,
      role: $("#new-role").value,
    };

    try {
      const created = await api.post("/admin/users", payload);
      createForm.reset();
      status.textContent = `Created ${created.email} as ${roleLabel(created.role)}.`;
      page = 1;
      load();
    } catch (error) {
      if (error.status === 403) {
        showDenied();
        return;
      }
      const { message, fieldId } = describeCreateError(error);
      createError.textContent = message;
      createError.hidden = false;
      if (fieldId) {
        const field = document.getElementById(fieldId);
        field.classList.add("is-invalid");
        field.setAttribute("aria-invalid", "true");
        field.focus();
      }
    } finally {
      createButton.disabled = false;
      createButton.textContent = createLabel;
    }
  });

  prevButton.addEventListener("click", () => {
    page -= 1;
    load();
  });
  nextButton.addEventListener("click", () => {
    page += 1;
    load();
  });

  load();
});
