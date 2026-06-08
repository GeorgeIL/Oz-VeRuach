/* ── Recipe form: dynamic ingredient / step rows ─────────────────────────── */

function addIngredient(value = "") {
  const list = document.getElementById("ingredients-list");
  const row = document.createElement("div");
  row.className = "dynamic-row";
  row.innerHTML = `
    <span class="row-icon">·</span>
    <input type="text" class="ingredient-input"
           placeholder="e.g. 200g spaghetti"
           value="${escapeAttr(value)}" />
    <button type="button" class="btn-remove" onclick="removeRow(this)" title="Remove">✕</button>
  `;
  list.appendChild(row);
  row.querySelector("input").focus();
}

function addStep(value = "") {
  const list = document.getElementById("steps-list");
  const index = list.querySelectorAll(".dynamic-row").length + 1;
  const row = document.createElement("div");
  row.className = "dynamic-row";
  row.innerHTML = `
    <span class="step-number">${index}</span>
    <textarea class="step-input" rows="2"
              placeholder="Describe this step…">${escapeHtml(value)}</textarea>
    <button type="button" class="btn-remove" onclick="removeStep(this)" title="Remove">✕</button>
  `;
  list.appendChild(row);
  row.querySelector("textarea").focus();
}

function removeRow(btn) {
  btn.closest(".dynamic-row").remove();
}

function removeStep(btn) {
  btn.closest(".dynamic-row").remove();
  renumberSteps();
}

function renumberSteps() {
  document.querySelectorAll("#steps-list .step-number").forEach((el, i) => {
    el.textContent = i + 1;
  });
}

/* ── Save / update recipe ───────────────────────────────────────────────────── */

async function saveRecipe(action, slug) {
  const alertEl = document.getElementById("alert");
  alertEl.style.display = "none";

  const title = (document.getElementById("title").value || "").trim();
  const description = (
    document.getElementById("description").value || ""
  ).trim();
  const notes = (document.getElementById("notes").value || "").trim();
  const tagsRaw = document.getElementById("tags").value || "";
  const tags = tagsRaw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  const ingredients = Array.from(document.querySelectorAll(".ingredient-input"))
    .map((el) => el.value.trim())
    .filter(Boolean);

  const steps = Array.from(document.querySelectorAll(".step-input"))
    .map((el) => el.value.trim())
    .filter(Boolean);

  if (!title) {
    showAlert(alertEl, "Recipe title is required", "error");
    return;
  }
  if (ingredients.length === 0) {
    showAlert(alertEl, "Add at least one ingredient", "error");
    return;
  }
  if (steps.length === 0) {
    showAlert(alertEl, "Add at least one step", "error");
    return;
  }

  const method = action === "create" ? "POST" : "PUT";
  const url = action === "create" ? "/recipes/" : `/recipes/${slug}`;
  const btn = document.getElementById("submitBtn");
  btn.disabled = true;

  try {
    const resp = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        description,
        ingredients,
        steps,
        notes,
        tags,
      }),
    });
    const data = await resp.json();
    if (resp.ok) {
      window.location.href = data.redirect;
    } else {
      showAlert(alertEl, data.error || "Save failed", "error");
    }
  } catch {
    showAlert(alertEl, "Network error — please try again", "error");
  } finally {
    btn.disabled = false;
  }
}

/* ── Delete recipe ──────────────────────────────────────────────────────────── */

async function deleteRecipe(slug) {
  if (!confirm("Delete this recipe? This cannot be undone.")) return;

  try {
    const resp = await fetch(`/recipes/${slug}`, { method: "DELETE" });
    const data = await resp.json();
    if (resp.ok) {
      window.location.href = data.redirect;
    } else {
      alert(data.error || "Delete failed");
    }
  } catch {
    alert("Network error");
  }
}

/* ── Utilities ──────────────────────────────────────────────────────────────── */

function showAlert(el, msg, type = "error") {
  el.textContent = msg;
  el.className = `alert alert--${type}`;
  el.style.display = "block";
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function escapeAttr(str) {
  return String(str).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/* ── Recipe image management ─────────────────────────────────────────────────── */

function initRecipeImageManager(slug) {
  const alertEl = document.getElementById("imageAlert");
  const previewEl = document.getElementById("imagePreview");
  const statusLine = document.getElementById("imageStatusLine");
  const urlInput = document.getElementById("imageUrlInput");
  const fileInput = document.getElementById("imageFileInput");
  const setUrlBtn = document.getElementById("setUrlBtn");
  const uploadBtn = document.getElementById("uploadBtn");
  const removeBtn = document.getElementById("removeImageBtn");
  let pollTimer = null;

  function showPreview(url) {
    if (!previewEl) return;
    if (url) {
      previewEl.outerHTML = `<img id="imagePreview" class="recipe-detail-image" src="${escapeAttr(url)}" alt="Recipe image" />`;
    } else {
      previewEl.outerHTML =
        '<div id="imagePreview" class="image-placeholder">No image</div>';
    }
  }

  function setPendingState() {
    const el = document.getElementById("imagePreview");
    if (el && el.tagName !== "IMG") {
      el.className = "image-placeholder image-placeholder--pending";
      el.textContent = "Generating photo…";
    }
    if (statusLine) {
      statusLine.classList.remove("hidden");
    }
  }

  function clearPendingState() {
    if (statusLine) {
      statusLine.classList.add("hidden");
    }
  }

  async function pollStatus() {
    try {
      const resp = await fetch(`/recipes/${slug}/image/status`);
      const data = await resp.json();
      if (!resp.ok) return;

      if (data.status === "pending") {
        setPendingState();
        return;
      }

      clearPendingState();
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }

      if (data.image_url) {
        showPreview(data.image_url);
        if (urlInput) urlInput.value = data.image_url;
      }
    } catch {
      /* ignore transient network errors while polling */
    }
  }

  if (statusLine && !statusLine.classList.contains("hidden")) {
    pollTimer = setInterval(pollStatus, 5000);
    pollStatus();
  }

  if (setUrlBtn) {
    setUrlBtn.addEventListener("click", async () => {
      const imageUrl = (urlInput.value || "").trim();
      if (!imageUrl) {
        showAlert(alertEl, "Enter an image URL", "error");
        return;
      }
      setUrlBtn.disabled = true;
      try {
        const resp = await fetch(`/recipes/${slug}/image`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_url: imageUrl }),
        });
        const data = await resp.json();
        if (resp.ok) {
          showPreview(data.image_url);
          clearPendingState();
          showAlert(alertEl, "Image updated", "success");
        } else {
          showAlert(alertEl, data.error || "Update failed", "error");
        }
      } catch {
        showAlert(alertEl, "Network error", "error");
      } finally {
        setUrlBtn.disabled = false;
      }
    });
  }

  if (uploadBtn) {
    uploadBtn.addEventListener("click", async () => {
      if (!fileInput.files || !fileInput.files[0]) {
        showAlert(alertEl, "Choose an image file first", "error");
        return;
      }
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      uploadBtn.disabled = true;
      try {
        const resp = await fetch(`/recipes/${slug}/image/upload`, {
          method: "POST",
          body: formData,
        });
        const data = await resp.json();
        if (resp.ok) {
          showPreview(data.image_url);
          if (urlInput) urlInput.value = data.image_url;
          clearPendingState();
          fileInput.value = "";
          showAlert(alertEl, "Image uploaded", "success");
        } else {
          showAlert(alertEl, data.error || "Upload failed", "error");
        }
      } catch {
        showAlert(alertEl, "Network error", "error");
      } finally {
        uploadBtn.disabled = false;
      }
    });
  }

  if (removeBtn) {
    removeBtn.addEventListener("click", async () => {
      if (!confirm("Remove this recipe image?")) return;
      removeBtn.disabled = true;
      try {
        const resp = await fetch(`/recipes/${slug}/image`, { method: "DELETE" });
        const data = await resp.json();
        if (resp.ok) {
          showPreview("");
          if (urlInput) urlInput.value = "";
          clearPendingState();
          showAlert(alertEl, "Image removed", "success");
        } else {
          showAlert(alertEl, data.error || "Remove failed", "error");
        }
      } catch {
        showAlert(alertEl, "Network error", "error");
      } finally {
        removeBtn.disabled = false;
      }
    });
  }
}
