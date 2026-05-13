# Data Format Inventory

This document records the remaining file-backed data formats during the SQLite
migration. Task duplicate results and hash DB records now write directly to the
root workspace database; several files remain as compatibility or audit formats.

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

## Duplicate Results

### `data/roots/<root_id>/duplicates.json`

Legacy root-scoped duplicate detection result. Current task buttons write the
same result shape directly to `workspace.sqlite3`; the duplicates page keeps
JSON compatibility for older workspaces and tests.

Top-level fields:

```json
{
  "generated_at": "2026-04-23T12:34:56",
  "destination_root": "D:/Photos",
  "group_count": 2,
  "groups": []
}
```

Each group contains:

```json
{
  "group_id": "dup_0001",
  "reason": "strict",
  "hash": "abc123",
  "kept_path": "2026/04/23/kept.jpg",
  "items": [
    {"role": "kept", "path": "2026/04/23/kept.jpg"},
    {"role": "duplicate", "path": "2026/04/23/kept_dup1.jpg"}
  ]
}
```

Notes:

- `destination_root` must match the active root before the UI treats the result
  as current.
- `reason` currently behaves as the detection method, commonly `strict` or
  `phash`.
- Item `path` values are relative to `destination_root` and must still be
  resolved through path-safety helpers when used for file access.

Migration status: active task writes now target SQLite. Legacy JSON can still be
read while older results exist.

## Image Index Cache

### `data/roots/<root_id>/indexes/<digest>.json`

Full image index cache.

Top-level fields:

```json
{
  "generated_at": "2026-05-13T10:00:00",
  "root": "D:/Photos",
  "items": []
}
```

Each item is the scan metadata returned by the image scanner:

```json
{
  "relative_path": "2026/04/23/photo.jpg",
  "path": "2026/04/23/photo.jpg",
  "name": "photo.jpg",
  "size": 12345,
  "captured_at": "",
  "modified_at": "2026-05-13T10:00:00",
  "timeline_time": "2026-05-13 10:00:00",
  "timeline_ts": 1778643600,
  "timeline_source": "file",
  "exists": true
}
```

Optional fields observed or expected by domain models include `hash`, `width`,
and `height`.

### `data/roots/<root_id>/indexes/<digest>.summary.json`

Fast first-paint summary cache.

Fields:

```json
{
  "generated_at": "2026-05-13T10:00:00",
  "root": "D:/Photos",
  "total": 1200,
  "duplicate_group_count": 15,
  "items": []
}
```

`items` is a preview slice, not necessarily the full index.

### `data/roots/<root_id>/indexes/<digest>.timeline.json`

Timeline navigation cache.

Fields:

```json
{
  "generated_at": "2026-05-13T10:00:00",
  "root": "D:/Photos",
  "entries": [
    {"key": "2026-05", "label": "2026-05", "index_label": "202605"}
  ]
}
```

Migration recommendation: second SQLite target. It benefits from indexed
pagination, summary reads, and timeline queries.

## Logs

### `data/roots/<root_id>/logs/delete_log.csv`

Delete and recycle lifecycle log.

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

Migration recommendation: suitable for SQLite after duplicates and image index
APIs are validated. It needs careful compatibility because restore and purge
flows depend on audit history.

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

## Initial Migration Priority

Recommended order:

1. Duplicate results.
2. Image index, summary, and timeline cache.
3. Recycle/delete lifecycle records.
4. Task summary metadata.
5. Optional audit logs.
