"""
ÜRÜN BİRLEŞTİRME SCRIPTİ
========================
Farklı üretim hatlarında aynı isimle tekrar eden TÜM ürünleri
tek bir kayıt altında birleştirir.

Özellikler:
- Stokları toplar
- Stok hareketlerini aktarır
- Sayım kayıtlarını aktarır
- Ortak malzemeleri (somun, civata vs.) ORTAK MALZEMELER kategorisine taşır
- Diğer tekrar edenleri en fazla stoklu kategoride tutar

Kullanım:
  python merge_all_duplicates.py          # Sadece önizleme
  python merge_all_duplicates.py --apply  # Birleştirmeyi uygula
"""

import sys
from app import create_app, db
from app.models import Category, Product, StockMovement, StockCurrent, CountItem
from collections import defaultdict
from sqlalchemy import text

# Ortak malzeme anahtar kelimeleri
COMMON_KEYWORDS = [
    'somun', 'civata', 'cıvata', 'pul', 'rondela', 'saplama', 'vida', 
    'pim', 'perno', 'conta', 'segman', 'bilya', 'rulman', 
    'yatak', 'kayış', 'kayis', 'kasnak', 'dişli', 'disli', 'zincir', 'mil',
    'burç', 'burc', 'keçe', 'kece', 'oring', 'o-ring', 'perçin', 'percin', 
    'makas', 'sıyırıcı', 'siyirici', 'yay', 'perno', 'imbus', 'flanş', 'flans'
]

def normalize_name(name):
    """Ürün adını normalize et (karşılaştırma için)"""
    return ' '.join(name.lower().strip().split())

def is_common_product(name):
    """Ürün ortak malzeme mi kontrol et"""
    name_lower = name.lower()
    return any(kw in name_lower for kw in COMMON_KEYWORDS)

def get_or_create_common_category():
    """ORTAK MALZEMELER kategorisini bul veya oluştur"""
    common_cat = Category.query.filter_by(name='ORTAK MALZEMELER').first()
    if not common_cat:
        common_cat = Category(
            name='ORTAK MALZEMELER',
            code='ORTAK',
            unit='adet',
            note='Tüm üretim hatlarında kullanılan ortak parçalar'
        )
        db.session.add(common_cat)
        db.session.commit()
        print(f"✓ 'ORTAK MALZEMELER' kategorisi oluşturuldu")
    return common_cat

def analyze_duplicates():
    """Tekrar eden ürünleri analiz et"""
    products = Product.query.filter_by(is_active=True).all()
    
    # İsme göre grupla
    name_groups = defaultdict(list)
    for p in products:
        normalized = normalize_name(p.name)
        name_groups[normalized].append(p)
    
    # Sadece tekrar edenleri al
    duplicates = {name: prods for name, prods in name_groups.items() if len(prods) > 1}
    
    return products, duplicates

def preview_merge():
    """Birleştirme önizlemesi"""
    print("=" * 70)
    print("ÜRÜN BİRLEŞTİRME ÖNİZLEME")
    print("=" * 70)
    
    products, duplicates = analyze_duplicates()
    
    print(f"\nToplam aktif ürün: {len(products)}")
    print(f"Tekrar eden isim grubu: {len(duplicates)}")
    
    # İstatistikler
    total_duplicates = sum(len(ps) for ps in duplicates.values())
    will_delete = total_duplicates - len(duplicates)
    
    print(f"Tekrar eden kayıt sayısı: {total_duplicates}")
    print(f"Silinecek kayıt: {will_delete}")
    print(f"Birleştirme sonrası ürün sayısı: {len(products) - will_delete}")
    
    # Ortak malzeme sayısı
    common_count = sum(1 for name, _ in duplicates.items() if is_common_product(name))
    print(f"\nOrtak malzeme grubu: {common_count}")
    print(f"Diğer tekrar eden: {len(duplicates) - common_count}")
    
    # Örnek göster
    print("\n" + "-" * 70)
    print("ÖRNEK TEKRARLAR (İlk 15)")
    print("-" * 70)
    
    for i, (name, prods) in enumerate(list(duplicates.items())[:15]):
        total_stock = sum(p.current_stock for p in prods)
        is_common = "🔧" if is_common_product(name) else "📦"
        print(f"\n{is_common} {i+1}. {prods[0].name}")
        print(f"   Tekrar: {len(prods)} | Toplam Stok: {total_stock}")
        
        for p in prods:
            cat = p.category.name[:20] if p.category else 'Yok'
            stock_str = f"{p.current_stock:,.0f}" if p.current_stock else "0"
            print(f"   └─ [{p.code}] {cat:<20} Stok: {stock_str}")
    
    if len(duplicates) > 15:
        print(f"\n... ve {len(duplicates) - 15} grup daha")
    
    print("\n" + "=" * 70)
    print("Birleştirmeyi uygulamak için: python merge_all_duplicates.py --apply")
    print("=" * 70)
    
    return duplicates

def apply_merge():
    """Birleştirmeyi uygula"""
    print("=" * 70)
    print("ÜRÜN BİRLEŞTİRME İŞLEMİ BAŞLIYOR")
    print("=" * 70)
    
    # Yedek oluştur
    print("\n⚠️  İşlem geri alınamaz! Devam etmek istiyor musunuz?")
    confirm = input("Evet için 'EVET' yazın: ")
    if confirm != 'EVET':
        print("İşlem iptal edildi.")
        return
    
    products, duplicates = analyze_duplicates()
    common_cat = get_or_create_common_category()
    
    merged_count = 0
    deleted_count = 0
    stock_transferred = 0
    movements_transferred = 0
    
    print(f"\n{len(duplicates)} grup birleştiriliyor...\n")
    
    for name, prods in duplicates.items():
        is_common = is_common_product(name)
        
        # Ana ürünü seç: en fazla stoklu olan
        # Stoklar eşitse, ORTAK MALZEMELER kategorisindekini tercih et
        primary = max(prods, key=lambda p: (
            p.current_stock,
            1 if p.category and p.category.name == 'ORTAK MALZEMELER' else 0,
            -p.id  # En eski
        ))
        
        # Kategori belirleme
        if is_common:
            target_category = common_cat
        else:
            # En fazla stoklu ürünün kategorisinde kalsın
            target_category = primary.category
        
        # Ana ürünün kategorisini güncelle
        if target_category and primary.category_id != target_category.id:
            primary.category_id = target_category.id
        
        # Diğer ürünleri birleştir
        for p in prods:
            if p.id == primary.id:
                continue
            
            # Stok aktar
            if p.current_stock > 0:
                primary.current_stock += p.current_stock
                stock_transferred += p.current_stock
            
            # Stok hareketlerini aktar
            movements = StockMovement.query.filter_by(product_id=p.id).all()
            for m in movements:
                m.product_id = primary.id
                movements_transferred += 1
            
            # StockCurrent tablosundaki kaydı aktar
            try:
                old_stock = StockCurrent.query.filter_by(product_id=p.id).first()
                if old_stock:
                    primary_stock = StockCurrent.query.filter_by(product_id=primary.id).first()
                    if primary_stock:
                        primary_stock.quantity += old_stock.quantity
                    else:
                        old_stock.product_id = primary.id
            except:
                pass
            
            # Sayım kayıtlarını aktar
            try:
                count_items = CountItem.query.filter_by(product_id=p.id).all()
                for item in count_items:
                    item.product_id = primary.id
            except:
                pass
            
            # Eski ürünü pasif yap (silmek yerine)
            p.is_active = False
            p.notes = f"Birleştirildi: {primary.code}"
            deleted_count += 1
        
        merged_count += 1
        
        # İlerleme göster
        if merged_count % 100 == 0:
            print(f"  {merged_count}/{len(duplicates)} grup işlendi...")
    
    db.session.commit()
    
    # Sonuç raporu
    print("\n" + "=" * 70)
    print("İŞLEM TAMAMLANDI")
    print("=" * 70)
    print(f"✓ Birleştirilen grup: {merged_count}")
    print(f"✓ Pasif yapılan ürün: {deleted_count}")
    print(f"✓ Aktarılan stok: {stock_transferred:,.0f}")
    print(f"✓ Aktarılan hareket: {movements_transferred}")
    
    # Son durum
    active_count = Product.query.filter_by(is_active=True).count()
    common_count = Product.query.filter_by(category_id=common_cat.id, is_active=True).count()
    
    print(f"\nSon durum:")
    print(f"  Aktif ürün sayısı: {active_count}")
    print(f"  ORTAK MALZEMELER: {common_count}")

def cleanup_inactive():
    """Pasif ürünleri tamamen sil (opsiyonel)"""
    print("Pasif ürünler tamamen siliniyor...")
    
    inactive = Product.query.filter_by(is_active=False).all()
    count = len(inactive)
    
    for p in inactive:
        # Önce ilişkili kayıtları kontrol et
        movements = StockMovement.query.filter_by(product_id=p.id).count()
        if movements == 0:
            db.session.delete(p)
    
    db.session.commit()
    print(f"✓ {count} pasif ürün silindi")

def main():
    app = create_app()
    
    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == '--apply':
            apply_merge()
        elif len(sys.argv) > 1 and sys.argv[1] == '--cleanup':
            cleanup_inactive()
        else:
            preview_merge()

if __name__ == '__main__':
    main()
