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
    backToGallery: "メイン画面へ戻る",
    confirmLeaveWhileBusy: "現在の一括処理はまだ実行中です。ここで画面を離れると、現在の処理が中断されるか、このページでの状態表示が停止する可能性があります。続行しますか？",
    bulkConfirm: "実行",
    bulkDeleted: (count) => `このページの${count}件をごみ箱へ移動しました`,
    bulkDeleting: (count) => `このページの${count}件を処理中...`,
    bulkDisabledForPhash: "類似画像は手動確認が必要なため一括削除できません",
    bulkMove100ToRecycle: "次の100グループを移動",
    bulkMoveToRecycle: "現在ページの重複を移動",
    bulkStrict100Title: "現在ページから最大100グループの重複ファイルをごみ箱へ移動",
    bulkStrictTitle: (count) => `このページの${count}件を一括削除`,
    confirmBulkStrict100Delete: (count) =>
            `現在ページから最大100グループ内の${count}件の重複ファイルをごみ箱へ移動します。保持ファイルは削除しません。続行しますか？`,
    confirmBulkStrictDelete: (count) =>
            `このページの${count}件の重複ファイルをごみ箱へ移動します。保持ファイルは削除しません。続行しますか？`,
    deleteSelected: "削除",
    deleted: (path) => `${path} をごみ箱へ移動しました`,
    deleting: (path) => `${path} を削除中...`,
    groupUnavailable: "ファイルが存在しません",
    groups: "グループ",
    items: (count) => `${count} 枚`,
    leavePage: "このまま離れる",
    loading: "読み込み中...",
    method: (reason) => `検出方法：${reason}`,
    methodPhash: "類似検出",
    methodStrict: "完全一致",
    nextPage: "次へ",
    noMethodResults: "結果がありません",
    noResults: "結果がありません",
    noSelection: "画像を選択してください",
    noStrictDuplicatesToDelete: "このページに一括削除できる strict 重複ファイルはありません",
    openTasksTool: "整理ツール",
    openedResultRoot: "フォルダを開きました",
    pageInfo: (page, total) => `${page} / ${total}`,
    pageIntro: "重複画像を確認・削除できます",
    pageTitle: "重複一覧",
    prevPage: "前へ",
    ready: "準備完了",
    refresh: "更新",
    resultRoot: "結果フォルダ",
    statusAvailable: "有効",
    statusDeleted: "削除済み"
  },
  recycle: {
    archiveLogs: "ログアーカイブ",
    archivedLogs: (count, path) => `${count} 件の削除ログをアーカイブしました: ${path}`,
    backToGallery: "メイン画面へ戻る",
    clearRecycle: "このページを空にする",
    clearRecycle100: "100件を空にする",
    clear100Title: "現在ページから最大100件のごみ箱ファイルを空にする",
    clearCurrentPageTitle: (count) => `このページの${count}件を空にする`,
    cleared: (count) => `このページの${count}件を削除しました`,
    cleared100: (count) => `${count}件のごみ箱ファイルを削除しました`,
    clearedAndArchived: (count, path) => `ごみ箱から ${count} 件を削除し、削除ログをアーカイブしました: ${path}`,
    clearedLogs: (count, target) => `${target}を ${count} 件消去しました。`,
    confirmLeaveWhileBusy: "現在のごみ箱処理はまだ実行中です。ここで画面を離れると、現在の処理が中断されるか、このページでの状態表示が停止する可能性があります。続行しますか？",
    confirmArchiveLogs: {
      confirm: "ログをアーカイブ",
      message: "現在の delete_log.csv をタイムスタンプ付きでバックアップし、現在のログ表示を空にしますか？",
      title: "削除ログをアーカイブ"
    },
    confirmClear: {
      confirm: "このページを空にする",
      message: (count) => `このページの${count}件を空にしますか？この操作は元に戻せません。`,
      messagePermanent: (count) => `このページの${count}件を空にしますか？この環境ではファイルは完全に削除され、復元できません。`,
      messageSystemRecycle: (count) => `このページの${count}件を Windows のシステムごみ箱へ移動しますか？`,
      title: "このページを空にする"
    },
    confirmClear100: {
      messagePermanent: (count) => `現在ページから${count}件のごみ箱ファイルを空にしますか？この環境ではファイルは完全に削除され、復元できません。`,
      messageSystemRecycle: (count) => `現在ページから${count}件のごみ箱ファイルを Windows のシステムごみ箱へ移動しますか？`
    },
    confirmClearLogs: {
      confirm: "ログを消去",
      message: (target) =>
            `${target}を消去しますか？\n現在のごみ箱内のファイルには影響しません。`,
      title: "ログを消去"
    },
    confirmPurge: {
      confirm: "完全削除",
      message: (path) =>
            `${path} を完全削除しますか？\nこのファイルは deleted から永久に削除され、復元できません。`,
      messagePermanent: (path) =>
            `${path} を削除しますか？この環境ではファイルは完全に削除され、復元できません。`,
      messageSystemRecycle: (path) =>
            `${path} を削除しますか？ファイルは Windows のシステムごみ箱へ移動されます。`,
      title: "完全削除の確認"
    },
    confirmRestore: {
      confirm: "復元",
      message: (path) =>
            `${path} を復元しますか？\nファイルは元のパスへ戻されます。`,
      title: "復元の確認"
    },
    deleteLogs: "削除ログ",
    deletedAt: "削除日時",
    deletedFile: "ファイル",
    itemCount: (count) => `${count} 件`,
    itemStatus: "状態",
    leavePage: "このまま離れる",
    loading: "読み込み中...",
    logActions: {
      deleted: "削除",
      purged: "完全削除",
      restored: "復元"
    },
    logClearTargets: {
      purged: "完全削除済みログ",
      restored: "復元済みログ",
      restoredAndPurged: "復元済み + 完全削除済みログ"
    },
    logEntries: "ログ件数",
    logFilters: {
      all: "すべて",
      deleted: "削除済み",
      purged: "完全削除済み",
      restored: "復元済み"
    },
    logSummary: (shown, filtered, total) => `${shown} / ${filtered} 件を表示、全 ${total} 件`,
    logTable: {
      action: "操作",
      file: "ファイル",
      originalPath: "元のパス",
      recyclePath: "回収パス",
      time: "時刻"
    },
    noFilteredLogs: "この条件に一致するログはありません。",
    noLogs: "削除ログはまだありません。",
    noLogsToArchive: "アーカイブする削除ログはありません。",
    noRecycleItems: "ごみ箱は空です。",
    nextPage: "次へ",
    originalExists: "元のパスに既にファイルがあります",
    pageInfo: (page, total) => `${page} / ${total}`,
    pageIntro: "ごみ箱内の項目を確認し、復元、空にする前の確認、削除ログ閲覧を行います。",
    pageTitle: "ごみ箱",
    pending: "未処理",
    prevPage: "前へ",
    purged: (path) => `${path} を完全削除しました`,
    purgedItem: "完全削除済み",
    ready: "準備完了",
    recycleItems: "項目",
    refresh: "更新",
    restoreButton: "復元",
    restoreTarget: "元のパス",
    restoreUnavailable: "元のパス情報がないため復元できません",
    restored: (path) => `${path} を復元しました`,
    restoredItem: "復元済み",
    systemRecycleUnsupported: "システムのごみ箱への移動は Windows のみ対応しています。"
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
  tasks: {
    backToGallery: "メイン画面へ戻る",
    confirmLeaveWhileRunning: "現在の処理はまだ実行中です。ここで画面を離れると、現在の処理が中断されるか、このページでの監視が停止する可能性があります。続行しますか？",
    confirmRunRebuild: "現在のフォルダーをもとに Hash DB と重複結果を再構築しますか？",
    confirmRunTask: "整理を開始し、Hash DB と重複結果を更新しますか？",
    csvPath: "CSV パス",
    destDir: "出力ディレクトリ",
    duplicateDetection: "重複検出",
    errors: {
      taskAlreadyRunning: "別の整理または再構築タスクが実行中です。完了してから再試行してください。"
    },
    hashDbPath: "Hash DB パス",
    hashMethod: "Hash 種別",
    hideHashMaintenance: "重複結果メンテナンスを隠す",
    idle: "未開始",
    language: "言語",
    leavePage: "このまま離れる",
    liveOutput: "リアルタイム出力",
    logPath: "ログパス",
    maintenanceTools: "メンテナンスツール",
    mode: "モード",
    noDirectoryToOpen: "開けるディレクトリがありません。",
    noTaskOutput: "まだタスク出力はありません。",
    noTaskStarted: "まだタスクは開始されていません。",
    stillRunning: "タスクはまだ実行中です...",
    openDirectory: "開く",
    openedDirectory: (path) => `ディレクトリを開きました：${path}`,
    outputs: "出力ファイル",
    pageIntro: "整理タスクを実行し、結果をルートデータベースへ書き込みます。",
    pageTitle: "MediaArchiveOrganizer タスク",
    phashThreshold: "pHash しきい値",
    rebuildRoot: "再構築対象ディレクトリ",
    runRebuildTask: "再構築",
    runTask: "開始",
    showHashMaintenance: "重複結果メンテナンスを表示",
    sourceDir: "入力ディレクトリ",
    taskConfig: "タスク設定",
    taskId: "タスク ID",
    taskSummary: "タスク概要"
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
