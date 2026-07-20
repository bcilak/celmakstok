"""fix percent sign and missing part codes

'%' is a SQL LIKE wildcard, so codes containing it broke Product.code
ilike searches (unexpected matches). This migration replaces '%' with
'-' in existing products.code and bom_items.code values, and assigns
a '999-<id>' code to any row that has no code at all. products.code
is unique, so replacements that would collide get a numeric suffix.

Revision ID: h2b3c4d5e6f9
Revises: g1a2b3c4d5e8
Create Date: 2026-07-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'h2b3c4d5e6f9'
down_revision = 'g1a2b3c4d5e8'
branch_labels = None
depends_on = None


def _fix_codes(conn, table, enforce_unique):
    rows = conn.execute(sa.select(table.c.id, table.c.code)).fetchall()
    existing_codes = {row.code for row in rows if row.code}

    for row in rows:
        code = row.code
        new_code = code

        if code and '%' in code:
            new_code = code.replace('%', '-')
        if not new_code or not new_code.strip():
            new_code = f'999-{row.id}'

        if new_code == code:
            continue

        if enforce_unique:
            base = new_code
            suffix = 1
            while new_code in existing_codes and new_code != code:
                new_code = f'{base}-{suffix}'
                suffix += 1

        if code:
            existing_codes.discard(code)
        existing_codes.add(new_code)

        conn.execute(table.update().where(table.c.id == row.id).values(code=new_code))


def upgrade():
    conn = op.get_bind()
    metadata = sa.MetaData()
    products = sa.Table('products', metadata, autoload_with=conn)
    bom_items = sa.Table('bom_items', metadata, autoload_with=conn)

    _fix_codes(conn, products, enforce_unique=True)
    _fix_codes(conn, bom_items, enforce_unique=False)


def downgrade():
    # Data-only fix; original codes are not recoverable.
    pass
