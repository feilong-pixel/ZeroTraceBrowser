from .base import *
from .settings_context import load_settings
from .image_context import resolve_under_root
from .root_workspace import root_database_path
from core.storage.hash_db_repository import HashDbRepository
from MediaArchiveOrganizer.core.duplicate_detector import compute_phash, phash_distance


def search_similar_images(
    relative_path: str,
    method: str = "phash",
    threshold: int = 8,
    limit: int = 50,
) -> dict[str, Any]:
    method = str(method or "phash").strip().lower()
    if method != "phash":
        raise HTTPException(status_code=400, detail="Unsupported similarity method")

    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    query_path = resolve_under_root(active_root, relative_path)
    if not query_path.exists() or not query_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    query_hash = compute_phash(str(query_path))
    if not query_hash:
        return {
            "query": str(relative_path),
            "method": method,
            "query_hash": "",
            "items": [],
            "count": 0,
        }

    database_path = root_database_path(active_root)
    hash_db = HashDbRepository(database_path).load_hash_db()
    records = hash_db.get("phash", {})
    items: list[dict[str, Any]] = []

    for candidate_hash, paths in records.items():
        try:
            distance = phash_distance(query_hash, str(candidate_hash))
        except ValueError:
            continue
        if distance > threshold:
            continue

        for candidate in paths:
            candidate_path = Path(candidate).expanduser().resolve()
            if candidate_path == query_path or not candidate_path.exists() or not candidate_path.is_file():
                continue
            try:
                candidate_relative = candidate_path.relative_to(active_root).as_posix()
            except ValueError:
                continue
            items.append(
                {
                    "relative_path": candidate_relative,
                    "hash": str(candidate_hash),
                    "distance": distance,
                    "score": round(1 - (distance / 64), 4),
                    "reason": method,
                }
            )

    items.sort(key=lambda item: (item["distance"], item["relative_path"].lower()))
    items = items[:limit]
    return {
        "query": str(relative_path),
        "method": method,
        "query_hash": query_hash,
        "threshold": threshold,
        "items": items,
        "count": len(items),
    }
