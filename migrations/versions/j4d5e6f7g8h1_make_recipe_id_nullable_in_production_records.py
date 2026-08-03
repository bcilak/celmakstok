"""make recipe_id nullable in production_records (schema drift fix)

The live production database's production_records.recipe_id column is
still NOT NULL from the old "Recipe" system, even though the model
(ProductionRecord.recipe_id) has declared it nullable=True for a long
time since BOM-based production replaced recipes and no longer sets
this field. This caused a hard crash on every BOM production:
psycopg2.errors.NotNullViolation: null value in column "recipe_id".

This migration makes the column nullable if it isn't already, matching
the model.

Revision ID: j4d5e6f7g8h1
Revises: i3c4d5e6f7g0
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'j4d5e6f7g8h1'
down_revision = 'i3c4d5e6f7g0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    columns = {c['name']: c for c in sa.inspect(conn).get_columns('production_records')}
    col = columns.get('recipe_id')
    if col is not None and not col.get('nullable', True):
        with op.batch_alter_table('production_records', schema=None) as batch_op:
            batch_op.alter_column('recipe_id', existing_type=sa.Integer(), nullable=True)


def downgrade():
    pass
