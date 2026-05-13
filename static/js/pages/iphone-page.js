// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { markI18nReady, t, translateStaticText } from "../locales/i18n.js";

function getIphoneElements() {
  return {
    iphonePage: $(".iphone-page"),
    iphoneDeviceSelect: $("#iphoneDeviceSelect"),
    detectIphoneButton: $("#detectIphoneButton"),
    indexIphoneButton: $("#indexIphoneButton"),
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

function bindIphoneEvents(els) {
  on(els.detectIphoneButton, "click", () => {
    detectDevices(els);
  });

  on(els.indexIphoneButton, "click", () => {
    markPending(els, "iphone.indexPending");
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
