"""add fireli weight fields to bom_nodes

Revision ID: f1a2b3c4d5e7
Revises: e1a2b3c4d5e6
Create Date: 2026-03-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e7'
down_revision = 'e1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('bom_nodes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantity_net',    sa.Numeric(12, 4), nullable=True))
        batch_op.add_column(sa.Column('weight_per_unit', sa.Numeric(12, 4), nullable=True))
        batch_op.add_column(sa.Column('weight_unit',     sa.String(20),     nullable=True))


def downgrade():
    with op.batch_alter_table('bom_nodes', schema=None) as batch_op:
        batch_op.drop_column('weight_unit')
        batch_op.drop_column('weight_per_unit')
        batch_op.drop_column('quantity_net')
