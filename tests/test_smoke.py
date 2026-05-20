"""Fixture'ın ayağa kalktığını ve BOM ağacının hesaplandığını doğrular."""


def test_products_seeded(app_ctx):
    from app.models import Product
    assert Product.query.filter_by(is_active=True).count() >= 6


def test_list_boms(app_ctx):
    from app import db
    from app.utils.bom_utils import list_boms
    boms = {b["bom_id"]: b for b in list_boms(db)}
    assert set(boms) >= {5, 8, 9}
    assert "ÜRÜN AĞACI" in boms[8]["root_name"]
    assert "MUHAFAZALI" in boms[9]["root_name"]


def test_bom8_cost_rollup(app_ctx):
    from app import db
    from app.utils.bom_utils import get_bom_tree
    root = get_bom_tree(8, db)["roots"][0]
    # alt tambur 470*2 + bıçak 145*1 = 1085
    assert round(float(root["total_cost"]), 2) == 1085.0
