from pathlib import Path
from PIL import Image
from typing import Dict
from MediaArchiveOrganizer.core.date_classifier import get_target_date


class MetadataReader:
    """
    Read image metadata (EXIF, dimensions, timestamps).
    """

    def read(self, path: Path) -> Dict:
        result = {
            "timestamp": None,
            "width": None,
            "height": None,
            "hash": None,  # Populated by HashCalculator
        }

        # 1. Dimensions
        try:
            with Image.open(path) as img:
                result["width"], result["height"] = img.size
        except Exception:
            pass

        # 2. Timestamp
        try:
            result["timestamp"] = get_target_date(str(path)).isoformat()
        except Exception:
            pass

        return result
