// SPDX-License-Identifier: MIT

import { initLang, scheduleI18nFallback, translateStaticText } from "./locales/i18n.js";
import { applyStoredDisplayStyle } from "./core/theme.js";

import { initSettingsPage } from "./pages/settings-page.js?v=20260424-io9";
import { initIndexPage } from "./pages/index-page.js?v=20260529-timeline-page";
import { initViewerPage } from "./pages/viewer-page.js?v=20260529-viewer-first-paint";
import { initDuplicatesPage } from "./pages/duplicates-page.js?v=20260424-io10";
import { initRecyclePage } from "./pages/recycle-page.js?v=20260424-io9";
import { initTasksPage } from "./pages/tasks-page.js?v=20260513-db-cleanup";
import { initMaintenancePage } from "./pages/maintenance-page.js?v=20260528-maintenance";
import { initImportPage } from "./pages/import-page.js?v=20260524-import-shell";
import { initMobileImportPage } from "./pages/mobile-import-page.js?v=20260522-mobile-import";
import { initSimilarityPage } from "./pages/similarity-page.js?v=20260522-similarity";

function initApp() {
  applyStoredDisplayStyle();
  initLang();
  translateStaticText();
  scheduleI18nFallback();
  initSettingsPage();
  initIndexPage();
  initViewerPage();
  initDuplicatesPage();
  initRecyclePage();
  initTasksPage();
  initMaintenancePage();
  initImportPage();
  initMobileImportPage();
  initSimilarityPage();
}

// Wait for the DOM to be fully loaded before initializing the app
document.addEventListener("DOMContentLoaded", initApp);
