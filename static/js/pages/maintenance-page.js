// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { formatDisplayTime } from "../core/format.js";
import { t, getLang, markI18nReady, setLang } from "../locales/i18n.js";
import { ensureDialog, setDialogLanguage, showConfirm } from "../core/dialog.js";

function getMaintenanceElements() {
  return {
    maintenancePage: $(".maintenance-page"),
    galleryIndexRootInput: $("#galleryIndexRootInput"),
    rebuildRootInput: $("#rebuildRootInput"),
    hashMethodSelect: $("#hashMethodSelect"),
    rebuildThresholdInput: $("#rebuild_thresholdInput"),
    runRebuildButton: $("#runRebuildButton"),
    runImageIndexRebuildButton: $("#runImageIndexRebuildButton"),
    timestampRepairRootInput: $("#timestampRepairRootInput"),
    timestampRepairThresholdInput: $("#timestampRepairThresholdInput"),
    syncModifiedTimeCheckbox: $("#syncModifiedTimeCheckbox"),
    renameFromExifCheckbox: $("#renameFromExifCheckbox"),
    includeVideosCheckbox: $("#includeVideosCheckbox"),
    runTimestampRepairButton: $("#runTimestampRepairButton"),
    taskLog: $("#taskLog"),
    liveOutputStatus: $("#liveOutputStatus"),
    taskStatus: $("#taskStatus"),
    taskId: $("#taskId"),
    taskStartedAt: $("#taskStartedAt"),
    taskFinishedAt: $("#taskFinishedAt"),
    logPath: $("#logPath"),
    csvPath: $("#csvPath"),
    hashDbPath: $("#hashDbPath"),
    openLogPathButton: $("#openLogPathButton"),
    openCsvPathButton: $("#openCsvPathButton"),
    openHashDbPathButton: $("#openHashDbPathButton"),
    backToGalleryLink: $("#backToGalleryLink"),
  };
}

function createMaintenanceState() {
  return {
    currentTaskId: null,
    pollHandle: null,
    currentLang: getLang(),
    activeRoot: "",
    isTaskRunning: false,
    allowNavigation: false,
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail === "Another organizer task is already running" ? t("tasks.errors.taskAlreadyRunning") : data.detail || "Request failed");
  }
  return data;
}

function setTaskLog(els, value) {
  if (!els.taskLog || els.taskLog.textContent === value) return;
  setText(els.taskLog, value);
  els.taskLog.scrollTop = els.taskLog.scrollHeight;
}

function setTaskStatus(els, value) {
  setText(els.taskStatus, value);
  setText(els.liveOutputStatus, value);
}

function setOutputPath(input, button, path, exists) {
  if (input) {
    input.value = path || "-";
    input.title = path || "";
  }
  if (button) {
    button.disabled = !path || !exists;
  }
}

function setTaskRunning(els, state, isRunning) {
  state.isTaskRunning = isRunning;
  for (const button of [els.runRebuildButton, els.runImageIndexRebuildButton, els.runTimestampRepairButton]) {
    if (button) button.disabled = isRunning;
  }
}

function updateSummary(els, task) {
  setTaskStatus(els, task?.status || t("tasks.idle"));
  setText(els.taskId, task?.task_id || "-");
  setText(els.taskStartedAt, formatDisplayTime(task?.started_at));
  setText(els.taskFinishedAt, formatDisplayTime(task?.finished_at));
  setOutputPath(els.logPath, els.openLogPathButton, task?.outputs?.log_path || "", task?.outputs?.log_exists);
  setOutputPath(els.csvPath, els.openCsvPathButton, task?.outputs?.duplicate_report_path || "", task?.outputs?.duplicate_report_exists);
  setOutputPath(els.hashDbPath, els.openHashDbPathButton, task?.outputs?.hash_db_path || "", task?.outputs?.hash_db_exists);
  setTaskLog(
    els,
    task?.output_lines?.length
      ? task.output_lines.map((line) => line === "__ZTB_TASK_STILL_RUNNING__" ? t("tasks.stillRunning") : line).join("\n")
      : t("tasks.noTaskOutput"),
  );
}

async function pollTask(els, state, taskIdValue) {
  try {
    const task = await fetchJson(`/api/tasks/${taskIdValue}`);
    updateSummary(els, task);
    if (task.status === "running") {
      setTaskRunning(els, state, true);
      state.pollHandle = window.setTimeout(() => pollTask(els, state, taskIdValue), 1200);
    } else {
      state.pollHandle = null;
      setTaskRunning(els, state, false);
    }
  } catch (error) {
    setTaskLog(els, error.message);
    state.pollHandle = null;
    setTaskRunning(els, state, false);
  }
}

async function runTaskEndpoint(els, state, endpoint, payload, confirmKey, confirmButtonKey, warning = false) {
  if (state.isTaskRunning) return;
  const confirmed = await showConfirm(t(confirmKey), {
    title: warning ? t("dialog.title.warning") : t("dialog.title.confirm"),
    confirmText: t(confirmButtonKey),
    cancelText: t("dialog.buttons.cancel"),
  });
  if (!confirmed) return;
  if (state.pollHandle) window.clearTimeout(state.pollHandle);
  setTaskRunning(els, state, true);
  try {
    const task = await fetchJson(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.currentTaskId = task.task_id;
    updateSummary(els, task);
    pollTask(els, state, state.currentTaskId);
  } catch (error) {
    setTaskLog(els, error.message);
    setTaskRunning(els, state, false);
  }
}

function toggleRebuildThreshold(els) {
  if (!els.rebuildThresholdInput || !els.hashMethodSelect) return;
  els.rebuildThresholdInput.disabled = els.hashMethodSelect.value === "strict";
}

function normalizeThreshold(value) {
  const threshold = Number(value);
  return Number.isFinite(threshold) && threshold >= 0 ? threshold : 4;
}

function setSelectValue(select, value, fallback) {
  if (!select) return;
  const nextValue = value || fallback;
  select.value = nextValue;
  if (select.value !== nextValue) select.value = fallback;
}

async function openOutputPath(els, input) {
  const targetPath = input.value.trim();
  if (!targetPath || targetPath === "-") {
    setTaskLog(els, t("tasks.noDirectoryToOpen"));
    return;
  }
  const result = await fetchJson("/api/open-path", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: targetPath }),
  });
  setTaskLog(els, t("tasks.openedDirectory", result.path));
}

async function restoreRunningTask(els, state) {
  const payload = await fetchJson("/api/tasks/running");
  const task = payload.task;
  if (!task) return;
  state.currentTaskId = task.task_id;
  updateSummary(els, task);
  setTaskRunning(els, state, task.status === "running");
  if (task.status === "running") {
    state.pollHandle = window.setTimeout(() => pollTask(els, state, state.currentTaskId), 1200);
  }
}

function applyTranslations(els, state) {
  document.documentElement.lang = state.currentLang === "zh" ? "zh-CN" : state.currentLang;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  setDialogLanguage(state.currentLang);
  if (!state.currentTaskId) {
    setTaskStatus(els, t("tasks.idle"));
    setTaskLog(els, t("tasks.noTaskStarted"));
  }
  markI18nReady();
}

async function initializeMaintenancePage(els, state) {
  try {
    const config = await fetchJson("/api/config");
    const taskDefaults = config.task_defaults || {};
    const rebuildRoot = config.active_root || "";
    state.activeRoot = config.active_root || "";
    els.galleryIndexRootInput.value = config.active_root || rebuildRoot;
    els.rebuildRootInput.value = rebuildRoot;
    els.timestampRepairRootInput.value = config.active_root || rebuildRoot;
    els.timestampRepairThresholdInput.value = "7";
    els.syncModifiedTimeCheckbox.checked = true;
    els.renameFromExifCheckbox.checked = false;
    els.includeVideosCheckbox.checked = false;
    setSelectValue(els.hashMethodSelect, taskDefaults.rebuild_hash_method, "strict");
    els.rebuildThresholdInput.value = String(normalizeThreshold(taskDefaults.rebuild_phash_threshold ?? taskDefaults.phash_threshold));
    state.currentLang = config.language === "zh-CN" ? "zh" : (config.language || "en");
    setLang(state.currentLang);
    applyTranslations(els, state);
    toggleRebuildThreshold(els);
    await restoreRunningTask(els, state);
  } catch (error) {
    setTaskLog(els, error.message);
    markI18nReady();
  }
}

function bindLeaveGuard(els, state) {
  on(window, "beforeunload", (event) => {
    if (!state.isTaskRunning || state.allowNavigation) return;
    event.preventDefault();
    event.returnValue = "";
  });
  on(els.backToGalleryLink, "click", async (event) => {
    if (!state.isTaskRunning) return;
    event.preventDefault();
    const confirmed = await showConfirm(t("tasks.confirmLeaveWhileRunning"), {
      title: t("dialog.title.warning"),
      confirmText: t("tasks.leavePage"),
      cancelText: t("dialog.buttons.cancel"),
    });
    if (confirmed) {
      state.allowNavigation = true;
      window.location.href = els.backToGalleryLink.href;
    }
  });
}

function bindMaintenanceEvents(els, state) {
  on(els.hashMethodSelect, "change", () => toggleRebuildThreshold(els));
  on(els.runImageIndexRebuildButton, "click", () => {
    runTaskEndpoint(
      els,
      state,
      "/api/tasks/rebuild-image-index",
      { root: state.activeRoot, lang: state.currentLang },
      "tasks.confirmRunImageIndexRebuild",
      "tasks.runImageIndexRebuildTask",
    );
  });
  on(els.runRebuildButton, "click", () => {
    runTaskEndpoint(
      els,
      state,
      "/api/tasks/rebuild-hash-db",
      {
        root: state.activeRoot,
        rebuild_mode: "replace",
        hash_method: els.hashMethodSelect.value,
        phash_threshold: Number(els.rebuildThresholdInput.value || 0),
        lang: state.currentLang,
      },
      "tasks.confirmRunRebuild",
      "tasks.runRebuildTask",
      true,
    );
  });
  on(els.runTimestampRepairButton, "click", () => {
    runTaskEndpoint(
      els,
      state,
      "/api/tasks/repair-timestamps",
      {
        root: els.timestampRepairRootInput.value.trim(),
        threshold_days: Number(els.timestampRepairThresholdInput.value || 7),
        sync_modified_time: Boolean(els.syncModifiedTimeCheckbox.checked),
        rename_from_exif: Boolean(els.renameFromExifCheckbox.checked),
        include_videos: Boolean(els.includeVideosCheckbox.checked),
        lang: state.currentLang,
      },
      "tasks.confirmRunTimestampRepair",
      "tasks.runTimestampRepairTask",
      true,
    );
  });
  for (const [button, input] of [[els.openLogPathButton, els.logPath], [els.openCsvPathButton, els.csvPath], [els.openHashDbPathButton, els.hashDbPath]]) {
    on(button, "click", () => openOutputPath(els, input).catch((error) => setTaskLog(els, error.message)));
  }
}

function renderInitialState(els) {
  setTaskStatus(els, t("tasks.idle"));
  setText(els.taskId, "-");
  setText(els.taskStartedAt, "-");
  setText(els.taskFinishedAt, "-");
  setOutputPath(els.logPath, els.openLogPathButton, "", false);
  setOutputPath(els.csvPath, els.openCsvPathButton, "", false);
  setOutputPath(els.hashDbPath, els.openHashDbPathButton, "", false);
  setTaskLog(els, t("tasks.noTaskStarted"));
}

export function initMaintenancePage() {
  const els = getMaintenanceElements();
  if (!els.maintenancePage) return;
  const state = createMaintenanceState();
  ensureDialog();
  renderInitialState(els);
  bindMaintenanceEvents(els, state);
  bindLeaveGuard(els, state);
  initializeMaintenancePage(els, state).catch((error) => {
    setTaskLog(els, error.message);
    markI18nReady();
  });
  return { els, state };
}
