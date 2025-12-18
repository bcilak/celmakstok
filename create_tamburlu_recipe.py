"""
TAMBURLU Üretim Hattı Reçetelerini Oluşturma Scripti
3 model: 135'lik, 165'lik, 195'lik
"""
from app import create_app, db
from app.models import Category, Product, Recipe, RecipeItem
import random

app = create_app()

# TAMBURLU reçete verileri
TAMBURLU_DATA = [
    {"parca": "Cıvata M8 x 20", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Cıvata M10 x 25", "135lik": 22, "165lik": 22, "195lik": 28},
    {"parca": "Cıvata M10 x 30 İmpus", "135lik": 6, "165lik": 6, "195lik": 6},
    {"parca": "Cıvata M10 x 30 (Muhafaza)", "135lik": 8, "165lik": 8, "195lik": 12},
    {"parca": "Cıvata M10 x 50 İmpus", "135lik": 6, "165lik": 6, "195lik": 8},
    {"parca": "Cıvata M12 x 30 İmpus Havşa Başlı", "135lik": 6, "165lik": 6, "195lik": 6},
    {"parca": "Cıvata M12 x 140", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Cıvata M16 x 35", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Cıvata M16 x 40", "135lik": 3, "165lik": 3, "195lik": 3},
    {"parca": "Somun M8", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Somun M10", "135lik": 28, "165lik": 28, "195lik": 34},
    {"parca": "Somun M12", "135lik": 6, "165lik": 6, "195lik": 6},
    {"parca": "Somun M16", "135lik": 4, "165lik": 4, "195lik": 4},
    {"parca": "Pul M8", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Pul M10", "135lik": 28, "165lik": 28, "195lik": 34},
    {"parca": "Pul M12", "135lik": 6, "165lik": 6, "195lik": 6},
    {"parca": "Pul M16", "135lik": 4, "165lik": 4, "195lik": 4},
    {"parca": "Segman", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Kama", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Rulman 6206", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Rulman 6307", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Keçe 35'lik", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Keçe 40'lık", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Keçe 45'lik", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Şanzıman Gövdesi", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Şanzıman Kapak", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Üst Mil", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Alt Mil", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Ara Mil", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Z=63 Düz Helis Dişli", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Z=76 Düz Helis Dişli", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Z=25 Kuyruklu Konik Dişli", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Z=17 Küçük Kuyruklu Dişli", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Şanz. Şaft Mili", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "m=5 z=33 Düz Frezeli Dişli", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "m=5 z=36 Düz Frezeli Dişli", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "m=5 z=31 Düz Frezeli Dişli", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Frezeli Kısa Mil", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Frezeli Uzun Mil", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Frezeli Ara Mil", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Tambur Gövdesi", "135lik": 2, "165lik": 2, "195lik": 2},
    {"parca": "Bıçak", "135lik": 12, "165lik": 12, "195lik": 12},
    {"parca": "Bıçak Yuvası", "135lik": 12, "165lik": 12, "195lik": 12},
    {"parca": "Bıçak Pimi", "135lik": 12, "165lik": 12, "195lik": 12},
    {"parca": "Koruyucu Muhafaza", "135lik": 1, "165lik": 1, "195lik": 1},
    {"parca": "Kuyruk Mili Bağlantı Grubu", "135lik": 1, "165lik": 1, "195lik": 1}
]

def create_tamburlu():
    with app.app_context():
        # 1. TAMBURLU kategorisini oluştur veya bul
        category = Category.query.filter_by(name='TAMBURLU').first()
        if not category:
            category = Category(
                name='TAMBURLU',
                code='TAMBURLU',
                unit='adet',
                note='Tamburlu Çayır Biçme Makinesi üretim hattı'
            )
            db.session.add(category)
            db.session.flush()
            print(f"✓ TAMBURLU kategorisi oluşturuldu (ID: {category.id})")
        else:
            print(f"○ TAMBURLU kategorisi zaten var (ID: {category.id})")
        
        # 2. Malzemeleri oluştur
        product_map = {}  # parca adı -> Product
        created_products = 0
        
        for item in TAMBURLU_DATA:
            parca_adi = item['parca']
            
            # Ürün zaten var mı kontrol et
            product = Product.query.filter_by(name=parca_adi, category_id=category.id).first()
            
            if not product:
                # Ürün kodu oluştur
                code = f"TMB-{len(product_map)+1:03d}"
                
                product = Product(
                    code=code,
                    name=parca_adi,
                    category_id=category.id,
                    unit_type='adet',
                    current_stock=random.randint(50, 500),  # Test stoku
                    minimum_stock=10
                )
                db.session.add(product)
                created_products += 1
            
            product_map[parca_adi] = product
        
        db.session.flush()
        print(f"✓ {created_products} yeni ürün oluşturuldu")
        print(f"○ Toplam {len(product_map)} ürün reçetede kullanılacak")
        
        # 3. Reçeteleri oluştur (135'lik, 165'lik, 195'lik)
        variants = ['135lik', '165lik', '195lik']
        
        for variant in variants:
            variant_display = variant.replace('lik', "'lik")  # 135lik -> 135'lik
            recipe_name = f"TAMBURLU {variant_display}"
            
            # Mevcut reçeteyi kontrol et
            existing_recipe = Recipe.query.filter_by(name=recipe_name).first()
            if existing_recipe:
                # Eski kalemleri sil
                RecipeItem.query.filter_by(recipe_id=existing_recipe.id).delete()
                recipe = existing_recipe
                print(f"○ {recipe_name} reçetesi güncelleniyor...")
            else:
                recipe = Recipe(
                    name=recipe_name,
                    category_id=category.id,
                    model_variant=variant_display,
                    description=f"TAMBURLU Çayır Biçme Makinesi {variant_display} model reçetesi"
                )
                db.session.add(recipe)
                db.session.flush()
                print(f"✓ {recipe_name} reçetesi oluşturuldu")
            
            # Reçete kalemlerini ekle
            for item in TAMBURLU_DATA:
                parca_adi = item['parca']
                miktar = item[variant]
                
                if miktar > 0:
                    product = product_map.get(parca_adi)
                    if product:
                        recipe_item = RecipeItem(
                            recipe_id=recipe.id,
                            product_id=product.id,
                            quantity=miktar
                        )
                        db.session.add(recipe_item)
            
            print(f"  → {len(TAMBURLU_DATA)} malzeme eklendi")
        
        db.session.commit()
        
        # Özet
        print("\n" + "="*50)
        print("TAMBURLU REÇETELERİ OLUŞTURULDU!")
        print("="*50)
        
        recipes = Recipe.query.filter_by(category_id=category.id).all()
        for recipe in recipes:
            print(f"\n{recipe.name}:")
            print(f"  Malzeme sayısı: {recipe.total_items}")
            
            # Toplam parça sayısı
            total_parts = sum(item.quantity for item in recipe.items)
            print(f"  Toplam parça: {int(total_parts)}")

if __name__ == '__main__':
    create_tamburlu()
