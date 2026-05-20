"""
NLU saf fonksiyon golden testleri — DB gerektirmez.

Bu testler dil-anlama katmanındaki heuristikleri kilitler. "İlk denemede çalışıyordu
sonra bozuldu" regresyonlarını yakalamak için buradalar. Davranış değişirse test kırılır.
"""
import pytest

from app.routes.reports import (
    _turkish_stem,
    _turkish_stem_aggressive,
    _extract_quantity,
    _is_anaphoric_reference,
    _name_extra_token_count,
    _search_terms,
    _normalize_search_keyword,
    _is_cost_only_query,
)


# --- Türkçe stemmer ---------------------------------------------------------
@pytest.mark.parametrize("word,expected", [
    ("tamburlunun", "tamburlu"),   # ilgi eki — kök seslisi korunur (tamburl DEĞİL)
    ("tamburlu", "tamburlu"),      # çekimsiz — değişmez
    ("makinesinin", "makine"),
    ("tamburunun", "tamburu"),     # konservatif
    ("kutusunun", "kutu"),
    ("stoktan", "stok"),
    ("kafa", "kafa"),              # kısa kelime dokunulmaz
    ("165", "165"),               # sayı dokunulmaz
])
def test_turkish_stem(word, expected):
    assert _turkish_stem(word) == expected


def test_turkish_stem_aggressive_for_subparts():
    # "tamburunun" → konservatif "tamburu" → agresif "tambur" (alt parça eşleşmesi için)
    assert _turkish_stem_aggressive("tamburunun") == "tambur"


# --- Miktar çıkarımı --------------------------------------------------------
@pytest.mark.parametrize("query,expected", [
    ("10 adet 135 tamburlu maliyeti ne olur?", 10),
    ("15 tanesinin maliyeti nedir", 15),
    ("200 adet üretmek istesem", 200),
    ("165 tamburlu maliyeti nedir", None),   # 165 ürün adı, miktar DEĞİL
    ("tamburlu maliyeti", None),
    ("135 tamburlu stok", None),
])
def test_extract_quantity(query, expected):
    assert _extract_quantity(query) == expected


# --- Anafora (sohbet hafızası) ---------------------------------------------
@pytest.mark.parametrize("query,expected", [
    ("bunun stok maliyeti nedir", True),
    ("şunun maliyeti", True),
    ("onun stok değeri", True),
    ("bu ürünün maliyeti", True),
    ("aynısının fiyatı", True),
    ("bu hafta kritik ürünler", False),     # 'bu hafta' tetiklememeli
    ("165 tamburlu maliyeti", False),
    ("kritik stok neler", False),
])
def test_anaphora_detection(query, expected):
    assert _is_anaphoric_reference(query) is expected


# --- BOM adı "sıkılık" skoru (#8 vs #9) -------------------------------------
def test_name_tightness_prefers_exact():
    terms = _search_terms(_normalize_search_keyword(
        "165 tamburlu çayır biçme makinesi ürün ağacı maliyeti"))
    e8 = _name_extra_token_count("165 TAMBURLU ÇAYIR BİÇME MAKİNESİ ÜRÜN AĞACI", terms)
    e9 = _name_extra_token_count("165 TAMBURLU ÇAYIR BİÇME MAKİNESİ MUHAFAZALI ÜRÜN AĞACI", terms)
    assert e8 == 0
    assert e9 > e8   # MUHAFAZALI fazladan kelime → daha gevşek eşleşme


# --- Sadece-maliyet sorusu tespiti -----------------------------------------
@pytest.mark.parametrize("query,expected", [
    ("165 tamburlu maliyeti nedir", True),
    ("tamburlu fiyatı", True),
    ("165 tamburlu stok maliyeti", False),   # 'stok' ekstra → sadece-maliyet değil
    ("165 tamburlu maliyet kırılımı", False),
])
def test_is_cost_only_query(query, expected):
    assert _is_cost_only_query(query) is expected
