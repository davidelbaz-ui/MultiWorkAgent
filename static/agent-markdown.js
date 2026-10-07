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

  function fenceLanguage(codeEl) {
    if (!codeEl) {
      return "";
    }
    const fromClass = codeEl.className.match(/language-([\w-]+)/)?.[1];
    if (fromClass && fromClass !== "plaintext" && fromClass !== "text") {
      return fromClass;
    }
    const fromData = codeEl.dataset.agentLang;
    return fromData || "";
  }

  function displayLanguageLabel(lang) {
    if (!lang) {
      return "Code";
    }
    const normalized = lang.toLowerCase();
    const aliases = {
      shell: "Shell",
      sh: "Shell",
      bash: "Bash",
      yml: "YAML",
      yaml: "YAML",
      js: "JavaScript",
      ts: "TypeScript",
      py: "Python",
      rb: "Ruby",
      md: "Markdown",
      json: "JSON",
      plaintext: "Code",
      text: "Code",
    };
    return aliases[normalized] || normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }

  function highlightCodeBlocks(root) {
    if (!hljs) {
      return;
    }
    root.querySelectorAll("pre code").forEach((block) => {
      if (block.dataset.hljsDone === "1") {
        return;
      }
      const explicitLang = fenceLanguage(block);
      if (explicitLang) {
        try {
          hljs.highlightElement(block);
        } catch {
          block.classList.add("language-plaintext");
        }
      } else {
        block.classList.add("language-plaintext");
      }
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

      const toolbar = document.createElement("div");
      toolbar.className = "agent-code-toolbar";
      const lang = fenceLanguage(code);
      const label = document.createElement("span");
      label.className = "agent-code-lang";
      label.textContent = displayLanguageLabel(lang);
      toolbar.appendChild(label);
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "agent-code-copy msg-action-btn";
      copyBtn.setAttribute("aria-label", "Copy code");
      const copySvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      copySvg.setAttribute("class", "msg-action-icon");
      copySvg.setAttribute("viewBox", "0 0 24 24");
      copySvg.setAttribute("aria-hidden", "true");
      copySvg.setAttribute("fill", "none");
      copySvg.setAttribute("stroke", "currentColor");
      copySvg.setAttribute("stroke-width", "2");
      copySvg.setAttribute("stroke-linecap", "round");
      copySvg.setAttribute("stroke-linejoin", "round");
      [
        "M8 8H6a2 2 0 0 0-2-2V6a2 2 0 0 0 2-2h8a2 2 0 0 0 2 2v2",
        "M16 16H8a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2z",
      ].forEach((d) => {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d);
        copySvg.appendChild(path);
      });
      copyBtn.appendChild(copySvg);
      copyBtn.addEventListener("click", async () => {
        const text = code?.textContent || pre.textContent || "";
        try {
          await navigator.clipboard.writeText(text);
          copyBtn.classList.add("is-copied");
          window.setTimeout(() => copyBtn.classList.remove("is-copied"), 1600);
        } catch {
          copyBtn.classList.add("is-copy-failed");
          window.setTimeout(() => copyBtn.classList.remove("is-copy-failed"), 1600);
        }
      });
      toolbar.appendChild(copyBtn);
      wrap.appendChild(toolbar);
      wrap.appendChild(pre);
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
