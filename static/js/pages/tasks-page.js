// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { formatDisplayTime } from "../core/format.js";
import { t, getLang, markI18nReady, setLang } from "../locales/i18n.js";
import { ensureDialog, setDialogLanguage, showConfirm } from "../core/dialog.js";

function getTasksElements() {
  return {
    tasksPage: $(".tasks-page"),

    srcInput: $("#srcInput"),
    dstInput: $("#dstInput"),
    openSrcDirButton: $("#openSrcDirButton"),
    openDstDirButton: $("#openDstDirButton"),
    modeSelect: $("#modeSelect"),
    duplicateSelect: $("#duplicateSelect"),
    thresholdInput: $("#thresholdInput"),
    skipExistingExactCheckbox: $("#skipExistingExactCheckbox"),
    langSelect: $("#langSelect"),

    runTaskButton: $("#runTaskButton"),
    toggleMaintenanceButton: $("#toggleMaintenanceButton"),
    maintenancePanel: $("#maintenancePanel"),

    rebuildRootInput: $("#rebuildRootInput"),
    hashMethodSelect: $("#hashMethodSelect"),
    rebuildThresholdInput: $("#rebuild_thresholdInput"),
    runRebuildButton: $("#runRebuildButton"),
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

function createTasksState() {
  return {
    currentTaskId: null,
    pollHandle: null,
    currentLang: getLang(),
    maintenanceOpen: false,
    activeRoot: "",
    isTaskRunning: false,
    allowNavigation: false,
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(localizeTaskError(data.detail || "Request failed"));
  }

  return data;
}

function localizeTaskError(message) {
  if (message === "Another organizer task is already running") {
    return t("tasks.errors.taskAlreadyRunning");
  }
  return message;
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

function localizeTaskOutputLine(line) {
  return line === "__ZTB_TASK_STILL_RUNNING__" ? t("tasks.stillRunning") : line;
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

  if (els.runTaskButton) {
    els.runTaskButton.disabled = isRunning;
  }

  if (els.runRebuildButton) {
    els.runRebuildButton.disabled = isRunning;
  }

  if (els.runTimestampRepairButton) {
    els.runTimestampRepairButton.disabled = isRunning;
  }
}

async function confirmLeaveWhileRunning() {
  return showConfirm(
    t("tasks.confirmLeaveWhileRunning"),
    {
      title: t("dialog.title.warning"),
      confirmText: t("tasks.leavePage"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );
}

function bindLeaveGuard(els, state) {
  on(window, "beforeunload", (event) => {
    if (!state.isTaskRunning || state.allowNavigation) {
      return;
    }

    event.preventDefault();
    event.returnValue = "";
  });

  on(els.backToGalleryLink, "click", async (event) => {
    if (!state.isTaskRunning) {
      return;
    }

    event.preventDefault();
    const confirmed = await confirmLeaveWhileRunning();
    if (confirmed) {
      state.allowNavigation = true;
      window.location.href = els.backToGalleryLink.href;
    }
  });
}

function applyTranslations(els, state) {
  document.documentElement.lang =
    state.currentLang === "zh" ? "zh-CN" : state.currentLang;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });

  setDialogLanguage(state.currentLang);

  if (els.toggleMaintenanceButton) {
    els.toggleMaintenanceButton.textContent = state.maintenanceOpen
      ? t("tasks.hideHashMaintenance")
      : t("tasks.showHashMaintenance");
  }
  if (!state.currentTaskId) {
    setTaskStatus(els, t("tasks.idle"));
    setTaskLog(els, t("tasks.noTaskStarted"));
  }
  markI18nReady();
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
      ? task.output_lines.map(localizeTaskOutputLine).join("\n")
      : t("tasks.noTaskOutput"),
  );
}

async function pollTask(els, state, taskIdValue) {
  try {
    const task = await fetchJson(`/api/tasks/${taskIdValue}`);
    updateSummary(els, task);

    if (task.status === "running") {
      setTaskRunning(els, state, true);
      state.pollHandle = window.setTimeout(
        () => pollTask(els, state, taskIdValue),
        1200,
      );
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

async function runTask(els, state) {
  if (state.isTaskRunning) {
    return;
  }

  const confirmed = await showConfirm(
    t("tasks.confirmRunTask"),
    {
      title: t("dialog.title.confirm"),
      confirmText: t("tasks.runTask"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) {
    return;
  }

  if (state.pollHandle) {
    window.clearTimeout(state.pollHandle);
  }

  setTaskRunning(els, state, true);

  try {
    const skipExistingExact =
      els.duplicateSelect.value === "strict" && Boolean(els.skipExistingExactCheckbox.checked);
    const task = await fetchJson("/api/tasks/run-organizer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        src: els.srcInput.value.trim(),
        dst: els.dstInput.value.trim(),
        mode: els.modeSelect.value,
        duplicate_detection: els.duplicateSelect.value,
        phash_threshold: Number(els.thresholdInput.value || 0),
        skip_existing_exact: skipExistingExact,
        lang: state.currentLang,
      }),
    });

    state.currentTaskId = task.task_id;
    updateSummary(els, task);
    pollTask(els, state, state.currentTaskId);
  } catch (error) {
    setTaskLog(els, error.message);
    setTaskRunning(els, state, false);
  }
}

async function runRebuildTask(els, state) {
  if (state.isTaskRunning) {
    return;
  }

  const confirmed = await showConfirm(
    t("tasks.confirmRunRebuild"),
    {
      title: t("dialog.title.warning"),
      confirmText: t("tasks.runRebuildTask"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) {
    return;
  }

  if (state.pollHandle) {
    window.clearTimeout(state.pollHandle);
  }

  setTaskRunning(els, state, true);

  try {
    const task = await fetchJson("/api/tasks/rebuild-hash-db", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        root: els.rebuildRootInput.value.trim(),
        rebuild_mode: "replace",
        hash_method: els.hashMethodSelect.value,
        phash_threshold: Number(els.rebuildThresholdInput.value || 0),
        lang: state.currentLang,
      }),
    });

    state.currentTaskId = task.task_id;
    updateSummary(els, task);
    pollTask(els, state, state.currentTaskId);
  } catch (error) {
    setTaskLog(els, error.message);
    setTaskRunning(els, state, false);
  }
}

async function runTimestampRepairTask(els, state) {
  if (state.isTaskRunning) {
    return;
  }

  const confirmed = await showConfirm(
    t("tasks.confirmRunTimestampRepair"),
    {
      title: t("dialog.title.warning"),
      confirmText: t("tasks.runTimestampRepairTask"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) {
    return;
  }

  if (state.pollHandle) {
    window.clearTimeout(state.pollHandle);
  }

  setTaskRunning(els, state, true);

  try {
    const task = await fetchJson("/api/tasks/repair-timestamps", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        root: els.timestampRepairRootInput.value.trim(),
        threshold_days: Number(els.timestampRepairThresholdInput.value || 7),
        sync_modified_time: Boolean(els.syncModifiedTimeCheckbox.checked),
        rename_from_exif: Boolean(els.renameFromExifCheckbox.checked),
        include_videos: Boolean(els.includeVideosCheckbox.checked),
        lang: state.currentLang,
      }),
    });

    state.currentTaskId = task.task_id;
    updateSummary(els, task);
    pollTask(els, state, state.currentTaskId);
  } catch (error) {
    setTaskLog(els, error.message);
    setTaskRunning(els, state, false);
  }
}

function syncMaintenanceState(els, state) {
  if (els.maintenancePanel) {
    els.maintenancePanel.classList.toggle("is-hidden", !state.maintenanceOpen);
  }

  if (els.toggleMaintenanceButton) {
    els.toggleMaintenanceButton.textContent = state.maintenanceOpen
      ? t("tasks.hideHashMaintenance")
      : t("tasks.showHashMaintenance");
  }
}

function toggleThreshold(els) {
  if (!els.thresholdInput || !els.duplicateSelect) return;
  els.thresholdInput.disabled = els.duplicateSelect.value !== "phash";
}

function toggleSkipExistingExact(els) {
  if (!els.skipExistingExactCheckbox || !els.duplicateSelect) return;
  const canSkipExistingExact = els.duplicateSelect.value === "strict";
  els.skipExistingExactCheckbox.disabled = !canSkipExistingExact;
  if (!canSkipExistingExact) {
    els.skipExistingExactCheckbox.checked = false;
  }
}

function toggleRebuildThreshold(els) {
  if (!els.rebuildThresholdInput || !els.hashMethodSelect) return;
  els.rebuildThresholdInput.disabled = els.hashMethodSelect.value === "strict";
}

function setSelectValue(select, value, fallback) {
  if (!select) return;
  const nextValue = value || fallback;
  select.value = nextValue;
  if (select.value !== nextValue) {
    select.value = fallback;
  }
}

function normalizeThreshold(value) {
  const threshold = Number(value);
  return Number.isFinite(threshold) && threshold >= 0 ? threshold : 4;
}

function suggestedTaskDestination(sourceRoot) {
  return sourceRoot ? `${sourceRoot}_organized` : "";
}

async function openDirectoryFromInput(els, state, input) {
  const targetPath = input.value.trim() || state.activeRoot;
  if (!targetPath) {
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

async function initializeTasksPage(els, state) {
  try {
    const config = await fetchJson("/api/config");
    const taskDefaults = config.task_defaults || {};
    state.activeRoot = config.active_root || "";
    const sourceRoot = taskDefaults.src || config.active_root || "";
    const destinationRoot = taskDefaults.dst || suggestedTaskDestination(sourceRoot);
    const rebuildRoot = taskDefaults.rebuild_root || destinationRoot;

    els.srcInput.value = sourceRoot;
    els.dstInput.value = destinationRoot;
    els.rebuildRootInput.value = rebuildRoot;
    if (els.timestampRepairRootInput) {
      els.timestampRepairRootInput.value = config.active_root || rebuildRoot || destinationRoot;
    }
    if (els.timestampRepairThresholdInput) {
      els.timestampRepairThresholdInput.value = "7";
    }
    if (els.syncModifiedTimeCheckbox) {
      els.syncModifiedTimeCheckbox.checked = true;
    }
    if (els.renameFromExifCheckbox) {
      els.renameFromExifCheckbox.checked = false;
    }
    if (els.includeVideosCheckbox) {
      els.includeVideosCheckbox.checked = false;
    }
    setSelectValue(els.modeSelect, taskDefaults.mode, "copy");
    setSelectValue(els.duplicateSelect, taskDefaults.duplicate_detection, "strict");
    setSelectValue(els.hashMethodSelect, taskDefaults.rebuild_hash_method, "strict");
    els.thresholdInput.value = String(normalizeThreshold(taskDefaults.phash_threshold));
    els.skipExistingExactCheckbox.checked = taskDefaults.skip_existing_exact !== false;
    els.rebuildThresholdInput.value = String(
      normalizeThreshold(taskDefaults.rebuild_phash_threshold ?? taskDefaults.phash_threshold),
    );

    state.currentLang = config.language === "zh-CN" ? "zh" : (config.language || "en");
    setLang(state.currentLang);

    els.langSelect.value = state.currentLang;

    applyTranslations(els, state);
    syncMaintenanceState(els, state);
    toggleThreshold(els);
    toggleSkipExistingExact(els);
    toggleRebuildThreshold(els);
    await restoreRunningTask(els, state);
  } catch (error) {
    setTaskLog(els, error.message);
    markI18nReady();
  }
}

async function restoreRunningTask(els, state) {
  const payload = await fetchJson("/api/tasks/running");
  const task = payload.task;
  if (!task) {
    return;
  }

  state.currentTaskId = task.task_id;
  updateSummary(els, task);
  setTaskRunning(els, state, task.status === "running");

  if (task.status === "running") {
    if (state.pollHandle) {
      window.clearTimeout(state.pollHandle);
    }
    state.pollHandle = window.setTimeout(
      () => pollTask(els, state, state.currentTaskId),
      1200,
    );
  }
}

function bindTasksEvents(els, state) {
  on(els.duplicateSelect, "change", () => {
    toggleThreshold(els);
    toggleSkipExistingExact(els);
  });

  on(els.hashMethodSelect, "change", () => {
    toggleRebuildThreshold(els);
  });

  on(els.runTaskButton, "click", () => {
    runTask(els, state);
  });

  on(els.openSrcDirButton, "click", () => {
    openDirectoryFromInput(els, state, els.srcInput).catch((error) => {
      setTaskLog(els, error.message);
    });
  });

  on(els.openDstDirButton, "click", () => {
    openDirectoryFromInput(els, state, els.dstInput).catch((error) => {
      setTaskLog(els, error.message);
    });
  });

  [
    [els.openLogPathButton, els.logPath],
    [els.openCsvPathButton, els.csvPath],
    [els.openHashDbPathButton, els.hashDbPath],
  ].forEach(([button, input]) => {
    on(button, "click", () => {
      openOutputPath(els, input).catch((error) => {
        setTaskLog(els, error.message);
      });
    });
  });

  on(els.runRebuildButton, "click", () => {
    runRebuildTask(els, state);
  });

  on(els.runTimestampRepairButton, "click", () => {
    runTimestampRepairTask(els, state);
  });

  on(els.toggleMaintenanceButton, "click", () => {
    state.maintenanceOpen = !state.maintenanceOpen;
    syncMaintenanceState(els, state);
  });
}

function renderTasksInitialState(els) {
  setTaskStatus(els, t("tasks.idle"));
  setText(els.taskId, "-");
  setText(els.taskStartedAt, "-");
  setText(els.taskFinishedAt, "-");
  setOutputPath(els.logPath, els.openLogPathButton, "", false);
  setOutputPath(els.csvPath, els.openCsvPathButton, "", false);
  setOutputPath(els.hashDbPath, els.openHashDbPathButton, "", false);
  setTaskLog(els, t("tasks.noTaskStarted"));
}

export function initTasksPage() {
  const els = getTasksElements();

  if (!els.tasksPage && !els.runTaskButton) return;

  const state = createTasksState();

  ensureDialog();
  renderTasksInitialState(els);
  bindTasksEvents(els, state);
  bindLeaveGuard(els, state);

  initializeTasksPage(els, state).catch((error) => {
    setTaskLog(els, error.message);
    markI18nReady();
  });

  return { els, state };
}
