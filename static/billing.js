async function billingApiJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(
      data.error || data.message || `Request failed (${res.status})`,
    );
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function readPlanCatalog() {
  const el = document.getElementById("billing-plan-catalog-data");
  if (!el?.textContent) {
    return [];
  }
  try {
    const parsed = JSON.parse(el.textContent);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function selectedBillingInterval() {
  const checked = document.querySelector('input[name="billing-interval"]:checked');
  return checked?.value === "annual" ? "annual" : "monthly";
}

function selectedChangePlanInterval() {
  const checked = document.querySelector('input[name="billing-change-interval"]:checked');
  return checked?.value === "annual" ? "annual" : "monthly";
}

function applyBillingIntervalDisplay() {
  const card = document.getElementById("billing-page");
  const interval = selectedBillingInterval();
  if (card) {
    card.dataset.billingInterval = interval;
  }
}

async function startCheckout(plan, billingInterval) {
  const data = await billingApiJson("/api/billing/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan, billing_interval: billingInterval }),
  });
  if (data.checkout_url) {
    window.location.href = data.checkout_url;
    return;
  }
  window.location.reload();
}

function planPriceForInterval(item, interval) {
  return interval === "annual" ? item.annual_price : item.monthly_price;
}

function planPriceSuffix(interval) {
  return interval === "annual" ? "/yr" : "/mo";
}

function closeChangePlanModal() {
  const root = document.getElementById("billing-change-plan-root");
  if (!root) {
    return;
  }
  void uiCloseOverlay(root, "is-open", root.querySelector(".app-dialog") || undefined);
}

function renderChangePlanList() {
  const card = document.getElementById("billing-page");
  const list = document.getElementById("billing-change-plan-list");
  if (!card || !list) {
    return;
  }
  const currentTier = card.dataset.currentTier || "";
  const interval = selectedChangePlanInterval();
  const catalog = readPlanCatalog().filter((item) => item.tier !== currentTier);
  list.innerHTML = "";
  if (!catalog.length) {
    const empty = document.createElement("p");
    empty.className = "meta-row";
    empty.textContent = "No other plans available.";
    list.appendChild(empty);
    return;
  }
  catalog.forEach((item) => {
    const row = document.createElement("article");
    row.className = "billing-change-plan-item";
    row.innerHTML = `
      <div class="billing-change-plan-item__main">
        <h3 class="billing-change-plan-item__name">${item.display_name}</h3>
        <p class="billing-change-plan-item__price">
          <strong>${planPriceForInterval(item, interval)}</strong>
          <span class="billing-price-suffix">${planPriceSuffix(interval)}</span>
        </p>
        <p class="billing-change-plan-item__freq">Billed every ${interval === "annual" ? "year" : "month"}</p>
        <p class="billing-change-plan-item__quota">${item.monthly_quota} runs / month</p>
      </div>
      <button type="button" class="btn btn-primary btn-sm" data-change-plan-tier="${item.tier}">Select</button>`;
    row.querySelector("[data-change-plan-tier]")?.addEventListener("click", async () => {
      const tier = item.tier;
      try {
        await startCheckout(tier, interval);
      } catch (err) {
        console.error(err);
        await openAppConfirm({
          title: "Checkout failed",
          message: err.message || "Could not start checkout.",
          confirmLabel: "OK",
        });
      }
    });
    list.appendChild(row);
  });
}

async function openChangePlanModal() {
  const root = document.getElementById("billing-change-plan-root");
  if (!root) {
    return;
  }
  const card = document.getElementById("billing-page");
  const currentInterval = card?.dataset.currentInterval || "monthly";
  const input =
    document.querySelector(`input[name="billing-change-interval"][value="${currentInterval}"]`) ||
    document.querySelector('input[name="billing-change-interval"][value="monthly"]');
  if (input) {
    input.checked = true;
  }
  renderChangePlanList();
  await uiOpenOverlay(root, "is-open", root.querySelector(".app-dialog") || undefined);
}

function initBillingSubscribe() {
  const card = document.getElementById("billing-page");
  if (!card) {
    return;
  }
  const mode = card.dataset.billingMode || "unconfigured";
  const isOwner = card.dataset.accountRole === "owner";
  const subscribed = Boolean(document.querySelector(".billing-plans-section--subscribed"));

  if (!subscribed) {
    document.querySelectorAll('input[name="billing-interval"]').forEach((input) => {
      input.addEventListener("change", applyBillingIntervalDisplay);
    });
    applyBillingIntervalDisplay();

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
        try {
          await startCheckout(plan, selectedBillingInterval());
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
  }

  document.getElementById("billing-change-plan")?.addEventListener("click", () => {
    if (!isOwner) {
      return;
    }
    void openChangePlanModal();
  });

  document.querySelectorAll('input[name="billing-change-interval"]').forEach((input) => {
    input.addEventListener("change", renderChangePlanList);
  });

  document.getElementById("billing-change-plan-close")?.addEventListener("click", closeChangePlanModal);
  document.getElementById("billing-change-plan-backdrop")?.addEventListener("click", closeChangePlanModal);

  document.getElementById("billing-cancel-plan")?.addEventListener("click", async () => {
    if (!isOwner) {
      return;
    }
    const ok = await openAppConfirm({
      title: "Cancel plan",
      message:
        "Cancel at the end of the current billing period? You keep this plan and your monthly run quota until the period ends.",
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
        message: err.message || "Could not refresh invoices.",
        confirmLabel: "OK",
      });
    }
  });
}

document.addEventListener("DOMContentLoaded", initBillingSubscribe);
