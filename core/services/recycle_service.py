# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any


def append_log(log_dir: Path, log_name: str, *values: str) -> None:
    with (log_dir / log_name).open("a", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(values)


def read_delete_log_rows(log_dir: Path) -> list[dict[str, str]]:
    log_path = log_dir / "delete_log.csv"
    if not log_path.exists():
        return []

    rows: list[dict[str, str]] = []
    with log_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for index, row in enumerate(reader):
            if not row:
                continue
            if index == 0 and row[0] == "timestamp":
                continue
            if len(row) >= 5:
                timestamp, root, relative_path, deleted_to, action = row[:5]
            elif len(row) >= 4:
                timestamp, root, relative_path, deleted_to = row[:4]
                action = "deleted"
            elif len(row) == 3:
                timestamp, root, relative_path, deleted_to = row[0], "", row[1], row[2]
                action = "deleted"
            else:
                continue
            rows.append(
                {
                    "timestamp": timestamp,
                    "root": root,
                    "relative_path": relative_path,
                    "deleted_to": deleted_to,
                    "action": action,
                }
            )
    return rows


def write_delete_log_rows(log_dir: Path, rows: list[dict[str, str]]) -> None:
    log_path = log_dir / "delete_log.csv"
    with log_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "root", "relative_path", "deleted_to", "action"])
        for row in rows:
            writer.writerow(
                [
                    row.get("timestamp", ""),
                    row.get("root", ""),
                    row.get("relative_path", ""),
                    row.get("deleted_to", ""),
                    row.get("action", "deleted"),
                ]
            )


def archive_delete_log(log_dir: Path) -> dict[str, Any]:
    log_path = log_dir / "delete_log.csv"
    rows = read_delete_log_rows(log_dir)
    if not rows:
        write_delete_log_rows(log_dir, [])
        return {
            "archived": False,
            "archive_path": "",
            "archived_count": 0,
        }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = log_dir / f"delete_log_{timestamp}.csv"
    counter = 1
    while archive_path.exists():
        archive_path = log_dir / f"delete_log_{timestamp}_{counter}.csv"
        counter += 1

    if log_path.exists():
        log_path.replace(archive_path)
    else:
        write_delete_log_rows(log_dir, rows)
        log_path.replace(archive_path)

    write_delete_log_rows(log_dir, [])
    return {
        "archived": True,
        "archive_path": str(archive_path),
        "archived_count": len(rows),
    }


def list_recycle_items(log_rows: list[dict[str, str]], deleted_dir: Path) -> list[dict[str, Any]]:
    log_by_deleted_to: dict[str, dict[str, str]] = {}
    for row in log_rows:
        deleted_to = row.get("deleted_to")
        if not deleted_to:
            continue
        log_by_deleted_to[deleted_to] = row

    items: list[dict[str, Any]] = []
    for file_path in sorted(deleted_dir.rglob("*"), key=lambda path: path.stat().st_mtime, reverse=True):
        if not file_path.is_file() or file_path.name == ".gitkeep":
            continue
        stat = file_path.stat()
        log_row = log_by_deleted_to.get(str(file_path), {})
        if log_row.get("action") in {"restored", "purged"}:
            continue
        root = log_row.get("root", "")
        relative_path = log_row.get("relative_path", "")
        original_path = str((Path(root) / relative_path).resolve()) if root and relative_path else ""
        items.append(
            {
                "deleted_to": str(file_path),
                "name": file_path.name,
                "size": stat.st_size,
                "deleted_at": log_row.get("timestamp") or datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "root": root,
                "relative_path": relative_path,
                "original_path": original_path,
                "restorable": bool(root and relative_path),
                "original_exists": bool(original_path and Path(original_path).exists()),
            }
        )
    return items


def list_recycle_items_from_records(log_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for log_row in log_rows:
        if log_row.get("action") in {"restored", "purged"}:
            continue
        deleted_to = log_row.get("deleted_to")
        if not deleted_to:
            continue
        file_path = Path(deleted_to)
        if not file_path.is_file() or file_path.name == ".gitkeep":
            continue
        stat = file_path.stat()
        root = log_row.get("root", "")
        relative_path = log_row.get("relative_path", "")
        original_path = str((Path(root) / relative_path).resolve()) if root and relative_path else ""
        items.append(
            {
                "deleted_to": str(file_path),
                "name": file_path.name,
                "size": stat.st_size,
                "deleted_at": log_row.get("timestamp") or datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "root": root,
                "relative_path": relative_path,
                "original_path": original_path,
                "restorable": bool(root and relative_path),
                "original_exists": bool(original_path and Path(original_path).exists()),
            }
        )
    return items
