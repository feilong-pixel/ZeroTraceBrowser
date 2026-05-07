// SPDX-License-Identifier: MIT

export default {
  app: {
    intro: "Lightweight image browser with controlled operations.",
    title: "ZeroTraceBrowser"
  },
  browser: {
    actions: {
      copied: path=>`Copied to ${path}`,
      copiedMany: (count, target)=>`Copied ${count} images to ${target}`,
      copying: path=>`Copying ${path} ...`,
      copyingMany: (current, total)=>`Copying ${current} / ${total} images ...`,
      deleted: path=>`Moved ${path} to the Recycle Bin.`,
      deletedMany: count=>`Moved ${count} images to the Recycle Bin.`,
      deleting: path=>`Moving ${path} to the Recycle Bin ...`,
      deletingMany: (current, total)=>`Moving ${current} / ${total} images to the Recycle Bin ...`
    },
    buttons: {
      clearSelection: "Clear selection",
      clearDateFilter: "Clear",
      copySelected: "Copy",
      dateFilter: "Date",
      dateFilterActive: "Date filter on",
      deleteSelected: "Delete",
      invertSelection: "Invert selection",
      openDuplicatesResults: "Results",
      previewSelected: "Open selected",
      recycleTool: "Recycle Bin",
      settingsTool: "Settings",
      showSidebar: "Show controls",
      tasksTool: "Organizer",
      toggleSidebar: "Hide controls"
    },
    copy: {
      confirm: "Copy",
      confirmManyMessage: (count, target) =>
            `Copy ${count} selected images?\nThe files will be copied to: ${target}`,
      confirmMessage: (path, target) =>
            `Copy ${path}?\nThe file will be copied to: ${target}`,
      confirmTitle: "Copy Image",
      targetMissing: "Set a copy target directory first, or save a default copy target."
    },
    duplicates: {
      count: (count) => `Groups: ${count}`,
      empty: "No available duplicates.json result was found.",
      generatedAt: (time) => `Generated: ${time}`,
      noMatchInGroup: "Files in the current duplicate group are no longer available.",
      summaryReady: "Results are ready. Open the results page to review groups."
    },
    labels: {
      copyTargetShort: "Copy target",
      currentRoot: "Current folder",
      deleteMode: "Delete mode",
      duplicates: "Duplicates",
      endDate: "End date",
      imageCount: "Images",
      imageCountUpdatedAt: (time) => `Count updated: ${time}`,
      search: "Search",
      selection: "Selection",
      startDate: "Start date",
      status: "Status",
      tools: "Tools"
    },
    placeholders: {
      date: "YYYY-MM-DD / YYYY/MM/DD",
      search: "Filter by file name"
    },
    selection: {
      chooseImage: "Select an image first.",
      defaultCopyTarget: "Use default directory",
      hintEmpty: "Tip: You can select images by clicking them in the gallery",
      hintMultiple: "Tip: Shift-click selects a range. Ctrl+A selects the current results.",
      hintSingle: "Tip: Preview first, then copy or delete",
      multipleDetail: (name, count) => `${name} and ${count - 1} more`,
      multipleTitle: (count) => `${count} images selected`,
      noneDetail: "Select one or more images before operating",
      noneTitle: "No image selected",
      recycleDeleteMode: "Move to Recycle Bin",
      singleTitle: "1 image selected"
    },
    status: {
      loadedImages: (count) => `Loaded ${count} images.`,
      loadedImagesProgress: (count, total) => `Loaded ${count} / ${total} images...`,
      loadingImages: "Loading image list...",
      noMatch: "No matching images.",
      ready: "Ready.",
      rootMissing: "The current directory does not exist. Showing an empty result."
    }
  },
  delete: {
    confirm: {
      confirm: "Move to Recycle Bin",
      messageMany: (count) =>
            `Move ${count} selected images to the Recycle Bin?\nYou can restore them later from the Recycle Bin page.`,
      message: (path) =>
            `Move ${path} to the Recycle Bin?\nYou can restore it later from the Recycle Bin page.`,
      title: "Move to Recycle Bin"
    }
  },
  dialog: {
    buttons: {
      cancel: "Cancel",
      confirm: "Confirm",
      ok: "OK"
    },
    title: {
      confirm: "Confirm",
      error: "Operation Failed",
      warning: "Warning"
    }
  },
  duplicates: {
    backToGallery: "Back to gallery",
    confirmLeaveWhileBusy: "A bulk action is still running. Leaving this page may interrupt the current operation or stop the live status display. Continue?",
    bulkConfirm: "Move to Recycle Bin",
    bulkDeleted: (count) => `Moved ${count} files from this page to the Recycle Bin.`,
    bulkDeleting: (count) => `Moving ${count} files from this page to the Recycle Bin...`,
    bulkDisabledForPhash: "pHash similarity results require manual review and cannot be bulk deleted.",
    bulkMoveToRecycle: "Move duplicates",
    bulkStrictTitle: (count) => `Move ${count} strict duplicate files from this page to the Recycle Bin`,
    confirmBulkStrictDelete: (count) =>
            `This will move ${count} strict duplicate files from the current page to the Recycle Bin. Only duplicate files will be processed; kept files will not be deleted. Continue?`,
    deleteSelected: "Delete",
    deleted: (path) => `Moved ${path} to the Recycle Bin`,
    deleting: (path) => `Moving ${path} to the Recycle Bin ...`,
    groupUnavailable: "Files in this group are no longer available. Click [Open Organizer Tool] and rebuild Hash DB from the maintenance tools in the [MediaArchiveOrganizer Tasks] page.",
    groups: "Groups",
    items: (count) => `${count} items`,
    leavePage: "Leave page",
    loading: "Loading duplicate results...",
    method: (reason) => `Method: ${reason}`,
    methodPhash: "pHash Similarity",
    methodStrict: "Strict Match",
    nextPage: "Next Page",
    noMethodResults: "No duplicate results for the selected detection method.",
    noResults: "No duplicate results yet.",
    noSelection: "Please select the image you want to delete.",
    noStrictDuplicatesToDelete: "No strict duplicate files on this page are available for bulk deletion.",
    openTasksTool: "Organizer",
    openedResultRoot: "Opened the results folder in File Explorer.",
    pageInfo: (page, total) => `Page ${page} / ${total}`,
    pageIntro: "Browse duplicate groups with pagination and handle duplicate files directly on this page.",
    pageTitle: "Duplicate Results",
    prevPage: "Prev Page",
    ready: "Ready.",
    refresh: "Refresh",
    resultRoot: "Results folder",
    statusAvailable: "Available",
    statusDeleted: "Deleted"
  },
  recycle: {
    archiveLogs: "Archive",
    archivedLogs: (count, path) => `Archived ${count} delete log entries: ${path}`,
    backToGallery: "Back to gallery",
    clearRecycle: "Clear Page",
    clearCurrentPageTitle: (count) => `Clear ${count} Recycle Bin files on this page`,
    cleared: (count) => `Cleared ${count} Recycle Bin files from this page.`,
    clearedAndArchived: (count, path) => `Emptied ${count} files from the Recycle Bin and archived delete logs: ${path}`,
    clearedLogs: (count, target) => `Cleared ${count} ${target}.`,
    confirmLeaveWhileBusy: "A Recycle Bin action is still running. Leaving this page may interrupt the current operation or stop the live status display. Continue?",
    confirmArchiveLogs: {
      confirm: "Archive logs",
      message: "Archive the current delete_log.csv with a timestamp and clear the current log display?",
      title: "Archive delete logs"
    },
    confirmClear: {
      confirm: "Clear Page",
      message: (count) => `Clear ${count} Recycle Bin files on this page? This action cannot be undone.`,
      messagePermanent: (count) => `Clear ${count} Recycle Bin files on this page? On this system, files will be deleted permanently and cannot be recovered.`,
      messageSystemRecycle: (count) => `Move ${count} Recycle Bin files on this page to the Windows system Recycle Bin?`,
      title: "Clear Page"
    },
    confirmClearLogs: {
      confirm: "Clear logs",
      message: (target) =>
            `Clear ${target}?\nThis will not affect files currently in the Recycle Bin.`,
      title: "Clear logs"
    },
    confirmPurge: {
      confirm: "Delete permanently",
      message: (path) =>
            `Permanently delete ${path}?\nThis file will be removed from deleted and cannot be recovered.`,
      messagePermanent: (path) =>
            `Delete ${path}? On this system, the file will be deleted permanently and cannot be recovered.`,
      messageSystemRecycle: (path) =>
            `Delete ${path}? The file will be moved to the Windows system Recycle Bin.`,
      title: "Confirm permanent deletion"
    },
    confirmRestore: {
      confirm: "Restore",
      message: (path) =>
            `Restore ${path}?\nThe file will be moved back to its original location.`,
      title: "Confirm restore"
    },
    deleteLogs: "Delete logs",
    deletedAt: "Deleted at",
    deletedFile: "Deleted file",
    itemCount: (count) => `${count} items`,
    itemStatus: "Status",
    leavePage: "Leave page",
    loading: "Loading Recycle Bin...",
    logActions: {
      deleted: "Deleted",
      purged: "Purged",
      restored: "Restored"
    },
    logClearTargets: {
      purged: "Purged logs",
      restored: "Restored logs",
      restoredAndPurged: "Restored + purged logs"
    },
    logEntries: "Log entries",
    logFilters: {
      all: "All",
      deleted: "Deleted",
      purged: "Purged",
      restored: "Restored"
    },
    logSummary: (shown, filtered, total) => `Showing ${shown} / ${filtered} of ${total}`,
    logTable: {
      action: "Action",
      file: "File",
      originalPath: "Original path",
      recyclePath: "Recycle Bin path",
      time: "Time"
    },
    noFilteredLogs: "No logs match this filter.",
    noLogs: "No delete logs yet.",
    noLogsToArchive: "No delete logs to archive.",
    noRecycleItems: "Recycle bin is empty.",
    nextPage: "Next Page",
    originalExists: "Original path already exists",
    pageInfo: (page, total) => `Page ${page} / ${total}`,
    pageIntro: "Review items in the Recycle Bin, restore files, empty the bin safely, and inspect delete logs.",
    pageTitle: "Recycle Bin",
    pending: "Pending",
    prevPage: "Prev Page",
    purged: (path) => `Permanently deleted ${path}`,
    purgedItem: "Permanently deleted",
    ready: "Ready.",
    recycleItems: "Recycle Bin items",
    refresh: "Refresh",
    restoreButton: "Restore",
    restoreTarget: "Original path",
    restoreUnavailable: "Original path metadata is missing",
    restored: (path) => `Restored to ${path}`,
    restoredItem: "Restored",
    systemRecycleUnsupported: "Moving files to the system Recycle Bin is supported only on Windows."
  },
  settings: {
    advanced: {
      placeholder: "Thumbnail size, default sorting, and Viewer defaults can be added here later."
    },
    buttons: {
      addRoot: "Add",
      backToGallery: "Back to gallery",
      clearCopyTarget: "Clear",
      removeRoot: "Remove",
      saveCopyTarget: "Save",
      saveLanguage: "Save",
      switchRoot: "Set Current"
    },
    confirmCleanupRoot: {
      cancel: "Remove only",
      confirm: "Remove and clear",
      message: "Also clear this folder's generated data and history? This includes hash_db, duplicates, image summaries, Timeline index, delete_log, and this folder's local recycle copies. Original images in the folder are not deleted.",
      title: "Clear folder history"
    },
    confirmRemoveRoot: {
      confirm: "Remove",
      message: "Remove this folder from the loaded folder list?",
      title: "Remove folder"
    },
    intro: "Manage image roots, the default copy target, and interface language.",
    labels: {
      activeRoot: "Current folder",
      copyTarget: "Default copy target",
      copyTargetInput: "Default copy folder",
      language: "Interface language",
      languageSelect: "Interface language",
      newRootInput: "Add folder",
      rootSelect: "Loaded folders"
    },
    placeholders: {
      copyTarget: "Backend default is used when empty",
      newRoot: "D:\\Images"
    },
    sections: {
      advanced: "Advanced",
      copyTarget: "Copy Target",
      language: "Language",
      overview: "Overview",
      roots: "Image folders",
      status: "Status"
    },
    status: {
      copyTargetCleared: "Default copy target cleared",
      copyTargetSaved: "Default copy target saved",
      invalidRoot: "Enter a folder to add",
      languageSaved: "Language saved",
      loadFailed: "Failed to load settings",
      ready: "Ready",
      requestFailed: "Request failed",
      rootAdded: "Folder added and set as current",
      rootNotRegistered: "This folder is not registered",
      rootRemoved: "Folder removed",
      rootRemovedWithCleanup: "Folder removed and related data cleared",
      rootRequired: "At least one folder must remain",
      rootSwitched: "Current folder switched",
      unsupportedLanguage: "Unsupported language"
    },
    title: "Settings"
  },
  system: {
    labels: {
      finishedAt: "Finished at",
      generatedAt: "Generated at",
      startedAt: "Started at",
      status: "Status",
      summary: "Summary"
    }
  },
  tasks: {
    backToGallery: "Back to gallery",
    confirmLeaveWhileRunning: "A task is still running. Leaving this page may interrupt the current processing or stop live monitoring. Continue?",
    confirmRunRebuild: "Rebuild the Hash DB and duplicate results from the current folder?",
    confirmRunTask: "Start organizing and update the Hash DB and duplicate results?",
    csvPath: "CSV Path",
    destDir: "Destination Directory",
    duplicateDetection: "Duplicate detection",
    errors: {
      taskAlreadyRunning: "Another organizer or rebuild task is already running."
    },
    hashDbPath: "Hash DB Path",
    hashMethod: "Hash Method",
    hideHashMaintenance: "Hide duplicate result maintenance",
    idle: "Idle",
    jsonPath: "JSON Path",
    language: "Language",
    leavePage: "Leave page",
    liveOutput: "Live Output",
    logPath: "Log Path",
    maintenanceTools: "Maintenance Tools",
    mode: "Mode",
    noDirectoryToOpen: "No directory to open.",
    noTaskOutput: "No task output yet.",
    noTaskStarted: "No task started.",
    openDirectory: "Open",
    openedDirectory: (path) => `Opened directory: ${path}`,
    outputs: "Outputs",
    pageIntro: "Run organizer jobs and generate logs, CSV, and duplicates.json.",
    pageTitle: "MediaArchiveOrganizer Tasks",
    phashThreshold: "pHash Threshold",
    rebuildRoot: "Rebuild Root",
    runRebuildTask: "Rebuild",
    runTask: "Start",
    showHashMaintenance: "Show duplicate result maintenance",
    sourceDir: "Source folder",
    taskConfig: "Task config",
    taskId: "Task ID",
    taskSummary: "Task summary"
  },
  viewer: {
    action: {
      copied: (path) => `Copied to ${path}`,
      copying: (path) => `Copying ${path} ...`,
      deleted: (path) => `Moved ${path} to the Recycle Bin.`,
      deleting: (path) => `Moving ${path} to the Recycle Bin ...`,
      openedEditor: (path) => `Opened in image editor: ${path}`,
      openingEditor: (path) => `Opening ${path} in image editor ...`
    },
    buttons: {
      backToGallery: "Back to Gallery",
      copySelected: "Copy",
      deleteSelected: "Delete",
      openEditor: "Edit in Paint",
      rotateLeft: "Rotate left",
      rotateRight: "Rotate right",
      showSidebar: "Show Info",
      toggleSidebar: "Hide Info"
    },
    display: {
      index: (i, t) => `${i} / ${t}`,
      zoom: (z) => `Zoom: ${z}%`
    },
    exif: {
      empty: "Select an image to view capture metadata.",
      failed: "Failed to read EXIF metadata.",
      loading: "Loading EXIF metadata...",
      unavailable: "No usable EXIF metadata was found for this image."
    },
    hint: "Tip: Use left and right to switch images. Delete moves files to the Recycle Bin.",
    labels: {
      actions: "Actions",
      exifAperture: "Aperture",
      exifCamera: "Camera",
      exifDatetime: "Captured at",
      exifDimensions: "Dimensions",
      exifFocalLength: "Focal Length",
      exifGpsAltitude: "Altitude",
      exifGpsCoordinates: "Location",
      exifInfo: "EXIF",
      exifIso: "ISO",
      exifLens: "Lens",
      exifShutter: "Shutter",
      info: "Image info",
      status: "Status"
    },
    status: {
      ready: "Ready."
    }
  }
};
