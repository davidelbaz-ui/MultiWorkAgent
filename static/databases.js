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

async function promptAddDatabase(selectedBusinessId) {
  if (!selectedBusinessId) {
    await openAppConfirm({
      title: "Select a business",
      message:
        "Choose one business in the header switcher (not “All businesses”), then add a database again.",
      confirmLabel: "OK",
    });
    return;
  }

  const engineRaw = await openAppPrompt({
    title: "Database engine",
    label: "Engine (sqlite, postgresql, mysql)",
    defaultValue: "sqlite",
  });
  if (engineRaw === null) {
    return;
  }
  const engine = engineRaw.trim().toLowerCase();
  if (!["sqlite", "postgresql", "mysql"].includes(engine)) {
    await openAppConfirm({
      title: "Invalid engine",
      message: "Use sqlite, postgresql, or mysql.",
      confirmLabel: "OK",
    });
    return;
  }

  const name = await openAppPrompt({
    title: "Connection name",
    label: "Display name for this connection",
    defaultValue: "",
  });
  if (name === null || !name.trim()) {
    return;
  }

  let host = "";
  let port = null;
  let databaseName = "";
  let username = "";
  let password = "";

  if (engine === "sqlite") {
    databaseName = await openAppPrompt({
      title: "SQLite file path",
      label: "Absolute or relative path to the .sqlite / .db file",
      defaultValue: "",
    });
    if (databaseName === null || !databaseName.trim()) {
      return;
    }
  } else {
    host = await openAppPrompt({
      title: `${engine} host`,
      label: "Hostname",
      defaultValue: "127.0.0.1",
    });
    if (host === null || !host.trim()) {
      return;
    }
    const portRaw = await openAppPrompt({
      title: `${engine} port`,
      label: "Port (leave empty for default)",
      defaultValue: engine === "postgresql" ? "5432" : "3306",
    });
    if (portRaw === null) {
      return;
    }
    try {
      port = parseOptionalPort(portRaw);
    } catch (err) {
      await openAppConfirm({
        title: "Invalid port",
        message: err.message,
        confirmLabel: "OK",
      });
      return;
    }
    databaseName = await openAppPrompt({
      title: "Database name",
      label: "Database / schema name",
      defaultValue: "",
    });
    if (databaseName === null || !databaseName.trim()) {
      return;
    }
    username = await openAppPrompt({
      title: "Username",
      label: "Database user",
      defaultValue: "",
    });
    if (username === null) {
      return;
    }
    password = await openAppPrompt({
      title: "Password",
      label: "Database password",
      defaultValue: "",
    });
    if (password === null) {
      return;
    }
  }

  const readWrite = await openAppConfirm({
    title: "Access mode",
    message:
      "Allow read/write access for the agent? Choose Cancel for read-only (recommended).",
    confirmLabel: "Read/write",
    cancelLabel: "Read-only",
  });
  const accessMode = readWrite ? "read_write" : "read";

  const body = {
    name: name.trim(),
    engine,
    host: host.trim(),
    database_name: databaseName.trim(),
    username: username.trim(),
    password,
    access_mode: accessMode,
  };
  if (port !== null) {
    body.port = port;
  }

  try {
    await databaseApiJson(`/api/businesses/${selectedBusinessId}/databases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    window.location.reload();
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
    void promptAddDatabase(selectedBusinessId);
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
