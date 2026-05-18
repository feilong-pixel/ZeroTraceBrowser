# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import app as ztb_app
import core.routes.tasks_route as tasks_routes
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.task_repository import TaskRunRepository
from tests.test_api_user_flow import create_test_image


class ImmediateThread:
    def __init__(self, target, args=(), daemon=None):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        self.target(*self.args)


class NoopThread(ImmediateThread):
    def start(self) -> None:
        return


def organizer_payload(src: Path, dst: Path) -> dict[str, object]:
    return {
        "src": str(src),
        "dst": str(dst),
        "mode": "copy",
        "duplicate_detection": "strict",
        "phash_threshold": 4,
        "skip_existing_exact": True,
        "lang": "en",
    }


def rebuild_payload(root: Path) -> dict[str, object]:
    return {
        "root": str(root),
        "rebuild_mode": "replace",
        "hash_method": "strict",
        "phash_threshold": 4,
        "lang": "en",
    }


def mark_task_completed(
    task_id: str,
    command: list[str],
    workdir: Path,
    env: dict[str, str] | None = None,
) -> None:
    task = ztb_app.TASK_REGISTRY.tasks[task_id]
    task["output_lines"] = ["fake organizer finished"]
    task["return_code"] = 0
    task["status"] = "completed"
    task["finished_at"] = datetime.now().isoformat()

    log_index = command.index("--log-path") + 1 if "--log-path" in command else None
    if log_index is not None:
        Path(command[log_index]).write_text("fake log", encoding="utf-8")


def mark_task_failed(
    task_id: str,
    command: list[str],
    workdir: Path,
    env: dict[str, str] | None = None,
) -> None:
    task = ztb_app.TASK_REGISTRY.tasks[task_id]
    task["output_lines"] = ["fake task failed"]
    task["return_code"] = 7
    task["status"] = "failed"
    task["error"] = "Fake task failure"
    task["finished_at"] = datetime.now().isoformat()


def test_run_organizer_task_starts_completes_and_can_be_queried(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_task_completed)

    response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination))

    assert response.status_code == 200
    task = response.json()
    assert task["task_type"] == "organizer"
    assert task["status"] == "completed"
    assert task["return_code"] == 0
    assert task["output_lines"] == ["fake organizer finished"]
    assert task["outputs"]["log_exists"] is True
    assert task["params"]["src"] == str(image_root)
    assert task["params"]["dst"] == str(destination)
    saved_run = TaskRunRepository(task["outputs"]["database_path"]).load_task(task["task_id"])
    assert saved_run is not None
    assert saved_run["task_type"] == "organizer"
    assert saved_run["source_root"] == str(image_root)
    assert saved_run["destination_root"] == str(destination)
    assert saved_run["skip_existing_exact"] == 1

    query_response = client.get(f"/api/tasks/{task['task_id']}")
    assert query_response.status_code == 200
    assert query_response.json()["status"] == "completed"


def test_run_organizer_accepts_both_duplicate_detection(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_completed(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake organizer finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()
        assert command[command.index("--duplicate-detection") + 1] == "both"
        assert "--skip-existing-exact" in command

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_completed)

    payload = organizer_payload(image_root, destination)
    payload["duplicate_detection"] = "both"
    response = client.post("/api/tasks/run-organizer", json=payload)

    assert response.status_code == 200
    assert response.json()["params"]["duplicate_detection"] == "both"
    config = client.get("/api/config").json()
    assert config["task_defaults"]["duplicate_detection"] == "both"


def test_run_organizer_failed_task_exposes_error_state(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_task_failed)

    response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, workspace / "organized"))

    assert response.status_code == 200
    task = response.json()
    assert task["status"] == "failed"
    assert task["return_code"] == 7
    assert task["error"] == "Fake task failure"
    assert task["output_lines"] == ["fake task failed"]
    assert task["finished_at"]

    query_response = client.get(f"/api/tasks/{task['task_id']}")
    assert query_response.status_code == 200
    queried = query_response.json()
    assert queried["status"] == "failed"
    assert queried["error"] == "Fake task failure"


def test_run_organizer_rejects_second_task_while_one_is_running(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    monkeypatch.setattr(tasks_routes.threading, "Thread", NoopThread)

    first_response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination))
    assert first_response.status_code == 200
    assert first_response.json()["status"] == "running"

    second_response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, workspace / "organized_2"))

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Another organizer task is already running"


def test_running_task_endpoint_exposes_active_task(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    monkeypatch.setattr(tasks_routes.threading, "Thread", NoopThread)

    idle_response = client.get("/api/tasks/running")
    assert idle_response.status_code == 200
    assert idle_response.json()["task"] is None

    first_response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination))
    assert first_response.status_code == 200
    task = first_response.json()

    running_response = client.get("/api/tasks/running")
    assert running_response.status_code == 200
    running_task = running_response.json()["task"]
    assert running_task["task_id"] == task["task_id"]
    assert running_task["status"] == "running"
    assert running_task["params"]["dst"] == str(destination)


def test_rebuild_hash_db_task_starts_and_can_be_queried(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_rebuild_completed(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake rebuild finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()

        assert "--duplicates-json-path" not in command
        assert "--duplicates-db-path" in command
        assert command[command.index("--phash-threshold") + 1] == "4"

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_rebuild_completed)

    response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(image_root))

    assert response.status_code == 200
    task = response.json()
    assert task["task_type"] == "rebuild_hash_db"
    assert task["status"] == "completed"
    assert task["outputs"]["database_path"].endswith("workspace.sqlite3")
    assert task["params"]["root"] == str(image_root)
    saved_run = TaskRunRepository(task["outputs"]["database_path"]).load_task(task["task_id"])
    assert saved_run is not None
    assert saved_run["task_type"] == "rebuild_hash_db"
    assert saved_run["source_root"] == ""
    assert saved_run["destination_root"] == str(image_root)
    assert saved_run["duplicate_detection"] == "strict"

    query_response = client.get(f"/api/tasks/{task['task_id']}")
    assert query_response.status_code == 200
    assert query_response.json()["output_lines"] == ["fake rebuild finished"]


def test_rebuild_hash_db_uses_requested_phash_threshold(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_rebuild_completed(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake rebuild finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()
        assert command[command.index("--rebuild-hash-method") + 1] == "phash"
        assert command[command.index("--phash-threshold") + 1] == "9"

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_rebuild_completed)

    payload = rebuild_payload(image_root)
    payload["hash_method"] = "phash"
    payload["phash_threshold"] = 9
    response = client.post("/api/tasks/rebuild-hash-db", json=payload)

    assert response.status_code == 200
    assert response.json()["params"]["phash_threshold"] == 9


def test_rebuild_hash_db_failed_task_exposes_error_state(api_client, monkeypatch) -> None:
    client, _, image_root, _ = api_client
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_task_failed)

    response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(image_root))

    assert response.status_code == 200
    task = response.json()
    assert task["task_type"] == "rebuild_hash_db"
    assert task["status"] == "failed"
    assert task["return_code"] == 7
    assert task["error"] == "Fake task failure"
    assert task["output_lines"] == ["fake task failed"]

    query_response = client.get(f"/api/tasks/{task['task_id']}")
    assert query_response.status_code == 200
    queried = query_response.json()
    assert queried["status"] == "failed"
    assert queried["error"] == "Fake task failure"


def test_rebuild_hash_db_rejects_append_mode(api_client) -> None:
    client, _, image_root, _ = api_client
    payload = rebuild_payload(image_root)
    payload["rebuild_mode"] = "append"

    response = client.post("/api/tasks/rebuild-hash-db", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported rebuild mode"


def test_rebuild_hash_db_keeps_results_separate_per_root(api_client, monkeypatch) -> None:
    client, workspace, _, _ = api_client
    root_a = workspace / "archive_a"
    root_b = workspace / "archive_b"
    create_test_image(root_a / "same.jpg")
    create_test_image(root_a / "same_dup1.jpg", color=(11, 22, 33))
    create_test_image(root_b / "other.jpg")
    create_test_image(root_b / "other_dup1.jpg", color=(44, 55, 66))

    client.post("/api/settings/roots", json={"path": str(root_a)})
    client.post("/api/settings/roots", json={"path": str(root_b)})
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_rebuild_completed(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake rebuild finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()

        root_index = command.index("--rebuild-hash-db-root") + 1
        db_index = command.index("--duplicates-db-path") + 1
        rebuild_root = Path(command[root_index])
        database_path = Path(command[db_index])

        if rebuild_root == root_a:
            payload_root = root_a
            group_id = "dup_a"
            hash_value = "hash_a"
            kept = "same.jpg"
            duplicate = "same_dup1.jpg"
        elif rebuild_root == root_b:
            payload_root = root_b
            group_id = "dup_b"
            hash_value = "hash_b"
            kept = "other.jpg"
            duplicate = "other_dup1.jpg"
        else:
            raise AssertionError(f"Unexpected rebuild root: {rebuild_root}")
        DuplicateResultRepository(database_path).save_result(
            {
                "generated_at": "2026-04-23T12:34:56",
                "destination_root": str(payload_root),
                "group_count": 1,
                "groups": [
                    {
                        "group_id": group_id,
                        "reason": "strict",
                        "hash": hash_value,
                        "kept_path": kept,
                        "items": [
                            {"role": "kept", "path": kept},
                            {"role": "duplicate", "path": duplicate},
                        ],
                    },
                ],
            },
            source_path=database_path,
        )

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_rebuild_completed)

    first_response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(root_a))
    assert first_response.status_code == 200
    first_task = first_response.json()
    assert first_task["outputs"]["database_exists"] is True

    second_response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(root_b))
    assert second_response.status_code == 200
    second_task = second_response.json()
    assert second_task["outputs"]["database_exists"] is True

    client.post("/api/settings/active-root", json={"path": str(root_a)})
    payload_a = client.get("/api/duplicates").json()
    assert payload_a["destination_root"] == str(root_a)
    assert payload_a["groups"][0]["group_id"] == "dup_a"

    client.post("/api/settings/active-root", json={"path": str(root_b)})
    payload_b = client.get("/api/duplicates").json()
    assert payload_b["destination_root"] == str(root_b)
    assert payload_b["groups"][0]["group_id"] == "dup_b"


def test_run_organizer_publishes_duplicates_and_shared_hash_db(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_completed_with_capture(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        captured.append({"command": command, "env": env or {}})
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake organizer finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_completed_with_capture)

    data = organizer_payload(image_root, destination)
    data["duplicate_detection"] = "both"
    first_task = client.post("/api/tasks/run-organizer", json=data).json()
    second_task = client.post("/api/tasks/run-organizer", json=data).json()

    assert first_task["outputs"]["database_path"] == second_task["outputs"]["database_path"]
    assert first_task["outputs"]["hash_db_path"] == second_task["outputs"]["hash_db_path"]
    assert first_task["outputs"]["hash_db_path"].endswith("workspace.sqlite3")
    assert first_task["outputs"]["database_path"].endswith("workspace.sqlite3")
    assert captured[0]["env"] == {
        "IMAGE_ORGANIZER_HASH_DB_SQLITE": first_task["outputs"]["database_path"],
        "IMAGE_ORGANIZER_TASK_ID": first_task["task_id"],
    }
    assert captured[1]["env"] == {
        "IMAGE_ORGANIZER_HASH_DB_SQLITE": second_task["outputs"]["database_path"],
        "IMAGE_ORGANIZER_TASK_ID": second_task["task_id"],
    }

    first_command = captured[0]["command"]
    assert isinstance(first_command, list)
    assert "--duplicates-json-path" not in first_command
    assert first_command[first_command.index("--duplicates-db-path") + 1] == first_task["outputs"]["database_path"]
    assert first_command[first_command.index("--task-id") + 1] == first_task["task_id"]
    assert "--skip-existing-exact" in first_command


def test_run_organizer_updates_published_duplicates(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    destination.mkdir(parents=True, exist_ok=True)
    database_path = RootContext.from_root(destination, ztb_app.ROOT_DATA_DIR).database_path
    DuplicateResultRepository(database_path).save_result(
        {
            "destination_root": str(destination),
            "group_count": 1,
            "groups": [
                {
                    "group_id": "old_dup",
                    "reason": "strict",
                    "hash": "old_hash",
                    "kept_path": "a.jpg",
                    "items": [
                        {"role": "kept", "path": "a.jpg"},
                        {"role": "duplicate", "path": "b.jpg"},
                    ],
                },
            ],
        },
        source_path=database_path,
    )
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_completed_with_global_duplicates(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        database_path = Path(command[command.index("--duplicates-db-path") + 1])
        DuplicateResultRepository(database_path).save_result(
            {"destination_root": "updated", "group_count": 0, "groups": []},
            source_path=database_path,
        )
        task["output_lines"] = ["fake organizer finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()
        ztb_app.summarize_task_root(task)

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_completed_with_global_duplicates)

    response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination))

    assert response.status_code == 200
    assert DuplicateResultRepository(database_path).load_summary()["destination_root"] == "updated"


def test_run_organizer_writes_task_results_to_root_database(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    destination.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_completed_with_database_outputs(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        database_path = Path(command[command.index("--duplicates-db-path") + 1])
        DuplicateResultRepository(database_path).save_result(
            {
                "destination_root": str(destination),
                "group_count": 1,
                "groups": [
                    {
                        "group_id": "dup_db",
                        "reason": "strict",
                        "hash": "hash_db",
                        "kept_path": "a.jpg",
                        "items": [
                            {"role": "kept", "path": "a.jpg"},
                            {"role": "duplicate", "path": "b.jpg"},
                        ],
                    },
                ],
            },
            source_path=database_path,
        )
        HashDbRepository(database_path).save_hash_db(
            {"phash": {}, "strict": {"hash_db": [str(destination / "a.jpg")]}},
            source_path=database_path,
        )
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake organizer finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()
        ztb_app.summarize_task_root(task)

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_completed_with_database_outputs)

    response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination))

    assert response.status_code == 200
    database_path = RootContext.from_root(destination, ztb_app.ROOT_DATA_DIR).database_path
    assert DuplicateResultRepository(database_path).load_summary()["group_count"] == 1
    assert HashDbRepository(database_path).load_summary()["path_count"] == 1


def test_rebuild_hash_db_reuses_duplicates_and_hash_db_paths_for_same_root(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    root = workspace / "archive"
    root.mkdir(parents=True, exist_ok=True)
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_completed_with_capture(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        captured.append({"command": command, "env": env or {}})
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake rebuild finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_completed_with_capture)

    first_task = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(root)).json()
    second_task = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(root)).json()

    assert first_task["outputs"]["database_path"] == second_task["outputs"]["database_path"]
    assert first_task["outputs"]["hash_db_path"] == second_task["outputs"]["hash_db_path"]
    assert captured[0]["env"] == {
        "IMAGE_ORGANIZER_HASH_DB_SQLITE": first_task["outputs"]["database_path"],
        "IMAGE_ORGANIZER_TASK_ID": first_task["task_id"],
    }
    assert captured[1]["env"] == {
        "IMAGE_ORGANIZER_HASH_DB_SQLITE": second_task["outputs"]["database_path"],
        "IMAGE_ORGANIZER_TASK_ID": second_task["task_id"],
    }


def test_rebuild_hash_db_writes_task_results_to_root_database(api_client, monkeypatch) -> None:
    client, workspace, _, _ = api_client
    root = workspace / "archive"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_rebuild_completed_with_database_outputs(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        database_path = Path(command[command.index("--duplicates-db-path") + 1])
        DuplicateResultRepository(database_path).save_result(
            {
                "destination_root": str(root),
                "group_count": 1,
                "groups": [
                    {
                        "group_id": "dup_rebuild_db",
                        "reason": "phash",
                        "hash": "hash_rebuild_db",
                        "kept_path": "keep.jpg",
                        "items": [
                            {"role": "kept", "path": "keep.jpg"},
                            {"role": "duplicate", "path": "dup.jpg"},
                        ],
                    },
                ],
            },
            source_path=database_path,
        )
        HashDbRepository(database_path).save_hash_db(
            {"phash": {"hash_rebuild_db": [str(root / "keep.jpg")]}, "strict": {}},
            source_path=database_path,
        )
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake rebuild finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()
        ztb_app.summarize_task_root(task)

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_rebuild_completed_with_database_outputs)

    response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(root))

    assert response.status_code == 200
    database_path = RootContext.from_root(root, ztb_app.ROOT_DATA_DIR).database_path
    assert DuplicateResultRepository(database_path).load_summary()["method_counts"] == {"phash": 1}
    assert HashDbRepository(database_path).load_summary()["method_counts"] == {
        "phash": {"record_count": 1, "path_count": 1}
    }


def test_rebuild_hash_db_persists_rebuild_root_separately_from_destination_defaults(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    rebuild_root = workspace / "rebuild_root"
    rebuild_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_task_completed)

    organizer_response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination))
    assert organizer_response.status_code == 200

    rebuild_response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(rebuild_root))
    assert rebuild_response.status_code == 200

    config = client.get("/api/config").json()
    assert config["task_defaults"]["dst"] == str(destination)
    assert config["task_defaults"]["rebuild_root"] == str(rebuild_root)


def test_run_organizer_persists_skip_existing_exact_default(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    rebuild_root = workspace / "rebuild_root"
    rebuild_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_task_completed)

    organizer_data = organizer_payload(image_root, destination)
    organizer_data["skip_existing_exact"] = False
    organizer_response = client.post("/api/tasks/run-organizer", json=organizer_data)
    assert organizer_response.status_code == 200

    rebuild_response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(rebuild_root))
    assert rebuild_response.status_code == 200

    config = client.get("/api/config").json()
    assert config["task_defaults"]["skip_existing_exact"] is False


def test_rebuild_hash_db_persists_rebuild_phash_threshold_separately(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    rebuild_root = workspace / "rebuild_root"
    rebuild_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_task_completed)

    organizer_data = organizer_payload(image_root, destination)
    organizer_data["phash_threshold"] = 5
    organizer_response = client.post("/api/tasks/run-organizer", json=organizer_data)
    assert organizer_response.status_code == 200

    rebuild_data = rebuild_payload(rebuild_root)
    rebuild_data["hash_method"] = "phash"
    rebuild_data["phash_threshold"] = 9
    rebuild_response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_data)
    assert rebuild_response.status_code == 200

    config = client.get("/api/config").json()
    assert config["task_defaults"]["phash_threshold"] == 5
    assert config["task_defaults"]["rebuild_phash_threshold"] == 9


def test_completed_task_saves_root_summary_for_index_reuse(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    destination.mkdir(parents=True, exist_ok=True)
    original_thread = tasks_routes.threading.Thread
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_completed_with_outputs(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        create_test_image(destination / "2026" / "04" / "25" / "a.jpg")
        create_test_image(destination / "2026" / "04" / "25" / "b.jpg", color=(10, 20, 30))
        database_path = Path(ztb_app.TASK_REGISTRY.tasks[task_id]["outputs"]["database_path"])
        DuplicateResultRepository(database_path).save_result(
            {
                "destination_root": str(destination),
                "group_count": 1,
                "groups": [
                    {
                        "group_id": "dup_1",
                        "reason": "strict",
                        "hash": "hash_1",
                        "kept_path": "2026/04/25/a.jpg",
                        "items": [
                            {"role": "kept", "path": "2026/04/25/a.jpg"},
                            {"role": "duplicate", "path": "2026/04/25/b.jpg"},
                        ],
                    },
                ],
            },
            source_path=database_path,
        )
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake organizer finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()
        ztb_app.summarize_task_root(task)

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_completed_with_outputs)

    response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination))
    assert response.status_code == 200
    monkeypatch.setattr(tasks_routes.threading, "Thread", original_thread)

    client.post("/api/settings/roots", json={"path": str(destination)})
    config = client.get("/api/config").json()
    assert config["root_summary"]["image_count"] == 2
    assert config["root_summary"]["duplicate_group_count"] == 1
    assert isinstance(config["root_summary"]["updated_at"], str)
    assert config["duplicate_results"]["group_count"] == 1

    images = client.get("/api/images?offset=0&limit=48&include_exif=false&async_scan=true&refresh_scan=false&include_total=true").json()
    assert images["total"] == 2
    assert isinstance(images["total_generated_at"], str)


def test_completed_rebuild_task_saves_root_summary_for_index_reuse(api_client, monkeypatch) -> None:
    client, workspace, _, _ = api_client
    rebuild_root = workspace / "rebuilt_archive"
    rebuild_root.mkdir(parents=True, exist_ok=True)
    create_test_image(rebuild_root / "keep.jpg")
    create_test_image(rebuild_root / "dup.jpg", color=(90, 80, 70))
    original_thread = tasks_routes.threading.Thread
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_rebuild_completed_with_outputs(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        database_path = Path(ztb_app.TASK_REGISTRY.tasks[task_id]["outputs"]["database_path"])
        DuplicateResultRepository(database_path).save_result(
            {
                "destination_root": str(rebuild_root),
                "group_count": 1,
                "groups": [
                    {
                        "group_id": "dup_rebuild",
                        "reason": "strict",
                        "hash": "hash_rebuild",
                        "kept_path": "keep.jpg",
                        "items": [
                            {"role": "kept", "path": "keep.jpg"},
                            {"role": "duplicate", "path": "dup.jpg"},
                        ],
                    },
                ],
            },
            source_path=database_path,
        )
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        task["output_lines"] = ["fake rebuild finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()
        ztb_app.summarize_task_root(task)

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_rebuild_completed_with_outputs)

    response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(rebuild_root))
    assert response.status_code == 200
    monkeypatch.setattr(tasks_routes.threading, "Thread", original_thread)

    client.post("/api/settings/roots", json={"path": str(rebuild_root)})
    config = client.get("/api/config").json()
    assert config["root_summary"]["image_count"] == 2
    assert config["root_summary"]["duplicate_group_count"] == 1
    assert isinstance(config["root_summary"]["updated_at"], str)
    assert config["duplicate_results"]["group_count"] == 1

    images = client.get("/api/images?offset=0&limit=48&include_exif=false&async_scan=true&refresh_scan=false&include_total=true").json()
    assert images["total"] == 2
    assert isinstance(images["total_generated_at"], str)
