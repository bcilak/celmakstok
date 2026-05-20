"""
Ürün çözümleme golden testleri — sentetik BOM/ürün fixture'ı üzerinde.

Bu testler "hangi ürün seçiliyor" davranışını kilitler; defalarca bozulan asıl yer burası.
"""
import pytest

from app.routes.reports import (
    _resolve_primary_product,
    _product_search_query,
    analyze_product_family,
    _select_main_product,
    _is_anaphoric_reference,
)


# --- Birincil ürün çözümü ---------------------------------------------------
def test_resolve_prefers_bom_root_mamul(app_ctx):
    """'165 tamburlu maliyeti' → alt parça değil, BOM kökü mamul seçilmeli."""
    p = _resolve_primary_product("165 tamburlu maliyeti nedir")
    assert p is not None
    assert p.type == "mamul"
    assert p.code in ("165-TAMBURLU-CAYI-01", "165-TAMBURLU-CAYIR-B")


def test_resolve_135_tamburlu(app_ctx):
    p = _resolve_primary_product("135 tamburlu maliyeti")
    assert p is not None
    assert p.code == "135-TAMBURLU-CAYI"


def test_resolve_explicit_id(app_ctx):
    from app.models import Product
    target = Product.query.filter_by(code="135-TAMBURLU-CAYI").first()
    p = _resolve_primary_product(f"#{target.id} maliyeti")
    assert p is not None and p.id == target.id


def test_resolve_turkish_suffix(app_ctx):
    """'tamburlunun' eki bir ürünü bulabilmeli (stemmer sayesinde)."""
    p = _resolve_primary_product("tamburlunun maliyeti nedir")
    assert p is not None
    assert "TAMBURLU" in p.name.upper()


def test_resolve_general_query_returns_none(app_ctx):
    assert _resolve_primary_product("kritik stokta neler var") is None


# --- BOM tightness: #8 (tam) #9'dan (MUHAFAZALI) önce gelmeli ---------------
def test_family_bom_tightness_order(app_ctx):
    fam = analyze_product_family("165 tamburlu çayır biçme makinesi ürün ağacı").get("result")
    assert isinstance(fam, dict)
    boms = fam.get("urun_agaclari") or []
    assert boms, "en az bir BOM eşleşmeli"
    # En sıkı eşleşen (extra_tokens=0, yani #8) ilk sırada olmalı
    assert boms[0]["bom_id"] == 8
    assert "MUHAFAZALI" not in (boms[0]["urun_agaci"] or "")


def test_select_main_product_picks_tight_bom(app_ctx):
    fam = analyze_product_family("165 tamburlu çayır biçme makinesi ürün ağacı").get("result")
    product, bom = _select_main_product("165 tamburlu çayır biçme makinesi ürün ağacı", fam)
    assert bom is not None
    assert bom["bom_id"] == 8


# --- "eski" filtresi --------------------------------------------------------
def test_eski_excluded_by_default(app_ctx):
    """'eski' yazılmadıkça ESKİ ürün seçilmemeli."""
    pq, _ = _product_search_query("165 tamburlu")
    results = pq.all()
    # En azından ESKİ olmayan alternatif bulunmalı; çözüm ESKİ döndürmemeli
    p = _resolve_primary_product("165 tamburlu maliyeti")
    assert "ESKİ" not in (p.name or "").upper()


def test_eski_included_when_searched(app_ctx):
    """Kullanıcı açıkça 'eski' ararsa ESKİ ürün eşleşebilmeli."""
    pq, _ = _product_search_query("165 tamburlu eski")
    names = [p.name.upper() for p in pq.all()]
    assert any("ESKİ" in n for n in names)
