# Database Schema

ZeroTraceBrowser's SQLite migration should stay root-scoped. Each image root
workspace owns its own database:

```text
data/roots/<root_id>/workspace.sqlite3
```

The task result flow writes duplicate results and hash DB records directly to
this database. The index-page flow writes image index, summary, and timeline
data directly to the same database. Duplicate and image-index reads use SQLite
for the active root. Recycle-bin current state also writes to SQLite, while CSV
delete logs remain as audit history. Viewer EXIF metadata is cached in SQLite
after the first `/api/exif` read.

## Versioning

### `schema_migrations`

Tracks applied schema versions.

| Column | Type | Notes |
| --- | --- | --- |
| `version` | INTEGER PRIMARY KEY | Current schema version is `3`. |
| `applied_at` | TEXT | SQLite timestamp. |

## Duplicate Results

### `duplicate_results`

One current duplicate result per root database.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Always `1` for the current result. |
| `generated_at` | TEXT | Duplicate result generation time. |
| `destination_root` | TEXT | Normalized root path from the result payload. |
| `group_count` | INTEGER | Stored top-level count or computed group count. |
| `source_path` | TEXT | Source path or database path used by the migration/write job. |
| `raw_json` | TEXT | Original top-level payload for compatibility/debugging. |
| `updated_at` | TEXT | SQLite timestamp. |

### `duplicate_groups`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Internal row id. |
| `result_id` | INTEGER | References `duplicate_results(id)`. |
| `group_id` | TEXT | Existing group identifier. |
| `reason` | TEXT | Detection method, for example `strict` or `phash`. |
| `hash` | TEXT | Duplicate hash key. |
| `kept_path` | TEXT | Relative path selected as kept. |
| `item_count` | INTEGER | Number of raw items in the group. |
| `position` | INTEGER | Original group order. |
| `raw_json` | TEXT | Original group payload. |

Unique key: `(result_id, group_id)`.

### `duplicate_items`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Internal row id. |
| `group_row_id` | INTEGER | References `duplicate_groups(id)`. |
| `role` | TEXT | `kept` or `duplicate`. |
| `path` | TEXT | Relative path under `destination_root`. |
| `file_exists` | INTEGER | Boolean marker as `0` or `1`; repository APIs expose it as `exists`. |
| `position` | INTEGER | Original item order. |
| `raw_json` | TEXT | Original item payload. |

## Image Index

### `image_indexes`

| Column | Type | Notes |
| --- | --- | --- |
| `cache_digest` | TEXT PRIMARY KEY | Existing digest from scan root/extensions/exclusions. |
| `root` | TEXT | Root path for the index. |
| `generated_at` | TEXT | Cache generation time. |
| `timeline_generated_at` | TEXT | Generation time for timeline entries. |
| `total` | INTEGER | Full image count. |
| `duplicate_group_count` | INTEGER | Optional current duplicate count. |
| `updated_at` | TEXT | SQLite timestamp. |

### `image_items`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Internal row id. |
| `cache_digest` | TEXT | References `image_indexes(cache_digest)`. |
| `relative_path` | TEXT | Path relative to root. |
| `path` | TEXT | Backward-compatible path value. |
| `name` | TEXT | File name. |
| `size` | INTEGER | File size in bytes. |
| `captured_at` | TEXT | EXIF capture time when available. |
| `modified_at` | TEXT | File modified time. |
| `timeline_time` | TEXT | Display timeline time. |
| `timeline_ts` | REAL | Sort timestamp. |
| `timeline_source` | TEXT | `exif`, `file`, or empty. |
| `file_exists` | INTEGER | Boolean marker as `0` or `1`; repository APIs expose it as `exists`. |
| `hash` | TEXT | Optional content hash. |
| `width` | INTEGER | Optional image width. |
| `height` | INTEGER | Optional image height. |
| `position` | INTEGER | Original scan order. |
| `raw_json` | TEXT | Original scan item payload. |

Unique key: `(cache_digest, relative_path)`.

### `timeline_entries`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Internal row id. |
| `cache_digest` | TEXT | References `image_indexes(cache_digest)`. |
| `key` | TEXT | Timeline group key, for example `2026-05`. |
| `label` | TEXT | Display label. |
| `index_label` | TEXT | Compact index label. |
| `position` | INTEGER | Original timeline order. |

Unique key: `(cache_digest, key)`.

## Recycle Records

### `recycle_records`

Stores the current CSV delete-log shape in table form.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Internal row id. |
| `timestamp` | TEXT | Operation time. |
| `root` | TEXT | Source root. |
| `relative_path` | TEXT | Original relative path. |
| `deleted_to` | TEXT | Application recycle path. |
| `action` | TEXT | `deleted`, `restored`, or `purged`. |
| `updated_at` | TEXT | SQLite timestamp. |

Unique key: `deleted_to`.

## Viewer EXIF Cache

### `image_exif_cache`

Stores viewer metadata read from source image files. The file signature prevents
serving stale EXIF after an image changes.

| Column | Type | Notes |
| --- | --- | --- |
| `relative_path` | TEXT PRIMARY KEY | Path relative to the active image root. |
| `file_size` | INTEGER | Source file size at cache time. |
| `mtime_ns` | INTEGER | Source file modification timestamp in nanoseconds. |
| `raw_json` | TEXT | EXIF summary payload returned by `/api/exif`. |
| `updated_at` | TEXT | SQLite timestamp. |

## Hash DB

### `hash_db_metadata`

Stores the current hash database source and raw payload for compatibility.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Always `1` for the current hash DB snapshot. |
| `source_path` | TEXT | Source path or database path used by the migration/write job. |
| `raw_json` | TEXT | Normalized hash DB payload. |
| `updated_at` | TEXT | SQLite timestamp. |

### `hash_db_records`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Internal row id. |
| `method` | TEXT | `phash` or `strict`. |
| `hash` | TEXT | Hash value. |
| `path` | TEXT | Absolute image path recorded by MediaArchiveOrganizer. |
| `position` | INTEGER | Original path order for a hash bucket. |

Unique key: `(method, hash, path)`.

## API Surface

Initial repository APIs:

```text
core.storage.database
  root_database_path(root_context)
  init_root_database(database_path)
  connect(database_path)

core.storage.duplicates_repository.DuplicateResultRepository
  save_result(payload, source_path="")
  load_result()
  load_summary()
  clear_result()

core.storage.image_index_repository.ImageIndexRepository
  save_index(cache_digest, root, items, total=None, generated_at=None,
             duplicate_group_count=None, timeline_entries=None)
  load_metadata(cache_digest)
  load_summary(cache_digest)
  list_images(cache_digest, offset=0, limit=None)
  load_timeline_entries(cache_digest)
  replace_timeline_entries(cache_digest, root, entries, generated_at)

core.storage.recycle_repository.RecycleRepository
  append_record(timestamp, root, relative_path, deleted_to, action="deleted")
  list_records(include_terminal=True)
  update_action(deleted_to, action)

core.storage.hash_db_repository.HashDbRepository
  save_hash_db(payload, source_path="")
  load_hash_db()
  load_summary()
  clear_hash_db()

core.storage.exif_repository.ExifRepository
  save_exif(relative_path, payload, file_size, mtime_ns)
  load_exif(relative_path, file_size, mtime_ns)
```

These APIs are intentionally table-oriented. Future migration work can adjust
or add methods as remaining audit formats move to SQLite.
