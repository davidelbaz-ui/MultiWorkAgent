function initAdminUsersSheets() {
  const form = document.getElementById("admin-users-filters");
  const root = document.getElementById("admin-users-sheets");
  if (!form || !root) {
    return;
  }

  const sheetSearch = document.getElementById("admin-users-sheet-search");
  const sheetFilters = document.getElementById("admin-users-sheet-filters");
  const sheetSort = document.getElementById("admin-users-sheet-sort");
  const sheetInput = document.getElementById("admin-users-q-sheet");
  const mainSearch = document.getElementById("admin-users-q");

  const sheets = {
    search: sheetSearch,
    filters: sheetFilters,
    sort: sheetSort,
  };

  const setFormHidden = (name, value) => {
    const input = form.querySelector(`input[name="${name}"]`);
    if (input) {
      input.value = value;
    }
  };

  const getSelectedInSheet = (sheetEl, name) => {
    const list = sheetEl?.querySelector(`[data-filter-name="${name}"]`);
    const selected = list?.querySelector(".admin-sheet-option.is-selected");
    return selected?.dataset.value ?? form.querySelector(`input[name="${name}"]`)?.value;
  };

  const selectOption = (btn) => {
    const list = btn.closest(".admin-sheet-option-list");
    if (!list) {
      return;
    }
    list.querySelectorAll(".admin-sheet-option").forEach((el) => {
      el.classList.toggle("is-selected", el === btn);
    });
  };

  root.querySelectorAll(".admin-sheet-option").forEach((btn) => {
    btn.addEventListener("click", () => selectOption(btn));
  });

  const closeSheets = () => {
    root.hidden = true;
    root.setAttribute("aria-hidden", "true");
    Object.values(sheets).forEach((sheet) => {
      if (sheet) {
        sheet.hidden = true;
      }
    });
    document.body.classList.remove("admin-sheet-open");
    root.querySelectorAll("[data-admin-users-sheet]").forEach((btn) => {
      btn.setAttribute("aria-expanded", "false");
    });
  };

  const openSheet = (key) => {
    const sheet = sheets[key];
    if (!sheet) {
      return;
    }
    if (key === "search" && sheetInput && mainSearch) {
      sheetInput.value = mainSearch.value;
    }
    root.hidden = false;
    root.setAttribute("aria-hidden", "false");
    Object.values(sheets).forEach((el) => {
      if (el) {
        el.hidden = el !== sheet;
      }
    });
    document.body.classList.add("admin-sheet-open");
    const trigger = document.querySelector(`[data-admin-users-sheet="${key}"]`);
    trigger?.setAttribute("aria-expanded", "true");
    window.requestAnimationFrame(() => {
      if (key === "search") {
        sheetInput?.focus();
      }
    });
  };

  document.querySelectorAll("[data-admin-users-sheet]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.getAttribute("data-admin-users-sheet");
      if (!key) {
        return;
      }
      if (!root.hidden && sheets[key] && !sheets[key].hidden) {
        closeSheets();
        return;
      }
      openSheet(key);
    });
  });

  root.querySelectorAll("[data-admin-sheet-close]").forEach((btn) => {
    btn.addEventListener("click", closeSheets);
  });

  document.querySelectorAll("[data-admin-users-apply]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-admin-users-apply");
      if (mode === "search") {
        if (mainSearch && sheetInput) {
          mainSearch.value = sheetInput.value;
        }
      } else if (mode === "filters" && sheetFilters) {
        ["role", "sign_in", "last_login"].forEach((name) => {
          setFormHidden(name, getSelectedInSheet(sheetFilters, name) ?? "");
        });
      } else if (mode === "sort" && sheetSort) {
        setFormHidden("sort", getSelectedInSheet(sheetSort, "sort") ?? "");
      }
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !root.hidden) {
      closeSheets();
    }
  });
}

document.addEventListener("DOMContentLoaded", initAdminUsersSheets);
