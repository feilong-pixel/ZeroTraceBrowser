# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException


def normalize_task_mode(mode: str) -> str:
    return mode if mode in {"copy", "move"} else "copy"


def normalize_duplicate_detection(duplicate_detection: str) -> str:
    return duplicate_detection if duplicate_detection in {"off", "phash", "strict"} else "phash"


def normalize_phash_threshold(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 4


def normalize_task_lang(language: str) -> str:
    return {"zh": "zh", "en": "en", "ja": "ja"}.get(language, language)


class SettingsStore:
    def __init__(
        self,
        settings_path: Path,
        default_image_root: str,
        default_copy_target: str,
        supported_languages: set[str],
    ) -> None:
        self.settings_path = settings_path
        self.default_image_root = default_image_root
        self.default_copy_target = default_copy_target
        self.supported_languages = supported_languages

    def default_settings(self) -> dict[str, Any]:
        return {
            "language": "en",
            "image_roots": [self.default_image_root],
            "active_root": self.default_image_root,
            "default_copy_target": self.default_copy_target,
            "root_summaries": {},
            "task_defaults": {
                "src": "",
                "dst": "",
                "rebuild_root": "",
                "mode": "copy",
                "duplicate_detection": "phash",
                "phash_threshold": 4,
            },
        }

    def load(self) -> dict[str, Any]:
        settings = self.default_settings()
        if self.settings_path.exists():
            with self.settings_path.open("r", encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                settings.update(stored)

        roots = [
            str(Path(path).expanduser().resolve())
            for path in settings.get("image_roots", [])
            if str(path).strip()
        ]
        if not roots:
            roots = [self.default_image_root]
        settings["image_roots"] = list(dict.fromkeys(roots))

        active_root = str(Path(settings.get("active_root", roots[0])).expanduser().resolve())
        if active_root not in settings["image_roots"]:
            active_root = settings["image_roots"][0]
        settings["active_root"] = active_root

        language = settings.get("language", "en").strip()
        settings["language"] = language if language in self.supported_languages else "en"
        settings["default_copy_target"] = str(
            settings.get("default_copy_target", self.default_copy_target)
        ).strip()
        root_summaries = settings.get("root_summaries", {})
        if not isinstance(root_summaries, dict):
            root_summaries = {}
        normalized_root_summaries: dict[str, dict[str, Any]] = {}
        for raw_root, raw_summary in root_summaries.items():
            if not isinstance(raw_summary, dict):
                continue
            normalized_root = str(Path(raw_root).expanduser().resolve())
            normalized_root_summaries[normalized_root] = {
                "image_count": raw_summary.get("image_count") if isinstance(raw_summary.get("image_count"), int) else None,
                "duplicate_group_count": raw_summary.get("duplicate_group_count") if isinstance(raw_summary.get("duplicate_group_count"), int) else None,
                "updated_at": str(raw_summary.get("updated_at", "")).strip(),
            }
        settings["root_summaries"] = normalized_root_summaries

        task_defaults = settings.get("task_defaults", {})
        if not isinstance(task_defaults, dict):
            task_defaults = {}
        settings["task_defaults"] = {
            "src": str(task_defaults.get("src", "")).strip(),
            "dst": str(task_defaults.get("dst", "")).strip(),
            "rebuild_root": str(task_defaults.get("rebuild_root", "")).strip(),
            "mode": normalize_task_mode(str(task_defaults.get("mode", "copy")).strip()),
            "duplicate_detection": normalize_duplicate_detection(
                str(task_defaults.get("duplicate_detection", "phash")).strip(),
            ),
            "phash_threshold": normalize_phash_threshold(task_defaults.get("phash_threshold", 4)),
        }
        return settings

    def save(self, settings: dict[str, Any]) -> None:
        self.settings_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def active_root(self) -> Path:
        return Path(self.load()["active_root"]).resolve()

    def validate_language(self, language: str) -> str:
        if language not in self.supported_languages:
            raise HTTPException(status_code=400, detail="Unsupported language")
        return language

    def serialize(self, settings: dict[str, Any]) -> dict[str, Any]:
        return {
            "language": settings["language"],
            "image_roots": settings["image_roots"],
            "active_root": settings["active_root"],
            "default_copy_target": settings["default_copy_target"],
            "root_summaries": settings.get("root_summaries", {}),
            "task_defaults": settings["task_defaults"],
        }

    def remember_task_defaults(self, src: str, dst: str, mode: str, duplicate_detection: str, phash_threshold: Any) -> None:
        settings = self.load()
        existing_defaults = settings.get("task_defaults", {})
        settings["task_defaults"] = {
            "src": str(Path(src).expanduser().resolve()),
            "dst": str(Path(dst).expanduser().resolve()),
            "rebuild_root": str(existing_defaults.get("rebuild_root", "")).strip(),
            "mode": normalize_task_mode(mode),
            "duplicate_detection": normalize_duplicate_detection(duplicate_detection),
            "phash_threshold": normalize_phash_threshold(phash_threshold),
        }
        self.save(settings)

    def save_root_summary(
        self,
        root: str,
        image_count: int | None = None,
        duplicate_group_count: int | None = None,
        updated_at: str = "",
    ) -> None:
        settings = self.load()
        root_key = str(Path(root).expanduser().resolve())
        root_summaries = settings.get("root_summaries", {})
        if not isinstance(root_summaries, dict):
            root_summaries = {}
        existing = root_summaries.get(root_key, {})
        if not isinstance(existing, dict):
            existing = {}
        root_summaries[root_key] = {
            "image_count": image_count if isinstance(image_count, int) else existing.get("image_count"),
            "duplicate_group_count": duplicate_group_count if isinstance(duplicate_group_count, int) else existing.get("duplicate_group_count"),
            "updated_at": updated_at or str(existing.get("updated_at", "")).strip(),
        }
        settings["root_summaries"] = root_summaries
        self.save(settings)

    def remember_rebuild_root(self, rebuild_root: str) -> None:
        settings = self.load()
        task_defaults = settings.get("task_defaults", {})
        if not isinstance(task_defaults, dict):
            task_defaults = {}
        task_defaults["rebuild_root"] = str(Path(rebuild_root).expanduser().resolve())
        settings["task_defaults"] = {
            "src": str(task_defaults.get("src", "")).strip(),
            "dst": str(task_defaults.get("dst", "")).strip(),
            "rebuild_root": str(task_defaults.get("rebuild_root", "")).strip(),
            "mode": normalize_task_mode(str(task_defaults.get("mode", "copy")).strip()),
            "duplicate_detection": normalize_duplicate_detection(
                str(task_defaults.get("duplicate_detection", "phash")).strip(),
            ),
            "phash_threshold": normalize_phash_threshold(task_defaults.get("phash_threshold", 4)),
        }
        self.save(settings)
