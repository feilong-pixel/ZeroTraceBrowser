# SPDX-License-Identifier: MIT

import csv
import json
import os
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from media_engine.core.hash_db import add_hash_record, connect_sqlite_hash_db, load_hash_db
from media_engine.core.date_classifier import build_date_path, get_target_date
from media_engine.core.exif_reader import get_exif_datetime
from media_engine.locales import get_texts
from media_engine.main import format_organize_summary, validate_paths
import media_engine.services.organizer as organizer_mod
from media_engine.services.organizer import (
    apply_windows_file_times,
    organize_images,
    rebuild_duplicate_results_from_hash_db,
    read_windows_file_times,
    rebuild_duplicate_results_json,
    rebuild_hash_db,
    transfer_file,
)


def create_media_file(path: Path, content: str = "demo") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def create_image_file(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), color=color).save(path)
    return path


def create_image_file_with_exif_date(path: Path, exif_date: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (32, 32), color=(32, 96, 160))
    exif = Image.Exif()
    exif[36867] = exif_date
    image.save(path, format="JPEG", exif=exif)
    return path


def expected_target_path(src_file: Path, dst_dir: Path) -> Path:
    target_date = get_target_date(str(src_file))
    return Path(build_date_path(str(dst_dir), target_date)) / src_file.name


def expected_target_dir(src_file: Path, dst_dir: Path) -> Path:
    target_date = get_target_date(str(src_file))
    return Path(build_date_path(str(dst_dir), target_date))


def windows_filetime_from_unix(timestamp: float) -> tuple[int, int]:
    filetime = int((timestamp + 11644473600) * 10000000)
    return filetime & 0xFFFFFFFF, filetime >> 32


def set_windows_creation_time(path: Path, timestamp: float) -> None:
    if not sys.platform.startswith("win"):
        return
    current_times = read_windows_file_times(str(path))
    assert current_times is not None
    apply_windows_file_times(str(path), (windows_filetime_from_unix(timestamp), current_times[1], current_times[2]))


def assert_windows_creation_time(path: Path, expected: float) -> None:
    if not sys.platform.startswith("win"):
        return
    assert abs(path.stat().st_ctime - expected) < 2


def test_add_hash_record_does_not_reinsert_existing_path(monkeypatch: pytest.MonkeyPatch) -> None:
    inserted: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "media_engine.core.hash_db.insert_hash_record",
        lambda method, hash_value, path: inserted.append((method, hash_value, path)),
    )
    db = {"strict": {"abc": ["existing.jpg"]}, "phash": {}}

    add_hash_record(db, "strict", "abc", "existing.jpg")

    assert inserted == []


def test_get_or_compute_hash_uses_memory_cache_before_sqlite(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_file = create_media_file(work_dir / "cached.jpg", content="cached-content")
    signature = organizer_mod.get_file_signature(str(src_file))
    cache = {
        str(src_file.resolve()): {
            **signature,
            "strict": "cached-strict",
        }
    }

    monkeypatch.setattr(
        organizer_mod,
        "load_file_hash_cache_entry",
        lambda *_args, **_kwargs: pytest.fail("SQLite cache should not be read for an in-memory hit"),
    )

    assert organizer_mod.get_or_compute_hash(cache, "strict", str(src_file)) == "cached-strict"


@pytest.fixture
def work_dir() -> Path:
    base_dir = Path.cwd() / "tests_runtime"
    base_dir.mkdir(exist_ok=True)
    temp_dir = base_dir / f"run_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def hash_db_path(work_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB", str(work_dir / "hash_db.json"))


def test_copy_mode_organizes_and_keeps_source(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "copy.log"
    src_file = create_media_file(src_dir / "a.jpg")

    target_path = expected_target_path(src_file, dst_dir)

    organize_images(str(src_dir), str(dst_dir), str(log_path), mode="copy")

    assert src_file.exists()
    assert target_path.exists()
    assert "OK | COPY" in log_path.read_text(encoding="utf-8")


def test_move_mode_organizes_and_removes_source(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "move.log"
    src_file = create_media_file(src_dir / "a.jpg")

    target_path = expected_target_path(src_file, dst_dir)

    organize_images(str(src_dir), str(dst_dir), str(log_path), mode="move")

    assert not src_file.exists()
    assert target_path.exists()
    assert "OK | MOVE" in log_path.read_text(encoding="utf-8")


def test_target_date_uses_exif_datetime_original(work_dir: Path) -> None:
    src_file = create_image_file_with_exif_date(work_dir / "src" / "photo.jpg", "2019:02:03 04:05:06")

    exif_datetime = get_exif_datetime(str(src_file))
    target_datetime = get_target_date(str(src_file))

    assert exif_datetime == datetime(2019, 2, 3, 4, 5, 6)
    assert target_datetime == datetime(2019, 2, 3, 4, 5, 6)


def test_target_date_without_exif_uses_file_modified_time(work_dir: Path) -> None:
    src_file = create_media_file(work_dir / "src" / "a.jpg")
    expected_timestamp = datetime(2020, 1, 2, 3, 4, 5).timestamp()
    os.utime(src_file, (expected_timestamp, expected_timestamp))

    target_datetime = get_target_date(str(src_file))

    assert target_datetime == datetime.fromtimestamp(expected_timestamp)


def test_transfer_file_preserves_windows_creation_time(work_dir: Path) -> None:
    src_file = create_media_file(work_dir / "src" / "a.jpg")
    copy_target = work_dir / "dst" / "copy.jpg"
    move_target = work_dir / "dst" / "move.jpg"
    copy_target.parent.mkdir(parents=True, exist_ok=True)
    original_created_at = 1577934245.0
    set_windows_creation_time(src_file, original_created_at)

    transfer_file(str(src_file), str(copy_target), "copy")

    assert src_file.exists()
    assert copy_target.exists()
    assert_windows_creation_time(copy_target, original_created_at)

    transfer_file(str(src_file), str(move_target), "move")

    assert not src_file.exists()
    assert move_target.exists()
    assert_windows_creation_time(move_target, original_created_at)


def test_validate_paths_rejects_missing_source(work_dir: Path) -> None:
    texts = get_texts("en")
    missing_src = work_dir / "missing"
    dst_dir = work_dir / "dst"

    with pytest.raises(ValueError, match="Source directory does not exist"):
        validate_paths(str(missing_src), str(dst_dir), texts)


def test_validate_paths_rejects_destination_inside_source(work_dir: Path) -> None:
    texts = get_texts("en")
    src_dir = work_dir / "src"
    nested_dst = src_dir / "nested" / "dst"
    src_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="Destination directory must not be"):
        validate_paths(str(src_dir), str(nested_dst), texts)


def test_duplicate_names_get_numeric_suffix(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "duplicate.log"
    src_file_1 = create_media_file(src_dir / "camera1" / "same.jpg", content="first")
    src_file_2 = create_media_file(src_dir / "camera2" / "same.jpg", content="second")

    target_dir = Path(build_date_path(str(dst_dir), get_target_date(str(src_file_1))))

    organize_images(str(src_dir), str(dst_dir), str(log_path), mode="copy")

    first_target = target_dir / "same.jpg"
    second_target = target_dir / "same_1.jpg"

    assert first_target.exists()
    assert second_target.exists()
    assert first_target.read_text(encoding="utf-8") == "first"
    assert second_target.read_text(encoding="utf-8") == "second"


def test_strict_duplicate_detection_keeps_duplicates_within_current_destination(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "strict.log"
    first_file = create_media_file(src_dir / "camera1" / "same.jpg", content="first")
    create_media_file(src_dir / "camera2" / "same.jpg", content="first")
    target_dir = expected_target_dir(first_file, dst_dir)

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="strict",
    )

    log_text = log_path.read_text(encoding="utf-8")
    assert "DUP | strict=" in log_text
    assert (target_dir / "same.jpg").exists()
    assert (target_dir / "same_dup1.jpg").exists()


def test_duplicate_report_csv_is_written_for_detected_duplicates(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "strict.log"
    first_file = create_media_file(src_dir / "camera1" / "same_name.jpg", content="first")
    create_media_file(src_dir / "camera2" / "different_name.jpg", content="first")
    target_dir = expected_target_dir(first_file, dst_dir)

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="strict",
    )

    report_path = work_dir / "duplicate_report.csv"
    assert report_path.exists()

    with report_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    row = rows[0]
    assert row["original_name"] == "different_name.jpg"
    assert row["original_path"].endswith(str(Path("camera2") / "different_name.jpg"))
    assert row["kept_path"].endswith(str(target_dir / "same_name.jpg"))
    assert row["duplicate_method"] == "strict"
    assert row["hash"]
    assert row["duplicate_path"].endswith(str(target_dir / "same_name_dup1.jpg"))


def test_duplicates_json_is_written_for_detected_duplicates(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "strict.log"
    first_file = create_media_file(src_dir / "camera1" / "same_name.jpg", content="first")
    create_media_file(src_dir / "camera2" / "different_name.jpg", content="first")
    target_dir = expected_target_dir(first_file, dst_dir)

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="strict",
    )

    json_path = work_dir / "duplicates.json"
    assert json_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    expected_kept_path = (target_dir / "same_name.jpg").relative_to(dst_dir).as_posix()
    expected_duplicate_path = (target_dir / "same_name_dup1.jpg").relative_to(dst_dir).as_posix()
    assert payload["destination_root"] == str(dst_dir.resolve())
    assert payload["group_count"] == 1
    assert len(payload["groups"]) == 1

    group = payload["groups"][0]
    assert group["group_id"] == "dup_0001"
    assert group["reason"] == "strict"
    assert group["kept_path"] == expected_kept_path
    assert len(group["items"]) == 2
    assert group["items"][0]["role"] == "kept"
    assert group["items"][0]["path"] == expected_kept_path
    assert group["items"][1]["role"] == "duplicate"
    assert group["items"][1]["path"] == expected_duplicate_path


def test_organize_images_can_write_duplicates_directly_to_sqlite(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "strict.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    first_file = create_media_file(src_dir / "camera1" / "same_name.jpg", content="first")
    create_media_file(src_dir / "camera2" / "different_name.jpg", content="first")
    target_dir = expected_target_dir(first_file, dst_dir)
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="strict",
        duplicates_db_path=str(sqlite_path),
    )

    assert sqlite_path.exists()
    assert not (work_dir / "duplicates.json").exists()
    assert not (work_dir / "hash_db.json").exists()
    with sqlite3.connect(sqlite_path) as connection:
        duplicate_result = connection.execute(
            "SELECT destination_root, group_count FROM duplicate_results WHERE id = 1"
        ).fetchone()
        hash_record_count = connection.execute("SELECT COUNT(*) FROM hash_db_records").fetchone()[0]
    assert duplicate_result == (str(dst_dir.resolve()), 1)
    assert hash_record_count == 2
    assert (target_dir / "same_name.jpg").exists()
    assert (target_dir / "same_name_dup1.jpg").exists()


def test_organize_images_strict_result_rebuild_does_not_compute_phash(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "strict.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_image_file(src_dir / "camera1" / "same.png", color=(255, 0, 0))
    create_image_file(src_dir / "camera2" / "same.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    def fail_compute_phash(path: str) -> str:
        raise AssertionError("strict organizer runs should not compute pHash")

    monkeypatch.setattr(organizer_mod, "compute_phash", fail_compute_phash)

    stats = organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="strict",
        duplicates_db_path=str(sqlite_path),
    )

    assert stats["similar_group_count"] == 1
    with sqlite3.connect(sqlite_path) as connection:
        methods = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT method FROM hash_db_records ORDER BY method"
            ).fetchall()
        ]
        reasons = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT reason FROM duplicate_groups ORDER BY reason"
            ).fetchall()
        ]

    assert methods == ["strict"]
    assert reasons == ["strict"]


def test_organize_images_both_result_rebuild_reuses_current_hash_db(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "both.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_image_file(src_dir / "camera1" / "same.png", color=(255, 0, 0))
    create_image_file(src_dir / "camera2" / "same.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    def fail_rebuild_duplicate_results_json(*args, **kwargs):
        raise AssertionError("organizer result publishing should reuse the current hash DB")

    monkeypatch.setattr(
        organizer_mod,
        "rebuild_duplicate_results_json",
        fail_rebuild_duplicate_results_json,
    )

    stats = organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="both",
        phash_threshold=0,
        duplicates_db_path=str(sqlite_path),
    )

    assert stats["similar_group_count"] == 2
    with sqlite3.connect(sqlite_path) as connection:
        reasons = [
            row[0]
            for row in connection.execute(
                "SELECT reason FROM duplicate_groups ORDER BY reason"
            ).fetchall()
        ]

    assert reasons == ["phash", "strict"]


def test_organize_images_strict_skip_preserves_existing_phash_results(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "strict.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    existing_a = create_image_file(dst_dir / "existing_a.jpg", color=(255, 0, 0))
    existing_b = create_image_file(dst_dir / "existing_b.jpg", color=(254, 0, 0))
    create_image_file(src_dir / "new_a.jpg", color=(0, 255, 0))
    create_image_file(src_dir / "new_b.jpg", color=(0, 255, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    rebuild_duplicate_results_from_hash_db(
        str(dst_dir),
        "",
        {
            "phash": {"0000000000000000": [str(existing_a)], "0000000000000001": [str(existing_b)]},
            "strict": {},
        },
        "phash",
        phash_threshold=64,
        sqlite_db_path=str(sqlite_path),
    )

    stats = organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="strict",
        duplicates_db_path=str(sqlite_path),
        skip_existing_exact=True,
    )

    assert stats["similar_group_count"] == 1
    with sqlite3.connect(sqlite_path) as connection:
        reasons = [
            row[0]
            for row in connection.execute(
                "SELECT reason FROM duplicate_groups ORDER BY reason"
            ).fetchall()
        ]

    assert reasons == ["phash"]


def test_organize_images_writes_file_hash_cache_to_sqlite(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "both.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    first_file = create_image_file(src_dir / "camera1" / "same.png", color=(255, 0, 0))
    create_image_file(src_dir / "camera2" / "same.png", color=(255, 0, 0))
    target_dir = expected_target_dir(first_file, dst_dir)
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="both",
        phash_threshold=0,
        duplicates_db_path=str(sqlite_path),
    )

    file_cache_path = work_dir / "hash_db.json.file_cache.json"
    with connect_sqlite_hash_db() as connection:
        cache_rows = connection.execute(
            """
            SELECT path, source_path, strict_hash, phash
            FROM file_hash_cache
            ORDER BY path
            """
        ).fetchall()
        hash_record_count = connection.execute("SELECT COUNT(*) FROM hash_db_records").fetchone()[0]

    assert not file_cache_path.exists()
    assert len(cache_rows) == 4
    assert hash_record_count == 4
    assert any(row[0] == str((target_dir / "same.png").resolve()) for row in cache_rows)
    assert any(
        row[0] == str((target_dir / "same_dup1.png").resolve())
        and row[1].endswith(str(Path("camera2") / "same.png"))
        and row[2]
        and row[3]
        for row in cache_rows
    )


def test_organize_images_skips_existing_exact_files_in_sqlite(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src_first = work_dir / "src_first"
    src_second = work_dir / "src_second"
    dst_dir = work_dir / "dst"
    first_log_path = work_dir / "first.log"
    second_log_path = work_dir / "second.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    first_file = create_media_file(src_first / "camera1" / "same.jpg", content="same-content")
    create_media_file(src_second / "camera2" / "same.jpg", content="same-content")
    target_dir = expected_target_dir(first_file, dst_dir)
    task_id = "task_skip"
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    organize_images(
        str(src_first),
        str(dst_dir),
        str(first_log_path),
        mode="copy",
        duplicate_detection="strict",
        duplicates_db_path=str(sqlite_path),
    )
    with connect_sqlite_hash_db() as connection:
        connection.execute(
            """
            INSERT INTO task_runs (task_id, task_type, status, destination_root)
            VALUES (?, 'organizer', 'running', ?)
            """,
            (task_id, str(dst_dir.resolve())),
        )
        connection.commit()

    organize_images(
        str(src_second),
        str(dst_dir),
        str(second_log_path),
        mode="copy",
        lang=get_texts("zh"),
        duplicate_detection="strict",
        duplicates_db_path=str(sqlite_path),
        skip_existing_exact=True,
        task_id=task_id,
    )
    output = capsys.readouterr().out

    with sqlite3.connect(sqlite_path) as connection:
        skipped_row = connection.execute(
            """
            SELECT source_path, existing_path, strict_hash, file_name, size
            FROM task_skipped_existing
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        index_row = connection.execute(
            "SELECT seen_count, first_task_id, last_task_id FROM skipped_existing_index"
        ).fetchone()
        task_row = connection.execute(
            """
            SELECT scanned_count, saved_count, skipped_existing_count, skipped_existing_bytes, similar_group_count
            FROM task_runs
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        hash_record_count = connection.execute("SELECT COUNT(*) FROM hash_db_records").fetchone()[0]

    assert (target_dir / "same.jpg").exists()
    assert not (target_dir / "same_dup1.jpg").exists()
    assert "已存在于图库，跳过复制" in output
    assert "节省" in output
    assert "SKIP_EXISTING" in second_log_path.read_text(encoding="utf-8")
    assert skipped_row[1] == str((target_dir / "same.jpg").resolve())
    assert skipped_row[2]
    assert skipped_row[3] == "same.jpg"
    assert skipped_row[4] == len("same-content")
    assert index_row == (1, task_id, task_id)
    assert task_row == (1, 0, 1, len("same-content"), 0)
    assert hash_record_count == 1


def test_skip_existing_exact_is_ignored_when_duplicate_detection_is_phash(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "phash.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    first_file = create_media_file(src_dir / "camera1" / "first_name.jpg", content="same-content")
    create_media_file(src_dir / "camera2" / "second_name.jpg", content="same-content")
    target_dir = expected_target_dir(first_file, dst_dir)
    task_id = "task_phash_skip"
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))
    with connect_sqlite_hash_db() as connection:
        connection.execute(
            """
            INSERT INTO task_runs (task_id, task_type, status, destination_root)
            VALUES (?, 'organizer', 'running', ?)
            """,
            (task_id, str(dst_dir.resolve())),
        )
        connection.commit()

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="phash",
        duplicates_db_path=str(sqlite_path),
        skip_existing_exact=True,
        task_id=task_id,
    )

    with sqlite3.connect(sqlite_path) as connection:
        skipped_count = connection.execute("SELECT COUNT(*) FROM task_skipped_existing").fetchone()[0]
        strict_count = connection.execute(
            "SELECT COUNT(*) FROM hash_db_records WHERE method = 'strict'"
        ).fetchone()[0]
        task_row = connection.execute(
            "SELECT scanned_count, saved_count, skipped_existing_count FROM task_runs WHERE task_id = ?",
            (task_id,),
        ).fetchone()

    assert (target_dir / "first_name.jpg").exists()
    assert (target_dir / "second_name.jpg").exists()
    assert skipped_count == 0
    assert strict_count == 0
    assert task_row == (2, 2, 0)


def test_organize_summary_hides_skip_fields_when_skip_existing_is_off() -> None:
    stats = {
        "scanned_count": 8,
        "saved_count": 8,
        "skipped_existing_count": 0,
        "skipped_existing_bytes": 0,
        "similar_group_count": 4,
    }

    summary = format_organize_summary(get_texts("zh"), stats, include_skip=False)

    assert summary == "扫描照片：8 张\n保存到图库：8 张\n发现相似照片：4 组"
    assert "已存在于图库" not in summary
    assert "节省空间" not in summary


def test_saved_count_tracks_files_after_transfer_even_if_cache_copy_fails(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "copy.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_media_file(src_dir / "photo.jpg", content="photo")
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    def fail_cache_copy(cache, source_path: str, target_path: str) -> None:
        raise OSError("cache update failed")

    monkeypatch.setattr(organizer_mod, "copy_hash_cache_entry", fail_cache_copy)

    stats = organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="off",
        duplicates_db_path=str(sqlite_path),
    )

    assert stats["scanned_count"] == 1
    assert stats["saved_count"] == 1
    assert len(list(dst_dir.rglob("*.jpg"))) == 1


def test_organize_summary_shows_skip_fields_when_skip_existing_is_on() -> None:
    stats = {
        "scanned_count": 8,
        "saved_count": 4,
        "skipped_existing_count": 4,
        "skipped_existing_bytes": 2048,
        "similar_group_count": 1,
    }

    summary = format_organize_summary(get_texts("zh"), stats, include_skip=True)

    assert "新增保存：4 张" in summary
    assert "已存在于图库：4 张" in summary
    assert "节省空间：2 KB" in summary


def test_duplicate_names_follow_kept_file_name_sequence(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "strict.log"
    first_file = create_media_file(src_dir / "camera1" / "first_name.jpg", content="first")
    create_media_file(src_dir / "camera2" / "second_name.jpg", content="first")
    create_media_file(src_dir / "camera3" / "third_name.jpg", content="first")
    target_dir = expected_target_dir(first_file, dst_dir)

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="strict",
    )

    assert (target_dir / "first_name.jpg").exists()
    assert (target_dir / "first_name_dup1.jpg").exists()
    assert (target_dir / "first_name_dup2.jpg").exists()

    payload = json.loads((work_dir / "duplicates.json").read_text(encoding="utf-8"))
    assert payload["group_count"] == 1
    group = payload["groups"][0]
    assert [item["path"] for item in group["items"]] == [
        (target_dir / "first_name.jpg").relative_to(dst_dir).as_posix(),
        (target_dir / "first_name_dup1.jpg").relative_to(dst_dir).as_posix(),
        (target_dir / "first_name_dup2.jpg").relative_to(dst_dir).as_posix(),
    ]


def test_hash_db_does_not_redirect_files_outside_current_destination(work_dir: Path) -> None:
    first_src = work_dir / "src_first"
    first_dst = work_dir / "dst_first"
    second_src = work_dir / "src_second"
    second_dst = work_dir / "dst_second"
    first_log = work_dir / "first.log"
    second_log = work_dir / "second.log"

    create_media_file(first_src / "same.jpg", content="identical")
    second_file = create_media_file(second_src / "same.jpg", content="identical")
    second_target_dir = expected_target_dir(second_file, second_dst)

    organize_images(
        str(first_src),
        str(first_dst),
        str(first_log),
        mode="copy",
        duplicate_detection="strict",
    )
    organize_images(
        str(second_src),
        str(second_dst),
        str(second_log),
        mode="copy",
        duplicate_detection="strict",
    )

    second_log_text = second_log.read_text(encoding="utf-8")
    assert "DUP | strict=" not in second_log_text
    assert "OK | COPY" in second_log_text
    assert (second_target_dir / "same.jpg").exists()


def test_phash_duplicate_detection_uses_distance_threshold(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "phash.log"
    create_image_file(src_dir / "camera1" / "same.png", color=(255, 0, 0))
    create_image_file(src_dir / "camera2" / "same.png", color=(255, 0, 0))

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="phash",
        phash_threshold=0,
    )

    log_text = log_path.read_text(encoding="utf-8")
    assert "DUP | phash=" in log_text


def test_both_duplicate_detection_indexes_strict_and_phash(work_dir: Path) -> None:
    src_dir = work_dir / "src"
    dst_dir = work_dir / "dst"
    log_path = work_dir / "both.log"
    first_file = create_image_file(src_dir / "camera1" / "same.png", color=(255, 0, 0))
    create_image_file(src_dir / "camera2" / "same.png", color=(255, 0, 0))
    target_dir = expected_target_dir(first_file, dst_dir)

    organize_images(
        str(src_dir),
        str(dst_dir),
        str(log_path),
        mode="copy",
        duplicate_detection="both",
        phash_threshold=0,
    )

    log_text = log_path.read_text(encoding="utf-8")
    db = load_hash_db()
    strict_paths = [path for paths in db["strict"].values() for path in paths]
    phash_paths = [path for paths in db["phash"].values() for path in paths]

    assert "DUP | strict=" in log_text
    assert (target_dir / "same.png").exists()
    assert (target_dir / "same_dup1.png").exists()
    assert len(strict_paths) == 2
    assert len(phash_paths) == 2


def test_rebuild_hash_db_replace_rebuilds_only_target_root(work_dir: Path) -> None:
    root_a = work_dir / "organized_a"
    root_b = work_dir / "organized_b"
    create_media_file(root_a / "2026" / "04" / "16" / "a.jpg", content="first")
    create_media_file(root_b / "2026" / "04" / "16" / "b.jpg", content="second")

    stats = rebuild_hash_db(str(root_a), rebuild_mode="replace", hash_method="strict")
    db = load_hash_db()

    assert stats["scanned_files"] == 1
    assert stats["strict_indexed"] == 1
    assert stats["phash_indexed"] == 0
    strict_paths = [path for paths in db["strict"].values() for path in paths]
    assert len(strict_paths) == 1
    assert strict_paths[0].endswith(str(Path("organized_a") / "2026" / "04" / "16" / "a.jpg"))


def test_rebuild_hash_db_can_write_directly_to_sqlite(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_media_file(root / "2026" / "04" / "16" / "a.jpg", content="first")
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    stats = rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")
    db = load_hash_db()

    assert stats["db_path"] == str(sqlite_path.resolve())
    assert sqlite_path.exists()
    assert not (work_dir / "hash_db.json").exists()
    assert len(db["strict"]) == 1
    with sqlite3.connect(sqlite_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM hash_db_records").fetchone()[0] == 1


def test_rebuild_hash_db_reuses_cached_strict_hash_for_unchanged_files(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    create_media_file(root / "2026" / "04" / "16" / "a.jpg", content="same")
    calls = {"strict": 0}

    def fake_compute_file_hash(path: str) -> str:
        calls["strict"] += 1
        return "strict-hash"

    monkeypatch.setattr(organizer_mod, "compute_file_hash", fake_compute_file_hash)

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")
    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")

    assert calls["strict"] == 1


def test_rebuild_hash_db_reuses_sqlite_file_hash_cache_for_unchanged_files(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_media_file(root / "2026" / "04" / "16" / "a.jpg", content="same")
    calls = {"strict": 0}

    def fake_compute_file_hash(path: str) -> str:
        calls["strict"] += 1
        return "strict-hash"

    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))
    monkeypatch.setattr(organizer_mod, "compute_file_hash", fake_compute_file_hash)

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")
    stats = rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")

    with sqlite3.connect(sqlite_path) as connection:
        cache_count = connection.execute("SELECT COUNT(*) FROM file_hash_cache").fetchone()[0]

    assert calls["strict"] == 1
    assert stats["reused_records"] == 1
    assert stats["recomputed_hashes"] == 0
    assert cache_count == 1


def test_rebuild_hash_db_sqlite_reconciles_existing_records_without_reinserting(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_media_file(root / "a.jpg", content="same-content")
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")
    with sqlite3.connect(sqlite_path) as connection:
        first_id = connection.execute("SELECT id FROM hash_db_records").fetchone()[0]

    def fail_compute_file_hash(path: str) -> str:
        raise AssertionError("existing hash_db_records should be reused during rebuild")

    monkeypatch.setattr(organizer_mod, "compute_file_hash", fail_compute_file_hash)

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")
    with sqlite3.connect(sqlite_path) as connection:
        rows = connection.execute("SELECT id, method, path FROM hash_db_records").fetchall()

    assert rows == [(first_id, "strict", str(root / "a.jpg"))]


def test_rebuild_hash_db_sqlite_recomputes_when_cache_signature_changed(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    target = create_media_file(root / "a.jpg", content="old-content")
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")
    target.write_text("new-content-with-different-size", encoding="utf-8")

    computed_paths: list[str] = []
    original_compute_file_hash = organizer_mod.compute_file_hash

    def tracked_compute_file_hash(path: str) -> str:
        computed_paths.append(path)
        return original_compute_file_hash(path)

    monkeypatch.setattr(organizer_mod, "compute_file_hash", tracked_compute_file_hash)

    stats = rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")

    assert computed_paths == [str(target)]
    assert stats["corrected_records"] == 1
    assert stats["recomputed_hashes"] == 1
    assert stats["inserted_records"] == 1


def test_rebuild_hash_db_sqlite_recomputes_phash_when_cache_signature_changed(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    target = create_image_file(root / "a.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="phash")
    target.write_text("not-an-image-anymore", encoding="utf-8")

    computed_paths: list[str] = []

    def tracked_compute_phash(path: str) -> None:
        computed_paths.append(path)
        return None

    monkeypatch.setattr(organizer_mod, "compute_phash", tracked_compute_phash)

    stats = rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="phash")

    with sqlite3.connect(sqlite_path) as connection:
        phash_count = connection.execute(
            "SELECT COUNT(*) FROM hash_db_records WHERE method = 'phash'"
        ).fetchone()[0]

    assert computed_paths == [str(target)]
    assert stats["corrected_records"] == 1
    assert stats["recomputed_hashes"] == 0
    assert stats["phash_indexed"] == 0
    assert phash_count == 0


def test_rebuild_hash_db_sqlite_prunes_stale_phash_records(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    target = create_image_file(root / "a.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="phash")
    target.unlink()

    stats = rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="phash")

    with sqlite3.connect(sqlite_path) as connection:
        phash_count = connection.execute(
            "SELECT COUNT(*) FROM hash_db_records WHERE method = 'phash'"
        ).fetchone()[0]

    assert stats["stale_pruned"] == 1
    assert stats["phash_indexed"] == 0
    assert phash_count == 0


def test_rebuild_hash_db_both_reuses_organizer_cache_for_unchanged_files(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_dir = work_dir / "src"
    root = work_dir / "organized"
    log_path = work_dir / "both.log"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_image_file(src_dir / "camera1" / "same.png", color=(255, 0, 0))
    create_image_file(src_dir / "camera2" / "same.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    organize_images(
        str(src_dir),
        str(root),
        str(log_path),
        mode="copy",
        duplicate_detection="both",
        phash_threshold=0,
        duplicates_db_path=str(sqlite_path),
    )

    def fail_compute_file_hash(path: str) -> str:
        raise AssertionError("unchanged strict hashes should be reused during rebuild")

    def fail_compute_phash(path: str) -> str:
        raise AssertionError("unchanged pHashes should be reused during rebuild")

    monkeypatch.setattr(organizer_mod, "compute_file_hash", fail_compute_file_hash)
    monkeypatch.setattr(organizer_mod, "compute_phash", fail_compute_phash)

    stats = rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="both")

    assert stats["scanned_files"] == 2
    assert stats["strict_indexed"] == 2
    assert stats["phash_indexed"] == 2


def test_rebuild_hash_db_strict_preserves_existing_phash_records(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_image_file(root / "a.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="both")
    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")

    with sqlite3.connect(sqlite_path) as connection:
        strict_count = connection.execute(
            "SELECT COUNT(*) FROM hash_db_records WHERE method = 'strict'"
        ).fetchone()[0]
        phash_count = connection.execute(
            "SELECT COUNT(*) FROM hash_db_records WHERE method = 'phash'"
        ).fetchone()[0]

    assert strict_count == 1
    assert phash_count == 1


def test_rebuild_hash_db_json_strict_preserves_existing_phash_records(
    work_dir: Path,
) -> None:
    root = work_dir / "organized"
    create_image_file(root / "a.png", color=(255, 0, 0))

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="both")
    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")

    db = load_hash_db()

    assert sum(len(paths) for paths in db["strict"].values()) == 1
    assert sum(len(paths) for paths in db["phash"].values()) == 1


def test_rebuild_duplicate_results_from_hash_db_can_publish_preserved_phash_after_strict_rebuild(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    first = create_image_file(root / "a.png", color=(255, 0, 0))
    second = create_image_file(root / "b.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="both")
    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")
    stats = rebuild_duplicate_results_from_hash_db(
        str(root),
        "",
        load_hash_db(),
        "both",
        phash_threshold=0,
        sqlite_db_path=str(sqlite_path),
    )

    assert stats["duplicate_group_count"] >= 1
    with sqlite3.connect(sqlite_path) as connection:
        reasons = {
            row[0]
            for row in connection.execute("SELECT reason FROM duplicate_groups").fetchall()
        }

    assert "phash" in reasons
    assert first.exists()
    assert second.exists()


def test_strict_duplicate_publish_preserves_existing_phash_groups(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    first = create_image_file(root / "a.png", color=(255, 0, 0))
    second = create_image_file(root / "b.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="both")
    rebuild_duplicate_results_from_hash_db(
        str(root),
        "",
        load_hash_db(),
        "both",
        phash_threshold=0,
        sqlite_db_path=str(sqlite_path),
    )
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute("DELETE FROM hash_db_records WHERE method = 'phash'")
        connection.commit()

    rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")
    rebuild_duplicate_results_from_hash_db(
        str(root),
        "",
        load_hash_db(),
        "strict",
        phash_threshold=0,
        sqlite_db_path=str(sqlite_path),
        merge_existing_methods={"strict"},
    )

    with sqlite3.connect(sqlite_path) as connection:
        reasons = {
            row[0]
            for row in connection.execute("SELECT reason FROM duplicate_groups").fetchall()
        }

    assert "phash" in reasons
    assert first.exists()
    assert second.exists()


def test_rebuild_hash_db_does_not_trust_sqlite_records_without_matching_cache_signature(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    first = create_image_file(root / "2026" / "04" / "16" / "same.png", color=(255, 0, 0))
    second = create_image_file(root / "2026" / "04" / "16" / "same_dup1.png", color=(255, 0, 0))
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    with connect_sqlite_hash_db() as connection:
        for position, path in enumerate((first, second)):
            connection.execute(
                "INSERT INTO hash_db_records (method, hash, path, position) VALUES ('strict', 'strict-old', ?, ?)",
                (str(path), position),
            )
            connection.execute(
                "INSERT INTO hash_db_records (method, hash, path, position) VALUES ('phash', '0000000000000000', ?, ?)",
                (str(path), position),
            )
        connection.commit()

    computed = {"strict": 0, "phash": 0}
    original_compute_file_hash = organizer_mod.compute_file_hash
    original_compute_phash = organizer_mod.compute_phash

    def tracked_compute_file_hash(path: str) -> str:
        computed["strict"] += 1
        return original_compute_file_hash(path)

    def tracked_compute_phash(path: str) -> str:
        computed["phash"] += 1
        return original_compute_phash(path)

    monkeypatch.setattr(organizer_mod, "compute_file_hash", tracked_compute_file_hash)
    monkeypatch.setattr(organizer_mod, "compute_phash", tracked_compute_phash)

    stats = rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="both")

    with sqlite3.connect(sqlite_path) as connection:
        cache_count = connection.execute("SELECT COUNT(*) FROM file_hash_cache").fetchone()[0]
        record_count = connection.execute("SELECT COUNT(*) FROM hash_db_records").fetchone()[0]

    assert stats["cache_backfilled"] == 0
    assert stats["strict_indexed"] == 2
    assert stats["phash_indexed"] == 2
    assert stats["recomputed_hashes"] == 4
    assert stats["inserted_records"] == 4
    assert computed == {"strict": 2, "phash": 2}
    assert cache_count == 2
    assert record_count == 4


def test_rebuild_hash_db_replace_prunes_unsupported_sidecar_records(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    image = create_media_file(root / "2026" / "04" / "16" / "photo.jpg", content="image")
    sidecar = create_media_file(root / "2026" / "04" / "16" / "photo.AAE", content="sidecar")
    monkeypatch.setenv("IMAGE_ORGANIZER_HASH_DB_SQLITE", str(sqlite_path))

    with connect_sqlite_hash_db() as connection:
        connection.execute(
            "INSERT INTO hash_db_records (method, hash, path, position) VALUES ('strict', 'old-image', ?, 0)",
            (str(image.resolve()),),
        )
        connection.execute(
            "INSERT INTO hash_db_records (method, hash, path, position) VALUES ('strict', 'old-sidecar', ?, 1)",
            (str(sidecar.resolve()),),
        )
        connection.commit()

    stats = rebuild_hash_db(str(root), rebuild_mode="replace", hash_method="strict")

    with sqlite3.connect(sqlite_path) as connection:
        paths = [
            row[0]
            for row in connection.execute(
                "SELECT path FROM hash_db_records WHERE method = 'strict' ORDER BY path"
            ).fetchall()
        ]

    assert stats["scanned_files"] == 1
    assert stats["strict_indexed"] == 1
    assert stats["stale_pruned"] == 1
    assert paths == [str(image.resolve())]


def test_rebuild_duplicate_results_json_from_existing_archive(work_dir: Path) -> None:
    root = work_dir / "organized"
    json_path = work_dir / "duplicates.json"
    create_media_file(root / "2026" / "04" / "16" / "a.jpg", content="same")
    create_media_file(root / "2026" / "04" / "16" / "a_dup1.jpg", content="same")
    create_media_file(root / "2026" / "04" / "16" / "b.jpg", content="different")

    stats = rebuild_duplicate_results_json(str(root), str(json_path), hash_method="strict")
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert stats["duplicate_group_count"] == 1
    assert payload["destination_root"] == str(root.resolve())
    assert payload["group_count"] == 1
    group = payload["groups"][0]
    assert group["reason"] == "strict"
    assert [item["role"] for item in group["items"]] == ["kept", "duplicate"]
    assert [item["path"] for item in group["items"]] == [
        "2026/04/16/a.jpg",
        "2026/04/16/a_dup1.jpg",
    ]


def test_rebuild_duplicate_results_json_reuses_cached_phash_for_unchanged_files(
    work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = work_dir / "organized"
    json_path = work_dir / "duplicates.json"
    create_image_file(root / "2026" / "04" / "16" / "a.jpg", color=(10, 20, 30))
    create_image_file(root / "2026" / "04" / "16" / "b.jpg", color=(10, 20, 30))
    calls = {"phash": 0}

    def fake_compute_phash(path: str) -> str:
        calls["phash"] += 1
        return "0000000000000000"

    monkeypatch.setattr(organizer_mod, "compute_phash", fake_compute_phash)

    rebuild_duplicate_results_json(str(root), str(json_path), hash_method="phash", phash_threshold=0)
    rebuild_duplicate_results_json(str(root), str(json_path), hash_method="phash", phash_threshold=0)

    assert calls["phash"] == 2


def test_rebuild_duplicate_results_json_append_phash_keeps_existing_strict_groups(work_dir: Path) -> None:
    root = work_dir / "organized"
    json_path = work_dir / "duplicates.json"
    create_media_file(root / "2026" / "04" / "16" / "strict_a.jpg", content="same")
    create_media_file(root / "2026" / "04" / "16" / "strict_a_dup1.jpg", content="same")
    create_image_file(root / "2026" / "04" / "17" / "visual_a.jpg", color=(32, 96, 160))
    create_image_file(root / "2026" / "04" / "17" / "visual_a_dup1.jpg", color=(32, 96, 160))

    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "destination_root": str(root.resolve()),
                "group_count": 1,
                "groups": [
                    {
                        "group_id": "dup_0001",
                        "reason": "strict",
                        "hash": "strict_hash",
                        "kept_path": "2026/04/16/strict_a.jpg",
                        "items": [
                            {"role": "kept", "path": "2026/04/16/strict_a.jpg"},
                            {"role": "duplicate", "path": "2026/04/16/strict_a_dup1.jpg"},
                        ],
                        "source_files": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    stats = rebuild_duplicate_results_json(
        str(root),
        str(json_path),
        hash_method="phash",
        phash_threshold=0,
        merge_existing_methods={"phash"},
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert stats["duplicate_group_count"] == 2
    assert payload["group_count"] == 2
    assert [group["reason"] for group in payload["groups"]] == ["strict", "phash"]


def test_rebuild_duplicate_results_sqlite_phash_keeps_existing_strict_groups(work_dir: Path) -> None:
    root = work_dir / "organized"
    sqlite_path = work_dir / "workspace.sqlite3"
    create_media_file(root / "2026" / "04" / "16" / "strict_a.jpg", content="same")
    create_media_file(root / "2026" / "04" / "16" / "strict_a_dup1.jpg", content="same")
    create_image_file(root / "2026" / "04" / "17" / "visual_a.jpg", color=(32, 96, 160))
    visual_dup = create_image_file(root / "2026" / "04" / "17" / "visual_a_dup1.jpg", color=(32, 96, 160))
    with visual_dup.open("ab") as handle:
        handle.write(b"metadata")

    rebuild_duplicate_results_json(
        str(root),
        "",
        hash_method="strict",
        sqlite_db_path=str(sqlite_path),
    )
    stats = rebuild_duplicate_results_json(
        str(root),
        "",
        hash_method="phash",
        phash_threshold=0,
        merge_existing_methods={"phash"},
        sqlite_db_path=str(sqlite_path),
    )

    with sqlite3.connect(sqlite_path) as connection:
        reasons = [
            row[0]
            for row in connection.execute(
                "SELECT reason FROM duplicate_groups ORDER BY position"
            ).fetchall()
        ]

    assert stats["duplicate_group_count"] == 2
    assert reasons == ["strict", "phash"]
