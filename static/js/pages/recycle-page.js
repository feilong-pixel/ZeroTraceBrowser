// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { formatDisplayTime } from "../core/format.js";
import { t, getLang, markI18nReady, setLang } from "../locales/i18n.js";
import { ensureDialog, setDialogLanguage, showConfirm } from "../core/dialog.js";

function getRecycleElements() {
  return {
    recyclePage: $(".recycle-page"),

    recycleList: $("#recycleList"),
    recyclePagination: $("#recyclePagination"),
    recyclePageInfo: $("#recyclePageInfo"),
    recycleLogs: $("#recycleLogs"),
    recycleCount: $("#recycleCount"),
    summaryRecycleCount: $("#summaryRecycleCount"),
    summaryLogCount: $("#summaryLogCount"),
    recycleStatus: $("#recycleStatus"),
    recycleLogFilter: $("#recycleLogFilter"),
    recycleLogClearTarget: $("#recycleLogClearTarget"),
    recycleLogSummary: $("#recycleLogSummary"),

    refreshRecycleButton: $("#refreshRecycleButton"),
    prevRecyclePageButton: $("#prevRecyclePageButton"),
    nextRecyclePageButton: $("#nextRecyclePageButton"),
    clearRecycleLogsButton: $("#clearRecycleLogsButton"),
    archiveRecycleLogsButton: $("#archiveRecycleLogsButton"),
    clearRecycleButton: $("#clearRecycleButton"),
    backToGalleryLink: $("#backToGalleryLink"),
  };
}

function createRecycleState() {
  return {
    lang: getLang(),
    recycle: [],
    recycleTotal: 0,
    page: 1,
    pageSize: 20,
    logs: [],
    logFilter: "all",
    itemStatuses: {},
    isBusy: false,
    systemRecycleSupported: true,
  };
}

function setStatus(els, message) {
  const text = message || "-";
  setText(els.recycleStatus, shortStatusText(text));
  if (els.recycleStatus) {
    els.recycleStatus.title = text;
  }
}

function shortStatusText(message) {
  const text = String(message || "").trim();
  if (!text || text === "-") return "-";

  const restored = t("recycle.restoredItem");
  const purged = t("recycle.purgedItem");
  const ready = t("recycle.ready");
  const loading = t("recycle.loading");

  if (text.includes(restored)) return restored;
  if (text.includes(purged)) return purged;
  if (text.includes(loading)) return loading;
  if (text.includes(ready)) return ready;

  return text.split(/[：:]/)[0] || text;
}

function setBusyState(els, state, isBusy) {
  state.isBusy = isBusy;

  if (els.refreshRecycleButton) {
    els.refreshRecycleButton.disabled = isBusy;
  }
  if (els.archiveRecycleLogsButton) {
    els.archiveRecycleLogsButton.disabled = isBusy;
  }
  if (els.recycleLogFilter) {
    els.recycleLogFilter.disabled = isBusy;
  }
  if (els.prevRecyclePageButton) {
    els.prevRecyclePageButton.disabled = isBusy || els.prevRecyclePageButton.disabled;
  }
  if (els.nextRecyclePageButton) {
    els.nextRecyclePageButton.disabled = isBusy || els.nextRecyclePageButton.disabled;
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}

function applyTranslations(els, state) {
  document.documentElement.lang =
    state.lang === "zh" ? "zh-CN" : state.lang;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });

  setDialogLanguage(state.lang);
  markI18nReady();
}

function statusTextFor(state, deletedTo) {
  const status = state.itemStatuses[deletedTo];

  if (status === "restored") return t("recycle.restoredItem");
  if (status === "purged") return t("recycle.purgedItem");

  return t("recycle.pending");
}

function statusClassFor(state, deletedTo) {
  const status = state.itemStatuses[deletedTo];

  if (status === "restored") return "is-success";
  if (status === "purged") return "is-danger";

  return "";
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

function fileNameFromPath(path) {
  return String(path || "").split(/[\\/]/).pop() || String(path || "-");
}

function normalizeLogAction(action) {
  return action || "deleted";
}

function logClearTargetLabel(actions) {
  const key = actions.includes("restored") && actions.includes("purged")
    ? "restoredAndPurged"
    : actions[0];

  return t(`recycle.logClearTargets.${key}`);
}

function recyclePageUrl(state) {
  const params = new URLSearchParams({
    offset: String((state.page - 1) * state.pageSize),
    limit: String(state.pageSize),
  });
  return `/api/recycle-bin?${params.toString()}`;
}

function totalRecyclePages(state) {
  return Math.max(1, Math.ceil(state.recycleTotal / state.pageSize));
}

function setRecyclePaginationVisible(els, visible) {
  if (!els.recyclePagination) return;
  els.recyclePagination.classList.toggle("is-hidden", !visible);
}

function clearRecycleConfirmMessage(state) {
  return state.systemRecycleSupported
    ? t("recycle.confirmClear.messageSystemRecycle")
    : t("recycle.confirmClear.messagePermanent");
}

function purgeConfirmMessage(state, deletedTo) {
  return state.systemRecycleSupported
    ? t("recycle.confirmPurge.messageSystemRecycle", deletedTo)
    : t("recycle.confirmPurge.messagePermanent", deletedTo);
}

function renderRecycleItems(els, state) {
  const total = state.recycleTotal;
  const totalPages = totalRecyclePages(state);
  state.page = Math.min(state.page, totalPages);

  setText(els.recycleCount, t("recycle.itemCount", total));
  setText(els.summaryRecycleCount, String(total));
  setText(els.recyclePageInfo, t("recycle.pageInfo", state.page, totalPages));
  if (els.clearRecycleButton) {
    els.clearRecycleButton.disabled = state.isBusy || total === 0;
    els.clearRecycleButton.title = total === 0 ? t("recycle.noRecycleItems") : "";
  }
  if (els.prevRecyclePageButton) {
    els.prevRecyclePageButton.disabled = state.isBusy || state.page <= 1;
  }
  if (els.nextRecyclePageButton) {
    els.nextRecyclePageButton.disabled = state.isBusy || state.page >= totalPages;
  }

  if (!state.recycle.length) {
    els.recycleList.className = "recycle-list muted";
    setText(els.recycleList, t("recycle.noRecycleItems"));
    setRecyclePaginationVisible(els, false);
    return;
  }

  setRecyclePaginationVisible(els, totalPages > 1);
  els.recycleList.className = "recycle-list";
  els.recycleList.innerHTML = state.recycle
    .map(
      (item) => `
      <article class="recycle-item">
        <div class="recycle-item-layout">
          <div class="recycle-thumb-column">
            <img
              class="recycle-thumb"
              src="/api/recycle-bin/thumbnail?deleted_to=${encodeURIComponent(item.deleted_to)}"
              alt="${item.relative_path || item.name}"
              loading="eager"
              decoding="async"
            />
          </div>
          <div class="recycle-item-content">
            <div class="recycle-item-head">
              <strong>${item.relative_path || item.name}</strong>
              <span class="muted">${item.size}</span>
            </div>
            <div class="recycle-meta">${t("recycle.deletedAt")}: ${formatDisplayTime(item.deleted_at)}</div>
            <div class="recycle-meta">${t("recycle.deletedFile")}: ${item.deleted_to}</div>
            <div class="recycle-meta">${t("recycle.restoreTarget")}: ${item.original_path || "-"}</div>
            <div class="recycle-flags">
              ${
                item.restorable
                  ? ""
                  : `<span class="muted">${t("recycle.restoreUnavailable")}</span>`
              }
              ${
                item.original_exists
                  ? `<span class="recycle-warning">${t("recycle.originalExists")}</span>`
                  : ""
              }
            </div>
            <div class="recycle-item-actions">
              <div class="recycle-status-row">
                <span class="recycle-status-label">${t("recycle.itemStatus")}</span>
                <strong class="recycle-status ${statusClassFor(state, item.deleted_to)}">
                  ${statusTextFor(state, item.deleted_to)}
                </strong>
              </div>
              <button
                type="button"
                data-action="restore"
                data-path="${item.deleted_to}"
                ${state.isBusy || !item.restorable || item.original_exists ? "disabled" : ""}
              >
                ${t("recycle.restoreButton")}
              </button>
              <button
                type="button"
                class="danger"
                data-action="purge"
                data-path="${item.deleted_to}"
                ${state.isBusy ? "disabled" : ""}
              >
                ${t("recycle.confirmPurge.confirm")}
              </button>
            </div>
          </div>
        </div>
      </article>
    `,
    )
    .join("");
}

function renderLogs(els, state) {
  setText(els.summaryLogCount, String(state.logs.length));
  if (els.recycleLogFilter) {
    els.recycleLogFilter.value = state.logFilter;
  }

  if (!state.logs.length) {
    setText(els.recycleLogSummary, t("recycle.logSummary", 0, 0, 0));
    els.recycleLogs.className = "recycle-log-table-wrap muted";
    setText(els.recycleLogs, t("recycle.noLogs"));
    return;
  }

  const filteredLogs = state.logs.filter((row) => {
    if (state.logFilter === "all") return true;
    return normalizeLogAction(row.action) === state.logFilter;
  });
  const visibleLogs = filteredLogs.slice(0, 50);

  setText(
    els.recycleLogSummary,
    t("recycle.logSummary", visibleLogs.length, filteredLogs.length, state.logs.length),
  );

  if (!filteredLogs.length) {
    els.recycleLogs.className = "recycle-log-table-wrap muted";
    setText(els.recycleLogs, t("recycle.noFilteredLogs"));
    return;
  }

  els.recycleLogs.className = "recycle-log-table-wrap";
  els.recycleLogs.innerHTML = `
    <table class="recycle-log-table">
      <thead>
        <tr>
          <th>${escapeHtml(t("recycle.logTable.time"))}</th>
          <th>${escapeHtml(t("recycle.logTable.action"))}</th>
          <th>${escapeHtml(t("recycle.logTable.file"))}</th>
          <th>${escapeHtml(t("recycle.logTable.originalPath"))}</th>
          <th>${escapeHtml(t("recycle.logTable.recyclePath"))}</th>
        </tr>
      </thead>
      <tbody>
        ${visibleLogs
          .map((row) => {
            const action = normalizeLogAction(row.action);
            const recyclePath = row.deleted_to || "-";
            const originalPath = row.relative_path || "-";

            return `
              <tr>
                <td>${escapeHtml(formatDisplayTime(row.timestamp))}</td>
                <td><span class="recycle-log-action is-${escapeHtml(action)}">${escapeHtml(t(`recycle.logActions.${action}`))}</span></td>
                <td title="${escapeHtml(recyclePath)}">${escapeHtml(fileNameFromPath(originalPath !== "-" ? originalPath : recyclePath))}</td>
                <td title="${escapeHtml(row.root || "")}">${escapeHtml(originalPath)}</td>
                <td title="${escapeHtml(recyclePath)}">${escapeHtml(recyclePath)}</td>
              </tr>
            `;
          })
          .join("")}
      </tbody>
    </table>
  `;
}

async function loadAll(els, state) {
  setBusyState(els, state, true);
  setStatus(els, t("recycle.loading"));

  try {
    const config = await fetchJson("/api/config");
    state.lang = config.language === "zh-CN" ? "zh" : (config.language || "en");
    state.systemRecycleSupported = config.system_recycle_supported !== false;
    setLang(state.lang);

    applyTranslations(els, state);

    const [recyclePayload, logPayload] = await Promise.all([
      fetchJson(recyclePageUrl(state)),
      fetchJson("/api/recycle-bin/logs"),
    ]);

    state.recycle = recyclePayload.items || [];
    state.recycleTotal = Number(recyclePayload.count || state.recycle.length);
    state.logs = logPayload.items || [];

    renderRecycleItems(els, state);
    renderLogs(els, state);

    setStatus(els, t("recycle.ready"));
  } finally {
    setBusyState(els, state, false);
    renderRecycleItems(els, state);
    renderLogs(els, state);
  }
}

async function loadRecyclePage(els, state) {
  setBusyState(els, state, true);
  setStatus(els, t("recycle.loading"));

  try {
    const recyclePayload = await fetchJson(recyclePageUrl(state));
    state.recycle = recyclePayload.items || [];
    state.recycleTotal = Number(recyclePayload.count || state.recycle.length);
    renderRecycleItems(els, state);
    setStatus(els, t("recycle.ready"));
  } finally {
    setBusyState(els, state, false);
    renderRecycleItems(els, state);
  }
}

async function restoreItem(els, state, deletedTo) {
  if (state.isBusy) return;

  const confirmed = await showConfirm(
    t("recycle.confirmRestore.message", deletedTo),
    {
      title: t("recycle.confirmRestore.title"),
      confirmText: t("recycle.confirmRestore.confirm"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) return;

  setBusyState(els, state, true);
  setStatus(els, t("recycle.loading"));

  try {
    const result = await fetchJson("/api/recycle-bin/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deleted_to: deletedTo }),
    });

    state.itemStatuses[deletedTo] = "restored";
    renderRecycleItems(els, state);

    setStatus(els, t("recycle.restored", result.restored_to));
  } finally {
    setBusyState(els, state, false);
    renderRecycleItems(els, state);
  }
}

async function clearRecycleBin(els, state) {
  if (state.isBusy) return;

  const confirmed = await showConfirm(
    clearRecycleConfirmMessage(state),
    {
      title: t("recycle.confirmClear.title"),
      confirmText: t("recycle.confirmClear.confirm"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) return;

  setBusyState(els, state, true);
  setStatus(els, t("recycle.loading"));

  try {
    const result = await fetchJson("/api/recycle-bin/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });

    await loadAll(els, state);
    const archive = result.log_archive;
    setStatus(
      els,
      archive?.archived
        ? t("recycle.clearedAndArchived", result.removed_count || 0, archive.archive_path)
        : t("recycle.cleared", result.removed_count || 0),
    );
  } finally {
    setBusyState(els, state, false);
    renderRecycleItems(els, state);
    renderLogs(els, state);
  }
}

async function archiveRecycleLogs(els, state) {
  if (state.isBusy) return;

  const confirmed = await showConfirm(
    t("recycle.confirmArchiveLogs.message"),
    {
      title: t("recycle.confirmArchiveLogs.title"),
      confirmText: t("recycle.confirmArchiveLogs.confirm"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) return;

  setBusyState(els, state, true);
  setStatus(els, t("recycle.loading"));

  try {
    const result = await fetchJson("/api/recycle-bin/logs/archive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });

    await loadAll(els, state);
    setStatus(
      els,
      result.archived
        ? t("recycle.archivedLogs", result.archived_count || 0, result.archive_path)
        : t("recycle.noLogsToArchive"),
    );
  } finally {
    setBusyState(els, state, false);
    renderRecycleItems(els, state);
    renderLogs(els, state);
  }
}

async function clearRecycleLogs(els, state) {
  if (state.isBusy) return;

  const actions = (els.recycleLogClearTarget?.value || "purged")
    .split(",")
    .filter(Boolean);
  const targetLabel = logClearTargetLabel(actions);
  const confirmed = await showConfirm(
    t("recycle.confirmClearLogs.message", targetLabel),
    {
      title: t("recycle.confirmClearLogs.title"),
      confirmText: t("recycle.confirmClearLogs.confirm"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) return;

  setBusyState(els, state, true);
  setStatus(els, t("recycle.loading"));

  try {
    const result = await fetchJson("/api/recycle-bin/logs/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true, actions }),
    });

    await loadAll(els, state);
    setStatus(els, t("recycle.clearedLogs", result.removed_count || 0, targetLabel));
  } finally {
    setBusyState(els, state, false);
    renderRecycleItems(els, state);
    renderLogs(els, state);
  }
}

async function purgeItem(els, state, deletedTo) {
  if (state.isBusy) return;

  const confirmed = await showConfirm(
    purgeConfirmMessage(state, deletedTo),
    {
      title: t("recycle.confirmPurge.title"),
      confirmText: t("recycle.confirmPurge.confirm"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) return;

  setBusyState(els, state, true);
  setStatus(els, t("recycle.loading"));

  try {
    const result = await fetchJson("/api/recycle-bin/purge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deleted_to: deletedTo }),
    });

    state.itemStatuses[deletedTo] = "purged";
    renderRecycleItems(els, state);

    setStatus(els, t("recycle.purged", result.deleted_to));
  } finally {
    setBusyState(els, state, false);
    renderRecycleItems(els, state);
  }
}

async function confirmLeaveWhileBusy() {
  return showConfirm(
    t("recycle.confirmLeaveWhileBusy"),
    {
      title: t("dialog.title.warning"),
      confirmText: t("recycle.leavePage"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );
}

function bindLeaveGuard(els, state) {
  on(window, "beforeunload", (event) => {
    if (!state.isBusy) return;
    event.preventDefault();
    event.returnValue = "";
  });

  on(els.backToGalleryLink, "click", async (event) => {
    if (!state.isBusy) return;
    event.preventDefault();
    const confirmed = await confirmLeaveWhileBusy();
    if (confirmed) {
      window.location.href = els.backToGalleryLink.href;
    }
  });
}

function bindRecycleEvents(els, state) {
  on(els.recycleList, "click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;

    if (button.dataset.action === "restore") {
      restoreItem(els, state, button.dataset.path).catch((error) => {
        setStatus(els, error.message);
      });
      return;
    }

    if (button.dataset.action === "purge") {
      purgeItem(els, state, button.dataset.path).catch((error) => {
        setStatus(els, error.message);
      });
    }
  });

  on(els.refreshRecycleButton, "click", () => {
    state.page = 1;
    loadAll(els, state).catch((error) => {
      setStatus(els, error.message);
    });
  });

  on(els.prevRecyclePageButton, "click", () => {
    state.page = Math.max(1, state.page - 1);
    loadRecyclePage(els, state).catch((error) => {
      setStatus(els, error.message);
      renderRecycleItems(els, state);
    });
  });

  on(els.nextRecyclePageButton, "click", () => {
    state.page = Math.min(totalRecyclePages(state), state.page + 1);
    loadRecyclePage(els, state).catch((error) => {
      setStatus(els, error.message);
      renderRecycleItems(els, state);
    });
  });

  on(els.clearRecycleButton, "click", () => {
    clearRecycleBin(els, state).catch((error) => {
      setStatus(els, error.message);
    });
  });

  on(els.clearRecycleLogsButton, "click", () => {
    clearRecycleLogs(els, state).catch((error) => {
      setStatus(els, error.message);
    });
  });

  on(els.archiveRecycleLogsButton, "click", () => {
    archiveRecycleLogs(els, state).catch((error) => {
      setStatus(els, error.message);
    });
  });

  on(els.recycleLogFilter, "change", () => {
    state.logFilter = els.recycleLogFilter.value || "all";
    renderLogs(els, state);
  });

}

function renderRecycleInitialState(els) {
  setText(els.recycleCount, "0");
  setText(els.summaryRecycleCount, "0");
  setText(els.summaryLogCount, "0");
  setText(els.recycleStatus, t("recycle.ready"));
  setText(els.recyclePageInfo, t("recycle.pageInfo", 1, 1));
  setRecyclePaginationVisible(els, false);
  if (els.clearRecycleButton) {
    els.clearRecycleButton.disabled = true;
    els.clearRecycleButton.title = t("recycle.noRecycleItems");
  }
}

export function initRecyclePage() {
  const els = getRecycleElements();

  if (!els.recyclePage && !els.recycleList) return;

  const state = createRecycleState();

  ensureDialog();
  renderRecycleInitialState(els);
  bindRecycleEvents(els, state);
  bindLeaveGuard(els, state);

  loadAll(els, state).catch((error) => {
    setStatus(els, error.message);
    markI18nReady();
  });

  return { els, state };
}
