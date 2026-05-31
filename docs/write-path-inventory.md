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
| `/api/tasks/run-organizer` | Copies or moves source media into destination root; writes `tasks/<task_id>/organizer.log`; may write legacy hash/duplicate JSON through `media_engine`. | `task_runs`; imports legacy hash DB into `hash_db_records`; publishes duplicate result if available. | Root summary, gallery index summary metadata, in-memory image list cache. | This remains the broadest path and can touch originals if mode is `move`; safety depends on task validation. |
| `/api/tasks/rebuild-hash-db` | Writes task log and media_engine hash output. | Replaces or updates `hash_db_records`; publishes duplicate results for requested method. | Root summary and gallery index metadata after completion. | Strict and pHash are currently rebuilt by the selected mode, not as a single combined UI action. |
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

## Producer / Consumer / Completer Matrix

Use this matrix before changing page reads or import writes. A slow page is
often a symptom that a producer left incomplete data, not proof that the page
should become a broader repair path.

| State | Producers | Consumers | Completers | Completer boundary |
| --- | --- | --- | --- | --- |
| Active-root media files | Organizer task, Shortcut upload, Phone Sync upload, MTP import, copy/delete/restore/purge use cases | Gallery, viewer, duplicates thumbnails, similarity, recycle restore/purge | None for originals | Original-file mutation must be explicit. No page read may move, delete, rename, or reorganize originals. |
| `hash_db_records` | Organizer task, hash DB rebuild, shared import service, MTP import | Duplicate rebuild, similarity search, duplicate skip checks | Hash DB rebuild | Any producer adding records for a final file must also write the matching `file_hash_cache` row. |
| `file_hash_cache` | Organizer/hash rebuild cache writes, shared import service | Hash DB rebuild and duplicate rebuild helpers | Hash DB rebuild backfill | Cache backfill is allowed in explicit rebuild/maintenance. Page reads should not scan the root to repair missing cache rows. |
| `duplicate_results`, `duplicate_groups`, `duplicate_items` | Organizer/rebuild duplicate publish, duplicate dirty markers from import, delete/restore availability sync | Duplicates page, settings summary, similarity duplicate hints | Duplicate-result rebuild from hash DB; recycle availability reconciliation | Dirty rebuild may run only from complete hash/cache state or explicit maintenance. Missing source hash/cache data is a producer bug. |
| `image_indexes`, `image_items`, `timeline_entries` | Gallery scan, image index rebuild, shared import service, delete/restore invalidation | Gallery, Timeline, Viewer return/hydration, settings summaries | Image index rebuild, controlled gallery scan | Page reads may use cached indexes and bounded scans. Broad index rebuilding belongs to explicit scan/rebuild paths. |
| `mobile_photo_index`, `mobile_import_records`, `import_items` | MTP index/import, Shortcut upload, Phone Sync manifest/upload | Import page, sync status, duplicate/deleted-marker decisions | Protocol-specific resume/status repair | Import state is audit/authority for sync decisions, not disposable UI cache. |
| `recycle_records` and delete logs | Delete, restore, purge, clear recycle | Recycle page, duplicate availability sync, deleted-marker checks | Log/archive maintenance | Safe-delete state is authoritative. Derived duplicate availability may sync from it, but recycle state must not be inferred from duplicate results. |
| EXIF cache | Viewer EXIF read, metadata helpers | Viewer, image metadata consumers | Read-through EXIF cache | Safe as a bounded consumer-side cache because it is per-file and signature-checked. |
| Thumbnails | Thumbnail endpoints, cleanup flows | Gallery, viewer, duplicates, recycle | Read-through thumbnail generation | Safe as derived cache. It must stay under root workspace thumbnails and be regenerable. |
| Similarity features | Similarity cache build/search | Similarity page | Similarity cache build | Expensive feature completion should be explicit or bounded to requested candidates. |

### Contract Checks

Before adding or changing an endpoint, answer these questions in code review:

1. Which state does this path produce?
2. Which pages consume that state?
3. Which fields must be written together for the consumer to trust it?
4. Which missing pieces may be completed lazily, and what is the cost limit?
5. Which test proves the full flow from producer through completer to page API?

Concrete import contract:

- Successful final-file imports must write `hash_db_records` for strict and
  optional pHash.
- The same import must write `file_hash_cache` for the final path with size,
  `mtime_ns`, strict hash, and optional pHash.
- Historical imports that can affect existing duplicate groups should mark
  duplicate results dirty.
- Imports must update or invalidate gallery index data through the shared
  import service, not by each endpoint inventing its own partial rule.
- The duplicates page may consume duplicate results and trigger the existing
  dirty-result completer, but it should not compensate for missing import hash
  cache data by scanning the whole root.

### Page Read Responsibilities

Page reads should be classified by what they are allowed to produce while
serving a request:

| Page/API | Primary role | Data it may read | Writes allowed during read | Writes that must stay outside the read path |
| --- | --- | --- | --- | --- |
| Index / gallery | Consumer | Active-root files, `image_items`, `timeline_entries`, thumbnails, EXIF cache. | Bounded image/index cache refresh, thumbnail generation, and signature-checked EXIF cache writes. | Hash DB repair, duplicate rebuild, broad recycle reconciliation, import-status repair. |
| Viewer | Consumer | One media file, adjacent index context, EXIF cache, thumbnail/image bytes. | Signature-checked EXIF cache for the requested file. | Gallery index rebuild, duplicate rebuild, import/recycle mutation. |
| Duplicates | Consumer of duplicate results; completer trigger only while legacy dirty-read behavior remains. | `duplicate_results`, `duplicate_groups`, `duplicate_items`, active file existence, thumbnails. | Thumbnail generation and bounded availability reconciliation from known recycle/delete state. | Hash DB cache backfill, root-wide scan, import repair, unbounded duplicate rebuild hidden behind page load. |
| Recycle | Consumer of safe-delete state. | `recycle_records`, delete logs, deleted files, deleted thumbnails. | Thumbnail generation for deleted files and one-time legacy delete-log migration. | Inferring recycle state from duplicate results or moving/deleting originals outside explicit restore/purge/clear actions. |
| Similarity | Consumer of similarity features and query image. | Similarity feature cache, image bytes, thumbnails, duplicate hints. | Bounded requested-candidate feature extraction if the feature path explicitly owns that cache. | Hash DB repair, duplicate result publication, import/recycle mutation. |
| Maintenance / tasks | Explicit completer UI. | Task status, logs, root summaries. | Starts explicit completer tasks such as hash DB rebuild, duplicate rebuild, image index rebuild, timestamp repair. | Silent mutation without a user-triggered task. |

Current boundary exceptions to remove over time:

- `/api/duplicates` still runs the dirty duplicate-result completer when the
  duplicate summary is marked dirty. This is compatibility behavior, not the
  desired long-term page responsibility. The next safer shape is for producers
  to mark dirty, maintenance/tasks to complete the rebuild, and duplicates to
  show the dirty state without doing broad work on page load.
- `/api/recycle-bin` can migrate legacy delete CSV rows into
  `recycle_records`. That is a bounded compatibility migration. New recycle
  writes must go through delete/restore/purge/clear producers, not page reads.

Consumer read audit:

| Consumer read path | Observed write during read | Boundary classification | Follow-up |
| --- | --- | --- | --- |
| `/api/images` with async scan | Starts or continues a bounded gallery index scan; may write preview/full `image_items` and `timeline_entries`. | Allowed consumer-owned cache/completer hybrid. It is bounded to gallery index state and does not repair hash, duplicates, import, or recycle authority. | Keep this path focused on image index only. If it becomes expensive, move broad rebuild to `/api/tasks/rebuild-image-index`. |
| `/api/timeline-index` | If full image index exists but timeline entries are stale/missing, writes `timeline_entries` from that full index. | Allowed bounded completion inside the image-index domain. It does not scan root files or repair unrelated state. | Keep generation source restricted to full index, not summary items. |
| `/api/exif` | Writes `image_exif_cache` for the requested file signature. | Allowed read-through cache. | Keep signature checks mandatory. |
| `/api/thumbnail`, `/api/duplicates/thumbnail`, `/api/recycle-bin/thumbnail` | Writes thumbnail files under the root workspace thumbnail directory. | Allowed read-through derived cache. | Keep thumbnails disposable and root-scoped. |
| `/api/duplicates` | May run dirty duplicate-result rebuild; may write duplicate item availability from file existence or recycle records. | Boundary exception. This crosses from consumer into duplicate completer/reconciler. | Do not expand this behavior. Later move dirty rebuild to explicit task/completer and keep page read to dirty-state display plus bounded display filtering. |
| `/api/recycle-bin` and `/api/recycle-bin/logs` | May migrate legacy delete CSV rows into `recycle_records`. | Boundary exception for backward compatibility. | Keep one-time and bounded. New recycle state must be produced by delete/restore/purge/clear flows. |
| `/api/similarity/*` | May write similarity file/feature cache for requested candidates. | Allowed domain-owned derived cache if bounded to requested similarity work. | Do not let similarity write hash DB, duplicate result publication, import state, or recycle state. |

The important test for consumers is negative: page reads should not repair data
owned by another producer. If a consumer needs missing data outside its own
bounded cache, it should expose the state or invoke an explicit completer
rather than silently mutating hash/import/duplicate/recycle authority.

### Import Granularity

Producer granularity should be explicit because each producer decides when a
set of writes is complete enough for later consumers.

| Entry point | Current granularity | Recommended contract |
| --- | --- | --- |
| Shortcut upload | One request, one selected media file. | Complete the full import contract before responding: final file, import record, strict/pHash records, file hash cache, duplicate dirty marker when needed, and gallery index update/invalidation. |
| Phone Sync upload | Server advertises `batch_size = 10`; each upload request still handles one manifest item. | Persist each item independently before responding. The manifest batch is protocol flow control, not the DB transaction boundary. |
| MTP fallback import | Frontend currently loops in batches of 5; backend accepts a request `limit` and can copy/import up to that many items. | Treat each `/api/mobile/index` or `/api/iphone/index` request as one slow-import mini-task. At the end of a request, if any item was imported, the producer must complete hash records, file hash cache, import records, duplicate dirty marker, and gallery index invalidation for the imported set. A larger UI batch such as 100 is acceptable only if the request remains cancellable/retryable and writes a complete contract before returning. |
| Organizer task | One explicit background task over the selected source/destination. | The task may process many files, but task completion must publish complete hash/cache/duplicate/index summaries for the destination root. |
| Hash DB rebuild | One explicit background task over the selected root. | Reconcile `hash_db_records` and `file_hash_cache` together, then publish duplicate results for the requested method. |
| Image index rebuild | One explicit background task over the selected root. | Rebuild image/timeline index state only; do not mutate hash or duplicate authority. |

Default guidance:

- Use small protocol batches for phone sync, because the phone needs frequent
  progress and retry points.
- Use smaller batches for MTP than local disk tasks because MTP copy is slow and
  less reliable. The current UI batch of 5 is conservative. Moving to 50 or 100
  should be treated as a UI/operation choice, not a change to the producer
  contract.
- Regardless of batch size, the boundary is "request/task finished with imported
  items", not "page later notices missing data". When that boundary is reached,
  all consumer-facing data required by index, duplicates, and recycle must
  either be written or explicitly marked dirty for the correct completer.

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
