// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { ensureDialog, setDialogLanguage, showConfirm } from "../core/dialog.js";
import { markI18nReady, t, translateStaticText } from "../locales/i18n.js";

const MOBILE_DEVICE_TYPE = "iphone";

const mobileImportState = {
  isDetecting: false,
  isIndexing: false,
  cancelRequested: false,
};

const INDEX_BATCH_SIZE = 5;

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
    backToGalleryLink: $("#backToGalleryLink"),
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

async function confirmLeaveWhileIndexing() {
  return showConfirm(
    t("mobileImport.confirmLeaveWhileIndexing"),
    {
      title: t("dialog.title.warning"),
      confirmText: t("mobileImport.leavePage"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );
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

function updateMobileImportControls(els) {
  const hasDevice = Boolean(getSelectedDeviceId(els));
  if (els.detectIphoneButton) {
    els.detectIphoneButton.disabled = mobileImportState.isDetecting || mobileImportState.isIndexing;
  }
  if (els.indexIphoneButton) {
    els.indexIphoneButton.disabled = !hasDevice || mobileImportState.isDetecting || mobileImportState.isIndexing;
  }
  if (els.cancelIphoneIndexButton) {
    els.cancelIphoneIndexButton.disabled = !mobileImportState.isIndexing || mobileImportState.cancelRequested;
  }
  if (els.iphoneDeviceSelect) {
    els.iphoneDeviceSelect.disabled = mobileImportState.isDetecting || mobileImportState.isIndexing;
  }
  if (els.iphoneCopyAllInput) {
    els.iphoneCopyAllInput.disabled = mobileImportState.isIndexing;
  }
  updateIndexLimitState(els);
}

function getIndexLimit(els) {
  const value = Number.parseInt(els.iphoneIndexLimitInput?.value || "1", 10);
  if (!Number.isFinite(value) || value < 1) return 1;
  return Math.min(value, 10000);
}

function appendBatchDetails(els, batchNumber, data) {
  appendLog(
    els,
    t(
      "mobileImport.batchSummary",
      batchNumber,
      data.indexed ?? 0,
      data.imported ?? 0,
      data.skipped_duplicate ?? 0,
      data.already_imported ?? 0,
    ),
  );

  (data.skipped_duplicate_items || []).forEach((item) => {
    appendLog(els, t("mobileImport.skippedItem", item.target || item.filename || "-", item.existing_local_path || "-"));
  });

  (data.imported_items || []).forEach((item) => {
    appendLog(els, t("mobileImport.importedItem", item.target || item.filename || "-", item.local_path || "-"));
  });

  (data.already_imported_items || []).forEach((item) => {
    appendLog(els, t("mobileImport.alreadyImportedItem", item.target || item.filename || "-", item.local_path || "-"));
  });
}

function updateIndexLimitState(els) {
  if (!els.iphoneIndexLimitInput) return;
  els.iphoneIndexLimitInput.disabled = mobileImportState.isIndexing || Boolean(els.iphoneCopyAllInput?.checked);
}

async function detectDevices(els) {
  if (mobileImportState.isDetecting || mobileImportState.isIndexing) return;
  mobileImportState.isDetecting = true;
  updateMobileImportControls(els);
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
  } finally {
    mobileImportState.isDetecting = false;
    updateMobileImportControls(els);
  }
}

async function buildDeviceIndex(els) {
  if (mobileImportState.isDetecting || mobileImportState.isIndexing) return;
  const deviceId = getSelectedDeviceId(els);
  if (!deviceId) {
    setStatus(els, t("mobileImport.noDeviceDetected"));
    appendLog(els, t("mobileImport.noDeviceDetected"));
    return;
  }

  mobileImportState.isIndexing = true;
  mobileImportState.cancelRequested = false;
  updateMobileImportControls(els);
  setStatus(els, t("mobileImport.indexing"));
  appendLog(els, t("mobileImport.indexing"));
  try {
    const copyAll = Boolean(els.iphoneCopyAllInput?.checked);
    const requestedLimit = getIndexLimit(els);
    const totals = {
      indexed: 0,
      imported: 0,
      skipped_duplicate: 0,
      already_imported: 0,
    };
    let batchNumber = 0;
    let lastData = null;

    while (mobileImportState.isIndexing && !mobileImportState.cancelRequested && (copyAll || totals.indexed < requestedLimit)) {
      const remaining = copyAll ? INDEX_BATCH_SIZE : requestedLimit - totals.indexed;
      const batchLimit = Math.min(INDEX_BATCH_SIZE, remaining);
      if (batchLimit < 1) break;

      batchNumber += 1;
      appendLog(els, t("mobileImport.batchStarting", batchNumber, batchLimit));
      const response = await fetch("/api/mobile/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_type: MOBILE_DEVICE_TYPE, device_id: deviceId, limit: batchLimit, copy_all: false }),
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      lastData = data;

      if (data.status === "failed") {
        throw new Error(data.message || t("mobileImport.indexFailed"));
      }

      if ((data.indexed ?? 0) < 1) {
        appendLog(els, t("mobileImport.noMorePhotos"));
        break;
      }

      totals.indexed += data.indexed ?? 0;
      totals.imported += data.imported ?? 0;
      totals.skipped_duplicate += data.skipped_duplicate ?? 0;
      totals.already_imported += data.already_imported ?? 0;
      appendBatchDetails(els, batchNumber, data);

      setText(els.iphoneDeviceName, data.device_name || deviceId);
      setText(els.iphoneAlbumCount, String(data.album_count ?? 0));
      setText(els.iphoneMediaCount, String(totals.indexed));
      setText(els.iphoneLastIndexedAt, data.indexed_at || "-");

      if (mobileImportState.cancelRequested) {
        appendLog(els, t("mobileImport.cancelledAfterBatch", batchNumber));
        break;
      }
    }

    const totalMessage = mobileImportState.cancelRequested
      ? t(
        "mobileImport.cancelledSummary",
        totals.indexed,
        totals.imported,
        totals.skipped_duplicate,
        totals.already_imported,
      )
      : t(
        "mobileImport.totalSummary",
        totals.indexed,
        totals.imported,
        totals.skipped_duplicate,
        totals.already_imported,
      );
    setStatus(els, totalMessage);
    appendLog(els, totalMessage);
    if (lastData) {
      setText(els.iphoneDeviceName, lastData.device_name || deviceId);
      setText(els.iphoneAlbumCount, String(lastData.album_count ?? 0));
      setText(els.iphoneLastIndexedAt, lastData.indexed_at || "-");
    }
  } catch (error) {
    setStatus(els, t("mobileImport.indexFailed"));
    appendLog(els, `${t("mobileImport.indexFailed")}: ${error.message || error}`);
  } finally {
    mobileImportState.isIndexing = false;
    mobileImportState.cancelRequested = false;
    updateMobileImportControls(els);
  }
}

function bindMobileImportEvents(els) {
  updateMobileImportControls(els);

  on(els.iphoneCopyAllInput, "change", () => {
    updateMobileImportControls(els);
  });

  on(els.iphoneDeviceSelect, "change", () => {
    updateMobileImportControls(els);
  });

  on(els.detectIphoneButton, "click", () => {
    detectDevices(els);
  });

  on(els.indexIphoneButton, "click", () => {
    buildDeviceIndex(els);
  });

  on(els.cancelIphoneIndexButton, "click", () => {
    if (els.cancelIphoneIndexButton?.disabled) return;
    mobileImportState.cancelRequested = true;
    updateMobileImportControls(els);
    setStatus(els, t("mobileImport.cancelRequested"));
    appendLog(els, t("mobileImport.cancelRequestedDetail"));
  });

  on(els.backToGalleryLink, "click", async (event) => {
    if (!mobileImportState.isIndexing) return;

    event.preventDefault();
    const confirmed = await confirmLeaveWhileIndexing();
    if (confirmed) {
      window.location.href = els.backToGalleryLink.href;
    }
  });
}

export function initMobileImportPage() {
  const els = getMobileImportElements();
  if (!els.mobileImportPage) return;

  translateStaticText();
  ensureDialog();
  setDialogLanguage();
  bindMobileImportEvents(els);
  setStatus(els, t("mobileImport.ready"));
  setText(els.iphoneLog, t("mobileImport.logEmpty"));
  setText(els.iphoneDeviceName, "-");
  setText(els.iphoneAlbumCount, "0");
  setText(els.iphoneMediaCount, "0");
  setText(els.iphoneLastIndexedAt, "-");
  updateMobileImportControls(els);
  markI18nReady();
}
