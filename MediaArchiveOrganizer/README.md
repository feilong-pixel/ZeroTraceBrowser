# Media Archive Organizer

An advanced media organization tool for users who need duplicate detection, stricter matching, and more controllable archiving workflows.

The program reads image EXIF time first. If EXIF time is unavailable, it falls back to the file's modified time.
Organized files are placed into the target directory using a `year\month\day` folder structure.

It supports:

- date-based folder organization
- move or copy modes
- perceptual duplicate detection for similar images
- strict SHA-256 duplicate detection for exact file matches
- multilingual CLI messages
- per-run log output for traceability

Language navigation:

- English: [README.md](./README.md)
- 中文: [README_zh.md](./README_zh.md)
- 日本語: [README_ja.md](./README_ja.md)


## Positioning

This project is intended for advanced usage.

Compared with a basic date-based organizer, it adds:

- duplicate detection
- strict exact-file matching
- perceptual image matching with threshold control
- persistent hash database
- stronger destination safety rules
- automated smoke tests

If you only need simple date-based sorting with minimal complexity, a basic organizer may be a better fit.


## Features

- Recursively scans subfolders in the source directory
- Organizes images and videos by date automatically
- Uses `move` mode by default
- Supports `copy` mode to keep original files
- Supports duplicate detection: off, perceptual image matching (`phash`), or strict file matching (`SHA-256`)
- Supports Chinese, English, and Japanese UI
- Generates a separate log file for each run
- Automatically appends a numeric suffix for duplicate file names
- Renames detected duplicates as `kept_name_dupN.ext` so they stay grouped in the archive
- Generates `duplicate_report.csv` for duplicate traceability
- Generates `duplicates.json` for structured duplicate results that other tools can read


## Supported File Types

- `.jpg`
- `.jpeg`
- `.png`
- `.mp4`
- `.mov`


## Environment

- Windows 10 or Windows 11
- Python 3.10 or later
- Dependency: `Pillow`, `exifread`, `pywin32` (Windows only)

Install dependency:

```powershell
.\venv\Scripts\python.exe -m pip install Pillow exifread pywin32
```

Notes:

- It is recommended to create the virtual environment first with `python -m venv venv` from the project root
- The project virtual environment is typically located at `.\venv`
- Prefer `.\venv\Scripts\python.exe` and `.\venv\Scripts\pip.exe` so you always know where dependencies are being installed
- If you run plain `python` or `pip`, you may accidentally use the global Python installation or another virtual environment


## Basic Usage

Enter the project root first, then run the command:

```powershell
cd D:\01_wk\16_person\ZeroTraceBrowser\MediaArchiveOrganizer
```

Recommended command:

```powershell
.\venv\Scripts\python.exe .\main.py --src SOURCE_DIR --dst TARGET_DIR
```

Example:

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos
```


## Arguments

### `--src`

Source directory. Required.

### `--dst`

Destination directory. Required.

### `--mode`

Organization mode:

- `move`: move files, default
- `copy`: copy files and keep originals

Example:

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --mode copy
```

### `--lang`

Interface language:

- `zh`: Chinese
- `en`: English
- `ja`: Japanese

Example:

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --lang en
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --lang ja
```

### `--duplicate-detection`

Duplicate detection mode:

- `off`: disable duplicate detection
- `phash`: detect visually similar images with perceptual hash
- `strict`: detect exact file matches with SHA-256

Notes:

- `phash` is suitable for visually similar images
- `strict` is for exact-match users who only want byte-identical files treated as duplicates
- `hash_db` is only used as a hint inside the current destination root and will not redirect files into old destination folders
- Detected duplicates are still copied or moved into the normal dated archive folder
- Duplicate files are renamed based on the first retained file name, such as `photo_dup1.jpg` and `photo_dup2.jpg`
- Each run appends duplicate reference rows to `duplicate_report.csv` in the same folder as the run log
- Each run also writes `duplicates.json` in the same folder as the run log for structured duplicate groups

Example:

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection off
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection strict
```

### `--phash-threshold`

Sets the maximum Hamming distance for perceptual hash matching. The default is `4`.

Notes:

- Lower values are stricter
- Higher values make similar images more likely to be treated as duplicates
- This option only applies when `--duplicate-detection phash` is used

Example:

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection phash --phash-threshold 4
```

### `--rebuild-hash-db-root`

Rebuilds `hash_db.json` from the specified organized archive root.

Notes:

- `--src` and `--dst` are not required when this option is used
- The rebuild scans supported media files under the specified root
- This command rebuilds only `hash_db.json`; `duplicates.json` is generated during normal organization runs when duplicates are detected

Example:

```powershell
.\venv\Scripts\python.exe .\main.py --rebuild-hash-db-root D:\SortedPhotos
```

### `--rebuild-hash-db-mode`

Sets how `hash_db.json` is rebuilt:

- `replace`: rebuild from scratch, default
- `append`: keep existing records and append new records

Example:

```powershell
.\venv\Scripts\python.exe .\main.py --rebuild-hash-db-root D:\SortedPhotos --rebuild-hash-db-mode append
```

### `--rebuild-hash-method`

Sets which hash records are rebuilt:

- `strict`: rebuild only SHA-256 exact-match records
- `phash`: rebuild only pHash visual-similarity records
- `both`: rebuild both record types, default

Example:

```powershell
.\venv\Scripts\python.exe .\main.py --rebuild-hash-db-root D:\SortedPhotos --rebuild-hash-method both
```


## Common Examples

### Move files by default

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos
```

### Copy files and keep originals

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --mode copy
```

### Use English UI

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --lang en
```

### Use Japanese UI

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --lang ja
```

### Use strict duplicate detection

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection strict
```

### Use perceptual duplicate detection

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection phash --phash-threshold 4
```

### Rebuild hash_db from an organized archive

```powershell
.\venv\Scripts\python.exe .\main.py --rebuild-hash-db-root D:\SortedPhotos --rebuild-hash-db-mode replace --rebuild-hash-method both
```


## Logs

The program automatically creates or reuses the `log` folder under the script directory.

Log file names use this format:

```text
organize_log_YYYYMMDD_HHMMSS.txt
```

Example:

```text
organize_log_20260413_135222.txt
```

After execution, the program prints the full path of the generated log file.

When duplicates are detected, the program also appends records to:

```text
duplicate_report.csv
```

It also writes structured duplicate results to:

```text
duplicates.json
```

The report is created in the same folder as the run log and currently includes:

- `original_name`
- `original_path`
- `kept_path`
- `duplicate_method`
- `hash`
- `duplicate_path`


## Organization Rules

- Recursively scans all subfolders in the source directory
- Uses image EXIF time first
- Falls back to file modified time when EXIF is unavailable
- Outputs files to `target\year\month\day\`
- When duplicate detection is enabled, only records inside the current destination root are used as matches
- Adds a numeric suffix if a file with the same name already exists
- Duplicate files are still placed into the normal dated archive folder
- Duplicate files are renamed from the retained file name using `_dupN`

Duplicate name example:

```text
photo.jpg
photo_1.jpg
photo_2.jpg
```

Duplicate detection naming example:

```text
photo.jpg
photo_dup1.jpg
photo_dup2.jpg
```


## Project Structure

- `main.py`
  Program entry point
- `core/`
  Date detection and EXIF reading logic
- `services/`
  File organization logic
- `locales/`
  Chinese, English, and Japanese UI texts
- `log/`
  Log output folder for each run


## Notes

- Make sure the source and destination paths are correct
- The destination must not be the source directory itself or a directory inside the source
- Default `move` mode removes files from the source directory
- Use `--mode copy` if you need to keep original files
- It is recommended to test with a small number of files first
- Back up important files before large batch processing


## Common Failure Causes

- File is in use and cannot be moved or copied
- File permission is insufficient
- Image EXIF data is invalid
- Destination directory is not writable


## Disclaimer

This tool is intended to automatically organize image and video files.
In actual use, the result may still differ from expectations due to incorrect paths, permission problems, file locks, disk issues, invalid time metadata, interrupted execution, or other unforeseen factors.

Please note:

- Default `move` mode moves original files
- Duplicate file names are automatically renamed
- If EXIF time or file time is inaccurate, the destination date folder may not match the real capture date
- Logs are only for assistance and do not guarantee completeness of results

To reduce risk:

1. Test with a small set of files first
2. Prefer `--mode copy` for verification
3. Back up important data before full processing
4. Check both the log and destination folders after execution
