/** @type {((value: string | null) => void) | null} */
let appDialogResolve = null;
/** @type {HTMLElement | null} */
let appDialogPreviousFocus = null;

function closeAppDialog(result) {
  const root = document.getElementById("app-dialog-root");
  const input = document.getElementById("app-dialog-input");
  if (!root || !appDialogResolve) {
    return;
  }
  const resolve = appDialogResolve;
  appDialogResolve = null;
  void (async () => {
    await uiCloseOverlay(root, "is-open", root.querySelector(".app-dialog"));
    input?.blur();
    resolve(result);
    appDialogPreviousFocus?.focus();
    appDialogPreviousFocus = null;
  })();
}

function initAppDialog() {
  const root = document.getElementById("app-dialog-root");
  const backdrop = document.getElementById("app-dialog-backdrop");
  const cancelBtn = document.getElementById("app-dialog-cancel");
  const confirmBtn = document.getElementById("app-dialog-confirm");
  const input = document.getElementById("app-dialog-input");
  if (!root || !backdrop || !cancelBtn || !confirmBtn) {
    return;
  }

  cancelBtn.addEventListener("click", () => closeAppDialog(null));
  backdrop.addEventListener("click", () => closeAppDialog(null));
  confirmBtn.addEventListener("click", () => {
    const mode = root.dataset.mode;
    if (mode === "confirm") {
      closeAppDialog(true);
      return;
    }
    closeAppDialog(input?.value ?? "");
  });

  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      confirmBtn.click();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && uiIsOverlayOpen(root, "is-open")) {
      e.preventDefault();
      closeAppDialog(null);
    }
  });
}

/**
 * @param {{ title: string, label: string, defaultValue?: string }} options
 * @returns {Promise<string | null>}
 */
function openAppPrompt(options) {
  const root = document.getElementById("app-dialog-root");
  const titleEl = document.getElementById("app-dialog-title");
  const messageEl = document.getElementById("app-dialog-message");
  const fieldWrap = document.getElementById("app-dialog-field");
  const labelEl = document.getElementById("app-dialog-label");
  const input = document.getElementById("app-dialog-input");
  const confirmBtn = document.getElementById("app-dialog-confirm");
  if (!root || !titleEl || !messageEl || !fieldWrap || !labelEl || !input || !confirmBtn) {
    return Promise.resolve(null);
  }

  return new Promise((resolve) => {
    appDialogPreviousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    appDialogResolve = resolve;
    root.dataset.mode = "prompt";
    titleEl.textContent = options.title;
    messageEl.hidden = true;
    fieldWrap.hidden = false;
    labelEl.textContent = options.label;
    input.value = options.defaultValue ?? "";
    confirmBtn.textContent = "Save";
    confirmBtn.className = "btn btn-primary";
    void (async () => {
      await uiOpenOverlay(root, "is-open");
      input.focus();
      input.select();
    })();
  });
}

/**
 * @param {{ title: string, message: string, confirmLabel?: string }} options
 * @returns {Promise<boolean>}
 */
function openAppConfirm(options) {
  const root = document.getElementById("app-dialog-root");
  const titleEl = document.getElementById("app-dialog-title");
  const messageEl = document.getElementById("app-dialog-message");
  const fieldWrap = document.getElementById("app-dialog-field");
  const confirmBtn = document.getElementById("app-dialog-confirm");
  if (!root || !titleEl || !messageEl || !fieldWrap || !confirmBtn) {
    return Promise.resolve(false);
  }

  return new Promise((resolve) => {
    appDialogPreviousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    appDialogResolve = (value) => resolve(Boolean(value));
    root.dataset.mode = "confirm";
    titleEl.textContent = options.title;
    messageEl.textContent = options.message;
    messageEl.hidden = false;
    fieldWrap.hidden = true;
    confirmBtn.textContent = options.confirmLabel ?? "Confirm";
    confirmBtn.className = "btn btn-danger";
    void (async () => {
      await uiOpenOverlay(root, "is-open");
      confirmBtn.focus();
    })();
  });
}

function initAgentDrawer() {
  const shell = document.getElementById("agent-shell");
  const menuBtn = document.getElementById("agent-menu-btn");
  const closeBtn = document.getElementById("agent-drawer-close");
  const backdrop = document.getElementById("agent-drawer-backdrop");
  const drawer = document.getElementById("agent-drawer");
  if (!shell || !menuBtn || !drawer) {
    return;
  }

  const open = () => {
    shell.classList.add("drawer-open");
    menuBtn.setAttribute("aria-expanded", "true");
    drawer.setAttribute("aria-hidden", "false");
    backdrop?.setAttribute("aria-hidden", "false");
  };

  const close = () => {
    shell.classList.remove("drawer-open");
    menuBtn.setAttribute("aria-expanded", "false");
    drawer.setAttribute("aria-hidden", "true");
    window.setTimeout(() => {
      backdrop?.setAttribute("aria-hidden", "true");
    }, UI_MOTION_MS);
    menuBtn.focus();
  };

  menuBtn.addEventListener("click", () => {
    if (shell.classList.contains("drawer-open")) {
      close();
    } else {
      open();
    }
  });
  closeBtn?.addEventListener("click", close);
  backdrop?.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && shell.classList.contains("drawer-open")) {
      close();
    }
  });
}

function initAccountMenu() {
  const root = document.querySelector("[data-account-menu]");
  if (!root) {
    return;
  }

  const trigger = root.querySelector(".account-menu-trigger");
  const panel = root.querySelector(".account-menu-panel");
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

  const open = () => {
    panel.hidden = false;
    requestAnimationFrame(() => {
      root.classList.add("is-open");
      trigger.setAttribute("aria-expanded", "true");
    });
  };

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    if (root.classList.contains("is-open")) {
      close();
    } else {
      open();
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
}

function initBusinessSwitcher() {
  const root = document.querySelector("[data-business-switcher]");
  if (!root) {
    return;
  }

  const trigger = root.querySelector(".business-switcher-trigger");
  const menu = root.querySelector(".business-switcher-menu");
  const label = root.querySelector(".business-switcher-label");
  const options = root.querySelectorAll(".business-switcher-option");
  if (!trigger || !menu || !label) {
    return;
  }

  const close = () => {
    root.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    window.setTimeout(() => {
      if (!root.classList.contains("is-open")) {
        menu.hidden = true;
      }
    }, 220);
  };

  const open = () => {
    menu.hidden = false;
    requestAnimationFrame(() => {
      root.classList.add("is-open");
      trigger.setAttribute("aria-expanded", "true");
    });
  };

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    if (root.classList.contains("is-open")) {
      close();
    } else {
      open();
    }
  });

  options.forEach((option) => {
    option.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (option.classList.contains("is-selected")) {
        close();
        return;
      }

      const value = option.dataset.value || "all";
      try {
        await fetch("/api/businesses/selection", {
          method: "PUT",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ business_id: value === "all" ? null : value }),
        });
      } catch (err) {
        console.error(err);
        return;
      }

      window.location.reload();
    });
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
}

function resizeAgentTextarea(textarea) {
  if (!textarea) {
    return;
  }
  const box = textarea.closest(".agent-prompt-box");
  const style = window.getComputedStyle(textarea);
  const lineHeight = parseFloat(style.lineHeight) || 22;
  const maxHeight = parseFloat(style.maxHeight) || 112;

  textarea.style.height = "0";
  const contentHeight = textarea.scrollHeight;
  const nextHeight = Math.min(contentHeight, maxHeight);
  textarea.style.height = `${nextHeight}px`;

  const isMultiline = contentHeight > lineHeight + 6;
  box?.classList.toggle("is-multiline", isMultiline);
  textarea.style.overflowY = isMultiline && contentHeight > maxHeight ? "auto" : "hidden";
}

async function initAgentComposer() {
  const form = document.getElementById("agent-composer");
  const textarea = document.getElementById("agent-message-input");
  const messages = document.getElementById("agent-messages");
  const inner = document.getElementById("agent-scroll-inner");
  const scroll = document.getElementById("agent-scroll");
  const fileInput = document.getElementById("agent-file-input");
  const uploadBtn = document.getElementById("agent-upload-btn");
  const attachmentsEl = document.getElementById("agent-attachments");
  const composerStack = document.getElementById("agent-composer-stack");
  const editingHint = document.getElementById("agent-editing-hint");
  const cancelEditBtn = document.getElementById("agent-cancel-edit");
  const threadLabel = document.getElementById("agent-thread-label");
  const scopeChip = document.getElementById("agent-scope-chip");
  const chatsList = document.getElementById("agent-chats-list");
  const newSideChatBtn = document.getElementById("agent-new-side-chat");
  const sendBtn = form?.querySelector(".agent-send-btn");
  const sendIcon = sendBtn?.querySelector(".agent-send-icon");
  const stopIcon = sendBtn?.querySelector(".agent-stop-icon");
  if (!form || !textarea || !messages || !inner || !fileInput || !attachmentsEl) {
    return;
  }

  /** @type {{ id: number, original_name: string, size_bytes: number }[]} */
  let draftFiles = [];
  let editingMessageId = null;
  let editingMessageAttachments = 0;
  let draftSaveTimer = null;
  let draftSaveInFlight = false;
  let lastSavedDraft = "";
  /** @type {AbortController | null} */
  let streamAbort = null;
  let activeRunId = null;

  const apiJson = async (url, options = {}) => {
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
  };

  const saveDraftBody = async (body, { keepalive = false } = {}) => {
    if (draftSaveInFlight && !keepalive) {
      return;
    }
    draftSaveInFlight = true;
    try {
      await fetch("/api/agent/draft", {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ body }),
        keepalive,
      });
      lastSavedDraft = body;
    } finally {
      draftSaveInFlight = false;
    }
  };

  const queueDraftSave = (body) => {
    if (body === lastSavedDraft) {
      return;
    }
    clearTimeout(draftSaveTimer);
    draftSaveTimer = setTimeout(() => saveDraftBody(body), 450);
  };

  const renderAttachments = () => {
    attachmentsEl.innerHTML = "";
    if (draftFiles.length === 0) {
      void uiHideElement(attachmentsEl);
      return;
    }
    void uiShowElement(attachmentsEl);

    draftFiles.forEach((file) => {
      const item = document.createElement("li");
      item.className = "agent-attachment";

      const name = document.createElement("span");
      name.className = "agent-attachment-name";
      name.textContent = file.original_name;
      name.title = file.original_name;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "agent-attachment-remove";
      removeBtn.setAttribute("aria-label", `Remove ${file.original_name}`);
      removeBtn.textContent = "×";
      removeBtn.addEventListener("click", async () => {
        try {
          const data = await apiJson(`/api/agent/draft/files/${file.id}`, { method: "DELETE" });
          draftFiles = data.draft.files;
          renderAttachments();
        } catch (err) {
          console.error(err);
        }
      });

      item.append(name, removeBtn);
      attachmentsEl.appendChild(item);
    });
  };

  const appendAttachmentLines = (container, attachments) => {
    if (!attachments?.length) {
      return;
    }
    const list = document.createElement("div");
    list.className = "msg-attachments";
    attachments.forEach((file) => {
      const line = document.createElement("div");
      line.className = "msg-attachment-line";
      line.textContent = file.original_name;
      list.appendChild(line);
    });
    container.appendChild(list);
  };

  const svgIcon = (paths) => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "msg-action-icon");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    paths.forEach((d) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    });
    return svg;
  };

  const clearEditMode = async ({ restoreDraft = true } = {}) => {
    editingMessageId = null;
    editingMessageAttachments = 0;
    composerStack?.classList.remove("is-editing");
    void uiHideElement(editingHint);
    messages.querySelectorAll(".msg-user-block.is-editing-target").forEach((el) => {
      el.classList.remove("is-editing-target");
    });
    textarea.placeholder = "Message agent…";
    if (restoreDraft) {
      const data = await apiJson("/api/agent/state");
      applyDraft(data.draft || { body: "", files: [] });
    }
  };

  const startEditMessage = async (msg) => {
    if (editingMessageId === msg.id) {
      return;
    }
    await clearEditMode({ restoreDraft: false });
    editingMessageId = msg.id;
    editingMessageAttachments = msg.attachments?.length || 0;
    composerStack?.classList.add("is-editing");
    void uiShowElement(editingHint);
    textarea.value = msg.content || "";
    textarea.placeholder = "Edit message…";
    lastSavedDraft = textarea.value;
    resizeAgentTextarea(textarea);
    textarea.focus();
    const block = messages.querySelector(`.msg-user-block[data-message-id="${msg.id}"]`);
    block?.classList.add("is-editing-target");
  };

  const deleteMessage = async (messageId) => {
    if (editingMessageId === messageId) {
      await clearEditMode();
    }
    const data = await apiJson(`/api/agent/messages/${messageId}`, { method: "DELETE" });
    renderMessages(data.messages || []);
    if (scroll) {
      requestAnimationFrame(() => {
        scroll.scrollTop = scroll.scrollHeight;
      });
    }
  };

  const buildUserMessageBlock = (msg) => {
    const block = document.createElement("div");
    block.className = "msg-user-block";
    block.dataset.messageId = String(msg.id);

    const bubble = document.createElement("div");
    bubble.className = "msg user";
    if (msg.content) {
      const text = document.createElement("span");
      text.textContent = msg.content;
      bubble.appendChild(text);
    }
    appendAttachmentLines(bubble, msg.attachments);
    block.appendChild(bubble);

    const actions = document.createElement("div");
    actions.className = "msg-user-actions";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "msg-action-btn";
    editBtn.setAttribute("aria-label", "Edit message");
    editBtn.appendChild(
      svgIcon([
        "M4 20h4l10.5-10.5a1.5 1.5 0 0 0 0-2.12l-2.88-2.88a1.5 1.5 0 0 0-2.12 0L4 16v4",
        "M13.5 6.5l2 2",
      ]),
    );
    editBtn.addEventListener("click", () => startEditMessage(msg));

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "msg-action-btn";
    deleteBtn.setAttribute("aria-label", "Delete message");
    deleteBtn.appendChild(
      svgIcon([
        "M4 7h16",
        "M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2",
        "M7 7l1 12a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1l1-12",
      ]),
    );
    deleteBtn.addEventListener("click", () => deleteMessage(msg.id));

    actions.append(editBtn, deleteBtn);
    block.appendChild(actions);
    return block;
  };

  const renderMessage = (msg) => {
    if (msg.role === "user") {
      return buildUserMessageBlock(msg);
    }
    const div = document.createElement("div");
    div.className = `msg ${msg.role}`;
    if (msg.content) {
      const text = document.createElement("span");
      text.textContent = msg.content;
      div.appendChild(text);
    }
    appendAttachmentLines(div, msg.attachments);
    return div;
  };

  const removeEmptyState = () => {
    inner.classList.remove("agent-scroll-inner--empty");
    inner.classList.add("agent-scroll-inner--thread");
    messages.querySelector(".agent-empty")?.remove();
  };

  const ensureStreamingBubble = () => {
    removeEmptyState();
    let bubble = messages.querySelector(".msg.agent.is-streaming");
    if (!bubble) {
      bubble = document.createElement("div");
      bubble.className = "msg agent is-streaming";
      const textSpan = document.createElement("span");
      textSpan.className = "msg-agent-text";
      const dot = document.createElement("span");
      dot.className = "agent-stream-dot";
      dot.setAttribute("aria-hidden", "true");
      bubble.append(textSpan, dot);
      messages.appendChild(bubble);
    }
    return bubble;
  };

  const clearStreamingBubble = () => {
    messages.querySelector(".msg.agent.is-streaming")?.remove();
  };

  const setSendStopMode = (stopping) => {
    if (!(sendBtn instanceof HTMLButtonElement)) {
      return;
    }
    sendBtn.classList.toggle("is-stop", stopping);
    sendBtn.type = stopping ? "button" : "submit";
    sendBtn.setAttribute("aria-label", stopping ? "Stop response" : "Send message");
  };

  const stopAgentStream = () => {
    if (activeRunId) {
      fetch(`/api/agent/runs/${activeRunId}/cancel`, {
        method: "POST",
        credentials: "same-origin",
      }).catch(() => {});
    }
    streamAbort?.abort();
  };

  const consumeAgentStream = async (response) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    /** @type {HTMLElement | null} */
    let textEl = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const dataLine = chunk.split("\n").find((line) => line.startsWith("data: "));
        if (!dataLine) {
          continue;
        }
        let payload;
        try {
          payload = JSON.parse(dataLine.slice(6));
        } catch {
          continue;
        }
        if (payload.type === "start") {
          activeRunId = payload.run_id || null;
          if (payload.message) {
            messages.appendChild(buildUserMessageBlock(payload.message));
          }
          const bubble = ensureStreamingBubble();
          textEl = bubble.querySelector(".msg-agent-text");
          textarea.value = "";
          lastSavedDraft = "";
          draftFiles = [];
          renderAttachments();
          resizeAgentTextarea(textarea);
        } else if (payload.type === "delta" && payload.text) {
          if (!textEl) {
            const bubble = ensureStreamingBubble();
            textEl = bubble.querySelector(".msg-agent-text");
          }
          if (textEl) {
            textEl.textContent += payload.text;
          }
          if (scroll) {
            scroll.scrollTop = scroll.scrollHeight;
          }
        } else if (payload.type === "done") {
          activeRunId = null;
          clearStreamingBubble();
          const state = await apiJson("/api/agent/state");
          applyWorkspaceState(state, { scrollToEnd: true });
        }
      }
    }
  };

  const renderMessages = (list) => {
    messages.innerHTML = "";
    if (!list.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state agent-empty";
      empty.textContent = "Send a message to start. Mention resources with @ when connected.";
      messages.appendChild(empty);
      inner.classList.add("agent-scroll-inner--empty");
      inner.classList.remove("agent-scroll-inner--thread");
      return;
    }
    inner.classList.remove("agent-scroll-inner--empty");
    inner.classList.add("agent-scroll-inner--thread");
    list.forEach((msg) => messages.appendChild(renderMessage(msg)));
  };

  const applyDraft = (draft) => {
    draftFiles = draft.files || [];
    textarea.value = draft.body || "";
    lastSavedDraft = draft.body || "";
    renderAttachments();
    resizeAgentTextarea(textarea);
  };

  const uploadDraftFiles = async (fileList) => {
    for (const file of Array.from(fileList)) {
      const formData = new FormData();
      formData.append("file", file);
      const data = await apiJson("/api/agent/draft/files", {
        method: "POST",
        body: formData,
      });
      draftFiles = data.draft.files;
    }
    renderAttachments();
  };

  const updateScopeLabel = (data) => {
    if (!scopeChip) {
      return;
    }
    const label = data.scope_label || "All businesses";
    scopeChip.textContent = label;
    scopeChip.classList.toggle("agent-scope-chip--all", !data.selected_business_id);
  };

  const updateThreadLabel = (data) => {
    if (!threadLabel) {
      return;
    }
    const title = data.title || "Main chat";
    threadLabel.textContent = title;
  };

  const renderThreadsList = (threads, activeId) => {
    if (!chatsList) {
      return;
    }
    chatsList.innerHTML = "";
    (threads || []).forEach((thread) => {
      const li = document.createElement("li");
      li.className = "agent-chat-item";
      if (thread.id === activeId) {
        li.classList.add("is-active");
      }

      const selectBtn = document.createElement("button");
      selectBtn.type = "button";
      selectBtn.className = "agent-chat-select";
      selectBtn.dataset.threadId = thread.id;

      if (thread.kind === "main") {
        const kind = document.createElement("span");
        kind.className = "agent-chat-kind";
        kind.textContent = "Main";
        selectBtn.appendChild(kind);
      }

      const name = document.createElement("span");
      name.className = "agent-chat-name";
      name.textContent = thread.title || (thread.kind === "main" ? "Main chat" : "Side chat");
      selectBtn.appendChild(name);

      selectBtn.addEventListener("click", async () => {
        if (thread.id === activeId) {
          return;
        }
        try {
          if (editingMessageId) {
            await clearEditMode({ restoreDraft: false });
          }
          clearTimeout(draftSaveTimer);
          if (!editingMessageId && textarea.value !== lastSavedDraft) {
            await saveDraftBody(textarea.value);
          }
          const data = await apiJson(`/api/agent/threads/${thread.id}/activate`, { method: "POST" });
          applyWorkspaceState(data, { scrollToEnd: true });
        } catch (err) {
          console.error(err);
        }
      });

      li.appendChild(selectBtn);

      const actions = document.createElement("div");
      actions.className = "agent-chat-actions";

      const renameBtn = document.createElement("button");
      renameBtn.type = "button";
      renameBtn.className = "agent-chat-action";
      renameBtn.setAttribute("aria-label", "Rename chat");
      renameBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5z"/></svg>';
      renameBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const current = thread.title || "";
        const next = await openAppPrompt({
          title: "Rename chat",
          label: "Chat name",
          defaultValue: current,
        });
        if (next === null) {
          return;
        }
        const trimmed = next.trim();
        if (!trimmed || trimmed === current) {
          return;
        }
        try {
          const data = await apiJson(`/api/agent/threads/${thread.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: trimmed }),
          });
          applyWorkspaceState(data);
        } catch (err) {
          console.error(err);
        }
      });
      actions.appendChild(renameBtn);

      if (thread.kind === "side") {
        const deleteBtn = document.createElement("button");
        deleteBtn.type = "button";
        deleteBtn.className = "agent-chat-action agent-chat-action--danger";
        deleteBtn.setAttribute("aria-label", "Delete chat");
        deleteBtn.innerHTML =
          '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
        deleteBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          const ok = await openAppConfirm({
            title: "Delete chat",
            message: `Delete “${thread.title || "Side chat"}”? This cannot be undone.`,
            confirmLabel: "Delete",
          });
          if (!ok) {
            return;
          }
          try {
            if (editingMessageId) {
              await clearEditMode({ restoreDraft: false });
            }
            const data = await apiJson(`/api/agent/threads/${thread.id}`, { method: "DELETE" });
            applyWorkspaceState(data, { scrollToEnd: true });
          } catch (err) {
            console.error(err);
          }
        });
        actions.appendChild(deleteBtn);
      }

      li.appendChild(actions);
      chatsList.appendChild(li);
    });
  };

  const limitsBanner = document.getElementById("agent-limits-banner");

  const updateLimitsUI = (limits, message) => {
    if (!limits) {
      return;
    }
    const concurrentEl = document.getElementById("agent-concurrent-line");
    const runsTodayEl = document.getElementById("agent-runs-today");
    if (concurrentEl) {
      concurrentEl.textContent = `Concurrent: ${limits.concurrent} / ${limits.concurrent_max}`;
    }
    if (runsTodayEl) {
      const used = limits.runs_display_used ?? limits.runs_24h;
      const max = limits.runs_display_max ?? limits.runs_daily_max;
      const period = limits.runs_display_period === "month" ? "This month" : "Today";
      runsTodayEl.textContent = `${period}: ${used} / ${max} runs`;
    }
    if (limitsBanner) {
      if (!limits.can_run) {
        limitsBanner.hidden = false;
        limitsBanner.textContent =
          message || limits.blocked_message || "Run limit reached. Try again later.";
      } else {
        limitsBanner.hidden = true;
        limitsBanner.textContent = "";
      }
    }
    if (sendBtn instanceof HTMLButtonElement && !form.classList.contains("is-agent-running")) {
      sendBtn.disabled = !limits.can_run;
    }
  };

  const updateRunInspector = (run) => {
    if (!run) {
      return;
    }
    const stats = document.getElementById("agent-run-stats");
    const meter = document.getElementById("agent-run-meter-fill");
    const statusEl = document.getElementById("agent-run-status");
    const summaryEl = document.getElementById("agent-run-summary");
    const runsTodayEl = document.getElementById("agent-runs-today");
    const inputCap = run.run_input_cap || 30000;
    const outputCap = run.run_output_cap || 2000;
    const inputTokens = run.input_tokens || 0;
    const outputTokens = run.output_tokens || 0;
    if (stats) {
      stats.textContent = `${inputTokens} / ${inputCap} input · ${outputTokens} / ${outputCap} output`;
    }
    if (meter) {
      const pct = inputCap ? Math.min(100, Math.round((inputTokens / inputCap) * 100)) : 0;
      meter.style.width = `${pct}%`;
    }
    if (summaryEl) {
      const summary = run.summary || "";
      if (summary && run.status && run.status !== "idle") {
        summaryEl.hidden = false;
        summaryEl.textContent = summary;
      } else {
        summaryEl.hidden = true;
        summaryEl.textContent = "";
      }
    }
    if (statusEl) {
      const runStatus = run.status || "idle";
      if (runStatus === "idle") {
        statusEl.hidden = true;
        statusEl.textContent = "";
      } else {
        statusEl.hidden = false;
        const labels = {
          completed: "Last run completed",
          error: "Last run failed",
          unconfigured: "Agent not configured",
          timeout: "Last run timed out",
        };
        const units =
          run.run_units >= 1 ? " · 1 run" : run.run_units > 0 ? ` · ${run.run_units} run` : "";
        statusEl.textContent = (labels[runStatus] || `Last run: ${runStatus}`) + units;
      }
    }
    if (runsTodayEl && typeof run.runs_today === "number") {
      const limits = run.limits || {};
      const used = limits.runs_display_used ?? run.runs_today;
      const max = limits.runs_display_max ?? run.runs_daily_max ?? 50;
      const period = limits.runs_display_period === "month" ? "This month" : "Today";
      runsTodayEl.textContent = `${period}: ${used} / ${max} runs`;
    }
    if (run.limits) {
      updateLimitsUI(run.limits);
    }
    const toolsList = document.getElementById("agent-run-tool-calls");
    const toolsEmpty = document.getElementById("agent-run-tool-calls-empty");
    const toolCalls = run.tool_calls || [];
    if (toolsList) {
      toolsList.innerHTML = "";
      toolCalls.forEach((tc) => {
        const li = document.createElement("li");
        li.textContent = tc.label || tc.tool_name || "tool";
        li.title = JSON.stringify({ input: tc.input, output: tc.output }, null, 0);
        toolsList.appendChild(li);
      });
    }
    if (toolsEmpty) {
      toolsEmpty.hidden = toolCalls.length > 0;
    }
  };

  const setAgentRunning = (running) => {
    form.classList.toggle("is-agent-running", running);
    setSendStopMode(running);
    if (sendBtn instanceof HTMLButtonElement) {
      sendBtn.disabled = false;
    }
    textarea.readOnly = running;
  };

  const applyWorkspaceState = (data, { scrollToEnd = false } = {}) => {
    renderMessages(data.messages || []);
    applyDraft(data.draft || { body: "", files: [] });
    updateScopeLabel(data);
    updateThreadLabel(data);
    updateRunInspector(data.run);
    updateLimitsUI(data.limits);
    renderThreadsList(data.threads || [], data.active_thread_id || data.thread_id);
    if (scroll && scrollToEnd) {
      requestAnimationFrame(() => {
        scroll.scrollTop = scroll.scrollHeight;
      });
    }
  };

  const loadState = async () => {
    const data = await apiJson("/api/agent/state");
    applyWorkspaceState(data, { scrollToEnd: Boolean((data.messages || []).length) });
  };

  const clearMainBtn = document.getElementById("agent-clear-main-chat");
  clearMainBtn?.addEventListener("click", async () => {
    const ok = await openAppConfirm({
      title: "Clear main chat",
      message: "Delete all messages in Main chat? This cannot be undone.",
      confirmLabel: "Clear",
    });
    if (!ok) {
      return;
    }
    try {
      if (editingMessageId) {
        await clearEditMode({ restoreDraft: false });
      }
      clearTimeout(draftSaveTimer);
      const data = await apiJson("/api/agent/main/clear", { method: "POST" });
      applyWorkspaceState(data, { scrollToEnd: false });
    } catch (err) {
      console.error(err);
    }
  });

  uploadBtn?.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", async () => {
    if (!fileInput.files?.length) {
      return;
    }
    try {
      await uploadDraftFiles(fileInput.files);
    } catch (err) {
      console.error(err);
    }
    fileInput.value = "";
  });

  textarea.addEventListener("paste", async (e) => {
    const clipboard = e.clipboardData;
    if (!clipboard) {
      return;
    }

    const pastedFiles = [];
    for (const item of clipboard.items) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          pastedFiles.push(file);
        }
      }
    }

    if (pastedFiles.length > 0) {
      e.preventDefault();
      try {
        await uploadDraftFiles(pastedFiles);
      } catch (err) {
        console.error(err);
      }
    }
  });

  const shell = document.getElementById("agent-shell");

  const hasFiles = (dt) => {
    if (!dt) {
      return false;
    }
    return Array.from(dt.types).includes("Files");
  };

  shell?.addEventListener("dragenter", (e) => {
    if (!hasFiles(e.dataTransfer)) {
      return;
    }
    e.preventDefault();
    shell.classList.add("is-drag-over");
  });

  shell?.addEventListener("dragover", (e) => {
    if (!hasFiles(e.dataTransfer)) {
      return;
    }
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    shell.classList.add("is-drag-over");
  });

  shell?.addEventListener("dragleave", (e) => {
    const next = e.relatedTarget;
    if (next && shell.contains(next)) {
      return;
    }
    shell.classList.remove("is-drag-over");
  });

  shell?.addEventListener("drop", async (e) => {
    if (!hasFiles(e.dataTransfer)) {
      return;
    }
    e.preventDefault();
    shell.classList.remove("is-drag-over");
    if (!e.dataTransfer.files?.length) {
      return;
    }
    try {
      await uploadDraftFiles(e.dataTransfer.files);
    } catch (err) {
      console.error(err);
    }
  });

  const submitMessage = async () => {
    const text = textarea.value;
    const trimmed = text.trim();

    try {
      clearTimeout(draftSaveTimer);

      if (editingMessageId) {
        if (!trimmed && editingMessageAttachments === 0) {
          return;
        }
        await apiJson(`/api/agent/messages/${editingMessageId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text }),
        });
        const state = await apiJson("/api/agent/state");
        applyWorkspaceState(state, { scrollToEnd: true });
        await clearEditMode({ restoreDraft: true });
      } else {
        if (!trimmed && draftFiles.length === 0) {
          return;
        }
        setAgentRunning(true);
        streamAbort = new AbortController();
        const res = await fetch("/api/agent/messages/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          credentials: "same-origin",
          body: JSON.stringify({ content: text }),
          signal: streamAbort.signal,
        });
        const contentType = res.headers.get("content-type") || "";
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          const err = new Error(data.error || `Request failed (${res.status})`);
          err.status = res.status;
          err.data = data;
          throw err;
        }
        if (!contentType.includes("text/event-stream") || !res.body) {
          throw new Error("Unexpected response from agent stream.");
        }
        await consumeAgentStream(res);
      }

      if (scroll) {
        requestAnimationFrame(() => {
          scroll.scrollTop = scroll.scrollHeight;
        });
      }
    } catch (err) {
      if (err?.name === "AbortError") {
        try {
          const state = await apiJson("/api/agent/state");
          applyWorkspaceState(state, { scrollToEnd: true });
        } catch (reloadErr) {
          console.error(reloadErr);
        }
      } else if (err?.status === 429 && err?.data?.limits) {
        updateLimitsUI(err.data.limits, err.data.error);
      } else {
        console.error(err);
      }
    } finally {
      clearStreamingBubble();
      activeRunId = null;
      streamAbort = null;
      setAgentRunning(false);
    }
  };

  cancelEditBtn?.addEventListener("click", () => clearEditMode());

  textarea.addEventListener("input", () => {
    resizeAgentTextarea(textarea);
    if (!editingMessageId) {
      queueDraftSave(textarea.value);
    }
  });

  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitMessage();
    }
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitMessage();
  });

  sendBtn?.addEventListener("click", (e) => {
    if (form.classList.contains("is-agent-running")) {
      e.preventDefault();
      e.stopPropagation();
      stopAgentStream();
    }
  });

  window.addEventListener("beforeunload", () => {
    if (!editingMessageId && textarea.value !== lastSavedDraft) {
      saveDraftBody(textarea.value, { keepalive: true });
    }
  });

  newSideChatBtn?.addEventListener("click", async () => {
    try {
      if (editingMessageId) {
        await clearEditMode({ restoreDraft: false });
      }
      clearTimeout(draftSaveTimer);
      if (!editingMessageId && textarea.value !== lastSavedDraft) {
        await saveDraftBody(textarea.value);
      }
      const data = await apiJson("/api/agent/threads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      applyWorkspaceState(data, { scrollToEnd: false });
      textarea.focus();
    } catch (err) {
      console.error(err);
    }
  });

  try {
    await loadState();
  } catch (err) {
    console.error(err);
  }
}

function initGlobalSearch() {
  const wrap = document.getElementById("global-search-wrap");
  const column = document.getElementById("global-search-column");
  const input = document.getElementById("global-search");
  const clearBtn = document.getElementById("global-search-clear");
  const resultsPanel = document.getElementById("global-search-results");
  const resultsList = document.getElementById("global-search-results-list");
  const statusEl = document.getElementById("global-search-status");
  if (!wrap || !input || !resultsPanel || !resultsList) {
    return;
  }

  /** @type {Array<{ id: string, type: string, label: string, meta: string, href: string, thread_id?: string, message_id?: number }>} */
  let resultItems = [];
  let activeIndex = -1;
  let searchTimer = null;
  let searchRequestId = 0;

  const syncClear = () => {
    const hasText = input.value.trim().length > 0;
    wrap.classList.toggle("has-value", hasText);
    if (clearBtn) {
      clearBtn.classList.toggle("is-visible", hasText);
      clearBtn.setAttribute("aria-hidden", hasText ? "false" : "true");
      clearBtn.tabIndex = hasText ? 0 : -1;
    }
  };

  const setResultsOpen = (open) => {
    input.setAttribute("aria-expanded", open ? "true" : "false");
    if (!open) {
      activeIndex = -1;
      void uiHideElement(resultsPanel);
      return;
    }
    void uiShowElement(resultsPanel);
  };

  const renderResults = (results, { query, loading = false, scopeLabel = "" } = {}) => {
    resultsList.innerHTML = "";
    resultItems = results;
    activeIndex = results.length ? 0 : -1;

    if (loading) {
      statusEl.textContent = scopeLabel ? `Searching… · ${scopeLabel}` : "Searching…";
      statusEl.hidden = false;
      setResultsOpen(true);
      return;
    }

    if (!query) {
      statusEl.hidden = true;
      setResultsOpen(false);
      return;
    }

    if (!results.length) {
      const scopeSuffix = scopeLabel ? ` · ${scopeLabel}` : "";
      statusEl.textContent = `No results for “${query}”${scopeSuffix}`;
      statusEl.hidden = false;
      setResultsOpen(true);
      return;
    }

    if (scopeLabel) {
      statusEl.textContent = scopeLabel;
      statusEl.hidden = false;
    } else {
      statusEl.hidden = true;
    }

    results.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = "global-search-result";
      li.setAttribute("role", "option");
      li.dataset.index = String(index);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "global-search-result-btn";
      btn.id = `global-search-option-${index}`;

      const label = document.createElement("span");
      label.className = "global-search-result-label";
      label.textContent = item.label;

      const meta = document.createElement("span");
      meta.className = "global-search-result-meta";
      meta.textContent = item.meta;

      btn.append(label, meta);
      btn.addEventListener("click", () => {
        void activateResult(item);
      });
      li.appendChild(btn);
      resultsList.appendChild(li);
    });

    highlightActive();
    setResultsOpen(true);
  };

  const highlightActive = () => {
    resultsList.querySelectorAll(".global-search-result").forEach((row, index) => {
      row.classList.toggle("is-active", index === activeIndex);
    });
    if (activeIndex >= 0) {
      const active = resultsList.querySelector(`#global-search-option-${activeIndex}`);
      active?.scrollIntoView({ block: "nearest" });
    }
  };

  const activateResult = async (item) => {
    if (item.thread_id) {
      try {
        await fetch(`/api/agent/threads/${item.thread_id}/activate`, { method: "POST" });
      } catch (err) {
        console.error(err);
      }
    }
    if (item.run_id) {
      try {
        await fetch(`/api/agent/runs/${item.run_id}/focus`, { method: "POST" });
      } catch (err) {
        console.error(err);
      }
    }
    window.location.href = item.href;
  };

  const runSearch = async (query) => {
    const trimmed = query.trim();
    syncClear();
    if (!trimmed) {
      renderResults([], { query: "" });
      return;
    }

    const requestId = ++searchRequestId;
    renderResults([], { query: trimmed, loading: true });

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(trimmed)}`, {
        headers: { Accept: "application/json" },
      });
      const data = await res.json();
      if (requestId !== searchRequestId) {
        return;
      }
      if (!res.ok) {
        throw new Error(data.error || "Search failed");
      }
      renderResults(data.results || [], {
        query: trimmed,
        scopeLabel: data.scope_label || "",
      });
    } catch (err) {
      console.error(err);
      if (requestId !== searchRequestId) {
        return;
      }
      statusEl.textContent = "Search unavailable. Try again.";
      statusEl.hidden = false;
      resultsList.innerHTML = "";
      setResultsOpen(true);
    }
  };

  const queueSearch = () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearch(input.value), 120);
  };

  const focusSearch = () => {
    input.focus();
    input.select();
    if (input.value.trim()) {
      queueSearch();
    }
  };

  input.addEventListener("input", queueSearch);

  input.addEventListener("focus", () => {
    if (input.value.trim()) {
      queueSearch();
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      if (!resultItems.length) {
        return;
      }
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, resultItems.length - 1);
      highlightActive();
      return;
    }
    if (e.key === "ArrowUp") {
      if (!resultItems.length) {
        return;
      }
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      highlightActive();
      return;
    }
    if (e.key === "Enter") {
      if (activeIndex >= 0 && resultItems[activeIndex]) {
        e.preventDefault();
        void activateResult(resultItems[activeIndex]);
      }
      return;
    }
    if (e.key === "Escape") {
      if (uiIsOverlayOpen(resultsPanel, "ui-motion-visible")) {
        e.preventDefault();
        setResultsOpen(false);
      }
    }
  });

  clearBtn?.addEventListener("click", () => {
    input.value = "";
    searchRequestId += 1;
    syncClear();
    renderResults([], { query: "" });
    input.focus();
  });

  document.addEventListener("click", (e) => {
    if (!column?.contains(e.target)) {
      setResultsOpen(false);
    }
  });

  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "k") {
      return;
    }
    if (uiIsOverlayOpen(document.getElementById("app-dialog-root"), "is-open")) {
      return;
    }
    e.preventDefault();
    focusSearch();
  });

  syncClear();
}

document.addEventListener("DOMContentLoaded", () => {
  initAppDialog();
  initGlobalSearch();
  initAgentDrawer();
  initBusinessSwitcher();
  initAccountMenu();
  initAgentComposer();
});
