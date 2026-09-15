"""Artifact provenance capture (spec section 22).

Captures identity (type, content hash, size) for files produced by an
experiment run - model checkpoints, metric dumps, stdout/stderr logs,
etc. This module only computes provenance for files that already exist on
disk; the actual production of those files (Phase 17's Docker sandbox
runner writing to /output) is a separate, not-yet-built concern. Every
`ArtifactProvenance` returned here is meant to be persisted against a
specific `run_id` (see `Artifact` in app/db/models/provenance.py) so
artifacts remain traceable back to the run that produced them.

Never fabricates an artifact record for a file that does not exist.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.db.models.enums import ArtifactType

_HASH_CHUNK_SIZE = 1024 * 1024  # 1 MiB - stream, never load whole file into memory

# Recognized sandbox output filenames -> artifact type (spec section 22 /
# the execution sandbox lifecycle in Phase 17). Anything else falls back
# to extension-based classification, then OTHER.
_TYPE_BY_FILENAME: dict[str, ArtifactType] = {
    "model.joblib": ArtifactType.MODEL,
    "metrics.json": ArtifactType.METRIC_DUMP,
    "stdout.log": ArtifactType.STDOUT,
    "stderr.log": ArtifactType.STDERR,
}

_TYPE_BY_EXTENSION: dict[str, ArtifactType] = {
    ".log": ArtifactType.LOG,
    ".joblib": ArtifactType.MODEL,
    ".pkl": ArtifactType.MODEL,
}


class ArtifactCaptureError(Exception):
    """Base error for artifact provenance capture failures."""


class ArtifactFileNotFoundError(ArtifactCaptureError):
    pass


class ArtifactDirectoryNotFoundError(ArtifactCaptureError):
    pass


@dataclass(frozen=True)
class ArtifactProvenance:
    artifact_type: ArtifactType
    relative_path: str
    content_hash: str
    size_bytes: int


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def classify_artifact_type(filename: str) -> ArtifactType:
    if filename in _TYPE_BY_FILENAME:
        return _TYPE_BY_FILENAME[filename]
    suffix = Path(filename).suffix.lower()
    return _TYPE_BY_EXTENSION.get(suffix, ArtifactType.OTHER)


def capture_artifact_provenance(
    path: Path,
    *,
    artifact_type: ArtifactType | None = None,
    relative_to: Path | None = None,
) -> ArtifactProvenance:
    """Capture provenance for a single artifact file.

    `artifact_type` may be supplied explicitly (e.g. the caller already
    knows this is a MODEL artifact); otherwise it is inferred from the
    filename via `classify_artifact_type`.
    """
    path = Path(path)
    if not path.is_file():
        raise ArtifactFileNotFoundError(f"Artifact file not found: {path}")

    resolved_type = artifact_type or classify_artifact_type(path.name)
    relative_path = path.relative_to(relative_to).as_posix() if relative_to else path.name

    return ArtifactProvenance(
        artifact_type=resolved_type,
        relative_path=relative_path,
        content_hash=_stream_sha256(path),
        size_bytes=path.stat().st_size,
    )


def capture_artifacts_from_directory(directory: Path) -> list[ArtifactProvenance]:
    """Capture provenance for every top-level file in `directory` (e.g. a
    sandbox run's /output directory). Not recursive - sandbox output is a
    flat set of files in the MVP.

    Raises ArtifactDirectoryNotFoundError if the directory itself is
    missing (a real capture failure - never silently reported as "no
    artifacts"). An existing-but-empty directory legitimately returns [].
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise ArtifactDirectoryNotFoundError(f"Artifact directory not found: {directory}")

    artifacts = []
    for entry in sorted(directory.iterdir()):
        if entry.is_file():
            artifacts.append(capture_artifact_provenance(entry, relative_to=directory))
    return artifacts
