from pathlib import Path
from PIL import Image, ExifTags
import os
from typing import Optional, Dict


class MetadataReader:
    """
    读取图像元数据（EXIF、尺寸、时间）。
    """

    def read(self, path: Path) -> Dict:
        result = {
            "timestamp": None,
            "width": None,
            "height": None,
            "hash": None,  # 由 HashCalculator 填充
        }

        # 1. 尺寸
        try:
            with Image.open(path) as img:
                result["width"], result["height"] = img.size
        except Exception:
            pass

        # 2. EXIF 时间
        try:
            with Image.open(path) as img:
                exif = img._getexif()
                if exif:
                    for tag, value in exif.items():
                        decoded = ExifTags.TAGS.get(tag, tag)
                        if decoded == "DateTimeOriginal":
                            result["timestamp"] = value.replace(":", "-", 2)
                            break
        except Exception:
            pass

        # 3. 文件修改时间（作为 fallback）
        if not result["timestamp"]:
            ts = os.path.getmtime(path)
            result["timestamp"] = self._format_timestamp(ts)

        return result

    def _format_timestamp(self, ts: float) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(ts).isoformat()
