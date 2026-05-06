# SPDX-License-Identifier: MIT

"""
Lightweight platform utilities that can be imported by use cases
without pulling in HTTPException or FastAPI dependencies.

For the full-featured versions (with HTTPException on unsupported OS)
see ``core.context_modules.system_context``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def is_windows() -> bool:
    """Return ``True`` when running on Windows."""
    return sys.platform.startswith("win")


def default_dispose_fn() -> Callable[[Path], None]:
    """
    Return the appropriate file disposal callable for the current platform.

    - On Windows: move to system Recycle Bin (via ``shell32.SHFileOperationW``).
    - On other platforms: permanent unlink (``path.unlink()``).

    This function raises no HTTPException; it is intended for use in
    use cases where disposal behaviour is injected via ``dispose_fn``.
    """
    import ctypes
    from ctypes import wintypes

    if not is_windows():
        return lambda p: p.unlink()

    def _move_to_recycle_bin(path: Path) -> None:
        target = path.expanduser().resolve()

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", wintypes.WORD),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", wintypes.LPVOID),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        FO_DELETE = 0x0003
        FOF_SILENT = 0x0004
        FOF_NOCONFIRMATION = 0x0010
        FOF_ALLOWUNDO = 0x0040
        FOF_NOERRORUI = 0x0400

        operation = SHFILEOPSTRUCTW()
        operation.hwnd = None
        operation.wFunc = FO_DELETE
        operation.pFrom = f"{target}\0\0"
        operation.pTo = None
        operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT

        ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))

    return _move_to_recycle_bin
