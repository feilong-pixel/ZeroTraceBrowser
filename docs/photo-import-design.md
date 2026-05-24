# Photo Import Design

This document defines the production direction for importing phone photos into
ZeroTraceBrowser. The import page is dedicated to Phone Sync: a paired phone
sends photo bytes to ZeroTraceBrowser over local Wi-Fi.

Both channels are copy-only. Neither channel deletes, moves, or reorganizes
source photos automatically.

---

## Goals

- Keep all import processing local.
- Import into the current active image root unless the user explicitly chooses
  another configured root.
- Preserve original media bytes and file times where possible.
- Detect strict duplicates before writing a second copy.
- Respect local deleted markers so photos removed through ZeroTraceBrowser are
  not silently re-imported.
- Persist import state in the active root workspace database.
- Make interrupted imports resumable from server-side state.
- Make the normal phone experience quiet after first pairing: when the phone and
  computer are on the same Wi-Fi, the phone app finds the computer, uploads
  unsynced photos, and ZeroTraceBrowser processes them locally.
- Keep MTP/device browsing as fallback or experimental recovery, not the main
  large-library import path.

## Non-Goals

- No cloud relay.
- No source deletion.
- No automatic cleanup of phone libraries.
- No direct write-back to phone storage in the main import flow.
- No local-folder import UI on this page. Local folder copy/organize workflows
  belong on the task/organizer surface.
- No new frontend framework or external database.

---

## Phone Sync

Phone Sync is the preferred long-term phone workflow. A phone-side app uploads
original photo bytes to ZeroTraceBrowser over the local network. After the first
pairing, daily sync should be quiet and automatic.

The target experience is:

```text
Computer opens ZeroTraceBrowser.
Phone app scans a pairing QR code once.
After that, when phone and computer are on the same Wi-Fi:
  -> phone app automatically discovers the computer
  -> phone app uploads unsynced photos
  -> computer processes the files quietly
  -> UI shows one soft status line
```

Example status:

```text
Phone syncing: processed 128 / imported 96 / duplicates skipped 32.
```

The first phone client can be iOS Shortcuts for manual proof-of-life uploads. A
dedicated mobile app is the production target for automatic discovery,
background-friendly batching, and resume behavior.

### User Flow

Production flow:

```text
Open Import page on Windows
  -> show pairing QR code
  -> phone app scans and stores pairing
  -> later, phone and computer meet on the same Wi-Fi
  -> phone app discovers ZeroTraceBrowser
  -> phone app uploads unsynced photos in small batches
  -> page shows quiet aggregate sync status
```

Development fallback flow:

```text
Run iOS Shortcut
  -> send one selected photo to ZeroTraceBrowser
  -> server acknowledges the item
  -> page or response shows imported / skipped / failed status
```

### Existing Endpoint

The repository already supports:

```text
POST /api/iphone/upload
POST /upload
```

Current behavior:

- accepts raw file bytes
- reads photo metadata from headers
- writes into the active root by date
- computes strict hash and pHash
- skips strict duplicates
- skips photos with a matching local deleted marker
- stores state in `mobile_import_records`

### Production Endpoint Direction

Keep the existing Shortcut endpoint as compatibility, then add a generic mobile
upload endpoint:

```text
POST /api/mobile/upload
```

Required headers:

```text
X-ZTB-DeviceType: iphone
X-ZTB-DeviceId: user-iphone-13-main
X-Original-Filename: IMG_0948.jpeg
```

Recommended headers:

```text
X-ZTB-Uploader: User Name
X-Original-CreateDate: 2026/05/17 10:26:47 JST
X-Original-UpdateDate: 2026/05/17 11:42:31 JST
X-Original-FileSize: 2.5 MB
X-Original-FileType: jpeg
X-Original-DeviceName: User Name s iPhone 13
X-Original-DeviceModel: iPhone
X-ZTB-SessionId: phone-sync-...
X-ZTB-BatchId: batch-...
X-ZTB-ItemId: local-phone-asset-id
```

Response:

```json
{
  "status": "success",
  "imported": true,
  "device_type": "iphone",
  "device_id": "user-iphone-13-main",
  "file": "IMG_0948.jpeg",
  "local_path": "D:/Photos/2026/05/17/IMG_0948.jpeg",
  "strict_hash": "..."
}
```

Other valid statuses:

```text
skipped_duplicate
skipped_deleted_locally
invalid_file
failed
```

### Interface Contract

The production Phone Sync protocol should use five server APIs. The phone sends
original media bytes only when the server asks for or accepts a batch. The
computer remains the authority for destination root, duplicate policy, deleted
markers, and final import state.

### Identity and Decision Rules

Phone Sync must be keyed by stable identities:

```text
server_id + root_id + device_id + item_id
```

Definitions:

- `server_id`: stable identity of one ZeroTraceBrowser desktop installation.
- `root_id`: stable identity of the destination root workspace.
- `device_id`: stable identity of one phone.
- `item_id`: stable identity of one phone-side photo/video asset.

The phone may keep a local sync cache with this key. That cache is an
optimization only. It helps the phone avoid unnecessary manifest/upload work,
but it is never the final authority.

The desktop must make the final decision in this order:

```text
1. local deleted marker exists for strict hash
   -> skipped_deleted_locally

2. same server_id + device_id + item_id has a terminal sync status
   -> already_imported or previous terminal status

3. same server_id + root_id + device_id + item_id was already imported/skipped
   -> already_imported or previous terminal status

4. strict hash already exists in the destination root
   -> skipped_duplicate

5. otherwise
   -> imported
```

Important behavior:

- If the user deletes an imported photo through ZeroTraceBrowser, future phone
  syncs with the same strict hash return `skipped_deleted_locally`.
- Phone Sync must not silently follow the current UI `active_root`. Pairing
  binds a device to an explicit `root_id` / destination root. Changing that
  target requires an explicit PC-side action.
- If the user explicitly changes a paired device's sync target, only new or
  unprocessed phone assets should sync to the new root. Assets that already
  reached a terminal status for this `server_id + device_id + item_id` should
  not be uploaded again just because the destination root changed.
- If the PC database is rebuilt or migrated, the desktop can use current root
  strict hashes to avoid importing an existing photo again.
- If multiple phones upload the same photo, the first successful import keeps
  the local file and later phones receive `skipped_duplicate`.
- If the same phone connects to another ZeroTraceBrowser desktop, it is a
  different `server_id`; the phone treats it as a separate sync target.

### Multi-Root Duplicate Policy

ZeroTraceBrowser currently manages data most strongly at the active root
workspace level. Multi-root use is real, but cross-root duplicate policy is a
product choice, not a universally correct rule.

Different users may want different behavior:

- Some users want unified management across all roots on one PC.
- Some users want each root to remain independent.
- Some users want phone sync to avoid re-uploading the same phone asset, but
  still allow separate roots to contain their own copy.

For Phone Sync v1, use root-scoped duplicate checks:

```text
target root strict hash exists
  -> skipped_duplicate

same server_id + device_id + item_id has terminal status
  -> do not upload again only for that phone asset history

other roots contain same strict hash
  -> do not block v1 import by default
```

This means v1 prevents obvious repeat uploads and target-root duplicates, but
does not scan every configured root before importing. That keeps the first
implementation predictable and avoids surprising users who intentionally keep
separate root libraries.

Future cross-root policies can be added as explicit settings:

```text
root_scoped      -- only skip duplicates already in the sync target root
server_scoped    -- skip strict duplicates found in any root on this PC
hybrid           -- import into target root, but show cross-root duplicate hints
```

The default should remain `root_scoped` until cross-root indexing is a measured,
well-tested capability. A global/server-level hash registry may be added later,
but it should be treated as a separate feature rather than hidden inside the
first Phone Sync flow.

#### 1. Pair Device

The QR code should encode the desktop URL plus a short-lived pairing token. The
phone calls:

```text
POST /api/mobile/pair
```

Phone sends:

```json
{
  "pairing_token": "pair-...",
  "device_type": "iphone",
  "device_id": "user-iphone-13-main",
  "device_name": "User Name iPhone 13",
  "device_model": "iPhone 13",
  "platform": "ios",
  "app_id": "zerotrace-mobile",
  "app_version": "0.1.0",
  "owner_label": "User Name",
  "capabilities": {
    "background_upload": true,
    "asset_id": true,
    "sha256_on_device": false,
    "heic_original": true,
    "live_photo_pairing": false
  }
}
```

Desktop saves:

- `device_type`
- `device_id`
- `device_name`
- `device_model`
- `platform`
- `app_id`
- `app_version`
- `owner_label`
- pairing status
- paired root id / destination root
- paired_at
- last_seen_at
- capabilities JSON

Desktop returns:

```json
{
  "status": "paired",
  "device_type": "iphone",
  "device_id": "user-iphone-13-main",
  "server_id": "ztb-desktop-...",
  "root_id": "root-...",
  "destination_root": "D:/Photos",
  "sync_token": "sync-...",
  "sync_token_expires_at": "2026-05-24T10:30:00+09:00",
  "batch_size": 10,
  "accepted_types": ["jpg", "jpeg", "png", "heic", "mov"],
  "duplicate_policy": "strict_skip",
  "deleted_marker_policy": "skip_deleted_locally"
}
```

#### 2. Start Or Resume Sync

The phone uses this after discovery or app restart:

```text
POST /api/mobile/sync/start
```

Phone sends:

```json
{
  "device_type": "iphone",
  "device_id": "user-iphone-13-main",
  "sync_token": "sync-...",
  "last_client_cursor": "optional-client-cursor",
  "battery_state": "charging",
  "network_type": "wifi"
}
```

Desktop saves:

- sync session id
- device id
- destination root
- session status
- started_at / last_seen_at
- client status metadata

Desktop returns:

```json
{
  "status": "ready",
  "session_id": "phone-sync-...",
  "server_id": "ztb-desktop-...",
  "root_id": "root-...",
  "destination_root": "D:/Photos",
  "batch_size": 10,
  "server_cursor": "server-cursor-...",
  "known_item_ids": ["asset-local-id-1"],
  "skip_hashes": ["..."],
  "deleted_hashes": ["..."],
  "summary": {
    "processed": 128,
    "imported": 96,
    "skipped_duplicate": 32,
    "skipped_deleted_locally": 0,
    "failed": 0
  }
}
```

`known_item_ids`, `skip_hashes`, and `deleted_hashes` should be limited to the
current device/session window. They are hints for avoiding unnecessary upload,
not the final authority.

#### 3. Send Manifest

The phone sends metadata for candidate assets before uploading bytes:

```text
POST /api/mobile/sync/manifest
```

Phone sends:

```json
{
  "session_id": "phone-sync-...",
  "server_id": "ztb-desktop-...",
  "root_id": "root-...",
  "device_type": "iphone",
  "device_id": "user-iphone-13-main",
  "items": [
    {
      "item_id": "asset-local-id-1",
      "filename": "IMG_0948.HEIC",
      "media_type": "image",
      "mime_type": "image/heic",
      "size": 3456789,
      "created_at": "2026-05-17T10:26:47+09:00",
      "modified_at": "2026-05-17T11:42:31+09:00",
      "timezone": "Asia/Tokyo",
      "album": "Recents",
      "relative_hint": "2026/05",
      "width": 4032,
      "height": 3024,
      "duration_ms": 0,
      "sha256": "",
      "paired_item_id": "",
      "is_favorite": false,
      "is_screenshot": false
    }
  ]
}
```

Desktop saves:

- manifest item identity
- filename
- media type / MIME type
- size
- created / modified timestamps
- album / relative hint
- dimensions / duration
- optional phone-provided hash
- raw metadata JSON
- manifest_seen_at

Desktop returns:

```json
{
  "status": "accepted",
  "session_id": "phone-sync-...",
  "upload_batch_id": "batch-...",
  "upload": [
    {
      "item_id": "asset-local-id-1",
      "upload_url": "/api/mobile/sync/upload",
      "status": "upload_required"
    }
  ],
  "skip": [
    {
      "item_id": "asset-local-id-2",
      "status": "already_imported",
      "local_path": "D:/Photos/2026/05/17/IMG_0002.JPG"
    }
  ],
  "batch_size": 10
}
```

#### 4. Upload Item Bytes

The phone uploads one item at a time. This keeps retries simple and lets the
desktop acknowledge every asset independently.

```text
POST /api/mobile/sync/upload
```

Initial implementation uses raw request bytes plus one JSON metadata header, so
the desktop can accept uploads without adding a multipart parser dependency:

```text
X-ZTB-Mobile-Metadata: JSON object
body: original media bytes
```

Metadata:

```json
{
  "session_id": "phone-sync-...",
  "upload_batch_id": "batch-...",
  "device_type": "iphone",
  "device_id": "user-iphone-13-main",
  "item_id": "asset-local-id-1",
  "server_id": "ztb-desktop-...",
  "root_id": "root-...",
  "filename": "IMG_0948.HEIC",
  "created_at": "2026-05-17T10:26:47+09:00",
  "modified_at": "2026-05-17T11:42:31+09:00",
  "size": 3456789,
  "mime_type": "image/heic"
}
```

Desktop processing:

```text
receive bytes
  -> write to temporary staging file
  -> validate filename and supported type
  -> compute SHA-256
  -> compute pHash when supported
  -> check local_deleted_markers
  -> check root hash DB strict duplicates
  -> choose YYYY/MM/DD destination path
  -> copy/move from staging into active root
  -> record import item state
  -> update hash DB
  -> invalidate gallery index when at least one item imports
```

Desktop saves:

- strict hash
- pHash
- final import status
- local path or existing local path
- error message if failed
- imported_at
- raw upload metadata

Desktop returns:

```json
{
  "status": "imported",
  "session_id": "phone-sync-...",
  "server_id": "ztb-desktop-...",
  "root_id": "root-...",
  "device_type": "iphone",
  "device_id": "user-iphone-13-main",
  "item_id": "asset-local-id-1",
  "filename": "IMG_0948.HEIC",
  "strict_hash": "...",
  "phash": "...",
  "local_path": "D:/Photos/2026/05/17/IMG_0948.HEIC",
  "existing_local_path": "",
  "imported": true,
  "summary": {
    "processed": 129,
    "imported": 97,
    "skipped_duplicate": 32,
    "skipped_deleted_locally": 0,
    "failed": 0
  }
}
```

Other item statuses:

```text
already_imported
skipped_duplicate
skipped_deleted_locally
unsupported_type
invalid_file
failed
```

#### 5. Read Sync Status

The desktop page polls this endpoint:

```text
GET /api/mobile/sync/status
```

Desktop returns:

```json
{
  "status": "syncing",
  "destination_root": "D:/Photos",
  "paired_devices": 2,
  "connected_devices": [
    {
      "device_type": "iphone",
      "device_id": "user-iphone-13-main",
      "device_name": "User Name iPhone 13",
      "status": "syncing",
      "last_seen_at": "2026-05-24T10:15:00+09:00",
      "processed": 128,
      "imported": 96,
      "skipped_duplicate": 32,
      "skipped_deleted_locally": 0,
      "failed": 0
    }
  ],
  "summary": {
    "processed": 128,
    "imported": 96,
    "skipped_duplicate": 32,
    "skipped_deleted_locally": 0,
    "failed": 0
  },
  "recent_events": [
    {
      "time": "2026-05-24T10:15:00+09:00",
      "device_id": "user-iphone-13-main",
      "message": "Imported IMG_0948.HEIC"
    }
  ]
}
```

The UI should render the aggregate summary first and keep per-device detail
available but quiet.

### Pairing, Discovery, and Access

The production safety model is persistent pairing plus short-lived sync
authorization:

- User opens the Import page and shows a QR code.
- QR code contains LAN URL, pairing token, and server identity.
- Phone app stores the paired computer identity after the first scan.
- Later sessions use local discovery on the same Wi-Fi and request a short-lived
  sync token from the paired computer.
- Upload requests must include the active sync token.
- The sync session is bound to the selected destination root.

This keeps the daily experience quiet without leaving an unauthenticated write
endpoint permanently open on the LAN.

Multiple phones must be treated as a normal case:

- Each phone has a stable `(device_type, device_id)` identity.
- Pairing is per device, not one global phone slot.
- Multiple paired devices may be connected or uploading at the same time.
- Each device receives its own short-lived sync token.
- The server records per-device session and item state, then exposes an
  aggregate summary for the page.
- A failure from one device must not block other devices that are still syncing.

Discovery can be implemented in stages:

1. Manual LAN URL from QR code.
2. Remembered host and port retry.
3. Optional local discovery broadcast or mDNS if the dedicated mobile app needs
   it.

ZeroTraceBrowser should not require cloud accounts or external relay services.

### Batch Rules

- Start with small batches, for example 5 to 20 files.
- Acknowledge every uploaded item independently.
- Persist item state before responding.
- Client retry must be idempotent when `X-ZTB-ItemId` or the strict hash matches
  an already imported item.
- Resume state must come from the root workspace DB, not phone memory alone.
- The phone app should upload only unsynced asset IDs for the paired computer
  and destination root.
- The computer remains the authority for duplicate, deleted-local, and imported
  states.
- Concurrent uploads from different devices should be accepted, but final file
  writes and hash DB updates must remain serialized or transaction-safe per root
  workspace.

---

## Shared Import State

All durable state belongs under the destination root workspace:

```text
data/roots/<root_id>/workspace.sqlite3
```

Current tables already cover the phone path:

- `mobile_devices`
- `mobile_photo_index`
- `mobile_import_records`
- `local_deleted_markers`

The generic import design should either extend these tables or add a parallel
`import_runs` / `import_items` pair. The preferred first production step is to
add the run tables while keeping `mobile_import_records` for phone identity.

Suggested new tables:

```text
mobile_pairings
- id
- server_id
- root_id
- device_type
- device_id
- device_name
- device_model
- platform
- app_id
- app_version
- owner_label
- destination_root
- pairing_status       -- paired | revoked
- paired_at
- last_seen_at
- capabilities_json
- raw_json

mobile_sync_sessions
- id
- session_id
- server_id
- root_id
- device_type
- device_id
- destination_root
- status               -- ready | syncing | completed | failed | expired
- sync_token_hash
- token_expires_at
- client_cursor
- server_cursor
- battery_state
- network_type
- started_at
- last_seen_at
- finished_at
- raw_json

import_runs
- id
- run_id
- channel              -- phone_sync | mtp_fallback
- server_id
- root_id
- source_label
- device_type
- device_id
- destination_root
- status               -- running | completed | cancelled | failed
- started_at
- finished_at
- raw_json

import_items
- id
- run_id
- session_id
- upload_batch_id
- source_ref           -- mobile://...
- server_id
- root_id
- device_type
- device_id
- item_id
- original_filename
- media_type
- mime_type
- size
- created_at
- modified_at
- timezone
- album
- width
- height
- duration_ms
- strict_hash
- phash
- status               -- imported | skipped_duplicate | skipped_deleted_locally | failed
- local_path
- existing_local_path
- error
- manifest_seen_at
- imported_at
- raw_json
```

Status meanings:

- `imported`: a new local file was written.
- `skipped_duplicate`: strict hash already exists in the destination root.
- `skipped_deleted_locally`: strict hash matches a ZeroTraceBrowser deleted
  marker.
- `failed`: the server could not read, hash, or write the item.

---

## UI Design

The import page is a Phone Sync page, not a local folder import page.

Controls:

- pairing QR code for first setup
- connection status
- connected devices list
- active destination root display
- import status
- recent sync summary
- compact log
- link to Device Fallback for the existing experimental MTP page

The normal synced state should stay quiet, for example:

```text
Phone syncing: 2 devices / processed 128 / imported 96 / duplicates skipped 32.
```

Detailed per-file logs should be available behind an expandable panel, not as
the default screen.

The first page should be a practical working screen, not a landing page. It
should use the existing `tasks.html` two-column rhythm:

```text
main work area
  - page title
  - pairing QR code
  - connection status
  - connected devices
  - import status
  - compact log

right sidebar
  - Back to Gallery
  - Sync Summary
  - Recent Syncs
```

The page file should be:

```text
static/import.html
static/js/pages/import-page.js
```

The page should be reachable from the gallery tool list as `Import Photos`.
The existing `mobile-import.html` remains available through a fallback link for
manual device recovery and experimental MTP work.

#### Header

Title:

```text
Import Photos
```

Intro:

```text
Pair a phone once, then import new photos quietly over local Wi-Fi.
```

No hero section, no marketing copy, and no explanatory cards. The first visible
screen should immediately show the pairing and sync status.

#### Running State

During phone sync, show a quiet aggregate status in the main output header:

```text
Importing: processed 128 / imported 96 / duplicates skipped 32 / failed 0
```

The log should stay compact by default. Detailed per-file lines can appear in a
scrollable log box, but the user should not need to read it to understand
whether the import is healthy.

Progress summary fields:

- processed
- imported
- skipped duplicate
- skipped deleted locally
- failed
- destination root
- connected device
- paired device count
- last seen

#### Completion State

After completion:

- Keep the summary visible.
- Offer `Open Gallery`.
- Do not automatically navigate away.

If files were imported, the destination root gallery index should be invalidated
or refreshed according to the backend import result. The page should not assume
the gallery is current until the backend confirms.

#### Error State

Use direct, fixable messages:

- Phone is not paired.
- Phone is offline.
- Pairing token expired.
- Upload token expired.
- Some files failed to upload or import.

#### Sidebar

Sync Summary:

```text
Status
Processed
Imported
Skipped
Failed
Paired devices
```

Recent Syncs:

- show the latest 3 phone sync runs from the active root workspace when available
- each row shows channel, status, imported count, and finished time

#### Responsive Behavior

Desktop:

- main work area plus right sidebar
- pairing/status panels use horizontal space

Narrow/mobile:

- sidebar moves below main content
- form becomes one column
- action buttons remain reachable without horizontal scrolling

#### Initial i18n Namespace

Use a new top-level namespace:

```text
importPhotos
```

Suggested keys:

```text
importPhotos.pageTitle
importPhotos.pageIntro
importPhotos.pairingTitle
importPhotos.qrPlaceholder
importPhotos.connectionStatus
importPhotos.importStatus
importPhotos.connectedDevices
importPhotos.lastSeen
importPhotos.destinationRoot
importPhotos.logEmpty
importPhotos.summary
importPhotos.phoneSyncIdle
importPhotos.recentRuns
```

Add the keys to:

```text
static/js/locales/en.js
static/js/locales/zh.js
static/js/locales/ja.js
```

#### First Implementation Scope

The first implementation should be intentionally narrow:

- Add the static page shell.
- Add i18n text.
- Add QR placeholder.
- Add connection/import status placeholders.
- Add compact log placeholder.
- Link from `index.html` tools.

Do not add local-folder import to this page.

---

## Phased Implementation

### Phase 1: Design Lock

- Keep this document as the source of truth.
- Keep `docs/iphone-shortcut-upload.md` as the current Shortcut operation guide.
- Mark MTP as fallback/experimental in user-facing copy.

### Phase 2: Phone Sync Page Shell

- Add the static Phone Sync page.
- Add pairing QR placeholder.
- Add connection status, import status, and compact log placeholders.
- Link from the gallery tool list.

### Phase 3: Phone Sync Pairing

- Add `/api/mobile/upload`.
- Add first-scan pairing and short-lived sync token.
- Preserve `/api/iphone/upload` and `/upload` for Shortcut compatibility.
- Add tests for token requirement, repeated upload idempotency, duplicate skip,
  and deleted-marker skip.

### Phase 3b: Dedicated Phone App Discovery

- Add remembered host retry.
- Add optional LAN discovery if needed.
- Upload only unsynced phone asset IDs.
- Keep the computer as the import-state authority.

### Phase 4: Import Page

- Add `static/import.html` and `static/js/pages/import-page.js`.
- Add `zh/en/ja` i18n keys.
- Link the page from the existing navigation.
- Move the current iPhone page behavior under the Device Fallback tab or keep it
  as a temporary legacy page until the new page is stable.

### Phase 5: Run History and Resume

- Add import run history from root workspace DB.
- Show resumable failed/interrupted runs.
- Add explicit retry failed items action.

---

## Test Plan

Backend:

```powershell
~\.virtualenvs\venv\Scripts\python.exe -m pytest tests/test_api_iphone.py tests/test_storage_database.py tests/test_api_boundaries.py
```

New tests to add during implementation:

- `tests/test_api_import.py`
- local source path traversal rejection
- source/destination same-or-child rejection
- duplicate strict hash skip
- deleted marker skip
- phone upload token required
- phone upload idempotent retry
- root-scoped import history isolation

Frontend:

- i18n key alignment for `zh`, `en`, and `ja`
- Import page route loads
- guarded navigation while an import is active
- live log continues polling without blocking first paint

---

## Open Decisions

- Whether paired Phone Sync devices should reconnect automatically after app
  restart or require the desktop app to be open first.
- The initial dedicated mobile upload uses raw bytes plus `X-ZTB-Mobile-Metadata`.
  Revisit multipart only if the app later needs richer streaming/form behavior.
- Whether HEIC support should become an optional install extra after the core
  JPEG/PNG/MOV path is stable.
