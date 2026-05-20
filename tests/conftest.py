"""
Test altyapısı — geçici SQLite veritabanı ile izole, hızlı ve tekrarlanabilir testler.

Üretim PostgreSQL'ine DOKUNMAZ. Her test oturumu kendi geçici dosya tabanlı
SQLite DB'sini oluşturur, sentetik ürün/BOM verisiyle doldurur ve sonunda siler.
"""
import os
import tempfile

import pytest

# config.py import edilmeden önce engine option'ları SQLite'ı patlatmasın diye
# TestConfig'i Config'ten türetip override ediyoruz.
from config import Config


class TestConfig(Config):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    # PostgreSQL'e özel pool ayarları SQLite'ta hata verir → temizle
    SQLALCHEMY_ENGINE_OPTIONS = {}
    # Gemini'yi testlerde devre dışı bırak (yerel/çözümleme yollarını test ediyoruz)
    GEMINI_API_KEY = None


@pytest.fixture(scope="session")
def app():
    from app import create_app, db

    db_fd, db_path = tempfile.mkstemp(suffix=".db", prefix="celmak_test_")
    os.close(db_fd)

    TestConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
    application = create_app(TestConfig)

    with application.app_context():
        db.create_all()
        _seed(db)
        yield application
        db.session.remove()
        db.drop_all()

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture()
def app_ctx(app):
    """Her test için temiz bir app context."""
    with app.app_context():
        yield app


# ---------------------------------------------------------------------------
# Sentetik veri — gerçek ÇELMAK yapısını minimal ama temsili biçimde taklit eder.
# ---------------------------------------------------------------------------

def _seed(db):
    from app.models import Product, Category, BomItem, BomNode, BomEdge, User

    admin = User(name="Test Admin", username="testadmin", role="admin", is_active=True)
    admin.set_password("x")
    db.session.add(admin)
    db.session.flush()

    cat = Category(name="Tamburlu", code="TMB", unit="adet")
    db.session.add(cat)
    db.session.flush()

    def mk_product(code, name, ptype="mamul", cost=0.0, stock=0.0, unit="adet"):
        p = Product(
            code=code, name=name, type=ptype, unit_type=unit,
            current_stock=stock, minimum_stock=0, unit_cost=cost,
            currency="TRY", vat_rate=20, is_active=True, category_id=cat.id,
        )
        db.session.add(p)
        db.session.flush()
        return p

    # --- Ana mamuller (BOM kökleri) ---
    # İki AYNI isimli "165 TAMBURLU ÇAYIR BİÇME MAKİNESİ" (gerçek veride olduğu gibi)
    p165a = mk_product("165-TAMBURLU-CAYI-01", "165 TAMBURLU ÇAYIR BİÇME MAKİNESİ")
    p165b = mk_product("165-TAMBURLU-CAYIR-B", "165 TAMBURLU ÇAYIR BİÇME MAKİNESİ")
    p135 = mk_product("135-TAMBURLU-CAYI", "135 TAMBURLU ÇAYIR BİÇME MAKİNESİ")
    p165_eski = mk_product("165-TAMBURLU-ESKI", "165 TAMBURLU ÇAYIR BİÇME MAKİNESİ ESKİ")

    # --- Alt parçalar / hammaddeler (fiyatlı yapraklar) ---
    alt_tambur = mk_product("165-ALT-TAMBUR", "165 Tamburlu Alt Tambur", "hammadde", cost=470.0, stock=5)
    bicak = mk_product("165-BICAK-TUTUCU", "165 Tamburlu Bıçak Tutucu", "hammadde", cost=145.0, stock=100)
    # Çok seviyeli (MRP) test için: montaj → parça
    montaj = mk_product("135-MONTAJ", "135 Tambur Montaj Grubu", "yarimamul", cost=0.0, stock=0)
    pik = mk_product("135-PIK-GG25", "Pik Döküm GG25 İşlenmiş", "hammadde", cost=730.0, stock=0)

    db.session.flush()

    def mk_item(product):
        it = BomItem(code=product.code, name=product.name, type=product.type,
                     unit_type=product.unit_type, product_id=product.id)
        db.session.add(it)
        db.session.flush()
        return it

    def mk_node(bom_id, num, level, product, qty=1.0, display=None):
        n = BomNode(
            bom_id=bom_id, num=num, level=level, item_id=mk_item(product).id,
            display_name=display or product.name, quantity=qty, piece_count=1,
            unit_type=product.unit_type,
        )
        db.session.add(n)
        db.session.flush()
        return n

    def mk_edge(bom_id, parent, child, qty=1.0):
        db.session.add(BomEdge(bom_id=bom_id, parent_node_id=(parent.id if parent else None),
                               child_node_id=child.id, quantity=qty))
        db.session.flush()

    # --- BOM #8: "165 ... ÜRÜN AĞACI" (p165a) — tek seviye, 2 yaprak ---
    r8 = mk_node(8, "1.", 0, p165a, display="165 TAMBURLU ÇAYIR BİÇME MAKİNESİ ÜRÜN AĞACI")
    c8a = mk_node(8, "1.1.", 1, alt_tambur, qty=2.0)
    c8b = mk_node(8, "1.2.", 1, bicak, qty=1.0)
    mk_edge(8, None, r8)
    mk_edge(8, r8, c8a, 2.0)
    mk_edge(8, r8, c8b, 1.0)

    # --- BOM #9: "165 ... MUHAFAZALI ÜRÜN AĞACI" (p165b) ---
    r9 = mk_node(9, "1.", 0, p165b, display="165 TAMBURLU ÇAYIR BİÇME MAKİNESİ MUHAFAZALI ÜRÜN AĞACI")
    c9a = mk_node(9, "1.1.", 1, bicak, qty=1.0)
    mk_edge(9, None, r9)
    mk_edge(9, r9, c9a, 1.0)

    # --- BOM #5: "135 ... ÜRÜN AĞACI" (p135) — ÇOK SEVİYELİ (MRP testi) ---
    # kök → montaj(qty 2) → pik(qty 3)  =>  1 makine için 6 pik gerekir
    r5 = mk_node(5, "1.", 0, p135, display="135 TAMBURLU ÇAYIR BİÇME MAKİNESİ ÜRÜN AĞACI")
    m5 = mk_node(5, "1.1.", 1, montaj, qty=2.0)
    leaf5 = mk_node(5, "1.1.1.", 2, pik, qty=3.0)
    mk_edge(5, None, r5)
    mk_edge(5, r5, m5, 2.0)
    mk_edge(5, m5, leaf5, 3.0)

    db.session.commit()
