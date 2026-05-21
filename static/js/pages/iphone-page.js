// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { markI18nReady, t, translateStaticText } from "../locales/i18n.js";

function getIphoneElements() {
  return {
    iphonePage: $(".iphone-page"),
    iphoneDeviceSelect: $("#iphoneDeviceSelect"),
    iphoneIndexLimitInput: $("#iphoneIndexLimitInput"),
    iphoneCopyAllInput: $("#iphoneCopyAllInput"),
    detectIphoneButton: $("#detectIphoneButton"),
    indexIphoneButton: $("#indexIphoneButton"),
    cancelIphoneIndexButton: $("#cancelIphoneIndexButton"),
    iphoneQueryFilenameInput: $("#iphoneQueryFilenameInput"),
    searchIphoneSimilarButton: $("#searchIphoneSimilarButton"),
    selectAllIphoneResultsButton: $("#selectAllIphoneResultsButton"),
    invertIphoneSelectionButton: $("#invertIphoneSelectionButton"),
    clearIphoneSelectionButton: $("#clearIphoneSelectionButton"),
    moveIphoneResultsButton: $("#moveIphoneResultsButton"),
    deleteIphoneResultsButton: $("#deleteIphoneResultsButton"),
    iphoneStatus: $("#iphoneStatus"),
    iphoneLog: $("#iphoneLog"),
    iphoneResults: $("#iphoneResults"),
    iphoneDeviceName: $("#iphoneDeviceName"),
    iphoneAlbumCount: $("#iphoneAlbumCount"),
    iphoneMediaCount: $("#iphoneMediaCount"),
    iphoneLastIndexedAt: $("#iphoneLastIndexedAt"),
  };
}

function setStatus(els, message) {
  setText(els.iphoneStatus, message);
}

function appendLog(els, message) {
  if (!els.iphoneLog) return;
  const current = els.iphoneLog.textContent.trim();
  els.iphoneLog.textContent = current && current !== t("iphone.logEmpty")
    ? `${current}\n${message}`
    : message;
}

function markPending(els, actionKey) {
  setStatus(els, t("iphone.pending"));
  appendLog(els, t(actionKey));
}

function updateDeviceSummary(els, device) {
  setText(els.iphoneDeviceName, device?.name || "-");
  setText(els.iphoneAlbumCount, String(device?.album_count_sample ?? 0));
  setText(els.iphoneMediaCount, String(device?.media_count_sample ?? 0));
  setText(els.iphoneLastIndexedAt, "-");
}

function renderDeviceOptions(els, devices) {
  if (!els.iphoneDeviceSelect) return;
  els.iphoneDeviceSelect.innerHTML = "";

  if (!devices.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = t("iphone.noDevice");
    els.iphoneDeviceSelect.appendChild(option);
    updateDeviceSummary(els, null);
    return;
  }

  devices.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.device_id || device.name || String(index);
    option.textContent = device.name || option.value;
    els.iphoneDeviceSelect.appendChild(option);
  });
  updateDeviceSummary(els, devices[0]);
}

function getSelectedDeviceId(els) {
  return els.iphoneDeviceSelect?.value.trim() || "";
}

function getIndexLimit(els) {
  const value = Number.parseInt(els.iphoneIndexLimitInput?.value || "1", 10);
  if (!Number.isFinite(value) || value < 1) return 1;
  return Math.min(value, 10000);
}

function updateIndexLimitState(els) {
  if (!els.iphoneIndexLimitInput) return;
  els.iphoneIndexLimitInput.disabled = Boolean(els.iphoneCopyAllInput?.checked);
}

async function detectDevices(els) {
  setStatus(els, t("iphone.detecting"));
  appendLog(els, t("iphone.detecting"));
  try {
    const response = await fetch("/api/iphone/devices");
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    const devices = Array.isArray(data.devices) ? data.devices : [];
    renderDeviceOptions(els, devices);
    setStatus(els, devices.length ? t("iphone.deviceDetected") : t("iphone.noDeviceDetected"));
    appendLog(els, devices.length ? t("iphone.deviceDetected") : (data.message || t("iphone.noDeviceDetected")));
  } catch (error) {
    setStatus(els, t("iphone.detectFailed"));
    appendLog(els, `${t("iphone.detectFailed")}: ${error.message || error}`);
  }
}

async function buildDeviceIndex(els) {
  const deviceId = getSelectedDeviceId(els);
  if (!deviceId) {
    setStatus(els, t("iphone.noDeviceDetected"));
    appendLog(els, t("iphone.noDeviceDetected"));
    return;
  }

  setStatus(els, t("iphone.indexing"));
  appendLog(els, t("iphone.indexing"));
  try {
    const copyAll = Boolean(els.iphoneCopyAllInput?.checked);
    const limit = getIndexLimit(els);
    const response = await fetch("/api/iphone/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId, limit, copy_all: copyAll }),
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    const resultKey = data.status === "imported"
      ? "iphone.indexedImported"
      : data.status === "skipped_duplicate"
        ? "iphone.indexedSkipped"
        : "iphone.indexed";
    const resultCount = data.status === "imported"
      ? data.imported ?? data.indexed ?? 0
      : data.status === "skipped_duplicate"
        ? data.skipped_duplicate ?? data.indexed ?? 0
        : data.indexed ?? 0;
    setStatus(els, t(resultKey, resultCount));
    appendLog(els, t(resultKey, resultCount));
    setText(els.iphoneDeviceName, data.device_name || deviceId);
    setText(els.iphoneAlbumCount, String(data.album_count ?? 0));
    setText(els.iphoneMediaCount, String(data.indexed ?? 0));
    setText(els.iphoneLastIndexedAt, data.indexed_at || "-");
  } catch (error) {
    setStatus(els, t("iphone.indexFailed"));
    appendLog(els, `${t("iphone.indexFailed")}: ${error.message || error}`);
  }
}

function bindIphoneEvents(els) {
  updateIndexLimitState(els);

  on(els.iphoneCopyAllInput, "change", () => {
    updateIndexLimitState(els);
  });

  on(els.detectIphoneButton, "click", () => {
    detectDevices(els);
  });

  on(els.indexIphoneButton, "click", () => {
    buildDeviceIndex(els);
  });

  on(els.cancelIphoneIndexButton, "click", () => {
    markPending(els, "iphone.cancelIndexPending");
  });

  on(els.searchIphoneSimilarButton, "click", () => {
    const filename = els.iphoneQueryFilenameInput?.value.trim();
    markPending(els, filename ? "iphone.searchPending" : "iphone.filenameMissing");
    if (els.iphoneResults) {
      els.iphoneResults.className = "iphone-results muted";
      setText(els.iphoneResults, t("iphone.noResults"));
    }
  });

  on(els.selectAllIphoneResultsButton, "click", () => {
    markPending(els, "iphone.selectAllPending");
  });

  on(els.invertIphoneSelectionButton, "click", () => {
    markPending(els, "iphone.invertSelectionPending");
  });

  on(els.clearIphoneSelectionButton, "click", () => {
    markPending(els, "iphone.clearSelectionPending");
  });

  on(els.moveIphoneResultsButton, "click", () => {
    markPending(els, "iphone.movePending");
  });

  on(els.deleteIphoneResultsButton, "click", () => {
    markPending(els, "iphone.deletePending");
  });
}

export function initIphonePage() {
  const els = getIphoneElements();
  if (!els.iphonePage) return;

  translateStaticText();
  bindIphoneEvents(els);
  setStatus(els, t("iphone.ready"));
  setText(els.iphoneLog, t("iphone.logEmpty"));
  setText(els.iphoneDeviceName, "-");
  setText(els.iphoneAlbumCount, "0");
  setText(els.iphoneMediaCount, "0");
  setText(els.iphoneLastIndexedAt, "-");
  markI18nReady();
}
