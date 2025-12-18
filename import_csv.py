"""
CSV Ürün İçe Aktarma Scripti
master_urun_tablosu.csv dosyasını veritabanına aktarır
"""

import csv
import re
from app import create_app, db
from app.models import Category, Product

def generate_code(category_name, index):
    """Kategori adından benzersiz ürün kodu oluştur"""
    # Türkçe karakterleri dönüştür
    tr_map = {
        'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G',
        'ı': 'i', 'İ': 'I', 'ö': 'o', 'Ö': 'O',
        'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'
    }
    
    name = category_name
    for tr, en in tr_map.items():
        name = name.replace(tr, en)
    
    # Sadece harf ve rakamları al, boşlukları kaldır
    name = re.sub(r'[^A-Za-z0-9]', '', name)
    
    # İlk 6 karakteri al ve büyük harfe çevir
    prefix = name[:6].upper()
    
    # Kod oluştur: PREFIX-0001
    return f"{prefix}-{index:04d}"

def import_csv(csv_path):
    """CSV dosyasını veritabanına aktar"""
    app = create_app()
    
    with app.app_context():
        # Mevcut kategorileri al
        existing_categories = {c.name: c for c in Category.query.all()}
        
        # Kategori sayaçları (kod üretimi için)
        category_counters = {}
        
        # İstatistikler
        stats = {
            'categories_created': 0,
            'products_created': 0,
            'products_skipped': 0,
            'errors': []
        }
        
        print("CSV dosyası okunuyor...")
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            rows = list(reader)
            total = len(rows)
            
            print(f"Toplam {total} ürün bulundu.")
            if rows:
                print(f"İlk satır kolonları: {list(rows[0].keys())}")
                print(f"İlk satır: {rows[0]}\n")
            
            for i, row in enumerate(rows):
                try:
                    category_name = row.get('Kategori', '').strip()
                    product_name = row.get('Ürün Adı', '').strip()
                    
                    # Boş satırları atla
                    if not category_name or not product_name:
                        continue
                    
                    # Kategoriyi bul veya oluştur
                    if category_name not in existing_categories:
                        new_category = Category(
                            name=category_name,
                            description=f"{category_name} kategorisi",
                            is_production_line=True
                        )
                        db.session.add(new_category)
                        db.session.flush()  # ID almak için
                        existing_categories[category_name] = new_category
                        category_counters[category_name] = 0
                        stats['categories_created'] += 1
                        print(f"✓ Yeni kategori: {category_name}")
                    
                    # Sayacı güncelle
                    if category_name not in category_counters:
                        # Mevcut kategorideki son ürün kodunu bul
                        last_product = Product.query.filter(
                            Product.category_id == existing_categories[category_name].id
                        ).order_by(Product.id.desc()).first()
                        
                        if last_product and '-' in last_product.code:
                            try:
                                last_num = int(last_product.code.split('-')[-1])
                                category_counters[category_name] = last_num
                            except:
                                category_counters[category_name] = 0
                        else:
                            category_counters[category_name] = 0
                    
                    category_counters[category_name] += 1
                    
                    # Ürün kodu oluştur
                    product_code = generate_code(category_name, category_counters[category_name])
                    
                    # Aynı isimde ürün var mı kontrol et
                    existing_product = Product.query.filter_by(
                        name=product_name,
                        category_id=existing_categories[category_name].id
                    ).first()
                    
                    if existing_product:
                        stats['products_skipped'] += 1
                        continue
                    
                    # Ürünü oluştur
                    product = Product(
                        code=product_code,
                        name=product_name,
                        category_id=existing_categories[category_name].id,
                        unit_type='adet',
                        current_stock=0,
                        minimum_stock=0,
                        is_active=True
                    )
                    db.session.add(product)
                    stats['products_created'] += 1
                    
                    # Her 100 üründe bir commit ve ilerleme göster
                    if (i + 1) % 100 == 0:
                        db.session.commit()
                        print(f"İlerleme: {i + 1}/{total} ({(i + 1) * 100 // total}%)")
                
                except Exception as e:
                    stats['errors'].append(f"Satır {i + 2}: {str(e)}")
                    continue
            
            # Son commit
            db.session.commit()
        
        # Sonuçları göster
        print("\n" + "=" * 50)
        print("İÇE AKTARMA TAMAMLANDI")
        print("=" * 50)
        print(f"✓ Oluşturulan kategori: {stats['categories_created']}")
        print(f"✓ Oluşturulan ürün: {stats['products_created']}")
        print(f"○ Atlanan ürün (zaten var): {stats['products_skipped']}")
        
        if stats['errors']:
            print(f"\n⚠ Hatalar ({len(stats['errors'])}):")
            for error in stats['errors'][:10]:
                print(f"  - {error}")
            if len(stats['errors']) > 10:
                print(f"  ... ve {len(stats['errors']) - 10} hata daha")
        
        print("\nVeritabanı durumu:")
        print(f"  Toplam kategori: {Category.query.count()}")
        print(f"  Toplam ürün: {Product.query.count()}")

if __name__ == '__main__':
    import sys
    
    # Varsayılan CSV yolu
    csv_path = r"C:\Users\Baris\Desktop\master_urun_tablosu.csv"
    
    # Komut satırından yol verilmişse onu kullan
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    print(f"CSV dosyası: {csv_path}\n")
    import_csv(csv_path)
