# SPDX-License-Identifier: MIT

import argparse
import os
import sys
from datetime import datetime

try:
    from .locales import get_texts
    from .services.organizer import organize_images, rebuild_duplicate_results_json, rebuild_hash_db
except ImportError:
    from locales import get_texts
    from services.organizer import organize_images, rebuild_duplicate_results_json, rebuild_hash_db


def configure_console_encoding() -> None:
    # Force UTF-8 console output so localized help text renders correctly on Windows.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", line_buffering=True)


def emit_progress(message: str) -> None:
    print(message, flush=True)


def build_log_path() -> str:
    # Store run logs in a dedicated folder next to the script.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, "log")
    os.makedirs(log_dir, exist_ok=True)

    # Use a timestamped file name so each run keeps its own log record.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"organize_log_{timestamp}.txt")


def validate_paths(src_dir: str, dst_dir: str, texts: dict[str, str]) -> tuple[str, str]:
    # Normalize both paths first so validation works with relative inputs as well.
    src_abs = os.path.abspath(src_dir)
    dst_abs = os.path.abspath(dst_dir)

    if not os.path.isdir(src_abs):
        raise ValueError(texts["src_not_found"].format(path=src_abs))

    # Only compare nested paths when both locations are on the same drive.
    src_drive = os.path.splitdrive(src_abs)[0].lower()
    dst_drive = os.path.splitdrive(dst_abs)[0].lower()
    if src_drive == dst_drive:
        # Prevent the destination from being the source itself or any child of it.
        common_path = os.path.commonpath([src_abs, dst_abs])
        if common_path == src_abs:
            raise ValueError(texts["dst_inside_src"].format(src=src_abs, dst=dst_abs))

    return src_abs, dst_abs


def validate_existing_dir(path: str, texts: dict[str, str], text_key: str) -> str:
    path_abs = os.path.abspath(path)
    if not os.path.isdir(path_abs):
        raise ValueError(texts[text_key].format(path=path_abs))
    return path_abs


def main():
    configure_console_encoding()

    # Parse the language early so argparse help text can be localized.
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--lang", choices=("zh", "en", "ja"), default="en")
    base_args, _ = base_parser.parse_known_args()
    texts = get_texts(base_args.lang)

    # Build the main parser after the localized text bundle is available.
    parser = argparse.ArgumentParser(description=texts["app_description"])
    parser.add_argument("--src", help=texts["src_help"])
    parser.add_argument("--dst", help=texts["dst_help"])
    parser.add_argument("--mode", choices=("move", "copy"), default="move", help=texts["mode_help"])
    parser.add_argument(
        "--duplicate-detection",
        choices=("off", "phash", "strict"),
        default="phash",
        help=texts["duplicate_detection_help"],
    )
    parser.add_argument(
        "--phash-threshold",
        type=int,
        default=4,
        help=texts["phash_threshold_help"],
    )
    parser.add_argument(
        "--rebuild-hash-db-root",
        default="",
        help=texts["rebuild_hash_db_root_help"],
    )
    parser.add_argument(
        "--rebuild-hash-db-mode",
        choices=("replace", "append"),
        default="replace",
        help=texts["rebuild_hash_db_mode_help"],
    )
    parser.add_argument(
        "--rebuild-hash-method",
        choices=("strict", "phash", "both"),
        default="both",
        help=texts["rebuild_hash_method_help"],
    )
    parser.add_argument("--duplicates-json-path", default="", help=argparse.SUPPRESS)
    parser.add_argument("--duplicates-db-path", default="", help=argparse.SUPPRESS)
    parser.add_argument("--lang", choices=("zh", "en", "ja"), default="en", help=texts["lang_help"])
    parser.add_argument("--log-path", default="", help=argparse.SUPPRESS)

    args = parser.parse_args()
    texts = get_texts(args.lang)

    if args.rebuild_hash_db_root:
        root_dir = validate_existing_dir(args.rebuild_hash_db_root, texts, "rebuild_root_not_found")
        print(texts["rebuild_hash_db_start"].format(root=root_dir))
        print(texts["rebuild_hash_db_mode_selected"].format(mode=args.rebuild_hash_db_mode))
        print(texts["rebuild_hash_method_selected"].format(method=args.rebuild_hash_method))
        stats = rebuild_hash_db(
            root_dir,
            args.rebuild_hash_db_mode,
            args.rebuild_hash_method,
            progress_callback=lambda count: emit_progress(
                texts["rebuild_hash_db_progress"].format(count=count)
            ),
        )
        duplicate_stats = None
        if args.duplicates_json_path or args.duplicates_db_path:
            merge_existing_methods = None
            if args.rebuild_hash_db_mode == "append":
                merge_existing_methods = (
                    {"strict", "phash"}
                    if args.rebuild_hash_method == "both"
                    else {args.rebuild_hash_method}
                )
            duplicate_stats = rebuild_duplicate_results_json(
                root_dir,
                os.path.abspath(args.duplicates_json_path) if args.duplicates_json_path else "",
                args.rebuild_hash_method,
                args.phash_threshold,
                scan_progress_callback=lambda count: emit_progress(
                    texts["rebuild_duplicates_scan_progress"].format(count=count)
                ),
                group_progress_callback=lambda count: emit_progress(
                    texts["rebuild_duplicates_group_progress"].format(count=count)
                ),
                merge_existing_methods=merge_existing_methods,
                sqlite_db_path=os.path.abspath(args.duplicates_db_path) if args.duplicates_db_path else None,
            )
        print(
            texts["rebuild_hash_db_done"].format(
                root=stats["root_dir"],
                db_path=stats["db_path"],
                scanned=stats["scanned_files"],
                strict=stats["strict_indexed"],
                phash=stats["phash_indexed"],
            )
        )
        if duplicate_stats:
            print(
                texts["rebuild_duplicates_json_done"].format(
                    json_path=duplicate_stats["json_path"],
                    groups=duplicate_stats["duplicate_group_count"],
                )
            )
        return

    if not args.src or not args.dst:
        parser.error(texts["src_dst_required"])

    src_dir, dst_dir = validate_paths(args.src, args.dst, texts)

    log_path = os.path.abspath(args.log_path) if args.log_path else build_log_path()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    print(texts["start_message"])
    print(texts["mode_selected"].format(mode=args.mode))
    print(texts["duplicate_detection_selected"].format(mode=args.duplicate_detection, threshold=args.phash_threshold))

    organize_images(
        src_dir,
        dst_dir,
        log_path,
        args.mode,
        texts,
        args.duplicate_detection,
        args.phash_threshold,
        progress_callback=lambda count: emit_progress(
            texts["organize_progress"].format(count=count)
        ),
        duplicates_json_path=os.path.abspath(args.duplicates_json_path) if args.duplicates_json_path else None,
        duplicates_db_path=os.path.abspath(args.duplicates_db_path) if args.duplicates_db_path else None,
    )

    print(texts["done_message"].format(log_path=log_path))


if __name__ == "__main__":
    main()
