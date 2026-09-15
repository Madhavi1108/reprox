import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models.enums import ArtifactType, DeterminismClassification, DeterminismIntent


class CodeSnapshot(Base):
    __tablename__ = "code_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE"), unique=True
    )
    vcs_present: Mapped[bool] = mapped_column(Boolean, default=False)
    git_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    git_branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_dirty: Mapped[bool] = mapped_column(Boolean, default=False)
    is_detached_head: Mapped[bool] = mapped_column(Boolean, default=False)
    is_shallow_clone: Mapped[bool] = mapped_column(Boolean, default=False)
    tree_fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint_algorithm_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())

    files: Mapped[list["CodeFile"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class CodeFile(Base):
    __tablename__ = "code_files"
    __table_args__ = (UniqueConstraint("code_snapshot_id", "relative_path", name="uq_codefile_snapshot_path"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("code_snapshots.id", ondelete="CASCADE")
    )
    relative_path: Mapped[str] = mapped_column(String(1000))
    size_bytes: Mapped[int] = mapped_column(Integer)
    file_hash: Mapped[str] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)

    snapshot: Mapped["CodeSnapshot"] = relationship(back_populates="files")


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_dataset_project_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    versions: Mapped[list["DatasetVersion"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "content_hash", name="uq_datasetversion_dataset_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"))
    content_hash: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    schema_json: Mapped[dict] = mapped_column(JSONB)
    stats_json: Mapped[dict] = mapped_column(JSONB)
    duplicate_row_count: Mapped[int] = mapped_column(Integer, default=0)
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    source_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())

    dataset: Mapped["Dataset"] = relationship(back_populates="versions")


class RunDatasetLink(Base):
    __tablename__ = "run_dataset_links"
    __table_args__ = (
        UniqueConstraint("run_id", "dataset_version_id", "role", name="uq_rundatasetlink_run_version_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE")
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="RESTRICT")
    )
    role: Mapped[str] = mapped_column(String(50), default="primary")


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE"), unique=True
    )
    os_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    architecture: Mapped[str | None] = mapped_column(String(50), nullable=True)
    python_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cpu_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cpu_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ram_total_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gpu_present: Mapped[bool] = mapped_column(Boolean, default=False)
    gpu_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cuda_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    environment_fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())

    dependencies: Mapped[list["Dependency"]] = relationship(back_populates="environment", cascade="all, delete-orphan")


class Dependency(Base):
    __tablename__ = "dependencies"
    __table_args__ = (UniqueConstraint("environment_id", "package_name", name="uq_dependency_env_package"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("environments.id", ondelete="CASCADE")
    )
    package_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(100))

    environment: Mapped["Environment"] = relationship(back_populates="dependencies")


class Configuration(Base):
    __tablename__ = "configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE"), unique=True
    )
    raw_json: Mapped[dict] = mapped_column(JSONB)
    canonical_json: Mapped[str] = mapped_column(Text)
    configuration_fingerprint_hash: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RandomnessProfile(Base):
    __tablename__ = "randomness_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE"), unique=True
    )
    python_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    numpy_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    other_seeds_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    determinism_intent: Mapped[DeterminismIntent] = mapped_column(default=DeterminismIntent.NOT_REQUESTED)
    determinism_classification: Mapped[DeterminismClassification] = mapped_column(
        default=DeterminismClassification.UNKNOWN
    )
    randomness_fingerprint_hash: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE")
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(default=ArtifactType.OTHER)
    file_path: Mapped[str] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (UniqueConstraint("run_id", "name", name="uq_metric_run_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    value: Mapped[float] = mapped_column(Numeric)
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Fingerprint(Base):
    __tablename__ = "fingerprints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE"), unique=True
    )
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dataset_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    environment_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    configuration_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    randomness_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    composite_hash: Mapped[str] = mapped_column(String(64))
    fingerprint_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    missing_components_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    computed_at: Mapped[datetime] = mapped_column(server_default=func.now())
