// SPDX-License-Identifier: MIT

import { $, on, setText } from "../core/dom.js";
import { formatDisplayTime } from "../core/format.js";
import { t, getLang, markI18nReady, setLang } from "../locales/i18n.js";
import { ensureDialog, setDialogLanguage, showAlert, showConfirm } from "../core/dialog.js";

const VIRTUAL_GAP = 14;
const VIRTUAL_CARD_HEIGHT = 238;
const VIRTUAL_HEADER_HEIGHT = 38;
const VIRTUAL_OVERSCAN_ROWS = 2;
const LOAD_MORE_THRESHOLD_PAGES = 2;
const LOAD_MORE_RECHECK_DELAY_MS = 220;
const LOAD_MORE_EMPTY_RECHECK_DELAY_MS = 1600;
const IMAGE_PAGE_SIZE = 48;
const TIMELINE_GROUP_PAGE_SIZE = 300;
const THUMBNAIL_CONCURRENCY = 3;
const GALLERY_VIEW_STATE_KEY = "zerotrace.galleryViewState";
const GALLERY_SCROLL_SAVE_INTERVAL_MS = 250;
const TIMELINE_NEIGHBOR_LOAD_THRESHOLD_PX = 1200;

function getIndexElements() {
  return {
    galleryPage: $(".gallery-page"),
    toggleSidebarButton: $("#toggleSidebarButton"),
    galleryScroller: $("#galleryScroller"),
    gallery: $("#gallery"),
    galleryStickyHeader: $("#galleryStickyHeader"),
    galleryIndex: $("#galleryIndex"),
    statusMessage: $("#statusMessage"),
    imageRoot: $("#imageRoot"),
    imageCount: $("#imageCount"),
    imageCountUpdatedAt: $("#imageCountUpdatedAt"),
    searchInput: $("#searchInput"),
    dateFilterToggle: $("#dateFilterToggle"),
    dateFilterPanel: $("#dateFilterPanel"),
    dateStartInput: $("#dateStartInput"),
    dateEndInput: $("#dateEndInput"),
    clearDateFilterButton: $("#clearDateFilterButton"),
    duplicatesBox: $("#duplicatesBox"),
    similarityToolLink: document.querySelector("[data-i18n='browser.buttons.similarityTool']"),

    selectionCount: $("#selectionCount"),
    selectionDetail: $("#selectionDetail"),
    selectionCopyTarget: $("#selectionCopyTarget"),
    selectionDeleteMode: $("#selectionDeleteMode"),
    selectionHint: $("#selectionHint"),

    previewSelectedButton: $("#previewSelectedButton"),
    copySelectedButton: $("#copySelectedButton"),
    clearSelectionButton: $("#clearSelectionButton"),
    invertSelectionButton: $("#invertSelectionButton"),
    deleteSelectedButton: $("#deleteSelectedButton"),

    cardTemplate: $("#cardTemplate"),
  };
}

function createIndexState() {
  return {
    items: [],
    filtered: [],
    config: null,
    duplicates: null,
    lang: getLang(),
    selectedPaths: new Set(),
    lastSelectedPath: null,
    activeDuplicateGroupId: null,
    activeTimelineGroupKey: "",
    isTimelineGroupMode: false,
    imagesLoadToken: 0,
    isImageListLoading: false,
    isLoadingMoreImages: false,
    nextImagesOffset: 0,
    hasMoreImages: false,
    imageScanComplete: false,
    previewOnly: false,
    lastLoadMoreOffset: null,
    totalImageCount: null,
    totalImageCountUpdatedAt: "",
    timelineIndexUserScrollUntil: 0,
    refreshScanTimer: 0,
    backgroundScanTimer: 0,
    uiRefreshTimer: 0,
    loadMoreRecheckTimer: 0,
    hasPendingUiRefresh: false,
    pendingRestoreScrollTop: null,
    pendingSelectedPath: "",
    hasRestoredScroll: false,
    hasRestoredSelectedPath: false,
    lastScrollSaveAt: 0,
    timelineIndexEntries: [],
    loadedTimelineGroups: new Set(),
    loadingTimelineGroups: new Set(),
    timelineGroupNextOffsets: new Map(),
    virtual: {
      rows: [],
      groups: [],
      totalHeight: 0,
      columns: 1,
      activeIndexKey: "",
      activeTimelineButtonKey: "",
      renderFrame: 0,
      thumbnailQueue: [],
      activeThumbnailLoads: 0,
    },
  };
}

function setStatus(els, message, isError = false) {
  if (!els.statusMessage) return;
  els.statusMessage.textContent = message;
  els.statusMessage.style.color = isError ? "var(--danger)" : "";
}

function readGalleryViewState(root) {
  try {
    const saved = JSON.parse(sessionStorage.getItem(GALLERY_VIEW_STATE_KEY) || "{}");
    return saved?.root === root ? saved : null;
  } catch {
    return null;
  }
}

function saveGalleryViewState(els, state) {
  if (!els.galleryScroller || !state.config?.active_root) return;

  const timelineGroups = state.isTimelineGroupMode
    ? state.virtual.groups.filter((group) => state.loadedTimelineGroups.has(group.key))
    : [];
  const payload = {
    root: state.config.active_root,
    scrollTop: els.galleryScroller.scrollTop,
    query: els.searchInput?.value.trim() || "",
    dateStart: els.dateStartInput?.value || "",
    dateEnd: els.dateEndInput?.value || "",
    duplicateGroupId: state.activeDuplicateGroupId || "",
    timelineGroupKey: state.activeTimelineGroupKey || "",
    timelineMode: Boolean(state.isTimelineGroupMode),
    timelineStartGroupKey: timelineGroups[0]?.key || "",
    timelineEndGroupKey: timelineGroups[timelineGroups.length - 1]?.key || "",
    savedAt: Date.now(),
  };

  try {
    sessionStorage.setItem(GALLERY_VIEW_STATE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore private-mode or quota failures; navigation should continue normally.
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

async function postJson(url, payload) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function getSelectedItems(state) {
  if (!state.selectedPaths.size) return [];

  return state.items.filter((item) => state.selectedPaths.has(item.relative_path));
}

function getPrimarySelectedItem(state) {
  const selectedItems = getSelectedItems(state);
  if (!selectedItems.length) return null;

  return (
    selectedItems.find((item) => item.relative_path === state.lastSelectedPath) ||
    selectedItems[0]
  );
}

function imageExists(item) {
  return item?.exists !== false;
}

function isVideoItem(item) {
  const path = String(item?.relative_path || "").toLowerCase();
  return item?.media_type === "video" || /\.(mp4|webm|mov|m4v|avi|mkv)$/.test(path);
}

function pruneSelectionToFiltered(state) {
  const visiblePaths = new Set(state.filtered.map((item) => item.relative_path));

  for (const path of [...state.selectedPaths]) {
    if (!visiblePaths.has(path)) {
      state.selectedPaths.delete(path);
    }
  }

  if (state.lastSelectedPath && !state.selectedPaths.has(state.lastSelectedPath)) {
    state.lastSelectedPath = state.selectedPaths.values().next().value || null;
  }
}

function updateSelection(els, state) {
  const selectedItems = getSelectedItems(state);
  const deletableItems = selectedItems.filter(imageExists);
  const selectedImage = getPrimarySelectedItem(state);
  const selectedCount = selectedItems.length;
  const deletableCount = deletableItems.length;
  const hasSelection = selectedCount > 0;
  const copyTarget = state.config?.default_copy_target?.trim() || "";

  if (els.selectionCount) {
    setText(
      els.selectionCount,
      selectedCount > 1
        ? t("browser.selection.multipleTitle", selectedCount)
        : selectedCount === 1
          ? t("browser.selection.singleTitle")
          : t("browser.selection.noneTitle"),
    );
  }

  if (els.selectionDetail) {
    setText(
      els.selectionDetail,
      selectedCount > 1
        ? t("browser.selection.multipleDetail", selectedImage?.name || "", selectedCount)
        : hasSelection && selectedImage
          ? selectedImage.name
          : t("browser.selection.noneDetail"),
    );
  }

  if (els.selectionCopyTarget) {
    setPathText(els.selectionCopyTarget, copyTarget || t("browser.selection.defaultCopyTarget"));
  }

  if (els.selectionDeleteMode) {
    setText(
      els.selectionDeleteMode,
      t("browser.selection.recycleDeleteMode"),
    );
  }

  if (els.selectionHint) {
    setText(
      els.selectionHint,
      selectedCount > 1
        ? t("browser.selection.hintMultiple")
        : selectedCount === 1
          ? t("browser.selection.hintSingle")
          : t("browser.selection.hintEmpty"),
    );
  }

  els.galleryPage?.classList.toggle("has-selection", hasSelection);

  if (els.previewSelectedButton) {
    els.previewSelectedButton.disabled = !selectedImage || !imageExists(selectedImage);
  }

  if (els.copySelectedButton) {
    els.copySelectedButton.disabled = deletableCount === 0;
  }

  if (els.clearSelectionButton) {
    els.clearSelectionButton.disabled = !hasSelection;
  }

  if (els.deleteSelectedButton) {
    els.deleteSelectedButton.disabled = !hasSelection;
  }

  if (els.invertSelectionButton) {
    els.invertSelectionButton.disabled = !state.filtered.length;
  }

  if (els.similarityToolLink) {
    const params = new URLSearchParams();
    if (selectedImage?.relative_path && imageExists(selectedImage)) {
      params.set("path", selectedImage.relative_path);
    }
    els.similarityToolLink.href = `/similarity.html${params.toString() ? `?${params.toString()}` : ""}`;
  }

  document.querySelectorAll(".card").forEach((card) => {
    const isSelected = state.selectedPaths.has(card.dataset.path);
    card.classList.toggle("is-selected", isSelected);
    card.setAttribute("aria-selected", isSelected ? "true" : "false");
  });
}

function getActiveDuplicateGroup(state) {
  if (!state.duplicates?.available || !state.activeDuplicateGroupId) return null;

  return (
    state.duplicates.groups.find(
      (group) => group.group_id === state.activeDuplicateGroupId,
    ) || null
  );
}

function getAvailableDuplicateGroup(group) {
  if (!group) return null;

  const availableItems = group.items.filter((item) => item.exists);

  return {
    ...group,
    availableItems,
    availableCount: availableItems.length,
    isEmpty: availableItems.length === 0,
    previewPaths: availableItems.slice(0, 3).map((item) => item.path),
    keptPathAvailable: availableItems.some(
      (item) => item.path === group.kept_path,
    ),
  };
}

function setPathText(element, value) {
  if (!element) return;
  element.textContent = value || "";
}

function getImageTimestamp(item) {
  return Number.isFinite(item?.timeline_ts) ? item.timeline_ts : null;
}

function compareImagesByTime(left, right) {
  const safeLeft = getImageTimestamp(left) ?? 0;
  const safeRight = getImageTimestamp(right) ?? 0;

  if (safeLeft !== safeRight) return safeRight - safeLeft;
  return String(left.relative_path || "").localeCompare(String(right.relative_path || ""));
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
  const itemTimestamp = getImageTimestamp(item);
  if (itemTimestamp === null) return false;
  const itemTime = itemTimestamp * 1000;

  let startTime = parseDateInput(startValue);
  let endTime = parseDateInput(endValue, true);

  if (startTime !== null && endTime !== null && startTime > endTime) {
    [startTime, endTime] = [parseDateInput(endValue), parseDateInput(startValue, true)];
  }

  if (startTime !== null && itemTime < startTime) return false;
  if (endTime !== null && itemTime > endTime) return false;

  return true;
}

function hasDateFilter(els) {
  return Boolean(els.dateStartInput?.value || els.dateEndInput?.value);
}

function updateDateFilterToggle(els) {
  if (!els.dateFilterToggle) return;

  const isExpanded = !els.dateFilterPanel?.classList.contains("is-hidden");
  const isActive = hasDateFilter(els);
  const label = isActive
    ? t("browser.buttons.dateFilterActive")
    : t("browser.buttons.dateFilter");

  els.galleryPage?.classList.toggle("is-date-filter-open", isExpanded);
  els.dateFilterToggle.classList.toggle("is-active", isActive);
  els.dateFilterToggle.setAttribute("aria-expanded", isExpanded ? "true" : "false");
  els.dateFilterToggle.textContent = label;
}

function getTimelineMonthLabel(item) {
  const value = String(item?.timeline_time || "");
  const match = value.match(/^(\d{4})-(\d{2})/);
  return match ? `${match[1]}-${match[2]}` : "Unknown date";
}

function getTimelineGroupKey(item) {
  const label = getTimelineMonthLabel(item);
  return label === "Unknown date" ? "unknown" : label;
}

function getTimelineTickLabel(label) {
  if (label === "Unknown date") return "Unknown";

  return label.replace("-", "");
}

function findFirstVirtualRowIndex(rows, y) {
  let low = 0;
  let high = rows.length;

  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    const row = rows[mid];

    if (row.y + row.height < y) {
      low = mid + 1;
    } else {
      high = mid;
    }
  }

  return low;
}

function findActiveTimelineGroup(groups, y) {
  if (!groups.length) return null;

  let low = 0;
  let high = groups.length - 1;
  let active = groups[0];

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const group = groups[mid];

    if (group.y <= y) {
      active = group;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return active;
}

function getGalleryMinCardWidth(els) {
  return els.galleryScroller?.clientWidth <= 720 ? 150 : 170;
}

function getCssPixelValue(name, fallback) {
  const value = Number.parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue(name),
  );
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function getVirtualCardHeight() {
  return getCssPixelValue("--gallery-card-height", VIRTUAL_CARD_HEIGHT);
}

function getVirtualColumnCount(els) {
  const width = els.gallery?.clientWidth || els.galleryScroller?.clientWidth || 0;
  const minCardWidth = getGalleryMinCardWidth(els);

  return Math.max(1, Math.floor((width + VIRTUAL_GAP) / (minCardWidth + VIRTUAL_GAP)));
}

function getLoadMoreThreshold(els, state) {
  const pageRows = Math.ceil(IMAGE_PAGE_SIZE / Math.max(1, state.virtual.columns || getVirtualColumnCount(els)));
  const pageHeight = pageRows * (getVirtualCardHeight() + VIRTUAL_GAP);
  const viewportHeight = els.galleryScroller?.clientHeight || window.innerHeight;

  return Math.max(viewportHeight * 2, pageHeight * LOAD_MORE_THRESHOLD_PAGES);
}

function runThumbnailQueue(state) {
  while (
    state.virtual.activeThumbnailLoads < THUMBNAIL_CONCURRENCY &&
    state.virtual.thumbnailQueue.length
  ) {
    const thumb = state.virtual.thumbnailQueue.shift();
    if (!thumb?.isConnected || !thumb.dataset.src) continue;

    const src = thumb.dataset.src;
    state.virtual.activeThumbnailLoads += 1;
    thumb.src = src;
    thumb.removeAttribute("data-src");
    thumb.classList.add("is-loading");
  }
}

function finishThumbnailLoad(state) {
  state.virtual.activeThumbnailLoads = Math.max(0, state.virtual.activeThumbnailLoads - 1);
  runThumbnailQueue(state);
}

function loadLazyThumbnail(state, thumb) {
  const src = thumb.dataset.src;
  if (!src) return;

  if (!state.virtual.thumbnailQueue.includes(thumb)) {
    state.virtual.thumbnailQueue.push(thumb);
  }
  runThumbnailQueue(state);
}

function pruneThumbnailQueue(state) {
  state.virtual.thumbnailQueue = state.virtual.thumbnailQueue.filter((thumb) => thumb.isConnected);
}

function queueLazyThumbnail(els, state, thumb, src) {
  thumb.dataset.src = src;
  thumb.removeAttribute("src");
  thumb.loading = "eager";

  if ("fetchPriority" in thumb) {
    thumb.fetchPriority = "auto";
  }

  on(thumb, "load", () => {
    thumb.classList.remove("is-loading");
    thumb.classList.add("is-loaded");
    finishThumbnailLoad(state);
  });

  on(thumb, "error", () => {
    thumb.classList.remove("is-loading");
    thumb.classList.add("is-error");
    finishThumbnailLoad(state);
  });

  window.requestAnimationFrame(() => {
    loadLazyThumbnail(state, thumb);
  });
}

function createGalleryCard(els, state, item) {
  const node = els.cardTemplate.content.firstElementChild.cloneNode(true);
  const thumb = node.querySelector(".thumb");

  node.dataset.path = item.relative_path;
  node.classList.toggle("is-video", isVideoItem(item));
  node.classList.toggle("is-missing", !imageExists(item));
  node.classList.toggle("is-selected", state.selectedPaths.has(item.relative_path));
  node.setAttribute(
    "aria-selected",
    state.selectedPaths.has(item.relative_path) ? "true" : "false",
  );

  thumb.alt = item.name;
  if (imageExists(item)) {
    queueLazyThumbnail(
      els,
      state,
      thumb,
      `/api/thumbnail?relative_path=${encodeURIComponent(item.relative_path)}`,
    );
  } else {
    thumb.removeAttribute("src");
    thumb.classList.add("is-error");
  }
  node.querySelector(".file-name").textContent = item.name;
  node.querySelector(".file-path").textContent = item.relative_path;

  on(node, "click", (event) => {
    updateCardSelection(els, state, item.relative_path, event);
    updateSelection(els, state);
  });

  on(node, "dblclick", () => {
    if (imageExists(item)) {
      openViewer(els, state, item.relative_path);
    }
  });

  on(node, "keydown", (event) => {
    if (event.key === "Enter") {
      if (!imageExists(item)) return;
      openViewer(els, state, item.relative_path);
    }

    if (event.key === " ") {
      event.preventDefault();
      togglePathSelection(state, item.relative_path);
      updateSelection(els, state);
    }
  });

  return node;
}

function buildVirtualGalleryLayout(els, state) {
  const columns = getVirtualColumnCount(els);
  const cardHeight = getVirtualCardHeight();
  const rows = [];
  const groups = [];
  let y = 0;
  let currentKey = "";
  let currentItems = [];

  function flushGroup() {
    if (!currentItems.length) return;

    const firstItem = currentItems[0];
    const label = getTimelineMonthLabel(firstItem);
    const groupTop = y;

    groups.push({
      key: currentKey,
      label,
      year: label === "Unknown date" ? "Unknown" : label.slice(0, 4),
      month: label === "Unknown date" ? "" : label.slice(5, 7),
      indexLabel: getTimelineTickLabel(label),
      y: groupTop,
    });

    rows.push({
      type: "header",
      key: currentKey,
      label,
      y,
      height: VIRTUAL_HEADER_HEIGHT,
    });
    y += VIRTUAL_HEADER_HEIGHT;

    for (let index = 0; index < currentItems.length; index += columns) {
      rows.push({
        type: "items",
        key: currentKey,
        items: currentItems.slice(index, index + columns),
        y,
        height: cardHeight,
      });
      y += cardHeight + VIRTUAL_GAP;
    }

    currentItems = [];
  }

  for (const item of state.filtered) {
    const key = getTimelineGroupKey(item);

    if (key !== currentKey) {
      flushGroup();
      currentKey = key;
    }

    currentItems.push(item);
  }

  flushGroup();

  state.virtual.rows = rows;
  state.virtual.groups = groups;
  state.virtual.columns = columns;
  state.virtual.totalHeight = Math.max(0, y - VIRTUAL_GAP);
}

function getTimelineIndexEntries(state) {
  const hasFilter =
    Boolean(state.query) ||
    Boolean(state.dateStart) ||
    Boolean(state.dateEnd) ||
    Boolean(state.activeDuplicateGroupId);

  const groups = state.virtual.groups;
  const entries = [];
  const seen = new Set();
  const loadedGroupsByKey = new Map(groups.map((group) => [group.key, group]));

  if (!hasFilter && state.timelineIndexEntries.length) {
    for (const entry of state.timelineIndexEntries) {
      const groupKey = entry.key;
      const loadedGroup = loadedGroupsByKey.get(groupKey);
      const key = `group:${groupKey}`;

      seen.add(key);
      entries.push({
        key,
        label: entry.index_label || entry.label || groupKey,
        groupKey,
        y: loadedGroup ? loadedGroup.y : null,
      });
    }
  }

  for (const group of groups) {
    const label = group.indexLabel || group.month || group.year;
    const key = `group:${group.key}`;

    if (seen.has(key)) continue;
    seen.add(key);
    entries.push({ key, label, groupKey: group.key, y: group.y });
  }

  return entries;
}

function renderTimelineIndex(els, state) {
  if (!els.galleryIndex) return;

  const entries = getTimelineIndexEntries(state);
  els.galleryIndex.innerHTML = "";
  els.galleryIndex.classList.toggle("is-hidden", entries.length <= 1);

  if (entries.length <= 1) return;

  const fragment = document.createDocumentFragment();

  for (const entry of entries) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "gallery-index-button";
    button.textContent = entry.label;
    button.dataset.indexKey = entry.key;
    button.title = entry.label;
    button.setAttribute("aria-label", entry.label);
    button.classList.toggle("is-active", entry.key === state.virtual.activeTimelineButtonKey);

    on(button, "click", (event) => {
      event.preventDefault();
      state.timelineIndexUserScrollUntil = 0;

      if (state.virtual.renderFrame) {
        window.cancelAnimationFrame(state.virtual.renderFrame);
        state.virtual.renderFrame = 0;
      }

      if (entry.y === null && entry.groupKey) {
        state.activeTimelineGroupKey = entry.groupKey;
        loadTimelineGroup(els, state, entry.groupKey).catch((error) => {
          setStatus(els, error.message, true);
        });
        return;
      }

      if (!els.galleryScroller || entry.y === null) return;
      state.activeTimelineGroupKey = entry.groupKey || "";
      els.galleryScroller.scrollTo({ top: entry.y, behavior: "smooth" });
      updateStickyHeader(els, state);
    });

    fragment.appendChild(button);
  }

  els.galleryIndex.appendChild(fragment);
}

function markTimelineIndexUserScroll(state) {
  state.timelineIndexUserScrollUntil = Date.now() + 1200;
}

function centerTimelineIndexOnActive(els, state, activeGroupKey) {
  if (!els.galleryIndex || !activeGroupKey) return;
  if (Date.now() < state.timelineIndexUserScrollUntil) return;

  const activeButton = [...els.galleryIndex.querySelectorAll(".gallery-index-button")]
    .find((button) => button.dataset.indexKey === activeGroupKey);
  if (!activeButton) return;

  const targetTop =
    activeButton.offsetTop -
    (els.galleryIndex.clientHeight - activeButton.offsetHeight) / 2;

  els.galleryIndex.scrollTop = Math.max(0, targetTop);
}

function updateStickyHeader(els, state) {
  if (!els.galleryStickyHeader || !els.galleryScroller) return;

  const scrollTop = els.galleryScroller.scrollTop;
  const activeGroup = findActiveTimelineGroup(
    state.virtual.groups,
    scrollTop + VIRTUAL_HEADER_HEIGHT,
  );

  els.galleryStickyHeader.classList.toggle("is-hidden", !activeGroup);
  const activeLabel = activeGroup?.label || "";
  if (els.galleryStickyHeader.textContent !== activeLabel) {
    els.galleryStickyHeader.textContent = activeLabel;
  }
  state.virtual.activeIndexKey = activeGroup?.key || "";
  state.activeTimelineGroupKey = activeGroup?.key || "";

  if (!els.galleryIndex) return;

  const activeGroupKey = activeGroup ? `group:${activeGroup.key}` : "";

  if (state.virtual.activeTimelineButtonKey !== activeGroupKey) {
    const previousButton = state.virtual.activeTimelineButtonKey
      ? els.galleryIndex.querySelector(
          `.gallery-index-button[data-index-key="${CSS.escape(state.virtual.activeTimelineButtonKey)}"]`,
        )
      : null;
    const activeButton = activeGroupKey
      ? els.galleryIndex.querySelector(
          `.gallery-index-button[data-index-key="${CSS.escape(activeGroupKey)}"]`,
        )
      : null;

    previousButton?.classList.remove("is-active");
    activeButton?.classList.add("is-active");
    state.virtual.activeTimelineButtonKey = activeGroupKey;
    centerTimelineIndexOnActive(els, state, activeGroupKey);
  }
}

function renderVirtualGalleryViewport(els, state) {
  pruneThumbnailQueue(state);
  els.gallery.innerHTML = "";

  if (!state.filtered.length) {
    const activeGroup = getAvailableDuplicateGroup(getActiveDuplicateGroup(state));
    const emptyMessage = activeGroup
      ? t("browser.duplicates.noMatchInGroup")
      : t("browser.status.noMatch");

    els.gallery.style.height = "";
    els.gallery.classList.add("is-empty");
    els.gallery.innerHTML = `<div class="panel muted">${emptyMessage}</div>`;
    els.galleryStickyHeader?.classList.add("is-hidden");
    els.galleryIndex?.classList.add("is-hidden");
    return;
  }

  els.gallery.classList.remove("is-empty");
  els.gallery.style.height = `${state.virtual.totalHeight}px`;

  const scrollTop = els.galleryScroller?.scrollTop || 0;
  const viewportHeight = els.galleryScroller?.clientHeight || window.innerHeight;
  const start = Math.max(0, scrollTop - (VIRTUAL_CARD_HEIGHT + VIRTUAL_GAP) * VIRTUAL_OVERSCAN_ROWS);
  const end = scrollTop + viewportHeight + (VIRTUAL_CARD_HEIGHT + VIRTUAL_GAP) * VIRTUAL_OVERSCAN_ROWS;
  const fragment = document.createDocumentFragment();
  const startIndex = findFirstVirtualRowIndex(state.virtual.rows, start);

  for (let index = startIndex; index < state.virtual.rows.length; index += 1) {
    const row = state.virtual.rows[index];
    if (row.y > end) break;

    if (row.type === "header") {
      const header = document.createElement("div");
      header.className = "gallery-section-heading";
      header.textContent = row.label;
      header.style.transform = `translateY(${row.y}px)`;
      fragment.appendChild(header);
      continue;
    }

    const rowNode = document.createElement("div");
    rowNode.className = "gallery-virtual-row";
    rowNode.style.setProperty("--virtual-columns", String(state.virtual.columns));
    rowNode.style.transform = `translateY(${row.y}px)`;

    for (const item of row.items) {
      rowNode.appendChild(createGalleryCard(els, state, item));
    }

    fragment.appendChild(rowNode);
  }

  els.gallery.appendChild(fragment);
  updateStickyHeader(els, state);
}

function renderGallery(els, state) {
  if (!els.galleryScroller || !els.gallery) return;

  buildVirtualGalleryLayout(els, state);
  renderTimelineIndex(els, state);
  renderVirtualGalleryViewport(els, state);
}

function scheduleVirtualGalleryRender(els, state) {
  if (state.virtual.renderFrame) return;

  state.virtual.renderFrame = window.requestAnimationFrame(() => {
    state.virtual.renderFrame = 0;
    renderVirtualGalleryViewport(els, state);
  });
}

function rebuildVirtualGallery(els, state) {
  if (!state.filtered.length) {
    renderGallery(els, state);
    return;
  }

  const previousTop = els.galleryScroller?.scrollTop || 0;
  buildVirtualGalleryLayout(els, state);
  renderTimelineIndex(els, state);
  renderVirtualGalleryViewport(els, state);

  if (els.galleryScroller) {
    els.galleryScroller.scrollTop = Math.min(previousTop, state.virtual.totalHeight);
  }
}

function scrollToGalleryPath(els, state, path) {
  if (!els.galleryScroller || !path) return;

  const row = state.virtual.rows.find(
    (candidate) =>
      candidate.type === "items" &&
      candidate.items.some((item) => item.relative_path === path),
  );

  if (row) {
    els.galleryScroller.scrollTo({ top: Math.max(0, row.y - VIRTUAL_HEADER_HEIGHT), behavior: "auto" });
    renderVirtualGalleryViewport(els, state);
  }
}

function restorePendingSelectedPath(els, state) {
  if (!state.pendingSelectedPath || state.hasRestoredSelectedPath) return false;
  if (!state.filtered.some((item) => item.relative_path === state.pendingSelectedPath)) return false;

  state.selectedPaths.add(state.pendingSelectedPath);
  state.lastSelectedPath = state.pendingSelectedPath;
  scrollToGalleryPath(els, state, state.pendingSelectedPath);
  updateSelection(els, state);
  state.hasRestoredSelectedPath = true;
  state.pendingSelectedPath = "";
  return true;
}

function renderDuplicates(els, state) {
  const payload = state.duplicates;

  if (!payload?.available) {
    els.duplicatesBox.className = "muted";
    els.duplicatesBox.textContent = t("browser.duplicates.empty");
    return;
  }

  const parts = [];
  const methodCounts = payload.method_counts || {};
  const hasMethodCounts =
    Object.prototype.hasOwnProperty.call(methodCounts, "strict") ||
    Object.prototype.hasOwnProperty.call(methodCounts, "phash");

  if (hasMethodCounts) {
    parts.push(
      `<div class="duplicates-meta">${t(
        "browser.duplicates.methodCounts",
        Number(methodCounts.strict || 0),
        Number(methodCounts.phash || 0),
      )}</div>`,
    );
  } else if (payload.group_count > 0) {
    parts.push(
      `<div class="duplicates-meta">${t("browser.duplicates.count", payload.group_count)}</div>`,
    );
  }

  if (payload.generated_at) {
    parts.push(
      `<div class="duplicates-meta">${t("browser.duplicates.generatedAt", formatDisplayTime(payload.generated_at))}</div>`,
    );
  }

  parts.push(
    `<div class="duplicates-meta">${t("browser.duplicates.summaryReady")}</div>`,
  );

  parts.push(`
    <div class="duplicates-toolbar">
      <a href="/duplicates.html" class="button-link subtle-link duplicates-results-button">
        ${t("browser.buttons.openDuplicatesResults")}
      </a>
    </div>
  `);

  els.duplicatesBox.className = "";
  els.duplicatesBox.innerHTML = parts.join("");
}

function applyFilter(els, state, options = {}) {
  const { resetScroll = true } = options;
  const query = els.searchInput.value.trim().toLowerCase();
  const startDate = els.dateStartInput?.value || "";
  const endDate = els.dateEndInput?.value || "";
  const activeGroup = getAvailableDuplicateGroup(getActiveDuplicateGroup(state));
  let items = [...state.items];

  if (activeGroup) {
    const allowed = new Set(activeGroup.availableItems.map((item) => item.path));
    items = items.filter((item) => allowed.has(item.relative_path));
  }

  if (query) {
    items = items.filter((item) =>
      item.relative_path.toLowerCase().includes(query),
    );
  }

  if (startDate || endDate) {
    items = items.filter((item) =>
      isImageWithinDateRange(item, startDate, endDate),
    );
  }

  state.query = query;
  state.dateStart = startDate;
  state.dateEnd = endDate;
  state.filtered = items.sort(compareImagesByTime);
  if (!state.isImageListLoading) {
    pruneSelectionToFiltered(state);
  }

  if (resetScroll && els.galleryScroller) {
    els.galleryScroller.scrollTop = 0;
  }

  const hasFilter = Boolean(query || startDate || endDate || state.activeDuplicateGroupId);
  const displayCount =
    !hasFilter && Number.isInteger(state.totalImageCount)
      ? String(state.totalImageCount)
      : state.hasMoreImages
        ? `${state.filtered.length}+`
        : String(state.filtered.length);
  setText(
    els.imageCount,
    displayCount,
  );
  setText(
    els.imageCountUpdatedAt,
    !hasFilter && state.totalImageCountUpdatedAt
      ? t("browser.labels.imageCountUpdatedAt", formatDisplayTime(state.totalImageCountUpdatedAt))
      : "-",
  );
  renderGallery(els, state);
  updateSelection(els, state);
  renderDuplicates(els, state);
  updateDateFilterToggle(els);
}

function openViewer(els, state, path) {
  saveGalleryViewState(els, state);

  const params = new URLSearchParams();

  params.set("path", path);
  if (state.isTimelineGroupMode) {
    const groupKey = getTimelineGroupKey({ timeline_time: path.replace(/[\\/]/g, "-") });
    if (groupKey !== "unknown") {
      params.set("timeline_group", groupKey);
    }
    const timelineGroups = state.virtual.groups.filter((group) =>
      state.loadedTimelineGroups.has(group.key),
    );
    if (timelineGroups.length) {
      params.set("timeline_start", timelineGroups[0].key);
      params.set("timeline_end", timelineGroups[timelineGroups.length - 1].key);
    }
  }

  if (els.searchInput.value.trim()) {
    params.set("q", els.searchInput.value.trim());
  }

  if (els.dateStartInput?.value) {
    params.set("from", els.dateStartInput.value);
  }

  if (els.dateEndInput?.value) {
    params.set("to", els.dateEndInput.value);
  }

  if (state.activeDuplicateGroupId) {
    params.set("dup_group", state.activeDuplicateGroupId);
  }

  window.location.href = `/viewer.html?${params.toString()}`;
}

function updateSidebarToggleText(els) {
  if (!els.toggleSidebarButton || !els.galleryPage) return;

  const isCollapsed = els.galleryPage.classList.contains("is-collapsed");
  const label = isCollapsed ? t("browser.buttons.showSidebar") : t("browser.buttons.toggleSidebar");
  els.toggleSidebarButton.textContent = isCollapsed ? "<>" : "><";
  els.toggleSidebarButton.setAttribute("aria-label", label);
  els.toggleSidebarButton.title = label;
}

function translatePage(els, state) {
  state.lang = getLang();
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : state.lang;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });

  setDialogLanguage(state.lang);

  if (els.searchInput) {
    els.searchInput.placeholder = t("browser.placeholders.search");
  }

  if (els.dateStartInput) {
    els.dateStartInput.placeholder = t("browser.placeholders.date");
  }

  if (els.dateEndInput) {
    els.dateEndInput.placeholder = t("browser.placeholders.date");
  }

  updateSelection(els, state);

  renderDuplicates(els, state);
  updateDateFilterToggle(els);
  updateSidebarToggleText(els);
  markI18nReady();
}

async function loadConfig(els, state) {
  state.config = await fetchJson("/api/config");
  state.lang = state.config.language || "en";
  state.duplicates = state.config.duplicate_results || null;
  state.totalImageCount = Number.isInteger(state.config.root_summary?.image_count)
    ? state.config.root_summary.image_count
    : null;
  state.totalImageCountUpdatedAt = state.config.root_summary?.updated_at || "";

  setLang(state.lang);

  setText(els.imageRoot, state.config.active_root);
}

async function loadDuplicates(state) {
  state.duplicates = await fetchJson("/api/duplicates");

  if (
    state.activeDuplicateGroupId &&
    !state.duplicates.groups.some(
      (group) => group.group_id === state.activeDuplicateGroupId,
    )
  ) {
    state.activeDuplicateGroupId = null;
  }
}

async function loadTimelineIndex(state) {
  try {
    const payload = await fetchJson("/api/timeline-index");
    state.timelineIndexEntries = Array.isArray(payload.entries) ? payload.entries : [];
  } catch {
    state.timelineIndexEntries = [];
  }
}

function loadDeferredIndexData(els, state) {
  loadTimelineIndex(state)
    .then(() => {
      renderTimelineIndex(els, state);
    })
    .catch(() => {
      state.timelineIndexEntries = [];
      renderTimelineIndex(els, state);
    });

  if (!state.activeDuplicateGroupId) return;

  loadDuplicates(state)
    .then(() => {
      applyFilter(els, state, { resetScroll: false });
    })
    .catch(() => {
      state.duplicates = state.config?.duplicate_results || null;
      renderDuplicates(els, state);
    });
}

async function fetchImagesPage(offset, options = {}) {
  const { refreshScan = offset > 0, includeTotal = offset === 0 } = options;
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(IMAGE_PAGE_SIZE),
    include_exif: "false",
    async_scan: "true",
    refresh_scan: refreshScan ? "true" : "false",
    include_total: includeTotal ? "true" : "false",
  });

  return fetchJson(`/api/images?${params.toString()}`);
}

function clearLoadMoreRecheck(state) {
  if (!state.loadMoreRecheckTimer) return;

  window.clearTimeout(state.loadMoreRecheckTimer);
  state.loadMoreRecheckTimer = 0;
}

function scheduleLoadMoreRecheck(els, state, delay = LOAD_MORE_RECHECK_DELAY_MS) {
  if (!state.hasMoreImages || state.nextImagesOffset === null) return;
  if (state.loadMoreRecheckTimer) return;

  state.loadMoreRecheckTimer = window.setTimeout(() => {
    state.loadMoreRecheckTimer = 0;
    maybeLoadMoreImages(els, state);
  }, delay);
}

function clearImageRefreshTimers(state) {
  if (state.backgroundScanTimer) {
    window.clearTimeout(state.backgroundScanTimer);
    state.backgroundScanTimer = 0;
  }

  if (state.uiRefreshTimer) {
    window.clearTimeout(state.uiRefreshTimer);
    state.uiRefreshTimer = 0;
  }

  clearLoadMoreRecheck(state);
  state.hasPendingUiRefresh = false;
}

async function fetchImagesByTimelineGroup(groupKey, offset = 0) {
  const params = new URLSearchParams({
    group_key: groupKey,
    offset: String(offset),
    limit: String(TIMELINE_GROUP_PAGE_SIZE),
  });
  return fetchJson(`/api/images/timeline-group?${params.toString()}`);
}

async function fetchTimelineNeighborGroup(groupKey, direction) {
  const params = new URLSearchParams({
    group_key: groupKey,
    direction,
  });
  return fetchJson(`/api/images/timeline-neighbor?${params.toString()}`);
}

function mergeImageItems(state, items) {
  const knownPaths = new Set(state.items.map((item) => item.relative_path));
  for (const item of items) {
    if (!knownPaths.has(item.relative_path)) {
      state.items.push(item);
      knownPaths.add(item.relative_path);
    }
  }
}

function updateImagePaginationState(state, data) {
  state.hasMoreImages = Boolean(data.has_more);
  state.imageScanComplete = Boolean(data.scan_complete);
  state.previewOnly = Boolean(data.preview_only);
  state.totalImageCount = Number.isInteger(data.total) ? data.total : state.totalImageCount;
  state.totalImageCountUpdatedAt =
    typeof data.total_generated_at === "string" && data.total_generated_at
      ? data.total_generated_at
      : state.totalImageCountUpdatedAt;
  state.nextImagesOffset =
    data.has_more && data.next_offset !== null && data.next_offset !== undefined
      ? data.next_offset
      : null;
  if (!state.hasMoreImages) {
    state.lastLoadMoreOffset = null;
    clearLoadMoreRecheck(state);
  }
}

function updateTimelineGroupPaginationState(state, groupKey, data) {
  if (data.has_more && data.next_offset !== null && data.next_offset !== undefined) {
    state.timelineGroupNextOffsets.set(groupKey, data.next_offset);
  } else {
    state.timelineGroupNextOffsets.delete(groupKey);
    state.loadedTimelineGroups.add(groupKey);
  }
}

async function loadTimelineGroupPage(els, state, groupKey, offset = 0, options = {}) {
  const { refreshUi = true } = options;
  if (!groupKey) return null;
  const loadKey = `${groupKey}:${offset}`;
  if (state.loadingTimelineGroups.has(loadKey)) return null;

  state.loadingTimelineGroups.add(loadKey);
  try {
    const data = await fetchImagesByTimelineGroup(groupKey, offset);
    mergeImageItems(state, data.items || []);
    updateTimelineGroupPaginationState(state, groupKey, data);
    if (refreshUi) {
      applyFilter(els, state, { resetScroll: false });
    }
    return data;
  } finally {
    state.loadingTimelineGroups.delete(loadKey);
  }
}

async function preloadTimelineNeighborGroup(els, state, groupKey, direction = "next", chainDepth = 0) {
  if (!groupKey) return;
  let neighborKey = "";
  const anchorGroup = state.virtual.groups.find((group) => group.key === groupKey);
  const anchorOffset =
    els.galleryScroller && anchorGroup
      ? Math.max(0, els.galleryScroller.scrollTop - anchorGroup.y)
      : 0;

  try {
    const neighbor = await fetchTimelineNeighborGroup(groupKey, direction);
    neighborKey = neighbor.neighbor_group_key;
    if (!neighborKey) return;
    if (state.loadedTimelineGroups.has(neighborKey) || state.loadingTimelineGroups.has(neighborKey)) return;

    state.loadingTimelineGroups.add(neighborKey);
    const data = await fetchImagesByTimelineGroup(neighborKey);
    mergeImageItems(state, data.items || []);
    state.loadedTimelineGroups.add(neighborKey);
    applyFilter(els, state, { resetScroll: false });
    if (direction === "prev" && els.galleryScroller) {
      const restoredGroup = state.virtual.groups.find((group) => group.key === groupKey);
      if (restoredGroup) {
        els.galleryScroller.scrollTop = Math.max(0, restoredGroup.y + anchorOffset);
        renderVirtualGalleryViewport(els, state);
        updateStickyHeader(els, state);
      }
    }
  } catch {
    // Neighbor preload is opportunistic; the current timeline view stays usable.
  } finally {
    if (neighborKey) {
      state.loadingTimelineGroups.delete(neighborKey);
    }
  }
}

function maybeLoadTimelineNeighbors(els, state) {
  if (!state.isTimelineGroupMode) return;
  if (!els.galleryScroller || state.virtual.groups.length < 1) return;
  if (state.loadedTimelineGroups.size < 1) return;
  if (state.isImageListLoading || state.isLoadingMoreImages) return;

  const scrollTop = els.galleryScroller.scrollTop;
  const loadedGroups = state.virtual.groups.filter((group) =>
    state.loadedTimelineGroups.has(group.key),
  );
  const firstGroup = loadedGroups[0];

  if (
    firstGroup &&
    state.loadedTimelineGroups.has(firstGroup.key) &&
    scrollTop - firstGroup.y < TIMELINE_NEIGHBOR_LOAD_THRESHOLD_PX
  ) {
    preloadTimelineNeighborGroup(els, state, firstGroup.key, "prev", 0);
  }
}

async function loadTimelineGroup(els, state, groupKey) {
  if (!groupKey) return;

  setStatus(els, t("browser.status.loadingImages"));
  state.activeTimelineGroupKey = groupKey;
  state.isTimelineGroupMode = true;
  state.loadingTimelineGroups.add(groupKey);
  state.isImageListLoading = true;
  state.isLoadingMoreImages = false;
  state.lastLoadMoreOffset = null;
  state.hasMoreImages = false;
  state.nextImagesOffset = null;
  clearImageRefreshTimers(state);
  state.items = [];
  state.filtered = [];
  state.loadedTimelineGroups.clear();
  state.loadingTimelineGroups.clear();
  state.timelineGroupNextOffsets.clear();

  try {
    await loadTimelineGroupPage(els, state, groupKey, 0);
    state.isImageListLoading = false;
    setStatus(els, t("browser.status.loadedImages", state.filtered.length));

    if (els.galleryScroller) {
      els.galleryScroller.scrollTo({ top: 0, behavior: "auto" });
      renderVirtualGalleryViewport(els, state);
      updateStickyHeader(els, state);
    }
  } finally {
    state.loadingTimelineGroups.delete(groupKey);
    state.isImageListLoading = false;
  }
}

async function loadImages(els, state) {
  setStatus(els, t("browser.status.loadingImages"));

  const loadToken = state.imagesLoadToken + 1;
  state.imagesLoadToken = loadToken;
  state.isTimelineGroupMode = false;
  state.isImageListLoading = true;
  state.isLoadingMoreImages = false;
  state.nextImagesOffset = 0;
  state.hasMoreImages = false;
  state.imageScanComplete = false;
  state.previewOnly = false;
  state.lastLoadMoreOffset = null;
  clearImageRefreshTimers(state);
  state.items = [];
  state.totalImageCount = Number.isInteger(state.config?.root_summary?.image_count)
    ? state.config.root_summary.image_count
    : null;
  state.totalImageCountUpdatedAt = state.config?.root_summary?.updated_at || "";

  const data = await fetchImagesPage(0, { refreshScan: false, includeTotal: false });
  if (loadToken !== state.imagesLoadToken) return;

  mergeImageItems(state, data.items || []);
  updateImagePaginationState(state, data);
  setText(els.imageRoot, data.root || state.config.active_root);

  const availablePaths = new Set(state.items.map((item) => item.relative_path));
  for (const path of [...state.selectedPaths]) {
    if (!availablePaths.has(path)) {
      state.selectedPaths.delete(path);
    }
  }

  if (state.lastSelectedPath && !state.selectedPaths.has(state.lastSelectedPath)) {
    state.lastSelectedPath = state.selectedPaths.values().next().value || null;
  }

  state.isImageListLoading = false;
  applyFilter(els, state);
  restorePendingSelectedPath(els, state);

  setStatus(
    els,
    state.config.active_root_exists
      ? state.hasMoreImages
        ? t("browser.status.loadedImagesProgress", state.items.length, "?")
        : t("browser.status.loadedImages", state.items.length)
      : t("browser.status.rootMissing"),
  );

  if (!state.items.length && state.hasMoreImages) {
    window.setTimeout(() => loadMoreImages(els, state), 250);
  }
  if (state.hasMoreImages) {
    window.setTimeout(() => maybeLoadMoreImages(els, state), 0);
  }

  scheduleBackgroundImageRefresh(els, state);
}

function refreshGalleryFromBackground(els, state) {
  state.hasPendingUiRefresh = false;
  applyFilter(els, state, { resetScroll: false });
  restorePendingSelectedPath(els, state);
  updateStickyHeader(els, state);
  setStatus(
    els,
    state.hasMoreImages
      ? t("browser.status.loadedImagesProgress", state.items.length, "?")
      : t("browser.status.loadedImages", state.items.length),
  );
}

function scheduleUiRefresh(els, state, immediate = false) {
  state.hasPendingUiRefresh = true;

  if (immediate) {
    if (state.uiRefreshTimer) {
      window.clearTimeout(state.uiRefreshTimer);
      state.uiRefreshTimer = 0;
    }
    refreshGalleryFromBackground(els, state);
    return;
  }

  if (state.uiRefreshTimer) return;

  state.uiRefreshTimer = window.setTimeout(() => {
    state.uiRefreshTimer = 0;
    if (!state.hasPendingUiRefresh) return;
    refreshGalleryFromBackground(els, state);
  }, 2500);
}

async function loadMoreImages(els, state, options = {}) {
  const { background = false, refreshUi = true } = options;
  if (!state.hasMoreImages || state.nextImagesOffset === null) return false;
  if (state.isImageListLoading || state.isLoadingMoreImages) return false;

  state.isLoadingMoreImages = true;
  const loadToken = state.imagesLoadToken;

  try {
    const previousItemCount = state.items.length;
    const requestedOffset = state.nextImagesOffset;
    const data = await fetchImagesPage(state.nextImagesOffset);
    if (loadToken !== state.imagesLoadToken) return false;

    mergeImageItems(state, data.items || []);
    updateImagePaginationState(state, data);
    const addedItemCount = state.items.length - previousItemCount;
    const advancedOffset = state.nextImagesOffset !== requestedOffset;
    const shouldRefreshUi = refreshUi && (addedItemCount > 0 || !state.hasMoreImages);

    if (shouldRefreshUi) {
      if (background) {
        scheduleUiRefresh(els, state, !state.hasMoreImages);
      } else {
        refreshGalleryFromBackground(els, state);
      }
    }
    return addedItemCount > 0 || !state.hasMoreImages || advancedOffset;
  } catch (error) {
    setStatus(els, error.message, true);
    return null;
  } finally {
    state.isLoadingMoreImages = false;
  }
}

async function loadMoreTimelineGroupImages(els, state) {
  if (!state.isTimelineGroupMode || state.isImageListLoading || state.isLoadingMoreImages) return false;

  const loadedGroups = state.virtual.groups.filter((group) =>
    state.loadedTimelineGroups.has(group.key) || state.timelineGroupNextOffsets.has(group.key),
  );
  const lastGroup = loadedGroups[loadedGroups.length - 1];
  const groupKey = lastGroup?.key || state.activeTimelineGroupKey;
  if (!groupKey) return false;

  state.isLoadingMoreImages = true;
  try {
    const nextOffset = state.timelineGroupNextOffsets.get(groupKey);
    if (nextOffset !== undefined) {
      return Boolean(await loadTimelineGroupPage(els, state, groupKey, nextOffset));
    }

    const neighbor = await fetchTimelineNeighborGroup(groupKey, "next");
    const neighborKey = neighbor.neighbor_group_key;
    if (!neighborKey || state.loadedTimelineGroups.has(neighborKey)) return false;

    return Boolean(await loadTimelineGroupPage(els, state, neighborKey, 0));
  } catch (error) {
    setStatus(els, error.message, true);
    return null;
  } finally {
    state.isLoadingMoreImages = false;
  }
}

async function restoreTimelineGroupWindow(els, state, startGroupKey, endGroupKey, selectedPath = "") {
  if (!startGroupKey) return false;
  const selectedGroupKey = selectedPath
    ? getTimelineGroupKey({ timeline_time: selectedPath.replace(/[\\/]/g, "-") })
    : "";

  state.activeTimelineGroupKey = startGroupKey;
  state.isTimelineGroupMode = true;
  state.isImageListLoading = true;
  state.isLoadingMoreImages = false;
  state.lastLoadMoreOffset = null;
  state.hasMoreImages = false;
  state.nextImagesOffset = null;
  clearImageRefreshTimers(state);
  state.items = [];
  state.filtered = [];
  state.loadedTimelineGroups.clear();
  state.loadingTimelineGroups.clear();
    state.timelineGroupNextOffsets.clear();

  let groupKey = startGroupKey;
  let guard = 0;
  let renderedSelectedGroup = false;

  while (groupKey && guard < 240) {
    guard += 1;
    await loadTimelineGroupPage(els, state, groupKey, 0, { refreshUi: false });

    while (state.timelineGroupNextOffsets.has(groupKey) && guard < 240) {
      guard += 1;
      const nextOffset = state.timelineGroupNextOffsets.get(groupKey);
      await loadTimelineGroupPage(els, state, groupKey, nextOffset, { refreshUi: false });
    }

    if (!renderedSelectedGroup && selectedGroupKey && groupKey === selectedGroupKey) {
      state.isImageListLoading = false;
      applyFilter(els, state, { resetScroll: false });
      restorePendingSelectedPath(els, state);
      renderedSelectedGroup = true;
      break;
    }

    if (!endGroupKey || groupKey === endGroupKey) break;

    const neighbor = await fetchTimelineNeighborGroup(groupKey, "next");
    groupKey = neighbor.neighbor_group_key || "";
  }

  state.isImageListLoading = false;
  if (!renderedSelectedGroup) {
    applyFilter(els, state, { resetScroll: false });
  }
  return true;
}

async function restoreGalleryScrollPosition(els, state) {
  if (!els.galleryScroller || state.hasRestoredScroll) return;
  const targetTop = Number(state.pendingRestoreScrollTop);
  if (!Number.isFinite(targetTop) || targetTop <= 0) return;

  state.hasRestoredScroll = true;
  const applyTargetScroll = () => {
    els.galleryScroller.scrollTop = Math.min(targetTop, Math.max(0, state.virtual.totalHeight));
    renderVirtualGalleryViewport(els, state);
    updateStickyHeader(els, state);
  };

  applyFilter(els, state, { resetScroll: false });
  applyTargetScroll();

  while (
    state.hasMoreImages &&
    state.virtual.totalHeight < targetTop + els.galleryScroller.clientHeight
  ) {
    const loaded = await loadMoreImages(els, state, { refreshUi: true });
    applyTargetScroll();
    if (loaded !== true) break;
  }
}

function scheduleBackgroundImageRefresh(els, state) {
  if (state.backgroundScanTimer) return;

  if (state.imageScanComplete) return;

  if (!state.hasMoreImages && !state.previewOnly) return;

  state.backgroundScanTimer = window.setTimeout(async () => {
    state.backgroundScanTimer = 0;
    if (state.isImageListLoading || state.isLoadingMoreImages) return;

    try {
      const previousItemCount = state.items.length;
      const offset = state.nextImagesOffset ?? state.items.length;
      const data = await fetchImagesPage(offset, { refreshScan: true });
      mergeImageItems(state, data.items || []);
      updateImagePaginationState(state, data);
      if (state.items.length > previousItemCount || !state.hasMoreImages) {
        scheduleUiRefresh(els, state, !state.hasMoreImages);
      }

      if (state.imageScanComplete) {
        loadTimelineIndex(state)
          .then(() => renderTimelineIndex(els, state))
          .catch(() => {
            state.timelineIndexEntries = [];
            renderTimelineIndex(els, state);
          });
        return;
      }
    } catch (_error) {
      // keep current UI
    }

    scheduleBackgroundImageRefresh(els, state);
  }, 1200);
}



function maybeLoadMoreImages(els, state) {
  if (!els.galleryScroller) return;
  if (state.isImageListLoading || state.isLoadingMoreImages) return;

  const remaining =
    els.galleryScroller.scrollHeight -
    els.galleryScroller.scrollTop -
    els.galleryScroller.clientHeight;

  if (state.isTimelineGroupMode) {
    if (remaining < getLoadMoreThreshold(els, state)) {
      loadMoreTimelineGroupImages(els, state).then(() => updateStickyHeader(els, state));
    }
    return;
  }

  if (!state.hasMoreImages) return;

  if (remaining < getLoadMoreThreshold(els, state)) {
    if (state.nextImagesOffset === state.lastLoadMoreOffset) return;

    state.lastLoadMoreOffset = state.nextImagesOffset;
    loadMoreImages(els, state).then((loaded) => {
      if (loaded !== true) {
        state.lastLoadMoreOffset = null;
      }
      updateStickyHeader(els, state);
      if (loaded !== null && state.hasMoreImages) {
        scheduleLoadMoreRecheck(
          els,
          state,
          loaded ? LOAD_MORE_RECHECK_DELAY_MS : LOAD_MORE_EMPTY_RECHECK_DELAY_MS,
        );
      }
    });
  }
}

async function deleteSelected(els, state) {
  const selectedItems = getSelectedItems(state);

  if (!selectedItems.length) {
    setStatus(els, t("browser.selection.chooseImage"), true);
    return;
  }

  const confirmed = await showConfirm(
    selectedItems.length > 1
      ? t("delete.confirm.messageMany", selectedItems.length)
      : t("delete.confirm.message", selectedItems[0].relative_path),
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
    let latestTotal = null;
    let latestTotalGeneratedAt = "";
    for (let index = 0; index < selectedItems.length; index += 1) {
      const item = selectedItems[index];
      setStatus(
        els,
        selectedItems.length > 1
          ? t("browser.actions.deletingMany", index + 1, selectedItems.length)
          : t("browser.actions.deleting", item.relative_path),
      );
      const result = await postJson("/api/delete", { relative_path: item.relative_path });
      if (Number.isInteger(result?.total)) {
        latestTotal = result.total;
      }
      if (typeof result?.total_generated_at === "string" && result.total_generated_at) {
        latestTotalGeneratedAt = result.total_generated_at;
      }
    }

    const deletedPath = selectedItems[0].relative_path;
    const deletedCount = selectedItems.length;
    removePathsFromGalleryState(
      els,
      state,
      selectedItems.map((item) => item.relative_path),
    );
    if (Number.isInteger(latestTotal)) {
      state.totalImageCount = latestTotal;
    }
    if (latestTotalGeneratedAt) {
      state.totalImageCountUpdatedAt = latestTotalGeneratedAt;
    }
    applyFilter(els, state, { resetScroll: false });
    setStatus(
      els,
      deletedCount > 1
        ? t("browser.actions.deletedMany", deletedCount)
        : t("browser.actions.deleted", deletedPath),
    );
  } catch (error) {
    setStatus(els, error.message, true);
  }
}

async function copySelected(els, state) {
  const selectedItems = getSelectedItems(state).filter(imageExists);

  if (!selectedItems.length) {
    const message = t("browser.selection.chooseImage");
    setStatus(els, message, true);
    await showAlert(message, {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  const defaultTarget = state.config?.default_copy_target?.trim() || "";
  if (!defaultTarget) {
    const message = t("browser.copy.targetMissing");
    setStatus(els, message, true);
    await showAlert(message, {
      title: t("dialog.title.warning"),
      confirmText: t("dialog.buttons.ok"),
    });
    return;
  }

  const confirmed = await showConfirm(
    selectedItems.length > 1
      ? t("browser.copy.confirmManyMessage", selectedItems.length, defaultTarget)
      : t("browser.copy.confirmMessage", selectedItems[0].relative_path, defaultTarget),
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
    let lastCopiedTo = "";

    for (let index = 0; index < selectedItems.length; index += 1) {
      const item = selectedItems[index];
      setStatus(
        els,
        selectedItems.length > 1
          ? t("browser.actions.copyingMany", index + 1, selectedItems.length)
          : t("browser.actions.copying", item.relative_path),
      );

      const result = await postJson("/api/copy", {
        relative_path: item.relative_path,
        target_dir: "",
      });

      lastCopiedTo = result.copied_to;
    }

    const message =
      selectedItems.length > 1
        ? t("browser.actions.copiedMany", selectedItems.length, defaultTarget)
        : t("browser.actions.copied", lastCopiedTo);
    setStatus(els, message);
  } catch (error) {
    setStatus(els, error.message, true);
    await showAlert(error.message, {
      title: t("dialog.title.error"),
      confirmText: t("dialog.buttons.ok"),
    });
  }
}

function clearSelection(els, state) {
  state.selectedPaths.clear();
  state.lastSelectedPath = null;
  updateSelection(els, state);
}

function invertSelection(els, state) {
  if (!state.filtered.length) return;

  const visiblePaths = state.filtered.map((item) => item.relative_path);
  const nextSelectedPaths = new Set(state.selectedPaths);

  for (const path of visiblePaths) {
    if (nextSelectedPaths.has(path)) {
      nextSelectedPaths.delete(path);
    } else {
      nextSelectedPaths.add(path);
    }
  }

  state.selectedPaths = nextSelectedPaths;
  state.lastSelectedPath =
    visiblePaths.find((path) => state.selectedPaths.has(path)) || null;

  updateSelection(els, state);
}

function togglePathSelection(state, path) {
  if (state.selectedPaths.has(path)) {
    state.selectedPaths.delete(path);
    if (state.lastSelectedPath === path) {
      state.lastSelectedPath = state.selectedPaths.values().next().value || null;
    }
  } else {
    state.selectedPaths.add(path);
    state.lastSelectedPath = path;
  }
}

function updateCardSelection(els, state, path, event) {
  if (event.shiftKey && state.lastSelectedPath) {
    const fromIndex = state.filtered.findIndex(
      (item) => item.relative_path === state.lastSelectedPath,
    );
    const toIndex = state.filtered.findIndex((item) => item.relative_path === path);

    if (fromIndex >= 0 && toIndex >= 0) {
      const start = Math.min(fromIndex, toIndex);
      const end = Math.max(fromIndex, toIndex);

      for (const item of state.filtered.slice(start, end + 1)) {
        state.selectedPaths.add(item.relative_path);
      }

      state.lastSelectedPath = path;
      return;
    }
  }

  togglePathSelection(state, path);
}

function removePathsFromGalleryState(els, state, paths) {
  const removedPaths = new Set(paths);
  state.items = state.items.filter((item) => !removedPaths.has(item.relative_path));

  for (const path of removedPaths) {
    state.selectedPaths.delete(path);
  }

  if (state.lastSelectedPath && removedPaths.has(state.lastSelectedPath)) {
    state.lastSelectedPath = state.selectedPaths.values().next().value || null;
  }

  if (Number.isInteger(state.totalImageCount)) {
    state.totalImageCount = Math.max(0, state.totalImageCount - removedPaths.size);
  }

  applyFilter(els, state, { resetScroll: false });
}

function selectAllFiltered(els, state) {
  for (const item of state.filtered) {
    state.selectedPaths.add(item.relative_path);
  }

  state.lastSelectedPath = state.filtered.at(-1)?.relative_path || null;
  updateSelection(els, state);
}

function isTextEntryTarget(target) {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    target?.isContentEditable
  );
}

function bindIndexEvents(els, state) {
  on(els.searchInput, "input", () => applyFilter(els, state));
  on(els.dateStartInput, "input", () => applyFilter(els, state));
  on(els.dateEndInput, "input", () => applyFilter(els, state));

  on(els.dateFilterToggle, "click", () => {
    els.dateFilterPanel?.classList.toggle("is-hidden");
    updateDateFilterToggle(els);
  });

  on(els.clearDateFilterButton, "click", () => {
    if (els.dateStartInput) els.dateStartInput.value = "";
    if (els.dateEndInput) els.dateEndInput.value = "";
    applyFilter(els, state);
  });

  on(els.previewSelectedButton, "click", () => {
    const selectedImage = getPrimarySelectedItem(state);

    if (!selectedImage) {
      setStatus(els, t("browser.selection.chooseImage"), true);
      return;
    }

    openViewer(els, state, selectedImage.relative_path);
  });

  on(els.copySelectedButton, "click", () => {
    copySelected(els, state);
  });

  on(els.clearSelectionButton, "click", () => {
    clearSelection(els, state);
  });

  on(els.invertSelectionButton, "click", () => {
    invertSelection(els, state);
  });

  on(els.deleteSelectedButton, "click", () => {
    deleteSelected(els, state);
  });

  on(document, "keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
      if (isTextEntryTarget(event.target)) return;
      event.preventDefault();
      selectAllFiltered(els, state);
      return;
    }

    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    if (!state.filtered.length) return;

    const selectedImage = getPrimarySelectedItem(state);
    const index = state.filtered.findIndex(
      (item) => item.relative_path === selectedImage?.relative_path,
    );

    const baseIndex = index >= 0 ? index : 0;
    const nextIndex =
      event.key === "ArrowRight"
        ? (baseIndex + 1) % state.filtered.length
        : (baseIndex - 1 + state.filtered.length) % state.filtered.length;

    state.selectedPaths = new Set([state.filtered[nextIndex].relative_path]);
    state.lastSelectedPath = state.filtered[nextIndex].relative_path;
    scrollToGalleryPath(els, state, state.lastSelectedPath);
    updateSelection(els, state);
  });

  on(els.toggleSidebarButton, "click", () => {
    els.galleryPage.classList.toggle("is-collapsed");
    updateSidebarToggleText(els);
    rebuildVirtualGallery(els, state);
  });

  on(els.galleryScroller, "scroll", () => {
    scheduleVirtualGalleryRender(els, state);
    maybeLoadMoreImages(els, state);
    maybeLoadTimelineNeighbors(els, state);
    const now = Date.now();
    if (now - state.lastScrollSaveAt > GALLERY_SCROLL_SAVE_INTERVAL_MS) {
      state.lastScrollSaveAt = now;
      saveGalleryViewState(els, state);
    }
  });

  on(els.galleryIndex, "wheel", () => markTimelineIndexUserScroll(state));
  on(els.galleryIndex, "pointerdown", () => markTimelineIndexUserScroll(state));
  on(els.galleryIndex, "touchstart", () => markTimelineIndexUserScroll(state));
  on(els.galleryIndex, "scroll", () => markTimelineIndexUserScroll(state));

  on(window, "resize", () => {
    rebuildVirtualGallery(els, state);
  });

  on(window, "pagehide", () => saveGalleryViewState(els, state));
}

async function initializeIndexPage(els, state) {
  const params = new URLSearchParams(window.location.search);
  const query = params.get("q") || "";
  const startDate = params.get("from") || "";
  const endDate = params.get("to") || "";
  const selected = params.get("selected");
  const duplicateGroupId = params.get("dup_group");

  await loadConfig(els, state);
  state.activeDuplicateGroupId = duplicateGroupId;
  state.pendingSelectedPath = selected || "";

  if (query && els.searchInput) {
    els.searchInput.value = query;
  }

  if (startDate && els.dateStartInput) {
    els.dateStartInput.value = startDate;
  }

  if (endDate && els.dateEndInput) {
    els.dateEndInput.value = endDate;
  }

  if (startDate || endDate) {
    els.dateFilterPanel?.classList.remove("is-hidden");
  }

  const savedViewState = readGalleryViewState(state.config.active_root);
  const canUseSavedViewState =
    savedViewState &&
    (savedViewState.query || "") === query &&
    (savedViewState.dateStart || "") === startDate &&
    (savedViewState.dateEnd || "") === endDate &&
    (savedViewState.duplicateGroupId || "") === (duplicateGroupId || "");
  if (
    canUseSavedViewState
  ) {
    state.pendingRestoreScrollTop = Number(savedViewState.scrollTop) || null;
  }

  translatePage(els, state);
  await loadImages(els, state);
  loadDeferredIndexData(els, state);

  if (
    selected &&
    canUseSavedViewState &&
    savedViewState.timelineMode &&
    savedViewState.timelineStartGroupKey
  ) {
    await restoreTimelineGroupWindow(
      els,
      state,
      savedViewState.timelineStartGroupKey,
      savedViewState.timelineEndGroupKey || savedViewState.timelineGroupKey || "",
      selected,
    );
  }

  if (!restorePendingSelectedPath(els, state)) {
    restoreGalleryScrollPosition(els, state);
  }

  if (
    selected &&
    !state.hasRestoredSelectedPath &&
    state.filtered.some((item) => item.relative_path === selected)
  ) {
    state.selectedPaths.add(selected);
    state.lastSelectedPath = selected;
    scrollToGalleryPath(els, state, selected);
    updateSelection(els, state);
  }

  setStatus(els, t("browser.status.ready"));
}

function renderIndexInitialState(els) {
  updateSelection(els, createIndexState());
  setText(els.imageCount, "0");
  setText(els.imageCountUpdatedAt, "-");
}

export function initIndexPage() {
  const els = getIndexElements();

  if (!els.galleryPage && !els.gallery) return;

  const state = createIndexState();

  ensureDialog();
  renderIndexInitialState(els);
  bindIndexEvents(els, state);

  initializeIndexPage(els, state).catch((error) => {
    setStatus(els, error.message, true);
    markI18nReady();
  });

  return { els, state };
}
