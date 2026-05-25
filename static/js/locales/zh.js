// SPDX-License-Identifier: MIT

export default {
  app: {
    intro: "轻量图片浏览与受控操作面板。",
    title: "ZeroTraceBrowser"
  },
  browser: {
    actions: {
      copied: path=>`已复制到 ${path}`,
      copiedMany: (count, target)=>`已复制 ${count} 张图片到 ${target}`,
      copying: path=>`正在复制 ${path} ...`,
      copyingMany: (current, total)=>`正在复制 ${current} / ${total} 张图片 ...`,
      deleted: path=>`已删除 ${path}。`,
      deletedMany: count=>`已将 ${count} 张图片移入回收区。`,
      deleting: path=>`正在删除 ${path} ...`,
      deletingMany: (current, total)=>`正在移入回收区 ${current} / ${total} 张图片 ...`
    },
    buttons: {
      clearSelection: "清空选择",
      clearDateFilter: "清除",
      copySelected: "复制",
      dateFilter: "日期",
      dateFilterActive: "日期筛选中",
      deleteSelected: "删除",
      invertSelection: "反选",
      importPhotosTool: "导入照片",
      mobileImportTool: "iPhone 导入",
      similarityTool: "相似检索",
      openDuplicatesResults: "重复结果",
      previewSelected: "预览",
      recycleTool: "回收区",
      settingsTool: "设置",
      showSidebar: "显示操作栏",
      tasksTool: "整理工具",
      toggleSidebar: "隐藏操作栏"
    },
    copy: {
      confirm: "确认复制",
      confirmManyMessage: (count, target) =>
            `确定复制已选择的 ${count} 张图片吗？\n文件将复制到：${target}`,
      confirmMessage: (path, target) =>
            `确定复制 ${path} 吗？\n文件将复制到：${target}`,
      confirmTitle: "复制图片",
      targetMissing: "请先设置复制目标目录，或保存默认复制目录。"
    },
    duplicates: {
      count: (count) => `重复组：${count}`,
      empty: "尚未发现可用的重复结果。",
      generatedAt: (time) => `生成时间：${time}`,
      noMatchInGroup: "当前重复组中的文件已不存在。",
      summaryReady: "结果已就绪，可进入专用页面查看。"
    },
    labels: {
      copyTargetShort: "复制目标",
      currentRoot: "当前目录",
      deleteMode: "删除方式",
      duplicates: "重复检测",
      endDate: "结束日期",
      imageCount: "图片数量",
      imageCountUpdatedAt: (time) => `统计更新时间：${time}`,
      info: "信息",
      search: "搜索",
      selection: "当前选择",
      startDate: "开始日期",
      status: "状态",
      tools: "工具"
    },
    placeholders: {
      date: "YYYY-MM-DD / YYYY/MM/DD",
      search: "按文件名过滤"
    },
    selection: {
      chooseImage: "请先选择图片",
      defaultCopyTarget: "使用默认目录",
      hintEmpty: "提示：您也可以先在图库中点击图片进行选择",
      hintMultiple: "提示：Shift 点击可范围选择，Ctrl+A 可选择当前筛选结果",
      hintSingle: "提示：可以先预览确认，再执行复制或删除",
      multipleDetail: (name, count) => `${name} 等 ${count} 张图片`,
      multipleTitle: (count) => `已选择 ${count} 张图片`,
      noneDetail: "请先选择图片后再操作",
      noneTitle: "尚未选择图片",
      recycleDeleteMode: "移入回收区",
      singleTitle: "已选择 1 张图片"
    },
    status: {
      loadedImages: (count) => `已加载 ${count} 张图片。`,
      loadedImagesProgress: (count, total) => `已加载 ${count} / ${total} 张图片...`,
      loadingImages: "正在加载图片列表...",
      noMatch: "没有匹配的图片。",
      ready: "准备就绪",
      rootMissing: "当前目录不存在，已显示空结果。"
    }
  },
  importPhotos: {
    configLoadFailed: "加载同步设置失败",
    connectedDevices: "已连接设备",
    connectionStatus: "连接状态",
    destinationRoot: "目标根目录",
    deviceFallbackLink: "打开设备备用导入",
    deviceLastSeen: (time) => `最后连接：${time}`,
    failed: "失败",
    imported: "已导入",
    importStatus: "导入状态",
    lastSeen: "最后连接",
    localAddress: "本地地址",
    logEmpty: "尚无手机同步活动。",
    notPaired: "未配对",
    noPairedDevices: "尚未配对手机。之后可在这里同时管理多台手机。",
    pageIntro: "手机配对一次后，即可在本地 Wi-Fi 下安静导入新照片。",
    pageTitle: "手机照片同步",
    paired: "已配对",
    pairedDeviceList: "已配对设备",
    pairedDevices: "已配对设备",
    pairingIntro: "打开手机 App 并扫描此二维码一次。配对后，手机在同一 Wi-Fi 下可以再次找到这台电脑。",
    pairingLoadFailed: "加载配对码失败",
    pairingReadyLog: (baseUrl, expiresAt) => `配对码已就绪：${baseUrl}\n有效期至：${expiresAt}`,
    pairingReady: "配对码就绪",
    pairingTitle: "配对手机",
    phoneSyncIdle: "手机同步空闲",
    phoneSyncRunning: "手机同步中",
    processed: "已处理",
    qrPayloadReady: "配对信息已就绪",
    qrPlaceholder: "二维码将显示在这里",
    qrReady: "请用手机 App 扫描",
    recentRuns: "最近同步",
    recentRunsEmpty: "尚无手机同步记录。",
    refreshPairing: "刷新配对二维码",
    scanToPair: "请用手机 App 扫描二维码完成配对。",
    skipped: "已跳过",
    status_idle: "空闲",
    status_ready: "就绪",
    status_syncing: "同步中",
    statusSummaryLine: (processed, imported, duplicate, deleted, failed) =>
      `手机同步：已处理 ${processed} / 新导入 ${imported} / 重复跳过 ${duplicate} / 本地删除跳过 ${deleted} / 失败 ${failed}。`,
    statusLoadFailed: "加载手机同步状态失败",
    summary: "同步概要",
    syncing: "同步中",
    syncTarget: "同步目标",
    connectedDeviceLine: (count) => `当前根目录已有 ${count} 个手机同步会话。`,
    waitingForPhone: "等待中"
  },
  mobileImport: {
    albumCount: "相册",
    backToGallery: "返回主画面",
    buildIndex: "建立 iPhone 图片库索引",
    alreadyImportedItem: (target, path) => `已导入过：${target} -> ${path}`,
    batchStarting: (batch, limit) => `开始处理第 ${batch} 批，最多 ${limit} 张照片...`,
    batchSummary: (batch, indexed, imported, skipped, already) =>
      `第 ${batch} 批完成。已索引：${indexed} / 新导入：${imported} / strict 重复跳过：${skipped} / 已导入过：${already}`,
    cancelIndex: "取消索引",
    cancelRequested: "已请求取消",
    cancelRequestedDetail: "已请求取消索引。当前批次会继续完成，之后停止处理后续批次。",
    cancelledAfterBatch: (batch) => `取消请求已生效：第 ${batch} 批完成后已停止继续索引。`,
    cancelledSummary: (indexed, imported, skipped, already) =>
      `索引已取消。已索引：${indexed} / 新导入：${imported} / strict 重复跳过：${skipped} / 已导入过：${already}`,
    confirmLeaveWhileIndexing: "iPhone 图片库索引仍在执行中。离开页面不会中断后台导入，但当前页面的实时输出将停止更新。仍要返回主画面吗？",
    copyAllPhotos: "拷贝 iPhone 全部照片",
    detectDevice: "检测 iPhone",
    detectFailed: "iPhone 检测失败",
    detecting: "正在检测 iPhone...",
    deviceDetected: "已检测到 iPhone",
    deviceName: "iPhone",
    deviceSection: "iPhone",
    deviceSummary: "iPhone 概要",
    indexLimit: "索引照片数量",
    indexed: (count) => `iPhone 图片库索引完成：${count} 张图片`,
    indexedImported: (count) => `iPhone 图片库索引完成：已导入 ${count} 张图片`,
    indexedSkipped: (count) => `iPhone 图片库索引完成：${count} 张图片已因 strict 重复跳过`,
    importedItem: (target, path) => `导入：${target} -> ${path}`,
    importSection: "导入",
    indexing: "正在建立 iPhone 图片库索引...",
    indexFailed: "建立 iPhone 图片库索引失败",
    lastIndexedAt: "最后索引",
    leavePage: "仍要离开",
    liveOutput: "iPhone 输出",
    logEmpty: "尚未开始 iPhone 导入操作。",
    mediaCount: "媒体",
    noMorePhotos: "没有更多可处理照片。",
    noDevice: "尚未加载 iPhone",
    noDeviceDetected: "没有检测到可用 iPhone",
    pageIntro: "索引和导入 iPhone 中的照片，所有源文件删除都保持显式、可控。",
    pageTitle: "iPhone 导入",
    pending: "等待接入",
    ready: "准备就绪",
    skippedItem: (target, path) => `跳过：${target} -> ${path}`,
    storage: "存储",
    totalSummary: (indexed, imported, skipped, already) =>
      `全部批次完成。已索引：${indexed} / 新导入：${imported} / strict 重复跳过：${skipped} / 已导入过：${already}`,
    storageNote: "iPhone 照片 Hash 会按设备标识缓存在本地。除非明确选择，否则原始照片仍保留在 iPhone 上。"
  },
  similarity: {
    backToGallery: "返回主画面",
    buildCache: "建立相似缓存",
    cacheBuilt: (processed, documentCount, featureCount, embeddingCount, skippedCached) =>
      `相似缓存已建立：新增 ${processed} 张 / 已缓存跳过 ${skippedCached} 张 / 文档 ${documentCount} / 特征点 ${featureCount} / 向量 ${embeddingCount}`,
    cacheBuilding: "正在建立相似缓存...",
    cacheFailed: "建立相似缓存失败",
    cacheLocalOnly: "相似缓存预热目前只支持当前本地 root 图库。",
    clear: "清除",
    confirmLeaveWhileBusy: "相似检索或删除操作仍在运行中。离开页面可能中断当前操作或停止状态显示。继续离开吗？",
    currentMethod: "方式",
    currentThreshold: "阈值",
    deleteSelected: "删除",
    endDate: "结束日期",
    limit: "结果数量",
    leavePage: "离开页面",
    clearSelection: "清除",
    invertSelection: "反选",
    matchCount: "匹配",
    method: "方式",
    methodDocument: "表单/文档布局",
    methodEmbedding: "轻量视觉向量",
    methodFeature: "ORB/AKAZE 特征点",
    methodPhash: "pHash",
    noMatches: "没有找到相似图片。请确认 Hash DB 或手机索引已重建，或适当调高阈值。",
    noResults: "暂无相似结果。",
    pageIntro: "从当前本地图片目录或已导入本地的 iPhone 索引照片中，基于一张明确选择的图片查找视觉相似照片。",
    pageTitle: "相似照片检索",
    queryImage: "查询图片",
    queryCardLabel: "查询图",
    queryCardMeta: (method, threshold) => `${method}:${threshold} / 来源图片`,
    queryMissing: "请输入当前目录下图片的相对路径，或 iPhone 照片的 album/filename。",
    queryPath: "查询图片相对路径",
    queryPathPlaceholder: "例如 2026/05/IMG_0001.JPG 或 100APPLE/IMG_0001.JPG",
    querySummary: "查询概要",
    ready: (count) => `已找到 ${count} 个相似结果。`,
    resultMeta: (distance, score, reason) => `距离 ${distance} / 分数 ${score} / ${reason}`,
    results: "结果",
    selectAll: "全选",
    scope: "范围",
    scopeNote: "可检索当前本地图片目录，也可检索已索引且已有本地文件对应的 iPhone 照片。",
    searchFailed: "相似检索失败",
    searchSection: "检索",
    searching: "正在检索相似图片...",
    searchSimilar: "查找相似照片",
    source: "检索来源",
    sourceAndroid: "已索引 Android 照片",
    sourceIphone: "已索引 iPhone 照片",
    sourceLocal: "当前本地 root 图库",
    sourceUnavailable: "该检索来源尚未接入。",
    startDate: "开始日期",
    summary: (count) => `结果：${count}`,
    threshold: "阈值"
  },
  delete: {
    confirm: {
      confirm: "移至回收区",
      messageMany: (count) =>
            `确认将已选择的 ${count} 张图片移至回收区吗？\n稍后可在回收区页面恢复。`,
      message: (path) =>
            `确认删除 ${path} ?\n文件会被移动到 deleted 目录。`,
      title: "移至回收区"
    }
  },
  dialog: {
    buttons: {
      cancel: "取消",
      confirm: "确认",
      ok: "确定"
    },
    title: {
      confirm: "确认操作",
      error: "操作失败",
      warning: "警告"
    }
  },
  duplicates: {
    backToGallery: "返回主画面",
    confirmLeaveWhileBusy: "当前批量处理仍在执行。现在离开此页面，可能中断当前操作或停止本页状态显示，是否继续？",
    bulkConfirm: "确认移入",
    bulkDeleted: (count) => `已将当前页 ${count} 个文件移入回收区`,
    bulkDeleting: (count) => `正在移入当前页 ${count} 个文件`,
    bulkDisabledForPhash: "pHash 相似检测需逐组人工确认，不能批量删除。",
    bulkMove100ToRecycle: "移入后续 100 组",
    bulkMoveToRecycle: "移入当前页重复文件",
    bulkStrict100Title: "将从当前页开始的 100 组 strict 重复文件移入回收区",
    bulkStrictTitle: (count) => `将当前页 ${count} 个 strict 重复文件移入回收区`,
    confirmBulkStrict100Delete: (count) =>
            `将把从当前页开始最多 100 组中的 ${count} 个 strict 重复文件移入回收区。只会处理 duplicate 文件，不会删除 kept 保留文件。是否继续？`,
    confirmBulkStrictDelete: (count) =>
            `将把当前页 ${count} 个 strict 重复文件移入回收区。只会处理 duplicate 文件，不会删除 kept 保留文件。是否继续？`,
    deleteSelected: "删除",
    deleted: (path) => `已删除 ${path}`,
    deleting: (path) => `正在删除 ${path} ...`,
    groupUnavailable: "该组文件已不存在，请点击【打开整理工具】按钮，在【MediaArchiveOrganizer 任务】画面，使用维护工具重新生成 Hash DB。",
    groups: "重复组",
    items: (count) => `${count} 张`,
    leavePage: "仍要离开",
    loading: "正在加载重复结果...",
    method: (reason) => `检测方式：${reason}`,
    methodPhash: "pHash 相似检测",
    methodStrict: "严格一致",
    nextPage: "下一页",
    noMethodResults: "当前检测方式下暂无重复结果。",
    noResults: "暂无重复结果。",
    noSelection: "请选中计划删除的图片。",
    noStrictDuplicatesToDelete: "当前页没有可批量移入的 strict 重复文件。",
    openTasksTool: "整理工具",
    openedResultRoot: "已在资源管理器打开结果目录。",
    pageInfo: (page, total) => `第 ${page} / ${total} 页`,
    pageIntro: "查看重复组，支持分页并在当前页面直接处理重复图片。",
    pageTitle: "重复结果",
    prevPage: "上一页",
    ready: "准备就绪。",
    refresh: "刷新",
    resultRoot: "结果目录",
    statusAvailable: "可用",
    statusDeleted: "已删除"
  },
  recycle: {
    archiveLogs: "归档",
    archivedLogs: (count, path) => `已归档 ${count} 条删除日志：${path}`,
    backToGallery: "返回主画面",
    clearRecycle: "清空当前页",
    clearRecycle100: "清空 100 个文件",
    clear100Title: "从当前页开始清空最多 100 个回收区文件",
    clearCurrentPageTitle: (count) => `清空当前页 ${count} 个回收区文件`,
    cleared: (count) => `已清空当前页 ${count} 个回收区文件。`,
    cleared100: (count) => `已清空 ${count} 个回收区文件。`,
    clearedAndArchived: (count, path) => `已清空 ${count} 个回收区文件，并归档删除日志：${path}`,
    clearedLogs: (count, target) => `已清理 ${count} 条${target}。`,
    confirmLeaveWhileBusy: "当前回收区处理仍在执行。现在离开此页面，可能中断当前操作或停止本页状态显示，是否继续？",
    confirmArchiveLogs: {
      confirm: "归档日志",
      message: "确认将当前 delete_log.csv 备份为带时间戳的文件，并清空当前日志显示吗？",
      title: "归档删除日志"
    },
    confirmClear: {
      confirm: "清空当前页",
      message: (count) => `确认清空当前页 ${count} 个回收区文件吗？此操作无法撤销。`,
      messagePermanent: (count) => `确认清空当前页 ${count} 个回收区文件吗？当前系统下文件将被彻底删除，无法恢复。`,
      messageSystemRecycle: (count) => `确认将当前页 ${count} 个回收区文件放入 Windows 系统回收站吗？`,
      title: "清空当前页"
    },
    confirmClear100: {
      messagePermanent: (count) => `确认从当前页开始清空 ${count} 个回收区文件吗？当前系统下文件将被彻底删除，无法恢复。`,
      messageSystemRecycle: (count) => `确认从当前页开始将 ${count} 个回收区文件放入 Windows 系统回收站吗？`
    },
    confirmClearLogs: {
      confirm: "清理日志",
      message: (target) => `确认清理「${target}」吗？\n这不会影响当前回收区文件。`,
      title: "清理日志"
    },
    confirmPurge: {
      confirm: "彻底删除",
      message: (path) =>
            `确认彻底删除 ${path} 吗？\n该文件将从 deleted 中永久移除，且无法恢复。`,
      messagePermanent: (path) =>
            `确认删除 ${path} 吗？当前系统下该文件将被彻底删除，无法恢复。`,
      messageSystemRecycle: (path) =>
            `确认删除 ${path} 吗？文件将被放入 Windows 系统回收站。`,
      title: "确认彻底删除"
    },
    confirmRestore: {
      confirm: "恢复",
      message: (path) => `确认恢复 ${path} 吗？\n文件将恢复到原始路径。`,
      title: "确认恢复"
    },
    deleteLogs: "删除日志",
    deletedAt: "删除时间",
    deletedFile: "回收文件",
    itemCount: (count) => `${count} 项`,
    itemStatus: "状态",
    leavePage: "仍要离开",
    loading: "正在加载回收区...",
    logActions: {
      deleted: "删除",
      purged: "彻底删除",
      restored: "恢复"
    },
    logClearTargets: {
      purged: "已彻底删除记录",
      restored: "已恢复记录",
      restoredAndPurged: "已恢复 + 已彻底删除记录"
    },
    logEntries: "日志条数",
    logFilters: {
      all: "全部",
      deleted: "已删除",
      purged: "已彻底删除",
      restored: "已恢复"
    },
    logSummary: (shown, filtered, total) => `显示 ${shown} / ${filtered} 条，共 ${total} 条`,
    logTable: {
      action: "动作",
      file: "文件",
      originalPath: "原路径",
      recyclePath: "回收路径",
      time: "时间"
    },
    noFilteredLogs: "当前筛选条件下没有日志。",
    noLogs: "暂无删除日志。",
    noLogsToArchive: "暂无可归档的删除日志。",
    noRecycleItems: "回收区为空。",
    nextPage: "下一页",
    originalExists: "原路径已存在，需人工处理",
    pageInfo: (page, total) => `第 ${page} / ${total} 页`,
    pageIntro: "查看安全删除回收区，支持恢复、清空前确认和删除日志查看。",
    pageTitle: "回收区管理",
    pending: "待处理",
    prevPage: "上一页",
    purged: (path) => `已彻底删除 ${path}`,
    purgedItem: "已彻底删除",
    ready: "准备就绪。",
    recycleItems: "回收区项目",
    refresh: "刷新",
    restoreButton: "恢复",
    restoreTarget: "原路径",
    restoreUnavailable: "缺少原始路径，无法恢复",
    restored: (path) => `已恢复到 ${path}`,
    restoredItem: "已恢复",
    systemRecycleUnsupported: "移动到系统回收站仅支持 Windows。"
  },
  settings: {
    advanced: {
      placeholder: "这里可继续加入缩略图大小、默认排序方式、Viewer 默认行为等全局设置。"
    },
    buttons: {
      addRoot: "追加",
      backToGallery: "返回主画面",
      clearCopyTarget: "清空",
      removeRoot: "移除",
      saveCopyTarget: "保存",
      saveDisplayStyle: "保存",
      saveLanguage: "保存",
      switchRoot: "设为当前"
    },
    confirmCleanupRoot: {
      cancel: "仅移除目录",
      confirm: "移除并清理",
      message: "是否同时清除该目录的相关数据及历史？包括 hash_db、duplicates、图片摘要、Timeline index、delete_log，以及该目录在本地回收区中的副本。原目录中的图片不会被删除。",
      title: "清理目录历史"
    },
    confirmRemoveRoot: {
      confirm: "移除",
      message: "确认从加载目录中移除该目录吗？",
      title: "移除目录"
    },
    intro: "管理全局目录、默认复制目标与界面语言。",
    displayStyles: {
      default: "默认",
      harbor: "港湾",
      multiDark: "多彩深色",
      multiLight: "多彩浅色"
    },
    labels: {
      activeRoot: "当前目录",
      copyTarget: "默认复制目标",
      copyTargetInput: "默认复制目录",
      displayStyle: "显示风格",
      displayStyleSelect: "显示风格",
      language: "界面语言",
      languageSelect: "界面语言",
      newRootInput: "追加目录",
      rootSelect: "已加载目录"
    },
    placeholders: {
      copyTarget: "未设置时由后端决定",
      newRoot: "D:\\Images"
    },
    sections: {
      advanced: "高级设置",
      copyTarget: "复制目标目录",
      displayStyle: "显示风格",
      language: "语言",
      overview: "当前概览",
      roots: "加载目录",
      status: "状态"
    },
    status: {
      copyTargetCleared: "默认复制目录已清空",
      copyTargetSaved: "默认复制目录已保存",
      displayStyleSaved: "显示风格已保存",
      invalidRoot: "请输入要追加的目录",
      languageSaved: "语言设置已保存",
      loadFailed: "加载设置失败",
      ready: "准备就绪",
      requestFailed: "请求失败",
      rootAdded: "目录已追加并切换为当前目录",
      rootNotRegistered: "该目录尚未登记",
      rootRemoved: "目录已移除",
      rootRemovedWithCleanup: "目录已移除，并已清理相关数据及历史",
      rootRequired: "至少需要保留一个加载目录",
      rootSwitched: "当前目录已切换",
      unsupportedDisplayStyle: "不支持该显示风格",
      unsupportedLanguage: "不支持该语言"
    },
    title: "设置"
  },
  system: {
    labels: {
      finishedAt: "结束时间",
      generatedAt: "生成时间",
      startedAt: "开始时间",
      status: "状态",
      summary: "摘要"
    }
  },
  tasks: {
    backToGallery: "返回主画面",
    confirmLeaveWhileRunning: "当前处理仍在执行。现在返回主画面可能中断当前处理或停止本页监控，是否继续？",
    confirmRunRebuild: "确认根据当前目录重新生成 Hash DB 和重复结果吗？",
    confirmRunTimestampRepair: "确认对该目录执行 EXIF 时间戳修复吗？只处理带 EXIF 拍摄时间的文件。",
    confirmRunTask: "确认开始整理，并更新 Hash DB 与重复结果吗？",
    csvPath: "CSV 路径",
    destDir: "目标目录",
    duplicateDetection: "重复检测",
    errors: {
      taskAlreadyRunning: "已有整理或重建任务正在运行。请等待当前任务完成后再试。"
    },
    hashDbPath: "Hash DB 路径",
    hashMethod: "Hash 类型",
    hideHashMaintenance: "隐藏重复结果维护",
    includeVideosHelp: "使用 ffprobe 读取视频内嵌 creation_time。没有内嵌创建时间的视频会直接跳过。",
    includeVideosLabel: "包含带内嵌创建时间的视频",
    idle: "未开始",
    language: "语言",
    leavePage: "仍要返回",
    liveOutput: "实时输出",
    logPath: "日志路径",
    maintenanceTools: "维护工具",
    mode: "模式",
    noDirectoryToOpen: "没有可打开的目录。",
    noTaskOutput: "暂无任务输出。",
    noTaskStarted: "尚未开始任务。",
    stillRunning: "任务仍在运行中...",
    openDirectory: "打开",
    openedDirectory: (path) => `已打开目录：${path}`,
    outputs: "输出文件",
    pageIntro: "运行整理任务，并将结果写入根目录数据库。",
    pageTitle: "MediaArchiveOrganizer 任务",
    phashThreshold: "pHash 阈值",
    rebuildRoot: "重建目录",
    runRebuildTask: "重建结果",
    runTask: "开始整理",
    showHashMaintenance: "显示重复结果维护",
    skipExistingExactHelp: "重复检测选择 Strict 时可用。检测到 SHA-256 完全相同的照片时，仅建立整理记录，不再重复复制文件。",
    skipExistingExactLabel: "已存在于图库时不重复保存（推荐长期用户开启）",
    sourceDir: "源目录",
    renameFromExifHelp: "仅重命名当前文件名已经像日期时间格式的文件。目标格式：YYYYMMDD-HHMMSS。",
    renameFromExifLabel: "按 EXIF 重命名日期格式文件",
    runTimestampRepairTask: "修复时间戳",
    syncModifiedTimeHelp: "仅在文件修改时间与 EXIF 拍摄时间相差超过 7 天时，更新 modified time。",
    syncModifiedTimeLabel: "按 EXIF 同步修改时间",
    taskConfig: "任务配置",
    taskId: "任务 ID",
    taskSummary: "任务摘要",
    timestampRepairHelp: "图片使用 EXIF 拍摄时间。视频只有在开启视频选项且 ffprobe 读到内嵌 creation_time 时才处理。",
    timestampRepairNotReady: "EXIF 时间戳修复入口已显示，但后端任务尚未接入。",
    timestampRepairRoot: "修复目录",
    timestampRepairThreshold: "最小差距（天）",
    timestampRepairTitle: "EXIF 时间戳修复"
  },
  viewer: {
    action: {
      copied: (path) => `已复制到 ${path}`,
      copying: (path) => `正在复制 ${path} ...`,
      deleted: (path) => `已删除 ${path}。`,
      deleting: (path) => `正在删除 ${path} ...`,
      openedFolder: (path) => `已打开所在文件夹：${path}`,
      openingFolder: (path) => `正在打开 ${path} 所在文件夹 ...`,
      openedEditor: (path) => `已用图片编辑器打开：${path}`,
      openingEditor: (path) => `正在用图片编辑器打开 ${path} ...`
    },
    buttons: {
      backToGallery: "返回图库",
      copySelected: "复制",
      deleteSelected: "删除",
      openFolder: "打开所在文件夹",
      openEditor: "用画图编辑",
      rotateLeft: "向左旋转",
      rotateRight: "向右旋转",
      showSidebar: "显示信息栏",
      toggleSidebar: "隐藏信息栏"
    },
    display: {
      index: (i, t) => `${i} / ${t}`,
      zoom: (z) => `缩放：${z}%`
    },
    exif: {
      empty: "选择图片后显示拍摄信息。",
      failed: "EXIF 读取失败。",
      loading: "正在读取 EXIF 信息...",
      unavailable: "这张图片没有可用 EXIF 信息。"
    },
    hint: "提示：可使用左右切换图片，删除操作将移入回收区。",
    labels: {
      actions: "操作",
      exifAperture: "光圈",
      exifCamera: "机身",
      exifDatetime: "拍摄时间",
      exifDimensions: "尺寸",
      exifFocalLength: "焦距",
      exifGpsAltitude: "海拔",
      exifGpsCoordinates: "地理位置",
      exifInfo: "EXIF 信息",
      exifIso: "ISO",
      exifLens: "镜头",
      exifShutter: "快门",
      info: "图片信息",
      status: "状态"
    },
    status: {
      ready: "准备就绪"
    }
  }
};
