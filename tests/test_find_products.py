"""
find_products golden testleri — kanonik ürün bulma katmanı.

Bu katman LLM→Python mimarisinin temeli. Mahremiyet: maliyet/fiyat SIZMAMALI.
"""
from app.routes.reports import find_products, _resolve_ref, _product_ref


def test_explicit_id_is_exact(app_ctx):
    from app.models import Product
    p = Product.query.filter_by(code="135-TAMBURLU-CAYI").first()
    res = find_products(f"#{p.id} maliyeti")["result"]
    assert res["guven"] == "kesin"
    assert res["adaylar"][0]["ref"] == _product_ref(p.id)


def test_exact_code_is_exact(app_ctx):
    res = find_products("165-TAMBURLU-CAYI-01 maliyeti")["result"]
    assert res["guven"] == "kesin"


def test_135_high_confidence(app_ctx):
    res = find_products("135 tamburlu")["result"]
    assert res["guven"] in ("yuksek", "kesin")
    assert res["adaylar"][0]["urun_adi"].startswith("135 TAMBURLU")


def test_urun_agaci_tightness_picks_8(app_ctx):
    """'... ürün ağacı' → MUHAFAZALI değil, tam eşleşen (#8) ilk sırada, yüksek güven."""
    res = find_products("165 tamburlu çayır biçme makinesi ürün ağacı")["result"]
    assert res["guven"] == "yuksek"
    top = res["adaylar"][0]
    assert top["bom_id"] == 8
    assert "MUHAFAZALI" not in top["ad"].upper()


def test_no_cost_leaked(app_ctx):
    """Mahremiyet: aday yapısında maliyet/fiyat alanı OLMAMALI."""
    res = find_products("165 tamburlu")["result"]
    for c in res["adaylar"]:
        keys = set(c.keys())
        assert not (keys & {"maliyet", "unit_cost", "fiyat", "birim_maliyet", "currency"})


def test_not_found(app_ctx):
    res = find_products("xyzqwerty olmayan urun")["result"]
    assert res["guven"] == "yok"
    assert res["adaylar"] == []


def test_resolve_ref_roundtrip(app_ctx):
    from app.models import Product
    p = Product.query.filter_by(code="135-TAMBURLU-CAYI").first()
    assert _resolve_ref(_product_ref(p.id)).id == p.id
    assert _resolve_ref(f"#{p.id}").id == p.id
    assert _resolve_ref("135 tamburlu").code == "135-TAMBURLU-CAYI"


def test_tools_accept_ref(app_ctx):
    """Maliyet/üretim tool'ları find_products ref'iyle ('P<id>') çağrılabilmeli."""
    from app.models import Product
    from app.routes.reports import calculate_cost_for_quantity, get_product_costs, _ref_to_keyword
    p = Product.query.filter_by(code="135-TAMBURLU-CAYI").first()
    ref = f"P{p.id}"
    assert _ref_to_keyword(ref) == "135-TAMBURLU-CAYI"
    # ref ile miktar maliyeti
    r = calculate_cost_for_quantity(ref, 10)["result"]
    assert r["kod"] == "135-TAMBURLU-CAYI"
    assert r["hedef_miktar"] == 10
    # ref ile maliyet listesi
    rc = get_product_costs(ref)["result"]
    assert isinstance(rc, list) and rc
