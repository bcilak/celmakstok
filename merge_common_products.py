"""
Ortak Malzemeleri Birleştirme Script'i
======================================
Farklı üretim hatlarında tekrar eden ortak malzemeleri
(somun, civata, pul, rulman vs.) tespit edip
aynı isimdekileri tek bir ürün olarak birleştirir.
"""

from app import create_app, db
from app.models import Category, Product, StockMovement, StockCurrent
from collections import defaultdict

# Ortak malzeme anahtar kelimeleri
COMMON_KEYWORDS = [
    'somun', 'civata', 'pul', 'rondela', 'saplama', 'vida', 
    'pim', 'perno', 'conta', 'segman', 'bilya', 'rulman', 
    'yatak', 'kayis', 'kasnak', 'dişli', 'zincir', 'mil',
    'burç', 'keçe', 'oring', 'cıvata', 'perçin', 'makas'
]

def normalize_name(name):
    """Ürün adını normalize et (karşılaştırma için)"""
    # Küçük harf yap ve fazla boşlukları temizle
    return ' '.join(name.lower().strip().split())

def is_common_product(name):
    """Ürün ortak malzeme mi kontrol et"""
    name_lower = name.lower()
    return any(kw in name_lower for kw in COMMON_KEYWORDS)

def main():
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("ORTAK MALZEMELERİ BİRLEŞTİRME")
        print("=" * 60)
        
        # 1. Önce ORTAK MALZEMELER kategorisini oluştur/bul
        common_cat = Category.query.filter_by(name='ORTAK MALZEMELER').first()
        if not common_cat:
            common_cat = Category(
                name='ORTAK MALZEMELER',
                code='ORTAK',
                unit='adet',
                note='Tüm üretim hatlarında kullanılan ortak parçalar (somun, civata, rulman vs.)'
            )
            db.session.add(common_cat)
            db.session.commit()
            print(f"✓ 'ORTAK MALZEMELER' kategorisi oluşturuldu (ID: {common_cat.id})")
        else:
            print(f"○ 'ORTAK MALZEMELER' kategorisi mevcut (ID: {common_cat.id})")
        
        # 2. Tüm ürünleri tara, ortak malzemeleri bul
        all_products = Product.query.all()
        common_products = [p for p in all_products if is_common_product(p.name)]
        
        print(f"\nToplam ürün: {len(all_products)}")
        print(f"Ortak malzeme olarak tespit edilen: {len(common_products)}")
        
        # 3. Aynı isimli ürünleri grupla
        name_groups = defaultdict(list)
        for p in common_products:
            normalized = normalize_name(p.name)
            name_groups[normalized].append(p)
        
        # 4. Birden fazla kategoride olan ürünleri bul
        duplicates = {name: prods for name, prods in name_groups.items() if len(prods) > 1}
        
        print(f"Tekrar eden ürün grubu: {len(duplicates)}")
        
        merged_count = 0
        deleted_count = 0
        moved_count = 0
        
        # 5. Her grup için birleştir
        for name, products in duplicates.items():
            # En fazla bilgiye sahip olanı ana ürün yap
            # (en uzun koda sahip olan veya ilk eklenen)
            primary = max(products, key=lambda p: (len(p.code), -p.id))
            
            print(f"\n→ '{products[0].name}' ({len(products)} adet)")
            print(f"  Ana ürün: {primary.code} (Kategori: {primary.category.name if primary.category else 'Yok'})")
            
            # Ana ürünü ORTAK MALZEMELER kategorisine taşı
            if primary.category_id != common_cat.id:
                primary.category_id = common_cat.id
                moved_count += 1
            
            # Diğerlerini sil
            for p in products:
                if p.id != primary.id:
                    print(f"  Siliniyor: {p.code} (Kategori: {p.category.name if p.category else 'Yok'})")
                    
                    # Stok hareketlerini ana ürüne aktar
                    movements = StockMovement.query.filter_by(product_id=p.id).all()
                    for m in movements:
                        m.product_id = primary.id
                    
                    # Stok miktarını ana ürüne ekle
                    old_stock = StockCurrent.query.filter_by(product_id=p.id).first()
                    if old_stock:
                        primary_stock = StockCurrent.query.filter_by(product_id=primary.id).first()
                        if primary_stock:
                            primary_stock.quantity += old_stock.quantity
                        db.session.delete(old_stock)
                    
                    db.session.delete(p)
                    deleted_count += 1
            
            merged_count += 1
        
        # 6. Tek kategoride olup ortak malzeme olanları da ORTAK MALZEMELER'e taşı
        single_commons = {name: prods[0] for name, prods in name_groups.items() if len(prods) == 1}
        
        for name, p in single_commons.items():
            if p.category_id != common_cat.id:
                p.category_id = common_cat.id
                moved_count += 1
        
        db.session.commit()
        
        # 7. Sonuç raporu
        print("\n" + "=" * 60)
        print("İŞLEM TAMAMLANDI")
        print("=" * 60)
        print(f"✓ Birleştirilen grup: {merged_count}")
        print(f"✓ Silinen tekrar ürün: {deleted_count}")
        print(f"✓ ORTAK MALZEMELER'e taşınan: {moved_count}")
        
        # Son durum
        final_common = Product.query.filter_by(category_id=common_cat.id).count()
        final_total = Product.query.count()
        
        print(f"\nSon durum:")
        print(f"  Toplam ürün: {final_total}")
        print(f"  Ortak Malzemeler kategorisinde: {final_common}")
        
        # Boş kategorileri temizle
        empty_cats = []
        for cat in Category.query.all():
            if cat.id != common_cat.id:
                count = Product.query.filter_by(category_id=cat.id).count()
                if count == 0:
                    empty_cats.append(cat.name)
                    db.session.delete(cat)
        
        if empty_cats:
            db.session.commit()
            print(f"\n✓ Boş kategoriler silindi: {', '.join(empty_cats)}")

if __name__ == '__main__':
    main()
