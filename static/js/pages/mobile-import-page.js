// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { markI18nReady, t, translateStaticText } from "../locales/i18n.js";

const MOBILE_DEVICE_TYPE = "iphone";

function getMobileImportElements() {
  return {
    mobileImportPage: $(".mobile-import-page"),
    iphoneDeviceSelect: $("#iphoneDeviceSelect"),
    iphoneIndexLimitInput: $("#iphoneIndexLimitInput"),
    iphoneCopyAllInput: $("#iphoneCopyAllInput"),
    detectIphoneButton: $("#detectIphoneButton"),
    indexIphoneButton: $("#indexIphoneButton"),
    cancelIphoneIndexButton: $("#cancelIphoneIndexButton"),
    iphoneStatus: $("#iphoneStatus"),
    iphoneLog: $("#iphoneLog"),
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
  els.iphoneLog.textContent = current && current !== t("mobileImport.logEmpty")
    ? `${current}\n${message}`
    : message;
}

function markPending(els, actionKey) {
  setStatus(els, t("mobileImport.pending"));
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
    option.textContent = t("mobileImport.noDevice");
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
  setStatus(els, t("mobileImport.detecting"));
  appendLog(els, t("mobileImport.detecting"));
  try {
    const response = await fetch(`/api/mobile/devices?device_type=${encodeURIComponent(MOBILE_DEVICE_TYPE)}`);
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    const devices = Array.isArray(data.devices) ? data.devices : [];
    renderDeviceOptions(els, devices);
    setStatus(els, devices.length ? t("mobileImport.deviceDetected") : t("mobileImport.noDeviceDetected"));
    appendLog(els, devices.length ? t("mobileImport.deviceDetected") : (data.message || t("mobileImport.noDeviceDetected")));
  } catch (error) {
    setStatus(els, t("mobileImport.detectFailed"));
    appendLog(els, `${t("mobileImport.detectFailed")}: ${error.message || error}`);
  }
}

async function buildDeviceIndex(els) {
  const deviceId = getSelectedDeviceId(els);
  if (!deviceId) {
    setStatus(els, t("mobileImport.noDeviceDetected"));
    appendLog(els, t("mobileImport.noDeviceDetected"));
    return;
  }

  setStatus(els, t("mobileImport.indexing"));
  appendLog(els, t("mobileImport.indexing"));
  try {
    const copyAll = Boolean(els.iphoneCopyAllInput?.checked);
    const limit = getIndexLimit(els);
    const response = await fetch("/api/mobile/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_type: MOBILE_DEVICE_TYPE, device_id: deviceId, limit, copy_all: copyAll }),
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    const resultKey = data.status === "imported"
      ? "mobileImport.indexedImported"
      : data.status === "skipped_duplicate"
        ? "mobileImport.indexedSkipped"
        : "mobileImport.indexed";
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
    setStatus(els, t("mobileImport.indexFailed"));
    appendLog(els, `${t("mobileImport.indexFailed")}: ${error.message || error}`);
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
    markPending(els, "mobileImport.cancelIndexPending");
  });
}

export function initMobileImportPage() {
  const els = getMobileImportElements();
  if (!els.mobileImportPage) return;

  translateStaticText();
  bindIphoneEvents(els);
  setStatus(els, t("mobileImport.ready"));
  setText(els.iphoneLog, t("mobileImport.logEmpty"));
  setText(els.iphoneDeviceName, "-");
  setText(els.iphoneAlbumCount, "0");
  setText(els.iphoneMediaCount, "0");
  setText(els.iphoneLastIndexedAt, "-");
  markI18nReady();
}
