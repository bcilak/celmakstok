"""
Geçici statik üretim adedi verisi golden testleri.
DB'ye geçildiğinde _load_production_data() değişecek; bu testler sözleşmeyi korur.
"""
from app.routes.reports import (
    get_production_quantities,
    _detect_production_period,
    _is_production_quantity_query,
    _fold_search_text,
)


def test_period_detection():
    assert _detect_production_period("nisan üretimi") == "2026-04"
    assert _detect_production_period("mayıs ayında kaç tane") == "2026-05"
    assert _detect_production_period("toplam üretim") is None


def test_quantity_query_detection():
    f = _fold_search_text
    assert _is_production_quantity_query(f("nisan üretimi nedir"))
    assert _is_production_quantity_query(f("kaç tane 165 tamburlu üretildi"))
    assert _is_production_quantity_query(f("toplam kaç adet üretim"))
    assert not _is_production_quantity_query(f("üretim durumu nedir"))  # hat sorusu


def test_april_total():
    res = get_production_quantities("nisan üretimi")["result"]
    d = res["donemler"]["Nisan 2026"]
    assert d["toplam_adet"] == 24 + 21 + 17 + 95  # 157


def test_specific_product_across_months():
    res = get_production_quantities("165 tamburlu üretimi")["result"]
    # 165 hem nisan (95) hem mayıs (91) içinde
    nisan = res["donemler"]["Nisan 2026"]["kalemler"]
    mayis = res["donemler"]["Mayıs 2026 (8 Mayıs'a kadar)"]["kalemler"]
    assert any("165" in r["name"] and r["qty"] == 95 for r in nisan)
    assert any("165" in r["name"] and r["qty"] == 91 for r in mayis)


def test_product_and_period_filter():
    res = get_production_quantities("mayıs 165 tamburlu kaç tane")["result"]
    assert set(res["donemler"]) == {"Mayıs 2026 (8 Mayıs'a kadar)"}
    rows = res["donemler"]["Mayıs 2026 (8 Mayıs'a kadar)"]["kalemler"]
    assert len(rows) == 1 and rows[0]["qty"] == 91


def test_list_all_with_filler_words():
    """'nisan ayında üretilen tüm ürünleri adetleri ile listele' → dolgu kelimeleri ürün sanılmamalı."""
    from app.routes.reports import _production_query_terms
    q = "nisan ayında üretilen tüm ürünleri adetleri ile listele"
    assert _production_query_terms(q) == []   # tüm/ile/adetleri filtre olmamalı
    res = get_production_quantities(q)["result"]
    rows = res["donemler"]["Nisan 2026"]["kalemler"]
    assert len(rows) == 4   # Nisan'daki tüm ürünler


def test_bagarasi_match():
    res = get_production_quantities("bağarası üretimi")["result"]
    # Hem nisan (17) hem mayıs (5)
    total = sum(d["toplam_adet"] for d in res["donemler"].values())
    assert total == 17 + 5
