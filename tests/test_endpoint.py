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


def _ask(client, query):
    resp = client.post(
        "/reports/ai-assistant/ask",
        data=json.dumps({"query": query, "history": []}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    return resp.get_json()


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
