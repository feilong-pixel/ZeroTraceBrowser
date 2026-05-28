# SPDX-License-Identifier: MIT

import os
import shutil
import platform
from pathlib import Path

# Try importing pywin32; fall back when it is unavailable.
try:
    import win32file
    import win32con
    import pywintypes
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

def is_windows():
    return platform.system() == "Windows"

def read_windows_file_times(path: Path):
    """Read Windows file timestamps as FILETIME tuples."""
    if not is_windows():
        return None

    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x00000080,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        return None

    try:
        created = FILETIME()
        accessed = FILETIME()
        written = FILETIME()
        ok = kernel32.GetFileTime(
            handle,
            ctypes.byref(created),
            ctypes.byref(accessed),
            ctypes.byref(written),
        )
        if not ok:
            return None
        return (
            (created.dwLowDateTime, created.dwHighDateTime),
            (accessed.dwLowDateTime, accessed.dwHighDateTime),
            (written.dwLowDateTime, written.dwHighDateTime),
        )
    finally:
        kernel32.CloseHandle(handle)


def apply_windows_file_times(path: Path, times):
    """Apply Windows file timestamps from FILETIME tuples."""
    if not is_windows() or times is None:
        return

    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateFileW(
        str(path),
        0x40000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x00000080,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        return

    try:
        created = FILETIME(times[0][0], times[0][1])
        accessed = FILETIME(times[1][0], times[1][1])
        written = FILETIME(times[2][0], times[2][1])
        kernel32.SetFileTime(
            handle,
            ctypes.byref(created),
            ctypes.byref(accessed),
            ctypes.byref(written),
        )
    finally:
        kernel32.CloseHandle(handle)


def transfer_file(src: Path, dst: Path, mode: str):
    src, dst = Path(src), Path(dst)
    
    if not src.exists():
        raise FileNotFoundError(f"Source file does not exist: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    # 1. Read timestamps before transfer.
    file_times = read_windows_file_times(src)

    # 2. Transfer the file.
    try:
        if mode == "copy":
            shutil.copy2(src, dst)
        elif mode == "move":
            # Check whether the move stayed on the same device.
            src_stat = src.stat()
            shutil.move(str(src), str(dst))
            
            # Same-device moves usually preserve creation time.
            try:
                if dst.exists() and dst.stat().st_dev == src_stat.st_dev:
                    return
            except Exception:
                pass
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        # 3. Restore timestamps when needed.
        apply_windows_file_times(dst, file_times)

    except PermissionError as exc:
        raise PermissionError(f"Permission denied: {src}") from exc
