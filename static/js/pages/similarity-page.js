// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { ensureDialog, setDialogLanguage, showAlert, showConfirm } from "../core/dialog.js";
import { markI18nReady, t, translateStaticText } from "../locales/i18n.js";

function getSimilarityElements() {
  return {
    similarityPage: $(".similarity-page"),
    sourceSelect: $("#similaritySourceSelect"),
    queryInput: $("#similarityQueryPathInput"),
    methodSelect: $("#similarityMethodSelect"),
    thresholdInput: $("#similarityThresholdInput"),
    limitInput: $("#similarityLimitInput"),
    searchButton: $("#searchSimilarityButton"),
    clearButton: $("#clearSimilarityButton"),
    state: $("#similarityState"),
    results: $("#similarityResults"),
    selectAllButton: $("#selectAllSimilarityResultsButton"),
    invertSelectionButton: $("#invertSimilaritySelectionButton"),
    clearSelectionButton: $("#clearSimilaritySelectionButton"),
    deleteSelectedButton: $("#deleteSimilarityResultsButton"),
    summary: $("#similaritySummary"),
    querySummary: $("#similarityQuerySummary"),
    matchCount: $("#similarityMatchCount"),
    methodSummary: $("#similarityMethodSummary"),
    thresholdSummary: $("#similarityThresholdSummary"),
  };
}

function createSimilarityState() {
  return {
    items: [],
    selectedPaths: new Set(),
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}

async function postJson(url, payload) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function clampNumber(value, min, max, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

function setState(els, message, muted = true) {
  if (!els.state) return;
  els.state.className = muted ? "muted" : "";
  setText(els.state, message);
}

function updateSummary(els, queryPath = "-", count = 0, method = "pHash", threshold = 8) {
  setText(els.querySummary, queryPath || "-");
  setText(els.matchCount, String(count));
  setText(els.methodSummary, method);
  setText(els.thresholdSummary, String(threshold));
  setText(els.summary, count ? t("similarity.summary", count) : "-");
}

function getSelectedItems(state) {
  if (!state.selectedPaths.size) return [];
  return state.items.filter((item) => state.selectedPaths.has(item.relative_path));
}

function updateResultSelection(els, state) {
  document.querySelectorAll(".similarity-result-card").forEach((card) => {
    const isSelected = state.selectedPaths.has(card.dataset.path);
    card.classList.toggle("is-selected", isSelected);
    card.setAttribute("aria-selected", isSelected ? "true" : "false");
  });

  const hasResults = state.items.length > 0;
  const hasSelection = state.selectedPaths.size > 0;
  if (els.selectAllButton) els.selectAllButton.disabled = !hasResults;
  if (els.invertSelectionButton) els.invertSelectionButton.disabled = !hasResults;
  if (els.clearSelectionButton) els.clearSelectionButton.disabled = !hasSelection;
  if (els.deleteSelectedButton) els.deleteSelectedButton.disabled = !hasSelection;
}

function clearResults(els, state) {
  if (els.results) els.results.innerHTML = "";
  state.items = [];
  state.selectedPaths.clear();
  setState(els, t("similarity.noResults"));
  updateSummary(els);
  updateResultSelection(els, state);
}

function viewerUrl(relativePath) {
  const returnTo = `${window.location.pathname}${window.location.search}`;
  const params = new URLSearchParams({ path: relativePath, return_to: returnTo });
  return `/viewer.html?${params.toString()}`;
}

function resultTitle(item) {
  return item.mobile_target || item.relative_path.split("/").pop() || item.relative_path;
}

function resultSubtitle(item) {
  if (item.mobile_target && item.mobile_target !== item.relative_path) {
    return `${item.mobile_target} / ${item.relative_path}`;
  }
  return item.relative_path;
}

function resultMethodLabel(item, data) {
  const base = `${data.method || "phash"}:${data.threshold ?? "-"}`;
  if (item.source === "iphone" && item.import_status) {
    return `${base} / ${item.import_status}`;
  }
  return base;
}

function renderResults(els, state, data) {
  const items = Array.isArray(data.items) ? data.items : [];
  if (!els.results) return;
  els.results.innerHTML = "";
  state.items = items;
  state.selectedPaths.clear();

  updateSummary(
    els,
    data.query || "-",
    items.length,
    data.method || "phash",
    data.threshold ?? "-",
  );

  if (!items.length) {
    setState(els, t("similarity.noMatches"));
    return;
  }

  setState(els, t("similarity.ready", items.length), false);

  const fragment = document.createDocumentFragment();
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "card similarity-result-card";
    card.tabIndex = 0;
    card.setAttribute("role", "listitem");
    card.dataset.path = item.relative_path;

    const indicator = document.createElement("div");
    indicator.className = "selection-indicator";

    const image = document.createElement("img");
    image.className = "thumb similarity-result-thumb";
    image.loading = "lazy";
    image.decoding = "async";
    image.width = 320;
    image.height = 320;
    image.alt = resultTitle(item);
    image.src = `/api/thumbnail?relative_path=${encodeURIComponent(item.relative_path)}`;

    const body = document.createElement("div");
    body.className = "card-body similarity-result-body";

    const path = document.createElement("a");
    path.className = "file-name similarity-result-path";
    path.href = viewerUrl(item.relative_path);
    path.textContent = resultTitle(item);

    const relative = document.createElement("span");
    relative.className = "file-path";
    relative.textContent = resultSubtitle(item);

    const meta = document.createElement("div");
    meta.className = "similarity-result-meta";
    const methodLabel = resultMethodLabel(item, data);
    meta.textContent = t(
      "similarity.resultMeta",
      item.distance ?? "-",
      item.score ?? "-",
      methodLabel,
    );

    body.append(path, relative, meta);
    card.append(indicator, image, body);
    on(card, "click", () => {
      if (state.selectedPaths.has(item.relative_path)) {
        state.selectedPaths.delete(item.relative_path);
      } else {
        state.selectedPaths.add(item.relative_path);
      }
      updateResultSelection(els, state);
    });
    on(card, "dblclick", () => {
      window.location.href = viewerUrl(item.relative_path);
    });
    on(card, "keydown", (event) => {
      if (event.key === "Enter") {
        window.location.href = viewerUrl(item.relative_path);
      }
    });
    fragment.appendChild(card);
  });
  els.results.appendChild(fragment);
  updateResultSelection(els, state);
}

async function searchSimilarity(els, state) {
  const relativePath = els.queryInput?.value.trim() || "";
  const source = els.sourceSelect?.value || "local";
  const method = els.methodSelect?.value || "phash";
  const threshold = clampNumber(els.thresholdInput?.value || "8", 0, 64, 8);
  const limit = clampNumber(els.limitInput?.value || "50", 1, 200, 50);

  if (!relativePath) {
    setState(els, t("similarity.queryMissing"));
    return;
  }

  if (source === "android") {
    setState(els, t("similarity.sourceUnavailable"));
    return;
  }

  setState(els, t("similarity.searching"));
  if (els.results) els.results.innerHTML = "";
  state.items = [];
  state.selectedPaths.clear();
  updateResultSelection(els, state);
  updateSummary(els, relativePath, 0, method, threshold);

  try {
    const response = await fetch("/api/similarity/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ relative_path: relativePath, source, method, threshold, limit }),
    });
    if (!response.ok) throw new Error(await response.text());
    renderResults(els, state, await response.json());
  } catch (error) {
    setState(els, `${t("similarity.searchFailed")}: ${error.message || error}`);
  }
}

function selectAllResults(els, state) {
  state.selectedPaths = new Set(state.items.map((item) => item.relative_path));
  updateResultSelection(els, state);
}

function invertResultSelection(els, state) {
  const nextSelectedPaths = new Set(state.selectedPaths);
  for (const item of state.items) {
    if (nextSelectedPaths.has(item.relative_path)) {
      nextSelectedPaths.delete(item.relative_path);
    } else {
      nextSelectedPaths.add(item.relative_path);
    }
  }
  state.selectedPaths = nextSelectedPaths;
  updateResultSelection(els, state);
}

function clearResultSelection(els, state) {
  state.selectedPaths.clear();
  updateResultSelection(els, state);
}

async function deleteSelectedResults(els, state) {
  const selectedItems = getSelectedItems(state);
  if (!selectedItems.length) {
    await showAlert(t("browser.selection.chooseImage"), {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  const confirmed = await showConfirm(
    selectedItems.length > 1
      ? t("delete.confirm.messageMany", selectedItems.length)
      : t("delete.confirm.message", selectedItems[0].relative_path),
    {
      title: t("delete.confirm.title"),
      confirmText: t("delete.confirm.confirm"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );
  if (!confirmed) return;

  try {
    for (let index = 0; index < selectedItems.length; index += 1) {
      const item = selectedItems[index];
      setState(
        els,
        selectedItems.length > 1
          ? t("browser.actions.deletingMany", index + 1, selectedItems.length)
          : t("browser.actions.deleting", item.relative_path),
        false,
      );
      await postJson("/api/delete", { relative_path: item.relative_path });
    }

    const removedPaths = new Set(selectedItems.map((item) => item.relative_path));
    state.items = state.items.filter((item) => !removedPaths.has(item.relative_path));
    state.selectedPaths.clear();
    document.querySelectorAll(".similarity-result-card").forEach((card) => {
      if (removedPaths.has(card.dataset.path)) card.remove();
    });
    updateSummary(els, els.querySummary?.textContent || "-", state.items.length, els.methodSummary?.textContent || "phash", els.thresholdSummary?.textContent || "8");
    updateResultSelection(els, state);
    setState(
      els,
      selectedItems.length > 1
        ? t("browser.actions.deletedMany", selectedItems.length)
        : t("browser.actions.deleted", selectedItems[0].relative_path),
      false,
    );
  } catch (error) {
    setState(els, error.message || String(error));
    await showAlert(error.message || String(error), {
      title: t("dialog.title.error"),
      confirmText: t("dialog.buttons.ok"),
    });
  }
}

function applyQueryParams(els) {
  const params = new URLSearchParams(window.location.search);
  const path = params.get("path") || params.get("relative_path") || "";
  if (path && els.queryInput) els.queryInput.value = path;
}

function bindSimilarityEvents(els, state) {
  on(els.searchButton, "click", () => searchSimilarity(els, state));
  on(els.clearButton, "click", () => {
    if (els.queryInput) els.queryInput.value = "";
    clearResults(els, state);
  });
  on(els.queryInput, "keydown", (event) => {
    if (event.key === "Enter") searchSimilarity(els, state);
  });
  on(els.selectAllButton, "click", () => selectAllResults(els, state));
  on(els.invertSelectionButton, "click", () => invertResultSelection(els, state));
  on(els.clearSelectionButton, "click", () => clearResultSelection(els, state));
  on(els.deleteSelectedButton, "click", () => deleteSelectedResults(els, state));
}

export function initSimilarityPage() {
  const els = getSimilarityElements();
  if (!els.similarityPage) return;
  const state = createSimilarityState();

  translateStaticText();
  ensureDialog();
  setDialogLanguage();
  applyQueryParams(els);
  bindSimilarityEvents(els, state);
  clearResults(els, state);
  markI18nReady();
}
