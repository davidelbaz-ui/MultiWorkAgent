async function notificationsApiJson(url, options = {}) {
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

function formatNotificationTime(iso) {
  if (!iso) {
    return "";
  }
  try {
    const dt = new Date(iso);
    return dt.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function renderNotificationsList(items) {
  const list = document.getElementById("notifications-list");
  const empty = document.getElementById("notifications-empty");
  if (!list) {
    return;
  }
  list.innerHTML = "";
  if (!items.length) {
    if (empty) {
      empty.hidden = false;
    }
    return;
  }
  if (empty) {
    empty.hidden = true;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = `notifications-item${item.is_read ? "" : " notifications-item--unread"}`;
    li.dataset.notificationId = item.id;
    if (item.scope) {
      li.dataset.notificationScope = item.scope;
    }

    const row = document.createElement("div");
    row.className = "notifications-item-row";

    const main = document.createElement("div");
    main.className = "notifications-item-main";

    const link = item.href && !item.actions ? document.createElement("a") : document.createElement("div");
    link.className = "notifications-item-link";
    if (link instanceof HTMLAnchorElement && item.href) {
      link.href = item.href;
    }
    const title = document.createElement("span");
    title.className = "notifications-item-title";
    title.textContent = item.title || "";
    const body = document.createElement("span");
    body.className = "notifications-item-body";
    body.textContent = item.body || "";
    const time = document.createElement("span");
    time.className = "notifications-item-time";
    time.textContent = formatNotificationTime(item.created_at);
    link.append(title, body, time);
    main.appendChild(link);

    if (item.invite_id && Array.isArray(item.actions)) {
      const actions = document.createElement("div");
      actions.className = "notifications-item-actions";
      const acceptBtn = document.createElement("button");
      acceptBtn.type = "button";
      acceptBtn.className = "btn btn-sm btn-primary notifications-invite-accept";
      acceptBtn.dataset.inviteId = item.invite_id;
      acceptBtn.textContent = "Accept";
      const declineBtn = document.createElement("button");
      declineBtn.type = "button";
      declineBtn.className = "btn btn-sm notifications-invite-decline";
      declineBtn.dataset.inviteId = item.invite_id;
      declineBtn.textContent = "Decline";
      actions.append(acceptBtn, declineBtn);
      main.appendChild(actions);
    }

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "notifications-item-delete";
    deleteBtn.dataset.notificationId = item.id;
    deleteBtn.setAttribute("aria-label", `Delete notification: ${item.title || "notification"}`);
    deleteBtn.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M8 8l8 8M16 8l-8 8"/>
      </svg>`;

    row.append(main, deleteBtn);
    li.appendChild(row);
    list.appendChild(li);
  });
}

function syncNotificationsBadge(unread) {
  const badge = document.getElementById("notifications-badge");
  if (!badge) {
    return;
  }
  const count = Number(unread) || 0;
  if (count > 0) {
    badge.hidden = false;
    badge.setAttribute("aria-hidden", "false");
    badge.textContent = count > 9 ? "9+" : String(count);
  } else {
    badge.hidden = true;
    badge.setAttribute("aria-hidden", "true");
  }
}

async function refreshNotifications() {
  const data = await notificationsApiJson("/api/notifications");
  renderNotificationsList(data.notifications || []);
  syncNotificationsBadge(data.unread_count);
}

function initNotificationsMenu() {
  const root = document.querySelector("[data-notifications-menu]");
  if (!root) {
    return;
  }
  const trigger = root.querySelector(".notifications-trigger");
  const panel = root.querySelector(".notifications-panel");
  const deleteAll = document.getElementById("notifications-delete-all");
  if (!trigger || !panel) {
    return;
  }

  const close = () => {
    root.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    window.setTimeout(() => {
      if (!root.classList.contains("is-open")) {
        panel.hidden = true;
      }
    }, 220);
  };

  const open = async () => {
    panel.hidden = false;
    requestAnimationFrame(() => {
      root.classList.add("is-open");
      trigger.setAttribute("aria-expanded", "true");
    });
    try {
      await refreshNotifications();
    } catch (err) {
      console.error(err);
    }
  };

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    if (root.classList.contains("is-open")) {
      close();
    } else {
      void open();
    }
  });

  document.addEventListener("click", (e) => {
    if (!root.contains(e.target)) {
      close();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      close();
    }
  });

  deleteAll?.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const ok =
      typeof openAppConfirm === "function"
        ? await openAppConfirm({
            title: "Delete all notifications",
            message: "Remove every notification from your feed? This cannot be undone.",
            confirmLabel: "Delete all",
          })
        : window.confirm("Delete all notifications?");
    if (!ok) {
      return;
    }
    try {
      await notificationsApiJson("/api/notifications/delete-all", { method: "POST" });
      await refreshNotifications();
    } catch (err) {
      console.error(err);
    }
  });

  panel.addEventListener("click", async (e) => {
    const acceptBtn = e.target.closest(".notifications-invite-accept");
    if (acceptBtn instanceof HTMLElement) {
      e.preventDefault();
      e.stopPropagation();
      const inviteId = acceptBtn.dataset.inviteId;
      if (!inviteId) {
        return;
      }
      try {
        const data = await notificationsApiJson(
          `/api/team/invites/${encodeURIComponent(inviteId)}/accept`,
          { method: "POST" },
        );
        await refreshNotifications();
        if (data.redirect) {
          window.location.href = data.redirect;
        }
      } catch (err) {
        console.error(err);
        if (typeof openAppAlert === "function") {
          await openAppAlert({
            title: "Could not accept invite",
            message: err instanceof Error ? err.message : "Something went wrong.",
          });
        }
      }
      return;
    }

    const declineBtn = e.target.closest(".notifications-invite-decline");
    if (declineBtn instanceof HTMLElement) {
      e.preventDefault();
      e.stopPropagation();
      const inviteId = declineBtn.dataset.inviteId;
      if (!inviteId) {
        return;
      }
      try {
        await notificationsApiJson(
          `/api/team/invites/${encodeURIComponent(inviteId)}/decline`,
          { method: "POST" },
        );
        await refreshNotifications();
      } catch (err) {
        console.error(err);
      }
      return;
    }

    const deleteBtn = e.target.closest(".notifications-item-delete");
    if (deleteBtn instanceof HTMLElement) {
      e.preventDefault();
      e.stopPropagation();
      const id = deleteBtn.dataset.notificationId;
      if (!id) {
        return;
      }
      try {
        await notificationsApiJson(`/api/notifications/${encodeURIComponent(id)}`, {
          method: "DELETE",
        });
        await refreshNotifications();
      } catch (err) {
        console.error(err);
      }
      return;
    }

    const item = e.target.closest(".notifications-item");
    if (!(item instanceof HTMLElement)) {
      return;
    }
    const id = item.dataset.notificationId;
    if (!id || !item.classList.contains("notifications-item--unread")) {
      return;
    }
    try {
      await notificationsApiJson(`/api/notifications/${encodeURIComponent(id)}/read`, {
        method: "POST",
      });
      item.classList.remove("notifications-item--unread");
      const data = await notificationsApiJson("/api/notifications");
      syncNotificationsBadge(data.unread_count);
    } catch (err) {
      console.error(err);
    }
  });

  scheduleIdle(() => {
    void refreshNotifications().catch(() => {});
  });

  window.setInterval(() => {
    if (document.visibilityState !== "visible") {
      return;
    }
    void refreshNotifications().catch(() => {});
  }, 60000);
}

function scheduleIdle(fn, timeoutMs = 2500) {
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(fn, { timeout: timeoutMs });
  } else {
    setTimeout(fn, 100);
  }
}

document.addEventListener("DOMContentLoaded", initNotificationsMenu);
