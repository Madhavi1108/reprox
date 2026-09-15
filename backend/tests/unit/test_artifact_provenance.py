from pathlib import Path

import pytest

from app.db.models.enums import ArtifactType
from app.provenance.artifact import (
    ArtifactDirectoryNotFoundError,
    ArtifactFileNotFoundError,
    capture_artifact_provenance,
    capture_artifacts_from_directory,
    classify_artifact_type,
)


def test_classify_known_sandbox_filenames():
    assert classify_artifact_type("model.joblib") == ArtifactType.MODEL
    assert classify_artifact_type("metrics.json") == ArtifactType.METRIC_DUMP
    assert classify_artifact_type("stdout.log") == ArtifactType.STDOUT
    assert classify_artifact_type("stderr.log") == ArtifactType.STDERR


def test_classify_unrecognized_filename_falls_back_to_extension_or_other():
    assert classify_artifact_type("training.log") == ArtifactType.LOG
    assert classify_artifact_type("weights.pkl") == ArtifactType.MODEL
    assert classify_artifact_type("readme.txt") == ArtifactType.OTHER


def test_capture_single_artifact(tmp_path: Path):
    f = tmp_path / "metrics.json"
    f.write_text('{"accuracy": 0.94}')
    prov = capture_artifact_provenance(f)
    assert prov.artifact_type == ArtifactType.METRIC_DUMP
    assert prov.relative_path == "metrics.json"
    assert prov.size_bytes == len('{"accuracy": 0.94}')
    assert len(prov.content_hash) == 64


def test_explicit_artifact_type_overrides_inference(tmp_path: Path):
    f = tmp_path / "output.bin"
    f.write_bytes(b"\x00\x01\x02")
    prov = capture_artifact_provenance(f, artifact_type=ArtifactType.MODEL)
    assert prov.artifact_type == ArtifactType.MODEL


def test_missing_artifact_file_raises_not_fabricates(tmp_path: Path):
    with pytest.raises(ArtifactFileNotFoundError):
        capture_artifact_provenance(tmp_path / "does_not_exist.json")


def test_deterministic_hash_for_identical_content(tmp_path: Path):
    f = tmp_path / "model.joblib"
    f.write_bytes(b"fake model bytes")
    a = capture_artifact_provenance(f)
    b = capture_artifact_provenance(f)
    assert a.content_hash == b.content_hash


def test_content_change_alters_hash(tmp_path: Path):
    f = tmp_path / "model.joblib"
    f.write_bytes(b"version one")
    a = capture_artifact_provenance(f)
    f.write_bytes(b"version two")
    b = capture_artifact_provenance(f)
    assert a.content_hash != b.content_hash


def test_capture_artifacts_from_directory_classifies_each_file(tmp_path: Path):
    (tmp_path / "model.joblib").write_bytes(b"model")
    (tmp_path / "metrics.json").write_text("{}")
    (tmp_path / "stdout.log").write_text("training...")
    (tmp_path / "stderr.log").write_text("")

    artifacts = capture_artifacts_from_directory(tmp_path)
    by_type = {a.artifact_type: a for a in artifacts}

    assert len(artifacts) == 4
    assert by_type[ArtifactType.MODEL].relative_path == "model.joblib"
    assert by_type[ArtifactType.METRIC_DUMP].relative_path == "metrics.json"
    assert by_type[ArtifactType.STDOUT].relative_path == "stdout.log"
    assert by_type[ArtifactType.STDERR].relative_path == "stderr.log"


def test_capture_artifacts_from_missing_directory_raises(tmp_path: Path):
    with pytest.raises(ArtifactDirectoryNotFoundError):
        capture_artifacts_from_directory(tmp_path / "no_such_dir")


def test_capture_artifacts_from_empty_directory_returns_empty_list(tmp_path: Path):
    empty = tmp_path / "empty_output"
    empty.mkdir()
    assert capture_artifacts_from_directory(empty) == []


def test_directory_capture_is_not_recursive(tmp_path: Path):
    (tmp_path / "top.log").write_text("top level")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "inner.log").write_text("nested, should be ignored")

    artifacts = capture_artifacts_from_directory(tmp_path)
    assert len(artifacts) == 1
    assert artifacts[0].relative_path == "top.log"
