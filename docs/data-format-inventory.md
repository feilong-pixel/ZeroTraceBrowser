# Data Format Inventory

This document records the file-backed formats that intentionally remain after
the page data migration. Task duplicate results, hash DB records, image index
data, current recycle records, and viewer EXIF metadata now write to the root
workspace database.

## Root Workspace

Root-owned runtime data lives under:

```text
data/roots/<root_id>/
```

`root_id` is derived from the normalized absolute image root path. New runtime
data should remain inside this workspace so root removal and cleanup can stay
bounded.

## Configuration Files

### `settings.json`

Global application settings. It stores language, registered image roots, the
active root, copy target, task defaults, and display/theme preferences.

Migration recommendation: keep as JSON for now. It is small, human-readable,
and not queried like tabular data.

### `data/roots/<root_id>/root.json`

Per-root metadata written when the root workspace is created.

Typical fields:

```json
{
  "root": "D:/Photos",
  "root_id": "<sha1>",
  "created_at": "2026-05-13T10:00:00"
}
```

Migration recommendation: keep as JSON for now. It describes the workspace
itself and is useful during diagnostics.

## Database-Backed Runtime Data

`data/roots/<root_id>/workspace.sqlite3` is the active store for:

- duplicate results used by the duplicates page
- hash DB records produced by task and rebuild flows
- image index, summary, and timeline data used by the index page
- recycle-bin current state
- viewer EXIF metadata cache

The application no longer writes or imports page runtime data from
`duplicates.json` or `indexes/*.json` files.

## Viewer Metadata

Viewer EXIF reads are stored in `workspace.sqlite3` table
`image_exif_cache`. The cache is keyed by relative path plus file size and
mtime signature, so edits to the source image force a fresh metadata read.

The cache is derived from the original image file and can be rebuilt by opening
the image in the viewer.

## Logs

### `data/roots/<root_id>/logs/delete_log.csv`

Delete and recycle lifecycle audit log. Current recycle-bin state is stored in
`workspace.sqlite3`; this CSV remains for audit history and legacy import.

Header:

```csv
timestamp,root,relative_path,deleted_to,action
```

Older files may omit `root` or `action`; readers already tolerate legacy row
shapes.

Actions:

- `deleted`
- `restored`
- `purged`

Migration status: active delete/restore/purge/clear state now writes to SQLite.
CSV audit rows are still written for log history and compatibility.

### `data/roots/<root_id>/logs/copy_log.csv`

Copy operation audit log.

Header:

```csv
timestamp,root,relative_path,copied_to
```

Migration recommendation: later. It is append-only audit data and not currently
the main UI bottleneck.

## Task Outputs

### `data/roots/<root_id>/tasks/<task_id>/`

Task-scoped outputs from organizer and rebuild flows.

Common files:

```text
organizer.log
duplicate_report.csv
```

Current task duplicate results and hash DB records are written to
`data/roots/<root_id>/workspace.sqlite3`. Task logs and CSV duplicate reports
remain files unless the UI starts querying them directly.

## Remaining Candidates

Task logs, task CSV reports, `settings.json`, `root.json`, and audit CSV files
remain file-backed by design. Copy logs can be considered later if the UI starts
querying them directly.
