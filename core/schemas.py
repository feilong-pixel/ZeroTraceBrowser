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


class DisplayStyleUpdateRequest(BaseModel):
    display_style: str = Field(..., min_length=1)


class CopyTargetUpdateRequest(BaseModel):
    default_copy_target: str = Field(default="")


class OrganizerTaskRequest(BaseModel):
    src: str = Field(..., min_length=1)
    dst: str = Field(..., min_length=1)
    mode: str = Field(default="copy")
    duplicate_detection: str = Field(default="phash")
    phash_threshold: int = Field(default=4, ge=0)
    skip_existing_exact: bool = Field(default=True)
    lang: str = Field(default="en")


class RebuildHashDbTaskRequest(BaseModel):
    root: str = Field(..., min_length=1)
    rebuild_mode: str = Field(default="replace")
    hash_method: str = Field(default="both")
    phash_threshold: int = Field(default=4, ge=0)
    lang: str = Field(default="en")


class SimilaritySearchRequest(BaseModel):
    relative_path: str = Field(..., min_length=1)
    source: str = Field(default="local")
    method: str = Field(default="phash")
    threshold: int = Field(default=8, ge=0, le=64)
    limit: int = Field(default=50, ge=1, le=200)


class IphoneIndexRequest(BaseModel):
    device_id: str = Field(..., min_length=1)
    limit: int = Field(default=1, ge=1, le=10000)
    copy_all: bool = Field(default=False)


class IphoneDeleteRequest(BaseModel):
    device_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class MobileIndexRequest(BaseModel):
    device_type: str = Field(default="iphone", min_length=1)
    device_id: str = Field(..., min_length=1)
    limit: int = Field(default=1, ge=1, le=10000)
    copy_all: bool = Field(default=False)


class MobileDeleteRequest(BaseModel):
    device_type: str = Field(default="iphone", min_length=1)
    device_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class RestoreDeletedRequest(BaseModel):
    deleted_to: str = Field(..., min_length=1)


class ClearDeletedRequest(BaseModel):
    confirm: bool = Field(default=False)


class ClearRecycleLogsRequest(ClearDeletedRequest):
    actions: list[str] = Field(default_factory=list)


class PurgeDeletedRequest(BaseModel):
    deleted_to: str = Field(..., min_length=1)
