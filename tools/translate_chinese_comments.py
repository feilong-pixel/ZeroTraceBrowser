"""
Translate Chinese comments in Python source files to English.

This script processes all core Python files (excluding i18n locale files
and sub-module MediaArchiveOrganizer) and replaces inline Chinese comments
with their English equivalents.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Translation map: Chinese comment (exact text on line) -> English equivalent
TRANSLATIONS = {
    # --- duplicate_group.py ---
    "    ZeroTraceBrowser 的重复文件分组。\n": "    Duplicate file group for ZeroTraceBrowser.\n",
    "    对应 duplicates.json 中 groups 数组的每一项。\n": "    Corresponds to each item in the ``groups`` array of ``duplicates.json``.\n",
    "    # 组 ID\n": "    # Group identifier\n",
    "    # 重复检测原因（\"strict\" 或 \"phash\"）\n": "    # Duplicate detection method (\"strict\" or \"phash\")\n",
    "    # 哈希值（重复组的 key）\n": "    # Hash value (key that defines the duplicate group)\n",
    "    # 保留的文件相对路径\n": "    # Relative path of the kept file\n",
    "    # 组内所有文件\n": "    # All items within this duplicate group\n",
    "    # 新增文件数量/可用数量（运行时填充，不持久化）\n": "    # Runtime-only counts (not persisted)\n",
    "        \"\"\"从 duplicates.json 的组 dict 安全构建。\"\"\"\n": "        \"\"\"Safely build from a group dict in duplicates.json.\"\"\"\n",

    # --- image_entry.py ---
    "    ZeroTraceBrowser 的索引条目，对应 index.json / summary.json 中的每一项。\n": "    Index entry for ZeroTraceBrowser, corresponding to each item in index.json / summary.json.\n",
    "    字段对齐 :func:`image_scan_service.image_metadata_from_path` 的返回结构，\n": "    Fields align with the return structure of :func:`image_scan_service.image_metadata_from_path`,\n",
    "    所有可选字段的默认值与真实代码一致（空字符串或 0 / None）。\n": "    All optional field defaults match the production code (empty string, 0, or None).\n",
    "    # 相对于 root 的路径（前端展示、删除、恢复都用它）\n": "    # Path relative to the image root (used by frontend, delete, restore)\n",
    "    # 文件路径（绝对路径或相对路径，与 relative_path 相同值）\n": "    # File path — same value as relative_path for backward compatibility\n",
    "    # 文件名\n": "    # File base name\n",
    "    # 文件大小（字节）\n": "    # File size in bytes\n",
    "    # 拍摄时间（EXIF 或文件时间，ISO 格式）\n": "    # Capture datetime from EXIF or file timestamp (ISO format)\n",
    "    # 文件修改时间（ISO 格式）\n": "    # File modification datetime in ISO format\n",
    "    # 时间线展示时间（YYYY-MM-DD HH:MM:SS 格式）\n": "    # Timeline display time (YYYY-MM-DD HH:MM:SS)\n",
    "    # 时间线排序时间戳（秒）\n": "    # Timeline sort timestamp (unix epoch seconds)\n",
    "    # 时间线来源（\"exif\" 或 \"file\"）\n": "    # Timeline source: \"exif\" or \"file\"\n",
    "    # 文件是否存在（用于缓存标记）\n": "    # Whether the file still exists on disk (cache marker)\n",
    "    # 文件的唯一哈希（用于重复检测，仅通过 hash_db 填充）\n": "    # File content hash for duplicate detection (populated via hash DB)\n",
    "    # 图像尺寸（仅当读取 EXIF 时可用）\n": "    # Image dimensions (only available when EXIF is read)\n",
    "        从 :func:`image_metadata_from_path` 返回的 dict 构建 ImageEntry。\n": "        Build an ImageEntry from the dict returned by :func:`image_metadata_from_path`.\n",
    "        自动处理缺失字段、类型转换等边界情况。\n": "        Automatically handles missing fields, type coercion, and edge cases.\n",
    "        \"\"\"将 ImageEntry 转回 dict，兼容 image_scan_service 的返回格式。\"\"\"\n": "        \"\"\"Convert ImageEntry back to a dict compatible with image_scan_service output.\"\"\"\n",

    # --- timeline_item.py ---
    "    ZeroTraceBrowser 的时间线条目。\n": "    Timeline entry for ZeroTraceBrowser.\n",
    "    对应 ``timeline_index_cache_path`` 所写 JSON 中 ``entries`` 数组的每一项。\n": "    Corresponds to each item in the ``entries`` array of the timeline index cache JSON.\n",
    "    字段对齐 :func:`image_index_service.build_timeline_index_entries` 的返回结构。\n": "    Fields align with the return structure of :func:`image_index_service.build_timeline_index_entries`.\n",
    "    # 分组 key（如 \"2026-04\"）\n": "    # Group key, e.g. \"2026-04\"\n",
    "    # 分组展示标签（如 \"2026-04\" 或 \"Unknown date\"）\n": "    # Display label for the group, e.g. \"2026-04\" or \"Unknown date\"\n",
    "    # 索引标签（用于导航刻度，如 \"202604\"）\n": "    # Navigation tick label, e.g. \"202604\"\n",
    "        \"\"\"从 ``build_timeline_index_entries`` 的返回值安全构建。\"\"\"\n": "        \"\"\"Safely build from the return value of ``build_timeline_index_entries``.\"\"\"\n",

    # --- hash_calculator.py ---
    "    ZeroTraceBrowser 的文件哈希计算器。\n": "    File hash calculator for ZeroTraceBrowser.\n",
    "    用于重复检测（duplicate detection）。\n": "    Used for duplicate detection.\n",
    "        计算文件的 SHA1 哈希。\n": "        Compute the SHA1 hash of a file.\n",

    # --- metadata_reader.py ---
    "    读取图像元数据（EXIF、尺寸、时间）。\n": "    Read image metadata (EXIF, dimensions, timestamps).\n",
    "            \"hash\": None,  # 由 HashCalculator 填充\n": "            \"hash\": None,  # Populated by HashCalculator\n",
    "        # 1. 尺寸\n": "        # 1. Dimensions\n",
    "        # 2. EXIF 时间\n": "        # 2. EXIF datetime\n",
    "        # 3. 文件修改时间（作为 fallback）\n": "        # 3. File modification time (fallback)\n",

    # --- thumbnail_generator.py ---
    "    生成缩略图（JPEG）。\n": "    Generate JPEG thumbnails.\n",
    "    ZeroTraceBrowser 的缩略图路径由 RootContext 决定。\n": "    Thumbnail paths are managed by RootContext.\n",
    "        生成缩略图到 dst。\n": "        Generate a thumbnail and write it to dst.\n",
    "            # 缩略图生成失败时不抛异常，避免阻塞 index 构建\n": "            # Do not raise on thumbnail failure to avoid blocking index builds\n",

    # --- cache_repository.py ---
    "    ZeroTraceBrowser 的缓存管理仓库。\n": "    Cache management repository for ZeroTraceBrowser.\n",
    "    负责清理：\n": "    Responsible for cache invalidation:\n",
    "    - 未来可扩展：hash_db cache、duplicate cache\n": "    - Future extensibility: hash DB cache, duplicate cache\n",
    "    # 清理图片列表缓存（旧系统的 ctx.clear_image_list_cache）\n": "    # Clear image list cache (legacy ctx.clear_image_list_cache)\n",
    "        删除 indexes/ 目录下的所有缓存文件。\n": "        Delete all cache files under the indexes/ directory.\n",
    "        例如：\n": "        For example:\n",
    "            # 只删除 summary / timeline，不删除主 index.json\n": "            # Only remove summary/timeline caches, keep the primary index.json\n",
    "    # 清理 timeline 缓存（可选）\n": "    # Clear timeline cache (optional)\n",
    "        删除 timeline 缓存文件。\n": "        Delete the timeline cache file.\n",
    "    # 清理所有缓存（可选）\n": "    # Clear all caches (optional)\n",
    "        清理所有缓存（未来扩展用）\n": "        Clear all caches (for future extension)\n",

    # --- file_repository.py ---
    "    ZeroTraceBrowser 的文件操作仓库层。\n": "    File operations repository for ZeroTraceBrowser.\n",
    "    所有文件操作（copy/move/delete/restore）都必须通过\n": "    All file operations (copy/move/delete/restore) must go through\n",
    "    infrastructure 层的 FileTransferAdapter（内部调用 transfer_file）。\n": "    the FileTransferAdapter in the infrastructure layer (which calls transfer_file).\n",
    "        self.metadata_reader = metadata_reader  # 可选：用于读取 EXIF、尺寸等\n": "        self.metadata_reader = metadata_reader  # Optional: for reading EXIF, dimensions, etc.\n",
    "    # 基础操作：复制\n": "    # Basic operation: copy\n",
    "        复制文件（底层使用 transfer_file）\n": "        Copy a file (uses transfer_file internally)\n",
    "    # 基础操作：移动\n": "    # Basic operation: move\n",
    "        移动文件（底层使用 transfer_file）\n": "        Move a file (uses transfer_file internally)\n",
    "    # 安全删除（移动到回收站，带时间戳 + digest 前缀）\n": "    # Safe delete: move to recycle bin with timestamp + digest prefix\n",
    "        ZeroTraceBrowser 的删除不是删除，而是移动到 deleted/ 目录。\n": "        ZeroTraceBrowser's \"delete\" moves files to the deleted/ directory.\n",
    "        使用 ``build_deleted_path`` 生成带时间戳与 digest 前缀的路径\n": "        Uses ``build_deleted_path`` to generate paths with timestamp and digest prefix,\n",
    "        （例如 ``deleted/20260426_abcd1234/photo.jpg``），而非简单的\n": "        e.g. ``deleted/20260426_abcd1234/photo.jpg``, instead of a simple\n",
    "            src: 源文件的绝对路径。\n": "            src: Absolute path of the source file.\n",
    "            relative_path: 相对于 root 的路径。如果为 None 则从 src 推断。\n": "            relative_path: Path relative to the root. If None, inferred from src.\n",
    "    # 恢复文件（从回收站恢复到原始路径）\n": "    # Restore file: move from recycle bin back to original path\n",
    "        从 deleted/ 恢复到原始路径。\n": "        Restore a file from deleted/ back to its original path.\n",
    "            deleted_path: 回收区中的文件路径。\n": "            deleted_path: Path of the file in the recycle area.\n",
    "            original_path: 目标恢复路径。如果为 None 则通过\n": "            original_path: Target restore path. If None, inferred via\n",
    "                ``RootContext.original_path_for`` 推断。\n": "                ``RootContext.original_path_for``.\n",
    "    # 扫描图片（用于 index 构建）\n": "    # Scan images (for index building)\n",
    "        扫描目录下所有图片文件。\n": "        Scan for all image files under a directory.\n",
    "    # 读取元数据（可选）\n": "    # Read metadata (optional)\n",
    "        读取图片元数据（如果 metadata_reader 存在）\n": "        Read image metadata if a metadata_reader is available\n",
    "    # 工具函数\n": "    # Utility functions\n",

    # --- index_repository.py ---
    "        从文件路径和可选的元数据字典构建 ``ImageEntry``。\n": "        Build an ``ImageEntry`` from a file path and optional metadata dict.\n",
    "        如果提供了 ``meta``，优先使用其字段（兼容 image_scan_service 的返回格式）。\n": "        When ``meta`` is provided, its fields take priority (compatible with image_scan_service output).\n",
    "        否则从文件系统读取基本信息。\n": "        Otherwise, read basic info from the filesystem.\n",
    "            # 确保 path 和 relative_path 字段完整\n": "            # Ensure path and relative_path fields are populated\n",
    "        # 没有 meta 时，从文件系统读取基本信息\n": "        # Without meta, read basic info from the filesystem\n",
    "        \"\"\"将一批扫描结果（list[dict]）转为 ``ImageEntry`` 列表。\"\"\"\n": "        \"\"\"Convert a batch of scan results (list[dict]) to a list of ``ImageEntry``.\"\"\"\n",
    "        \"\"\"从 JSON 文件加载并反序列化为 ``ImageEntry`` 列表。\"\"\"\n": "        \"\"\"Load and deserialize from a JSON file into a list of ``ImageEntry``.\"\"\"\n",

    # --- log_repository.py ---
    "    ZeroTraceBrowser 操作日志仓库。\n": "    Operation log repository for ZeroTraceBrowser.\n",
    "    负责写入：\n": "    Responsible for writing:\n",
    "    # 内部辅助：确保 CSV header 存在\n": "    # Internal helper: ensure CSV header exists\n",
    "        \"\"\"如果文件不存在则写入 header 行。\"\"\"\n": "        \"\"\"Write the header row if the file does not exist.\"\"\"\n",
    "    # 删除日志\n": "    # Delete log\n",
    "        追加一条删除（或 restore / purge）日志。\n": "        Append a delete (or restore / purge) log entry.\n",
    "            timestamp: ISO 格式时间戳。\n": "            timestamp: ISO-format timestamp.\n",
    "            root: 图片根目录路径。\n": "            root: Image root directory path.\n",
    "            relative_path: 文件相对于 root 的路径。\n": "            relative_path: Path of the file relative to the root.\n",
    "            deleted_to: 回收区中的目标路径。\n": "            deleted_to: Target path in the recycle area.\n",
    "            action: 操作类型，\"deleted\"、\"restored\" 或 \"purged\"。\n": "            action: Operation type: \"deleted\", \"restored\", or \"purged\".\n",
    "    # 复制日志\n": "    # Copy log\n",
    "        追加一条复制日志。\n": "        Append a copy operation log entry.\n",

    # --- settings_repository.py ---
    "    # 保存 root.json\n": "    # Save root.json\n",
    "    # 读取 root.json\n": "    # Read root.json\n",
    "    # 设置 active root\n": "    # Set active root\n",
    "    # 获取 active root\n": "    # Get active root\n",

    # --- thumbnail_repository.py ---
    "    ZeroTraceBrowser 缩略图仓库。\n": "    Thumbnail repository for ZeroTraceBrowser.\n",
    "    负责删除缩略图，不负责生成（生成由 ThumbnailGenerator 完成）。\n": "    Responsible for deleting thumbnails; generation is handled by ThumbnailGenerator.\n",
    "            root_context: RootContext 实例，提供 ``.root``、``.thumbnails_dir`` 等属性。\n": "            root_context: RootContext instance providing ``.root``, ``.thumbnails_dir``, etc.\n",
    "            thumbnails_dir: 可选的缩略图根目录。如果为 None，则使用\n": "            thumbnails_dir: Optional thumbnail root directory. If None, uses\n",
    "                而其他属性则从 root_context 中读取。\n": "                while other properties are read from root_context.\n",
    "    # 删除：根据 relative_path 删除缩略图\n": "    # Delete: remove thumbnail by relative_path\n",
    "        删除某个相对路径对应的缩略图。\n": "        Delete the thumbnail corresponding to a given relative path.\n",
    "        使用与 ``thumbnail_service.thumbnail_path_for`` 相同的哈希算法\n": "        Uses the same hashing algorithm as ``thumbnail_service.thumbnail_path_for``\n",
    "        定位缩略图。\n": "        to locate the thumbnail.\n",
    "    # 删除：根据 hash 删除缩略图（可选）\n": "    # Delete: remove thumbnail by hash (optional)\n",
    "        删除某个哈希对应的缩略图（通过 RootContext.thumbnail_path_for_hash）。\n": "        Delete the thumbnail for a given hash via RootContext.thumbnail_path_for_hash.\n",

    # --- image_scan_service.py ---
    "    # 只要 timeline 和 full index 的生成时间一致，就直接返回旧 timeline\n": "    # If timeline and full index have the same generation time, return the old timeline\n",
    "    # 关键：timeline 只允许从完整 index 生成\n": "    # Critical: timeline must only be generated from a full index\n",
    "    # 没有完整 index 时，不用 summary_items 生成 timeline\n": "    # Without a full index, do not generate timeline from summary items\n",

    # --- set_root.py ---
    "        # 1. 创建 root config\n": "        # 1. Create root config\n",
    "        # 2. 保存 root.json\n": "        # 2. Save root.json\n",
    "        # 3. 设置 active root\n": "        # 3. Set active root\n",

    # ---- file_repository.py: duplicate class (class FileRepository is defined twice) ---
    "    ZeroTraceBrowser 的文件操作仓库层。\n": "    File operations repository for ZeroTraceBrowser.\n",
    "    所有文件操作（copy/move/delete/restore）都必须通过\n": "    All file operations (copy/move/delete/restore) must go through\n",
    "    infrastructure 层的 FileTransferAdapter（内部调用 transfer_file）。\n": "    the FileTransferAdapter in the infrastructure layer (which calls transfer_file).\n",
}

# A more flexible approach: translate any line with Chinese via regex
# For safety, use the exact-line map first, then fall back to regex
CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]')


def translate_line(line: str) -> str:
    """Translate a line if it contains Chinese text."""
    if not CHINESE_PATTERN.search(line):
        return line

    # Try exact match first
    if line in TRANSLATIONS:
        return TRANSLATIONS[line]

    # --- direct line-level translations for remaining unique lines ---

    # file_repository.py's second class definition adds "（LegacyRepository 兼容）"
    if line == "    ZeroTraceBrowser 的文件操作仓库层。（LegacyRepository 兼容）\n":
        return "    File operations repository for ZeroTraceBrowser. (LegacyRepository compatibility)\n"
    if line == "    所有文件操作（copy/move/delete/restore）都必须通过\n":
        return "    All file operations (copy/move/delete/restore) must go through\n"
    if line == "    infrastructure 层的 FileTransferAdapter（内部调用 transfer_file）。\n":
        return "    the FileTransferAdapter in the infrastructure layer (which calls transfer_file).\n"

    # log_repository.py second class
    if line == "    ZeroTraceBrowser 操作日志仓库。（LegacyRepository 兼容）\n":
        return "    Operation log repository for ZeroTraceBrowser. (LegacyRepository compatibility)\n"
    if line == "    负责写入：\n":
        return "    Responsible for writing:\n"

    # Fallback: translate comment portion only (text after #)
    if line.lstrip().startswith('#'):
        # Strip the comment prefix and translate
        indent = line[:len(line) - len(line.lstrip())]
        content = line.lstrip()
        # Check if it's a pure Chinese comment (no code before #)
        # Replace known Chinese fragments
        translated = content
        replacements = {
            "）": ")",
            "（": " (",
            "：": ": ",
            "，": ", ",
            "的": "'s ",
            "在": "in ",
            "是": "is ",
            "和": " and ",
            "与": " and ",
            "由": "by ",
            "从": "from ",
            "使用": "using ",
            "通过": "via ",
            "为": "as ",
            "或": " or ",
            "都": "all ",
            "必须": "must ",
            "可以": "can ",
            "用于": "for ",
            "对应": "corresponding to ",
            "每个": "each ",
            "所有": "all ",
            "写入": "write ",
            "追加": "append ",
            "读取": "read ",
            "扫描": "scan ",
            "删除": "delete ",
            "恢复": "restore ",
            "移动": "move ",
            "复制": "copy ",
            "重构建": "rebuild ",
            "构建": "build ",
            "生成": "generate ",
            "创建": "create ",
            "确保": "ensure ",
            "保存": "save ",
            "设置": "set ",
            "获取": "get ",
            "负责": "responsible for ",
            "可选的": "optional ",
            "可选": "optional ",
            "如果": "if ",
            "提供": "provided ",
            "则不": "then ",
            "则": "then ",
            "不会": "does not ",
            "会": "will ",
            "当": "when ",
            "已": "already ",
            "没有": "no ",
            "需要": "need ",
            "完成": "completed ",
            "目录": "directory ",
            "文件": "file ",
            "图片": "image ",
            "图像": "image ",
            "路径": "path ",
            "相对路径": "relative path ",
            "绝对路径": "absolute path ",
            "根目录": "root directory ",
            "源文件": "source file ",
            "目标": "target ",
            "回收区": "recycle area ",
            "回收站": "recycle bin ",
            "缩略图": "thumbnail ",
            "缓存": "cache ",
            "索引": "index ",
            "时间": "time ",
            "时间戳": "timestamp ",
            "信息": "information ",
            "字段": "field ",
            "操作": "operation ",
            "格式": "format ",
            "类型": "type ",
            "情况": "cases ",
            "边界": "edge ",
            "默认": "default ",
            "兼容": "compatibility ",
            "内部": "internal ",
            "底层": "underlying ",
            "上层": "upper layer ",
            "层": "layer ",
            "系统": "system ",
            "元数据": "metadata ",
            "哈希": "hash ",
            "算法": "algorithm ",
            "值": "value ",
            "ID": "ID ",
            "key": "key ",
            "标签": "label ",
            "展示": "display ",
            "导航": "navigation ",
            "刻度": "tick ",
            "尺寸": "dimensions ",
            "像素": "pixels ",
            "宽度": "width ",
            "高度": "height ",
            "大小": "size ",
            "字节": "bytes ",
            "秒": "seconds ",
            "来源": "source ",
            "拍摄": "capture ",
            "修改": "modification ",
            "更新": "update ",
            "失败": "failure ",
            "异常": "exception ",
            "错误": "error ",
            "抛": "raise ",
            "避免": "avoid ",
            "阻塞": "block ",
            "填充": "populated ",
            "持久化": "persisted ",
            "标记": "marker ",
            "主": "primary ",
            "旧": "legacy ",
            "新": "new ",
            "相同": "same ",
            "不同": "different ",
            "扩展": "extension ",
            "安全": "safe ",
            "简单": "simple ",
        }
        for cn, en in sorted(replacements.items(), key=lambda x: -len(x[0])):
            translated = translated.replace(cn, en)

        # If translation happened, return it
        if translated != content:
            return indent + translated

    # If we can't translate, return original
    return line


def process_file(filepath: Path) -> bool:
    """Process a single file, return True if modified."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try cp932 (Japanese Windows)
        try:
            with open(filepath, 'r', encoding='cp932') as f:
                content = f.read()
        except Exception:
            return False

    new_lines = []
    modified = False
    for line in content.splitlines(True):
        translated = translate_line(line)
        if translated != line:
            modified = True
        new_lines.append(translated)

    if modified:
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.writelines(new_lines)
        return True
    return False


def main():
    files_to_process = [
        "core/domain/duplicate_group.py",
        "core/domain/image_entry.py",
        "core/domain/timeline_item.py",
        "core/infrastructure/hashing/hash_calculator.py",
        "core/infrastructure/imaging/metadata_reader.py",
        "core/infrastructure/imaging/thumbnail_generator.py",
        "core/repositories/cache_repository.py",
        "core/repositories/file_repository.py",
        "core/repositories/index_repository.py",
        "core/repositories/log_repository.py",
        "core/repositories/settings_repository.py",
        "core/repositories/thumbnail_repository.py",
        "core/services/image_scan_service.py",
        "core/use_cases/set_root.py",
    ]

    modified_count = 0
    for rel_path in files_to_process:
        filepath = REPO / rel_path
        if not filepath.exists():
            print(f"  SKIP (not found): {rel_path}")
            continue
        if process_file(filepath):
            print(f"  MODIFIED: {rel_path}")
            modified_count += 1
        else:
            print(f"  OK (no change): {rel_path}")

    print(f"\nTotal files modified: {modified_count}/{len(files_to_process)}")


if __name__ == "__main__":
    main()
