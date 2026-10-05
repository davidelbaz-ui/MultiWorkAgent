(function () {
  const messagesEl = document.getElementById("support-messages");
  const form = document.getElementById("support-composer");
  const input = document.getElementById("support-message-input");
  const sendBtn = document.getElementById("support-send-btn");
  if (!messagesEl || !form || !input || !sendBtn) {
    return;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function formatTime(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    } catch (_e) {
      return iso;
    }
  }

  function renderMessages(messages) {
    messagesEl.innerHTML = "";
    if (!messages.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No messages yet.";
      messagesEl.appendChild(empty);
      return;
    }
    messages.forEach(function (msg) {
      const wrap = document.createElement("article");
      const type = msg.sender_type || "user";
      wrap.className = "support-msg support-msg--" + type;
      wrap.setAttribute("data-message-id", msg.id);

      const head = document.createElement("header");
      head.className = "support-msg-head";
      const who = document.createElement("span");
      who.className = "support-msg-who";
      who.textContent = msg.sender_label || "Message";
      const when = document.createElement("time");
      when.className = "support-msg-time";
      when.dateTime = msg.created_at || "";
      when.textContent = formatTime(msg.created_at);
      head.appendChild(who);
      head.appendChild(when);

      const body = document.createElement("div");
      body.className = "support-msg-body";
      body.textContent = msg.body || "";

      wrap.appendChild(head);
      wrap.appendChild(body);
      messagesEl.appendChild(wrap);
    });
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function setBusy(busy) {
    sendBtn.disabled = busy;
    input.disabled = busy;
  }

  function loadMessages() {
    return fetch("/api/support/messages", { credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) {
          throw new Error("Could not load support chat.");
        }
        return res.json();
      })
      .then(function (data) {
        renderMessages(data.messages || []);
      })
      .catch(function (err) {
        messagesEl.innerHTML =
          '<p class="empty-state">' + escapeHtml(err.message || "Could not load chat.") + "</p>";
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    const body = (input.value || "").trim();
    if (!body) {
      return;
    }
    setBusy(true);
    fetch("/api/support/messages", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: body }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) {
            throw new Error(data.error || "Could not send message.");
          }
          return data;
        });
      })
      .then(function (data) {
        input.value = "";
        renderMessages(data.messages || []);
      })
      .catch(function (err) {
        window.alert(err.message || "Could not send message.");
      })
      .finally(function () {
        setBusy(false);
        input.focus();
      });
  });

  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  loadMessages();
})();
