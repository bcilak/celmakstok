"""
Çok seviyeli BOM maliyet roll-up doğrulama testleri (get_bom_tree).

Miktar semantiği PER-PARENT'tır (parser node.quantity = piece_count, parent başına adet).
Bu yüzden roll-up hiyerarşi boyunca ÇARPMALIDIR.

Fixture BOM #5: kök → montaj (qty 2) → pik (qty 3, birim 730 TRY)
  → pik (bir montaj için):   730 * 3 = 2190
  → montaj (makine için):    2190 * 2 = 4380   (birim montaj maliyeti 2190)
  → kök (makine):            4380
"""
from app import db
from app.utils.bom_utils import get_bom_tree


def _find(node, code):
    if node.get("code") == code:
        return node
    for c in node.get("children") or []:
        r = _find(c, code)
        if r:
            return r
    return None


def test_leaf_cost(app_ctx):
    root = get_bom_tree(5, db)["roots"][0]
    pik = _find(root, "135-PIK-GG25")
    assert round(float(pik["total_cost"]), 2) == 2190.0   # 730 * 3


def test_intermediate_multiplies_own_quantity(app_ctx):
    root = get_bom_tree(5, db)["roots"][0]
    montaj = _find(root, "135-MONTAJ")
    # Montaj makine başına 2 adet → toplam 4380, birim 2190
    assert round(float(montaj["total_cost"]), 2) == 4380.0
    assert round(float(montaj["unit_cost"]), 2) == 2190.0


def test_root_total_is_full_explosion(app_ctx):
    root = get_bom_tree(5, db)["roots"][0]
    # Kök = 6 pik * 730 = 4380 (eksik sayan 2190 DEĞİL)
    assert round(float(root["total_cost"]), 2) == 4380.0


def test_single_level_unchanged(app_ctx):
    """Tek seviyeli BOM (#8) değişmemeli: 470*2 + 145*1 = 1085."""
    root = get_bom_tree(8, db)["roots"][0]
    assert round(float(root["total_cost"]), 2) == 1085.0
