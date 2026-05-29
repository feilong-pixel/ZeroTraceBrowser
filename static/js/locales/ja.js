// SPDX-License-Identifier: MIT

export default {
  app: {
    intro: "画像を軽快に閲覧し、安全に操作できるツールです",
    title: "ZeroTraceBrowser"
  },
  browser: {
    actions: {
      copied: path=>`${path} にコピーしました`,
      copiedMany: (count, target)=>`${count} 件を ${target} にコピーしました`,
      copying: path=>`${path} をコピー中 ...`,
      copyingMany: (current, total)=>`${current} / ${total} 件をコピー中 ...`,
      deleted: path=>`${path} をごみ箱へ移動しました`,
      deletedMany: count=>`${count} 件をごみ箱へ移動しました`,
      deleting: path=>`${path} をごみ箱へ移動中 ...`,
      deletingMany: (current, total)=>`${current} / ${total} 件をごみ箱へ移動中 ...`
    },
    buttons: {
      clearSelection: "選択解除",
      clearDateFilter: "クリア",
      copySelected: "コピー",
      dateFilter: "日付",
      dateFilterActive: "日付適用中",
      deleteSelected: "削除",
      invertSelection: "選択反転",
      importPhotosTool: "写真取り込み",
      mobileImportTool: "iPhone 取り込み",
      similarityTool: "類似検索",
      openDuplicatesResults: "重複一覧",
      previewSelected: "プレビュー",
      recycleTool: "ごみ箱",
      settingsTool: "設定",
      showSidebar: "パネル表示",
      tasksTool: "整理ツール",
      toggleSidebar: "パネル非表示"
    },
    copy: {
      confirm: "コピー",
      confirmManyMessage: (count, target) =>
            `選択した ${count} 件の画像をコピーしますか？\nコピー先：${target}`,
      confirmMessage: (path, target) =>
            `${path} をコピーしますか？\nコピー先：${target}`,
      confirmTitle: "画像コピー",
      targetMissing: "コピー先フォルダを設定してください"
    },
    duplicates: {
      count: (count) => `グループ数：${count}`,
      empty: "重複データがありません",
      generatedAt: (time) => `生成日時：${time}`,
      noMatchInGroup: "このグループに該当ファイルはありません",
      summaryReady: "結果を確認できます"
    },
    labels: {
      copyTargetShort: "コピー先",
      currentRoot: "現在のフォルダ",
      deleteMode: "削除方法",
      duplicates: "重複検出",
      endDate: "終了日",
      imageCount: "画像数",
      imageCountUpdatedAt: (time) => `件数更新時刻：${time}`,
      info: "情報",
      search: "検索",
      selection: "選択中",
      startDate: "開始日",
      status: "状態",
      tools: "ツール"
    },
    placeholders: {
      date: "YYYY-MM-DD / YYYY/MM/DD",
      search: "ファイル名で絞り込み"
    },
    selection: {
      chooseImage: "画像を選択してください",
      defaultCopyTarget: "デフォルトのコピー先を使用",
      hintEmpty: "ヒント：画像をクリックして選択できます",
      hintMultiple: "ヒント：Shiftクリックで範囲選択、Ctrl+Aで現在の結果を選択できます",
      hintSingle: "ヒント：プレビュー後に操作できます",
      multipleDetail: (name, count) => `${name} ほか ${count - 1} 件`,
      multipleTitle: (count) => `${count} 件選択中`,
      noneDetail: "操作するには画像を選択してください",
      noneTitle: "未選択",
      recycleDeleteMode: "ごみ箱へ移動",
      singleTitle: "1件選択中"
    },
    status: {
      loadedImages: (count) => `${count}枚の画像を読み込みました`,
      loadedImagesProgress: (count, total) => `${count} / ${total} 枚の画像を読み込み中...`,
      loadingImages: "画像を読み込み中...",
      noMatch: "一致する画像がありません",
      ready: "準備完了。",
      rootMissing: "フォルダが存在しないため表示できません"
    }
  },
  importPhotos: {
    configLoadFailed: "同期設定の読み込みに失敗しました",
    connectedDevices: "接続中の端末",
    connectionStatus: "接続状態",
    destinationRoot: "取り込み先ルート",
    deviceFallbackLink: "デバイス代替を開く",
    deviceLastSeen: (time) => `最終接続：${time}`,
    failed: "失敗",
    imported: "取り込み済み",
    importStatus: "取り込み状態",
    lastSeen: "最終接続",
    localAddress: "ローカルアドレス",
    logEmpty: "スマホ同期の活動はまだありません。",
    notPaired: "未ペアリング",
    noPairedDevices: "ペアリング済みのスマホはまだありません。今後ここで複数台を管理できます。",
    pageIntro: "一度スマホをペアリングすると、同じ Wi-Fi 上で新しい写真を静かに取り込めます。",
    pageTitle: "スマホ写真同期",
    paired: "ペアリング済み",
    pairedDeviceList: "ペアリング済み端末",
    pairedDevices: "ペアリング済み端末",
    pairingIntro: "スマホアプリを開き、このコードを一度スキャンしてください。ペアリング後は、同じ Wi-Fi 上でこのコンピューターを再検出できます。",
    pairingLoadFailed: "ペアリングコードの読み込みに失敗しました",
    pairingReadyLog: (baseUrl, expiresAt) => `ペアリングコードの準備ができました：${baseUrl}\n有効期限：${expiresAt}`,
    pairingReady: "ペアリング準備完了",
    pairingTitle: "スマホをペアリング",
    phoneSyncIdle: "スマホ同期は待機中",
    phoneSyncRunning: "スマホ同期中",
    processed: "処理済み",
    qrPayloadReady: "ペアリング情報の準備ができました",
    qrPlaceholder: "QR コードはここに表示されます",
    qrReady: "スマホアプリでスキャン",
    recentRuns: "最近の同期",
    recentRunsEmpty: "スマホ同期履歴はまだありません。",
    refreshPairing: "ペアリングコードを更新",
    scanToPair: "スマホアプリで QR コードをスキャンしてペアリングしてください。",
    skipped: "スキップ",
    status_idle: "待機中",
    status_ready: "準備完了",
    status_syncing: "同期中",
    statusSummaryLine: (processed, imported, duplicate, deleted, failed) =>
      `スマホ同期：処理済み ${processed} / 新規取り込み ${imported} / 重複スキップ ${duplicate} / ローカル削除スキップ ${deleted} / 失敗 ${failed}。`,
    statusLoadFailed: "スマホ同期状態の読み込みに失敗しました",
    summary: "同期概要",
    syncing: "同期中",
    syncTarget: "同期先",
    connectedDeviceLine: (count) => `このルートに ${count} 件のスマホ同期セッションがあります。`,
    waitingForPhone: "待機中"
  },
  mobileImport: {
    albumCount: "アルバム",
    backToGallery: "メイン画面へ戻る",
    buildIndex: "iPhone 索引を作成",
    alreadyImportedItem: (target, path) => `取り込み済み：${target} -> ${path}`,
    batchStarting: (batch, limit) => `第 ${batch} バッチを開始します。最大 ${limit} 件...`,
    batchSummary: (batch, indexed, imported, skipped, already) =>
      `第 ${batch} バッチ完了。索引済み：${indexed} / 新規取り込み：${imported} / strict 重複スキップ：${skipped} / 取り込み済み：${already}`,
    cancelIndex: "索引作成をキャンセル",
    cancelRequested: "キャンセルを要求しました",
    cancelRequestedDetail: "索引作成のキャンセルを要求しました。現在のバッチを完了してから、以降のバッチを停止します。",
    cancelledAfterBatch: (batch) => `キャンセルが反映されました：第 ${batch} バッチ完了後に索引作成を停止しました。`,
    cancelledSummary: (indexed, imported, skipped, already) =>
      `索引作成をキャンセルしました。索引済み：${indexed} / 新規取り込み：${imported} / strict 重複スキップ：${skipped} / 取り込み済み：${already}`,
    confirmLeaveWhileIndexing: "iPhone の索引作成はまだ実行中です。このページを離れてもバックエンドの取り込みは停止しませんが、ここでのリアルタイム出力は更新されなくなります。このまま離れますか？",
    copyAllPhotos: "iPhone 内のすべての写真をコピー",
    detectDevice: "iPhone 検出",
    detectFailed: "iPhone 検出に失敗しました",
    detecting: "iPhone を検出中...",
    deviceDetected: "iPhone を検出しました",
    deviceName: "iPhone",
    deviceSection: "iPhone",
    deviceSummary: "iPhone 概要",
    indexLimit: "索引化する写真数",
    indexed: (count) => `iPhone の写真ライブラリ索引が完了しました：${count} 件`,
    indexedImported: (count) => `iPhone の写真ライブラリ索引が完了しました：${count} 件を取り込みました`,
    indexedSkipped: (count) => `iPhone の写真ライブラリ索引が完了しました：strict 重複のため ${count} 件をスキップしました`,
    importedItem: (target, path) => `取り込み：${target} -> ${path}`,
    importSection: "取り込み",
    indexing: "iPhone の写真ライブラリ索引を作成中...",
    indexFailed: "iPhone の写真ライブラリ索引作成に失敗しました",
    lastIndexedAt: "最終索引",
    leavePage: "このまま離れる",
    liveOutput: "iPhone 出力",
    logEmpty: "iPhone 取り込み操作はまだ開始されていません。",
    mediaCount: "メディア",
    noMorePhotos: "処理できる写真はもうありません。",
    noDevice: "iPhone 未読み込み",
    noDeviceDetected: "利用可能な iPhone が見つかりません",
    pageIntro: "iPhone 内の写真を索引化・取り込みし、元ファイルの削除は明示的な操作に限定します。",
    pageTitle: "iPhone 取り込み",
    pending: "接続待ち",
    ready: "準備完了",
    skippedItem: (target, path) => `スキップ：${target} -> ${path}`,
    storage: "保存",
    totalSummary: (indexed, imported, skipped, already) =>
      `すべてのバッチが完了しました。索引済み：${indexed} / 新規取り込み：${imported} / strict 重複スキップ：${skipped} / 取り込み済み：${already}`,
    storageNote: "iPhone 写真の Hash はデバイスIDごとにローカルへ保存します。明示的に選択しない限り、元の写真は iPhone 上に残します。"
  },
  similarity: {
    backToGallery: "メイン画面へ戻る",
    buildCache: "類似キャッシュ作成",
    cacheBuilt: (processed, documentCount, featureCount, embeddingCount, skippedCached) =>
      `類似キャッシュを作成しました：新規 ${processed} 件 / キャッシュ済みスキップ ${skippedCached} 件 / 文書 ${documentCount} / 特徴点 ${featureCount} / ベクトル ${embeddingCount}`,
    cacheBuilding: "類似キャッシュを作成中...",
    cacheFailed: "類似キャッシュの作成に失敗しました",
    cacheLocalOnly: "類似キャッシュの事前作成は現在のローカル root のみ対応しています。",
    clear: "クリア",
    confirmLeaveWhileBusy: "類似検索または削除操作がまだ実行中です。このページを離れると、現在の操作が中断されるか、状態表示が停止する可能性があります。続行しますか？",
    currentMethod: "方式",
    currentThreshold: "しきい値",
    deleteSelected: "削除",
    endDate: "終了日",
    limit: "結果数",
    leavePage: "このまま離れる",
    clearSelection: "クリア",
    invertSelection: "選択反転",
    matchCount: "一致",
    method: "方式",
    methodDocument: "帳票/文書レイアウト",
    methodEmbedding: "軽量視覚ベクトル",
    methodFeature: "ORB/AKAZE 特徴点",
    methodPhash: "pHash",
    noMatches: "類似画像は見つかりませんでした。Hash DB またはスマホ索引を再構築するか、必要に応じてしきい値を上げてください。",
    noResults: "類似結果はまだありません。",
    pageIntro: "現在のローカル画像フォルダ、またはローカルファイルがある索引済み iPhone 写真から類似写真を検索します。",
    pageTitle: "類似写真検索",
    queryImage: "検索画像",
    queryCardLabel: "検索画像",
    queryCardMeta: (method, threshold) => `${method}:${threshold} / 元画像`,
    queryMissing: "現在の画像フォルダ内の相対パス、または iPhone の album/filename を入力してください。",
    queryPath: "検索画像の相対パス",
    queryPathPlaceholder: "例 2026/05/IMG_0001.JPG または 100APPLE/IMG_0001.JPG",
    querySummary: "検索概要",
    ready: (count) => `${count} 件の類似結果が見つかりました。`,
    resultMeta: (distance, score, reason) => `距離 ${distance} / スコア ${score} / ${reason}`,
    results: "結果",
    selectAll: "全選択",
    scope: "範囲",
    scopeNote: "現在のローカル画像フォルダ、またはローカルファイルがある索引済み iPhone 写真を検索できます。",
    searchFailed: "類似検索に失敗しました",
    searchSection: "検索",
    searching: "類似画像を検索中...",
    searchSimilar: "類似写真を検索",
    source: "検索元",
    sourceAndroid: "索引済み Android 写真",
    sourceIphone: "索引済み iPhone 写真",
    sourceLocal: "現在のローカル root",
    sourceUnavailable: "この検索元はまだ接続されていません。",
    startDate: "開始日",
    summary: (count) => `結果：${count}`,
    threshold: "しきい値"
  },
  delete: {
    confirm: {
      confirm: "ごみ箱へ移動",
      messageMany: (count) =>
            `選択した ${count} 件の画像をごみ箱へ移動しますか？\nあとでごみ箱ページから復元できます。`,
      message: (path) =>
            `${path} を削除しますか？\nごみ箱へ移動します。`,
      title: "ごみ箱へ移動確認"
    }
  },
  dialog: {
    buttons: {
      cancel: "キャンセル",
      confirm: "OK",
      ok: "OK"
    },
    title: {
      confirm: "確認",
      error: "エラー",
      warning: "警告"
    }
  },
  duplicates: {
    backToGallery: "ギャラリーへ戻る",
    confirmLeaveWhileBusy: "一括処理が実行中です。このページを離れると、処理が中断されるか、進行状況を確認できなくなる可能性があります。ページを離れますか？",
    bulkConfirm: "ごみ箱へ移動",
    bulkDeleted: (count) => `${count} 件をごみ箱へ移動しました。`,
    bulkDeleting: (count) => `${count} 件をごみ箱へ移動しています...`,
    bulkDisabledForPhash: "pHash の一括移動はこのページ内のみ対応しています。100 グループ移動は完全一致のみ利用できます。",
    bulkMove100ToRecycle: "100 グループを移動",
    bulkMoveToRecycle: "このページを移動",
    bulkCurrentPageTitle: (count, method) => `このページの ${method} 重複ファイル ${count} 件をごみ箱へ移動します`,
    bulkStrict100Title: "このページから最大 100 グループ分の完全一致ファイルをごみ箱へ移動します",
    bulkStrictTitle: (count) => `このページの完全一致ファイル ${count} 件をごみ箱へ移動します`,
    confirmBulkCurrentPageDelete: (count, method) =>
            `このページの ${method} 重複ファイル ${count} 件をごみ箱へ移動します。各グループで 1 件を残し、IMG で始まる端末の元画像を優先して残します。続行しますか？`,
    confirmBulkStrict100Delete: (count) =>
            `このページから最大 100 グループ分、完全一致の重複ファイル ${count} 件をごみ箱へ移動します。各グループで 1 件を残し、IMG で始まる端末の元画像を優先して残します。続行しますか？`,
    confirmBulkStrictDelete: (count) =>
            `このページの完全一致ファイル ${count} 件をごみ箱へ移動します。各グループで 1 件を残し、IMG で始まる端末の元画像を優先して残します。続行しますか？`,
    deleteSelected: "選択したファイルを移動",
    deleted: (path) => `${path} をごみ箱へ移動しました。`,
    deleting: (path) => `${path} をごみ箱へ移動しています...`,
    groupUnavailable: "このグループのファイルは見つかりません。",
    groups: "残りの重複グループ数",
    items: (count) => `${count} 件`,
    leavePage: "ページを離れる",
    loading: "重複結果を読み込んでいます...",
    method: (reason) => `検出方式：${reason}`,
    methodPhash: "類似画像",
    methodStrict: "完全一致",
    nextPage: "次のページ",
    noMethodResults: "この検出方式の重複結果はありません。",
    noResults: "重複結果はありません。",
    noSelection: "ごみ箱へ移動する画像を選択してください。",
    noDuplicatesToDelete: "このページには一括移動できる重複ファイルがありません。",
    noStrictDuplicatesToDelete: "このページには一括移動できる完全一致ファイルがありません。",
    openTasksTool: "整理ツール",
    openedResultRoot: "結果フォルダを開きました。",
    pageInfo: (page, total) => `${page} / ${total} ページ`,
    pageIntro: "検出された重複グループを確認し、不要なファイルだけをごみ箱へ移動できます。",
    pageTitle: "重複結果",
    prevPage: "前のページ",
    ready: "表示できます。",
    refresh: "再読み込み",
    resultRoot: "結果フォルダ",
    statusAvailable: "有効",
    statusDeleted: "移動済み"
  },
  recycle: {
    archiveLogs: "ログを保管",
    archivedLogs: (count, path) => `${count} 件の削除ログを保管しました：${path}`,
    backToGallery: "ギャラリーへ戻る",
    clearRecycle: "このページを削除",
    clearRecycle100: "100 件を削除",
    clear100Title: "このページから最大 100 件のごみ箱内ファイルを削除します",
    clearCurrentPageTitle: (count) => `このページの ${count} 件を削除します`,
    cleared: (count) => `${count} 件を削除しました。`,
    cleared100: (count) => `${count} 件のごみ箱内ファイルを削除しました。`,
    clearedAndArchived: (count, path) => `${count} 件を削除し、削除ログを保管しました：${path}`,
    clearedLogs: (count, target) => `${target}を ${count} 件削除しました。`,
    confirmLeaveWhileBusy: "ごみ箱の処理が実行中です。このページを離れると、処理が中断されるか、進行状況を確認できなくなる可能性があります。ページを離れますか？",
    confirmArchiveLogs: {
      confirm: "ログを保管",
      message: "現在の削除ログをタイムスタンプ付きで保管し、表示中のログ一覧を空にしますか？",
      title: "削除ログの保管"
    },
    confirmClear: {
      confirm: "削除",
      message: (count) => `このページの ${count} 件を削除しますか？`,
      messagePermanent: (count) => `このページの ${count} 件を完全に削除します。この環境では復元できません。続行しますか？`,
      messageSystemRecycle: (count) => `このページの ${count} 件を削除します。Windows ではシステムのごみ箱へ移動されます。続行しますか？`,
      title: "ごみ箱内ファイルの削除"
    },
    confirmClear100: {
      messagePermanent: (count) => `このページから ${count} 件のごみ箱内ファイルを完全に削除します。この環境では復元できません。続行しますか？`,
      messageSystemRecycle: (count) => `このページから ${count} 件のごみ箱内ファイルを削除します。Windows ではシステムのごみ箱へ移動されます。続行しますか？`
    },
    confirmClearLogs: {
      confirm: "ログを削除",
      message: (target) =>
            `${target}を削除しますか？\nごみ箱内のファイルには影響しません。`,
      title: "ログの削除"
    },
    confirmPurge: {
      confirm: "完全削除",
      message: (path) =>
            `${path} を完全に削除しますか？\nこのファイルはアプリのごみ箱から削除され、復元できません。`,
      messagePermanent: (path) =>
            `${path} を完全に削除します。この環境では復元できません。続行しますか？`,
      messageSystemRecycle: (path) =>
            `${path} を Windows のごみ箱へ移動しますか？`,
      title: "完全削除の確認"
    },
    confirmRestore: {
      confirm: "復元",
      message: (path) =>
            `${path} を元の場所へ復元しますか？`,
      title: "ファイルの復元"
    },
    deleteLogs: "削除ログ",
    deletedAt: "削除日時",
    deletedFile: "ファイル",
    itemCount: (count) => `${count} 件`,
    itemStatus: "状態",
    leavePage: "ページを離れる",
    loading: "ごみ箱を読み込んでいます...",
    logActions: {
      deleted: "削除",
      purged: "完全削除",
      restored: "復元"
    },
    logClearTargets: {
      purged: "完全削除済みのログ",
      restored: "復元済みのログ",
      restoredAndPurged: "復元済み・完全削除済みのログ"
    },
    logEntries: "ログ",
    logFilters: {
      all: "すべて",
      deleted: "削除済み",
      purged: "完全削除済み",
      restored: "復元済み"
    },
    logSummary: (shown, filtered, total) => `${shown} / ${filtered} 件を表示（全 ${total} 件）`,
    logTable: {
      action: "操作",
      file: "ファイル",
      originalPath: "元のパス",
      recyclePath: "ごみ箱内のパス",
      time: "時刻"
    },
    noFilteredLogs: "この条件に一致するログはありません。",
    noLogs: "削除ログはまだありません。",
    noLogsToArchive: "アーカイブする削除ログはありません。",
    noRecycleItems: "ごみ箱は空です。",
    nextPage: "次のページ",
    originalExists: "元の場所に同名のファイルがあります",
    pageInfo: (page, total) => `${page} / ${total} ページ`,
    pageIntro: "安全削除したファイルを確認し、必要に応じて復元または削除できます。Windows では削除時にシステムのごみ箱へ移動します。",
    pageTitle: "ごみ箱",
    pending: "未処理",
    prevPage: "前のページ",
    purged: (path) => `${path} を削除しました。`,
    purgedItem: "完全削除済み",
    ready: "表示できます。",
    recycleItems: "ごみ箱内のファイル",
    refresh: "再読み込み",
    restoreButton: "復元",
    restoreTarget: "復元先",
    restoreUnavailable: "復元先の情報がないため復元できません",
    restored: (path) => `${path} を復元しました。`,
    restoredItem: "復元済み",
    systemRecycleUnsupported: "Windows 以外では、システムのごみ箱へ移動できません。"
  },
  settings: {
    advanced: {
      placeholder: "サムネイルサイズ、既定の並び順、Viewer の既定動作などを後で追加できます。"
    },
    buttons: {
      addRoot: "追加",
      backToGallery: "メイン画面へ戻る",
      clearCopyTarget: "クリア",
      removeRoot: "削除",
      saveCopyTarget: "保存",
      saveDisplayStyle: "保存",
      saveLanguage: "保存",
      switchRoot: "適用"
    },
    confirmCleanupRoot: {
      cancel: "フォルダのみ削除",
      confirm: "削除してクリア",
      message: "このフォルダに関連する生成データと履歴も削除しますか？hash_db、duplicates、画像サマリー、Timeline index、delete_log、このフォルダのローカルごみ箱コピーが対象です。元フォルダ内の画像は削除されません。",
      title: "フォルダ履歴のクリア"
    },
    confirmRemoveRoot: {
      confirm: "削除",
      message: "このフォルダを読み込みフォルダ一覧から削除しますか？",
      title: "フォルダ削除"
    },
    intro: "フォルダや表示設定を管理します",
    displayStyles: {
      default: "標準",
      harbor: "Harbor",
      multiDark: "Multi ダーク",
      multiLight: "Multi ライト"
    },
    labels: {
      activeRoot: "現在のフォルダ",
      copyTarget: "コピー先",
      copyTargetInput: "コピー先",
      displayStyle: "表示スタイル",
      displayStyleSelect: "表示スタイル",
      language: "表示言語",
      languageSelect: "表示言語",
      newRootInput: "フォルダを追加",
      rootSelect: "読み込み済みフォルダ"
    },
    placeholders: {
      copyTarget: "未設定時はバックエンドの既定値を使用します",
      newRoot: "D:\\Images"
    },
    sections: {
      advanced: "詳細設定",
      copyTarget: "コピー先フォルダ",
      displayStyle: "表示スタイル",
      language: "言語",
      overview: "現在の概要",
      roots: "読み込みフォルダ",
      status: "状態"
    },
    status: {
      copyTargetCleared: "コピー先をクリアしました",
      copyTargetSaved: "保存しました",
      displayStyleSaved: "表示スタイルを保存しました",
      invalidRoot: "追加するフォルダを入力してください",
      languageSaved: "言語設定を保存しました",
      loadFailed: "設定の読み込みに失敗しました",
      ready: "準備完了",
      requestFailed: "リクエストに失敗しました",
      rootAdded: "フォルダを追加し、現在のフォルダに設定しました",
      rootNotRegistered: "このフォルダは登録されていません",
      rootRemoved: "フォルダを削除しました",
      rootRemovedWithCleanup: "フォルダを削除し、関連データと履歴をクリアしました",
      rootRequired: "少なくとも1つのフォルダが必要です",
      rootSwitched: "現在のフォルダを切り替えました",
      unsupportedDisplayStyle: "対応していない表示スタイルです",
      unsupportedLanguage: "対応していない言語です"
    },
    title: "設定"
  },
  system: {
    labels: {
      finishedAt: "終了時刻",
      generatedAt: "生成時刻",
      startedAt: "開始時刻",
      status: "状態",
      summary: "概要"
    }
  },
  maintenance: {
    backToTasks: "タスク",
    galleryIndexHelp: "現在の root のギャラリー画像索引、総数、Timeline ナビゲーションを再構築します。Hash DB や重複結果は再構築しません。",
    galleryIndexRoot: "現在のギャラリー root",
    galleryIndexTitle: "ギャラリー索引",
    hashMaintenanceHelp: "現在の root のファイル Hash と重複検出結果を再構築します。通常、ギャラリー索引の再構築より時間がかかります。",
    hashMaintenanceTitle: "Hash DB と重複結果",
    pageIntro: "索引を再構築し、長期運用後のギャラリーメタデータを修復します。",
    pageTitle: "メンテナンス"
  },
  tasks: {
    backToGallery: "メイン画面へ戻る",
    confirmLeaveWhileRunning: "現在の処理はまだ実行中です。ここで画面を離れると、現在の処理が中断されるか、このページでの監視が停止する可能性があります。続行しますか？",
    confirmRunImageIndexRebuild: "このフォルダーのギャラリー索引と Timeline を再構築しますか？",
    confirmRunRebuild: "現在のフォルダーをもとに Hash DB と重複結果を再構築しますか？",
    confirmRunTimestampRepair: "このフォルダーで EXIF タイムスタンプ修復を実行しますか？EXIF 撮影時刻があるファイルのみ処理します。",
    confirmRunTask: "整理を開始し、Hash DB と重複結果を更新しますか？",
    csvPath: "CSV パス",
    destDir: "出力ディレクトリ",
    duplicateDetection: "重複検出",
    errors: {
      taskAlreadyRunning: "別の整理または再構築タスクが実行中です。完了してから再試行してください。"
    },
    hashDbPath: "Hash DB パス",
    hashMethod: "Hash 種別",
    includeVideosHelp: "ffprobe で動画内の creation_time を読み取ります。内蔵作成時刻がない動画はスキップします。",
    includeVideosLabel: "内蔵作成時刻がある動画を含める",
    idle: "未開始",
    language: "言語",
    leavePage: "このまま離れる",
    liveOutput: "リアルタイム出力",
    logPath: "ログパス",
    mode: "モード",
    noDirectoryToOpen: "開けるディレクトリがありません。",
    noTaskOutput: "まだタスク出力はありません。",
    noTaskStarted: "まだタスクは開始されていません。",
    maintenanceMovedHelp: "索引再構築、タイムスタンプ修復、長期運用メンテナンスはメンテナンスページに移動しました。",
    stillRunning: "タスクはまだ実行中です...",
    openDirectory: "開く",
    openMaintenance: "メンテナンスを開く",
    openedDirectory: (path) => `ディレクトリを開きました：${path}`,
    outputs: "出力ファイル",
    pageIntro: "整理タスクを実行し、結果をルートデータベースへ書き込みます。",
    pageTitle: "Media Engine タスク",
    phashThreshold: "pHash しきい値",
    runImageIndexRebuildTask: "ギャラリー索引を再構築",
    runRebuildTask: "再構築",
    runTask: "開始",
    skipExistingExactHelp: "重複検出で Strict を選択した場合に使用できます。SHA-256 が完全に一致する写真を検出した場合は、整理記録のみを作成し、ファイルは再コピーしません。",
    skipExistingExactLabel: "すでにギャラリーにある写真は重複保存しない（長期利用者におすすめ）",
    sourceDir: "入力ディレクトリ",
    renameFromExifHelp: "現在のファイル名が日付時刻形式に見えるファイルだけをリネームします。形式: YYYYMMDD-HHMMSS。",
    renameFromExifLabel: "日付形式のファイル名を EXIF からリネーム",
    runTimestampRepairTask: "時刻を修復",
    syncModifiedTimeHelp: "ファイルの更新日時と EXIF 撮影時刻が 7 日を超えて違う場合のみ、更新日時を変更します。",
    syncModifiedTimeLabel: "EXIF から更新日時を同期",
    taskConfig: "タスク設定",
    taskId: "タスク ID",
    taskSummary: "タスク概要",
    timestampRepairHelp: "画像は EXIF 撮影時刻を使います。動画は動画オプションを有効にし、ffprobe が内蔵 creation_time を読める場合だけ処理します。",
    timestampRepairNotReady: "EXIF タイムスタンプ修復はページに表示されていますが、バックエンドタスクはまだ接続されていません。",
    timestampRepairRoot: "修復対象フォルダ",
    timestampRepairThreshold: "最小差分（日）",
    timestampRepairTitle: "EXIF タイムスタンプ修復"
  },
  viewer: {
    action: {
      copied: (path) => `${path} にコピーしました`,
      copying: (path) => `${path} をコピー中 ...`,
      deleted: (path) => `${path} をごみ箱へ移しました。`,
      deleting: (path) => `${path} をごみ箱へ移動中 ...`,
      openedFolder: (path) => `フォルダを開きました: ${path}`,
      openingFolder: (path) => `${path} のフォルダを開いています ...`,
      openedEditor: (path) => `画像エディターで開きました: ${path}`,
      openingEditor: (path) => `${path} を画像エディターで開いています ...`
    },
    buttons: {
      backToGallery: "ギャラリーへ戻る",
      copySelected: "コピー",
      deleteSelected: "削除",
      openFolder: "フォルダを開く",
      openEditor: "ペイントで編集",
      rotateLeft: "左回転",
      rotateRight: "右回転",
      showSidebar: "情報パネル表示",
      toggleSidebar: "情報パネル非表示"
    },
    display: {
      index: (i, t) => `${i} / ${t}`,
      zoom: (z) => `ズーム：${z}%`
    },
    exif: {
      empty: "画像を選択すると撮影情報を表示します。",
      failed: "EXIF 情報の読み取りに失敗しました。",
      loading: "EXIF 情報を読み込み中...",
      unavailable: "この画像には利用できる EXIF 情報がありません。"
    },
    hint: "ヒント: 左右キーで画像を切り替えられます。削除操作ではごみ箱へ移動します。",
    labels: {
      actions: "操作",
      exifAperture: "絞り",
      exifCamera: "カメラ",
      exifDatetime: "撮影日時",
      exifDimensions: "サイズ",
      exifFocalLength: "焦点距離",
      exifGpsAltitude: "高度",
      exifGpsCoordinates: "位置情報",
      exifInfo: "EXIF 情報",
      exifIso: "ISO",
      exifLens: "レンズ",
      exifShutter: "シャッター",
      info: "画像情報",
      status: "状態"
    },
    status: {
      ready: "準備完了。"
    }
  }
};
