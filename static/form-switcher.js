/** Dropdown UI matching the main app business switcher; submits a parent GET form on pick. */
function initFormSwitchers(form) {
  if (!form) {
    return;
  }

  const roots = form.querySelectorAll("[data-form-switcher]");

  const closeAll = (except) => {
    roots.forEach((root) => {
      if (except && root === except) {
        return;
      }
      const trigger = root.querySelector(".business-switcher-trigger");
      const menu = root.querySelector(".business-switcher-menu");
      if (!trigger || !menu) {
        return;
      }
      root.classList.remove("is-open");
      trigger.setAttribute("aria-expanded", "false");
      window.setTimeout(() => {
        if (!root.classList.contains("is-open")) {
          menu.hidden = true;
        }
      }, 220);
    });
  };

  roots.forEach((root) => {
    const trigger = root.querySelector(".business-switcher-trigger");
    const menu = root.querySelector(".business-switcher-menu");
    const label = root.querySelector(".business-switcher-label");
    const hidden = root.querySelector(`input[type="hidden"][name="${root.dataset.inputName}"]`);
    const options = root.querySelectorAll(".business-switcher-option");
    if (!trigger || !menu || !label || !hidden) {
      return;
    }

    const close = () => closeAll(null);

    const open = () => {
      closeAll(root);
      menu.hidden = false;
      requestAnimationFrame(() => {
        root.classList.add("is-open");
        trigger.setAttribute("aria-expanded", "true");
      });
    };

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      if (root.classList.contains("is-open")) {
        close();
      } else {
        open();
      }
    });

    options.forEach((option) => {
      option.addEventListener("click", (e) => {
        e.stopPropagation();
        const value = option.dataset.value ?? "";
        if (option.classList.contains("is-selected")) {
          close();
          return;
        }
        options.forEach((opt) => {
          opt.classList.toggle("is-selected", opt === option);
          opt.setAttribute("aria-selected", opt === option ? "true" : "false");
          opt.tabIndex = opt === option ? 0 : -1;
        });
        hidden.value = value;
        label.textContent = option.textContent.trim();
        close();
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.submit();
        }
      });
    });
  });

  document.addEventListener("click", (e) => {
    if (!form.contains(e.target)) {
      closeAll(null);
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAll(null);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("admin-users-filters");
  initFormSwitchers(form);
  initAdminUsersSearch(form);
});

function initAdminUsersSearch(form) {
  if (!form) {
    return;
  }
  const input = document.getElementById("admin-users-q");
  const clearBtn = document.getElementById("admin-users-search-clear");
  const wrap = document.getElementById("admin-users-search-wrap");
  if (!input || !clearBtn || !wrap) {
    return;
  }

  const syncClear = () => {
    const hasValue = input.value.length > 0;
    wrap.classList.toggle("has-value", hasValue);
    clearBtn.classList.toggle("is-visible", hasValue);
    clearBtn.setAttribute("aria-hidden", hasValue ? "false" : "true");
    clearBtn.tabIndex = hasValue ? 0 : -1;
  };

  syncClear();
  input.addEventListener("input", syncClear);

  clearBtn.addEventListener("click", () => {
    input.value = "";
    syncClear();
    input.focus();
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
    } else {
      form.submit();
    }
  });
}
