// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { formatDisplayTime } from "../core/format.js";
import { t, getLang, markI18nReady, setLang } from "../locales/i18n.js";
import { ensureDialog, setDialogLanguage, showAlert, showConfirm } from "../core/dialog.js";

function getDuplicatesElements() {
  return {
    duplicatesPage: $(".duplicates-page"),

    duplicatesSummary: $("#duplicatesSummary"),
    duplicatesState: $("#duplicatesState"),
    duplicatesList: $("#duplicatesList"),
    duplicatesPagination: $("#duplicatesPagination"),

    pageInfo: $("#pageInfo"),
    prevPageButton: $("#prevPageButton"),
    nextPageButton: $("#nextPageButton"),
    refreshDuplicatesButton: $("#refreshDuplicatesButton"),
    bulkDeleteDuplicatesButton: $("#bulkDeleteDuplicatesButton"),
    bulkDelete100DuplicatesButton: $("#bulkDelete100DuplicatesButton"),
    duplicateMethodFilter: $("#duplicateMethodFilter"),

    summaryGroupCount: $("#summaryGroupCount"),
    summaryDuplicatesStatus: $("#summaryDuplicatesStatus"),
    summaryGeneratedAt: $("#summaryGeneratedAt"),
    summaryResultRoot: $("#summaryResultRoot"),
    openResultRootButton: $("#openResultRootButton"),
    backToGalleryLink: $("#backToGalleryLink"),
    openTasksToolLink: $("#openTasksToolLink"),
  };
}

function createDuplicatesState() {
  return {
    lang: getLang(),
    payload: null,
    page: 1,
    pageSize: 20,
    methodFilter: "phash",
    selectedByGroup: {},
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

function applyTranslations(els, state) {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : state.lang;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });

  setDialogLanguage(state.lang);
  markI18nReady();
}

function availableGroup(group) {
  const items = group.items?.length
    ? group.items.map((item) => ({
      ...item,
      exists: item.exists !== false,
    }))
    : (group.preview_paths || group.previewPaths || []).map((path) => ({
      path,
      exists: true,
    }));
  const availableItems = items.filter((item) => item.exists);
  const displayItems = availableItems.length ? availableItems : items;

  return {
    ...group,
    isEmpty: items.length === 0,
    availableItems,
    displayItems,
  };
}

function selectedPathFor(state, groupId) {
  return state.selectedByGroup[groupId] || "";
}

function duplicateFileName(path) {
  return String(path || "").split(/[\\/]/).pop() || String(path || "");
}

function duplicateDirectory(path) {
  const value = String(path || "");
  const index = Math.max(value.lastIndexOf("/"), value.lastIndexOf("\\"));
  return index > 0 ? value.slice(0, index) : "-";
}

function isVideoPath(path) {
  return /\.(mp4|webm|mov|m4v|avi|mkv)$/i.test(String(path || ""));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  })[char]);
}

function setInputValue(input, value) {
  if (!input) return;
  input.value = value;
  input.title = value;
}

function setSummaryStatus(els, message) {
  const value = message || "-";
  setText(els.duplicatesState, value);
  setText(els.summaryDuplicatesStatus, shortSummaryStatus(value));
  if (els.summaryDuplicatesStatus) {
    els.summaryDuplicatesStatus.title = value;
  }
}

function setBusyState(els, state, isBusy) {
  state.isBusy = isBusy;

  if (els.bulkDeleteDuplicatesButton) {
    els.bulkDeleteDuplicatesButton.disabled = isBusy || els.bulkDeleteDuplicatesButton.disabled;
  }
  if (els.bulkDelete100DuplicatesButton) {
    els.bulkDelete100DuplicatesButton.disabled = isBusy || els.bulkDelete100DuplicatesButton.disabled;
  }
  if (els.refreshDuplicatesButton) {
    els.refreshDuplicatesButton.disabled = isBusy;
  }
  if (els.duplicateMethodFilter) {
    els.duplicateMethodFilter.disabled = isBusy;
  }
  if (els.prevPageButton) {
    els.prevPageButton.disabled = isBusy || els.prevPageButton.disabled;
  }
  if (els.nextPageButton) {
    els.nextPageButton.disabled = isBusy || els.nextPageButton.disabled;
  }
  if (els.openResultRootButton) {
    els.openResultRootButton.disabled = isBusy || els.openResultRootButton.disabled;
  }
}

function setPaginationVisible(els, visible) {
  if (!els.duplicatesPagination) return;
  els.duplicatesPagination.classList.toggle("is-hidden", !visible);
}

function shortSummaryStatus(message) {
  const text = String(message || "").trim();
  if (!text || text === "-") return "-";

  const ready = t("duplicates.ready");
  const loading = t("duplicates.loading");
  const noResults = t("duplicates.noResults");
  const noMethodResults = t("duplicates.noMethodResults");

  if (text.includes(ready)) return ready;
  if (text.includes(loading)) return loading;
  if (text.includes(noResults)) return noResults;
  if (text.includes(noMethodResults)) return noMethodResults;
  if (text.includes(t("duplicates.openedResultRoot"))) return t("duplicates.openedResultRoot");

  return text.split(/[：:]/)[0] || text;
}

function markDeletedPathInState(state, groupId, path) {
  if (!state.payload?.groups?.length) return;

  const nextGroups = state.payload.groups.map((group) => {
    if (group.group_id !== groupId) return group;

    const items = (group.items || []).map((item) =>
      item.path === path ? { ...item, exists: false } : item,
    );
    const availableCount = items.filter((item) => item.exists).length;

    return {
      ...group,
      items,
      available_count: availableCount,
      preview_paths: items.slice(0, 4).map((item) => item.path),
    };
  });

  state.payload = {
    ...state.payload,
    groups: nextGroups,
  };
}

function normalizedMethod(group) {
  return String(group?.reason || "").trim().toLowerCase();
}

function filteredGroups(state) {
  const groups = state.payload?.groups || [];
  if (state.payload?.page_limit) {
    return groups;
  }
  return groups.filter((group) => normalizedMethod(group) === state.methodFilter);
}

function methodCounts(payload) {
  const counts = {
    phash: 0,
    strict: 0,
  };

  if (payload?.method_counts) {
    counts.phash = Number(payload.method_counts.phash || 0);
    counts.strict = Number(payload.method_counts.strict || 0);
    return counts;
  }

  (payload?.groups || []).forEach((group) => {
    const method = normalizedMethod(group);
    if (method in counts) {
      counts[method] += 1;
    }
  });

  return counts;
}

function chooseInitialMethod(payload, currentMethod) {
  const counts = methodCounts(payload);

  if (counts[currentMethod] > 0) return currentMethod;
  if (counts.phash > 0) return "phash";
  if (counts.strict > 0) return "strict";

  return currentMethod;
}

function strictDuplicateItems(state) {
  if (state.methodFilter !== "strict") return [];

  // Server pagination means this intentionally returns only the current page.
  return filteredGroups(state).flatMap((group) =>
    (group.items || [])
      .filter((item) => item.exists !== false && item.role === "duplicate" && item.path)
      .map((item) => ({
        groupId: group.group_id,
        path: item.path,
      })),
  );
}

function totalPages(state) {
  const count = state.payload?.page_limit
    ? Number(state.payload.group_count || 0)
    : filteredGroups(state).length;
  return Math.max(1, Math.ceil(count / state.pageSize));
}

function pagedDuplicatesUrl(state) {
  const params = new URLSearchParams({
    offset: String((state.page - 1) * state.pageSize),
    limit: String(state.pageSize),
    method: state.methodFilter,
  });
  return `/api/duplicates?${params.toString()}`;
}

function markDuplicateThumbnailError(event) {
  event.currentTarget?.classList.add("is-error");
}

function renderDuplicatesPage(els, state) {
  const payload = state.payload;

  if (!payload?.available) {
    setText(els.duplicatesSummary, t("duplicates.noResults"));
    setSummaryStatus(els, t("duplicates.noResults"));
    els.duplicatesList.innerHTML = "";

    setText(els.summaryGroupCount, "0");
    setText(els.summaryGeneratedAt, "-");
    setInputValue(els.summaryResultRoot, "-");
    setText(els.pageInfo, t("duplicates.pageInfo", 1, 1));

    els.prevPageButton.disabled = true;
    els.nextPageButton.disabled = true;
    els.openResultRootButton.disabled = true;
    setPaginationVisible(els, false);
    return;
  }

  if (!payload.groups?.length) {
    setText(els.duplicatesSummary, t("duplicates.noResults"));
    setSummaryStatus(els, t("duplicates.noResults"));
    els.duplicatesList.innerHTML = "";

    setText(els.summaryGroupCount, "0");
    setText(els.summaryGeneratedAt, formatDisplayTime(payload.generated_at));
    setInputValue(els.summaryResultRoot, payload.destination_root || "-");
    setText(els.pageInfo, t("duplicates.pageInfo", 1, 1));

    els.prevPageButton.disabled = true;
    els.nextPageButton.disabled = true;
    els.openResultRootButton.disabled = !payload.destination_root;
    setPaginationVisible(els, false);
    return;
  }

  if (els.duplicateMethodFilter) {
    els.duplicateMethodFilter.value = state.methodFilter;
  }

  const allGroups = payload.groups || [];
  const activeGroups = filteredGroups(state);
  const isServerPaged = Boolean(payload.page_limit);
  const totalGroupCount = isServerPaged
    ? Number(payload.group_count || activeGroups.length)
    : activeGroups.length;
  const allGroupCount = isServerPaged
    ? Object.values(payload.method_counts || {}).reduce((sum, value) => sum + Number(value || 0), 0)
    : allGroups.length;
  const total = Math.max(1, Math.ceil(totalGroupCount / state.pageSize));
  state.page = Math.min(state.page, total);

  const start = (state.page - 1) * state.pageSize;
  const groups = (isServerPaged ? activeGroups : activeGroups.slice(start, start + state.pageSize))
    .map(availableGroup);

  setText(
    els.duplicatesSummary,
    `${totalGroupCount} / ${allGroupCount || totalGroupCount}`,
  );
  setText(els.summaryGroupCount, String(allGroupCount || totalGroupCount));
  setText(els.summaryGeneratedAt, formatDisplayTime(payload.generated_at));
  setInputValue(els.summaryResultRoot, payload.destination_root || "-");
  setText(els.pageInfo, t("duplicates.pageInfo", state.page, total));

  els.prevPageButton.disabled = state.page <= 1;
  els.nextPageButton.disabled = state.page >= total;
  els.openResultRootButton.disabled = !payload.destination_root;

  const bulkItems = strictDuplicateItems(state);
  if (els.bulkDeleteDuplicatesButton) {
    els.bulkDeleteDuplicatesButton.disabled = state.methodFilter !== "strict" || bulkItems.length === 0;
    els.bulkDeleteDuplicatesButton.title =
      state.methodFilter === "strict"
        ? t("duplicates.bulkStrictTitle", bulkItems.length)
        : t("duplicates.bulkDisabledForPhash");
  }
  if (els.bulkDelete100DuplicatesButton) {
    els.bulkDelete100DuplicatesButton.disabled = state.methodFilter !== "strict" || bulkItems.length === 0;
    els.bulkDelete100DuplicatesButton.title =
      state.methodFilter === "strict"
        ? t("duplicates.bulkStrict100Title")
        : t("duplicates.bulkDisabledForPhash");
  }

  if (!activeGroups.length) {
    setSummaryStatus(els, t("duplicates.noMethodResults"));
    els.duplicatesList.innerHTML = "";
    els.prevPageButton.disabled = true;
    els.nextPageButton.disabled = true;
    setPaginationVisible(els, false);
    return;
  }

  if (!state.isBusy) {
    setSummaryStatus(els, t("duplicates.ready"));
  }
  setPaginationVisible(els, true);

  els.duplicatesList.innerHTML = groups
    .map(
      (group) => `
      <article class="duplicate-group ${group.availableItems.length ? "is-active" : ""}">
        <div class="duplicate-group-summary">
          <div class="duplicate-group-head">
            <strong>${escapeHtml(group.group_id)}</strong>
            <span class="muted">${escapeHtml(t("duplicates.items", group.item_count))}</span>
          </div>
          <div class="duplicates-meta">${escapeHtml(t("duplicates.method", group.reason))}</div>
          ${
            group.availableItems.length === 0
              ? ""
              : `
            <button
              type="button"
              class="danger"
              data-action="delete-selected"
              data-group-id="${escapeHtml(group.group_id)}"
            >
              ${escapeHtml(t("duplicates.deleteSelected"))}
            </button>
          `
          }
        </div>
        <div class="duplicate-group-content">
          ${
            group.isEmpty
              ? `
            <div class="duplicate-group-empty">
              <strong>${escapeHtml(t("duplicates.groupUnavailable"))}</strong>
            </div>
          `
              : `
            <div class="duplicate-thumb-grid">
              ${group.displayItems
                .map(
                  (item) => {
                    const path = item.path;
                    const isDeleted = !item.exists;

                    return `
                <button
                  type="button"
                  class="duplicate-thumb-button ${selectedPathFor(state, group.group_id) === path ? "is-selected" : ""} ${isDeleted ? "is-deleted" : ""}"
                  ${isVideoPath(path) ? 'data-media-type="video"' : ""}
                  ${isDeleted ? "" : `data-action="select-image"`}
                  data-group-id="${escapeHtml(group.group_id)}"
                  data-path="${escapeHtml(path)}"
                  ${isDeleted ? "disabled" : ""}
                >
                  <span class="duplicate-thumb-radio" aria-hidden="true"></span>
                  ${
                    isDeleted
                      ? `<span class="duplicate-thumb duplicate-thumb-placeholder">${escapeHtml(t("duplicates.statusDeleted"))}</span>`
                      : `<img
                          class="duplicate-thumb"
                          src="/api/duplicates/thumbnail?relative_path=${encodeURIComponent(path)}"
                          alt="${escapeHtml(path)}"
                          loading="eager"
                          decoding="async"
                        />`
                  }
                  <span class="duplicate-file-name">${escapeHtml(duplicateFileName(path))}</span>
                  <span class="duplicate-path">${escapeHtml(duplicateDirectory(path))}</span>
                  <span class="duplicate-status ${isDeleted ? "is-deleted" : "is-available"}">
                    ${escapeHtml(t(isDeleted ? "duplicates.statusDeleted" : "duplicates.statusAvailable"))}
                  </span>
                </button>
              `;
                  },
                )
                .join("")}
            </div>
          `
          }
          </div>
      </article>
    `,
    )
    .join("");

  els.duplicatesList
    ?.querySelectorAll("img.duplicate-thumb")
    .forEach((image) => {
      on(image, "error", markDuplicateThumbnailError, { once: true });
    });
}

async function loadDuplicates(els, state) {
  setBusyState(els, state, true);
  setSummaryStatus(els, t("duplicates.loading"));

  try {
    const config = await fetchJson("/api/config");
    state.lang = config.language === "zh-CN" ? "zh" : (config.language || "en");
    setLang(state.lang);

    applyTranslations(els, state);

    state.payload = await fetchJson("/api/duplicates?offset=0&limit=1");
    state.methodFilter = chooseInitialMethod(state.payload, state.methodFilter);
    state.page = 1;
    state.payload = await fetchJson(pagedDuplicatesUrl(state));
  } finally {
    setBusyState(els, state, false);
    renderDuplicatesPage(els, state);
  }
}

async function loadDuplicatesPage(els, state) {
  setBusyState(els, state, true);
  setSummaryStatus(els, t("duplicates.loading"));

  try {
    state.payload = await fetchJson(pagedDuplicatesUrl(state));
  } finally {
    setBusyState(els, state, false);
    renderDuplicatesPage(els, state);
  }
}

async function deleteSelected(els, state, groupId) {
  if (state.isBusy) {
    return;
  }

  const path = selectedPathFor(state, groupId);

  if (!path) {
    const message = t("duplicates.noSelection");
    setSummaryStatus(els, message);
    await showAlert(message, {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  if (
    !(await showConfirm(
      t("delete.confirm.message", path),
      {
        title: t("delete.confirm.title"),
        confirmText: t("delete.confirm.confirm"),
        cancelText: t("dialog.buttons.cancel"),
      },
    ))
  ) {
    return;
  }

  setBusyState(els, state, true);
  setSummaryStatus(els, t("duplicates.deleting", path));

  try {
    await postJson("/api/delete", { relative_path: path });

    state.selectedByGroup[groupId] = "";
    markDeletedPathInState(state, groupId, path);
    renderDuplicatesPage(els, state);

    setSummaryStatus(els, t("duplicates.deleted", path));
  } finally {
    setBusyState(els, state, false);
    renderDuplicatesPage(els, state);
  }
}

async function bulkDeleteStrictDuplicates(els, state) {
  if (state.isBusy) {
    return;
  }

  if (state.methodFilter !== "strict") {
    const message = t("duplicates.bulkDisabledForPhash");
    setSummaryStatus(els, message);
    await showAlert(message, {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  const items = strictDuplicateItems(state);
  if (!items.length) {
    const message = t("duplicates.noStrictDuplicatesToDelete");
    setSummaryStatus(els, message);
    await showAlert(message, {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  if (
    !(await showConfirm(
      t("duplicates.confirmBulkStrictDelete", items.length),
      {
        title: t("duplicates.bulkMoveToRecycle"),
        confirmText: t("duplicates.bulkConfirm"),
        cancelText: t("dialog.buttons.cancel"),
      },
    ))
  ) {
    return;
  }

  setBusyState(els, state, true);
  setSummaryStatus(els, t("duplicates.bulkDeleting", items.length));

  try {
    let deletedCount = 0;
    for (const item of items) {
      await postJson("/api/delete", { relative_path: item.path });
      deletedCount += 1;
      markDeletedPathInState(state, item.groupId, item.path);
    }

    renderDuplicatesPage(els, state);
    setSummaryStatus(els, t("duplicates.bulkDeleted", deletedCount));
  } finally {
    setBusyState(els, state, false);
    renderDuplicatesPage(els, state);
  }
}

async function bulkDelete100StrictDuplicates(els, state) {
  if (state.isBusy) {
    return;
  }

  if (state.methodFilter !== "strict") {
    const message = t("duplicates.bulkDisabledForPhash");
    setSummaryStatus(els, message);
    await showAlert(message, {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  const offset = (state.page - 1) * state.pageSize;
  const payload = await fetchJson(`/api/duplicates?offset=${offset}&limit=100&method=strict`);
  const items = strictDuplicateItems({ ...state, payload, methodFilter: "strict" });
  if (!items.length) {
    const message = t("duplicates.noStrictDuplicatesToDelete");
    setSummaryStatus(els, message);
    await showAlert(message, {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  if (
    !(await showConfirm(
      t("duplicates.confirmBulkStrict100Delete", items.length),
      {
        title: t("duplicates.bulkMove100ToRecycle"),
        confirmText: t("duplicates.bulkConfirm"),
        cancelText: t("dialog.buttons.cancel"),
      },
    ))
  ) {
    return;
  }

  setBusyState(els, state, true);
  setSummaryStatus(els, t("duplicates.bulkDeleting", items.length));

  try {
    let deletedCount = 0;
    for (const item of items) {
      await postJson("/api/delete", { relative_path: item.path });
      deletedCount += 1;
      markDeletedPathInState(state, item.groupId, item.path);
    }

    await loadDuplicatesPage(els, state);
    setSummaryStatus(els, t("duplicates.bulkDeleted", deletedCount));
  } finally {
    setBusyState(els, state, false);
    renderDuplicatesPage(els, state);
  }
}

async function confirmLeaveWhileBusy() {
  return showConfirm(
    t("duplicates.confirmLeaveWhileBusy"),
    {
      title: t("dialog.title.warning"),
      confirmText: t("duplicates.leavePage"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );
}

function bindLeaveGuard(els, state) {
  on(window, "beforeunload", (event) => {
    if (!state.isBusy || state.allowNavigation) {
      return;
    }

    event.preventDefault();
    event.returnValue = "";
  });

  [els.backToGalleryLink, els.openTasksToolLink].forEach((link) => {
    on(link, "click", async (event) => {
      if (!state.isBusy) {
        return;
      }

      event.preventDefault();
      const confirmed = await confirmLeaveWhileBusy();
      if (confirmed) {
        state.allowNavigation = true;
        window.location.href = link.href;
      }
    });
  });
}

function bindDuplicatesEvents(els, state) {
  on(els.prevPageButton, "click", () => {
    state.page = Math.max(1, state.page - 1);
    loadDuplicatesPage(els, state).catch((error) => {
      setSummaryStatus(els, error.message);
      renderDuplicatesPage(els, state);
    });
  });

  on(els.nextPageButton, "click", () => {
    state.page = Math.min(totalPages(state), state.page + 1);
    loadDuplicatesPage(els, state).catch((error) => {
      setSummaryStatus(els, error.message);
      renderDuplicatesPage(els, state);
    });
  });

  on(els.refreshDuplicatesButton, "click", () => {
    loadDuplicates(els, state).catch((error) => {
      setSummaryStatus(els, error.message);
    });
  });

  on(els.bulkDeleteDuplicatesButton, "click", () => {
    bulkDeleteStrictDuplicates(els, state).catch((error) => {
      setSummaryStatus(els, error.message);
      renderDuplicatesPage(els, state);
    });
  });

  on(els.bulkDelete100DuplicatesButton, "click", () => {
    bulkDelete100StrictDuplicates(els, state).catch((error) => {
      setSummaryStatus(els, error.message);
      renderDuplicatesPage(els, state);
    });
  });

  on(els.duplicateMethodFilter, "change", () => {
    state.methodFilter = els.duplicateMethodFilter.value || "phash";
    state.page = 1;
    loadDuplicatesPage(els, state).catch((error) => {
      setSummaryStatus(els, error.message);
      renderDuplicatesPage(els, state);
    });
  });

  on(els.openResultRootButton, "click", async () => {
    try {
      await postJson("/api/duplicates/open-result-root", {});
      setSummaryStatus(els, t("duplicates.openedResultRoot"));
    } catch (error) {
      setSummaryStatus(els, error.message);
    }
  });

  on(els.duplicatesList, "click", (event) => {
    const actionTarget = event.target.closest("[data-action]");
    if (!actionTarget) return;

    const action = actionTarget.dataset.action;
    const groupId = actionTarget.dataset.groupId;
    const path = actionTarget.dataset.path;

    (async () => {
      if (action === "select-image" && groupId && path) {
        state.selectedByGroup[groupId] =
          selectedPathFor(state, groupId) === path ? "" : path;
        renderDuplicatesPage(els, state);
        return;
      }

      if (action === "delete-selected" && groupId) {
        await deleteSelected(els, state, groupId);
      }
    })().catch((error) => {
      setSummaryStatus(els, error.message);
    });
  });
}

function renderDuplicatesInitialState(els) {
  setText(els.duplicatesSummary, "0");
  setSummaryStatus(els, t("duplicates.ready"));
  setText(els.summaryGroupCount, "0");
  setText(els.summaryGeneratedAt, "-");
  setInputValue(els.summaryResultRoot, "-");
  setText(els.pageInfo, t("duplicates.pageInfo", 1, 1));
  els.openResultRootButton.disabled = true;
  if (els.bulkDeleteDuplicatesButton) {
    els.bulkDeleteDuplicatesButton.disabled = true;
    els.bulkDeleteDuplicatesButton.title = t("duplicates.bulkDisabledForPhash");
  }
  if (els.bulkDelete100DuplicatesButton) {
    els.bulkDelete100DuplicatesButton.disabled = true;
    els.bulkDelete100DuplicatesButton.title = t("duplicates.bulkDisabledForPhash");
  }
  setPaginationVisible(els, false);
}

export function initDuplicatesPage() {
  const els = getDuplicatesElements();

  if (!els.duplicatesPage && !els.duplicatesList) return;

  const state = createDuplicatesState();

  ensureDialog();
  renderDuplicatesInitialState(els);
  bindDuplicatesEvents(els, state);
  bindLeaveGuard(els, state);

  loadDuplicates(els, state).catch((error) => {
    setSummaryStatus(els, error.message);
    markI18nReady();
  });

  return { els, state };
}
