# SPDX-License-Identifier: MIT

"""Compatibility facade for image scan and file helper services.

New code should import from the focused service modules directly:
``image_scan_service``, ``image_index_service``, ``file_operations``,
``recycle_paths``, and ``thumbnail_service``.
"""

from core.services.file_operations import *
from core.services.image_index_service import *
from core.services.image_scan_service import *
from core.services.recycle_paths import *
from core.services.thumbnail_service import *
