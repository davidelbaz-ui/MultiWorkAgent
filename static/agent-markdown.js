/**
 * Markdown + syntax highlighting for agent chat replies (marked, DOMPurify, highlight.js).
 */
(function initAgentMarkdown(global) {
  const marked = global.marked;
  const DOMPurify = global.DOMPurify;
  const hljs = global.hljs;

  let configured = false;

  function configureMarked() {
    if (configured || !marked) {
      return;
    }
    marked.setOptions({
      gfm: true,
      breaks: true,
    });
    configured = true;
  }

  function secureLinks(root) {
    root.querySelectorAll("a[href]").forEach((anchor) => {
      anchor.setAttribute("target", "_blank");
      anchor.setAttribute("rel", "noopener noreferrer");
    });
  }

  function sanitizeHtml(html) {
    if (!DOMPurify) {
      return html;
    }
    return DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      ADD_ATTR: ["target", "rel", "class", "aria-hidden"],
    });
  }

  function highlightCodeBlocks(root) {
    if (!hljs) {
      return;
    }
    root.querySelectorAll("pre code").forEach((block) => {
      if (block.dataset.hljsDone === "1") {
        return;
      }
      hljs.highlightElement(block);
      block.dataset.hljsDone = "1";
    });
  }

  function attachCopyButtons(root) {
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.closest(".agent-code-wrap")) {
        return;
      }
      const code = pre.querySelector("code");
      const wrap = document.createElement("div");
      wrap.className = "agent-code-wrap";
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);

      const toolbar = document.createElement("div");
      toolbar.className = "agent-code-toolbar";
      const lang = code?.className?.match(/language-([\w-]+)/)?.[1];
      if (lang) {
        const label = document.createElement("span");
        label.className = "agent-code-lang";
        label.textContent = lang;
        toolbar.appendChild(label);
      }
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "agent-code-copy btn btn-sm";
      copyBtn.textContent = "Copy";
      copyBtn.addEventListener("click", async () => {
        const text = code?.textContent || pre.textContent || "";
        try {
          await navigator.clipboard.writeText(text);
          copyBtn.textContent = "Copied";
          window.setTimeout(() => {
            copyBtn.textContent = "Copy";
          }, 1600);
        } catch {
          copyBtn.textContent = "Failed";
          window.setTimeout(() => {
            copyBtn.textContent = "Copy";
          }, 1600);
        }
      });
      toolbar.appendChild(copyBtn);
      wrap.appendChild(toolbar);
    });
  }

  function renderInto(el, markdown, options = {}) {
    const text = typeof markdown === "string" ? markdown : "";
    el.classList.add("agent-md", "msg-agent-text");
    if (!text) {
      el.replaceChildren();
      return;
    }
    if (!marked || !DOMPurify) {
      el.textContent = text;
      return;
    }
    configureMarked();
    const html = marked.parse(text, { async: false });
    el.innerHTML = sanitizeHtml(html);
    secureLinks(el);
    highlightCodeBlocks(el);
    if (!options.streaming) {
      attachCopyButtons(el);
    }
  }

  function createContainer(markdown) {
    const el = document.createElement("div");
    renderInto(el, markdown);
    return el;
  }

  global.AgentMarkdown = {
    renderInto,
    createContainer,
    isAvailable: Boolean(marked && DOMPurify),
  };
})(window);
