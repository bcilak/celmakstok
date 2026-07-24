"""add product_id to production_records (schema drift fix)

The live production database's production_records table was missing the
product_id column entirely, even though it has been part of the
ProductionRecord model (and the 35a3166540d2 CREATE TABLE migration) for
a long time. The app already worked around this with a runtime column
check (_production_records_support_product_id() in production.py), but
that guard was easy to miss in new code (e.g. the catalog merge tool),
causing a hard crash: psycopg2.errors.UndefinedColumn on
production_records.product_id.

This migration adds the column if it's missing, so the workaround is no
longer needed anywhere.

Revision ID: i3c4d5e6f7g0
Revises: h2b3c4d5e6f9
Create Date: 2026-07-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'i3c4d5e6f7g0'
down_revision = 'h2b3c4d5e6f9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing_columns = {c['name'] for c in sa.inspect(conn).get_columns('production_records')}
    if 'product_id' not in existing_columns:
        with op.batch_alter_table('production_records', schema=None) as batch_op:
            batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_production_records_product_id', 'products', ['product_id'], ['id']
            )


def downgrade():
    conn = op.get_bind()
    existing_columns = {c['name'] for c in sa.inspect(conn).get_columns('production_records')}
    if 'product_id' in existing_columns:
        with op.batch_alter_table('production_records', schema=None) as batch_op:
            batch_op.drop_constraint('fk_production_records_product_id', type_='foreignkey')
            batch_op.drop_column('product_id')
