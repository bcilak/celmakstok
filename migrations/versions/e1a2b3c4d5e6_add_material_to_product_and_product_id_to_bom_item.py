"""Add material to Product and product_id to BomItem

Revision ID: e1a2b3c4d5e6
Revises: c6b0cb856884
Create Date: 2026-03-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5e6'
down_revision = '8f5447bea936'
branch_labels = None
depends_on = None


def upgrade():
    # Product modeline malzeme cinsi / özellik alanı ekle
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('material', sa.Text(), nullable=True))

    # BomItem'a Product Master bağlantısı ekle
    with op.batch_alter_table('bom_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_bom_items_product_id',
            'products',
            ['product_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('bom_items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_bom_items_product_id', type_='foreignkey')
        batch_op.drop_column('product_id')

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('material')
