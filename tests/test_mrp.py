"""
MRP eksik-parça golden testleri.

Çok seviyeli BOM'da doğru patlatma: yaprak-bazlı + hiyerarşi çarpanı.
135 tamburlu ağacı: kök → montaj(qty 2) → pik(qty 3) = makine başına 6 pik.
"""
from app.routes.reports import calculate_cost_for_quantity


def test_mrp_leaf_only_no_intermediate(app_ctx):
    r = calculate_cost_for_quantity("135 tamburlu", 10)["result"]
    codes = {c["kod"] for c in r["bilesenler"]}
    # Ara montaj grubu YAPRAK değil → listelenmemeli (çift sayım önlenir)
    assert "135-MONTAJ" not in codes
    assert "135-PIK-GG25" in codes


def test_mrp_quantity_multiplied_through_hierarchy(app_ctx):
    r = calculate_cost_for_quantity("135 tamburlu", 10)["result"]
    pik = next(c for c in r["bilesenler"] if c["kod"] == "135-PIK-GG25")
    # 2 (montaj) * 3 (pik) * 10 (makine) = 60 gerekli; stok 0 → 60 eksik
    assert pik["gerekli_miktar"] == 60.0
    assert pik["eksik_miktar"] == 60.0
    assert pik["eksik_tedarik_maliyeti"] == 60.0 * 730.0


def test_mrp_stock_netting(app_ctx):
    """Stok yeterliyse eksik 0 olmalı (bıçak tutucu stok=100)."""
    r = calculate_cost_for_quantity("165 tamburlu çayır biçme makinesi ürün ağacı", 10)["result"]
    comps = {c["kod"]: c for c in r["bilesenler"]}
    # BOM #8: alt tambur qty2 (stok 5), bıçak qty1 (stok 100)
    # 10 makine → alt tambur 20 gerekli - 5 stok = 15 eksik; bıçak 10 - 100 = 0 eksik
    assert comps["165-ALT-TAMBUR"]["eksik_miktar"] == 15.0
    assert comps["165-BICAK-TUTUCU"]["eksik_miktar"] == 0.0


def test_mrp_quantity_extracted_and_total(app_ctx):
    r = calculate_cost_for_quantity("135 tamburlu", 10)["result"]
    assert r["hedef_miktar"] == 10
    # Birim maliyet doğru patlatmadan: 6 pik * 730 = 4380 (get_bom_tree'nin eksik 2190'ı DEĞİL)
    assert round(r["birim_maliyet"], 2) == 4380.0
    assert round(r["toplam_maliyet"], 2) == 43800.0


def test_mrp_total_consistent_with_shortage(app_ctx):
    """Stok 0 iken toplam üretim maliyeti = toplam eksik tedarik maliyeti olmalı (tutarlılık)."""
    r = calculate_cost_for_quantity("135 tamburlu", 10)["result"]
    assert round(r["toplam_maliyet"], 2) == round(r["toplam_eksik_tedarik_maliyeti"], 2)
