"""
Uçtan uca endpoint testleri — /reports/ai-assistant/ask.
Disambiguation bloğunun üretim-adedi sorgularını YANLIŞ ürünle ele geçirmediğini doğrular.
"""
import json

import pytest


@pytest.fixture()
def client(app):
    from app.models import User
    c = app.test_client()
    with app.app_context():
        uid = User.query.filter_by(username="testadmin").first().id
    with c.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
    return c


def _ask_raw(client, payload):
    resp = client.post(
        "/reports/ai-assistant/ask",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    return resp.get_json()


def _ask(client, query):
    return _ask_raw(client, {"query": query, "history": []})


def test_production_query_not_hijacked_by_disambiguation(client):
    data = _ask(client, "mayıs ayında kaç 165 tamburlu üretildi")
    assert data["success"] is True
    answer = data["answer"]
    # Üretim adedi cevabı dönmeli, ÜRÜN/BOM (MUHAFAZALI) değil
    assert "Üretim Adetleri" in answer
    assert "91" in answer
    assert "MUHAFAZALI" not in answer.upper()
    # Belirsizlik (choices) de dönmemeli
    assert not data.get("choices")


def test_nisan_production_endpoint(client):
    data = _ask(client, "nisan üretimi nedir")
    assert data["success"] is True
    assert "157" in data["answer"] or "95" in data["answer"]


def test_ambiguous_query_returns_choice_buttons(client):
    """'tamburlu maliyeti' → belirsiz → tıklanabilir seçenekler dönmeli (find_products)."""
    data = _ask(client, "tamburlu maliyeti nedir")
    assert data["success"] is True
    assert data.get("source") == "find_products_disambiguation"
    assert data.get("choices") and len(data["choices"]) >= 2
    # Her seçeneğin tıklanınca göndereceği #ID sorgusu olmalı
    assert all(c["query"].startswith("#") for c in data["choices"])


def test_specific_query_no_disambiguation(client):
    """Spesifik (yüksek güven) sorgu doğrudan cevaplanmalı, seçenek sormamalı."""
    data = _ask(client, "165 tamburlu çayır biçme makinesi ürün ağacı maliyeti")
    assert data["success"] is True
    assert not data.get("choices")


def test_follow_ups_returned_for_product(client):
    """Ürün cevabında bağlamsal takip çipleri dönmeli."""
    data = _ask(client, "165 tamburlu çayır biçme makinesi ürün ağacı maliyeti")
    assert data["success"] is True
    fu = data.get("follow_ups")
    assert fu and len(fu) >= 2
    # Maliyet sorulduğu için 'Maliyeti' çipi tekrar önerilmemeli; stok/alt parça olmalı
    labels = [f["label"] for f in fu]
    assert "Stok durumu" in labels or "Alt parçaları" in labels
    # Her çipin göndereceği sorgu olmalı
    assert all(f.get("query") for f in fu)


def test_force_choices_lists_alternatives(client):
    """force_choices ile spesifik sorguda bile alternatifler buton olarak gelmeli ('değiştir')."""
    data = _ask_raw(client, {"query": "165 tamburlu", "history": [], "force_choices": True})
    assert data["success"] is True
    assert data.get("source") == "forced_choices"
    assert data.get("choices") and len(data["choices"]) >= 1


def test_choice_click_resolves_directly(client, app):
    """Seçenek tıklaması (#ID ...) yeniden belirsizlik tetiklememeli, o ürünü çözmeli."""
    from app.models import Product
    with app.app_context():
        pid = Product.query.filter_by(code="135-TAMBURLU-CAYI").first().id
    data = _ask(client, f"#{pid} tamburlu maliyeti nedir")
    assert data["success"] is True
    assert not data.get("choices")
    assert data.get("resolved_product", {}).get("id") == pid
