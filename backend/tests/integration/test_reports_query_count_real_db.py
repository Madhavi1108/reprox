"""Real-Postgres regression test for the N+1 bug found during a live-
infra hardening pass: `_reports_for_comparisons()` (Phase 30) issued a
fixed `db.query()` call count under the Phase 30 mock, but the mock
can't see ORM *relationship* lazy-loading (`comparison.differences`),
which was still issuing one extra real SQL statement per comparison.
See `tests/unit/test_export_query_count.py`'s docstring and
docs/PERFORMANCE_OPTIMIZATION.md/docs/BACKEND_TEST_REPORT.md.

This is the first test in this repo's history to run against a real,
reachable Postgres (previously never available in this dev environment -
docs/OUT_OF_SCOPE.md). It skips gracefully if none is reachable, so it
never breaks a future session that doesn't have live Postgres up.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db.models.comparison import Difference, ExperimentComparison
from app.db.models.core import Experiment, ExperimentRun, Project, User
from app.db.models.enums import (
    Confidence,
    ComparisonStatus,
    DifferenceCategory,
    DifferenceType,
    RunType,
    Severity,
)
from app.export.excel import _reports_for_comparisons


@pytest.fixture
def real_db_session():
    settings = get_settings()
    # A short connect_timeout matters here: without one, trying to reach
    # an unreachable/misconfigured Postgres can hang far longer than a
    # plain "connection refused" - this fixture must skip fast, not hang,
    # when no live Postgres exists (the common case for this repo).
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 3})
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("no reachable Postgres in this environment")
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db, engine
    finally:
        db.close()
        engine.dispose()


def _make_comparison(db, experiment, n_differences: int) -> ExperimentComparison:
    base_run = ExperimentRun(id=uuid.uuid4(), experiment_id=experiment.id, run_type=RunType.ORIGINAL)
    compare_run = ExperimentRun(id=uuid.uuid4(), experiment_id=experiment.id, run_type=RunType.REPRODUCTION)
    db.add_all([base_run, compare_run])
    db.flush()

    comparison = ExperimentComparison(
        id=uuid.uuid4(),
        base_run_id=base_run.id,
        compare_run_id=compare_run.id,
        code_status=ComparisonStatus.DIFFERENT,
    )
    db.add(comparison)
    db.flush()

    for i in range(n_differences):
        db.add(
            Difference(
                id=uuid.uuid4(),
                comparison_id=comparison.id,
                category=DifferenceCategory.CODE,
                field=f"field_{i}",
                old_value="a",
                new_value="b",
                difference_type=DifferenceType.VALUE_CHANGED,
                evidence_source="test",
                severity=Severity.LOW,
                confidence=Confidence.MEDIUM,
            )
        )
    return comparison


def test_reports_for_comparisons_query_count_is_fixed_against_real_postgres(real_db_session):
    db, engine = real_db_session

    user = db.query(User).first()
    if user is None:
        user = User(id=uuid.uuid4(), email=f"qc-{uuid.uuid4().hex[:8]}@test.local", display_name="QC")
        db.add(user)
        db.flush()

    project = Project(id=uuid.uuid4(), name="QC", slug=f"qc-{uuid.uuid4().hex[:8]}", owner_user_id=user.id)
    db.add(project)
    db.flush()
    experiment = Experiment(id=uuid.uuid4(), project_id=project.id, name="QC Exp", entrypoint_script="t.py")
    db.add(experiment)
    db.flush()

    try:
        # 2 comparisons, then 6 - if the query count scales with N, this
        # bug (or one like it) is back.
        for _ in range(2):
            _make_comparison(db, experiment, n_differences=1)
        db.commit()

        query_log = []

        def _log(conn, cursor, statement, parameters, context, executemany):
            query_log.append(statement)

        # _reports_for_comparisons() is DB-wide (queries every comparison
        # in the database, not just this test's), so on a shared dev DB
        # the absolute row/query counts aren't predictable - only that
        # adding more comparisons must NOT change the query count.
        event.listen(engine, "before_cursor_execute", _log)
        try:
            small_reports = _reports_for_comparisons(db)
            small_count = len(query_log)
            small_report_count = len(small_reports)

            for _ in range(4):
                _make_comparison(db, experiment, n_differences=2)
            db.commit()

            query_log.clear()
            large_reports = _reports_for_comparisons(db)
            large_count = len(query_log)
        finally:
            event.remove(engine, "before_cursor_execute", _log)

        assert len(large_reports) == small_report_count + 4
        assert small_count == large_count, (
            f"expected the same real SQL statement count before/after adding 4 more "
            f"comparisons (got {small_count} then {large_count}) - a query count that "
            f"grows with N is an N+1 regression"
        )
    finally:
        db.rollback()
        db.query(Experiment).filter(Experiment.id == experiment.id).delete()
        db.query(Project).filter(Project.id == project.id).delete()
        db.commit()
