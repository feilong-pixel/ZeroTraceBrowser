// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { ensureDialog, setDialogLanguage, showConfirm } from "../core/dialog.js";
import { markI18nReady, t, setLang, translateStaticText } from "../locales/i18n.js";

function getSettingsElements() {
  return {
    settingsPage: $(".settings-page"),

    // ===== Overview =====
    settingsActiveRoot: $("#settingsActiveRoot"),
    settingsCopyTarget: $("#settingsCopyTarget"),
    settingsLanguage: $("#settingsLanguage"),

    // ===== Language =====
    languageSelect: $("#languageSelect"),
    saveLanguageButton: $("#saveLanguageButton"),

    // ===== Copy Target =====
    copyTargetInput: $("#copyTargetInput"),
    saveCopyTargetButton: $("#saveCopyTargetButton"),
    clearCopyTargetButton: $("#clearCopyTargetButton"),

    // ===== Roots =====
    rootSelect: $("#rootSelect"),
    newRootInput: $("#newRootInput"),
    addRootButton: $("#addRootButton"),
    removeRootButton: $("#removeRootButton"),
    switchRootButton: $("#switchRootButton"),

    // ===== Status =====
    statusMessage: $("#statusMessage"),
  };
}

export function initSettingsPage() {
  const els = getSettingsElements();

  if (!els.settingsPage) return;

  const state = createInitialState();

  ensureDialog();
  bindEvents(els, state);

  loadInitialData(els, state);
}

function createInitialState() {
  return {
    activeRoot: null,
    copyTarget: null,
    language: "en",
    roots: [],
    isBusy: false,
  };
}

async function loadInitialData(els, state) {
  try {
    await refreshConfig(els, state);
    translateStaticText();

    setStatus(els, settingsText("settings.status.ready", "Ready."));
  } catch (err) {
    console.error(err);
    setStatus(els, settingsText("settings.status.loadFailed", "Failed to load settings"));
  } finally {
    markI18nReady();
  }
}

function renderAll(els, state) {
  renderOverview(els, state);
  renderLanguage(els, state);
  renderRoots(els, state);
  renderCopyTarget(els, state);
}

function renderOverview(els, state) {
  setText(els.settingsActiveRoot, state.activeRoot || "-");
  setText(els.settingsCopyTarget, state.copyTarget || "-");
  setText(els.settingsLanguage, getLanguageLabel(state.language));
}

function renderLanguage(els, state) {
  if (els.languageSelect) {
    els.languageSelect.value = state.language;
  }
}

function renderRoots(els, state) {
  const select = els.rootSelect;
  if (!select) return;

  select.innerHTML = "";

  state.roots.forEach((root) => {
    const opt = document.createElement("option");
    opt.value = root;
    opt.textContent = root;
    select.appendChild(opt);
  });

  if (state.activeRoot) {
    select.value = state.activeRoot;
  }

  const hasRoots = state.roots.length > 0;
  if (els.switchRootButton) els.switchRootButton.disabled = state.isBusy || !hasRoots;
  if (els.removeRootButton) els.removeRootButton.disabled = state.isBusy || state.roots.length <= 1;
}

function renderCopyTarget(els, state) {
  if (els.copyTargetInput) {
    els.copyTargetInput.value = state.copyTarget || "";
  }
}

function bindEvents(els, state) {
  // ===== Language =====
  on(els.saveLanguageButton, "click", async () => {
    const nextLanguage = els.languageSelect.value;

    try {
      setBusy(els, state, true);
      await postJson("/api/settings/language", { language: nextLanguage });
      await refreshConfig(els, state);

      translateStaticText();
      setStatus(els, settingsText("settings.status.languageSaved", "Language saved"));
    } catch (err) {
      handleError(els, err);
    } finally {
      setBusy(els, state, false);
    }
  });

  // ===== Copy Target =====
  on(els.saveCopyTargetButton, "click", async () => {
    try {
      setBusy(els, state, true);
      await postJson("/api/settings/copy-target", {
        default_copy_target: els.copyTargetInput.value.trim(),
      });
      await refreshConfig(els, state);

      setStatus(els, settingsText("settings.status.copyTargetSaved", "Default copy target saved"));
    } catch (err) {
      handleError(els, err);
    } finally {
      setBusy(els, state, false);
    }
  });

  on(els.clearCopyTargetButton, "click", async () => {
    try {
      setBusy(els, state, true);
      await postJson("/api/settings/copy-target", {
        default_copy_target: "",
      });
      await refreshConfig(els, state);

      setStatus(els, settingsText("settings.status.copyTargetCleared", "Default copy target cleared"));
    } catch (err) {
      handleError(els, err);
    } finally {
      setBusy(els, state, false);
    }
  });

  // ===== Roots =====
  on(els.addRootButton, "click", async () => {
    const newRoot = els.newRootInput.value.trim();
    if (!newRoot) {
      setStatus(els, settingsText("settings.status.invalidRoot", "Enter a root directory to add"));
      return;
    }

    try {
      setBusy(els, state, true);
      await postJson("/api/settings/roots", { path: newRoot });
      await refreshConfig(els, state);
      els.newRootInput.value = "";

      setStatus(els, settingsText("settings.status.rootAdded", "Root added and switched to current root"));
    } catch (err) {
      handleError(els, err);
    } finally {
      setBusy(els, state, false);
    }
  });

  on(els.removeRootButton, "click", async () => {
    const current = els.rootSelect.value;
    if (!current) return;

    try {
      const confirmed = await showConfirm(
        settingsText("settings.confirmRemoveRoot.message", "Remove this folder from the loaded folder list?"),
        {
          title: settingsText("settings.confirmRemoveRoot.title", "Remove folder"),
          confirmText: settingsText("settings.confirmRemoveRoot.confirm", "Remove"),
        },
      );
      if (!confirmed) return;

      const cleanupRootData = await showConfirm(
        settingsText(
          "settings.confirmCleanupRoot.message",
          "Also clear this folder's generated data and history? This includes hash DB, duplicate results, image summaries, timeline index, delete logs, and local recycle copies for this folder. Original images in the folder are not deleted.",
        ),
        {
          title: settingsText("settings.confirmCleanupRoot.title", "Clear folder history"),
          confirmText: settingsText("settings.confirmCleanupRoot.confirm", "Remove and clear"),
          cancelText: settingsText("settings.confirmCleanupRoot.cancel", "Remove only"),
        },
      );

      setBusy(els, state, true);
      const result = await postJson("/api/settings/remove-root", {
        path: current,
        cleanup_root_data: cleanupRootData,
      });
      await refreshConfig(els, state);

      setStatus(
        els,
        cleanupRootData
          ? settingsText("settings.status.rootRemovedWithCleanup", "Folder removed and related data cleared")
          : settingsText("settings.status.rootRemoved", "Folder removed"),
      );
    } catch (err) {
      handleError(els, err);
    } finally {
      setBusy(els, state, false);
    }
  });

  on(els.switchRootButton, "click", async () => {
    const current = els.rootSelect.value;
    if (!current) return;

    try {
      setBusy(els, state, true);
      await postJson("/api/settings/active-root", { path: current });
      await refreshConfig(els, state);

      setStatus(els, settingsText("settings.status.rootSwitched", "Current root switched"));
    } catch (err) {
      handleError(els, err);
    } finally {
      setBusy(els, state, false);
    }
  });
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function applyConfig(state, config) {
  state.activeRoot = config.active_root || null;
  state.copyTarget = config.default_copy_target || "";
  state.roots = config.image_roots || [];
  state.language = setLang(config.language || "en");
  setDialogLanguage(state.language);
  updateDocumentLanguage(state.language);
}

async function refreshConfig(els, state) {
  applyConfig(state, await fetchJson("/api/config"));
  renderAll(els, state);
}

function setStatus(els, msg) {
  if (!els.statusMessage) return;
  els.statusMessage.textContent = msg;
}

function handleError(els, err) {
  console.error(err);
  setStatus(els, getErrorMessage(err));
}

function settingsText(path, fallback) {
  const value = t(path);
  return value === path ? fallback : value;
}

function getLanguageLabel(language) {
  return {
    zh: "中文",
    en: "English",
    ja: "日本語",
  }[language] || language || "-";
}

function updateDocumentLanguage(language) {
  document.documentElement.lang = language === "zh" ? "zh-CN" : language;
}

function setBusy(els, state, isBusy) {
  state.isBusy = isBusy;

  [
    els.saveLanguageButton,
    els.saveCopyTargetButton,
    els.clearCopyTargetButton,
    els.addRootButton,
    els.switchRootButton,
    els.removeRootButton,
  ].forEach((button) => {
    if (button) button.disabled = isBusy;
  });

  if (!isBusy) {
    renderRoots(els, state);
  }
}

function getErrorMessage(err) {
  const raw = err?.message || "";

  if (raw.includes("At least one root must remain")) {
    return settingsText("settings.status.rootRequired", "At least one root must remain");
  }

  if (raw.includes("Root not registered")) {
    return settingsText("settings.status.rootNotRegistered", "Root not registered");
  }

  if (raw.includes("Unsupported language")) {
    return settingsText("settings.status.unsupportedLanguage", "Unsupported language");
  }

  return raw || settingsText("settings.status.requestFailed", "Request failed");
}
