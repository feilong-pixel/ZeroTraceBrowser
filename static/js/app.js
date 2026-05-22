// SPDX-License-Identifier: MIT

import { initLang, scheduleI18nFallback, translateStaticText } from "./locales/i18n.js";
import { applyStoredDisplayStyle } from "./core/theme.js";

import { initSettingsPage } from "./pages/settings-page.js?v=20260424-io9";
import { initIndexPage } from "./pages/index-page.js?v=20260429-timeline2";
import { initViewerPage } from "./pages/viewer-page.js?v=20260513-viewer-media";
import { initDuplicatesPage } from "./pages/duplicates-page.js?v=20260424-io10";
import { initRecyclePage } from "./pages/recycle-page.js?v=20260424-io9";
import { initTasksPage } from "./pages/tasks-page.js?v=20260513-db-cleanup";
import { initIphonePage } from "./pages/iphone-page.js?v=20260513-iphone";
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
  initIphonePage();
  initSimilarityPage();
}

// Wait for the DOM to be fully loaded before initializing the app
document.addEventListener("DOMContentLoaded", initApp);
