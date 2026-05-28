from .base import *
from .root_workspace import ensure_root_workspace, root_image_index_dir, image_index_dir_for_read, root_thumbnail_dir
import exifread
from media_engine.core.date_classifier import get_target_date


def resolve_under_root(root: Path, candidate: str) -> Path:
    return resolve_under_root_service(root, candidate)


def list_images(root: Path) -> list[dict[str, Any]]:
    return list_images_service(root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)


def list_images_page(root: Path, offset: int = 0, limit: int | None = None, include_exif: bool = True) -> dict[str, Any]:
    return list_images_page_service(root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES, offset, limit, include_exif)


def list_images_cached_page(root: Path, offset: int = 0, limit: int = 48, refresh: bool = True, include_total: bool = False) -> dict[str, Any]:
    ensure_root_workspace(root)
    index_dir = root_image_index_dir(root) if refresh else image_index_dir_for_read(root)
    return list_images_cached_page_service(index_dir, root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES, offset, limit, refresh, include_total)


def get_timeline_index(root: Path) -> dict[str, Any]:
    ensure_root_workspace(root)
    return get_timeline_index_service(image_index_dir_for_read(root), root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)


def get_images_for_timeline_group(root: Path, group_key: str) -> dict[str, Any]:
    ensure_root_workspace(root)
    return get_images_for_timeline_group_service(
        image_index_dir_for_read(root),
        root,
        SUPPORTED_EXTENSIONS,
        SKIP_SCAN_DIR_NAMES,
        group_key,
    )


def clear_image_list_cache(root: Path | None = None) -> None:
    clear_image_list_cache_service(root)


def copy_file_preserve_times(src: Path, dst: Path) -> None:
    copy_file_preserve_times_service(src, dst)


def move_file_preserve_times(src: Path, dst: Path) -> None:
    move_file_preserve_times_service(src, dst)


def iter_image_files(root: Path) -> Iterable[Path]:
    return iter_image_files_service(root, SUPPORTED_EXTENSIONS, SKIP_SCAN_DIR_NAMES)


def thumbnail_path_for(root: Path, relative_path: str) -> Path:
    ensure_root_workspace(root)
    return thumbnail_path_for_service(root_thumbnail_dir(root), root, relative_path)


def format_exif_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip("\x00 ") or "-"
    if isinstance(value, tuple) and len(value) == 2 and all(isinstance(item, int) for item in value) and value[1] != 0:
        return f"{value[0]}/{value[1]}"
    if isinstance(value, tuple):
        return ", ".join(format_exif_value(item) for item in value)
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        denominator = getattr(value, "denominator", 1) or 1
        numerator = getattr(value, "numerator", value)
        if denominator == 1:
            return str(numerator)
        return f"{numerator}/{denominator}"
    return str(value)


def rational_to_float(value: Any) -> float | None:
    if value is None:
        return None
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        d = value.denominator or 1
        return float(value.numerator) / float(d)
    if isinstance(value, tuple) and len(value) == 2 and value[1]:
        return float(value[0]) / float(value[1])
    try:
        return float(value)
    except Exception:
        return None


def gps_dms_to_decimal(value: Any, ref: Any) -> float | None:
    if not value or len(value) < 3:
        return None

    degrees = rational_to_float(value[0])
    minutes = rational_to_float(value[1])
    seconds = rational_to_float(value[2])
    if degrees is None or minutes is None or seconds is None:
        return None

    decimal = degrees + minutes / 60 + seconds / 3600
    if str(ref).upper() in {"S", "W"}:
        decimal *= -1
    return decimal


def read_gps_summary(tags):
    gps_lat = tags.get("GPS GPSLatitude")
    gps_lat_ref = tags.get("GPS GPSLatitudeRef")
    gps_lon = tags.get("GPS GPSLongitude")
    gps_lon_ref = tags.get("GPS GPSLongitudeRef")
    gps_alt = tags.get("GPS GPSAltitude")
    gps_alt_ref = tags.get("GPS GPSAltitudeRef")

    result = {}

    lat = gps_dms_to_decimal(gps_lat.values if hasattr(gps_lat, "values") else None,
                             gps_lat_ref.values[0] if hasattr(gps_lat_ref, "values") else None)
    lon = gps_dms_to_decimal(gps_lon.values if hasattr(gps_lon, "values") else None,
                             gps_lon_ref.values[0] if hasattr(gps_lon_ref, "values") else None)

    if lat is not None and lon is not None:
        result["gps_coordinates"] = f"{lat:.6f}, {lon:.6f}"

    if gps_alt:
        alt = rational_to_float(gps_alt.values[0])
        if alt is not None:
            ref = rational_to_float(gps_alt_ref.values[0]) if gps_alt_ref else 0
            if ref == 1:
                alt *= -1
            result["gps_altitude"] = f"{alt:.1f} m"

    return result


def read_exif_tags(path: Path):
    with open(path, "rb") as f:
        return exifread.process_file(f, details=True, strict=False)


def read_exif_summary(image_path: Path) -> dict[str, str]:
    from PIL import Image
    with Image.open(image_path) as img:
        width, height = img.size

    tags = read_exif_tags(image_path)
    gps_summary = read_gps_summary(tags)
    captured_at = get_target_date(image_path)

    summary = {
        "width": str(width),
        "height": str(height),
        "datetime": captured_at.isoformat(sep=" ") if captured_at else "-",
        "camera": format_exif_value(
            f"{tags.get('Image Make', '')} {tags.get('Image Model', '')}".strip()
        ) or "-",
        "lens": format_exif_value(tags.get("EXIF LensModel") or "-"),
        "focal_length": format_exif_value(tags.get("EXIF FocalLength") or "-"),
        "aperture": format_exif_value(tags.get("EXIF FNumber") or "-"),
        "shutter": format_exif_value(tags.get("EXIF ExposureTime") or "-"),
        "iso": format_exif_value(
            tags.get("EXIF ISOSpeedRatings")
            or tags.get("EXIF PhotographicSensitivity")
            or "-"
        ),
    }

    summary.update(gps_summary)
    return summary
