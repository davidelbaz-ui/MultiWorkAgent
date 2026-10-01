async function integrationApiJson(url, options = {}) {
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

function initIntegrationCatalogSearch() {
  const input = document.getElementById("integration-search");
  const clearBtn = document.getElementById("integration-search-clear");
  const catalog = document.getElementById("integration-catalog");
  const empty = document.getElementById("integration-no-results");
  if (!input || !catalog) {
    return;
  }

  const categories = catalog.querySelectorAll(".integration-category");
  const tiles = catalog.querySelectorAll(".integration-tile");
  const selectedBusinessId = catalog.dataset.selectedBusinessId || "";

  tiles.forEach((tile) => {
    tile.addEventListener("click", async () => {
      const slug = tile.dataset.slug;
      const name = tile.textContent?.trim() || slug;
      if (!selectedBusinessId) {
        await openAppConfirm({
          title: "Select a business",
          message:
            "Choose one business in the header switcher (not “All businesses”), then connect this provider again.",
          confirmLabel: "OK",
        });
        return;
      }

      const oauthAvailable = tile.dataset.oauthAvailable === "true";
      const oauthConfigured = tile.dataset.oauthConfigured === "true";
      let useOAuth = false;
      if (oauthAvailable) {
        const oauthMessage = oauthConfigured
          ? "Use OAuth authorization? Choose Cancel to paste an API key instead."
          : "OAuth is defined for this provider but not enabled on this server yet. Use an API key, or choose OAuth to see details.";
        useOAuth = await openAppConfirm({
          title: `Connect ${name}`,
          message: oauthMessage,
          confirmLabel: "OAuth",
          cancelLabel: "API key",
        });
      }

      try {
        if (useOAuth) {
          const data = await integrationApiJson(
            `/api/businesses/${selectedBusinessId}/integrations/oauth/start`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ provider_slug: slug }),
            },
          );
          if (data.authorize_url) {
            window.location.href = data.authorize_url;
            return;
          }
        } else {
          const apiKey = await openAppPrompt({
            title: `Connect ${name}`,
            label: "API key",
            defaultValue: "",
          });
          if (apiKey === null) {
            return;
          }
          const trimmed = apiKey.trim();
          if (!trimmed) {
            return;
          }
          await integrationApiJson(`/api/businesses/${selectedBusinessId}/integrations`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              provider_slug: slug,
              auth_type: "api_key",
              api_key: trimmed,
            }),
          });
        }
        window.location.reload();
      } catch (err) {
        console.error(err);
        if (err.data?.operator_detail) {
          console.info("Operator:", err.data.operator_detail);
        }
        await openAppConfirm({
          title: "Connection failed",
          message: err.message || "Could not save connection.",
          confirmLabel: "OK",
        });
      }
    });
  });

  const syncClear = () => {
    if (!clearBtn) {
      return;
    }
    const hasText = input.value.trim().length > 0;
    clearBtn.classList.toggle("is-visible", hasText);
    clearBtn.setAttribute("aria-hidden", hasText ? "false" : "true");
    clearBtn.tabIndex = hasText ? 0 : -1;
  };

  const applyFilter = () => {
    const q = input.value.trim().toLowerCase();
    let visibleTiles = 0;

    tiles.forEach((tile) => {
      const name = tile.dataset.name || tile.textContent.toLowerCase();
      const show = !q || name.includes(q);
      tile.hidden = !show;
      if (show) {
        visibleTiles += 1;
      }
    });

    categories.forEach((section) => {
      const anyVisible = section.querySelector(".integration-tile:not([hidden])");
      section.hidden = !anyVisible;
    });

    if (empty) {
      if (visibleTiles > 0) {
        void uiHideElement(empty);
      } else if (q) {
        void uiShowElement(empty);
      } else {
        void uiHideElement(empty);
      }
    }
    syncClear();
  };

  input.addEventListener("input", applyFilter);

  clearBtn?.addEventListener("click", () => {
    input.value = "";
    input.focus();
    applyFilter();
  });

  syncClear();
}

function initIntegrationDisconnect() {
  document.querySelector(".integration-connections-list")?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".integration-disconnect-btn");
    if (!(btn instanceof HTMLElement)) {
      return;
    }
    const connectionId = btn.dataset.connectionId;
    const businessId = btn.dataset.businessId;
    const providerName = btn.dataset.providerName || "this integration";
    if (!connectionId || !businessId) {
      return;
    }
    const ok = await openAppConfirm({
      title: "Disconnect integration",
      message: `Disconnect ${providerName}? The agent will lose access until you connect again.`,
      confirmLabel: "Disconnect",
    });
    if (!ok) {
      return;
    }
    try {
      await integrationApiJson(
        `/api/businesses/${businessId}/integrations/${connectionId}`,
        { method: "DELETE" },
      );
      window.location.reload();
    } catch (err) {
      console.error(err);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initIntegrationCatalogSearch();
  initIntegrationDisconnect();
});
