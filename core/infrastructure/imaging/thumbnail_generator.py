import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    """
    Generate JPEG thumbnails.
    Thumbnail paths are managed by RootContext.
    """

    def __init__(self, size=(512, 512), quality=85):
        self.size = size
        self.quality = quality

    def generate(self, src: Path, dst: Path):
        """
        Generate a thumbnail and write it to dst.
        """
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(src) as img:
                img.thumbnail(self.size)
                img.convert("RGB").save(dst, "JPEG", quality=self.quality)
        except Exception as exc:
            # Do not raise on thumbnail failure to avoid blocking index builds
            logger.debug("Failed to generate thumbnail for %s -> %s: %s", src, dst, exc)
