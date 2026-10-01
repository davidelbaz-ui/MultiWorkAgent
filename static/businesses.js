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

function initAddBusiness() {
  const button = document.getElementById("add-business-btn");
  if (!button) {
    return;
  }

  button.addEventListener("click", async () => {
    const name = await openAppPrompt({
      title: "Add business",
      label: "Business name",
      defaultValue: "",
    });
    if (name === null) {
      return;
    }
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }

    const industry = await openAppPrompt({
      title: "Add business",
      label: "Industry (optional)",
      defaultValue: "",
    });
    const industryValue = industry === null ? "" : industry.trim();

    try {
      await businessApiJson("/api/businesses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed, industry: industryValue }),
      });
      window.location.reload();
    } catch (err) {
      console.error(err);
    }
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
