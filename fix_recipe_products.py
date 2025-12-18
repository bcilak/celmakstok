"""
Reçetelerdeki ürünleri stoklu ürünlerle eşleştir.
Sorun: Reçeteler TAMBUR-xxxx kodlu ürünlere bağlı ama bu ürünlerin stoku 0.
Çözüm: Aynı isimli, stoklu ürünleri bul ve reçeteleri onlara bağla.
"""

from app import create_app, db
from app.models import Recipe, RecipeItem, Product

def fix_recipe_products():
    app = create_app()
    with app.app_context():
        # Tüm reçeteleri al
        recipes = Recipe.query.all()
        
        print("=" * 70)
        print("REÇETE ÜRÜN EŞLEŞTİRME")
        print("=" * 70)
        
        total_fixed = 0
        total_not_found = 0
        
        for recipe in recipes:
            print(f"\n📋 Reçete: {recipe.name}")
            print("-" * 50)
            
            for item in recipe.items:
                current_product = item.product
                
                # Eğer ürünün stoku 0 ise, aynı isimli stoklu ürün ara
                if current_product.current_stock <= 0:
                    # Aynı isimli, stoklu ürün bul
                    alternative = Product.query.filter(
                        Product.name == current_product.name,
                        Product.current_stock > 0,
                        Product.id != current_product.id
                    ).order_by(Product.current_stock.desc()).first()
                    
                    if alternative:
                        print(f"  ✅ {current_product.name}")
                        print(f"     ESKİ: {current_product.code} (stok: {current_product.current_stock})")
                        print(f"     YENİ: {alternative.code} (stok: {alternative.current_stock})")
                        
                        # Reçete kalemini güncelle
                        item.product_id = alternative.id
                        total_fixed += 1
                    else:
                        # Benzer isimli ürün ara (kısmi eşleşme)
                        name_parts = current_product.name.split()
                        if len(name_parts) >= 2:
                            search_term = ' '.join(name_parts[:2])
                            alternative = Product.query.filter(
                                Product.name.ilike(f'{search_term}%'),
                                Product.current_stock > 0,
                                Product.id != current_product.id
                            ).order_by(Product.current_stock.desc()).first()
                            
                            if alternative:
                                print(f"  ⚠️  {current_product.name}")
                                print(f"     ESKİ: {current_product.code} (stok: {current_product.current_stock})")
                                print(f"     YENİ (benzer): {alternative.name} | {alternative.code} (stok: {alternative.current_stock})")
                                
                                item.product_id = alternative.id
                                total_fixed += 1
                            else:
                                print(f"  ❌ {current_product.name} - Stoklu alternatif bulunamadı!")
                                total_not_found += 1
                        else:
                            print(f"  ❌ {current_product.name} - Stoklu alternatif bulunamadı!")
                            total_not_found += 1
                else:
                    print(f"  ✓ {current_product.name} (stok: {current_product.current_stock}) - OK")
        
        print("\n" + "=" * 70)
        print(f"ÖZET: {total_fixed} ürün düzeltildi, {total_not_found} ürün için alternatif bulunamadı")
        print("=" * 70)
        
        if total_fixed > 0:
            confirm = input("\nDeğişiklikleri kaydetmek istiyor musunuz? (e/h): ")
            if confirm.lower() == 'e':
                db.session.commit()
                print("✅ Değişiklikler kaydedildi!")
            else:
                db.session.rollback()
                print("❌ Değişiklikler iptal edildi.")
        else:
            print("Değişiklik yapılmadı.")

if __name__ == '__main__':
    fix_recipe_products()
