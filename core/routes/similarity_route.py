# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from core.schemas import SimilarityCacheBuildRequest, SimilaritySearchRequest


def create_similarity_router(ctx: Any) -> APIRouter:
    router = APIRouter()

    # POST /api/similarity/search
    @router.post("/api/similarity/search")
    def search_similarity(payload: SimilaritySearchRequest) -> dict[str, Any]:
        return ctx.search_similar_images(
            relative_path=payload.relative_path,
            source=payload.source,
            method=payload.method,
            threshold=payload.threshold,
            limit=payload.limit,
        )

    @router.post("/api/similarity/cache/build")
    def build_similarity_cache(payload: SimilarityCacheBuildRequest) -> dict[str, Any]:
        return ctx.build_similarity_cache(
            source=payload.source,
            methods=payload.methods,
            limit=payload.limit,
        )

    return router
