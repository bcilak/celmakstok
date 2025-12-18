"""
Veritabanını diyagrama uygun şekilde yeniden oluştur
ve CSV'den verileri aktar
"""

import csv
import re
from app import create_app, db
from app.models import User, Category, Product, StockCurrent

def generate_code(name, existing_codes):
    """Kategori adından benzersiz kod oluştur"""
    tr_map = {'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'İ': 'I', 
              'ö': 'o', 'Ö': 'O', 'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'}
    result = name
    for tr, en in tr_map.items():
        result = result.replace(tr, en)
    result = re.sub(r'[^A-Za-z0-9]', '', result)
    base_code = result[:8].upper()
    
    # Benzersiz yap
    code = base_code
    counter = 1
    while code in existing_codes:
        code = f"{base_code[:6]}{counter:02d}"
        counter += 1
    
    return code

def generate_product_code(category_code, index):
    """Ürün kodu oluştur"""
    return f"{category_code}-{index:04d}"

def rebuild_database():
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("VERİTABANI YENİDEN OLUŞTURULUYOR")
        print("=" * 50)
        
        # Tabloları sil ve yeniden oluştur
        db.drop_all()
        db.create_all()
        print("✓ Tablolar oluşturuldu")
        
        # Admin kullanıcısı
        admin = User(
            name='Sistem Yöneticisi',
            username='admin',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✓ Admin kullanıcısı oluşturuldu (admin / admin123)")
        
        # CSV'den kategorileri ve ürünleri oku
        csv_path = r"C:\Users\Baris\Desktop\master_urun_tablosu.csv"
        
        print(f"\nCSV dosyası okunuyor: {csv_path}")
        
        categories = {}  # name -> Category
        category_codes = set()  # benzersizlik için
        product_counters = {}  # category_id -> counter
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        print(f"Toplam {len(rows)} satır bulundu\n")
        
        # Önce kategorileri oluştur
        for row in rows:
            cat_name = row.get('Kategori', '').strip()
            if cat_name and cat_name not in categories:
                code = generate_code(cat_name, category_codes)
                category_codes.add(code)
                
                cat = Category(
                    name=cat_name,
                    code=code,
                    unit='adet',
                    note=f'{cat_name} üretim hattı'
                )
                db.session.add(cat)
                db.session.flush()
                categories[cat_name] = cat
                product_counters[cat.id] = 0
                print(f"✓ Üretim Hattı: {cat_name} (Kod: {code})")
        
        db.session.commit()
        print(f"\n✓ {len(categories)} üretim hattı oluşturuldu")
        
        # Şimdi ürünleri ekle
        products_created = 0
        
        for i, row in enumerate(rows):
            cat_name = row.get('Kategori', '').strip()
            product_name = row.get('Ürün Adı', '').strip()
            
            if not cat_name or not product_name:
                continue
            
            category = categories.get(cat_name)
            if not category:
                continue
            
            # Ürün kodu oluştur
            product_counters[category.id] += 1
            product_code = generate_product_code(category.code, product_counters[category.id])
            
            # Ürünü oluştur
            product = Product(
                code=product_code,
                name=product_name,
                category_id=category.id,
                unit_type='adet',
                current_stock=0,
                minimum_stock=0
            )
            db.session.add(product)
            products_created += 1
            
            # Her 500 üründe bir commit
            if products_created % 500 == 0:
                db.session.commit()
                print(f"İlerleme: {products_created} ürün eklendi...")
        
        db.session.commit()
        print(f"\n✓ {products_created} ürün oluşturuldu")
        
        # StockCurrent kayıtları oluştur
        print("\nStok kayıtları oluşturuluyor...")
        for product in Product.query.all():
            stock = StockCurrent(
                product_id=product.id,
                quantity=0
            )
            db.session.add(stock)
        
        db.session.commit()
        print(f"✓ {Product.query.count()} stok kaydı oluşturuldu")
        
        # Özet
        print("\n" + "=" * 50)
        print("TAMAMLANDI!")
        print("=" * 50)
        print(f"Kullanıcılar: {User.query.count()}")
        print(f"Üretim Hatları (Kategoriler): {Category.query.count()}")
        print(f"Ürünler: {Product.query.count()}")
        print(f"Stok Kayıtları: {StockCurrent.query.count()}")
        print("\nGiriş: admin / admin123")

if __name__ == '__main__':
    rebuild_database()
