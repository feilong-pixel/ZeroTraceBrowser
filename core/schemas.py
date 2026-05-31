# SPDX-License-Identifier: MIT

from __future__ import annotations

from pydantic import BaseModel, Field


class FileActionRequest(BaseModel):
    relative_path: str = Field(..., min_length=1)


class DeleteBatchRequest(BaseModel):
    relative_paths: list[str] = Field(..., min_length=1, max_length=200)


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
    duplicate_detection: str = Field(default="strict")
    phash_threshold: int = Field(default=4, ge=0)
    skip_existing_exact: bool = Field(default=True)
    lang: str = Field(default="en")


class RebuildHashDbTaskRequest(BaseModel):
    root: str = Field(..., min_length=1)
    rebuild_mode: str = Field(default="replace")
    hash_method: str = Field(default="strict")
    phash_threshold: int = Field(default=4, ge=0)
    lang: str = Field(default="en")


class RebuildImageIndexTaskRequest(BaseModel):
    root: str = Field(..., min_length=1)
    lang: str = Field(default="en")


class TimestampRepairTaskRequest(BaseModel):
    root: str = Field(..., min_length=1)
    threshold_days: int = Field(default=7, ge=1)
    sync_modified_time: bool = Field(default=True)
    rename_from_exif: bool = Field(default=False)
    include_videos: bool = Field(default=False)
    lang: str = Field(default="en")


class SimilaritySearchRequest(BaseModel):
    relative_path: str = Field(..., min_length=1)
    source: str = Field(default="local")
    method: str = Field(default="phash")
    threshold: int = Field(default=8, ge=0, le=256)
    limit: int = Field(default=50, ge=1, le=200)


class SimilarityCacheBuildRequest(BaseModel):
    source: str = Field(default="local")
    methods: list[str] = Field(default_factory=lambda: ["document", "feature", "embedding"])
    limit: int = Field(default=200, ge=1, le=10000)


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


class MobilePairRequest(BaseModel):
    pairing_token: str = Field(..., min_length=1)
    device_type: str = Field(default="iphone", min_length=1)
    device_id: str = Field(..., min_length=1)
    device_name: str = Field(default="")
    device_model: str = Field(default="")
    platform: str = Field(default="")
    app_id: str = Field(default="")
    app_version: str = Field(default="")
    owner_label: str = Field(default="")
    capabilities: dict = Field(default_factory=dict)


class MobileSyncStartRequest(BaseModel):
    device_type: str = Field(default="iphone", min_length=1)
    device_id: str = Field(..., min_length=1)
    sync_token: str = Field(..., min_length=1)
    last_client_cursor: str = Field(default="")
    battery_state: str = Field(default="")
    network_type: str = Field(default="")


class MobileManifestItem(BaseModel):
    item_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    media_type: str | None = Field(default="")
    mime_type: str | None = Field(default="")
    size: int = Field(default=0, ge=0)
    created_at: str | None = Field(default="")
    modified_at: str | None = Field(default="")
    timezone: str | None = Field(default="")
    album: str | None = Field(default="")
    relative_hint: str | None = Field(default="")
    width: int | None = Field(default=0, ge=0)
    height: int | None = Field(default=0, ge=0)
    duration_ms: int | None = Field(default=0, ge=0)
    sha256: str | None = Field(default="")
    paired_item_id: str | None = Field(default="")
    is_favorite: bool | None = Field(default=False)
    is_screenshot: bool | None = Field(default=False)


class MobileSyncManifestRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    server_id: str = Field(default="")
    root_id: str = Field(default="")
    device_type: str = Field(default="iphone", min_length=1)
    device_id: str = Field(..., min_length=1)
    items: list[MobileManifestItem] = Field(default_factory=list)


class RestoreDeletedRequest(BaseModel):
    deleted_to: str = Field(..., min_length=1)


class ClearDeletedRequest(BaseModel):
    confirm: bool = Field(default=False)


class ClearRecycleLogsRequest(ClearDeletedRequest):
    actions: list[str] = Field(default_factory=list)


class PurgeDeletedRequest(BaseModel):
    deleted_to: str = Field(..., min_length=1)
