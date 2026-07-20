"""add piece_count to bom_nodes

Revision ID: g1a2b3c4d5e8
Revises: f1a2b3c4d5e7
Create Date: 2026-07-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'g1a2b3c4d5e8'
down_revision = 'f1a2b3c4d5e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('bom_nodes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('piece_count', sa.Numeric(12, 4), nullable=True, server_default='1'))


def downgrade():
    with op.batch_alter_table('bom_nodes', schema=None) as batch_op:
        batch_op.drop_column('piece_count')
