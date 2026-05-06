from pathlib import Path
from typing import Optional


class FileRepository:
    """
    ZeroTraceBrowser 的文件操作仓库层。
    所有文件操作（copy/move/delete/restore）都必须通过
    infrastructure 层的 FileTransferAdapter（内部调用 transfer_file）。
    """

    def __init__(self, file_transfer_adapter, root_context, metadata_reader=None):
        self.transfer = file_transfer_adapter
        self.ctx = root_context
        self.metadata_reader = metadata_reader  # 可选：用于读取 EXIF、尺寸等

    # ---------------------------------------------------------
    # 基础操作：复制
    # ---------------------------------------------------------
    def copy(self, src: str, dst: str) -> str:
        """
        复制文件（底层使用 transfer_file）
        """
        src_p = Path(src)
        dst_p = Path(dst)

        dst_p.parent.mkdir(parents=True, exist_ok=True)
        # self._ensure_parent_exists(dst_p)
        self.transfer.copy(src_p, dst_p)

        return str(dst_p)

    # ---------------------------------------------------------
    # 基础操作：移动
    # ---------------------------------------------------------
    def move(self, src: str, dst: str) -> str:
        """
        移动文件（底层使用 transfer_file）
        """
        src_p = Path(src)
        dst_p = Path(dst)

        dst_p.parent.mkdir(parents=True, exist_ok=True)
        # self._ensure_parent_exists(dst_p)
        self.transfer.move(src_p, dst_p)

        return str(dst_p)

    # ---------------------------------------------------------
    # 安全删除（移动到回收站）
    # ---------------------------------------------------------
    def safe_delete(self, src: str) -> str:
        """
        ZeroTraceBrowser 的删除不是删除，而是移动到 deleted/ 目录。
        """
        src_p = Path(src)
        deleted_path = self.ctx.deleted_path_for(src_p)

        deleted_path.parent.mkdir(parents=True, exist_ok=True)
        # self._ensure_parent_exists(deleted_path)
        self.transfer.move(src_p, deleted_path)

        return str(deleted_path)

    # ---------------------------------------------------------
    # 恢复文件（从回收站恢复）
    # ---------------------------------------------------------
    def restore(self, deleted_path: str) -> str:
        """
        从 deleted/ 恢复到原始路径。
        """
        deleted_p = Path(deleted_path)
        original_path = self.ctx.original_path_for(deleted_p)

        original_path.parent.mkdir(parents=True, exist_ok=True)
        # self._ensure_parent_exists(original_path)
        self.transfer.move(deleted_p, original_path)

        return str(original_path)

    # ---------------------------------------------------------
    # 扫描图片（用于 index 构建）
    # ---------------------------------------------------------
    def scan_images(self, root_path: str):
        """
        扫描目录下所有图片文件。
        """
        root = Path(root_path)
        exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

        for p in root.rglob("*"):
            if p.suffix.lower() in exts and p.is_file():
                yield p

    # ---------------------------------------------------------
    # 读取元数据（可选）
    # ---------------------------------------------------------
    def read_metadata(self, path: str) -> Optional[dict]:
        """
        读取图片元数据（如果 metadata_reader 存在）
        """
        if not self.metadata_reader:
            return None
        return self.metadata_reader.read(Path(path))

    # ---------------------------------------------------------
    # 工具函数
    # ---------------------------------------------------------
    def _ensure_parent_exists(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
