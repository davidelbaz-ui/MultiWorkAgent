async function databaseApiJson(url, options = {}) {
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

function parseOptionalPort(raw) {
  if (raw === null || raw === undefined) {
    return null;
  }
  const trimmed = String(raw).trim();
  if (!trimmed) {
    return null;
  }
  const n = Number.parseInt(trimmed, 10);
  if (!Number.isFinite(n) || n < 1 || n > 65535) {
    throw new Error("Port must be between 1 and 65535.");
  }
  return n;
}

function formatSchemaMessage(schema) {
  if (!schema || !Array.isArray(schema.tables)) {
    return "No schema data.";
  }
  const lines = schema.tables.slice(0, 25).map((t) => {
    const cols = (t.columns || [])
      .slice(0, 8)
      .map((c) => c.name)
      .join(", ");
    const suffix = (t.columns || []).length > 8 ? "…" : "";
    return `${t.name}: ${cols}${suffix}`;
  });
  const extra =
    schema.tables.length > 25
      ? `\n… and ${schema.tables.length - 25} more tables.`
      : "";
  return lines.join("\n") + extra;
}

function defaultPortForEngine(engine) {
  if (engine === "postgresql") {
    return "5432";
  }
  if (engine === "mysql") {
    return "3306";
  }
  return "";
}

function buildDatabaseConnectionPayload(ctx) {
  const engine = ctx.engine;
  const body = {
    name: ctx.name.trim(),
    engine,
    host: (ctx.host || "").trim(),
    database_name: (ctx.databaseName || "").trim(),
    username: (ctx.username || "").trim(),
    password: ctx.password || "",
    access_mode: ctx.accessMode === "read_write" ? "read_write" : "read",
  };
  if (engine !== "sqlite") {
    const port = parseOptionalPort(ctx.port);
    if (port !== null) {
      body.port = port;
    }
  }
  return body;
}

function buildDatabaseWizardConfig(businessId) {
  const ctx = {
    businessId,
    name: "",
    engine: "sqlite",
    host: "127.0.0.1",
    port: "",
    databaseName: "",
    username: "",
    password: "",
    accessMode: "read",
  };

  const steps = [
    {
      id: "intro",
      title: "Overview",
      render(container) {
        container.appendChild(
          wizardPanel("Connect a database", [
            "Link a database to the business selected in the header.",
            "The agent can read schema metadata and run queries within the access mode you choose.",
            "Credentials are encrypted and scoped to this business only.",
          ]),
        );
      },
    },
    {
      id: "name",
      title: "Name",
      render(container, c) {
        const panel = wizardPanel("Connection name", [
          "A short label you will recognize in the list (e.g. Production Postgres, Analytics SQLite).",
        ]);
        const field = document.createElement("div");
        field.className = "app-wizard-field";
        field.innerHTML =
          '<label for="database-wizard-name">Display name</label>' +
          '<input type="text" id="database-wizard-name" autocomplete="off" maxlength="120">';
        const input = field.querySelector("#database-wizard-name");
        input.value = c.name;
        input.addEventListener("input", () => {
          c.name = input.value;
        });
        panel.appendChild(field);
        container.appendChild(panel);
      },
      validate(c) {
        if (!(c.name || "").trim()) {
          return "Enter a connection name.";
        }
        return true;
      },
    },
    {
      id: "engine",
      title: "Engine",
      render(container, c) {
        const panel = wizardPanel("Database engine", [
          "SQLite uses a file path on the server running MultiWorkAgent (local dev or your host).",
          "PostgreSQL and MySQL use host, port, database name, and login credentials.",
        ]);
        const list = document.createElement("div");
        list.className = "app-wizard-choice-list";
        const engines = [
          { value: "sqlite", label: "SQLite", hint: "File path to .sqlite / .db" },
          { value: "postgresql", label: "PostgreSQL", hint: "Host + database + user" },
          { value: "mysql", label: "MySQL", hint: "Host + database + user" },
        ];
        list.innerHTML = engines
          .map(
            (e) => `
          <label class="app-wizard-choice">
            <input type="radio" name="database-wizard-engine" value="${e.value}" ${
              c.engine === e.value ? "checked" : ""
            }>
            <span class="app-wizard-choice-text">
              <strong>${e.label}</strong>
              <span>${e.hint}</span>
            </span>
          </label>`,
          )
          .join("");
        list.querySelectorAll('input[name="database-wizard-engine"]').forEach((input) => {
          input.addEventListener("change", () => {
            c.engine = input.value;
            if (c.engine === "postgresql" || c.engine === "mysql") {
              if (!c.port) {
                c.port = defaultPortForEngine(c.engine);
              }
            }
          });
        });
        panel.appendChild(list);
        container.appendChild(panel);
      },
      validate(c) {
        if (!["sqlite", "postgresql", "mysql"].includes(c.engine)) {
          return "Choose a database engine.";
        }
        return true;
      },
    },
    {
      id: "connection",
      title: "Connection",
      render(container, c) {
        if (c.engine === "sqlite") {
          const panel = wizardPanel("SQLite file", [
            "Path to the database file on the app server. Use an absolute path in production.",
          ]);
          const field = document.createElement("div");
          field.className = "app-wizard-field";
          field.innerHTML =
            '<label for="database-wizard-path">File path</label>' +
            '<input type="text" id="database-wizard-path" autocomplete="off" placeholder="/path/to/data.sqlite">';
          const input = field.querySelector("#database-wizard-path");
          input.value = c.databaseName;
          input.addEventListener("input", () => {
            c.databaseName = input.value;
          });
          panel.appendChild(field);
          container.appendChild(panel);
          return;
        }

        const panel = wizardPanel(`${c.engine === "mysql" ? "MySQL" : "PostgreSQL"} connection`, [
          "Host must be reachable from where MultiWorkAgent runs (your machine locally, Vercel in production).",
        ]);

        const hostField = document.createElement("div");
        hostField.className = "app-wizard-field";
        hostField.innerHTML =
          '<label for="database-wizard-host">Host</label>' +
          '<input type="text" id="database-wizard-host" autocomplete="off">';
        const portField = document.createElement("div");
        portField.className = "app-wizard-field";
        portField.innerHTML =
          `<label for="database-wizard-port">Port</label>` +
          `<input type="text" id="database-wizard-port" inputmode="numeric" autocomplete="off" placeholder="${defaultPortForEngine(c.engine)}">`;
        const dbField = document.createElement("div");
        dbField.className = "app-wizard-field";
        dbField.innerHTML =
          '<label for="database-wizard-db">Database name</label>' +
          '<input type="text" id="database-wizard-db" autocomplete="off">';
        const userField = document.createElement("div");
        userField.className = "app-wizard-field";
        userField.innerHTML =
          '<label for="database-wizard-user">Username</label>' +
          '<input type="text" id="database-wizard-user" autocomplete="off">';
        const passField = document.createElement("div");
        passField.className = "app-wizard-field";
        passField.innerHTML =
          '<label for="database-wizard-password">Password</label>' +
          '<input type="password" id="database-wizard-password" autocomplete="off">';

        panel.append(hostField, portField, dbField, userField, passField);
        const port = panel.querySelector("#database-wizard-port");
        const db = panel.querySelector("#database-wizard-db");
        const user = panel.querySelector("#database-wizard-user");
        const pass = panel.querySelector("#database-wizard-password");
        host.value = c.host || "127.0.0.1";
        port.value = c.port || defaultPortForEngine(c.engine);
        db.value = c.databaseName || "";
        user.value = c.username || "";
        pass.value = c.password || "";
        host.addEventListener("input", () => {
          c.host = host.value;
        });
        port.addEventListener("input", () => {
          c.port = port.value;
        });
        db.addEventListener("input", () => {
          c.databaseName = db.value;
        });
        user.addEventListener("input", () => {
          c.username = user.value;
        });
        pass.addEventListener("input", () => {
          c.password = pass.value;
        });

        container.appendChild(panel);
      },
      validate(c) {
        if (c.engine === "sqlite") {
          if (!(c.databaseName || "").trim()) {
            return "Enter the SQLite file path.";
          }
          return true;
        }
        if (!(c.host || "").trim()) {
          return "Enter a hostname.";
        }
        try {
          parseOptionalPort(c.port);
        } catch (err) {
          return err instanceof Error ? err.message : "Invalid port.";
        }
        if (!(c.databaseName || "").trim()) {
          return "Enter the database name.";
        }
        return true;
      },
    },
    {
      id: "access",
      title: "Access",
      render(container, c) {
        const panel = wizardPanel("Agent access mode", [
          "Read-only is recommended unless the agent must write data.",
          "Destructive SQL still requires run confirmation in the agent UI when enabled.",
        ]);
        const list = document.createElement("div");
        list.className = "app-wizard-choice-list";
        list.innerHTML = `
          <label class="app-wizard-choice">
            <input type="radio" name="database-wizard-access" value="read" ${c.accessMode === "read" ? "checked" : ""}>
            <span class="app-wizard-choice-text">
              <strong>Read-only</strong>
              <span>SELECT and schema introspection only.</span>
            </span>
          </label>
          <label class="app-wizard-choice">
            <input type="radio" name="database-wizard-access" value="read_write" ${c.accessMode === "read_write" ? "checked" : ""}>
            <span class="app-wizard-choice-text">
              <strong>Read / write</strong>
              <span>Allows INSERT, UPDATE, DELETE when the agent runs tools.</span>
            </span>
          </label>`;
        list.querySelectorAll('input[name="database-wizard-access"]').forEach((input) => {
          input.addEventListener("change", () => {
            c.accessMode = input.value;
          });
        });
        panel.appendChild(list);
        container.appendChild(panel);
      },
      validate(c) {
        if (!["read", "read_write"].includes(c.accessMode)) {
          return "Choose an access mode.";
        }
        return true;
      },
    },
    {
      id: "privacy",
      title: "Privacy",
      render(container, c) {
        const box = document.createElement("div");
        box.className = "app-wizard-callout";
        box.innerHTML =
          "<strong>Credentials stay in your workspace.</strong> " +
          "Database passwords are encrypted for this business only. " +
          "We test the connection and cache schema metadata so the agent can plan queries. " +
          "Operators of MultiWorkAgent cannot read your password after you save.";
        container.appendChild(box);
        const summary = wizardPanel("Ready to connect", [
          `Name: ${c.name.trim()}`,
          `Engine: ${c.engine}`,
          c.engine === "sqlite"
            ? `File: ${c.databaseName.trim()}`
            : `Host: ${c.host.trim()} · Database: ${c.databaseName.trim()}`,
          `Access: ${c.accessMode === "read_write" ? "Read / write" : "Read-only"}`,
        ]);
        container.appendChild(summary);
      },
    },
  ];

  return {
    title: "Add database",
    finishLabel: "Connect database",
    steps,
    ctx,
    async onFinish(c) {
      const body = buildDatabaseConnectionPayload(c);
      await databaseApiJson(`/api/businesses/${c.businessId}/databases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      window.location.reload();
    },
  };
}

async function openAddDatabaseWizard(selectedBusinessId) {
  if (!selectedBusinessId) {
    if (typeof openSelectBusinessWizard === "function") {
      await openSelectBusinessWizard();
    } else {
      await openAppConfirm({
        title: "Select a business",
        message:
          "Choose one business in the header switcher (not “All businesses”), then add a database again.",
        confirmLabel: "OK",
      });
    }
    return;
  }
  try {
    await openAppWizard(buildDatabaseWizardConfig(selectedBusinessId));
  } catch (err) {
    console.error(err);
    await openAppConfirm({
      title: "Connection failed",
      message: err.message || "Could not save database connection.",
      confirmLabel: "OK",
    });
  }
}

function initDatabaseAdd() {
  const btn = document.getElementById("database-add-btn");
  if (!btn) {
    return;
  }
  btn.addEventListener("click", () => {
    const selectedBusinessId = btn.dataset.selectedBusinessId || "";
    void openAddDatabaseWizard(selectedBusinessId);
  });
}

function initDatabaseListActions() {
  const list = document.getElementById("database-connections-list");
  if (!list) {
    return;
  }

  list.addEventListener("click", async (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const disconnect = target.closest(".database-disconnect-btn");
    if (disconnect instanceof HTMLElement) {
      const connectionId = disconnect.dataset.connectionId;
      const businessId = disconnect.dataset.businessId;
      const connName = disconnect.dataset.name || "this connection";
      if (!connectionId || !businessId) {
        return;
      }
      const ok = await openAppConfirm({
        title: "Remove database",
        message: `Remove ${connName}? Cached schema and credentials will be deleted.`,
        confirmLabel: "Remove",
      });
      if (!ok) {
        return;
      }
      try {
        await databaseApiJson(
          `/api/businesses/${businessId}/databases/${connectionId}`,
          { method: "DELETE" },
        );
        window.location.reload();
      } catch (err) {
        console.error(err);
        await openAppConfirm({
          title: "Remove failed",
          message: err.message || "Could not remove connection.",
          confirmLabel: "OK",
        });
      }
      return;
    }

    const syncBtn = target.closest(".database-sync-btn");
    if (syncBtn instanceof HTMLElement) {
      const connectionId = syncBtn.dataset.connectionId;
      const businessId = syncBtn.dataset.businessId;
      if (!connectionId || !businessId) {
        return;
      }
      syncBtn.disabled = true;
      try {
        await databaseApiJson(
          `/api/businesses/${businessId}/databases/${connectionId}/sync-schema`,
          { method: "POST" },
        );
        window.location.reload();
      } catch (err) {
        console.error(err);
        await openAppConfirm({
          title: "Sync failed",
          message: err.message || "Could not refresh schema.",
          confirmLabel: "OK",
        });
      } finally {
        syncBtn.disabled = false;
      }
      return;
    }

    const schemaBtn = target.closest(".database-schema-btn");
    if (schemaBtn instanceof HTMLElement) {
      const connectionId = schemaBtn.dataset.connectionId;
      const businessId = schemaBtn.dataset.businessId;
      const connName = schemaBtn.dataset.name || "Database";
      if (!connectionId || !businessId) {
        return;
      }
      try {
        const data = await databaseApiJson(
          `/api/businesses/${businessId}/databases/${connectionId}/schema`,
        );
        await openAppConfirm({
          title: `${connName} — schema`,
          message: formatSchemaMessage(data.schema),
          confirmLabel: "OK",
        });
      } catch (err) {
        console.error(err);
        await openAppConfirm({
          title: "Schema unavailable",
          message: err.message || "Could not load cached schema.",
          confirmLabel: "OK",
        });
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initDatabaseAdd();
  initDatabaseListActions();
});
