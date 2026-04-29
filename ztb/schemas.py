# SPDX-License-Identifier: MIT

from __future__ import annotations

from pydantic import BaseModel, Field


class FileActionRequest(BaseModel):
    relative_path: str = Field(..., min_length=1)


class CopyRequest(FileActionRequest):
    target_dir: str = Field(default="", min_length=0)


class RootAddRequest(BaseModel):
    path: str = Field(..., min_length=1)


class RootUpdateRequest(BaseModel):
    path: str = Field(..., min_length=1)
    cleanup_root_data: bool = Field(default=False)


class OpenPathRequest(BaseModel):
    path: str = Field(..., min_length=1)


class LanguageUpdateRequest(BaseModel):
    language: str = Field(..., min_length=2)


class CopyTargetUpdateRequest(BaseModel):
    default_copy_target: str = Field(default="")


class OrganizerTaskRequest(BaseModel):
    src: str = Field(..., min_length=1)
    dst: str = Field(..., min_length=1)
    mode: str = Field(default="copy")
    duplicate_detection: str = Field(default="phash")
    phash_threshold: int = Field(default=4, ge=0)
    lang: str = Field(default="en")


class RebuildHashDbTaskRequest(BaseModel):
    root: str = Field(..., min_length=1)
    rebuild_mode: str = Field(default="replace")
    hash_method: str = Field(default="both")
    lang: str = Field(default="en")


class RestoreDeletedRequest(BaseModel):
    deleted_to: str = Field(..., min_length=1)


class ClearDeletedRequest(BaseModel):
    confirm: bool = Field(default=False)


class ClearRecycleLogsRequest(ClearDeletedRequest):
    actions: list[str] = Field(default_factory=list)


class PurgeDeletedRequest(BaseModel):
    deleted_to: str = Field(..., min_length=1)
