async function billingApiJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function initBillingSubscribe() {
  const card = document.getElementById("billing-page");
  if (!card) {
    return;
  }
  const mode = card.dataset.billingMode || "unconfigured";
  const isOwner = card.dataset.accountRole === "owner";
  const currentPlan = card.dataset.currentPlan || "";

  document.querySelectorAll("[data-billing-plan]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!isOwner) {
        await openAppConfirm({
          title: "Billing",
          message: "Only account owners can change subscription plans.",
          confirmLabel: "OK",
        });
        return;
      }

      const plan = btn.dataset.billingPlan;
      if (!plan) {
        return;
      }
      if (currentPlan && btn.textContent?.includes("current")) {
        return;
      }

      if (plan === "topup") {
        await openAppConfirm({
          title: "Top-up",
          message: "Credit top-ups will be available after usage metering (#13) is wired.",
          confirmLabel: "OK",
        });
        return;
      }

      try {
        const data = await billingApiJson("/api/billing/checkout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan }),
        });
        if (data.checkout_url) {
          window.location.href = data.checkout_url;
          return;
        }
        window.location.reload();
      } catch (err) {
        console.error(err);
        await openAppConfirm({
          title: "Checkout failed",
          message: err.message || "Could not start checkout.",
          confirmLabel: "OK",
        });
      }
    });
  });

  const cancelBtn = document.getElementById("billing-cancel-subscription");
  cancelBtn?.addEventListener("click", async () => {
    if (!isOwner) {
      return;
    }
    const ok = await openAppConfirm({
      title: "Cancel subscription",
      message:
        "Cancel at the end of the current billing period? You keep access until the period ends.",
      confirmLabel: "Cancel at period end",
    });
    if (!ok) {
      return;
    }
    try {
      await billingApiJson("/api/billing/cancel", { method: "POST" });
      window.location.reload();
    } catch (err) {
      console.error(err);
      await openAppConfirm({
        title: "Could not cancel",
        message: err.message || "Request failed.",
        confirmLabel: "OK",
      });
    }
  });

  if (mode === "mock") {
    const note = document.getElementById("billing-mode-note");
    if (note) {
      note.hidden = false;
    }
  }

  document.getElementById("billing-sync-invoices")?.addEventListener("click", async () => {
    if (!isOwner) {
      return;
    }
    try {
      await billingApiJson("/api/billing/invoices/sync", { method: "POST" });
      window.location.reload();
    } catch (err) {
      console.error(err);
      await openAppConfirm({
        title: "Sync failed",
        message: err.message || "Could not sync invoices from Square.",
        confirmLabel: "OK",
      });
    }
  });
}

document.addEventListener("DOMContentLoaded", initBillingSubscribe);
