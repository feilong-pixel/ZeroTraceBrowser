"""Compatibility facade for route/context helpers.

The implementation has been split into focused modules under
``core.context_modules``.  Keep importing through ``core.context`` from routes
until all call sites are migrated deliberately.
"""

from core.context_modules.system_context import *
from core.context_modules.settings_context import *
from core.context_modules.root_workspace import *
from core.context_modules.image_context import *
from core.context_modules.recycle_context import *
from core.context_modules.artifact_context import *
from core.context_modules.duplicates_context import *
from core.context_modules.task_context import *
from core.context_modules.cleanup_context import *
from core.context_modules.route_facade import *
