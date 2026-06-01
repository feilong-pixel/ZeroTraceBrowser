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
    buildCacheButton: $("#buildSimilarityCacheButton"),
    startDateInput: $("#similarityStartDateInput"),
    endDateInput: $("#similarityEndDateInput"),
    searchButton: $("#searchSimilarityButton"),
    clearButton: $("#clearSimilarityButton"),
    state: $("#similarityState"),
    results: $("#similarityResults"),
    selectAllButton: $("#selectAllSimilarityResultsButton"),
    invertSelectionButton: $("#invertSimilaritySelectionButton"),
    clearSelectionButton: $("#clearSimilaritySelectionButton"),
    deleteSelectedButton: $("#deleteSimilarityResultsButton"),
    backToGalleryLink: $("#backToGalleryLink"),
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
    isBusy: false,
    allowNavigation: false,
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

function thresholdMaxForMethod(method) {
  if (method === "document") return 256;
  if (method === "feature") return 100;
  if (method === "embedding") return 100;
  return 64;
}

function thresholdDefaultForMethod(method) {
  if (method === "document") return 80;
  if (method === "feature") return 70;
  if (method === "embedding") return 20;
  return 8;
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
  if (els.selectAllButton) els.selectAllButton.disabled = state.isBusy || !hasResults;
  if (els.invertSelectionButton) els.invertSelectionButton.disabled = state.isBusy || !hasResults;
  if (els.clearSelectionButton) els.clearSelectionButton.disabled = state.isBusy || !hasSelection;
  if (els.deleteSelectedButton) els.deleteSelectedButton.disabled = state.isBusy || !hasSelection;
  if (els.startDateInput) els.startDateInput.disabled = state.isBusy || !hasResults;
  if (els.endDateInput) els.endDateInput.disabled = state.isBusy || !hasResults;
}

function setBusyState(els, state, isBusy) {
  state.isBusy = isBusy;
  [
    els.sourceSelect,
    els.queryInput,
    els.methodSelect,
    els.thresholdInput,
    els.limitInput,
    els.searchButton,
    els.buildCacheButton,
    els.clearButton,
  ].forEach((control) => {
    if (control) control.disabled = isBusy;
  });
  updateResultSelection(els, state);
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

function createQueryCard(data) {
  const queryPath = data.query || "";
  const card = document.createElement("article");
  card.className = "card similarity-result-card similarity-query-card";
  card.setAttribute("role", "listitem");

  const badge = document.createElement("div");
  badge.className = "similarity-query-badge";
  badge.textContent = t("similarity.queryCardLabel");

  const image = document.createElement("img");
  image.className = "thumb similarity-result-thumb similarity-query-thumb";
  image.loading = "lazy";
  image.decoding = "async";
  image.width = 320;
  image.height = 320;
  image.alt = queryPath || t("similarity.queryImage");
  image.src = `/api/thumbnail?relative_path=${encodeURIComponent(queryPath)}`;

  const body = document.createElement("div");
  body.className = "card-body similarity-result-body";

  const title = document.createElement("a");
  title.className = "file-name similarity-result-path";
  title.href = viewerUrl(queryPath);
  title.textContent = queryPath.split("/").pop() || queryPath || "-";

  const relative = document.createElement("span");
  relative.className = "file-path";
  relative.textContent = queryPath || "-";

  const meta = document.createElement("div");
  meta.className = "similarity-result-meta similarity-query-meta";
  meta.textContent = t("similarity.queryCardMeta", data.method || "phash", data.threshold ?? "-");

  body.append(title, relative, meta);
  card.append(badge, image, body);
  return card;
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

  const fragment = document.createDocumentFragment();
  fragment.appendChild(createQueryCard(data));

  if (!items.length) {
    els.results.appendChild(fragment);
    setState(els, t("similarity.noMatches"));
    updateResultSelection(els, state);
    return;
  }

  setState(els, t("similarity.ready", items.length), false);

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
    on(path, "click", (event) => {
      if (!state.isBusy) return;
      event.preventDefault();
    });

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
      if (state.isBusy) return;
      if (state.selectedPaths.has(item.relative_path)) {
        state.selectedPaths.delete(item.relative_path);
      } else {
        state.selectedPaths.add(item.relative_path);
      }
      updateResultSelection(els, state);
    });
    on(card, "dblclick", () => {
      if (state.isBusy) return;
      window.location.href = viewerUrl(item.relative_path);
    });
    on(card, "keydown", (event) => {
      if (state.isBusy) return;
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
  if (state.isBusy) return;
  const relativePath = els.queryInput?.value.trim() || "";
  const source = els.sourceSelect?.value || "local";
  const method = els.methodSelect?.value || "phash";
  const threshold = clampNumber(
    els.thresholdInput?.value || String(thresholdDefaultForMethod(method)),
    0,
    thresholdMaxForMethod(method),
    thresholdDefaultForMethod(method),
  );
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
  setBusyState(els, state, true);
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
  } finally {
    setBusyState(els, state, false);
  }
}

async function buildSimilarityCache(els, state) {
  if (state.isBusy) return;
  const source = els.sourceSelect?.value || "local";

  if (source !== "local") {
    setState(els, t("similarity.cacheLocalOnly"));
    return;
  }

  setState(els, t("similarity.cacheBuilding"));
  setBusyState(els, state, true);
  try {
    const data = await postJson("/api/similarity/cache/build", {
      source,
      methods: ["document", "feature", "embedding"],
    });
    setState(
      els,
      t(
        "similarity.cacheBuilt",
        data.processed ?? 0,
        data.method_counts?.document ?? 0,
        data.method_counts?.feature ?? 0,
        data.method_counts?.embedding ?? 0,
        data.skipped_cached ?? 0,
      ),
      false,
    );
  } catch (error) {
    setState(els, `${t("similarity.cacheFailed")}: ${error.message || error}`);
  } finally {
    setBusyState(els, state, false);
  }
}

function selectAllResults(els, state) {
  if (state.isBusy) return;
  state.selectedPaths = new Set(state.items.map((item) => item.relative_path));
  updateResultSelection(els, state);
}

function invertResultSelection(els, state) {
  if (state.isBusy) return;
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
  if (state.isBusy) return;
  state.selectedPaths.clear();
  updateResultSelection(els, state);
}

async function deleteSelectedResults(els, state) {
  if (state.isBusy) return;
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
    setBusyState(els, state, true);
    const selectedPaths = selectedItems.map((item) => item.relative_path);
    setState(
      els,
      selectedItems.length > 1
        ? t("browser.actions.deletingMany", 1, selectedItems.length)
        : t("browser.actions.deleting", selectedPaths[0]),
      false,
    );
    await postJson("/api/delete-batch", { relative_paths: selectedPaths });

    const removedPaths = new Set(selectedPaths);
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
  } finally {
    setBusyState(els, state, false);
  }
}

async function confirmLeaveWhileBusy() {
  return showConfirm(
    t("similarity.confirmLeaveWhileBusy"),
    {
      title: t("dialog.title.confirm"),
      confirmText: t("similarity.leavePage"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );
}

function bindLeaveGuard(els, state) {
  on(window, "beforeunload", (event) => {
    if (!state.isBusy || state.allowNavigation) return;
    event.preventDefault();
    event.returnValue = "";
  });

  on(els.backToGalleryLink, "click", async (event) => {
    if (!state.isBusy) return;
    event.preventDefault();
    const confirmed = await confirmLeaveWhileBusy();
    if (confirmed) {
      state.allowNavigation = true;
      window.location.href = els.backToGalleryLink.href;
    }
  });
}

function applyQueryParams(els) {
  const params = new URLSearchParams(window.location.search);
  const path = params.get("path") || params.get("relative_path") || "";
  if (path && els.queryInput) els.queryInput.value = path;
}

function bindSimilarityEvents(els, state) {
  on(els.searchButton, "click", () => searchSimilarity(els, state));
  on(els.buildCacheButton, "click", () => buildSimilarityCache(els, state));
  on(els.methodSelect, "change", () => {
    if (state.isBusy) return;
    const max = thresholdMaxForMethod(els.methodSelect?.value || "phash");
    const fallback = thresholdDefaultForMethod(els.methodSelect?.value || "phash");
    if (els.thresholdInput) {
      els.thresholdInput.max = String(max);
      els.thresholdInput.value = String(fallback);
    }
  });
  on(els.clearButton, "click", () => {
    if (state.isBusy) return;
    if (els.queryInput) els.queryInput.value = "";
    clearResults(els, state);
  });
  on(els.queryInput, "keydown", (event) => {
    if (state.isBusy) return;
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
  bindLeaveGuard(els, state);
  clearResults(els, state);
  markI18nReady();
}
