"""usage dashboard: execution origin, run id and usage events

Revision ID: e7c3a91f5b42
Revises: d10691d55c95
Create Date: 2026-10-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c3a91f5b42'
down_revision: Union[str, Sequence[str], None] = 'd10691d55c95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (los registros anteriores quedan con origen NULL = no registrado)."""
    with op.batch_alter_table('execution_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trigger_source', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('run_id', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_execution_history_trigger_source'), ['trigger_source'], unique=False)
        batch_op.create_index(batch_op.f('ix_execution_history_run_id'), ['run_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_execution_history_executed_at'), ['executed_at'], unique=False)

    op.create_table(
        'usage_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('detail', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('usage_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usage_events_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_usage_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_usage_events_id'), ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usage_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usage_events_id'))
        batch_op.drop_index(batch_op.f('ix_usage_events_event_type'))
        batch_op.drop_index(batch_op.f('ix_usage_events_created_at'))
    op.drop_table('usage_events')

    with op.batch_alter_table('execution_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_execution_history_executed_at'))
        batch_op.drop_index(batch_op.f('ix_execution_history_run_id'))
        batch_op.drop_index(batch_op.f('ix_execution_history_trigger_source'))
        batch_op.drop_column('run_id')
        batch_op.drop_column('trigger_source')
