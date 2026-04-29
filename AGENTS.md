# ZeroTraceBrowser – Codex Behavior Rules

---

## 0. Core Philosophy

This project is a:

- lightweight
- controlled-operation
- engineer-oriented image browser

DO NOT introduce:
- implicit behavior
- automatic modification
- hidden logic

All behaviors must be explicit and predictable.

---

## 1. CRITICAL: Timeline (Single Source of Truth)

### 1.1 Definition

timeline_time is the ONLY valid time for:

- sorting
- grouping
- timeline display

---

## 1.2 Source of Truth

timeline_time / target_date MUST be decided ONLY by:

    MediaArchiveOrganizer/core/date_classifier.py

The only allowed decision function is:

    get_target_date(path)

get_target_date(path) uses:

1. get_exif_datetime(path)
2. get_file_datetime(path) fallback

DO NOT duplicate this logic elsewhere.

exif_reader.py is a low-level reader only.
date_classifier.py is the decision layer.

NEVER introduce new time sources.

---

### 1.3 Forbidden Behavior (VERY IMPORTANT)

DO NOT:

- use plt / image libraries to infer time
- parse time from UI text
- use Date.parse in frontend
- derive time from filename unless explicitly approved
- recompute time in frontend

---

## 2. Backend Rules (FastAPI)

All image-related APIs MUST return:

{
  "path": "...",
  "timeline_time": "YYYY-MM-DD HH:mm:ss",
  "timeline_ts": number,
  "timeline_source": "exif | file"
}

---

### 2.1 timeline_ts requirement

- MUST be integer timestamp (seconds)
- MUST be generated in backend
- MUST NOT be recomputed in frontend

---

## 3. Frontend Rules (CRITICAL)

### 3.1 Sorting

All sorting MUST use:

    timeline_ts (number)

NEVER:

- sort by string time
- sort by Date.parse()
- sort by DOM order
- sort during incremental rendering

---

### 3.2 Rendering

Correct:

    fetch → sort → render

Forbidden:

    render → load → append → re-sort

---

### 3.3 Stability Requirement

Sorting MUST be stable:

If timeline_ts is equal:

    fallback → path (string compare)

---

## 4. Module Responsibility

### exif_reader.py
- Low-level metadata reader only
- MAY read EXIF datetime
- MAY read file mtime
- MUST NOT decide UI sorting or timeline grouping

### date_classifier.py
- The only decision layer for image date
- MUST provide the canonical date used by organizing / timeline logic
- MUST use get_target_date(path)

### image API
- MUST expose backend-generated:
  - timeline_time
  - timeline_ts
  - timeline_source if available

### frontend
- MUST NOT compute image date
- MUST NOT parse display date strings
- MUST sort only by numeric timeline_ts

---

## 5. Error Handling

If EXIF is invalid:

- fallback to file mtime
- DO NOT return None in API

---

## 6. Performance Rules

- EXIF reading should be minimal (details=False already correct)
- Avoid re-reading EXIF multiple times for same file
- Prefer caching if needed

---

## 7. Code Quality Rules

- No duplicate time parsing logic
- All datetime parsing MUST go through:

    _parse_exif_datetime()

- Do NOT introduce new datetime formats without updating parser

---

## 8. Anti-Pattern Checklist (Codex MUST avoid)

❌ Multiple time sources  
❌ Frontend computing time  
❌ Sorting inside render loop  
❌ Using UI string as data  
❌ Implicit fallback logic  
❌ Hidden behavior  

---

## 9. Change Safety Rule

If modifying:

- exif_reader.py
- date_classifier.py
- image API

You MUST:

1. verify timeline consistency
2. ensure no second time source introduced

---

## 10. Design Principle Reminder

This system prioritizes:

- predictability over automation
- safety over convenience
- explicit logic over magic
