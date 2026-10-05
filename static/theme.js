const THEME_STORAGE_KEY = "bma-appearance";

function normalizeThemePreference(value) {
  if (value === "light" || value === "dark" || value === "device") {
    return value;
  }
  return "device";
}

function readThemePreference() {
  try {
    return normalizeThemePreference(localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return "device";
  }
}

function applyThemePreference(mode) {
  const preference = normalizeThemePreference(mode);
  const root = document.documentElement;
  if (preference === "device") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", preference);
  }
  root.dataset.themePreference = preference;
}

async function persistThemeToServer(preference) {
  try {
    await fetch("/api/settings/appearance", {
      method: "PATCH",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ theme: preference }),
    });
  } catch {
    /* offline or logged out */
  }
}

function setThemePreference(mode, options = {}) {
  const preference = normalizeThemePreference(mode);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    /* ignore */
  }
  applyThemePreference(preference);
  syncThemePickerUi(preference);
  if (options.syncServer !== false) {
    void persistThemeToServer(preference);
  }
}

function syncThemePickerUi(preference) {
  const group = document.querySelector("[data-theme-picker]");
  if (!group) {
    return;
  }
  group.querySelectorAll("[data-theme-value]").forEach((button) => {
    const active = button.dataset.themeValue === preference;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-checked", active ? "true" : "false");
  });
}

async function loadThemeFromServer() {
  try {
    const res = await fetch("/api/settings/appearance", { headers: { Accept: "application/json" } });
    if (!res.ok) {
      return null;
    }
    const data = await res.json();
    const theme = data?.appearance?.theme;
    return normalizeThemePreference(theme);
  } catch {
    return null;
  }
}

function initThemePicker() {
  const group = document.querySelector("[data-theme-picker]");
  if (!group) {
    return;
  }
  const preference = readThemePreference();
  syncThemePickerUi(preference);

  group.querySelectorAll("[data-theme-value]").forEach((button) => {
    button.addEventListener("click", () => {
      setThemePreference(button.dataset.themeValue || "device");
    });
  });
}

async function initThemeFromAccount() {
  const serverTheme = await loadThemeFromServer();
  if (serverTheme) {
    setThemePreference(serverTheme, { syncServer: false });
    return;
  }
  applyThemePreference(readThemePreference());
}

applyThemePreference(readThemePreference());

function scheduleIdle(fn, timeoutMs = 2500) {
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(fn, { timeout: timeoutMs });
  } else {
    setTimeout(fn, 100);
  }
}

scheduleIdle(() => {
  void initThemeFromAccount();
});

if (window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (readThemePreference() === "device") {
      applyThemePreference("device");
    }
  });
}

document.addEventListener("DOMContentLoaded", initThemePicker);
