// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { formatDisplayTime } from "../core/format.js";
import { t, getLang, markI18nReady, setLang } from "../locales/i18n.js";
import { ensureDialog, setDialogLanguage, showAlert, showConfirm } from "../core/dialog.js";

const IMAGE_PAGE_SIZE = 300;

function getViewerElements() {
  return {
    viewerPage: $(".viewer-page"),
    backToGalleryButton: $("#backToGalleryButton"),
    toggleViewerSidebarButton: $("#toggleViewerSidebarButton"),
    statusMessage: $("#statusMessage"),
    viewerCanvas: $("#viewerCanvas"),
    viewerImage: $("#viewerImage"),
    viewerName: $("#viewerName"),
    viewerPath: $("#viewerPath"),
    viewerZoom: $("#viewerZoom"),
    viewerExifBox: $("#viewerExifBox"),
    viewerPrevButton: $("#viewerPrevButton"),
    viewerNextButton: $("#viewerNextButton"),
    viewerZoomOutButton: $("#viewerZoomOutButton"),
    viewerZoomResetButton: $("#viewerZoomResetButton"),
    viewerZoomInButton: $("#viewerZoomInButton"),
    viewerRotateLeftButton: $("#viewerRotateLeftButton"),
    viewerRotateRightButton: $("#viewerRotateRightButton"),
    viewerCopyButton: $("#viewerCopyButton"),
    viewerOpenEditorButton: $("#viewerOpenEditorButton"),
    viewerDeleteButton: $("#viewerDeleteButton"),
  };
}

function createViewerState() {
  return {
    items: [],
    filtered: [],
    config: null,
    lang: getLang(),
    selected: null,
    index: -1,
    zoom: 1,
    base: 1,
    rotation: 0,
    query: "",
    dateStart: "",
    dateEnd: "",
    hasMoreImages: false,
    nextImagesOffset: 0,
    imagesLoadToken: 0,
    isLoadingMoreImages: false,
    backgroundLoadHandle: 0,
    exifLoadToken: 0,
  };
}

function setStatus(els, message, isError = false) {
  if (!els.statusMessage) return;
  els.statusMessage.textContent = message;
  els.statusMessage.style.color = isError ? "var(--danger)" : "";
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

function updateSidebarToggleText(els) {
  if (!els.toggleViewerSidebarButton || !els.viewerPage) return;

  const isCollapsed = els.viewerPage.classList.contains("is-collapsed");
  const label = isCollapsed ? t("viewer.buttons.showSidebar") : t("viewer.buttons.toggleSidebar");
  els.toggleViewerSidebarButton.textContent = isCollapsed ? "<>" : "><";
  els.toggleViewerSidebarButton.setAttribute("aria-label", label);
  els.toggleViewerSidebarButton.title = label;
}

function updateZoomText(els, state) {
  if (!els.viewerZoom) return;

  setText(
    els.viewerZoom,
    state.index < 0
      ? "-"
      : `${t("viewer.display.zoom", Math.round(state.base * state.zoom * 100))} · ${state.rotation}° · ${t("viewer.display.index", state.index + 1, state.filtered.length)}`,
  );
}

function applyImageTransform(els, state) {
  els.viewerImage.style.transform = `scale(${state.zoom}) rotate(${state.rotation}deg)`;
}

function translateViewerPage(els, state) {
  state.lang = getLang();
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : state.lang;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });

  setDialogLanguage(state.lang);

  const rotateLeftLabel = t("viewer.buttons.rotateLeft");
  const rotateRightLabel = t("viewer.buttons.rotateRight");
  els.viewerRotateLeftButton.setAttribute("aria-label", rotateLeftLabel);
  els.viewerRotateLeftButton.title = rotateLeftLabel;
  els.viewerRotateRightButton.setAttribute("aria-label", rotateRightLabel);
  els.viewerRotateRightButton.title = rotateRightLabel;

  updateZoomText(els, state);
  updateSidebarToggleText(els);
  markI18nReady();
}

function fitImageToCanvas(els, state) {
  if (!els.viewerImage.naturalWidth || !els.viewerImage.naturalHeight) return;

  const canvasRect = els.viewerCanvas.getBoundingClientRect();
  const availableWidth = Math.max(canvasRect.width - 24, 80);
  const availableHeight = Math.max(canvasRect.height - 24, 80);

  const isSideways = Math.abs(state.rotation) % 180 === 90;
  const renderedWidth = isSideways ? els.viewerImage.naturalHeight : els.viewerImage.naturalWidth;
  const renderedHeight = isSideways ? els.viewerImage.naturalWidth : els.viewerImage.naturalHeight;

  state.base = Math.min(
    availableWidth / renderedWidth,
    availableHeight / renderedHeight,
    1,
  );

  els.viewerImage.style.width = `${Math.round(
    els.viewerImage.naturalWidth * state.base,
  )}px`;
  els.viewerImage.style.height = `${Math.round(
    els.viewerImage.naturalHeight * state.base,
  )}px`;
  applyImageTransform(els, state);

  updateZoomText(els, state);
}

function renderExif(els, exif) {
  const fields = [
    ["viewer.labels.exifDimensions", `${exif.width || "-"} × ${exif.height || "-"}`],
    ["viewer.labels.exifDatetime", formatDisplayTime(exif.datetime)],
    ["viewer.labels.exifCamera", exif.camera || "-"],
    ["viewer.labels.exifLens", exif.lens || "-"],
    ["viewer.labels.exifFocalLength", exif.focal_length || "-"],
    ["viewer.labels.exifAperture", exif.aperture || "-"],
    ["viewer.labels.exifShutter", exif.shutter || "-"],
    ["viewer.labels.exifIso", exif.iso || "-"],
    ["viewer.labels.exifGpsCoordinates", exif.gps_coordinates || "-"],
    ["viewer.labels.exifGpsAltitude", exif.gps_altitude || "-"],
  ].filter(([, value]) => value && value !== "-");

  if (!fields.length) {
    setText(els.viewerExifBox, t("viewer.exif.unavailable"));
    els.viewerExifBox.className = "muted";
    return;
  }

  els.viewerExifBox.innerHTML = fields
    .map(
      ([key, value]) =>
        `<div class="meta-row"><span class="meta-label">${escapeHtml(t(key))}</span><strong class="meta-value">${escapeHtml(value)}</strong></div>`,
    )
    .join("");

  els.viewerExifBox.className = "meta-grid";
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

async function loadExif(els, state) {
  const item = state.filtered[state.index];
  if (!item) return;
  const exifLoadToken = state.exifLoadToken + 1;
  state.exifLoadToken = exifLoadToken;

  setText(els.viewerExifBox, t("viewer.exif.loading"));
  els.viewerExifBox.className = "muted";

  const response = await fetch(
    `/api/exif?relative_path=${encodeURIComponent(item.relative_path)}`,
  );

  const data = await response.json().catch(() => ({}));
  if (exifLoadToken !== state.exifLoadToken) return;

  if (!response.ok) {
    setText(els.viewerExifBox, data.detail || t("viewer.exif.failed"));
    return;
  }

  renderExif(els, data.exif || {});
}

async function loadConfig(state) {
  const config = await fetchJson("/api/config");
  state.config = config;
  state.lang = config.language || "en";
  setLang(state.lang);
}

async function fetchImagesPage(offset) {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(IMAGE_PAGE_SIZE),
    include_exif: "false",
    async_scan: "true",
    refresh_scan: offset > 0 ? "true" : "false",
    include_total: "false",
  });

  return fetchJson(`/api/images?${params.toString()}`);
}

function applyViewerFilters(state) {
  state.filtered = state.items.filter((item) => {
    if (
      state.query &&
      !item.relative_path.toLowerCase().includes(state.query.toLowerCase())
    ) {
      return false;
    }

    if (state.dateStart || state.dateEnd) {
      return isImageWithinDateRange(item, state.dateStart, state.dateEnd);
    }

    return true;
  });
}

function mergeImageItems(state, items) {
  const knownPaths = new Set(state.items.map((item) => item.relative_path));
  for (const item of items || []) {
    if (!knownPaths.has(item.relative_path)) {
      state.items.push(item);
      knownPaths.add(item.relative_path);
    }
  }
}

function updateImagePaginationState(state, data) {
  state.hasMoreImages = Boolean(data.has_more);
  state.nextImagesOffset =
    data.has_more && data.next_offset !== null && data.next_offset !== undefined
      ? data.next_offset
      : null;
}

function scheduleBackgroundImageLoad(els, state) {
  if (state.backgroundLoadHandle) {
    window.clearTimeout(state.backgroundLoadHandle);
  }

  const loadToken = state.imagesLoadToken;
  state.backgroundLoadHandle = window.setTimeout(async () => {
    state.backgroundLoadHandle = 0;

    while (
      loadToken === state.imagesLoadToken &&
      state.hasMoreImages &&
      state.nextImagesOffset !== null &&
      !state.isLoadingMoreImages
    ) {
      state.isLoadingMoreImages = true;

      try {
        const data = await fetchImagesPage(state.nextImagesOffset);
        if (loadToken !== state.imagesLoadToken) return;

        mergeImageItems(state, data.items || []);
        updateImagePaginationState(state, data);
        applyViewerFilters(state);
        updateZoomText(els, state);
      } catch {
        return;
      } finally {
        state.isLoadingMoreImages = false;
      }

      await new Promise((resolve) => window.setTimeout(resolve, 0));
    }
  }, 0);
}

async function loadImages(els, state, targetPath = "") {
  state.items = [];
  state.filtered = [];
  state.hasMoreImages = false;
  state.nextImagesOffset = 0;
  state.imagesLoadToken += 1;
  const loadToken = state.imagesLoadToken;

  let fetchedAny = false;

  while (state.nextImagesOffset !== null || !fetchedAny) {
    const offset = fetchedAny && state.nextImagesOffset !== null ? state.nextImagesOffset : 0;
    const data = await fetchImagesPage(offset);
    if (loadToken !== state.imagesLoadToken) return;

    fetchedAny = true;
    mergeImageItems(state, data.items || []);
    updateImagePaginationState(state, data);
    applyViewerFilters(state);

    const foundTarget = targetPath
      ? state.filtered.some((item) => item.relative_path === targetPath)
      : state.filtered.length > 0;
    if (foundTarget || !state.hasMoreImages || state.nextImagesOffset === null) {
      break;
    }

    await new Promise((resolve) => window.requestAnimationFrame(resolve));
  }

  if (!state.filtered.length) {
    throw new Error("No images");
  }

  if (state.hasMoreImages) {
    scheduleBackgroundImageLoad(els, state);
  }
}

function parseDateInput(value, endOfDay = false) {
  const normalized = String(value || "").trim();
  if (!normalized) return null;

  const match = normalized.match(/^(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?$/);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = match[3] ? Number(match[3]) : null;
  if (!year || month < 1 || month > 12) return null;

  if (!day) {
    return endOfDay
      ? new Date(year, month, 0, 23, 59, 59, 999).getTime()
      : new Date(year, month - 1, 1).getTime();
  }

  const daysInMonth = new Date(year, month, 0).getDate();
  if (day < 1 || day > daysInMonth) return null;

  return endOfDay
    ? new Date(year, month - 1, day, 23, 59, 59, 999).getTime()
    : new Date(year, month - 1, day).getTime();
}

function isImageWithinDateRange(item, startValue, endValue) {
  if (!Number.isFinite(item?.timeline_ts)) return false;
  const itemTime = item.timeline_ts * 1000;

  let startTime = parseDateInput(startValue);
  let endTime = parseDateInput(endValue, true);

  if (startTime !== null && endTime !== null && startTime > endTime) {
    [startTime, endTime] = [parseDateInput(endValue), parseDateInput(startValue, true)];
  }

  if (startTime !== null && itemTime < startTime) return false;
  if (endTime !== null && itemTime > endTime) return false;

  return true;
}

async function openAt(els, state, index) {
  if (index < 0 || index >= state.filtered.length) return;

  state.index = index;
  state.selected = state.filtered[index].relative_path;
  state.zoom = 1;
  state.base = 1;
  state.rotation = 0;

  setText(els.viewerName, state.filtered[index].name);
  setText(els.viewerPath, state.filtered[index].relative_path);

  els.viewerImage.src =
    `/api/image?relative_path=${encodeURIComponent(state.filtered[index].relative_path)}`;

  updateZoomText(els, state);
  loadExif(els, state).catch(() => {
    setText(els.viewerExifBox, t("viewer.exif.failed"));
    els.viewerExifBox.className = "muted";
  });
}

function shiftImage(els, state, delta) {
  if (!state.filtered.length) return;

  openAt(
    els,
    state,
    (state.index + delta + state.filtered.length) % state.filtered.length,
  );
}

function goBack(state) {
  const params = new URLSearchParams();

  if (state.query) {
    params.set("q", state.query);
  }

  if (state.dateStart) {
    params.set("from", state.dateStart);
  }

  if (state.dateEnd) {
    params.set("to", state.dateEnd);
  }

  if (state.selected) {
    params.set("selected", state.selected);
  }

  window.location.href = `/index.html${params.toString() ? `?${params.toString()}` : ""}`;
}

async function copySelected(els, state) {
  const item = state.filtered[state.index];
  if (!item) return;

  const targetDir = state.config?.default_copy_target?.trim() || "";
  if (!targetDir) {
    const message = t("browser.copy.targetMissing");
    setStatus(els, message, true);
    await showAlert(message, {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  const confirmed = await showConfirm(
    t("browser.copy.confirmMessage", item.relative_path, targetDir),
    {
      title: t("browser.copy.confirmTitle"),
      confirmText: t("browser.copy.confirm"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) {
    return;
  }

  try {
    setStatus(els, t("viewer.action.copying", item.relative_path));

    const result = await postJson("/api/copy", {
      relative_path: item.relative_path,
      target_dir: targetDir,
    });

    const message = t("viewer.action.copied", result.copied_to);
    setStatus(els, message);
  } catch (error) {
    setStatus(els, error.message, true);
    await showAlert(error.message, {
      title: t("dialog.title.error"),
      confirmText: t("dialog.buttons.ok"),
    });
  }
}

async function deleteSelected(els, state) {
  const item = state.filtered[state.index];
  if (!item) return;

  const confirmed = await showConfirm(
    t("delete.confirm.message", item.relative_path),
    {
      title: t("delete.confirm.title"),
      confirmText: t("delete.confirm.confirm"),
      cancelText: t("dialog.buttons.cancel"),
    },
  );

  if (!confirmed) {
    return;
  }

  try {
    setStatus(els, t("viewer.action.deleting", item.relative_path));

    await postJson("/api/delete", {
      relative_path: item.relative_path,
    });

    const deletedPath = item.relative_path;

    await loadImages(els, state);

    if (!state.filtered.length) {
      goBack(state);
      return;
    }

    await openAt(els, state, Math.min(state.index, state.filtered.length - 1));
    setStatus(els, t("viewer.action.deleted", deletedPath));
  } catch (error) {
    setStatus(els, error.message, true);
  }
}

async function openSelectedInEditor(els, state) {
  const item = state.filtered[state.index];
  if (!item) return;

  try {
    setStatus(els, t("viewer.action.openingEditor", item.relative_path));

    const result = await postJson("/api/open-image-editor", {
      relative_path: item.relative_path,
    });

    setStatus(els, t("viewer.action.openedEditor", result.path));
  } catch (error) {
    setStatus(els, error.message, true);
    await showAlert(error.message, {
      title: t("dialog.title.error"),
      confirmText: t("dialog.buttons.ok"),
    });
  }
}

function zoomIn(els, state) {
  state.zoom = Math.min(5, Number((state.zoom + 0.2).toFixed(2)));
  applyImageTransform(els, state);
  updateZoomText(els, state);
}

function zoomOut(els, state) {
  state.zoom = Math.max(0.2, Number((state.zoom - 0.2).toFixed(2)));
  applyImageTransform(els, state);
  updateZoomText(els, state);
}

function resetZoom(els, state) {
  state.zoom = 1;
  fitImageToCanvas(els, state);
}

function rotateImage(els, state, delta) {
  state.rotation = (state.rotation + delta + 360) % 360;
  fitImageToCanvas(els, state);
}

function bindViewerEvents(els, state) {
  on(els.backToGalleryButton, "click", () => goBack(state));
  on(els.viewerPrevButton, "click", () => shiftImage(els, state, -1));
  on(els.viewerNextButton, "click", () => shiftImage(els, state, 1));
  on(els.viewerZoomInButton, "click", () => zoomIn(els, state));
  on(els.viewerZoomOutButton, "click", () => zoomOut(els, state));
  on(els.viewerZoomResetButton, "click", () => resetZoom(els, state));
  on(els.viewerRotateLeftButton, "click", () => rotateImage(els, state, -90));
  on(els.viewerRotateRightButton, "click", () => rotateImage(els, state, 90));

  on(els.viewerCopyButton, "click", () => {
    copySelected(els, state);
  });

  on(els.viewerOpenEditorButton, "click", () => {
    openSelectedInEditor(els, state);
  });

  on(els.viewerDeleteButton, "click", () => {
    deleteSelected(els, state);
  });

  on(els.toggleViewerSidebarButton, "click", () => {
    els.viewerPage.classList.toggle("is-collapsed");
    updateSidebarToggleText(els);
  });

  on(els.viewerImage, "load", () => {
    state.zoom = 1;
    fitImageToCanvas(els, state);
  });

  on(
    els.viewerImage,
    "wheel",
    (event) => {
      event.preventDefault();

      state.zoom = Math.min(
        5,
        Math.max(
          0.2,
          Number((state.zoom + (event.deltaY < 0 ? 0.1 : -0.1)).toFixed(2)),
        ),
      );

      applyImageTransform(els, state);
      updateZoomText(els, state);
    },
    { passive: false },
  );

  on(window, "resize", () => fitImageToCanvas(els, state));

  on(document, "keydown", (event) => {
    if (event.key === "Escape") {
      goBack(state);
    } else if (event.key === "ArrowLeft") {
      shiftImage(els, state, -1);
    } else if (event.key === "ArrowRight") {
      shiftImage(els, state, 1);
    } else if (event.key === "+" || event.key === "=") {
      zoomIn(els, state);
    } else if (event.key === "-") {
      zoomOut(els, state);
    } else if (event.key === "0") {
      resetZoom(els, state);
    } else if (event.key === "[") {
      rotateImage(els, state, -90);
    } else if (event.key === "]") {
      rotateImage(els, state, 90);
    }
  });
}

async function initializeViewerPage(els, state) {
  const params = new URLSearchParams(window.location.search);
  const path = params.get("path");

  state.query = params.get("q") || "";
  state.dateStart = params.get("from") || "";
  state.dateEnd = params.get("to") || "";

  await loadConfig(state);
  translateViewerPage(els, state);
  setStatus(els, t("browser.status.loadingImages"));
  await loadImages(els, state, path || "");

  const index = state.filtered.findIndex(
    (item) => item.relative_path === path,
  );

  await openAt(els, state, index >= 0 ? index : 0);
  setStatus(els, t("viewer.status.ready"));
}

function renderViewerInitialState(els) {
  setText(els.viewerZoom, "-");
  setText(els.viewerExifBox, t("viewer.exif.empty"));
}

export function initViewerPage() {
  const els = getViewerElements();

  if (!els.viewerPage) return;

  const requiredElements = [
    els.backToGalleryButton,
    els.toggleViewerSidebarButton,
    els.statusMessage,
    els.viewerCanvas,
    els.viewerImage,
    els.viewerName,
    els.viewerPath,
    els.viewerZoom,
    els.viewerExifBox,
    els.viewerPrevButton,
    els.viewerNextButton,
    els.viewerZoomOutButton,
    els.viewerZoomResetButton,
    els.viewerZoomInButton,
    els.viewerRotateLeftButton,
    els.viewerRotateRightButton,
    els.viewerCopyButton,
    els.viewerOpenEditorButton,
    els.viewerDeleteButton,
  ];

  if (requiredElements.some((element) => !element)) {
    console.error("Viewer page is missing required elements.");
    return;
  }

  const state = createViewerState();

  ensureDialog();
  renderViewerInitialState(els);
  bindViewerEvents(els, state);

  initializeViewerPage(els, state).catch((error) => {
    setStatus(els, error.message, true);
    markI18nReady();
  });

  return { els, state };
}
