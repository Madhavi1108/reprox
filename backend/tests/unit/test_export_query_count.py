"""Phase 30 regression tests: the two N+1 query sites in
`app/export/excel.py` (`_lineage_edges_for_experiments`,
`_reports_for_comparisons`) must issue a fixed number of queries
regardless of how many experiments/comparisons exist - not one that
scales with input size. See docs/PERFORMANCE_OPTIMIZATION.md.

`_CountingSession`/`_CountingQuery` are a minimal fake (not a mock of the
real Session) that serve fixed in-memory rows and ignore filter
predicates - adequate here because the point under test is *how many
times* `db.query()` is called, not SQL correctness, and every fixture row
returned by a given model is already the row the corresponding filter
would have matched.

IMPORTANT LIMITATION, found the hard way: this fake cannot detect an
N+1 caused by lazily-loaded ORM *relationship* access (e.g.
`comparison.differences`), because `_comparison()`'s fixtures are
`MagicMock` objects - `.differences` is just an auto-created mock
attribute, never a real SQLAlchemy `InstrumentedAttribute` that would
trigger a lazy-load query on first access. `_reports_for_comparisons`
had exactly this bug (`generate_report()` reads `comparison.differences`,
lazy-loaded with no `selectinload`) even after Phase 30's fix - this test
suite stayed green throughout because `db.query()` call count (what this
fake measures) was never affected, only the real per-comparison SQL
round-trip count was. Found and fixed against a real Postgres instance in
a later hardening pass - see docs/PERFORMANCE_OPTIMIZATION.md and
docs/BACKEND_TEST_REPORT.md. This mock is kept for what it's actually
good at (catching `db.query()`-call-count regressions); it is not a
substitute for the real-engine verification that caught this one.
"""

import uuid
from unittest.mock import MagicMock, patch

from app.db.models.comparison import ExperimentComparison, ReproducibilityAssessment
from app.db.models.core import Experiment, ExperimentRun
from app.db.models.enums import RunType
from app.export.excel import _lineage_edges_for_experiments, _reports_for_comparisons


class _CountingQuery:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def options(self, *args, **kwargs):
        return self

    def one_or_none(self):
        return self._rows[0] if self._rows else None


class _CountingSession:
    def __init__(self, rows_by_model: dict):
        self._rows_by_model = rows_by_model
        self.query_call_count = 0

    def query(self, model):
        self.query_call_count += 1
        return _CountingQuery(self._rows_by_model.get(model, []))


def _experiment():
    e = MagicMock()
    e.id = uuid.uuid4()
    return e


def _run(experiment_id, parent_run_id=None):
    r = MagicMock()
    r.id = uuid.uuid4()
    r.experiment_id = experiment_id
    r.parent_run_id = parent_run_id
    r.run_type = RunType.ORIGINAL
    return r


def _comparison(base_run_id, compare_run_id):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.base_run_id = base_run_id
    c.compare_run_id = compare_run_id
    return c


def _fixture(n_experiments: int):
    experiments = [_experiment() for _ in range(n_experiments)]
    runs = []
    comparisons = []
    for experiment in experiments:
        base = _run(experiment.id)
        compare = _run(experiment.id, parent_run_id=base.id)
        runs.extend([base, compare])
        comparisons.append(_comparison(base.id, compare.id))
    return experiments, runs, comparisons


def test_lineage_edges_query_count_is_constant_regardless_of_experiment_count():
    small_experiments, small_runs, small_comparisons = _fixture(2)
    small_session = _CountingSession(
        {Experiment: small_experiments, ExperimentRun: small_runs, ExperimentComparison: small_comparisons}
    )
    _lineage_edges_for_experiments(small_session)

    large_experiments, large_runs, large_comparisons = _fixture(10)
    large_session = _CountingSession(
        {Experiment: large_experiments, ExperimentRun: large_runs, ExperimentComparison: large_comparisons}
    )
    _lineage_edges_for_experiments(large_session)

    assert small_session.query_call_count == large_session.query_call_count == 3


def test_reports_query_count_is_constant_regardless_of_comparison_count():
    with patch("app.export.excel.generate_report", return_value=object()):
        small_experiments, small_runs, small_comparisons = _fixture(2)
        small_session = _CountingSession(
            {
                Experiment: small_experiments,
                ExperimentRun: small_runs,
                ExperimentComparison: small_comparisons,
                ReproducibilityAssessment: [],
            }
        )
        small_results = _reports_for_comparisons(small_session)

        large_experiments, large_runs, large_comparisons = _fixture(10)
        large_session = _CountingSession(
            {
                Experiment: large_experiments,
                ExperimentRun: large_runs,
                ExperimentComparison: large_comparisons,
                ReproducibilityAssessment: [],
            }
        )
        large_results = _reports_for_comparisons(large_session)

    assert small_session.query_call_count == large_session.query_call_count == 4
    assert len(small_results) == 2
    assert len(large_results) == 10


def test_reports_for_comparisons_empty_db_issues_no_bulk_filter_queries():
    with patch("app.export.excel.generate_report", return_value=object()):
        session = _CountingSession({ExperimentComparison: []})
        results = _reports_for_comparisons(session)

    assert results == []
    assert session.query_call_count == 1
