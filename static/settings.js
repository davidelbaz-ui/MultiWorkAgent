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
  initTeamInvites();
});

function initTeamInvites() {
  const inviteBtn = document.getElementById("settings-invite-teammate");
  if (!inviteBtn || typeof openAppWizard !== "function") {
    return;
  }

  const ctx = {
    email: "",
    role: "operator",
  };

  inviteBtn.addEventListener("click", () => {
    ctx.email = "";
    ctx.role = "operator";
    void openAppWizard({
      title: "Invite teammate",
      finishLabel: "Send invite",
      steps: [
        {
          id: "email",
          title: "Email",
          validate(wizardCtx) {
            const input = document.getElementById("team-invite-email");
            const email =
              input instanceof HTMLInputElement ? input.value.trim() : wizardCtx.email;
            if (!email) {
              return "Enter an email address.";
            }
            wizardCtx.email = email;
            return true;
          },
          render(body, wizardCtx) {
            const label = document.createElement("label");
            label.className = "app-wizard-field";
            label.innerHTML = `Email address<input type="email" class="app-wizard-input" id="team-invite-email" autocomplete="email" placeholder="teammate@company.com">`;
            body.appendChild(label);
            const hint = document.createElement("p");
            hint.className = "meta-row";
            hint.textContent =
              "They must sign in with this email to accept. If they do not have an account yet, they can sign up first.";
            body.appendChild(hint);
            const input = label.querySelector("input");
            input?.addEventListener("input", () => {
              wizardCtx.email = input.value.trim();
            });
            requestAnimationFrame(() => input?.focus());
          },
        },
        {
          id: "role",
          title: "Role",
          render(body, wizardCtx) {
            const fieldset = document.createElement("fieldset");
            fieldset.className = "app-wizard-fieldset";
            fieldset.innerHTML = `
              <legend class="app-wizard-legend">Choose a role</legend>
              <label class="app-wizard-radio"><input type="radio" name="team-invite-role" value="operator" checked> Operator — run agent and edit data</label>
              <label class="app-wizard-radio"><input type="radio" name="team-invite-role" value="viewer"> Viewer — read-only</label>`;
            body.appendChild(fieldset);
            fieldset.querySelectorAll('input[name="team-invite-role"]').forEach((input) => {
              input.addEventListener("change", () => {
                if (input instanceof HTMLInputElement && input.checked) {
                  wizardCtx.role = input.value;
                }
              });
            });
          },
        },
        {
          id: "review",
          title: "Review",
          render(body, wizardCtx) {
            const roleLabel = wizardCtx.role === "viewer" ? "Viewer" : "Operator";
            const p = document.createElement("p");
            p.textContent = `Send an invitation to ${wizardCtx.email || "(email)"} as ${roleLabel}. They will see Accept and Decline in their notifications.`;
            body.appendChild(p);
          },
        },
      ],
      ctx,
      onFinish: async (wizardCtx) => {
        const emailInput = document.getElementById("team-invite-email");
        if (emailInput instanceof HTMLInputElement) {
          wizardCtx.email = emailInput.value.trim();
        }
        if (!wizardCtx.email) {
          throw new Error("Enter an email address.");
        }
        await settingsApiJson("/api/team/invites", {
          method: "POST",
          body: JSON.stringify({ email: wizardCtx.email, role: wizardCtx.role }),
        });
        window.location.reload();
      },
    });
  });

  document.getElementById("settings-pending-invites")?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".settings-cancel-invite");
    if (!(btn instanceof HTMLElement)) {
      return;
    }
    const inviteId = btn.dataset.inviteId;
    if (!inviteId) {
      return;
    }
    const ok = await openAppConfirm({
      title: "Cancel invite",
      message: "Withdraw this invitation?",
      confirmLabel: "Cancel invite",
    });
    if (!ok) {
      return;
    }
    try {
      await settingsApiJson(`/api/team/invites/${encodeURIComponent(inviteId)}`, {
        method: "DELETE",
      });
      btn.closest(".settings-pending-invite")?.remove();
    } catch (err) {
      console.error(err);
    }
  });
}
