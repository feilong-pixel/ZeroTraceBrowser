# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.storage.database import connect, init_root_database


@dataclass(frozen=True)
class SimilarityFileRecord:
    id: int
    relative_path: str
    absolute_path: str
    file_name: str
    size: int
    mtime_ns: int
    media_type: str
    updated_at: str


@dataclass(frozen=True)
class SimilarityFeatureRecord:
    id: int
    file_id: int
    relative_path: str
    absolute_path: str
    file_name: str
    size: int
    mtime_ns: int
    method: str
    model: str
    version: int
    value_text: str
    value_blob: bytes | None
    dimension: int
    keypoint_count: int
    detector: str
    created_at: str
    updated_at: str


class SimilarityRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = init_root_database(database_path)

    def upsert_file(
        self,
        *,
        relative_path: str,
        size: int,
        mtime_ns: int,
        absolute_path: str | Path = "",
        file_name: str = "",
        media_type: str = "image",
    ) -> SimilarityFileRecord:
        relative_path = str(relative_path).strip()
        if not relative_path:
            raise ValueError("relative_path is required")

        absolute_path_value = str(absolute_path)
        file_name_value = str(file_name).strip() or Path(relative_path).name
        media_type_value = str(media_type).strip() or "image"
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO similarity_files
                    (relative_path, absolute_path, file_name, size, mtime_ns, media_type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(relative_path) DO UPDATE SET
                    absolute_path = excluded.absolute_path,
                    file_name = excluded.file_name,
                    size = excluded.size,
                    mtime_ns = excluded.mtime_ns,
                    media_type = excluded.media_type,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    relative_path,
                    absolute_path_value,
                    file_name_value,
                    int(size),
                    int(mtime_ns),
                    media_type_value,
                ),
            )
            connection.commit()
        record = self.get_file(relative_path)
        if record is None:
            raise RuntimeError("failed to load similarity file record after upsert")
        return record

    def get_file(self, relative_path: str) -> SimilarityFileRecord | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, relative_path, absolute_path, file_name, size, mtime_ns, media_type, updated_at
                FROM similarity_files
                WHERE relative_path = ?
                """,
                (relative_path,),
            ).fetchone()
        return self._file_from_row(row) if row is not None else None

    def get_current_file(
        self,
        relative_path: str,
        *,
        size: int,
        mtime_ns: int,
    ) -> SimilarityFileRecord | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, relative_path, absolute_path, file_name, size, mtime_ns, media_type, updated_at
                FROM similarity_files
                WHERE relative_path = ? AND size = ? AND mtime_ns = ?
                """,
                (relative_path, int(size), int(mtime_ns)),
            ).fetchone()
        return self._file_from_row(row) if row is not None else None

    def upsert_feature(
        self,
        *,
        file_id: int,
        method: str,
        model: str = "",
        version: int = 1,
        value_text: str = "",
        value_blob: bytes | None = None,
        dimension: int = 0,
        keypoint_count: int = 0,
        detector: str = "",
    ) -> SimilarityFeatureRecord:
        method_value = str(method).strip()
        if not method_value:
            raise ValueError("method is required")

        model_value = str(model).strip()
        detector_value = str(detector).strip()
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO similarity_features
                    (
                        file_id, method, model, version, value_text, value_blob,
                        dimension, keypoint_count, detector, updated_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(file_id, method, model, version) DO UPDATE SET
                    value_text = excluded.value_text,
                    value_blob = excluded.value_blob,
                    dimension = excluded.dimension,
                    keypoint_count = excluded.keypoint_count,
                    detector = excluded.detector,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    int(file_id),
                    method_value,
                    model_value,
                    int(version),
                    str(value_text),
                    value_blob,
                    int(dimension),
                    int(keypoint_count),
                    detector_value,
                ),
            )
            row = connection.execute(
                """
                SELECT sf.id
                FROM similarity_features sf
                WHERE sf.file_id = ? AND sf.method = ? AND sf.model = ? AND sf.version = ?
                """,
                (int(file_id), method_value, model_value, int(version)),
            ).fetchone()
            connection.commit()

        if row is None:
            raise RuntimeError("failed to load similarity feature record after upsert")
        record = self.get_feature_by_id(int(row["id"]))
        if record is None:
            raise RuntimeError("failed to load similarity feature record after upsert")
        return record

    def get_feature(
        self,
        relative_path: str,
        *,
        method: str,
        model: str = "",
        version: int = 1,
        size: int | None = None,
        mtime_ns: int | None = None,
    ) -> SimilarityFeatureRecord | None:
        params: list[object] = [relative_path, method, model, int(version)]
        signature_filter = ""
        if size is not None:
            signature_filter += " AND sfiles.size = ?"
            params.append(int(size))
        if mtime_ns is not None:
            signature_filter += " AND sfiles.mtime_ns = ?"
            params.append(int(mtime_ns))

        with connect(self.database_path) as connection:
            row = connection.execute(
                f"""
                SELECT
                    sf.id, sf.file_id, sf.method, sf.model, sf.version, sf.value_text,
                    sf.value_blob, sf.dimension, sf.keypoint_count, sf.detector,
                    sf.created_at, sf.updated_at,
                    sfiles.relative_path, sfiles.absolute_path, sfiles.file_name,
                    sfiles.size, sfiles.mtime_ns
                FROM similarity_features sf
                JOIN similarity_files sfiles ON sfiles.id = sf.file_id
                WHERE sfiles.relative_path = ?
                  AND sf.method = ?
                  AND sf.model = ?
                  AND sf.version = ?
                  {signature_filter}
                """,
                tuple(params),
            ).fetchone()
        return self._feature_from_row(row) if row is not None else None

    def get_feature_by_id(self, feature_id: int) -> SimilarityFeatureRecord | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    sf.id, sf.file_id, sf.method, sf.model, sf.version, sf.value_text,
                    sf.value_blob, sf.dimension, sf.keypoint_count, sf.detector,
                    sf.created_at, sf.updated_at,
                    sfiles.relative_path, sfiles.absolute_path, sfiles.file_name,
                    sfiles.size, sfiles.mtime_ns
                FROM similarity_features sf
                JOIN similarity_files sfiles ON sfiles.id = sf.file_id
                WHERE sf.id = ?
                """,
                (int(feature_id),),
            ).fetchone()
        return self._feature_from_row(row) if row is not None else None

    def list_features(
        self,
        *,
        method: str,
        model: str = "",
        version: int = 1,
    ) -> list[SimilarityFeatureRecord]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    sf.id, sf.file_id, sf.method, sf.model, sf.version, sf.value_text,
                    sf.value_blob, sf.dimension, sf.keypoint_count, sf.detector,
                    sf.created_at, sf.updated_at,
                    sfiles.relative_path, sfiles.absolute_path, sfiles.file_name,
                    sfiles.size, sfiles.mtime_ns
                FROM similarity_features sf
                JOIN similarity_files sfiles ON sfiles.id = sf.file_id
                WHERE sf.method = ? AND sf.model = ? AND sf.version = ?
                ORDER BY sfiles.relative_path
                """,
                (method, model, int(version)),
            ).fetchall()
        return [self._feature_from_row(row) for row in rows]

    def delete_file(self, relative_path: str) -> bool:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM similarity_files WHERE relative_path = ?",
                (relative_path,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def delete_stale_files(self, signatures: dict[str, tuple[int, int]]) -> int:
        deleted = 0
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT relative_path, size, mtime_ns FROM similarity_files"
            ).fetchall()
            for row in rows:
                signature = signatures.get(row["relative_path"])
                if signature is None or signature != (int(row["size"]), int(row["mtime_ns"])):
                    cursor = connection.execute(
                        "DELETE FROM similarity_files WHERE relative_path = ?",
                        (row["relative_path"],),
                    )
                    deleted += cursor.rowcount
            connection.commit()
        return deleted

    @staticmethod
    def _file_from_row(row) -> SimilarityFileRecord:
        return SimilarityFileRecord(
            id=int(row["id"]),
            relative_path=str(row["relative_path"]),
            absolute_path=str(row["absolute_path"]),
            file_name=str(row["file_name"]),
            size=int(row["size"]),
            mtime_ns=int(row["mtime_ns"]),
            media_type=str(row["media_type"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _feature_from_row(row) -> SimilarityFeatureRecord:
        blob = row["value_blob"]
        return SimilarityFeatureRecord(
            id=int(row["id"]),
            file_id=int(row["file_id"]),
            relative_path=str(row["relative_path"]),
            absolute_path=str(row["absolute_path"]),
            file_name=str(row["file_name"]),
            size=int(row["size"]),
            mtime_ns=int(row["mtime_ns"]),
            method=str(row["method"]),
            model=str(row["model"]),
            version=int(row["version"]),
            value_text=str(row["value_text"]),
            value_blob=bytes(blob) if blob is not None else None,
            dimension=int(row["dimension"]),
            keypoint_count=int(row["keypoint_count"]),
            detector=str(row["detector"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
