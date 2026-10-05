function formatBytes(n) {
  const size = Number(n) || 0;
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

async function knowledgeApi(path, options = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...options });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function renderKnowledgeFiles(files) {
  const list = document.getElementById("knowledge-files-list");
  const empty = document.getElementById("knowledge-files-empty");
  if (!list || !empty) {
    return;
  }
  list.innerHTML = "";
  if (!files.length) {
    list.hidden = true;
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  list.hidden = false;
  files.forEach((file) => {
    const li = document.createElement("li");
    li.className = "integration-connection-row";
    li.dataset.fileId = file.id;
    const meta = document.createElement("div");
    meta.innerHTML = `
      <span class="integration-connection-name">${file.original_name}</span>
      <span class="meta-row">${formatBytes(file.size_bytes)}${file.mime_type ? ` · ${file.mime_type}` : ""}</span>`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-sm";
    btn.textContent = "Remove";
    btn.addEventListener("click", () => deleteKnowledgeFile(file.id));
    li.appendChild(meta);
    li.appendChild(btn);
    list.appendChild(li);
  });
}

async function loadKnowledgeFiles(businessId) {
  if (!businessId) {
    renderKnowledgeFiles([]);
    return;
  }
  const data = await knowledgeApi(`/api/businesses/${encodeURIComponent(businessId)}/knowledge-files`);
  renderKnowledgeFiles(data.files || []);
}

async function deleteKnowledgeFile(fileId) {
  const card = document.getElementById("knowledge-files-card");
  const businessId = card?.querySelector("#knowledge-upload-btn")?.dataset.selectedBusinessId || "";
  if (!businessId) {
    return;
  }
  await knowledgeApi(
    `/api/businesses/${encodeURIComponent(businessId)}/knowledge-files/${encodeURIComponent(fileId)}`,
    { method: "DELETE" },
  );
  await loadKnowledgeFiles(businessId);
}

async function uploadKnowledgeFiles(businessId, fileList) {
  for (const file of fileList) {
    const form = new FormData();
    form.append("file", file);
    await knowledgeApi(`/api/businesses/${encodeURIComponent(businessId)}/knowledge-files`, {
      method: "POST",
      body: form,
    });
  }
  await loadKnowledgeFiles(businessId);
}

function initKnowledgeFiles() {
  const card = document.getElementById("knowledge-files-card");
  const uploadBtn = document.getElementById("knowledge-upload-btn");
  const fileInput = document.getElementById("knowledge-file-input");
  if (!card || !uploadBtn || !fileInput) {
    return;
  }

  const businessId = uploadBtn.dataset.selectedBusinessId || "";
  loadKnowledgeFiles(businessId).catch((err) => console.error(err));

  uploadBtn.addEventListener("click", async () => {
    const id = uploadBtn.dataset.selectedBusinessId || "";
    if (!id) {
      if (typeof openSelectBusinessWizard === "function") {
        await openSelectBusinessWizard();
      }
      return;
    }
    fileInput.click();
  });

  fileInput.addEventListener("change", async () => {
    const id = uploadBtn.dataset.selectedBusinessId || "";
    const files = fileInput.files;
    if (!id || !files?.length) {
      fileInput.value = "";
      return;
    }
    uploadBtn.disabled = true;
    try {
      await uploadKnowledgeFiles(id, files);
    } catch (err) {
      console.error(err);
      if (typeof openAppConfirm === "function") {
        await openAppConfirm({
          title: "Upload failed",
          message: err.message || "Could not upload file.",
          confirmLabel: "OK",
        });
      }
    } finally {
      fileInput.value = "";
      uploadBtn.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", initKnowledgeFiles);
