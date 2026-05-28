# Write Path Inventory

This document is step 1 of the architecture consolidation plan in
`docs/photo-import-design.md`. Its purpose is to make every current write path
visible before the project starts unifying import, maintenance, duplicate, and
index logic.

Scope:

- Active root files under the configured image root.
- Root workspace files under `data/roots/<root_id>/`.
- Root database tables in `data/roots/<root_id>/hash_db.sqlite3`.
- Legacy compatibility files that are still written or imported into the root
  database.

The desired direction is that future changes route these writes through a
small number of shared services instead of letting each endpoint keep private
rules.

## Root Workspace Targets

Each configured image root owns a workspace created by `RootContext` and
`ensure_root_workspace`:

| Target | Owner | Notes |
| --- | --- | --- |
| `root.json` | root workspace setup | Root metadata for the workspace. |
| `deleted/` | delete/recycle flows | Application recycle area. User originals are moved here before restore/purge. |
| `thumbnails/` | thumbnail endpoints and cleanup flows | Derived cache; safe to regenerate. |
| `logs/copy_log.csv` | copy flow | CSV log only; no current DB mirror. |
| `logs/delete_log.csv` | delete/recycle compatibility | Recycle DB is preferred, but CSV is still appended and read as fallback. |
| `indexes/` | gallery index/timeline summary services | Backed by SQLite repository now, with JSON-path naming still used as cache keys. |
| `tasks/<task_id>/organizer.log` | task endpoints | Per-run task log/output files. |
| `hash_db.sqlite3` | root repositories | Main root-scoped database for hashes, duplicates, indexes, recycle, import, tasks, EXIF, and similarity cache. |

## Database Write Surface

Current root database tables with write APIs:

| Table(s) | Repository | Current writers |
| --- | --- | --- |
| `hash_db_metadata`, `hash_db_records` | `HashDbRepository` | Organizer import from legacy JSON, rebuild hash DB, iPhone Shortcut/MTP import, Phone Sync upload. |
| `duplicate_results`, `duplicate_groups`, `duplicate_items` | `DuplicateResultRepository` | Organizer/rebuild publishes results; import paths mark result dirty; duplicates API can rebuild and clear dirty state. |
| `image_indexes`, `image_items`, `timeline_entries` | `ImageIndexRepository` | Async gallery scan, gallery index rebuild task, index invalidation metadata writes. |
| `recycle_records` | `RecycleRepository` | Delete, restore, purge, clear recycle/log actions. |
| `task_runs`, `task_skipped_existing`, `skipped_existing_index` | `TaskRunRepository` | Task start/finish persistence and organizer skipped-existing import. |
| `image_exif_cache` | `ExifRepository` | `GET /api/exif` after metadata extraction. |
| `similarity_files`, `similarity_features` | `SimilarityRepository` | Similarity search/cache build for document/feature/embedding methods. |
| `mobile_devices`, `mobile_photo_index`, `mobile_import_records`, `local_deleted_markers` | `MobileRepository` | iPhone MTP index/import, Shortcut upload import records, delete-local markers. |
| `mobile_pairings`, `mobile_sync_sessions`, `import_items` | `PhoneSyncRepository` | Phone Sync pair/start/manifest/upload lifecycle. |

## Entry Point Inventory

| Entry point | File writes | DB writes | Derived data touched | Notes |
| --- | --- | --- | --- | --- |
| `/api/tasks/run-organizer` | Copies or moves source media into destination root; writes `tasks/<task_id>/organizer.log`; may write legacy hash/duplicate JSON through `MediaArchiveOrganizer`. | `task_runs`; imports legacy hash DB into `hash_db_records`; publishes duplicate result if available. | Root summary, gallery index summary metadata, in-memory image list cache. | This remains the broadest path and can touch originals if mode is `move`; safety depends on task validation. |
| `/api/tasks/rebuild-hash-db` | Writes task log and MediaArchiveOrganizer hash output. | Replaces or updates `hash_db_records`; publishes duplicate results for requested method. | Root summary and gallery index metadata after completion. | Strict and pHash are currently rebuilt by the selected mode, not as a single combined UI action. |
| `/api/tasks/rebuild-image-index` | No original media write; writes task log. | Replaces `image_indexes`, `image_items`, and `timeline_entries`. | Root summary, duplicate group count, in-memory image list cache. | This is the maintenance path that should keep index-page first paint stable. |
| `/api/tasks/repair-timestamps` | Updates file timestamps; optional EXIF-based rename; writes repair log. | `task_runs` completion. | Clears gallery cache and refreshes root summary. | This is a user-visible original-file mutation and should stay explicit. |
| `GET /api/images` async scan | No original media write. | Writes preview/full image index and timeline rows. | In-memory image list cache, timeline cache keys. | This path can update index state during normal page usage. |
| `GET /api/exif` | No original media write. | Upserts `image_exif_cache`. | None. | Read API with cache write side effect. |
| `GET /api/thumbnail`, recycle thumbnails | Writes thumbnail files under `thumbnails/`. | None. | Thumbnail cache. | Derived cache only; delete/restore/purge remove stale thumbnails. |
| `POST /api/copy` | Copies selected media to copy target; appends `logs/copy_log.csv`. | None. | Clears active-root image list cache. | Copy target can be outside active root by design. |
| `POST /api/delete` | Moves active-root media to `deleted/`; removes stale thumbnail; appends `logs/delete_log.csv`. | Upserts `recycle_records`; inserts/updates `local_deleted_markers`. | Clears active-root image list cache. | This is the key safe-delete path; originals are not unlinked directly. |
| `POST /api/recycle-bin/restore` | Moves file from `deleted/` back to original path; removes stale thumbnails; appends restore row to `delete_log.csv`. | Updates matching `recycle_records` action to `restored`. | Clears restored root image list cache. | Uses delete log/DB to recover original relative path. |
| `POST /api/recycle-bin/purge` | On Windows can move recycle-area file to system recycle; otherwise unlinks recycle-area file; removes thumbnail; appends purge row. | Updates matching `recycle_records` action to `purged`. | Removes empty deleted folders. | Applies only to app recycle files, not active originals. |
| `POST /api/recycle-bin/clear` | Purges all recycle-area files; removes thumbnails; archives delete log when items removed. | Updates matching `recycle_records` actions to `purged`. | Removes empty deleted folders. | Bulk version of purge. |
| recycle log archive/clear endpoints | Writes or truncates recycle log files. | Clears selected `recycle_records` rows depending on action. | None. | Administrative maintenance of audit data. |
| `/api/iphone/upload` and `/upload` Shortcut upload | Stages request body in temp, copies final file into active root date path. | Saves mobile index/import record; adds strict hash; marks duplicate result dirty; marks imported/skipped state. | Invalidates gallery index metadata and clears stale index cache. | Uses current duplicate/deleted-marker checks and suffix-aware strict matching. |
| `/api/iphone/index` / mobile iPhone MTP index | Copies selected MTP files into temp staging; when importing, copies final media into active root. | Saves `mobile_photo_index`; inserts mobile import records; adds strict hashes; marks duplicate result dirty; marks imported/skipped/deleted-device state. | Invalidates gallery index metadata and clears stale index cache. | This is one of the paths that previously admitted unsupported sidecars before filtering. |
| Phone Sync pair/start/manifest | No media file write. | Upserts `mobile_pairings`, `mobile_sync_sessions`, and `import_items`. | None. | Establishes import authority and per-item state before upload bytes arrive. |
| Phone Sync upload | Stages request body in temp, copies final file into active root date path. | Updates `import_items`; adds strict hash and optional pHash; marks duplicate result dirty. | Invalidates gallery index metadata and clears stale index cache. | This path has its own import-state table and currently shares helper functions with iPhone upload. |
| Similarity search/cache build | No original media write. | Upserts `similarity_files` and `similarity_features`; may delete stale similarity rows. | Similarity cache only. | Read-like feature with DB cache side effects. |
| Settings language/display/copy target | Writes `settings.json`. | None. | None. | Global setting write, not root-scoped. |
| Add or switch active root | Writes `settings.json`; ensures root workspace directories/log headers/root metadata. | Initializes root database schema. | None. | Switching root creates workspace if missing. |
| Remove root | Writes `settings.json`; optional cleanup removes root-related workspace data. | May delete root workspace database as part of cleanup. | Removes derived root data if requested. | Must remain explicit and conservative. |
| Phone Sync server id creation | Writes `settings.json`. | None. | None. | Lazy write when pairing code/status needs a server id. |
| root workspace legacy artifact migration | Copies legacy hash/duplicates artifacts into root workspace when requested by compatibility helpers. | May import legacy artifacts into root DB later. | None. | Temporary compatibility surface; should shrink over time. |

## Cross-Cutting Rules To Centralize

These rules currently appear in more than one path and should become shared
contracts before deeper refactoring:

- Supported media and sidecar exclusion: one allowlist for image/video files,
  with `.aae` and other sidecars excluded before hash/import records are
  created.
- Strict duplicate compatibility: allow compatible image aliases such as
  `.jpg` and `.jpeg`, but reject sidecar/image and video/image strict groups.
- Final destination naming: date path, collision suffix, portable timestamp
  handling, and unique path generation should be shared by Shortcut, MTP,
  Phone Sync, and organizer task code.
- Hash writes: strict hash writes and optional pHash writes should have one
  policy for when to compute, reuse, or skip.
- Duplicate dirty markers: any path that changes `hash_db_records` should use
  one function to mark duplicate results dirty or publish rebuilt results.
- Gallery invalidation: importing, deleting, restoring, timestamp repair, and
  index rebuild should use one invalidation/update contract for image index,
  timeline entries, root summary, and in-memory cache.
- Import state: mobile/phone/organizer skipped-existing records should converge
  on a shared status vocabulary even if their protocol tables stay separate.

## First Refactor Boundary

The safest first extraction is a shared media policy module, because it can be
validated without moving files:

1. `is_supported_media_filename(name)`
2. `is_sidecar_filename(name)`
3. `strict_extension_key(path_or_name)`
4. `strict_extensions_compatible(a, b)`
5. `phash_eligible(path_or_name)`

After that, migrate one low-risk write entry point to a shared import/write
service while keeping API responses unchanged. The best candidate is Shortcut
upload or Phone Sync upload, because both already stage files and write into
the active root through a narrow path.

