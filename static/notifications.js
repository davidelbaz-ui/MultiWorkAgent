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
    const link = item.href ? document.createElement("a") : document.createElement("div");
    link.className = "notifications-item-link";
    if (item.href) {
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
    li.appendChild(link);
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
  const markAll = document.getElementById("notifications-mark-all");
  if (!trigger || !panel) {
    return;
  }

  const close = () => {
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  };

  const open = async () => {
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    try {
      await refreshNotifications();
    } catch (err) {
      console.error(err);
    }
  };

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    if (panel.hidden) {
      void open();
    } else {
      close();
    }
  });

  document.addEventListener("click", (e) => {
    if (!root.contains(e.target)) {
      close();
    }
  });

  markAll?.addEventListener("click", async (e) => {
    e.preventDefault();
    try {
      await notificationsApiJson("/api/notifications/read-all", { method: "POST" });
      await refreshNotifications();
    } catch (err) {
      console.error(err);
    }
  });

  panel.addEventListener("click", async (e) => {
    const item = e.target.closest(".notifications-item");
    if (!(item instanceof HTMLElement)) {
      return;
    }
    const id = item.dataset.notificationId;
    if (!id || !item.classList.contains("notifications-item--unread")) {
      return;
    }
    try {
      await notificationsApiJson(`/api/notifications/${id}/read`, { method: "POST" });
      item.classList.remove("notifications-item--unread");
      const data = await notificationsApiJson("/api/notifications");
      syncNotificationsBadge(data.unread_count);
    } catch (err) {
      console.error(err);
    }
  });

  void refreshNotifications();
  window.setInterval(() => {
    void refreshNotifications().catch(() => {});
  }, 60000);
}

document.addEventListener("DOMContentLoaded", initNotificationsMenu);
