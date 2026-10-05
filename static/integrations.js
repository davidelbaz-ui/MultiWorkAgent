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

const INTEGRATION_API_KEY_HELP = {
  render:
    "In Render: open Account Settings → API Keys → Create API Key. Copy the key immediately — Render only shows it once.",
  github:
    "GitHub → Settings → Developer settings → Personal access tokens (or fine-grained tokens). Grant the repo/read scopes you need, then copy the token.",
  gitlab:
    "GitLab → Preferences → Access tokens. Create a token with api or read_api scope and copy it.",
  netlify:
    "Netlify → User settings → Applications → Personal access tokens → New token.",
  vercel:
    "Vercel → Account Settings → Tokens → Create. Copy the token — use a scoped token when possible.",
  stripe:
    "Stripe Dashboard → Developers → API keys. Use a restricted key where possible (secret key starts with sk_).",
};

function apiKeyHelpText(slug, name) {
  if (INTEGRATION_API_KEY_HELP[slug]) {
    return INTEGRATION_API_KEY_HELP[slug];
  }
  return (
    `Sign in to ${name}, open account or developer settings, and create an API key or personal access token. ` +
    "Copy it before you leave the page — most providers only show it once."
  );
}

function openSelectBusinessWizard() {
  return openAppWizard({
    title: "Select a business",
    finishLabel: "Got it",
    steps: [
      {
        id: "scope",
        title: "Workspace",
        render(container) {
          container.appendChild(
            wizardPanel("Choose one business first", [
              "Integrations connect to a single business workspace.",
              "Use the business switcher in the top bar and pick one company (not “All businesses”).",
              "Then open this provider again from the catalog.",
            ]),
          );
        },
      },
    ],
    onFinish: () => {},
  });
}

async function startOAuthConnect(ctx) {
  const data = await integrationApiJson(
    `/api/businesses/${ctx.businessId}/integrations/oauth/start`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider_slug: ctx.slug }),
    },
  );
  if (data.authorize_url) {
    window.location.href = data.authorize_url;
    return;
  }
  throw new Error("OAuth did not return an authorization URL.");
}

async function saveApiKeyConnect(ctx) {
  const trimmed = (ctx.apiKey || "").trim();
  if (!trimmed) {
    throw new Error("Enter an API key.");
  }
  await integrationApiJson(`/api/businesses/${ctx.businessId}/integrations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider_slug: ctx.slug,
      auth_type: "api_key",
      api_key: trimmed,
    }),
  });
  window.location.reload();
}

function buildIntegrationWizardConfig(ctx) {
  const steps = [
    {
      id: "intro",
      title: "Overview",
      render(container, c) {
        container.appendChild(
          wizardPanel(`Connect ${c.name}`, [
            `You are linking ${c.name} to the business selected in the header.`,
            "Each business keeps its own connections. Nothing is shared across workspaces.",
          ]),
        );
      },
    },
  ];

  if (ctx.oauthConfigured) {
    steps.push({
      id: "method",
      title: "How to connect",
      render(container, c) {
        const panel = wizardPanel("Choose a connection type", [
          "OAuth opens the provider’s sign-in page with your account.",
          "API key is for tokens you create in the provider’s dashboard.",
        ]);
        const list = document.createElement("div");
        list.className = "app-wizard-choice-list";
        list.innerHTML = `
          <label class="app-wizard-choice">
            <input type="radio" name="integration-auth-method" value="oauth" ${c.authMethod === "oauth" ? "checked" : ""}>
            <span class="app-wizard-choice-text">
              <strong>OAuth (recommended)</strong>
              <span>Sign in with ${c.name}. We store an access token, not your password.</span>
            </span>
          </label>
          <label class="app-wizard-choice">
            <input type="radio" name="integration-auth-method" value="api_key" ${c.authMethod === "api_key" ? "checked" : ""}>
            <span class="app-wizard-choice-text">
              <strong>API key</strong>
              <span>Paste a personal access token or API key from ${c.name}.</span>
            </span>
          </label>`;
        list.querySelectorAll('input[name="integration-auth-method"]').forEach((input) => {
          input.addEventListener("change", () => {
            c.authMethod = input.value;
          });
        });
        panel.appendChild(list);
        container.appendChild(panel);
      },
      validate(c) {
        if (!c.authMethod) {
          return "Choose OAuth or API key.";
        }
        return true;
      },
    });
  } else {
    ctx.authMethod = "api_key";
    steps.push({
      id: "method",
      title: "How to connect",
      render(container, c) {
        container.appendChild(
          wizardPanel("Connect with an API key", [
            `An API key from your ${c.name} account is the only way to connect here.`,
            "Paste it on the last step. We encrypt it and never show it again.",
          ]),
        );
      },
    });
  }

  steps.push({
    id: "instructions",
    title: "Instructions",
    render(container, c) {
      if (c.authMethod === "oauth") {
        container.appendChild(
          wizardPanel(`Authorize with ${c.name}`, [
            "On the next step you will leave MultiWorkAgent and approve access on the provider’s site.",
            "We save an encrypted token for this business only so the agent can call the API on your behalf.",
            "You can disconnect anytime from Connected integrations.",
          ]),
        );
      } else {
        container.appendChild(
          wizardPanel(`Get your ${c.name} API key`, [apiKeyHelpText(c.slug, c.name)]),
        );
      }
    },
  });

  steps.push({
    id: "privacy",
    title: "Privacy",
    render(container, c) {
      container.appendChild(wizardPrivacyCallout());
      if (c.authMethod === "api_key") {
        const field = document.createElement("div");
        field.className = "app-wizard-field";
        field.innerHTML = `
          <label for="integration-wizard-api-key">Paste API key</label>
          <input type="password" id="integration-wizard-api-key" autocomplete="off" spellcheck="false" placeholder="Starts with your provider prefix…">`;
        const input = field.querySelector("#integration-wizard-api-key");
        input.value = c.apiKey || "";
        input.addEventListener("input", () => {
          c.apiKey = input.value;
        });
        container.appendChild(field);
      } else {
        const p = document.createElement("p");
        p.className = "app-wizard-copy";
        p.textContent =
          "Click Connect with OAuth to open the provider. Your password stays with them — we only receive an access token.";
        container.appendChild(p);
      }
    },
    validate(c) {
      if (c.authMethod === "api_key" && !(c.apiKey || "").trim()) {
        return "Paste your API key to continue.";
      }
      return true;
    },
  });

  return {
    title: `Connect ${ctx.name}`,
    finishLabelForCtx: (c) =>
      c.authMethod === "oauth" ? "Connect with OAuth" : "Save connection",
    steps,
    ctx,
    async onFinish(c) {
      if (c.authMethod === "oauth") {
        await startOAuthConnect(c);
        return;
      }
      await saveApiKeyConnect(c);
    },
  };
}

function openIntegrationConnectWizard(ctx) {
  if (!ctx.authMethod) {
    ctx.authMethod = ctx.oauthConfigured ? "" : "api_key";
  }
  const config = buildIntegrationWizardConfig(ctx);
  return openAppWizard(config);
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
        await openSelectBusinessWizard();
        return;
      }

      const oauthAvailable = tile.dataset.oauthAvailable === "true";
      const oauthConfigured = tile.dataset.oauthConfigured === "true";

      try {
        await openIntegrationConnectWizard({
          slug,
          name,
          businessId: selectedBusinessId,
          oauthAvailable,
          oauthConfigured,
          authMethod: "",
          apiKey: "",
        });
      } catch (err) {
        console.error(err);
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
      const tileName = tile.dataset.name || tile.textContent.toLowerCase();
      const show = !q || tileName.includes(q);
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
