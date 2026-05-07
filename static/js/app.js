// SPDX-License-Identifier: MIT

import { initLang, scheduleI18nFallback, translateStaticText } from "./locales/i18n.js";
import { applyStoredDisplayStyle } from "./core/theme.js";

import { initSettingsPage } from "./pages/settings-page.js?v=20260424-io9";
import { initIndexPage } from "./pages/index-page.js?v=20260429-timeline2";
import { initViewerPage } from "./pages/viewer-page.js?v=20260429-timeline2";
import { initDuplicatesPage } from "./pages/duplicates-page.js?v=20260424-io10";
import { initRecyclePage } from "./pages/recycle-page.js?v=20260424-io9";
import { initTasksPage } from "./pages/tasks-page.js?v=20260424-io9";

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
}

// Wait for the DOM to be fully loaded before initializing the app
document.addEventListener("DOMContentLoaded", initApp);
