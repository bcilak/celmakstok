"""
Mahremiyet (token-ikame) golden testleri.

Gemini'ye gönderim sırasında (g.ai_privacy=True) maliyet/fiyat değerleri ⟦C..⟧
token'larıyla maskelenmeli; gerçek tutar yanıt metnine ASLA ham olarak girmemeli.
_unmask token'ları geri koymalı. Yerel modda (privacy kapalı) gerçek değer kullanılmalı.
"""
import json

from flask import g

from app.routes.reports import (
    get_product_costs,
    calculate_cost_for_quantity,
    _unmask,
    _mask_cost,
    _ai_privacy_on,
)


def _enable_privacy():
    g.ai_vault = {}
    g.ai_privacy = True


def _disable_privacy():
    g.ai_privacy = False


def test_privacy_off_by_default(app_ctx):
    assert _ai_privacy_on() is False
    # Privacy kapalıyken gerçek değer döner (token değil)
    assert _mask_cost(470.0, "TRY") == 470.0


def test_cost_masked_when_privacy_on(app_ctx):
    _enable_privacy()
    try:
        res = get_product_costs("165 tamburlu çayır biçme makinesi ürün ağacı")["result"]
        blob = json.dumps(res, ensure_ascii=False)
        # BOM kökü maliyeti 1085 → token olmalı, ham sayı sızmamalı
        assert "⟦C" in blob
        assert "1085" not in blob
        # vault gerçek değeri tutmalı
        assert any("1.085" in v or "1085" in v for v in g.ai_vault.values())
    finally:
        _disable_privacy()


def test_quantity_cost_masked(app_ctx):
    _enable_privacy()
    try:
        res = calculate_cost_for_quantity("135 tamburlu", 10)["result"]
        blob = json.dumps(res, ensure_ascii=False)
        # Maliyet alanları token; miktarlar (60 eksik) açık kalmalı
        assert "⟦C" in blob
        assert "43800" not in blob and "4380" not in blob
        # eksik miktar (adet) maskelenmemeli
        pik = next(c for c in res["bilesenler"] if c["kod"] == "135-PIK-GG25")
        assert pik["eksik_miktar"] == 60.0
        assert isinstance(pik["birim_maliyet"], str) and pik["birim_maliyet"].startswith("⟦C")
    finally:
        _disable_privacy()


def test_unmask_restores_real_values(app_ctx):
    _enable_privacy()
    try:
        res = get_product_costs("165 tamburlu çayır biçme makinesi ürün ağacı")["result"]
        blob = json.dumps(res, ensure_ascii=False)
        restored = _unmask(blob)
        # Token kalmamalı, gerçek tutar geri gelmeli
        assert "⟦C" not in restored
        assert "1.085" in restored or "1085" in restored
    finally:
        _disable_privacy()


def test_privacy_off_returns_real(app_ctx):
    # Privacy kapalı: ham maliyet görünür (yerel mod)
    res = get_product_costs("165 tamburlu çayır biçme makinesi ürün ağacı")["result"]
    blob = json.dumps(res, ensure_ascii=False)
    assert "⟦C" not in blob
