"""Dataset provenance capture (spec sections 11-12).

Dataset identity must NEVER depend on filename alone, and equal row
counts must NEVER be treated as equal datasets. The ground truth fed into
the composite experiment fingerprint is `content_hash` (byte-exact,
Level 1 comparison). Schema and per-column statistics are captured
alongside it so the comparison engine can explain *why* two datasets
differ even when their row counts match (Level 2/3 comparison) - this is
what catches "same row count, different content, same schema, different
distribution" cases correctly instead of reporting a false match.

Level 4 (distribution similarity tests) and Level 5 (semantic metadata
comparison) are explicitly out of scope for this phase - see
docs/EDGE_CASES.md.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DATASET_FINGERPRINT_VERSION = "1.0.0"

_HASH_CHUNK_SIZE = 1024 * 1024  # 1 MiB - stream the hash, never load the whole file just to hash it


class DatasetCaptureError(Exception):
    """Base error for dataset provenance capture failures."""


class DatasetFileNotFoundError(DatasetCaptureError):
    pass


class DatasetParseError(DatasetCaptureError):
    """Raised when the dataset file exists but cannot be parsed - e.g. a
    corrupted or malformed CSV. Never silently treated as an empty/valid
    dataset."""


@dataclass(frozen=True)
class ColumnStats:
    name: str
    dtype: str
    missing_count: int
    distinct_count: int
    mean: float | None
    std: float | None
    min: float | None
    max: float | None


@dataclass(frozen=True)
class DatasetProvenance:
    content_hash: str
    file_size_bytes: int
    row_count: int
    column_count: int
    schema: dict[str, str]
    column_stats: list[ColumnStats] = field(default_factory=list)
    duplicate_row_count: int = 0
    fingerprint_version: str = DATASET_FINGERPRINT_VERSION


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _compute_column_stats(df: pd.DataFrame) -> list[ColumnStats]:
    stats: list[ColumnStats] = []
    for col in df.columns:
        series = df[col]
        is_numeric = pd.api.types.is_numeric_dtype(series)
        stats.append(
            ColumnStats(
                name=str(col),
                dtype=str(series.dtype),
                missing_count=int(series.isna().sum()),
                distinct_count=int(series.nunique(dropna=True)),
                mean=_safe_float(series.mean()) if is_numeric else None,
                std=_safe_float(series.std()) if is_numeric else None,
                min=_safe_float(series.min()) if is_numeric else None,
                max=_safe_float(series.max()) if is_numeric else None,
            )
        )
    return stats


def capture_dataset_provenance(path: Path) -> DatasetProvenance:
    """Capture dataset provenance for a CSV file at `path`.

    MVP scope covers CSV only (matches the scikit-learn tabular workload);
    other formats are a documented gap (docs/EDGE_CASES.md). Raises
    DatasetFileNotFoundError / DatasetParseError rather than fabricating
    values when the dataset cannot be read.
    """
    path = Path(path)
    if not path.is_file():
        raise DatasetFileNotFoundError(f"Dataset file not found: {path}")

    content_hash = _stream_sha256(path)
    file_size_bytes = path.stat().st_size

    try:
        df = pd.read_csv(path)
    except Exception as exc:  # pandas raises several distinct error types
        raise DatasetParseError(f"Failed to parse dataset at {path}: {exc}") from exc

    schema = {str(col): str(dtype) for col, dtype in df.dtypes.items()}
    column_stats = _compute_column_stats(df)
    duplicate_row_count = int(df.duplicated().sum())

    return DatasetProvenance(
        content_hash=content_hash,
        file_size_bytes=file_size_bytes,
        row_count=len(df),
        column_count=len(df.columns),
        schema=schema,
        column_stats=column_stats,
        duplicate_row_count=duplicate_row_count,
    )
