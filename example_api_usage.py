"""
ÇELMAK Stok Takip API - Örnek Kullanım
Ürün ağacı görselleştirme ve analiz için örnek kodlar
"""

import requests
import json

# API Konfigürasyonu
API_BASE_URL = "http://localhost:5000/api"
BASE_URL = "http://localhost:5000"
API_KEY = "your-api-key-here"  # .env'den API_KEY

# Session kullan (cookie tabanlı auth için)
session = requests.Session()

# Headers
HEADERS = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
}

def login():
    """Flask uygulamasına giriş yap (session oluştur)"""
    try:
        # Login sayfasını ziyaret et (CSRF token için)
        session.get(f"{BASE_URL}/auth/login")

        # Login yap
        login_data = {
            'username': 'admin',
            'password': 'admin123'
        }
        response = session.post(f"{BASE_URL}/auth/login", data=login_data, allow_redirects=True)

        if response.status_code == 200 and 'logout' in response.text.lower():
            print("✓ Login başarılı (Session oluşturuldu)")
            return True
        else:
            print("✗ Login başarısız")
            return False
    except Exception as e:
        print(f"✗ Login hatası: {e}")
        return False

def health_check():
    """API sağlık kontrolü"""
    try:
        response = session.get(f"{API_BASE_URL}/v1/health", timeout=5)
        print("=== Health Check ===")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Hata: {response.text}")
        print()
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print("=== Health Check ===")
        print("❌ HATA: Flask uygulaması çalışmıyor!")
        print("\nÇözüm:")
        print("1. Yeni bir terminal açın")
        print("2. Çalıştırın: python run.py")
        print("3. Uygulama başladıktan sonra bu scripti tekrar çalıştırın")
        print()
        return False
    except Exception as e:
        print("=== Health Check ===")
        print(f"❌ Beklenmeyen hata: {e}")
        print()
        return False

def get_all_products():
    """Tüm ürünleri getir"""
    response = session.get(
        f"{API_BASE_URL}/v1/products/full"
    )
    data = response.json()
    print(f"=== Ürün Listesi ({data['count']} adet) ===")

    # İlk 5 ürünü göster
    for product in data['data'][:5]:
        print(f"- {product['code']}: {product['name']} (Stok: {product['current_stock']} {product['unit_type']})")
    print()

    return data['data']

def get_all_recipes():
    """Tüm reçeteleri getir"""
    response = session.get(
        f"{API_BASE_URL}/v1/recipes",
        headers=HEADERS
    )
    data = response.json()
    print(f"=== Reçete Listesi ({data['count']} adet) ===")

    for recipe in data['data']:
        print(f"- [{recipe['id']}] {recipe['name']} ({recipe['category_name']}) - {recipe['total_items']} malzeme")
    print()

    return data['data']

def get_recipe_detail(recipe_id):
    """Reçete detayını getir"""
    response = session.get(
        f"{API_BASE_URL}/v1/recipes/{recipe_id}",
        headers=HEADERS
    )
    data = response.json()['data']

    print(f"=== Reçete Detayı: {data['name']} ===")
    print(f"Kategori: {data['category_name']}")
    print(f"Model: {data['model_variant']}")
    print(f"\nMalzemeler ({len(data['items'])} adet):")

    for item in data['items']:
        status = "✓" if item['current_stock'] >= item['quantity'] else "✗"
        print(f"  {status} {item['product_name']}: {item['quantity']} {item['unit_type']} (Stok: {item['current_stock']})")
    print()

    return data

def get_product_tree():
    """Ürün ağacını hiyerarşik olarak getir"""
    response = session.get(
        f"{API_BASE_URL}/v1/product-tree",
        headers=HEADERS
    )
    data = response.json()

    print(f"=== Ürün Ağacı ({data['count']} reçete) ===")

    # İlk 2 reçeteyi detaylı göster
    for recipe in data['data'][:2]:
        print(f"\n📋 {recipe['name']} ({recipe['category_name']})")
        print(f"   └─ {len(recipe['children'])} malzeme:")

        for child in recipe['children'][:5]:  # İlk 5 malzeme
            print(f"      ├─ {child['code']}: {child['name']}")
            print(f"      │  ├─ Gerekli: {child['quantity_required']} {child['unit_type']}")
            print(f"      │  └─ Stok: {child['current_stock']} ({child['status']})")

        if len(recipe['children']) > 5:
            print(f"      └─ ... ve {len(recipe['children']) - 5} malzeme daha")
    print()

    return data['data']

def get_product_tree_flat():
    """Ürün ağacını düz (graph) formatında getir"""
    response = session.get(
        f"{API_BASE_URL}/v1/product-tree/flat",
        headers=HEADERS
    )
    data = response.json()

    print(f"=== Ürün Ağacı (Düz Format) ===")
    print(f"Düğümler (Nodes): {data['node_count']}")
    print(f"Bağlantılar (Edges): {data['edge_count']}")
    print()

    # İlk 5 düğüm
    print("Örnek Düğümler:")
    for node in data['nodes'][:5]:
        print(f"  - {node['id']} ({node['type']})")
    print()

    # İlk 5 bağlantı
    print("Örnek Bağlantılar:")
    for edge in data['edges'][:5]:
        print(f"  - {edge['source']} → {edge['target']}: {edge['label']}")
    print()

    return data

def check_production_feasibility(recipe_id, quantity=1):
    """Üretim yapılabilirliğini kontrol et"""
    response = session.get(
        f"{API_BASE_URL}/v1/recipe/{recipe_id}/can-produce",
        params={'quantity': quantity},
        headers=HEADERS
    )
    data = response.json()

    print(f"=== Üretim Kontrol (Reçete #{recipe_id}, Miktar: {quantity}) ===")

    if data['can_produce']:
        print(f"✓ {data['message']}")
    else:
        print(f"✗ {data['message']}")
        missing = data['missing_material']
        print(f"\nEksik Malzeme:")
        print(f"  - Ürün: {missing['product_name']} ({missing['product_code']})")
        print(f"  - Gerekli: {missing['required']} {missing['unit_type']}")
        print(f"  - Mevcut: {missing['available']} {missing['unit_type']}")
        print(f"  - Eksik: {missing['shortage']} {missing['unit_type']}")
    print()

    return data

def get_missing_materials(recipe_id, quantity=1):
    """Eksik malzemeleri listele"""
    response = session.get(
        f"{API_BASE_URL}/v1/recipe/{recipe_id}/missing-materials",
        params={'quantity': quantity},
        headers=HEADERS
    )
    data = response.json()

    print(f"=== Eksik Malzemeler ({data['recipe_name']}, Miktar: {quantity}) ===")

    if data['missing_count'] == 0:
        print("✓ Tüm malzemeler mevcut!")
    else:
        print(f"✗ {data['missing_count']} malzeme eksik:\n")

        for item in data['missing_materials']:
            print(f"  • {item['product_name']} ({item['product_code']})")
            print(f"    - Gerekli: {item['required']} {item['unit_type']}")
            print(f"    - Mevcut: {item['available']} {item['unit_type']}")
            print(f"    - Eksik: {item['shortage']} {item['unit_type']}")
            print()

    return data

def export_to_json(filename="product_tree.json"):
    """Ürün ağacını JSON dosyasına kaydet"""
    response = session.get(
        f"{API_BASE_URL}/v1/product-tree/flat",
        headers=HEADERS
    )
    data = response.json()

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✓ Ürün ağacı '{filename}' dosyasına kaydedildi.")
    print(f"  - Nodes: {data['node_count']}")
    print(f"  - Edges: {data['edge_count']}")
    print()

def generate_bom_report():
    """BOM (Bill of Materials) raporu oluştur"""
    print("=== BOM Raporu ===\n")

    # Tüm reçeteleri al
    recipes_response = requests.get(
        f"{API_BASE_URL}/v1/recipes",
        headers=HEADERS
    )
    recipes = recipes_response.json()['data']

    for recipe in recipes:
        # Her reçete için detay al
        detail_response = requests.get(
            f"{API_BASE_URL}/v1/recipes/{recipe['id']}",
            headers=HEADERS
        )
        detail = detail_response.json()['data']

        print(f"📋 {detail['name']} ({detail['category_name']})")
        print("-" * 60)
        print(f"{'Malzeme Kodu':<15} {'Malzeme Adı':<25} {'Miktar':<10} {'Birim':<8}")
        print("-" * 60)

        for item in detail['items']:
            print(f"{item['product_code']:<15} {item['product_name']:<25} {item['quantity']:<10.2f} {item['unit_type']:<8}")

        print("\n")

# ==================== ANA PROGRAM ====================

if __name__ == "__main__":
    print("=" * 70)
    print("   ÇELMAK Stok Takip API - Örnek Kullanım")
    print("=" * 70)
    print()

    # 0. Login yap (session oluştur)
    print("=== Authentication ===")
    if not login():
        print("\n⚠️  Login başarısız. Kullanıcı adı/şifre kontrol edin.")
        exit(1)
    print()

    # 1. Health Check
    if not health_check():
        print("\n⚠️  Flask uygulaması çalışmıyor. Lütfen önce uygulamayı başlatın.")
        print("\nTerminalde çalıştırın: python run.py")
        print()
        exit(1)

    # 2. Tüm ürünleri listele
    products = get_all_products()

    # 3. Tüm reçeteleri listele
    recipes = get_all_recipes()

    # 4. İlk reçetenin detayını getir
    if recipes:
        first_recipe = recipes[0]
        get_recipe_detail(first_recipe['id'])

        # 5. Üretim yapılabilirlik kontrolü
        check_production_feasibility(first_recipe['id'], quantity=5)

        # 6. Eksik malzemeleri listele
        get_missing_materials(first_recipe['id'], quantity=10)

    # 7. Ürün ağacını hiyerarşik olarak getir
    tree = get_product_tree()

    # 8. Ürün ağacını düz formatta getir (graph için)
    flat_tree = get_product_tree_flat()

    # 9. JSON'a aktar
    export_to_json("product_tree.json")

    # 10. BOM raporu oluştur (opsiyonel - uzun çıktı)
    # generate_bom_report()

    print("=" * 70)
    print("✓ Tüm örnekler başarıyla çalıştırıldı!")
    print("=" * 70)
