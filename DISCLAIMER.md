# ZeroTraceBrowser Disclaimer

## 1. Risk Notice

ZeroTraceBrowser is a local image browsing and controlled file-operation tool.

This tool does not automatically organize, delete, or move files on behalf of the user. Copying, deletion, batch operations, recycle cleanup, and root history cleanup must all be explicitly triggered by the user.

Although this tool is designed to handle files in a predictable and recoverable way, actual use may still be affected by file permissions, incorrect path settings, disk conditions, file locks, unexpected interruptions, system limitations, third-party library behavior, or other unforeseen factors. As a result, the following situations may occur:

- File operation results do not match expectations
- File copy operations fail or copy files to unintended locations
- Files moved into the app-level recycle area cannot be restored as expected
- Thumbnails, indexes, logs, or task results are incomplete
- Duplicate detection results are inaccurate or incomplete
- In extreme cases, files may be lost, overwritten, unrecoverable, or runtime data may become damaged

## 2. User Responsibility

Before performing operations, users are responsible for confirming the following:

- The image root directory is configured correctly
- The default copy target directory is configured correctly
- The currently selected items are truly the files the user intends to process
- Important files have been backed up in advance
- Related directories have the required read/write permissions
- Sufficient disk space is available
- The difference between "copy", "delete to app-level recycle area", and "clean recycle area" is clearly understood

For valuable files, it is recommended to verify the workflow first with a small set of test files or a test directory.

## 3. Safe Delete and App-level Recycle Area

ZeroTraceBrowser's delete operation is a safe delete by default: files are moved into ZeroTraceBrowser's app-level recycle area instead of being permanently removed from disk immediately.

The app-level recycle area is not the same as the Windows system Recycle Bin.

This means:

- Deleted files are stored inside runtime data managed by ZeroTraceBrowser
- Users can attempt to restore files from the Recycle page
- If the app-level recycle area is cleaned, files may no longer be recoverable through ZeroTraceBrowser
- If the runtime data directory is manually deleted, moved, or damaged, restore functionality may stop working

Before cleaning the recycle area, make sure the files inside it are no longer needed.

## 4. Runtime Data

ZeroTraceBrowser stores separate runtime data for each image root under `data/roots/<hash_id>/`, including but not limited to:

- Thumbnail cache
- Image index
- Timeline index
- Operation logs
- App-level recycle files
- Duplicate detection results
- Task outputs

This data is used to improve browsing speed, preserve operation history, and isolate state between image roots.

When removing an image root on the Settings page and choosing to clean related data, the derived data listed above may be deleted. This operation does not actively delete original image files inside the original image directory, but it does affect thumbnails, indexes, logs, recycle files, duplicate results, task history, and other runtime data.

Do not manually delete or move files under `data/roots/<hash_id>/` unless you clearly understand the impact.

## 5. Date Detection and Timeline

ZeroTraceBrowser's timeline sorting and grouping depend on backend-generated `timeline_time` / `timeline_ts`.

The time source is determined by the following rules:

1. Image EXIF time is used first
2. If EXIF time cannot be read, file time is used as a fallback

Therefore, timeline display, sorting, grouping, and related task results depend on the accuracy of the file's own time metadata.

If EXIF data is incorrect or missing, or if file time has been changed by the operating system, sync tools, copy tools, compression software, or other programs, the displayed timeline may not match the true capture time.

## 6. Duplicate Detection

Duplicate detection results are provided only as operational reference and do not constitute absolute judgment.

- `strict` mode only treats byte-identical files as duplicates
- `phash` mode is based on visual similarity and does not guarantee that two files are identical in business, legal, or archival meaning
- Image size, compression method, cropping, filters, screenshots, watermarks, metadata changes, and other factors may affect detection results
- Even when the program marks files as duplicates, users should manually review important materials

ZeroTraceBrowser does not automatically delete files based on duplicate detection results. Whether to delete, copy, or keep files must be decided and explicitly operated by the user.

## 7. Logs, Indexes, and Thumbnails

ZeroTraceBrowser generates logs, image indexes, timeline indexes, and thumbnail caches, but this data is only intended to assist browsing, troubleshooting, and record keeping.

This data does not guarantee:

- File operations always succeed
- Operation records are always complete
- Indexes always reflect every disk change in real time
- Thumbnails always match the current state of the original images
- Deleted files are always recoverable

If external programs modify the image directory at the same time, or if users manually move, delete, or rename files, the state shown in ZeroTraceBrowser may require refresh, rescan, or index regeneration before it reflects the latest disk state.

## 8. Third-party Libraries and Runtime Environment

This tool depends on runtime components such as Python, FastAPI, Pillow, the browser, and the operating system file system.

Behavior may vary depending on the operating system, disk, permission settings, file format, image metadata, and third-party library versions.

For damaged files, abnormal EXIF data, special image formats, very large images, or permission-restricted files, this tool may fail to read files, generate thumbnails, display metadata, or perform file operations correctly.

## 9. Limitation of Liability

This tool is provided "as is" without any express or implied warranty.

The developer or provider is not liable for:

- Direct or indirect losses caused by using or being unable to use this tool
- Misplaced, overwritten, deleted, or lost files caused by user mistakes
- Losses caused by users not backing up important data
- Failures caused by the operating system, permissions, hardware, disks, third-party libraries, or runtime environment
- Incorrect decisions caused by inaccurate date detection, duplicate detection, index cache, or thumbnail cache
- Unrecoverable problems caused by users manually modifying runtime data directories

## 10. No Professional or Compliance Advice

This tool is only a local image browsing and file-operation helper. It does not constitute legal advice, compliance advice, records management advice, evidence preservation advice, or any other professional advice.

If your files involve legal retention, regulatory requirements, evidentiary materials, business compliance, medical records, financial records, or other high-risk use cases, you should perform additional evaluation, backup, and verification before use.

## 11. Recommended Safe Usage

To reduce risk, it is recommended to use this tool as follows:

1. Use a test directory or a small set of test files for first-time use
2. Back up important images and videos before formal processing
3. Confirm the image root and copy target directories on the Settings page
4. Perform a small number of copy or delete operations first and confirm the results
5. After deleting files, confirm on the Recycle page that the files can be viewed or restored normally
6. Before cleaning the app-level recycle area, confirm each file is no longer needed
7. When handling duplicate images, review them manually before deleting or running batch operations
8. Do not manually delete or move runtime data under `data/roots/<hash_id>/` unless you clearly understand the impact

## 12. Final Statement

By running or using ZeroTraceBrowser, you acknowledge and accept the risks and limitations described above.
