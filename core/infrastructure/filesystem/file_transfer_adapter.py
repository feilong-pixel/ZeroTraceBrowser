from MediaArchiveOrganizer.core.file_transfer import transfer_file
from pathlib import Path

class FileTransferAdapter:
    def copy(self, src: str, dst: str) -> str:
        src_p = Path(src)
        dst_p = Path(dst)
        transfer_file(src_p, dst_p, "copy")
        return str(dst_p)

    def move(self, src: str, dst: str) -> str:
        src_p = Path(src)
        dst_p = Path(dst)
        transfer_file(src_p, dst_p, "move")
        return str(dst_p)
