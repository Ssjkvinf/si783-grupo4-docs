"""users, roles and execution author

Revision ID: a4b8c2d9e1f0
Revises: e7c3a91f5b42
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4b8c2d9e1f0'
down_revision: Union[str, Sequence[str], None] = 'e7c3a91f5b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tabla de usuarios y columna «ejecutado por» (los registros anteriores quedan con autor NULL = no registrado)."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('session_version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    with op.batch_alter_table('execution_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('executed_by', sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f('ix_execution_history_executed_by'), ['executed_by'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('execution_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_execution_history_executed_by'))
        batch_op.drop_column('executed_by')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))
        batch_op.drop_index(batch_op.f('ix_users_id'))
    op.drop_table('users')
