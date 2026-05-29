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
      importPhotosTool: "Import Photos",
      mobileImportTool: "iPhone Import",
      similarityTool: "Similarity",
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
      empty: "No available duplicate result was found.",
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
      info: "Info",
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
  importPhotos: {
    configLoadFailed: "Failed to load sync settings",
    connectedDevices: "Connected devices",
    connectionStatus: "Connection Status",
    destinationRoot: "Destination root",
    deviceFallbackLink: "Open Device Fallback",
    deviceLastSeen: (time) => `Last seen: ${time}`,
    failed: "Failed",
    imported: "Imported",
    importStatus: "Import Status",
    lastSeen: "Last seen",
    localAddress: "Local address",
    logEmpty: "No phone sync activity yet.",
    notPaired: "Not paired",
    noPairedDevices: "No paired phones yet. Multiple phones can be paired here later.",
    pageIntro: "Pair a phone once, then import new photos quietly over local Wi-Fi.",
    pageTitle: "Phone Photo Sync",
    paired: "Paired",
    pairedDeviceList: "Paired Devices",
    pairedDevices: "Paired devices",
    pairingIntro: "Open the phone app and scan this code once. After pairing, the phone can find this computer again on the same Wi-Fi.",
    pairingLoadFailed: "Failed to load pairing code",
    pairingReadyLog: (baseUrl, expiresAt) => `Pairing code ready for ${baseUrl}.\nExpires: ${expiresAt}`,
    pairingReady: "Pairing ready",
    pairingTitle: "Pair Phone",
    phoneSyncIdle: "Phone sync idle",
    phoneSyncRunning: "Phone syncing",
    processed: "Processed",
    qrPayloadReady: "Pairing payload ready",
    qrPlaceholder: "QR code will appear here",
    qrReady: "Scan with the phone app",
    recentRuns: "Recent Syncs",
    recentRunsEmpty: "No phone sync runs yet.",
    refreshPairing: "Refresh Pairing Code",
    scanToPair: "Scan the QR code from the phone app to pair.",
    skipped: "Skipped",
    status_idle: "idle",
    status_ready: "ready",
    status_syncing: "syncing",
    statusSummaryLine: (processed, imported, duplicate, deleted, failed) =>
      `Phone sync: processed ${processed} / imported ${imported} / duplicates skipped ${duplicate} / deleted skipped ${deleted} / failed ${failed}.`,
    statusLoadFailed: "Failed to load phone sync status",
    summary: "Sync Summary",
    syncing: "Syncing",
    syncTarget: "Sync target",
    connectedDeviceLine: (count) => `${count} phone sync session is known on this root.`,
    waitingForPhone: "Waiting"
  },
  mobileImport: {
    albumCount: "Albums",
    backToGallery: "Back to gallery",
    buildIndex: "Build iPhone Index",
    alreadyImportedItem: (target, path) => `Already imported: ${target} -> ${path}`,
    batchStarting: (batch, limit) => `Starting batch ${batch}, up to ${limit} photos...`,
    batchSummary: (batch, indexed, imported, skipped, already) =>
      `Batch ${batch} complete. Indexed: ${indexed} / imported: ${imported} / strict duplicates skipped: ${skipped} / already imported: ${already}`,
    cancelIndex: "Cancel Indexing",
    cancelRequested: "Cancel requested",
    cancelRequestedDetail: "Cancel requested. The current batch will finish, then later batches will stop.",
    cancelledAfterBatch: (batch) => `Cancel took effect: indexing stopped after batch ${batch}.`,
    cancelledSummary: (indexed, imported, skipped, already) =>
      `Indexing cancelled. Indexed: ${indexed} / imported: ${imported} / strict duplicates skipped: ${skipped} / already imported: ${already}`,
    confirmLeaveWhileIndexing: "iPhone indexing is still running. Leaving this page will not stop the backend import, but live output here will stop updating. Leave anyway?",
    copyAllPhotos: "Copy all photos from iPhone",
    detectDevice: "Detect iPhone",
    detectFailed: "iPhone detection failed",
    detecting: "Detecting iPhone...",
    deviceDetected: "iPhone detected",
    deviceName: "iPhone",
    deviceSection: "iPhone",
    deviceSummary: "iPhone Summary",
    indexLimit: "Photos to index",
    indexed: (count) => `iPhone photo library index complete: ${count} images`,
    indexedImported: (count) => `iPhone photo library index complete: imported ${count} image`,
    indexedSkipped: (count) => `iPhone photo library index complete: skipped ${count} strict duplicate`,
    importedItem: (target, path) => `Imported: ${target} -> ${path}`,
    importSection: "Import",
    indexing: "Building iPhone photo library index...",
    indexFailed: "iPhone photo library indexing failed",
    lastIndexedAt: "Last Indexed",
    leavePage: "Leave page",
    liveOutput: "iPhone Output",
    logEmpty: "No iPhone import operation started.",
    mediaCount: "Media",
    noMorePhotos: "No more photos to process.",
    noDevice: "No iPhone loaded",
    noDeviceDetected: "No available iPhone detected",
    pageIntro: "Index and import photos from iPhone while keeping source deletion explicit and controlled.",
    pageTitle: "iPhone Import",
    pending: "Pending",
    ready: "Ready",
    skippedItem: (target, path) => `Skipped: ${target} -> ${path}`,
    storage: "Storage",
    totalSummary: (indexed, imported, skipped, already) =>
      `All batches complete. Indexed: ${indexed} / imported: ${imported} / strict duplicates skipped: ${skipped} / already imported: ${already}`,
    storageNote: "iPhone photo hashes are cached locally by device id. Original photos stay on the iPhone unless you explicitly choose otherwise."
  },
  similarity: {
    backToGallery: "Back to gallery",
    buildCache: "Build Similarity Cache",
    cacheBuilt: (processed, documentCount, featureCount, embeddingCount, skippedCached) =>
      `Similarity cache built: added ${processed} / skipped cached ${skippedCached} / document ${documentCount} / features ${featureCount} / embedding ${embeddingCount}`,
    cacheBuilding: "Building similarity cache...",
    cacheFailed: "Failed to build similarity cache",
    cacheLocalOnly: "Similarity cache warmup currently supports only the current local root.",
    clear: "Clear",
    confirmLeaveWhileBusy: "A similarity search or delete operation is still running. Leaving this page may interrupt the current operation or stop the live status display. Continue?",
    currentMethod: "Method",
    currentThreshold: "Threshold",
    deleteSelected: "Delete",
    endDate: "End Date",
    limit: "Result limit",
    leavePage: "Leave page",
    clearSelection: "Clear",
    invertSelection: "Invert",
    matchCount: "Matches",
    method: "Method",
    methodDocument: "Document Layout",
    methodEmbedding: "Lite Visual Embedding",
    methodFeature: "ORB/AKAZE Features",
    methodPhash: "pHash",
    noMatches: "No similar images found. Rebuild the Hash DB or mobile index, or raise the threshold if needed.",
    noResults: "No similarity results yet.",
    pageIntro: "Find visually similar photos in the current local image root or indexed iPhone photos that already have a local file.",
    pageTitle: "Similar Photo Search",
    queryImage: "Query Image",
    queryCardLabel: "Query",
    queryCardMeta: (method, threshold) => `${method}:${threshold} / source image`,
    queryMissing: "Enter a relative path from the current root, or an iPhone album/filename.",
    queryPath: "Query image relative path",
    queryPathPlaceholder: "For example 2026/05/IMG_0001.JPG or 100APPLE/IMG_0001.JPG",
    querySummary: "Query Summary",
    ready: (count) => `Found ${count} similar results.`,
    resultMeta: (distance, score, reason) => `Distance ${distance} / score ${score} / ${reason}`,
    results: "Results",
    selectAll: "Select All",
    scope: "Scope",
    scopeNote: "Search the current local root, or indexed iPhone photos that already have a local file in this root.",
    searchFailed: "Similarity search failed",
    searchSection: "Search",
    searching: "Searching similar images...",
    searchSimilar: "Find Similar",
    source: "Source",
    sourceAndroid: "Indexed Android photos",
    sourceIphone: "Indexed iPhone photos",
    sourceLocal: "Current local root",
    sourceUnavailable: "This search source is not wired yet.",
    startDate: "Start Date",
    summary: (count) => `Results: ${count}`,
    threshold: "Threshold"
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
    bulkDisabledForPhash: "pHash can be bulk moved on the current page only; moving 100 groups is strict-only.",
    bulkMove100ToRecycle: "Move next 100 groups",
    bulkMoveToRecycle: "Move current page duplicates",
    bulkCurrentPageTitle: (count, method) => `Move ${count} ${method} duplicate files from this page to the Recycle Bin`,
    bulkStrict100Title: "Move strict duplicate files from the next 100 groups to the Recycle Bin",
    bulkStrictTitle: (count) => `Move ${count} strict duplicate files from this page to the Recycle Bin`,
    confirmBulkCurrentPageDelete: (count, method) =>
            `This will move ${count} ${method} duplicate files from the current page to the Recycle Bin. One file is kept in each group, preferring device originals whose names start with IMG. Continue?`,
    confirmBulkStrict100Delete: (count) =>
            `This will move ${count} strict duplicate files from up to 100 groups starting at the current page to the Recycle Bin. One file is kept in each group, preferring device originals whose names start with IMG. Continue?`,
    confirmBulkStrictDelete: (count) =>
            `This will move ${count} strict duplicate files from the current page to the Recycle Bin. One file is kept in each group, preferring device originals whose names start with IMG. Continue?`,
    deleteSelected: "Delete",
    deleted: (path) => `Moved ${path} to the Recycle Bin`,
    deleting: (path) => `Moving ${path} to the Recycle Bin ...`,
    groupUnavailable: "Files in this group are no longer available. Click [Open Organizer Tool] and rebuild Hash DB from the maintenance tools in the [Media Engine Tasks] page.",
    groups: "Remaining duplicate groups",
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
    noDuplicatesToDelete: "No duplicate files on this page are available for bulk deletion.",
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
    clearRecycle100: "Clear 100 Files",
    clear100Title: "Clear up to 100 Recycle Bin files from this page",
    clearCurrentPageTitle: (count) => `Clear ${count} Recycle Bin files on this page`,
    cleared: (count) => `Cleared ${count} Recycle Bin files from this page.`,
    cleared100: (count) => `Cleared ${count} Recycle Bin files.`,
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
    confirmClear100: {
      messagePermanent: (count) => `Clear ${count} Recycle Bin files starting from this page? On this system, files will be deleted permanently and cannot be recovered.`,
      messageSystemRecycle: (count) => `Move ${count} Recycle Bin files starting from this page to the Windows system Recycle Bin?`
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
      saveDisplayStyle: "Save",
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
    displayStyles: {
      default: "Default",
      harbor: "Harbor",
      multiDark: "Multi Dark",
      multiLight: "Multi Light"
    },
    labels: {
      activeRoot: "Current folder",
      copyTarget: "Default copy target",
      copyTargetInput: "Default copy folder",
      displayStyle: "Display style",
      displayStyleSelect: "Display style",
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
      displayStyle: "Display Style",
      language: "Language",
      overview: "Overview",
      roots: "Image folders",
      status: "Status"
    },
    status: {
      copyTargetCleared: "Default copy target cleared",
      copyTargetSaved: "Default copy target saved",
      invalidRoot: "Enter a folder to add",
      displayStyleSaved: "Display style saved",
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
      unsupportedDisplayStyle: "Unsupported display style",
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
  maintenance: {
    backToTasks: "Tasks",
    galleryIndexHelp: "Rebuilds the current root's gallery image index, total count, and Timeline navigation. It does not rebuild Hash DB or duplicate results.",
    galleryIndexRoot: "Current Gallery Root",
    galleryIndexTitle: "Gallery Index",
    hashMaintenanceHelp: "Rebuilds file hashes and duplicate detection results for the current root. This can take longer than the gallery index rebuild.",
    hashMaintenanceTitle: "Hash DB and Duplicate Results",
    pageIntro: "Rebuild indexes and repair long-running gallery metadata.",
    pageTitle: "Maintenance"
  },
  tasks: {
    backToGallery: "Back to gallery",
    confirmLeaveWhileRunning: "A task is still running. Leaving this page may interrupt the current processing or stop live monitoring. Continue?",
    confirmRunImageIndexRebuild: "Rebuild the gallery index and Timeline for this folder?",
    confirmRunRebuild: "Rebuild the Hash DB and duplicate results from the current folder?",
    confirmRunTimestampRepair: "Run EXIF timestamp repair on this folder? Only files with EXIF capture time are eligible.",
    confirmRunTask: "Start organizing and update the Hash DB and duplicate results?",
    csvPath: "CSV Path",
    destDir: "Destination Directory",
    duplicateDetection: "Duplicate detection",
    errors: {
      taskAlreadyRunning: "Another organizer or rebuild task is already running."
    },
    hashDbPath: "Hash DB Path",
    hashMethod: "Hash Method",
    includeVideosHelp: "Uses ffprobe to read media creation_time from videos. Videos without embedded creation time are skipped.",
    includeVideosLabel: "Include videos with embedded creation time",
    idle: "Idle",
    language: "Language",
    leavePage: "Leave page",
    liveOutput: "Live Output",
    logPath: "Log Path",
    mode: "Mode",
    noDirectoryToOpen: "No directory to open.",
    noTaskOutput: "No task output yet.",
    noTaskStarted: "No task started.",
    maintenanceMovedHelp: "Index rebuilds, timestamp repair, and long-running maintenance live on the maintenance page.",
    stillRunning: "Task is still running...",
    openDirectory: "Open",
    openMaintenance: "Open maintenance",
    openedDirectory: (path) => `Opened directory: ${path}`,
    outputs: "Outputs",
    pageIntro: "Run organizer jobs and write results to the root database.",
    pageTitle: "Media Engine Tasks",
    phashThreshold: "pHash Threshold",
    runImageIndexRebuildTask: "Rebuild gallery index",
    runRebuildTask: "Rebuild",
    runTask: "Start",
    skipExistingExactHelp: "Available when duplicate detection is Strict. When a photo with the exact same SHA-256 is detected, only an organizer record is created and the file is not copied again.",
    skipExistingExactLabel: "Do not save duplicates already in the gallery (recommended for long-term users)",
    sourceDir: "Source folder",
    renameFromExifHelp: "Renames only files whose current name already looks like a date/time. Target format: YYYYMMDD-HHMMSS.",
    renameFromExifLabel: "Rename date-formatted files from EXIF",
    runTimestampRepairTask: "Repair timestamps",
    syncModifiedTimeHelp: "Updates only the file modified time when it differs from EXIF capture time by more than 7 days.",
    syncModifiedTimeLabel: "Sync modified time from EXIF",
    taskConfig: "Task config",
    taskId: "Task ID",
    taskSummary: "Task summary",
    timestampRepairHelp: "Images use EXIF capture time. Videos are processed only when the video option is enabled and ffprobe finds embedded creation_time.",
    timestampRepairNotReady: "EXIF timestamp repair is visible on the page, but the backend task is not connected yet.",
    timestampRepairRoot: "Repair root",
    timestampRepairThreshold: "Minimum difference (days)",
    timestampRepairTitle: "EXIF timestamp repair"
  },
  viewer: {
    action: {
      copied: (path) => `Copied to ${path}`,
      copying: (path) => `Copying ${path} ...`,
      deleted: (path) => `Moved ${path} to the Recycle Bin.`,
      deleting: (path) => `Moving ${path} to the Recycle Bin ...`,
      openedFolder: (path) => `Opened folder: ${path}`,
      openingFolder: (path) => `Opening folder for ${path} ...`,
      openedEditor: (path) => `Opened in image editor: ${path}`,
      openingEditor: (path) => `Opening ${path} in image editor ...`
    },
    buttons: {
      backToGallery: "Back to Gallery",
      copySelected: "Copy",
      deleteSelected: "Delete",
      openFolder: "Open Folder",
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
