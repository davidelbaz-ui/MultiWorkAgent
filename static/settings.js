async function settingsApiJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { Accept: "application/json", "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

async function patchSettings(patch) {
  return settingsApiJson("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

function initNotificationPrefs() {
  const inputs = document.querySelectorAll("[data-notify-pref]");
  if (!inputs.length) {
    return;
  }
  inputs.forEach((input) => {
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    input.addEventListener("change", async () => {
      const key = input.dataset.notifyPref;
      if (!key) {
        return;
      }
      try {
        await patchSettings({ notifications: { [key]: input.checked } });
      } catch (err) {
        console.error(err);
        input.checked = !input.checked;
      }
    });
  });
}

function readAgentPatchFromInput(input) {
  const key = input.dataset.agentPref;
  if (!key) {
    return null;
  }
  if (input instanceof HTMLInputElement && input.type === "checkbox") {
    return { [key]: input.checked };
  }
  if (input instanceof HTMLInputElement && input.type === "number") {
    const value = Number.parseFloat(input.value);
    if (!Number.isFinite(value)) {
      throw new Error("Enter a valid number between 0 and 1.");
    }
    return { [key]: value };
  }
  return null;
}

function initAgentPrefs() {
  const card = document.getElementById("settings-agent-card");
  if (!card) {
    return;
  }
  const inputs = card.querySelectorAll("[data-agent-pref]");
  inputs.forEach((input) => {
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    const eventName = input.type === "number" ? "change" : "change";
    input.addEventListener(eventName, async () => {
      let patchPart;
      try {
        patchPart = readAgentPatchFromInput(input);
      } catch (err) {
        console.error(err);
        return;
      }
      if (!patchPart) {
        return;
      }
      try {
        await patchSettings({ agent: patchPart });
      } catch (err) {
        console.error(err);
      }
    });
  });
}

function initDangerZone() {
  const deleteDataBtn = document.getElementById("settings-delete-all-data");
  const deleteAccountBtn = document.getElementById("settings-delete-account");

  deleteDataBtn?.addEventListener("click", async () => {
    const ok = await openAppConfirm({
      title: "Delete all data",
      message:
        "This will permanently delete all businesses, agent chats, runs, integrations, database connections, invoices, and notifications for this account. Your login and settings will remain. This cannot be undone.",
      confirmLabel: "Delete all data",
    });
    if (!ok) {
      return;
    }
    try {
      await settingsApiJson("/api/settings/delete-all-data", { method: "POST" });
      window.location.href = "/";
    } catch (err) {
      console.error(err);
      await openAppConfirm({
        title: "Could not delete data",
        message: err instanceof Error ? err.message : "Something went wrong.",
        confirmLabel: "OK",
      });
    }
  });

  deleteAccountBtn?.addEventListener("click", async () => {
    const ok = await openAppConfirm({
      title: "Delete account",
      message:
        "This permanently deletes your MultiWorkAgent account and all data tied to it. You will be signed out immediately. This cannot be undone.",
      confirmLabel: "Delete account",
    });
    if (!ok) {
      return;
    }
    try {
      const data = await settingsApiJson("/api/settings/delete-account", { method: "POST" });
      window.location.href = data.redirect || "/signup";
    } catch (err) {
      console.error(err);
      await openAppConfirm({
        title: "Could not delete account",
        message: err instanceof Error ? err.message : "Something went wrong.",
        confirmLabel: "OK",
      });
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initNotificationPrefs();
  initAgentPrefs();
  initDangerZone();
});
