"""Add indexes to speed up queries used by AI endpoints

Revision ID: add_indexes_ai
Revises: c8edc83688d4
Create Date: 2026-02-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_indexes_ai'
down_revision = 'c8edc83688d4'
branch_labels = None
depends_on = None


def upgrade():
    # index for stock movements queries by user and date
    op.create_index('idx_stockmov_user_date', 'stock_movements', ['user_id', 'date'], unique=False)
    # index for production records by user and date
    op.create_index('idx_production_user_date', 'production_records', ['user_id', 'date'], unique=False)
    # index for count sessions by user and created_at
    op.create_index('idx_countsess_user_created', 'count_sessions', ['user_id', 'created_at'], unique=False)


def downgrade():
    op.drop_index('idx_countsess_user_created', table_name='count_sessions')
    op.drop_index('idx_production_user_date', table_name='production_records')
    op.drop_index('idx_stockmov_user_date', table_name='stock_movements')
