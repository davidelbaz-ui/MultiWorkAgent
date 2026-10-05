async function businessApiJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

async function updateBusiness(businessId, payload) {
  return businessApiJson(`/api/businesses/${businessId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function openAddBusinessWizard() {
  const ctx = { name: "", industry: "" };

  return openAppWizard({
    title: "Add business",
    finishLabel: "Create business",
    ctx,
    steps: [
      {
        id: "intro",
        title: "Workspace",
        render(container) {
          container.appendChild(
            wizardPanel("What is a business?", [
              "A business is a workspace with its own integrations, databases, chats, and agent runs.",
              "You can run many businesses from one login. Data never mixes between them.",
            ]),
          );
        },
      },
      {
        id: "name",
        title: "Name",
        render(container, c) {
          const panel = wizardPanel("Business name", [
            "Use the legal name, brand, or internal label you will recognize in the switcher.",
          ]);
          const field = document.createElement("div");
          field.className = "app-wizard-field";
          field.innerHTML =
            '<label for="business-wizard-name">Name</label>' +
            '<input type="text" id="business-wizard-name" autocomplete="organization" maxlength="120">';
          const input = field.querySelector("#business-wizard-name");
          input.value = c.name;
          input.addEventListener("input", () => {
            c.name = input.value;
          });
          panel.appendChild(field);
          container.appendChild(panel);
        },
        validate(c) {
          if (!(c.name || "").trim()) {
            return "Enter a business name.";
          }
          return true;
        },
      },
      {
        id: "industry",
        title: "Industry",
        render(container, c) {
          const panel = wizardPanel("Industry (optional)", [
            "Helps you organize cards and gives the agent light context (e.g. E-commerce, Agency, SaaS).",
          ]);
          const field = document.createElement("div");
          field.className = "app-wizard-field";
          field.innerHTML =
            '<label for="business-wizard-industry">Industry</label>' +
            '<input type="text" id="business-wizard-industry" autocomplete="off" maxlength="80">';
          const input = field.querySelector("#business-wizard-industry");
          input.value = c.industry;
          input.addEventListener("input", () => {
            c.industry = input.value;
          });
          panel.appendChild(field);
          container.appendChild(panel);
        },
      },
      {
        id: "review",
        title: "Review",
        render(container, c) {
          container.appendChild(
            wizardPanel("Ready to create", [
              `Name: ${c.name.trim()}`,
              c.industry.trim()
                ? `Industry: ${c.industry.trim()}`
                : "Industry: (none)",
              "You can rename or archive this workspace later from the Businesses page.",
            ]),
          );
        },
      },
    ],
    async onFinish(c) {
      await businessApiJson("/api/businesses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: c.name.trim(),
          industry: c.industry.trim(),
        }),
      });
      window.location.reload();
    },
  });
}

function initAddBusiness() {
  const button = document.getElementById("add-business-btn");
  if (!button) {
    return;
  }

  button.addEventListener("click", () => {
    void openAddBusinessWizard().catch((err) => console.error(err));
  });
}

function initBusinessCardActions() {
  document.querySelector(".business-grid")?.addEventListener("click", async (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const renameBtn = target.closest(".business-edit-name-btn");
    if (renameBtn instanceof HTMLElement) {
      const businessId = renameBtn.dataset.businessId;
      const current = renameBtn.dataset.businessName || "";
      if (!businessId) {
        return;
      }
      const next = await openAppPrompt({
        title: "Rename business",
        label: "Business name",
        defaultValue: current,
      });
      if (next === null) {
        return;
      }
      const trimmed = next.trim();
      if (!trimmed || trimmed === current) {
        return;
      }
      try {
        await updateBusiness(businessId, { name: trimmed });
        window.location.reload();
      } catch (err) {
        console.error(err);
      }
      return;
    }

    const industryBtn = target.closest(".business-edit-industry-btn");
    if (industryBtn instanceof HTMLElement) {
      const businessId = industryBtn.dataset.businessId;
      const current = industryBtn.dataset.businessIndustry || "";
      if (!businessId) {
        return;
      }
      const next = await openAppPrompt({
        title: "Industry",
        label: "Industry (optional)",
        defaultValue: current,
      });
      if (next === null) {
        return;
      }
      try {
        await updateBusiness(businessId, { industry: next.trim() });
        window.location.reload();
      } catch (err) {
        console.error(err);
      }
      return;
    }

    const archiveBtn = target.closest(".business-archive-btn");
    if (archiveBtn instanceof HTMLElement) {
      const businessId = archiveBtn.dataset.businessId;
      const label = archiveBtn.dataset.businessName || "this business";
      if (!businessId) {
        return;
      }
      const ok = await openAppConfirm({
        title: "Archive business",
        message: `Archive “${label}”? It will be hidden from lists and search until restored.`,
        confirmLabel: "Archive",
      });
      if (!ok) {
        return;
      }
      try {
        await updateBusiness(businessId, { archived: true });
        window.location.reload();
      } catch (err) {
        console.error(err);
      }
      return;
    }

    const deleteBtn = target.closest(".business-delete-btn");
    if (deleteBtn instanceof HTMLElement) {
      const businessId = deleteBtn.dataset.businessId;
      const label = deleteBtn.dataset.businessName || "this business";
      if (!businessId) {
        return;
      }
      const ok = await openAppConfirm({
        title: "Delete business",
        message: `Permanently delete “${label}”? This cannot be undone.`,
        confirmLabel: "Delete",
      });
      if (!ok) {
        return;
      }
      try {
        await businessApiJson(`/api/businesses/${businessId}`, { method: "DELETE" });
        window.location.reload();
      } catch (err) {
        console.error(err);
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initAddBusiness();
  initBusinessCardActions();
});
