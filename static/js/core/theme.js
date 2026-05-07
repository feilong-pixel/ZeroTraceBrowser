// SPDX-License-Identifier: MIT

const STORAGE_KEY = "ztbDisplayStyle";
const THEME_LINK_ID = "ztb-theme-link";

const DISPLAY_STYLES = {
  default: { href: "./css/style.css?v=20260424-io9" },
  "multi-light": { href: "./css/style_Multi.css?v=20260507-style", theme: "light" },
  "multi-dark": { href: "./css/style_Multi.css?v=20260507-style", theme: "dark" },
  harbor: { href: "./css/style_Harbor.css?v=20260507-style" },
};

export function normalizeDisplayStyle(displayStyle) {
  return Object.prototype.hasOwnProperty.call(DISPLAY_STYLES, displayStyle) ? displayStyle : "default";
}

export function getStoredDisplayStyle() {
  try {
    return normalizeDisplayStyle(localStorage.getItem(STORAGE_KEY) || "default");
  } catch {
    return "default";
  }
}

export function saveStoredDisplayStyle(displayStyle) {
  try {
    localStorage.setItem(STORAGE_KEY, normalizeDisplayStyle(displayStyle));
  } catch {
    // Local storage may be unavailable in private or locked-down browser modes.
  }
}

export function applyStoredDisplayStyle() {
  return applyDisplayStyle(getStoredDisplayStyle(), { persist: false });
}

export function applyDisplayStyle(displayStyle, options = {}) {
  const normalized = normalizeDisplayStyle(displayStyle);
  const style = DISPLAY_STYLES[normalized];
  const link = ensureThemeLink();

  link.href = style.href;

  if (style.theme) {
    document.documentElement.dataset.theme = style.theme;
  } else {
    delete document.documentElement.dataset.theme;
  }

  document.documentElement.dataset.displayStyle = normalized;

  if (options.persist !== false) {
    saveStoredDisplayStyle(normalized);
  }

  return normalized;
}

function ensureThemeLink() {
  const existing = document.getElementById(THEME_LINK_ID);
  if (existing) return existing;

  const currentLink = [...document.querySelectorAll('link[rel="stylesheet"]')]
    .find((link) => link.getAttribute("href")?.includes("/css/style") || link.getAttribute("href")?.includes("./css/style"));
  if (currentLink) {
    currentLink.id = THEME_LINK_ID;
    return currentLink;
  }

  const link = document.createElement("link");
  link.id = THEME_LINK_ID;
  link.rel = "stylesheet";
  document.head.appendChild(link);
  return link;
}
