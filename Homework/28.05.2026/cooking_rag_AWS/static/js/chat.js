/* ── Chat interface ──────────────────────────────────────────────────────────── */

const messagesEl = () => document.getElementById("messagesContainer");
const inputEl = () => document.getElementById("questionInput");
const sendBtnEl = () => document.getElementById("sendBtn");

function scrollToBottom(smooth = true) {
  const el = messagesEl();
  if (el)
    el.scrollTo({
      top: el.scrollHeight,
      behavior: smooth ? "smooth" : "instant",
    });
}

function autoResize(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
}

function handleKeyDown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}

function fillQuestion(text) {
  const input = inputEl();
  if (!input) return;
  input.value = text;
  autoResize(input);
  input.focus();
}

/* ── Send message ────────────────────────────────────────────────────────────── */

async function sendMessage() {
  const input = inputEl();
  const question = (input.value || "").trim();
  if (!question) return;

  const sendBtn = sendBtnEl();
  const alertEl = document.getElementById("alert");
  alertEl.style.display = "none";

  // Append user bubble
  appendMessage("user", question);
  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;

  // Show thinking indicator
  const thinkingId = appendThinking();

  try {
    const resp = await fetch("/chat/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await resp.json();

    removeThinking(thinkingId);

    if (resp.ok) {
      appendMessage("assistant", data.answer, data.recipe || null);
    } else {
      showAlert(data.error || "Something went wrong", "error");
      appendMessage("assistant", `⚠️ ${data.error || "An error occurred."}`);
    }
  } catch {
    removeThinking(thinkingId);
    showAlert("Network error — please try again", "error");
  } finally {
    sendBtn.disabled = false;
    scrollToBottom();
  }
}

/* ── DOM helpers ─────────────────────────────────────────────────────────────── */

function appendMessage(role, content, recipeData = null) {
  const container = messagesEl();
  const div = document.createElement("div");
  div.className = `message message--${role}`;

  if (role === "assistant") {
    div.innerHTML = `
      <div class="message-bubble">
        <div class="message-content"></div>
      </div>
      <span class="message-role">👨‍🍳 Chef AI</span>
    `;
    container.appendChild(div);
    mountAssistantContent(div, content, recipeData);
  } else {
    div.innerHTML = `
      <div class="message-bubble">
        <div class="message-content">${escapeHtml(content)}</div>
      </div>
      <span class="message-role">👤 You</span>
    `;
    container.appendChild(div);
  }

  scrollToBottom();
  return div;
}

function appendThinking() {
  const container = messagesEl();
  const div = document.createElement("div");
  div.className = "message message--assistant thinking-bubble";
  div.id = "thinking-" + Date.now();
  div.innerHTML = `<div class="message-bubble"><div class="message-content"></div></div>`;
  container.appendChild(div);
  scrollToBottom();
  return div.id;
}

function removeThinking(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/* ── AI recipe save ─────────────────────────────────────────────────────────── */

const SAVED_RECIPES_STORAGE_KEY = "chefAiSavedRecipes";
const RECIPE_FENCE_RE =
  /```(?:recipe-json|json)\s*\n?([\s\S]*?)```|<recipe-json>\s*([\s\S]*?)<\/recipe-json>/gi;

function normalizeRecipeData(raw) {
  if (!raw || typeof raw !== "object") return null;
  let tags = raw.tags || [];
  if (typeof tags === "string") {
    tags = tags.split(",").map((t) => t.trim()).filter(Boolean);
  }
  const steps = [];
  const rawSteps = Array.isArray(raw.steps) ? raw.steps : raw.steps ? [raw.steps] : [];
  rawSteps.forEach((item) => {
    const s = String(item).trim();
    if (!s) return;
    if ((s.match(/\b\d+[.)]\s/g) || []).length >= 2) {
      s.split(/(?:(?<=[.!?])\s+|\s+)(?=\d+[.)]\s)/).forEach((part) => {
        const cleaned = part.replace(/^\s*\d+[.)]\s*/, "").trim();
        if (cleaned) steps.push(cleaned);
      });
    } else {
      steps.push(s.replace(/^\s*\d+[.)]\s*/, ""));
    }
  });
  return {
    title: String(raw.title || raw.name || "").trim(),
    description: String(raw.description || "").trim(),
    ingredients: (Array.isArray(raw.ingredients) ? raw.ingredients : [])
      .map((i) => String(i).trim())
      .filter(Boolean),
    steps,
    notes: String(raw.notes || "").trim(),
    tags: tags.map((t) => String(t).trim().toLowerCase()).filter(Boolean),
  };
}

function getSavedRecipeKeys() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SAVED_RECIPES_STORAGE_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function markRecipeSaved(data) {
  const keys = getSavedRecipeKeys();
  keys.add(recipeFingerprint(data));
  localStorage.setItem(SAVED_RECIPES_STORAGE_KEY, JSON.stringify([...keys]));
}

function isRecipeSaved(data) {
  return getSavedRecipeKeys().has(recipeFingerprint(data));
}

function recipeFingerprint(data) {
  const title = String(data?.title || "")
    .trim()
    .toLowerCase();
  const ingredients = (data?.ingredients || [])
    .map((item) => String(item).trim().toLowerCase())
    .join("|");
  return `${title}::${ingredients.slice(0, 240)}`;
}

function isValidRecipeData(data) {
  return (
    data &&
    typeof data === "object" &&
    String(data.title || "").trim() &&
    Array.isArray(data.ingredients) &&
    data.ingredients.length > 0 &&
    Array.isArray(data.steps) &&
    data.steps.length > 0
  );
}

function tryParseTrailingRecipeJson(text) {
  const trimmed = String(text || "").trimEnd();
  const start = trimmed.lastIndexOf("{");
  if (start === -1) return null;

  const candidate = trimmed.slice(start);
  try {
    const data = JSON.parse(candidate);
    if (isValidRecipeData(data)) {
      return { display: trimmed.slice(0, start).trimEnd(), data };
    }
  } catch {
    /* not valid JSON */
  }
  return null;
}

function extractRecipeJsonBlocks(content) {
  const blocks = [];
  let display = content || "";

  RECIPE_FENCE_RE.lastIndex = 0;
  let match;
  while ((match = RECIPE_FENCE_RE.exec(content)) !== null) {
    try {
      const data = normalizeRecipeData(JSON.parse((match[1] || match[2] || "").trim()));
      if (isValidRecipeData(data)) {
        blocks.push(data);
      }
    } catch {
      /* ignore invalid JSON fences */
    }
  }

  RECIPE_FENCE_RE.lastIndex = 0;
  display = display.replace(RECIPE_FENCE_RE, "").trim();

  const trailing = tryParseTrailingRecipeJson(display);
  if (trailing) {
    if (!blocks.some((b) => recipeFingerprint(b) === recipeFingerprint(trailing.data))) {
      blocks.push(trailing.data);
    }
    display = trailing.display;
  }

  return { display, blocks };
}

function extractRecipeBlocksFromDom(div) {
  const blocks = [];
  div.querySelectorAll("pre code").forEach((code) => {
    const className = code.className || "";
    if (
      !className.includes("language-recipe-json") &&
      !className.includes("language-json")
    ) {
      return;
    }
    try {
      const data = JSON.parse(code.textContent.trim());
      if (isValidRecipeData(data)) {
        blocks.push(data);
      }
    } catch {
      /* ignore */
    }
  });
  return blocks;
}

function createSavedRecipeLabel() {
  const label = document.createElement("span");
  label.className = "recipe-saved-label";
  label.textContent = "✅ Added to your cookbook";
  return label;
}

function normalizeAssistantMarkdown(text) {
  if (!text) return "";

  let s = String(text);

  // Drop leading catalog row numbers before tags (e.g. "680 Tags:" from KB excerpts).
  s = s.replace(/(^|\n)(\d{1,4})\s+(\*\*Tags:\*\*|Tags:)/g, "$1$3");

  // Plain section labels (common in new-recipe agent replies) -> markdown h2.
  s = s.replace(/^Ingredients:\s*$/gim, "## Ingredients");
  s = s.replace(/^Steps:\s*$/gim, "## Steps");
  s = s.replace(/^Description:\s*$/gim, "## Description");
  s = s.replace(/^Notes:\s*$/gim, "## Notes");

  // Standalone recipe title line before Ingredients -> ## heading.
  s = s.replace(
    /\n(?![#*\-\d])([^\n:#*]{3,100})\n(?:\s*\n)*(## Ingredients\b)/gi,
    "\n## $1\n\n$2",
  );

  // Block headers must start on their own line.
  s = s.replace(/([^\n#])\s+(#{1,3}\s+)/g, "$1\n\n$2");

  // Tags line on its own.
  s = s.replace(/([^\n])\s+(\*\*Tags:\*\*)/g, "$1\n\n$2");
  s = s.replace(/([^\n])\s+(Tags:)/g, "$1\n\n$2");

  // Section headers that were already ## but inline.
  for (const heading of ["Description", "Ingredients", "Steps", "Notes"]) {
    const re = new RegExp(`([^\\n])\\s+(##\\s+${heading}\\b)`, "gi");
    s = s.replace(re, "$1\n\n$2");
  }

  // Indented lines -> markdown list items.
  s = s.replace(/^[ \t]{2,}(.+)$/gm, (_m, item) => {
    const t = item.trim();
    if (!t) return "";
    if (/^\d+\.\s/.test(t)) return t;
    if (t.startsWith("- ") || t.startsWith("* ")) return t;
    return `- ${t}`;
  });

  // Ingredient bullets: " - item - item" -> separate lines.
  s = s.replace(/(## Ingredients[^\n]*)\n?/gi, "$1\n");
  s = s.replace(/(## Ingredients[^\n]*?)\s+-\s+/gi, "$1\n- ");
  s = s.replace(/(\n- [^\n]+?)\s+-\s+/g, "$1\n- ");

  // Numbered steps on one line -> one step per line.
  s = s.replace(/(## Steps[^\n]*)\n?/gi, "$1\n");
  s = s.replace(/([^\n\d])\s+(\d+\.\s+)/g, "$1\n$2");

  // Avoid wrapping the entire recipe in one bold span.
  s = s.replace(/\*\*([^*\n]{240,})\*\*/g, "$1");

  return s.replace(/\n{3,}/g, "\n\n").trim();
}

function parseMarkdownRecipe(text) {
  if (!text) return null;

  const cleaned = String(text)
    .replace(/^\[Authoritative cookbook entry[^\]]*\]\s*\n?/i, "")
    .trim();
  if (!cleaned) return null;

  let title = "";
  const hashTitle = cleaned.match(/^#\s+(.+)$/m);
  if (hashTitle) {
    const candidate = hashTitle[1].trim();
    if (!/^\d+$/.test(candidate) && !candidate.includes("**Tags:**")) {
      title = candidate;
    }
  }
  if (!title) {
    for (const match of cleaned.matchAll(/^##\s+(.+?)\s*$/gm)) {
      const candidate = match[1].trim();
      if (!/^(ingredients|steps|instructions|directions|description|notes)$/i.test(candidate)) {
        title = candidate;
        break;
      }
    }
  }
  if (!title) {
    const intro = cleaned.split("\n", 1)[0];
    const introPatterns = [
      /recipe\s+for\s+(?:(?:a|an|the)\s+)?([^\n:.,!?]{2,60})/i,
      /here(?:'s| is)\s+(?:a\s+)?(?:new\s+)?([^\n:.,!?]{2,60}?)\s+recipe/i,
    ];
    for (const re of introPatterns) {
      const m = intro.match(re);
      if (m) {
        let cand = m[1].replace(/^(a|an|the|new)\s+/i, "").trim().replace(/[.:\-\s]+$/, "");
        if (cand && !/^(ingredients|steps|description|notes)$/i.test(cand)) {
          title = cand.replace(/\b\w/g, (c) => c.toUpperCase());
          break;
        }
      }
    }
  }
  if (!title) return null;

  const sectionRe =
    /^\s*(?:#{1,3}\s+)?\*{0,2}\s*(Ingredients|Steps|Instructions|Directions|Description|Notes)\s*:?\s*\*{0,2}\s*:?\s*$/gim;
  const sectionAliases = { instructions: "steps", directions: "steps" };
  const sections = {};
  const matches = [...cleaned.matchAll(sectionRe)];
  matches.forEach((match, idx) => {
    let name = match[1].toLowerCase();
    name = sectionAliases[name] || name;
    const start = match.index + match[0].length;
    const end = idx + 1 < matches.length ? matches[idx + 1].index : cleaned.length;
    sections[name] = cleaned.slice(start, end).trim();
  });

  const ingredients = [];
  const ingSection = sections.ingredients || "";
  for (const line of ingSection.match(/^\s*[-*]\s+(.+)$/gm) || []) {
    ingredients.push(line.replace(/^\s*[-*]\s+/, "").trim());
  }
  if (!ingredients.length && ingSection.includes(" - ")) {
    ingredients.push(
      ...ingSection
        .split(/\s+-\s+/)
        .map((part) => part.trim())
        .filter(Boolean),
    );
  }

  const steps = [];
  const stepSection = sections.steps || "";
  for (const line of stepSection.match(/^\s*\d+\.\s+(.+)$/gm) || []) {
    steps.push(line.replace(/^\s*\d+\.\s+/, "").trim());
  }

  const tagsMatch = cleaned.match(/^\*\*Tags:\*\*\s*(.+)$/im);
  const tags = tagsMatch
    ? tagsMatch[1]
        .split(",")
        .map((tag) => tag.trim().toLowerCase())
        .filter(Boolean)
    : [];

  const data = {
    title,
    description: sections.description || "",
    ingredients,
    steps,
    notes: sections.notes || "",
    tags,
  };
  return isValidRecipeData(data) ? data : null;
}

function looksLikeFullRecipeAnswer(text) {
  const lower = String(text || "").toLowerCase();
  return lower.includes("ingredient") && (lower.includes("step") || /^\s*\d+\.\s+/m.test(text));
}

function mountAssistantContent(messageDiv, rawContent, serverRecipe = null) {
  const contentEl = messageDiv.querySelector(".message-content");
  if (!contentEl) return;

  const { display, blocks } = extractRecipeJsonBlocks(rawContent);
  if (serverRecipe && isValidRecipeData(serverRecipe)) {
    blocks.push(serverRecipe);
  } else if (!blocks.length && looksLikeFullRecipeAnswer(rawContent)) {
    const parsed = parseMarkdownRecipe(rawContent);
    if (parsed) blocks.push(parsed);
  }

  const normalized = normalizeAssistantMarkdown(display || "");
  contentEl.innerHTML =
    typeof marked !== "undefined"
      ? marked.parse(normalized)
      : escapeHtml(normalized || "");
  attachRecipeButtons(messageDiv, blocks);
}

/**
 * Scan an assistant message for recipe JSON and inject save buttons.
 */
function attachRecipeButtons(div, recipeBlocks = []) {
  if (div.dataset.recipeButtonsDone === "true") return;

  const bubble = div.querySelector(".message-bubble");
  if (!bubble) return;

  const blocks =
    recipeBlocks.length > 0 ? recipeBlocks : extractRecipeBlocksFromDom(div);

  blocks.forEach((data) => {
    if (!isValidRecipeData(data)) return;

    if (isRecipeSaved(data)) {
      if (!bubble.nextElementSibling?.classList.contains("recipe-saved-label")) {
        bubble.after(createSavedRecipeLabel());
      }
      return;
    }

    if (bubble.nextElementSibling?.classList.contains("btn-add-recipe")) {
      return;
    }

    div.querySelectorAll("pre code.language-recipe-json, pre code.language-json").forEach((code) => {
      const pre = code.closest("pre");
      if (pre) pre.style.display = "none";
    });

    const btn = document.createElement("button");
    btn.className = "btn-add-recipe";
    btn.innerHTML = "📥 Add to My Cookbook";
    btn.onclick = () => saveAiRecipe(data, btn);
    bubble.after(btn);
  });

  div.dataset.recipeButtonsDone = "true";
}

/**
 * POST the extracted recipe JSON to the backend and redirect to the new recipe page.
 */
async function saveAiRecipe(data, btn) {
  btn.disabled = true;
  btn.textContent = "⏳ Saving...";
  try {
    const resp = await fetch("/recipes/from-chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const result = await resp.json();
    if (resp.ok) {
      markRecipeSaved(data);
      const label = createSavedRecipeLabel();
      btn.replaceWith(label);
      setTimeout(() => window.open(result.redirect, "_blank"), 700);
    } else {
      btn.disabled = false;
      btn.textContent = "📥 Add to My Cookbook";
      showAlert(result.error || "Failed to save recipe", "error");
    }
  } catch {
    btn.disabled = false;
    btn.textContent = "📥 Add to My Cookbook";
    showAlert("Network error - could not save recipe", "error");
  }
}

/* ── History controls ────────────────────────────────────────────────────────── */

async function clearHistory() {
  if (!confirm("Clear all conversation history?")) return;
  const resp = await fetch("/chat/clear", { method: "POST" });
  if (resp.ok) {
    localStorage.removeItem(SAVED_RECIPES_STORAGE_KEY);
    window.location.reload();
  }
}

/* ── Utilities ───────────────────────────────────────────────────────────────── */

function showAlert(msg, type = "error") {
  const el = document.getElementById("alert");
  el.textContent = msg;
  el.className = `alert alert--${type}`;
  el.style.display = "block";
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
}
