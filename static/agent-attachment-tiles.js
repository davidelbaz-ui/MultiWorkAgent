/**
 * Gemini-style attachment chips: preview on top, filename below, rounded tile.
 */
(function initAgentAttachmentTiles(global) {
  const TILE_RADIUS = "12px";

  function fileKind(mime, name) {
    const m = (mime || "").toLowerCase();
    if (m.startsWith("image/")) {
      return "image";
    }
    const lower = (name || "").toLowerCase();
    if (lower.endsWith(".pdf")) {
      return "pdf";
    }
    if (/\.(doc|docx)$/.test(lower)) {
      return "doc";
    }
    if (/\.(xls|xlsx|csv)$/.test(lower)) {
      return "sheet";
    }
    if (/\.(ppt|pptx)$/.test(lower)) {
      return "slide";
    }
    return "file";
  }

  function createFileIconSvg(kind) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "agent-attachment-tile-icon");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("fill", "currentColor");
    if (kind === "pdf") {
      path.setAttribute(
        "d",
        "M6 2h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm7 1.5V8h3.5L13 3.5zM8 12h8v1.5H8V12zm0 3h5v1.5H8V15z",
      );
    } else {
      path.setAttribute(
        "d",
        "M6 2h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm7 1.5V8h3.5L13 3.5z",
      );
    }
    svg.appendChild(path);
    return svg;
  }

  function revokeTrackedUrls(listEl) {
    const urls = listEl._attachmentBlobUrls;
    if (!Array.isArray(urls)) {
      return;
    }
    urls.forEach((url) => {
      try {
        URL.revokeObjectURL(url);
      } catch {
        /* ignore */
      }
    });
    listEl._attachmentBlobUrls = [];
  }

  /**
   * @param {HTMLElement} listEl
   * @param {Array<{ name: string, mime?: string, previewUrl?: string, file?: File }>} items
   * @param {{ onRemove: (index: number) => void, draftFileId?: number }} options
   */
  function renderTiles(listEl, items, options) {
    const onRemove = options.onRemove;
    revokeTrackedUrls(listEl);
    listEl.innerHTML = "";
    listEl.classList.add("agent-attachments--tiles");

    items.forEach((item, index) => {
      const name = item.name || "File";
      const mime = item.mime || "";
      const kind = fileKind(mime, name);

      const tile = document.createElement("li");
      tile.className = "agent-attachment-tile";

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "agent-attachment-tile-remove";
      removeBtn.setAttribute("aria-label", `Remove ${name}`);
      removeBtn.textContent = "×";
      removeBtn.addEventListener("click", () => onRemove(index));

      const preview = document.createElement("div");
      preview.className = "agent-attachment-tile-preview";
      preview.style.borderRadius = TILE_RADIUS;

      let previewUrl = item.previewUrl || "";
      if (!previewUrl && item.file && kind === "image") {
        previewUrl = URL.createObjectURL(item.file);
        if (!listEl._attachmentBlobUrls) {
          listEl._attachmentBlobUrls = [];
        }
        listEl._attachmentBlobUrls.push(previewUrl);
      }
      if (!previewUrl && item.draftFileId && kind === "image") {
        previewUrl = `/api/agent/draft/files/${item.draftFileId}`;
      }

      if (previewUrl && kind === "image") {
        const img = document.createElement("img");
        img.src = previewUrl;
        img.alt = "";
        img.decoding = "async";
        img.loading = "lazy";
        preview.appendChild(img);
      } else {
        preview.classList.add(`agent-attachment-tile-preview--${kind}`);
        preview.appendChild(createFileIconSvg(kind));
      }

      const label = document.createElement("span");
      label.className = "agent-attachment-tile-name";
      label.textContent = name;
      label.title = name;

      tile.append(removeBtn, preview, label);
      listEl.appendChild(tile);
    });
  }

  global.AgentAttachmentTiles = {
    renderTiles,
    revokeTrackedUrls,
    fileKind,
  };
})(window);
