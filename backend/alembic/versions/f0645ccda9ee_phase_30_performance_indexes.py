"""phase 30 performance indexes

Adds indexes on FK columns that are actually filtered/joined on by the
API routers (Phase 19) and Excel export (Phase 27) but had no index
until now - see docs/PERFORMANCE_OPTIMIZATION.md. Not run against a live
Postgres in this environment (same limitation as every prior DB-touching
phase) - structurally verified only.

Revision ID: f0645ccda9ee
Revises: c6dd8a238406
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f0645ccda9ee'
down_revision: Union[str, Sequence[str], None] = 'c6dd8a238406'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(op.f('ix_experiments_project_id'), 'experiments', ['project_id'])
    op.create_index(op.f('ix_experiment_runs_experiment_id'), 'experiment_runs', ['experiment_id'])
    op.create_index(op.f('ix_experiment_comparisons_base_run_id'), 'experiment_comparisons', ['base_run_id'])
    op.create_index(op.f('ix_experiment_comparisons_compare_run_id'), 'experiment_comparisons', ['compare_run_id'])
    op.create_index(op.f('ix_differences_comparison_id'), 'differences', ['comparison_id'])
    op.create_index(op.f('ix_provenance_nodes_run_id'), 'provenance_nodes', ['run_id'])
    op.create_index(op.f('ix_provenance_edges_from_node_id'), 'provenance_edges', ['from_node_id'])
    op.create_index(op.f('ix_provenance_edges_to_node_id'), 'provenance_edges', ['to_node_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_provenance_edges_to_node_id'), table_name='provenance_edges')
    op.drop_index(op.f('ix_provenance_edges_from_node_id'), table_name='provenance_edges')
    op.drop_index(op.f('ix_provenance_nodes_run_id'), table_name='provenance_nodes')
    op.drop_index(op.f('ix_differences_comparison_id'), table_name='differences')
    op.drop_index(op.f('ix_experiment_comparisons_compare_run_id'), table_name='experiment_comparisons')
    op.drop_index(op.f('ix_experiment_comparisons_base_run_id'), table_name='experiment_comparisons')
    op.drop_index(op.f('ix_experiment_runs_experiment_id'), table_name='experiment_runs')
    op.drop_index(op.f('ix_experiments_project_id'), table_name='experiments')
