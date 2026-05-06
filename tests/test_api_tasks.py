# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import app as ztb_app
import core.routes.tasks as tasks_routes
from tests.test_api_duplicates import write_duplicates_json
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
        "lang": "en",
    }


def rebuild_payload(root: Path) -> dict[str, object]:
    return {
        "root": str(root),
        "rebuild_mode": "replace",
        "hash_method": "strict",
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

    query_response = client.get(f"/api/tasks/{task['task_id']}")
    assert query_response.status_code == 200
    assert query_response.json()["status"] == "completed"


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

        json_index = command.index("--duplicates-json-path") + 1
        Path(command[json_index]).write_text(
            '{"destination_root":"","group_count":0,"groups":[]}',
            encoding="utf-8",
        )

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_rebuild_completed)

    response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(image_root))

    assert response.status_code == 200
    task = response.json()
    assert task["task_type"] == "rebuild_hash_db"
    assert task["status"] == "completed"
    assert task["outputs"]["duplicates_json_exists"] is True
    assert task["params"]["root"] == str(image_root)

    query_response = client.get(f"/api/tasks/{task['task_id']}")
    assert query_response.status_code == 200
    assert query_response.json()["output_lines"] == ["fake rebuild finished"]


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
        json_index = command.index("--duplicates-json-path") + 1
        rebuild_root = Path(command[root_index])
        json_path = Path(command[json_index])

        if rebuild_root == root_a:
            write_duplicates_json(
                json_path,
                root_a,
                [
                    {
                        "group_id": "dup_a",
                        "reason": "strict",
                        "hash": "hash_a",
                        "kept_path": "same.jpg",
                        "items": [
                            {"role": "kept", "path": "same.jpg"},
                            {"role": "duplicate", "path": "same_dup1.jpg"},
                        ],
                    },
                ],
            )
        elif rebuild_root == root_b:
            write_duplicates_json(
                json_path,
                root_b,
                [
                    {
                        "group_id": "dup_b",
                        "reason": "strict",
                        "hash": "hash_b",
                        "kept_path": "other.jpg",
                        "items": [
                            {"role": "kept", "path": "other.jpg"},
                            {"role": "duplicate", "path": "other_dup1.jpg"},
                        ],
                    },
                ],
            )
        else:
            raise AssertionError(f"Unexpected rebuild root: {rebuild_root}")

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_rebuild_completed)

    first_response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(root_a))
    assert first_response.status_code == 200
    first_task = first_response.json()
    assert first_task["outputs"]["duplicates_json_exists"] is True

    second_response = client.post("/api/tasks/rebuild-hash-db", json=rebuild_payload(root_b))
    assert second_response.status_code == 200
    second_task = second_response.json()
    assert second_task["outputs"]["duplicates_json_exists"] is True

    client.post("/api/settings/active-root", json={"path": str(root_a)})
    payload_a = client.get("/api/duplicates").json()
    assert payload_a["destination_root"] == str(root_a)
    assert payload_a["groups"][0]["group_id"] == "dup_a"

    client.post("/api/settings/active-root", json={"path": str(root_b)})
    payload_b = client.get("/api/duplicates").json()
    assert payload_b["destination_root"] == str(root_b)
    assert payload_b["groups"][0]["group_id"] == "dup_b"


def test_run_organizer_uses_task_scoped_duplicates_and_shared_hash_db(api_client, monkeypatch) -> None:
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

    first_task = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination)).json()
    second_task = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination)).json()

    assert first_task["outputs"]["duplicates_json_path"] != second_task["outputs"]["duplicates_json_path"]
    assert first_task["outputs"]["hash_db_path"] == second_task["outputs"]["hash_db_path"]
    assert first_task["outputs"]["duplicates_json_path"].endswith("duplicates.json")
    assert first_task["outputs"]["hash_db_path"].endswith("hash_db.json")
    assert first_task["outputs"]["duplicates_json_path"] != str(ztb_app.root_duplicates_path(destination))
    assert captured[0]["env"] == {"IMAGE_ORGANIZER_HASH_DB": first_task["outputs"]["hash_db_path"]}
    assert captured[1]["env"] == {"IMAGE_ORGANIZER_HASH_DB": second_task["outputs"]["hash_db_path"]}

    first_command = captured[0]["command"]
    assert isinstance(first_command, list)
    assert first_command[first_command.index("--duplicates-json-path") + 1] == first_task["outputs"]["duplicates_json_path"]


def test_run_organizer_does_not_overwrite_published_duplicates(api_client, monkeypatch) -> None:
    client, workspace, image_root, _ = api_client
    destination = workspace / "organized"
    destination.mkdir(parents=True, exist_ok=True)
    published_path = ztb_app.root_duplicates_path(destination)
    write_duplicates_json(
        published_path,
        destination,
        [
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
    )
    before = published_path.read_text(encoding="utf-8")
    monkeypatch.setattr(tasks_routes.threading, "Thread", ImmediateThread)

    def mark_completed_with_empty_duplicates(
        task_id: str,
        command: list[str],
        workdir: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        task = ztb_app.TASK_REGISTRY.tasks[task_id]
        json_index = command.index("--duplicates-json-path") + 1
        Path(command[json_index]).write_text(
            '{"destination_root":"","group_count":0,"groups":[]}',
            encoding="utf-8",
        )
        task["output_lines"] = ["fake organizer finished"]
        task["return_code"] = 0
        task["status"] = "completed"
        task["finished_at"] = datetime.now().isoformat()
        ztb_app.summarize_task_root(task)

    monkeypatch.setattr(ztb_app, "run_organizer_task", mark_completed_with_empty_duplicates)

    response = client.post("/api/tasks/run-organizer", json=organizer_payload(image_root, destination))

    assert response.status_code == 200
    assert published_path.read_text(encoding="utf-8") == before


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

    assert first_task["outputs"]["duplicates_json_path"] == second_task["outputs"]["duplicates_json_path"]
    assert first_task["outputs"]["hash_db_path"] == second_task["outputs"]["hash_db_path"]
    assert captured[0]["env"] == {"IMAGE_ORGANIZER_HASH_DB": first_task["outputs"]["hash_db_path"]}
    assert captured[1]["env"] == {"IMAGE_ORGANIZER_HASH_DB": second_task["outputs"]["hash_db_path"]}


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
        json_path = Path(ztb_app.TASK_REGISTRY.tasks[task_id]["outputs"]["duplicates_json_path"])
        write_duplicates_json(
            json_path,
            destination,
            [
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
    assert config["root_summary"]["duplicate_group_count"] is None
    assert isinstance(config["root_summary"]["updated_at"], str)
    assert config["duplicate_results"]["group_count"] == 0

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
        json_path = Path(ztb_app.TASK_REGISTRY.tasks[task_id]["outputs"]["duplicates_json_path"])
        write_duplicates_json(
            json_path,
            rebuild_root,
            [
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
