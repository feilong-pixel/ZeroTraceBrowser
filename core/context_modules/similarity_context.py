from .base import *
from .settings_context import load_settings
from .image_context import iter_image_files, resolve_under_root
from .root_workspace import root_database_path
import io
import math
from core.domain.root_context import RootContext
from core.storage.duplicates_repository import DuplicateResultRepository
from core.storage.hash_db_repository import HashDbRepository
from core.storage.mobile_repository import MobileRepository
from core.storage.similarity_repository import SimilarityRepository
from media_engine.core.duplicate_detector import (
    compute_document_hash,
    compute_phash,
    document_hash_distance,
    phash_distance,
)

FEATURE_DISTANCE_MAX = 100
FEATURE_DESCRIPTOR_CACHE: dict[tuple[str, int, int], tuple[str, int, Any]] = {}
FEATURE_CACHE_MODEL = "orb-akaze"
FEATURE_CACHE_VERSION = 1
DOCUMENT_CACHE_VERSION = 1
EMBEDDING_CACHE_MODEL = "ztb-lite-v1"
EMBEDDING_CACHE_VERSION = 1
EMBEDDING_DISTANCE_MAX = 100


def _resolve_similarity_query_path(active_root: Path, candidate: str) -> tuple[Path, str]:
    raw_candidate = str(candidate or "").strip().strip('"')
    if not raw_candidate:
        raise HTTPException(status_code=400, detail="Image path is required")

    candidate_path = Path(raw_candidate).expanduser()
    if candidate_path.is_absolute():
        query_path = candidate_path.resolve()
        try:
            relative_path = query_path.relative_to(active_root).as_posix()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Path escapes configured root") from exc
        return query_path, relative_path

    query_path = resolve_under_root(active_root, raw_candidate)
    try:
        relative_path = query_path.relative_to(active_root).as_posix()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path escapes configured root") from exc
    if not query_path.exists() and Path(raw_candidate).name == raw_candidate:
        matches: list[Path] = []
        for matched_path in active_root.rglob(raw_candidate):
            if matched_path.is_file():
                matches.append(matched_path.resolve())
                if len(matches) > 1:
                    break
        if len(matches) == 1:
            matched_path = matches[0]
            return matched_path, matched_path.relative_to(active_root).as_posix()
        if len(matches) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Multiple images matched filename. Use a relative path: {raw_candidate}",
            )
    return query_path, relative_path


def _collect_similarity_candidates(
    active_root: Path,
    query_path: Path,
    hash_db: dict[str, dict[str, list[str]]],
) -> dict[str, list[Path]]:
    candidates: dict[str, list[Path]] = {}
    seen_paths: set[Path] = set()

    def add_candidate(path: Path, hash_value: str | None = None) -> None:
        candidate_path = path.expanduser().resolve()
        if candidate_path == query_path or candidate_path in seen_paths:
            return
        if not candidate_path.exists() or not candidate_path.is_file():
            return
        try:
            candidate_path.relative_to(active_root)
        except ValueError:
            return

        candidate_hash = hash_value or compute_phash(str(candidate_path))
        if not candidate_hash:
            return
        seen_paths.add(candidate_path)
        candidates.setdefault(candidate_hash, []).append(candidate_path)

    for hash_value, paths in hash_db.get("phash", {}).items():
        for path in paths:
            add_candidate(Path(path), str(hash_value))

    for path in iter_image_files(active_root):
        add_candidate(path)

    return candidates


def _collect_similarity_candidate_paths(
    active_root: Path,
    query_path: Path,
    hash_db: dict[str, dict[str, list[str]]],
) -> list[Path]:
    seen_paths: set[Path] = set()
    candidates: list[Path] = []

    def add_path(path: Path) -> None:
        candidate_path = path.expanduser().resolve()
        if candidate_path == query_path or candidate_path in seen_paths:
            return
        if not candidate_path.exists() or not candidate_path.is_file():
            return
        try:
            candidate_path.relative_to(active_root)
        except ValueError:
            return
        seen_paths.add(candidate_path)
        candidates.append(candidate_path)

    for paths in hash_db.get("phash", {}).values():
        for path in paths:
            add_path(Path(path))

    for path in iter_image_files(active_root):
        add_path(path)

    return candidates


def _collect_duplicate_group_matches(active_root: Path, query_relative_path: str) -> dict[str, dict[str, Any]]:
    payload = DuplicateResultRepository(
        RootContext.from_root(active_root, ROOT_DATA_DIR, ensure=True).database_path
    ).load_result()
    if payload is None:
        return {}

    destination_root = str(payload.get("destination_root", "")).strip()
    if not destination_root or Path(destination_root).expanduser().resolve() != active_root:
        return {}

    matches: dict[str, dict[str, Any]] = {}
    for group in payload.get("groups", []):
        if not isinstance(group, dict):
            continue
        items = group.get("items", [])
        if not isinstance(items, list):
            continue
        group_paths = [
            str(item.get("path", "")).strip()
            for item in items
            if isinstance(item, dict) and str(item.get("path", "")).strip()
        ]
        if query_relative_path not in group_paths:
            continue

        reason = str(group.get("reason", "duplicates") or "duplicates")
        for item_path in group_paths:
            if item_path == query_relative_path:
                continue
            try:
                candidate_path = resolve_under_root(active_root, item_path)
            except HTTPException:
                continue
            if not candidate_path.exists() or not candidate_path.is_file():
                continue
            matches[item_path] = {
                "relative_path": item_path,
                "hash": str(group.get("hash", "")),
                "distance": 0,
                "score": 1,
                "reason": f"duplicates:{reason}",
                "source": "duplicates",
            }
    return matches


def _load_feature_image(path: Path):
    try:
        import cv2
        import numpy
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="OpenCV is required for feature similarity. Install opencv-python-headless.",
        ) from exc

    try:
        if Image is None or ImageOps is None:
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                return None
            return image
        with Image.open(path) as img:
            normalized = ImageOps.exif_transpose(img).convert("L")
            return numpy.array(normalized)
    except Exception:
        return None


def _active_similarity_cache_context(path: Path) -> tuple[Path, str, SimilarityRepository] | None:
    try:
        settings = load_settings()
        active_root = Path(settings["active_root"]).expanduser().resolve()
        resolved_path = path.expanduser().resolve()
        relative_path = resolved_path.relative_to(active_root).as_posix()
    except Exception:
        return None
    return active_root, relative_path, SimilarityRepository(root_database_path(active_root))


def _serialize_descriptors(descriptors: Any) -> bytes:
    try:
        import numpy
    except ImportError:
        return b""

    buffer = io.BytesIO()
    numpy.save(buffer, descriptors, allow_pickle=False)
    return buffer.getvalue()


def _deserialize_descriptors(payload: bytes | None) -> Any | None:
    if not payload:
        return None
    try:
        import numpy

        buffer = io.BytesIO(payload)
        return numpy.load(buffer, allow_pickle=False)
    except Exception:
        return None


def _cache_feature_descriptors(
    path: Path,
    stat,
    result: tuple[str, int, Any],
    cache_context: tuple[Path, str, SimilarityRepository] | None,
) -> None:
    if cache_context is None:
        return

    _active_root, relative_path, repository = cache_context
    detector, keypoint_count, descriptors = result
    payload = _serialize_descriptors(descriptors)
    if not payload:
        return
    try:
        file_record = repository.upsert_file(
            relative_path=relative_path,
            absolute_path=path,
            file_name=path.name,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )
        shape = getattr(descriptors, "shape", ())
        dimension = int(shape[1]) if len(shape) > 1 else 0
        repository.upsert_feature(
            file_id=file_record.id,
            method="feature",
            model=FEATURE_CACHE_MODEL,
            version=FEATURE_CACHE_VERSION,
            value_blob=payload,
            dimension=dimension,
            keypoint_count=keypoint_count,
            detector=detector,
        )
    except Exception:
        return


def _load_cached_feature_descriptors(
    stat,
    cache_context: tuple[Path, str, SimilarityRepository] | None,
) -> tuple[str, int, Any] | None:
    if cache_context is None:
        return None
    _active_root, relative_path, repository = cache_context
    try:
        record = repository.get_feature(
            relative_path,
            method="feature",
            model=FEATURE_CACHE_MODEL,
            version=FEATURE_CACHE_VERSION,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )
    except Exception:
        return None
    if record is None:
        return None
    descriptors = _deserialize_descriptors(record.value_blob)
    if descriptors is None:
        return None
    return record.detector or "feature", record.keypoint_count, descriptors


def _feature_descriptors(path: Path) -> tuple[str, int, Any] | None:
    import cv2

    try:
        stat = path.stat()
    except OSError:
        return None

    cache_key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    cached = FEATURE_DESCRIPTOR_CACHE.get(cache_key)
    if cached is not None:
        return cached

    cache_context = _active_similarity_cache_context(path)
    persistent = _load_cached_feature_descriptors(stat, cache_context)
    if persistent is not None:
        FEATURE_DESCRIPTOR_CACHE[cache_key] = persistent
        return persistent

    image = _load_feature_image(path)
    if image is None:
        return None

    orb = cv2.ORB_create(nfeatures=1200, fastThreshold=7)
    keypoints, descriptors = orb.detectAndCompute(image, None)
    if descriptors is not None and len(keypoints) >= 12:
        result = ("orb", len(keypoints), descriptors)
        FEATURE_DESCRIPTOR_CACHE[cache_key] = result
        _cache_feature_descriptors(path, stat, result, cache_context)
        return result

    akaze = cv2.AKAZE_create()
    keypoints, descriptors = akaze.detectAndCompute(image, None)
    if descriptors is not None and len(keypoints) >= 8:
        result = ("akaze", len(keypoints), descriptors)
        FEATURE_DESCRIPTOR_CACHE[cache_key] = result
        _cache_feature_descriptors(path, stat, result, cache_context)
        return result
    return None


def _document_hash(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return ""

    cache_context = _active_similarity_cache_context(path)
    if cache_context is not None:
        _active_root, relative_path, repository = cache_context
        try:
            cached = repository.get_feature(
                relative_path,
                method="document",
                version=DOCUMENT_CACHE_VERSION,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        except Exception:
            cached = None
        if cached is not None and cached.value_text:
            return cached.value_text

    value = compute_document_hash(str(path)) or ""
    if not value or cache_context is None:
        return value

    _active_root, relative_path, repository = cache_context
    try:
        file_record = repository.upsert_file(
            relative_path=relative_path,
            absolute_path=path,
            file_name=path.name,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )
        repository.upsert_feature(
            file_id=file_record.id,
            method="document",
            version=DOCUMENT_CACHE_VERSION,
            value_text=value,
        )
    except Exception:
        pass
    return value


def _serialize_float_vector(vector: list[float]) -> bytes:
    try:
        import numpy
    except ImportError:
        return b""
    array = numpy.asarray(vector, dtype=numpy.float32)
    buffer = io.BytesIO()
    numpy.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def _deserialize_float_vector(payload: bytes | None) -> list[float] | None:
    if not payload:
        return None
    try:
        import numpy

        buffer = io.BytesIO(payload)
        array = numpy.load(buffer, allow_pickle=False)
        return [float(value) for value in array.astype(numpy.float32).ravel()]
    except Exception:
        return None


def _compute_lite_embedding(path: Path) -> list[float]:
    try:
        import numpy
    except ImportError:
        return []
    if Image is None or ImageOps is None:
        return []

    try:
        with Image.open(path) as img:
            rgb = ImageOps.exif_transpose(img).convert("RGB").resize((32, 32))
            gray = rgb.convert("L").resize((16, 16))
    except Exception:
        return []

    rgb_array = numpy.asarray(rgb, dtype=numpy.float32) / 255.0
    gray_array = numpy.asarray(gray, dtype=numpy.float32) / 255.0
    low_freq = gray_array.reshape(8, 2, 8, 2).mean(axis=(1, 3)).ravel()
    channel_mean = rgb_array.mean(axis=(0, 1))
    channel_std = rgb_array.std(axis=(0, 1))
    grad_x = numpy.abs(numpy.diff(gray_array, axis=1)).mean(axis=1)
    grad_y = numpy.abs(numpy.diff(gray_array, axis=0)).mean(axis=0)
    vector = numpy.concatenate([low_freq, channel_mean, channel_std, grad_x, grad_y])
    norm = float(numpy.linalg.norm(vector))
    if norm <= 0:
        return []
    return [float(value) for value in (vector / norm)]


def _embedding_vector(path: Path) -> list[float]:
    try:
        stat = path.stat()
    except OSError:
        return []

    cache_context = _active_similarity_cache_context(path)
    if cache_context is not None:
        _active_root, relative_path, repository = cache_context
        try:
            cached = repository.get_feature(
                relative_path,
                method="embedding",
                model=EMBEDDING_CACHE_MODEL,
                version=EMBEDDING_CACHE_VERSION,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        except Exception:
            cached = None
        if cached is not None:
            vector = _deserialize_float_vector(cached.value_blob)
            if vector:
                return vector

    vector = _compute_lite_embedding(path)
    if not vector or cache_context is None:
        return vector

    payload = _serialize_float_vector(vector)
    if not payload:
        return vector
    _active_root, relative_path, repository = cache_context
    try:
        file_record = repository.upsert_file(
            relative_path=relative_path,
            absolute_path=path,
            file_name=path.name,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )
        repository.upsert_feature(
            file_id=file_record.id,
            method="embedding",
            model=EMBEDDING_CACHE_MODEL,
            version=EMBEDDING_CACHE_VERSION,
            value_blob=payload,
            dimension=len(vector),
        )
    except Exception:
        pass
    return vector


def _embedding_distance(left: list[float], right: list[float]) -> tuple[int, float] | None:
    if not left or not right or len(left) != len(right):
        return None
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return None
    score = max(0.0, min(1.0, dot / (left_norm * right_norm)))
    return round(EMBEDDING_DISTANCE_MAX * (1 - score)), round(score, 4)


def _has_current_similarity_cache(path: Path, methods: set[str]) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    cache_context = _active_similarity_cache_context(path)
    if cache_context is None:
        return False

    _active_root, relative_path, repository = cache_context
    for method in methods:
        model = ""
        version = DOCUMENT_CACHE_VERSION
        if method == "feature":
            model = FEATURE_CACHE_MODEL
            version = FEATURE_CACHE_VERSION
        elif method == "embedding":
            model = EMBEDDING_CACHE_MODEL
            version = EMBEDDING_CACHE_VERSION
        try:
            cached = repository.get_feature(
                relative_path,
                method=method,
                model=model,
                version=version,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        except Exception:
            return False
        if cached is None:
            return False
        if method == "document" and not cached.value_text:
            return False
        if method in {"feature", "embedding"} and not cached.value_blob:
            return False
    return True


def _feature_similarity_distance(
    left_path: Path,
    right_path: Path,
    left: tuple[str, int, Any] | None = None,
) -> tuple[int, float, str] | None:
    try:
        import cv2
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="OpenCV is required for feature similarity. Install opencv-python-headless.",
        ) from exc

    left = left or _feature_descriptors(left_path)
    right = _feature_descriptors(right_path)
    if left is None or right is None:
        return None

    left_method, left_count, left_descriptors = left
    right_method, right_count, right_descriptors = right
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(left_descriptors, right_descriptors)
    if not matches:
        return None

    matches = sorted(matches, key=lambda match: match.distance)
    good_distance = 64 if left_method == "orb" and right_method == "orb" else 80
    good_matches = [match for match in matches if match.distance <= good_distance]
    comparable_count = max(1, min(left_count, right_count))
    match_ratio = min(1.0, len(good_matches) / comparable_count)
    if not good_matches:
        average_quality = 0.0
    else:
        average_distance = sum(match.distance for match in good_matches[:50]) / min(len(good_matches), 50)
        average_quality = max(0.0, 1.0 - (average_distance / 100.0))
    score = round((match_ratio * 0.7) + (average_quality * 0.3), 4)
    distance = round(FEATURE_DISTANCE_MAX * (1 - score))
    detector = left_method if left_method == right_method else f"{left_method}+{right_method}"
    return distance, score, detector


def _mobile_record_target(record: dict[str, Any]) -> str:
    album = str(record.get("album", "") or "").strip().strip("/")
    filename = str(record.get("filename", "") or "").strip()
    return f"{album}/{filename}" if album else filename


def _mobile_record_local_path(active_root: Path, record: dict[str, Any]) -> tuple[Path, str] | None:
    for key in ("local_path", "existing_local_path"):
        raw_path = str(record.get(key, "") or "").strip()
        if not raw_path:
            continue
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            continue
        try:
            relative_path = path.relative_to(active_root).as_posix()
        except ValueError:
            continue
        return path, relative_path
    return None


def _collect_local_mobile_records(active_root: Path, device_type: str) -> list[dict[str, Any]]:
    database_path = root_database_path(active_root)
    records = MobileRepository(database_path).list_import_records(device_type)
    local_records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for record in records:
        local_path = _mobile_record_local_path(active_root, record)
        if local_path is None:
            continue
        path, relative_path = local_path
        phash = str(record.get("phash", "") or "").strip()
        if not phash:
            phash = compute_phash(str(path)) or ""
        if not phash:
            continue
        if relative_path in seen_paths:
            continue
        seen_paths.add(relative_path)
        local_records.append(
            {
                **record,
                "target": _mobile_record_target(record),
                "local_file_path": path,
                "relative_path": relative_path,
                "phash": phash,
            }
        )
    return local_records


def _find_mobile_query_record(
    records: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    normalized_query = str(query or "").strip().strip('"').replace("\\", "/").strip("/")
    if not normalized_query:
        raise HTTPException(status_code=400, detail="Image path is required")

    target_matches = [
        record
        for record in records
        if str(record.get("target", "")).replace("\\", "/").strip("/") == normalized_query
    ]
    if len(target_matches) == 1:
        return target_matches[0]
    if len(target_matches) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Multiple indexed iPhone photos matched. Use album/filename: {normalized_query}",
        )

    filename_matches = [
        record
        for record in records
        if str(record.get("filename", "") or "").strip() == normalized_query
        or str(record.get("relative_path", "") or "").replace("\\", "/").strip("/") == normalized_query
    ]
    if len(filename_matches) == 1:
        return filename_matches[0]
    if len(filename_matches) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Multiple indexed iPhone photos matched filename. Use album/filename: {normalized_query}",
        )

    raise HTTPException(status_code=404, detail=f"Indexed iPhone photo not found in local root: {normalized_query}")


def search_similar_mobile_images(
    relative_path: str,
    device_type: str = "iphone",
    method: str = "phash",
    threshold: int = 8,
    limit: int = 50,
) -> dict[str, Any]:
    method = str(method or "phash").strip().lower()
    if method != "phash":
        raise HTTPException(status_code=400, detail="Unsupported similarity method")

    normalized_device_type = str(device_type or "iphone").strip().lower()
    if normalized_device_type != "iphone":
        raise HTTPException(status_code=400, detail=f"Unsupported similarity source: {normalized_device_type}")

    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    records = _collect_local_mobile_records(active_root, normalized_device_type)
    query_record = _find_mobile_query_record(records, relative_path)
    query_hash = str(query_record.get("phash", "") or "").strip()

    items: list[dict[str, Any]] = []
    query_relative_path = str(query_record.get("relative_path", ""))
    query_target = str(query_record.get("target", ""))
    for record in records:
        candidate_relative = str(record.get("relative_path", ""))
        candidate_target = str(record.get("target", ""))
        if candidate_relative == query_relative_path and candidate_target == query_target:
            continue
        try:
            distance = phash_distance(query_hash, str(record.get("phash", "")))
        except ValueError:
            continue
        if distance > threshold:
            continue
        items.append(
            {
                "relative_path": candidate_relative,
                "hash": str(record.get("phash", "")),
                "distance": distance,
                "score": round(1 - (distance / 64), 4),
                "reason": method,
                "source": normalized_device_type,
                "device_type": normalized_device_type,
                "device_id": str(record.get("device_id", "")),
                "device_name": str(record.get("device_name", "")),
                "album": str(record.get("album", "")),
                "filename": str(record.get("filename", "")),
                "mobile_target": candidate_target,
                "import_status": str(record.get("import_status", "")),
                "save_state": str(record.get("save_state", "")),
            }
        )

    items.sort(key=lambda item: (item["distance"], item["relative_path"].lower(), item["mobile_target"].lower()))
    items = items[:limit]
    return {
        "query": query_target or query_relative_path,
        "query_relative_path": query_relative_path,
        "source": normalized_device_type,
        "method": method,
        "query_hash": query_hash,
        "threshold": threshold,
        "items": items,
        "count": len(items),
    }


def search_similar_images(
    relative_path: str,
    source: str = "local",
    method: str = "phash",
    threshold: int = 8,
    limit: int = 50,
) -> dict[str, Any]:
    source = str(source or "local").strip().lower()
    if source == "iphone":
        return search_similar_mobile_images(relative_path, "iphone", method, threshold, limit)
    if source != "local":
        raise HTTPException(status_code=400, detail=f"Unsupported similarity source: {source}")

    method = str(method or "phash").strip().lower()
    if method not in {"phash", "document", "feature", "embedding"}:
        raise HTTPException(status_code=400, detail="Unsupported similarity method")

    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    query_path, normalized_relative_path = _resolve_similarity_query_path(active_root, relative_path)
    if not query_path.exists() or not query_path.is_file():
        raise HTTPException(status_code=404, detail=f"Image not found in current root: {normalized_relative_path}")

    query_hash = ""
    if method == "document":
        query_hash = _document_hash(query_path)
    elif method == "phash":
        query_hash = compute_phash(str(query_path)) or ""
    query_features = _feature_descriptors(query_path) if method == "feature" else None
    query_embedding = _embedding_vector(query_path) if method == "embedding" else []
    if method == "feature" and query_features is None:
        return {
            "query": normalized_relative_path,
            "source": "local",
            "method": method,
            "query_hash": "",
            "threshold": threshold,
            "items": [],
            "count": 0,
        }
    if method == "embedding" and not query_embedding:
        return {
            "query": normalized_relative_path,
            "source": "local",
            "method": method,
            "query_hash": "",
            "threshold": threshold,
            "items": [],
            "count": 0,
        }
    if not query_hash:
        if method == "feature":
            query_hash = "feature"
        elif method == "embedding":
            query_hash = EMBEDDING_CACHE_MODEL
        else:
            return {
                "query": normalized_relative_path,
                "method": method,
                "query_hash": "",
                "items": [],
                "count": 0,
            }

    if method != "feature" and not query_hash:
        return {
            "query": normalized_relative_path,
            "method": method,
            "query_hash": "",
            "items": [],
            "count": 0,
        }

    database_path = root_database_path(active_root)
    hash_db = HashDbRepository(database_path).load_hash_db()
    items_by_path = _collect_duplicate_group_matches(active_root, normalized_relative_path)

    if method == "phash":
        records = _collect_similarity_candidates(active_root, query_path, hash_db)
        for candidate_hash, paths in records.items():
            try:
                distance = phash_distance(query_hash, str(candidate_hash))
            except ValueError:
                continue
            if distance > threshold:
                continue

            for candidate_path in paths:
                try:
                    candidate_relative = candidate_path.relative_to(active_root).as_posix()
                except ValueError:
                    continue
                current = items_by_path.get(candidate_relative)
                item = {
                    "relative_path": candidate_relative,
                    "hash": str(candidate_hash),
                    "distance": distance,
                    "score": round(1 - (distance / 64), 4),
                    "reason": method,
                    "source": "phash",
                }
                if current is None or item["distance"] < current["distance"]:
                    items_by_path[candidate_relative] = item
                if len(items_by_path) >= limit:
                    break
            if len(items_by_path) >= limit:
                break
    elif method == "document":
        for candidate_path in _collect_similarity_candidate_paths(active_root, query_path, hash_db):
            if len(items_by_path) >= limit:
                break
            candidate_hash = _document_hash(candidate_path)
            if not candidate_hash:
                continue
            try:
                distance = document_hash_distance(query_hash, candidate_hash)
            except ValueError:
                continue
            if distance > threshold:
                continue
            candidate_relative = candidate_path.relative_to(active_root).as_posix()
            current = items_by_path.get(candidate_relative)
            item = {
                "relative_path": candidate_relative,
                "hash": str(candidate_hash),
                "distance": distance,
                "score": round(1 - (distance / 256), 4),
                "reason": method,
                "source": "document",
            }
            if current is None or item["distance"] < current["distance"]:
                items_by_path[candidate_relative] = item
    elif method == "feature":
        for candidate_path in _collect_similarity_candidate_paths(active_root, query_path, hash_db):
            if len(items_by_path) >= limit:
                break
            result = _feature_similarity_distance(query_path, candidate_path, query_features)
            if result is None:
                continue
            distance, score, detector = result
            if distance > threshold:
                continue
            candidate_relative = candidate_path.relative_to(active_root).as_posix()
            current = items_by_path.get(candidate_relative)
            item = {
                "relative_path": candidate_relative,
                "hash": detector,
                "distance": distance,
                "score": score,
                "reason": method,
                "source": "feature",
            }
            if current is None or item["distance"] < current["distance"]:
                items_by_path[candidate_relative] = item
    else:
        for candidate_path in _collect_similarity_candidate_paths(active_root, query_path, hash_db):
            if len(items_by_path) >= limit:
                break
            candidate_embedding = _embedding_vector(candidate_path)
            result = _embedding_distance(query_embedding, candidate_embedding)
            if result is None:
                continue
            distance, score = result
            if distance > threshold:
                continue
            candidate_relative = candidate_path.relative_to(active_root).as_posix()
            current = items_by_path.get(candidate_relative)
            item = {
                "relative_path": candidate_relative,
                "hash": EMBEDDING_CACHE_MODEL,
                "distance": distance,
                "score": score,
                "reason": method,
                "source": "embedding",
            }
            if current is None or item["distance"] < current["distance"]:
                items_by_path[candidate_relative] = item

    items = list(items_by_path.values())
    items.sort(key=lambda item: (item["distance"], item["relative_path"].lower()))
    items = items[:limit]
    return {
        "query": normalized_relative_path,
        "source": "local",
        "method": method,
        "query_hash": query_hash,
        "threshold": threshold,
        "items": items,
        "count": len(items),
    }


def build_similarity_cache(
    source: str = "local",
    methods: list[str] | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    normalized_source = str(source or "local").strip().lower()
    if normalized_source != "local":
        raise HTTPException(status_code=400, detail="Similarity cache build supports local source only")

    requested_methods = {
        str(method or "").strip().lower()
        for method in (methods or ["document", "feature", "embedding"])
        if str(method or "").strip()
    }
    if not requested_methods:
        requested_methods = {"document", "feature", "embedding"}
    supported_methods = {"document", "feature", "embedding"}
    unknown_methods = sorted(requested_methods - supported_methods)
    if unknown_methods:
        raise HTTPException(status_code=400, detail=f"Unsupported cache methods: {', '.join(unknown_methods)}")

    settings = load_settings()
    active_root = Path(settings["active_root"]).expanduser().resolve()
    processed = 0
    skipped_cached = 0
    scanned = 0
    failed = 0
    method_counts = {method: 0 for method in sorted(requested_methods)}

    for path in iter_image_files(active_root):
        if processed >= limit:
            break
        scanned += 1
        if _has_current_similarity_cache(path, requested_methods):
            skipped_cached += 1
            continue
        processed += 1
        for method in sorted(requested_methods):
            try:
                if method == "document":
                    if _document_hash(path):
                        method_counts[method] += 1
                elif method == "feature":
                    if _feature_descriptors(path) is not None:
                        method_counts[method] += 1
                elif method == "embedding":
                    if _embedding_vector(path):
                        method_counts[method] += 1
            except Exception:
                failed += 1

    return {
        "source": normalized_source,
        "methods": sorted(requested_methods),
        "processed": processed,
        "limit": limit,
        "scanned": scanned,
        "skipped_cached": skipped_cached,
        "failed": failed,
        "method_counts": method_counts,
    }
