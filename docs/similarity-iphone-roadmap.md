# Similarity and iPhone Import Roadmap

This document captures the first implementation plan for three related features:

- Document-like similar photo search
- iPhone photo import
- iPhone imported-photo similarity review

For the current production import design, use `docs/photo-import-design.md`.
This roadmap keeps the similarity and earlier iPhone import direction for
historical context.

The goal is to keep ZeroTraceBrowser local-first, explicit, and safe while adding stronger visual similarity workflows.

---

## 1. Similar Photo Search

### Target Use Case

The primary target is not ordinary duplicate photos only. It includes document-like work records such as attendance screenshots, forms, receipts, and repeated business records.

These images may look semantically similar without being exact duplicates:

- Same template, different names or dates
- Same attendance screen, different day
- Same document layout, small text changes
- Similar phone screenshots with different record content

### Product Rule

Deep document embedding is not the default full-gallery scan path.

The first implementation should be:

```text
Select one image -> Find similar images in the current root
```

This avoids expensive background processing and keeps user intent explicit.

### Detection Layers

Use a staged similarity pipeline:

1. Existing pHash
   - Fast visual similarity.
   - Good for normal near-duplicate photos.
   - Already implemented.

2. Lightweight metadata and shape filters
   - File type.
   - Image dimensions.
   - Aspect ratio.
   - Optional capture/source metadata.

3. Optional deep embedding
   - Only for selected-image search.
   - Not required for the first DB/API skeleton.

Candidate models to evaluate later:

- CLIP
- DINOv2
- LayoutLMv3
- Donut / OCR-free document model

The first production-friendly choice should favor local inference, simple installation, and predictable runtime behavior.

### Storage Direction

Similarity data should be root-scoped:

```text
data/roots/<root_id>/workspace.sqlite3
```

Suggested tables for a later implementation:

```text
similarity_embeddings
- id
- relative_path
- model_name
- model_version
- vector
- file_size
- mtime_ns
- updated_at

similarity_search_cache
- id
- query_relative_path
- model_name
- result_json
- updated_at
```

Vector format can start as JSON or binary blob. Do not add a vector database until SQLite becomes a measured bottleneck.

### First API Shape

```text
POST /api/similarity/search
```

Input:

```json
{
  "relative_path": "2026/05/13/sample.jpg",
  "method": "phash",
  "limit": 50
}
```

Future method values:

```text
phash
embedding
hybrid
```

Output:

```json
{
  "query": "...",
  "method": "phash",
  "items": [
    {
      "relative_path": "...",
      "score": 0.92,
      "reason": "phash"
    }
  ]
}
```

---

## 2. iPhone Photo Import

### Target Use Case

Import iPhone photos into a configured local folder without automatic deletion or destructive changes.

Initial scope:

- User selects an import source directory.
- User selects an import destination directory.
- The app copies supported media files.
- The app preserves file times when possible.
- The app writes an import log.
- The app does not delete source files.

### Supported Inputs

Start with normal filesystem-visible imports:

- iPhone exported folder
- DCIM copied from iPhone
- iCloud Photos local export

Do not start with direct MTP/iPhone device browsing unless it becomes necessary. Direct device access is platform-sensitive and harder to test.

### Import Direction

The preferred long-term direction is a local Wi-Fi import loop:

```text
ZeroTraceBrowser requests the next small batch
  -> phone app uploads the requested originals over local Wi-Fi
  -> ZeroTraceBrowser hashes, dedupes, imports, and records results
  -> ZeroTraceBrowser requests the next batch
```

Keep the local app in control of import state, target paths, strict hash checks,
deleted-local markers, and audit logs. The phone-side tool should only select
and upload original media bytes. It should not delete photos, choose final local
paths, or decide duplicate policy.

The first production path should be HTTP upload over the LAN, using paired
device identity and small batches. Direct iPhone MTP browsing should remain a
fallback or experimental path for device probing and small manual recovery
imports, not the main large-library import mechanism.

### Batch Rules

Use small batches, for example 5 items, until reliability is proven:

- Each uploaded item is acknowledged individually.
- Imported, strict-duplicate, already-imported, deleted-local, and failed states
  are persisted in the root workspace.
- A completed mobile reference is skipped by later batches, even when the
  strict duplicate points to a differently named local file.
- If transfer stops, the next session resumes from persisted mobile import
  records rather than trusting client memory alone.

### Import Behavior

Default behavior:

```text
source files -> copy -> destination folder
```

Recommended destination layout:

```text
<destination>/
  YYYY/
    MM/
      DD/
        original-file
```

Date source priority:

1. EXIF capture time
2. File modified time
3. Import time

### iPhone-Specific Handling

Later phases can add:

- HEIC support
- Live Photo pairing
- MOV sidecar pairing
- Burst photo grouping
- Screenshot detection
- Timezone normalization

HEIC support may require an optional dependency. Do not add it to the base requirements until the import path is proven.

### First API Shape

```text
POST /api/import/iphone
```

Input:

```json
{
  "src": "D:/iPhone/DCIM",
  "dst": "D:/Photos/iPhone",
  "mode": "copy",
  "dedupe": "skip_same_name"
}
```

The first version should only support `copy`.

---

## 3. iPhone Similarity Review

### Target Use Case

After importing iPhone photos, the user wants to find similar photos against the existing image root.

Initial workflow:

```text
Import iPhone folder -> open import result -> select image -> find similar
```

Do not automatically delete or move similar results.

### Review UI

A practical first UI can be added to the viewer:

- Current image preview
- Similar candidates list
- Score / method label
- Open candidate
- Copy path
- Optional move duplicate to recycle for strict-safe matches only

For embedding-based semantic matches, bulk delete should stay disabled.

---

## Implementation Phases

### Phase 1: Similarity API Skeleton

- Add a root-scoped similarity route.
- Implement `phash` query using existing hash DB records.
- Add viewer entry point: selected image -> similar results.
- No new ML dependency.

### Phase 2: iPhone Import Skeleton

- Add an import route and use case.
- Copy supported files from a selected folder.
- Preserve file times.
- Write task-style import log.
- No source deletion.

### Phase 3: iPhone Import Page or Task Panel

- Add UI for source, destination, and import run status.
- Reuse task-style progress patterns.
- Add i18n keys.

### Phase 4: Embedding Experiment

- Add optional local embedding provider behind a feature flag.
- Store embeddings in root SQLite.
- Start with selected-image search only.
- Compare CLIP and DINOv2 on real document-like images.

### Phase 5: iPhone Similarity Review

- After import, surface a review workflow for selected images.
- Keep automatic destructive actions disabled.

---

## Safety Rules

- No cloud upload.
- No automatic deletion.
- iPhone import is copy-only at first.
- Similarity results are suggestions, not authority.
- Embedding dependencies must be optional.
- Runtime data remains under `data/roots/<root_id>/`.

