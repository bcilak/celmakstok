"""
SATIN ALMA BİRİMİ UYGULAMASI - ÇELMAK API Entegrasyonu
Kritik stok takibi ve sipariş önerileri
"""

import requests
import json
from datetime import datetime

# API Konfigürasyonu
API_BASE_URL = "http://localhost:5000/api"
BASE_URL = "http://localhost:5000"

# Session kullan (cookie tabanlı auth için)
session = requests.Session()

def login():
    """Flask uygulamasına giriş yap"""
    try:
        session.get(f"{BASE_URL}/auth/login")
        login_data = {
            'username': 'admin',
            'password': 'admin123'
        }
        response = session.post(f"{BASE_URL}/auth/login", data=login_data, allow_redirects=True)

        if response.status_code == 200 and 'logout' in response.text.lower():
            print("✓ ÇELMAK API bağlantısı başarılı")
            return True
        else:
            print("✗ Login başarısız")
            return False
    except Exception as e:
        print(f"✗ Bağlantı hatası: {e}")
        return False


def get_critical_stock():
    """Kritik stok listesini getir"""
    response = session.get(f"{API_BASE_URL}/v1/purchasing/critical-stock")
    data = response.json()

    print("\n" + "=" * 80)
    print("🚨 KRİTİK STOK LİSTESİ - SATIN ALMA BİRİMİ")
    print("=" * 80)

    if data['count'] == 0:
        print("\n✓ Tüm ürünler yeterli stok seviyesinde!")
        print()
        return []

    print(f"\n⚠️  Toplam {data['count']} ürün kritik seviyede veya altında\n")

    # Aciliyet seviyesine göre grupla
    critical = [p for p in data['data'] if p['urgency_level'] == 'critical']
    medium = [p for p in data['data'] if p['urgency_level'] == 'medium']
    low = [p for p in data['data'] if p['urgency_level'] == 'low']

    # Kritik öncelikli ürünler (Stok tükendi)
    if critical:
        print("🔴 ACİL - STOK TÜKENDİ ({} ürün)".format(len(critical)))
        print("-" * 80)
        for p in critical:
            print(f"• {p['code']}: {p['name']}")
            print(f"  Mevcut: {p['current_stock']} {p['unit_type']} | Minimum: {p['minimum_stock']} {p['unit_type']}")
            print(f"  Eksik: {p['shortage']} {p['unit_type']}")
            if p['days_remaining']:
                print(f"  ⏰ {p['days_remaining']} gün içinde tükenir!")
            print()

    # Orta öncelikli ürünler
    if medium:
        print("🟡 ORTA ÖNCELİK ({} ürün)".format(len(medium)))
        print("-" * 80)
        for p in medium[:5]:  # İlk 5'i göster
            print(f"• {p['code']}: {p['name']}")
            print(f"  Mevcut: {p['current_stock']} {p['unit_type']} | Minimum: {p['minimum_stock']} {p['unit_type']}")
            print(f"  Haftalık tüketim: {p['weekly_consumption']} {p['unit_type']}")
            if p['days_remaining']:
                print(f"  ⏰ ~{p['days_remaining']} gün içinde tükenir")
            print()
        if len(medium) > 5:
            print(f"  ... ve {len(medium) - 5} ürün daha\n")

    # Düşük öncelikli ürünler
    if low:
        print(f"🟢 DÜŞÜK ÖNCELİK ({len(low)} ürün) - Yakında sipariş verilmeli\n")

    print("=" * 80)
    return data['data']


def get_reorder_suggestions():
    """Sipariş önerilerini getir"""
    response = session.get(f"{API_BASE_URL}/v1/purchasing/reorder-suggestions")
    data = response.json()

    print("\n" + "=" * 80)
    print("📦 SİPARİŞ ÖNERİLERİ")
    print("=" * 80)

    if data['count'] == 0:
        print("\n✓ Sipariş gerekli ürün yok\n")
        return []

    print(f"\nÖnerilen {data['count']} ürün için sipariş listesi:\n")

    total_items = 0
    high_priority = [p for p in data['data'] if p['priority'] == 'high']
    medium_priority = [p for p in data['data'] if p['priority'] == 'medium']
    low_priority = [p for p in data['data'] if p['priority'] == 'low']

    # Yüksek öncelikli
    if high_priority:
        print("🔴 YÜKSEK ÖNCELİK")
        print("-" * 80)
        for p in high_priority:
            print(f"• {p['code']}: {p['name']}")
            print(f"  Mevcut Stok: {p['current_stock']} {p['unit_type']}")
            print(f"  Eksik: {p['shortage']} {p['unit_type']}")
            print(f"  Aylık Tüketim: {p['monthly_consumption']} {p['unit_type']}")
            print(f"  ➡️  ÖNERİLEN SİPARİŞ: {p['economic_order_quantity']} {p['unit_type']}")
            print()
            total_items += 1

    # Orta öncelikli
    if medium_priority:
        print("🟡 ORTA ÖNCELİK")
        print("-" * 80)
        for p in medium_priority[:5]:
            print(f"• {p['code']}: {p['name']}")
            print(f"  ➡️  ÖNERİLEN SİPARİŞ: {p['economic_order_quantity']} {p['unit_type']}")
            print()
            total_items += 1
        if len(medium_priority) > 5:
            print(f"  ... ve {len(medium_priority) - 5} ürün daha\n")

    print(f"📋 TOPLAM: {total_items} ürün için sipariş önerisi")
    print("=" * 80)

    return data['data']


def get_product_purchasing_details(product_code):
    """Belirli bir ürün için detaylı satın alma bilgisi"""
    # Önce ürün ID'sini bul
    products_response = session.get(f"{API_BASE_URL}/products/search?q={product_code}")
    products = products_response.json()

    if not products:
        print(f"❌ Ürün bulunamadı: {product_code}")
        return None

    product_id = products[0]['id']

    # Detaylı bilgi al
    response = session.get(f"{API_BASE_URL}/v1/purchasing/product/{product_id}/details")
    data = response.json()['data']

    print("\n" + "=" * 80)
    print(f"📊 ÜRÜN DETAY ANALİZİ: {data['product']['name']}")
    print("=" * 80)

    # Ürün Bilgileri
    print("\n📦 ÜRÜN BİLGİSİ:")
    print(f"  Kod: {data['product']['code']}")
    print(f"  Kategori: {data['product']['category']}")
    print(f"  Mevcut Stok: {data['product']['current_stock']} {data['product']['unit_type']}")
    print(f"  Minimum Stok: {data['product']['minimum_stock']} {data['product']['unit_type']}")
    print(f"  Durum: {data['product']['status']}")

    # Tüketim Analizi
    print("\n📈 TÜKETİM ANALİZİ (Son 30 Gün):")
    print(f"  Toplam Giriş: {data['consumption_analysis']['last_30_days_in']} {data['product']['unit_type']}")
    print(f"  Toplam Çıkış: {data['consumption_analysis']['last_30_days_out']} {data['product']['unit_type']}")
    print(f"  Günlük Ort. Tüketim: {data['consumption_analysis']['daily_avg_consumption']:.2f} {data['product']['unit_type']}")
    if data['consumption_analysis']['days_until_stockout']:
        print(f"  ⏰ Tahmini Stok Bitişi: {data['consumption_analysis']['days_until_stockout']} gün")

    # Satın Alma Bilgisi
    print("\n💰 SATIN ALMA BİLGİSİ:")
    print(f"  Eksik Miktar: {data['purchasing_info']['shortage']} {data['product']['unit_type']}")
    print(f"  ➡️  ÖNERİLEN SİPARİŞ: {data['purchasing_info']['suggested_order']} {data['product']['unit_type']}")
    if data['purchasing_info']['last_purchase_date']:
        print(f"\n  Son Alım Tarihi: {data['purchasing_info']['last_purchase_date'][:10]}")
        print(f"  Son Alım Miktarı: {data['purchasing_info']['last_purchase_quantity']} {data['product']['unit_type']}")
        print(f"  Tedarikçi/Kaynak: {data['purchasing_info']['last_purchase_source']}")

    # Son Hareketler
    if data['recent_movements']:
        print("\n📋 SON HAREKETLER:")
        for m in data['recent_movements'][:5]:
            print(f"  • {m['date'][:10]}: {m['type']} - {m['quantity']} {data['product']['unit_type']}")
            if m['source']:
                print(f"    Kaynak: {m['source']}")

    print("=" * 80)
    return data


def export_critical_stock_report():
    """Kritik stok raporunu Excel/CSV formatında indir"""
    response = session.get(f"{API_BASE_URL}/v1/purchasing/critical-stock")
    data = response.json()

    if data['count'] == 0:
        print("✓ Export edilecek kritik ürün yok")
        return

    # CSV olarak kaydet
    filename = f"kritik_stok_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    import csv
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)

        # Başlıklar
        writer.writerow([
            'Ürün Kodu',
            'Ürün Adı',
            'Kategori',
            'Mevcut Stok',
            'Minimum Stok',
            'Eksik Miktar',
            'Birim',
            'Öncelik',
            'Günlük Ort. Tüketim',
            'Tahmini Bitişi (Gün)'
        ])

        # Veriler
        for p in data['data']:
            writer.writerow([
                p['code'],
                p['name'],
                p['category_name'] or '',
                p['current_stock'],
                p['minimum_stock'],
                p['shortage'],
                p['unit_type'],
                p['urgency_level'],
                p['daily_avg_consumption'],
                p['days_remaining'] if p['days_remaining'] else 'N/A'
            ])

    print(f"\n✓ Rapor kaydedildi: {filename}\n")


# ==================== ANA PROGRAM ====================

if __name__ == "__main__":
    print("=" * 80)
    print("       SATIN ALMA BİRİMİ UYGULAMASI - ÇELMAK API ENTEGRASYONUchin")
    print("=" * 80)
    print()

    # Login
    if not login():
        print("\n⚠️  ÇELMAK API'ye bağlanılamadı")
        exit(1)

    # Menü
    while True:
        print("\n" + "=" * 80)
        print("MENÜ")
        print("=" * 80)
        print("1. Kritik Stok Listesi")
        print("2. Sipariş Önerileri")
        print("3. Ürün Detay Analizi")
        print("4. Kritik Stok Raporu (CSV Export)")
        print("0. Çıkış")
        print()

        choice = input("Seçiminiz: ")

        if choice == "1":
            get_critical_stock()

        elif choice == "2":
            get_reorder_suggestions()

        elif choice == "3":
            product_code = input("\nÜrün Kodu: ")
            get_product_purchasing_details(product_code)

        elif choice == "4":
            export_critical_stock_report()

        elif choice == "0":
            print("\n👋 Çıkılıyor...")
            break

        else:
            print("\n❌ Geçersiz seçim!")

        input("\nDevam etmek için Enter'a basın...")
