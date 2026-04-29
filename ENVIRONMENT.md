# ZeroTraceBrowser Environment Setup

## 1. Overview

ZeroTraceBrowser is a local image browsing and controlled file-operation tool built with Python and FastAPI.

It provides a local Web interface for:

- Browsing local image folders
- Viewing images and basic metadata
- Generating thumbnail caches
- Sorting and grouping images by timeline
- Copying images to a target directory
- Moving images into the app-level recycle area
- Generating Hash DB and duplicate detection results
- Managing the app-level recycle area and runtime data

This project is intended for local use. It does not require a database, cloud service, or external account.

## 2. Recommended Environment

- Operating system: Windows 10 or Windows 11
- Python: 3.10 or later
- Terminal: PowerShell
- Browser: Microsoft Edge, Chrome, Firefox, or another modern browser

It is recommended to use a repo-local virtual environment under the project root:

```text
.\venv\
```

This prevents dependencies from being installed into the system Python or another project's virtual environment.

## 3. Python Dependencies

Dependencies are managed by `requirements.txt`. The current dependency set includes:

- `fastapi`
- `uvicorn[standard]`
- `Pillow`
- `exifread`
- `pywin32` (Windows)
- `pytest`
- `httpx`

Purpose:

- `FastAPI`: backend Web API
- `uvicorn`: local Web server runner
- `Pillow`: image loading, thumbnail generation, and partial metadata handling
- `exifread`: EXIF metadata reading
- `pywin32`: Windows system file operations such as preserving file times
- `pytest`: automated tests
- `httpx`: test client dependency

## 4. Create a Virtual Environment

Open PowerShell in the project root:

```powershell
cd D:\path\to\ZeroTraceBrowser
```

Create the virtual environment:

```powershell
python -m venv venv
```

After creation, the project directory will contain:

```text
venv\
```

Common paths:

```text
.\venv\Scripts\python.exe
.\venv\Scripts\pip.exe
```

If you want to activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, allow it temporarily for the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
```

However, this project recommends using `.\venv\Scripts\python.exe` directly. This makes it clear that you are using the project's own Python even if the virtual environment is not activated.

## 5. Install Dependencies

Use the explicit Python path:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Optional: upgrade pip before installation:

```powershell
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Verify the core dependencies:

```powershell
.\venv\Scripts\python.exe -c "import fastapi, uvicorn; from PIL import Image; print('Environment OK')"
```

If you want to verify EXIF and Windows file-operation dependencies separately:

```powershell
.\venv\Scripts\python.exe -c "import exifread; print('exifread OK')"
.\venv\Scripts\python.exe -c "import win32file, win32con; print('pywin32 OK')"
```

`pywin32` is only needed on Windows. This project is recommended for Windows 10 / Windows 11.

## 6. Start the Server

Recommended:

```powershell
.\start.ps1
```

The script starts the server from the project root with:

```powershell
.\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

You can also run the command manually:

```powershell
.\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

When startup succeeds, the terminal usually shows something like:

```text
Uvicorn running on http://127.0.0.1:8000
```

Then open this URL in your browser:

```text
http://127.0.0.1:8000
```

## 7. Port

The default port is:

```text
8000
```

If the port is already in use, temporarily start the server on another port, for example:

```powershell
.\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
```

Then open:

```text
http://127.0.0.1:8001
```

Note: `start.ps1` currently uses port `8000`.

## 8. Run Tests

Recommended:

```powershell
.\test.ps1
```

The script runs:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

You can also run pytest directly:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

## 9. Main Files and Directories

```text
ZeroTraceBrowser/
├── app.py                      # FastAPI application entry point
├── requirements.txt            # Python dependencies
├── settings.json               # Local settings
├── start.ps1                   # Startup script
├── test.ps1                    # Test script

├── static/                     # Frontend pages, CSS, JavaScript
├── ztb/                        # Backend services and routes
├── MediaArchiveOrganizer/      # Image analysis and organization modules
├── tests/                      # Automated tests
├── data/                       # Runtime data
├── logs/                       # Logs
└── thumbnails/                 # Legacy or compatibility thumbnail directory
```

Primary runtime data is isolated by image root under:

```text
data/roots/<hash_id>/
```

It may contain:

- `deleted/`: app-level recycle area
- `thumbnails/`: thumbnail cache
- `logs/`: operation logs
- `indexes/`: image index and timeline index
- `tasks/`: task outputs
- `duplicates.json`: duplicate image results
- `hash_db.json`: Hash DB

## 10. Local Settings File

Project settings are stored in:

```text
settings.json
```

Common settings include:

- Current image root
- List of added image roots
- Default copy target directory
- Language setting
- Task page defaults
- Summary data for each image root

Prefer changing settings through the Settings page. Do not manually edit `settings.json` unless you understand its format.

## 11. Common Environment Problems

### Python is not recognized

If PowerShell cannot find `python`, check that:

- Python is installed
- Python is added to the system `PATH`
- Or use the Python Launcher: `py -m venv venv`

### Dependencies were installed into the wrong environment

Always prefer:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Do not rely only on `pip install ...`, because it may point to the system Python or another environment.

Check the current Python:

```powershell
.\venv\Scripts\python.exe -c "import sys; print(sys.executable)"
```

### Pillow / exifread / pywin32 is missing or fails to import

If you see errors related to `PIL`, `exifread`, `win32file`, or `win32con`, reinstall dependencies:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

You can also check whether packages are installed in the current virtual environment:

```powershell
.\venv\Scripts\python.exe -m pip show Pillow
.\venv\Scripts\python.exe -m pip show exifread
.\venv\Scripts\python.exe -m pip show pywin32
```

### PowerShell cannot run scripts

If `Activate.ps1`, `start.ps1`, or `test.ps1` is blocked by execution policy, run this in the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
```

Then run the script again.

### Port 8000 is already in use

If startup fails because the port is already in use:

1. Stop the currently running ZeroTraceBrowser service
2. Or start manually with another port:

```powershell
.\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
```

### The page still looks old after changes

If frontend JS, CSS, or backend code was changed but the browser still shows old behavior:

1. Restart the Uvicorn service
2. Refresh the browser page
3. Use a hard refresh if needed

Backend code changes usually require restarting the server.

### Images do not display or thumbnails load slowly

When opening a large image directory for the first time, thumbnails may need to be generated. The first load can be slower. Later visits usually hit the cache.

If images do not display, check that:

- The image root exists
- The current user has read permissions
- The file format is supported
- The server terminal does not show related errors

## 12. Recommended First-time Setup

1. Open PowerShell in the project root
2. Create the virtual environment:

   ```powershell
   python -m venv venv
   ```

3. Install dependencies:

   ```powershell
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Start the server:

   ```powershell
   .\start.ps1
   ```

5. Open the browser:

   ```text
   http://127.0.0.1:8000
   ```

6. Open the Settings page and add an image root
7. Configure the default copy target directory if needed
8. Return to the Gallery page and start browsing
9. To verify the project state, run:

   ```powershell
   .\test.ps1
   ```

## 13. Safety Recommendations

- Use the current version only on your local machine or in a trusted LAN
- Do not expose the service directly to the public internet
- Back up important image folders before batch operations
- After deleting files, confirm on the Recycle page that they can be restored
- Before cleaning the app-level recycle area, confirm the files are no longer needed
- Do not casually delete runtime data under `data/roots/<hash_id>/`

## 14. Quick Command Summary

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

Tests:

```powershell
.\test.ps1
```

Manual start:

```powershell
.\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```
