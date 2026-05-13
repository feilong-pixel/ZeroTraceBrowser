# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class TaskRegistry:
    def __init__(self) -> None:
        self.tasks: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def _has_running_task_unlocked(self) -> bool:
        return any(task.get("status") == "running" for task in self.tasks.values())

    def has_running_task(self) -> bool:
        with self.lock:
            return self._has_running_task_unlocked()

    def get_running_task(self) -> dict[str, Any] | None:
        with self.lock:
            for task in self.tasks.values():
                if task.get("status") == "running":
                    return task
        return None

    def add(self, task: dict[str, Any]) -> None:
        with self.lock:
            self.tasks[task["task_id"]] = task

    def add_if_idle(self, task: dict[str, Any]) -> bool:
        with self.lock:
            if self._has_running_task_unlocked():
                return False
            self.tasks[task["task_id"]] = task
            return True

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.tasks.get(task_id)

    def serialize(self, task: dict[str, Any]) -> dict[str, Any]:
        outputs = task["outputs"]

        def output_exists(path_value: str) -> bool:
            return bool(path_value.strip()) and Path(path_value).exists()

        return {
            "task_id": task["task_id"],
            "task_type": task.get("task_type", "organizer"),
            "status": task["status"],
            "started_at": task["started_at"],
            "finished_at": task.get("finished_at"),
            "params": task["params"],
            "outputs": {
                **outputs,
                "log_exists": output_exists(outputs["log_path"]),
                "duplicate_report_exists": output_exists(outputs["duplicate_report_path"]),
                "hash_db_exists": output_exists(outputs["hash_db_path"]),
                "database_exists": output_exists(outputs.get("database_path", "")),
            },
            "output_lines": task["output_lines"][-40:],
            "return_code": task.get("return_code"),
            "error": task.get("error"),
        }

    def run_subprocess_task(
        self,
        task_id: str,
        command: list[str],
        workdir: Path,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        with self.lock:
            task = self.tasks[task_id]

        try:
            output_queue = __import__("queue").Queue()
            env = os.environ.copy()
            if env_overrides:
                env.update(env_overrides)
            process = subprocess.Popen(
                command,
                cwd=str(workdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env=env,
            )
            output_lines: list[str] = []
            assert process.stdout is not None

            def read_stdout() -> None:
                assert process.stdout is not None
                for line in process.stdout:
                    clean_line = line.rstrip()
                    if clean_line:
                        output_queue.put(clean_line)

            threading.Thread(target=read_stdout, daemon=True).start()
            last_heartbeat_at = datetime.now()

            while process.poll() is None:
                try:
                    line = output_queue.get(timeout=0.5)
                    output_lines.append(line)
                    last_heartbeat_at = datetime.now()
                    with self.lock:
                        task["output_lines"] = output_lines[-200:]
                except Exception:
                    if (datetime.now() - last_heartbeat_at).total_seconds() >= 5:
                        output_lines.append("__ZTB_TASK_STILL_RUNNING__")
                        last_heartbeat_at = datetime.now()
                        with self.lock:
                            task["output_lines"] = output_lines[-200:]

            while not output_queue.empty():
                line = output_queue.get_nowait()
                output_lines.append(line)
                with self.lock:
                    task["output_lines"] = output_lines[-200:]

            return_code = process.wait()
            with self.lock:
                task["return_code"] = return_code
                task["status"] = "completed" if return_code == 0 else "failed"
                task["finished_at"] = datetime.now().isoformat()
                if return_code != 0 and not task.get("error"):
                    task["error"] = "Organizer process failed"
        except Exception as exc:
            with self.lock:
                task["status"] = "failed"
                task["finished_at"] = datetime.now().isoformat()
                task["error"] = str(exc)
