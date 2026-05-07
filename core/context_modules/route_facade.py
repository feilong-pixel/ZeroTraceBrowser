from .base import *
from .system_context import *
from .settings_context import *
from .root_workspace import *
from .image_context import *
from .recycle_context import *
from .artifact_context import *
from .duplicates_context import *
from .task_context import *
from .cleanup_context import *


class RouteContext:
    def __getattr__(self, name: str) -> Any:
        module_names = ("app", "core.app.factory", "core.context")
        runtime_keys = (
            "DATA_DIR",
            "ROOT_DATA_DIR",
            "SETTINGS_PATH",
            "LOG_DIR",
            "TASK_LOG_DIR",
            "DELETED_DIR",
            "THUMBNAIL_DIR",
            "IMAGE_INDEX_DIR",
            "ARTIFACT_INDEX_DIR",
            "DEFAULT_IMAGE_ROOT",
            "DEFAULT_COPY_TARGET",
            "SKIP_SCAN_DIR_NAMES",
            "move_to_system_recycle_bin",
            "open_path_in_file_manager",
            "open_image_in_system_editor",
            "is_windows",
        )
        source_module = next(
            (
                module
                for module_name in module_names
                if (module := sys.modules.get(module_name)) is not None and name in module.__dict__
            ),
            None,
        )
        if source_module is not None:
            value = source_module.__dict__[name]
            if callable(value):
                def call_with_current_app_globals(*args: Any, **kwargs: Any) -> Any:
                    for key in runtime_keys:
                        for module_name in module_names:
                            module = sys.modules.get(module_name)
                            if module is None or key not in module.__dict__:
                                continue
                            if key in module.__dict__:
                                globals()[key] = module.__dict__[key]
                                if hasattr(value, "__globals__"):
                                    value.__globals__[key] = module.__dict__[key]
                                break
                    return value(*args, **kwargs)

                return call_with_current_app_globals
            return value
        return globals()[name]


def build_route_context() -> RouteContext:
    return RouteContext()
