(function () {
  const messagesEl = document.getElementById("support-messages");
  const form = document.getElementById("support-composer");
  const input = document.getElementById("support-message-input");
  const sendBtn = document.getElementById("support-send-btn");
  const fileInput = document.getElementById("support-file-input");
  const uploadBtn = document.getElementById("support-upload-btn");
  const attachmentsEl = document.getElementById("support-attachments");
  if (!messagesEl || !form || !input || !sendBtn) {
    return;
  }

  const pendingFiles = [];

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

  function renderPendingAttachments() {
    if (!attachmentsEl) return;
    attachmentsEl.innerHTML = "";
    if (!pendingFiles.length) {
      attachmentsEl.hidden = true;
      return;
    }
    attachmentsEl.hidden = false;
    pendingFiles.forEach(function (file, index) {
      const item = document.createElement("li");
      item.className = "agent-attachment";
      const name = document.createElement("span");
      name.className = "agent-attachment-name";
      name.textContent = file.name;
      name.title = file.name;
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "agent-attachment-remove";
      removeBtn.setAttribute("aria-label", "Remove " + file.name);
      removeBtn.textContent = "×";
      removeBtn.addEventListener("click", function () {
        pendingFiles.splice(index, 1);
        renderPendingAttachments();
      });
      item.append(name, removeBtn);
      attachmentsEl.appendChild(item);
    });
  }

  function appendMessageAttachments(container, attachments) {
    if (!attachments || !attachments.length) return;
    const list = document.createElement("ul");
    list.className = "support-msg-attachments";
    attachments.forEach(function (att) {
      const li = document.createElement("li");
      const link = document.createElement("a");
      link.href = att.url || "#";
      link.className = "support-msg-attachment-link";
      link.textContent = att.original_name || "Attachment";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      li.appendChild(link);
      list.appendChild(li);
    });
    container.appendChild(list);
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
      if (msg.body) {
        body.textContent = msg.body;
      }
      appendMessageAttachments(body, msg.attachments);

      wrap.appendChild(head);
      wrap.appendChild(body);
      messagesEl.appendChild(wrap);
    });
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function setBusy(busy) {
    sendBtn.disabled = busy;
    input.disabled = busy;
    if (uploadBtn) uploadBtn.disabled = busy;
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

  if (uploadBtn && fileInput) {
    uploadBtn.addEventListener("click", function () {
      fileInput.click();
    });
    fileInput.addEventListener("change", function () {
      Array.from(fileInput.files || []).forEach(function (file) {
        pendingFiles.push(file);
      });
      fileInput.value = "";
      renderPendingAttachments();
    });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    const body = (input.value || "").trim();
    if (!body && !pendingFiles.length) {
      return;
    }
    setBusy(true);
    const formData = new FormData();
    formData.append("body", body);
    pendingFiles.forEach(function (file) {
      formData.append("files", file);
    });
    fetch("/api/support/messages", {
      method: "POST",
      credentials: "same-origin",
      body: formData,
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
        pendingFiles.length = 0;
        renderPendingAttachments();
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
