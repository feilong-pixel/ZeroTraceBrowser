from pathlib import Path
from PIL import Image


class ThumbnailGenerator:
    """
    生成缩略图（JPEG）。
    ZeroTraceBrowser 的缩略图路径由 RootContext 决定。
    """

    def __init__(self, size=(512, 512), quality=85):
        self.size = size
        self.quality = quality

    def generate(self, src: Path, dst: Path):
        """
        生成缩略图到 dst。
        """
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(src) as img:
                img.thumbnail(self.size)
                img.convert("RGB").save(dst, "JPEG", quality=self.quality)
        except Exception:
            # 缩略图生成失败时不抛异常，避免阻塞 index 构建
            pass
