import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models.enums import (
    Confidence,
    ComparisonStatus,
    DifferenceCategory,
    DifferenceType,
    ReproducibilityClassification,
    Severity,
)


class ExperimentComparison(Base):
    __tablename__ = "experiment_comparisons"
    __table_args__ = (
        UniqueConstraint("base_run_id", "compare_run_id", name="uq_comparison_base_compare"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE"), index=True
    )
    compare_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE"), index=True
    )
    code_status: Mapped[ComparisonStatus] = mapped_column(default=ComparisonStatus.UNKNOWN)
    dataset_status: Mapped[ComparisonStatus] = mapped_column(default=ComparisonStatus.UNKNOWN)
    environment_status: Mapped[ComparisonStatus] = mapped_column(default=ComparisonStatus.UNKNOWN)
    configuration_status: Mapped[ComparisonStatus] = mapped_column(default=ComparisonStatus.UNKNOWN)
    randomness_status: Mapped[ComparisonStatus] = mapped_column(default=ComparisonStatus.UNKNOWN)
    metrics_status: Mapped[ComparisonStatus] = mapped_column(default=ComparisonStatus.UNKNOWN)
    comparison_algorithm_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    differences: Mapped[list["Difference"]] = relationship(back_populates="comparison", cascade="all, delete-orphan")
    reproducibility_assessment: Mapped["ReproducibilityAssessment | None"] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", uselist=False
    )


class Difference(Base):
    __tablename__ = "differences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_comparisons.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[DifferenceCategory] = mapped_column()
    field: Mapped[str] = mapped_column(String(300))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    difference_type: Mapped[DifferenceType] = mapped_column()
    evidence_source: Mapped[str] = mapped_column(String(200))
    severity: Mapped[Severity] = mapped_column(default=Severity.LOW)
    confidence: Mapped[Confidence] = mapped_column(default=Confidence.MEDIUM)
    is_potential_contributor: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    comparison: Mapped["ExperimentComparison"] = relationship(back_populates="differences")


class ReproducibilityAssessment(Base):
    __tablename__ = "reproducibility_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiment_comparisons.id", ondelete="CASCADE"), unique=True
    )
    classification: Mapped[ReproducibilityClassification] = mapped_column()
    rationale_json: Mapped[dict] = mapped_column(JSONB)
    algorithm_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    comparison: Mapped["ExperimentComparison"] = relationship(back_populates="reproducibility_assessment")
