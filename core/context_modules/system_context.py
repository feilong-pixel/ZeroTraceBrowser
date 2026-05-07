from .base import *


def open_path_in_file_manager(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return

    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_image_in_system_editor(path: Path) -> None:
    if not sys.platform.startswith("win"):
        raise HTTPException(status_code=501, detail="Image editor opening is only supported on Windows")

    try:
        os.startfile(str(path), "edit")  # type: ignore[attr-defined]
    except OSError:
        subprocess.Popen(["mspaint.exe", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def move_to_system_recycle_bin(path: Path) -> None:
    target = path.expanduser().resolve()
    if not sys.platform.startswith("win"):
        raise HTTPException(status_code=501, detail="System recycle bin is only supported on Windows")

    import ctypes
    from ctypes import wintypes

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

    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0 or operation.fAnyOperationsAborted:
        raise HTTPException(status_code=500, detail=f"Failed to move file to system recycle bin: {result}")


def is_windows() -> bool:
    return sys.platform.startswith("win")
