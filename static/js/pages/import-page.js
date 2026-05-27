// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { ensureDialog, setDialogLanguage } from "../core/dialog.js";
import { getLang, markI18nReady, t, translateStaticText } from "../locales/i18n.js";

function getImportElements() {
  return {
    importPage: $(".import-page"),
    address: $("#phoneSyncAddress"),
    syncTarget: $("#phoneSyncTarget"),
    qrBox: $(".phone-sync-qr"),
    qrPattern: $(".phone-sync-qr-pattern"),
    qrLabel: $(".phone-sync-qr strong"),
    refreshPairingButton: $("#refreshPairingButton"),
    pairingStatus: $("#pairingStatus"),
    connectionStatus: $("#connectionStatus"),
    statusLine: $("#phoneSyncStatusLine"),
    connectedDeviceName: $("#connectedDeviceName"),
    lastSeen: $("#phoneLastSeen"),
    destinationRoot: $("#phoneDestinationRoot"),
    liveStatus: $("#importLiveStatus"),
    summaryStatus: $("#importSummaryStatus"),
    processedCount: $("#importProcessedCount"),
    importedCount: $("#importImportedCount"),
    skippedCount: $("#importSkippedCount"),
    failedCount: $("#importFailedCount"),
    sidebarProcessedCount: $("#sidebarProcessedCount"),
    sidebarImportedCount: $("#sidebarImportedCount"),
    pairedDeviceCount: $("#pairedDeviceCount"),
    pairedDeviceList: $("#pairedDeviceList"),
    recentRuns: $("#importRecentRuns"),
    log: $("#importLog"),
  };
}

function createImportState() {
  return {
    currentLang: getLang(),
    activeRoot: "",
    isRunning: false,
    processed: 0,
    imported: 0,
    skipped: 0,
    failed: 0,
    pairingCodeReady: false,
    pollTimer: null,
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

function setStatus(els, value) {
  setText(els.liveStatus, value);
  setText(els.summaryStatus, value);
}

function setCounts(els, state) {
  setText(els.processedCount, String(state.processed));
  setText(els.importedCount, String(state.imported));
  setText(els.skippedCount, String(state.skipped));
  setText(els.failedCount, String(state.failed));
  setText(els.sidebarProcessedCount, String(state.processed));
  setText(els.sidebarImportedCount, String(state.imported));
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Asia/Tokyo",
    timeZoneName: "short",
  }).format(date);
}

function normalizeSummary(summary = {}) {
  const skippedDuplicate = Number(summary.skipped_duplicate || 0);
  const skippedDeleted = Number(summary.skipped_deleted_locally || 0);
  return {
    processed: Number(summary.processed || 0),
    imported: Number(summary.imported || 0),
    skipped: skippedDuplicate + skippedDeleted,
    skippedDuplicate,
    skippedDeleted,
    failed: Number(summary.failed || 0),
  };
}

function setIdlePhoneState(els, state) {
  setText(els.pairingStatus, t("importPhotos.notPaired"));
  setText(els.connectionStatus, t("importPhotos.waitingForPhone"));
  setText(els.statusLine, t("importPhotos.phoneSyncIdle"));
  setText(els.connectedDeviceName, "-");
  setText(els.lastSeen, "-");
  setText(els.destinationRoot, state.activeRoot || "-");
  setText(els.syncTarget, state.activeRoot || "-");
  setText(els.pairedDeviceCount, "0");
  setText(els.pairedDeviceList, t("importPhotos.noPairedDevices"));
  setText(els.recentRuns, t("importPhotos.recentRunsEmpty"));
  setStatus(els, t("tasks.idle"));
  setCounts(els, state);
  setText(els.log, t("importPhotos.logEmpty"));
}

async function loadConfig(els, state) {
  try {
    const config = await fetchJson("/api/config");
    state.activeRoot = config.active_root || "";
    setText(els.destinationRoot, state.activeRoot || "-");
    setText(els.syncTarget, state.activeRoot || "-");
  } catch (error) {
    setText(els.log, `${t("importPhotos.configLoadFailed")}: ${error.message || error}`);
  }
}

function renderPairingCode(els, state, data) {
  state.pairingCodeReady = true;
  setText(els.address, data.base_url || "-");
  setText(els.syncTarget, data.destination_root || "-");
  setText(els.destinationRoot, data.destination_root || "-");
  setText(els.pairingStatus, t("importPhotos.pairingReady"));
  setText(els.connectionStatus, t("importPhotos.waitingForPhone"));
  setText(els.statusLine, t("importPhotos.scanToPair"));

  if (data.qr_svg && els.qrBox) {
    els.qrPattern?.classList.add("is-hidden");
    els.qrPattern?.setAttribute("hidden", "");
    let qrSvg = els.qrBox.querySelector(".phone-sync-qr-svg");
    if (!qrSvg) {
      qrSvg = document.createElement("div");
      qrSvg.className = "phone-sync-qr-svg";
      els.qrBox.prepend(qrSvg);
    }
    qrSvg.innerHTML = data.qr_svg;
    setText(els.qrLabel, t("importPhotos.qrReady"));
  } else {
    els.qrPattern?.classList.remove("is-hidden");
    els.qrPattern?.removeAttribute("hidden");
    els.qrBox?.querySelector(".phone-sync-qr-svg")?.remove();
    setText(els.qrLabel, t("importPhotos.qrPayloadReady"));
  }

  setText(els.log, t("importPhotos.pairingReadyLog", data.base_url || "-", data.pairing_token_expires_at || "-"));
}

async function refreshPairingCode(els, state) {
  try {
    const data = await fetchJson("/api/mobile/sync/pairing-code");
    renderPairingCode(els, state, data);
  } catch (error) {
    setText(els.log, `${t("importPhotos.pairingLoadFailed")}: ${error.message || error}`);
  }
}

function renderDevices(els, devices) {
  if (!els.pairedDeviceList) return;
  els.pairedDeviceList.replaceChildren();
  if (!devices.length) {
    els.pairedDeviceList.classList.add("phone-sync-device-empty");
    els.pairedDeviceList.textContent = t("importPhotos.noPairedDevices");
    return;
  }

  els.pairedDeviceList.classList.remove("phone-sync-device-empty");
  devices.forEach((device) => {
    const item = document.createElement("div");
    item.className = "phone-sync-device-card";

    const title = document.createElement("strong");
    title.textContent = device.device_id || "-";

    const meta = document.createElement("span");
    meta.textContent = `${device.device_type || "phone"} · ${t(`importPhotos.status_${device.status || "idle"}`)}`;

    const seen = document.createElement("small");
    seen.textContent = t("importPhotos.deviceLastSeen", formatTime(device.last_seen_at));

    item.append(title, meta, seen);
    els.pairedDeviceList.appendChild(item);
  });
}

function renderStatusLog(els, data, counts, devices) {
  const events = Array.isArray(data.recent_events) ? data.recent_events : [];
  if (events.length) {
    setText(els.log, events.map((event) => String(event.message || event)).join("\n"));
    setText(els.recentRuns, events.slice(0, 5).map((event) => String(event.message || event)).join("\n"));
    return;
  }

  if (counts.processed > 0) {
    const line = t(
      "importPhotos.statusSummaryLine",
      counts.processed,
      counts.imported,
      counts.skippedDuplicate,
      counts.skippedDeleted,
      counts.failed
    );
    setText(els.log, line);
    setText(els.recentRuns, line);
    return;
  }

  if (devices.length) {
    const line = t("importPhotos.connectedDeviceLine", devices.length);
    setText(els.log, line);
    setText(els.recentRuns, line);
    return;
  }

  setText(els.log, t("importPhotos.logEmpty"));
  setText(els.recentRuns, t("importPhotos.recentRunsEmpty"));
}

function renderSyncStatus(els, state, data) {
  const devices = Array.isArray(data.connected_devices) ? data.connected_devices : [];
  const counts = normalizeSummary(data.summary || {});
  const latestDevice = devices[0] || null;
  state.processed = counts.processed;
  state.imported = counts.imported;
  state.skipped = counts.skipped;
  state.failed = counts.failed;
  state.isRunning = data.status === "syncing";
  state.activeRoot = data.destination_root || state.activeRoot;

  const pairedCount = Number(data.paired_devices || 0);
  setText(els.pairedDeviceCount, String(pairedCount));
  setText(els.connectionStatus, state.isRunning ? t("importPhotos.syncing") : t("importPhotos.waitingForPhone"));
  setText(
    els.pairingStatus,
    pairedCount > 0 ? t("importPhotos.paired") : state.pairingCodeReady ? t("importPhotos.pairingReady") : t("importPhotos.notPaired")
  );
  setText(els.statusLine, state.isRunning ? t("importPhotos.phoneSyncRunning") : t("importPhotos.phoneSyncIdle"));
  setText(els.connectedDeviceName, latestDevice?.device_id || "-");
  setText(els.lastSeen, formatTime(latestDevice?.last_seen_at));
  setText(els.destinationRoot, state.activeRoot || "-");
  setText(els.syncTarget, state.activeRoot || "-");
  setStatus(els, state.isRunning ? t("importPhotos.syncing") : t("tasks.idle"));
  setCounts(els, state);
  renderDevices(els, devices);
  renderStatusLog(els, data, counts, devices);
}

async function loadSyncStatus(els, state) {
  try {
    const data = await fetchJson("/api/mobile/sync/status");
    renderSyncStatus(els, state, data);
  } catch (error) {
    setText(els.log, `${t("importPhotos.statusLoadFailed")}: ${error.message || error}`);
  }
}

function bindEvents(els, state) {
  on(els.refreshPairingButton, "click", () => refreshPairingCode(els, state));
}

function applyImportTranslations(els, state) {
  document.documentElement.lang = state.currentLang === "zh" ? "zh-CN" : state.currentLang;
  translateStaticText();
  setDialogLanguage(state.currentLang);
  setIdlePhoneState(els, state);
  markI18nReady();
}

export function initImportPage() {
  const els = getImportElements();
  if (!els.importPage) return;

  const state = createImportState();
  ensureDialog();
  bindEvents(els, state);
  applyImportTranslations(els, state);
  loadConfig(els, state).then(() => {
    refreshPairingCode(els, state);
    loadSyncStatus(els, state);
  });
  state.pollTimer = window.setInterval(() => loadSyncStatus(els, state), 5000);
  window.addEventListener("beforeunload", () => {
    if (state.pollTimer) window.clearInterval(state.pollTimer);
  });
}
