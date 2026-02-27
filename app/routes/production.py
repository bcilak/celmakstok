from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import Category, StockMovement, Product, Recipe, RecipeItem, ProductionRecord, ProductionConsumption
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta
from app.utils.decorators import roles_required
from app.utils.excel_utils import parse_bom_excel
from app.utils.decorators import roles_required

production_bp = Blueprint('production', __name__)

@production_bp.route('/')
@login_required
@roles_required('Genel', 'Yönetici')
def index():
    """Kategorileri üretim hatları olarak listele"""
    if current_user.is_admin():
        categories = Category.query.order_by(Category.name).all()
    else:
        categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    
    # Her kategori için istatistikler
    category_stats = {}
    for cat in categories:
        product_count = Product.query.filter_by(category_id=cat.id, is_active=True).count()
        total_stock = db.session.query(func.sum(Product.current_stock)).filter(
            Product.category_id == cat.id,
            Product.is_active == True
        ).scalar() or 0
        
        # Kritik stok sayısı
        critical_count = Product.query.filter(
            Product.category_id == cat.id,
            Product.is_active == True,
            Product.current_stock < Product.minimum_stock,
            Product.minimum_stock > 0
        ).count()
        
        category_stats[cat.id] = {
            'product_count': product_count,
            'total_stock': total_stock,
            'critical_count': critical_count
        }
    
    return render_template('production/index.html', 
        categories=categories, 
        category_stats=category_stats)

@production_bp.route('/category/<int:id>')
@login_required
@roles_required('Genel', 'Yönetici')
def view_category(id):
    """Kategorideki ürünleri listele"""
    category = Category.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    # Ürün sorgusu
    query = Product.query.filter_by(category_id=id, is_active=True)
    
    if search:
        query = query.filter(
            (Product.name.ilike(f'%{search}%')) | 
            (Product.code.ilike(f'%{search}%'))
        )
    
    if status == 'critical':
        query = query.filter(
            Product.current_stock < Product.minimum_stock,
            Product.minimum_stock > 0
        )
    elif status == 'empty':
        query = query.filter(Product.current_stock <= 0)
    elif status == 'ok':
        query = query.filter(Product.current_stock >= Product.minimum_stock)
    
    products = query.order_by(Product.name).paginate(page=page, per_page=50)
    
    # İstatistikler
    stats = {
        'total': Product.query.filter_by(category_id=id, is_active=True).count(),
        'total_stock': db.session.query(func.sum(Product.current_stock)).filter(
            Product.category_id == id, Product.is_active == True
        ).scalar() or 0,
        'critical': Product.query.filter(
            Product.category_id == id,
            Product.is_active == True,
            Product.current_stock < Product.minimum_stock,
            Product.minimum_stock > 0
        ).count(),
        'empty': Product.query.filter(
            Product.category_id == id,
            Product.is_active == True,
            Product.current_stock <= 0
        ).count()
    }
    
    return render_template('production/category_view.html', 
        category=category, 
        products=products,
        stats=stats,
        search=search,
        status=status)

@production_bp.route('/<int:id>')
@login_required
@roles_required('Genel', 'Yönetici')
def view(id):
    """Kategori görünümüne yönlendir"""
    category = Category.query.get_or_404(id)
    return redirect(url_for('production.view_category', id=category.id))

@production_bp.route('/category/<int:id>/consume', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def consume(id):
    """Kategoride malzeme tüketimi"""
    category = Category.query.get_or_404(id)
    
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', type=float)
        notes = request.form.get('notes', '')
        
        product = Product.query.get_or_404(product_id)
        
        if quantity <= 0:
            flash('Miktar sıfırdan büyük olmalıdır.', 'error')
        elif quantity > product.current_stock:
            flash(f'Yetersiz stok! Mevcut: {product.current_stock} {product.unit_type}', 'error')
        else:
            product.current_stock -= quantity
            
            movement = StockMovement(
                product_id=product_id,
                movement_type='cikis',
                quantity=quantity,
                source='Depo',
                destination=category.name,
                note=notes,
                user_id=current_user.id
            )
            db.session.add(movement)
            db.session.commit()
            
            flash(f'{category.name} için {product.name} tüketimi kaydedildi.', 'success')
            return redirect(url_for('production.view_category', id=id))
    
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('production/consume.html', category=category, products=products)

@production_bp.route('/lines/add', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def add_line():
    """Yeni kategori/hat ekle"""
    if request.method == 'POST':
        code = request.form.get('code', '').upper()
        name = request.form.get('name')
        unit = request.form.get('unit', 'adet')
        note = request.form.get('note', '')
        
        if Category.query.filter_by(code=code).first():
            flash('Bu hat kodu zaten kullanılıyor.', 'error')
        elif Category.query.filter_by(name=name).first():
            flash('Bu hat adı zaten kullanılıyor.', 'error')
        else:
            category = Category(code=code, name=name, unit=unit, note=note)
            db.session.add(category)
            db.session.commit()
            flash('Üretim hattı başarıyla eklendi.', 'success')
            return redirect(url_for('production.index'))
    
    return render_template('production/add_line.html')

@production_bp.route('/lines/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def edit_line(id):
    """Kategori/hat düzenle"""
    category = Category.query.get_or_404(id)
    
    if request.method == 'POST':
        category.name = request.form.get('name')
        category.unit = request.form.get('unit', 'adet')
        category.note = request.form.get('note', '')
        category.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Üretim hattı başarıyla güncellendi.', 'success')
        return redirect(url_for('production.index'))
    
    return render_template('production/edit_line.html', line=category)

@production_bp.route('/lines/<int:id>/toggle')
@login_required
@roles_required('Yönetici')
def toggle_line(id):
    """Kategori/hat aktif/pasif durumu değiştir"""
    category = Category.query.get_or_404(id)
    category.is_active = not category.is_active
    db.session.commit()
    
    status = 'aktif' if category.is_active else 'devre dışı'
    flash(f'{category.name} {status} yapıldı.', 'success')
    return redirect(url_for('production.index'))


@production_bp.route('/lines/<int:id>/delete', methods=['POST'])
@login_required
@roles_required('Yönetici')
def delete_line(id):
    """Üretim hattı/kategori sil"""
    category = Category.query.get_or_404(id)
    
    # Kategoriye bağlı aktif ürün var mı kontrol et
    product_count = Product.query.filter_by(category_id=id, is_active=True).count()
    if product_count > 0:
        flash(f'{category.name} hattında {product_count} aktif ürün bulunuyor. Önce ürünleri başka bir kategoriye taşıyın veya silin.', 'error')
        return redirect(url_for('production.index'))
    
    # Kategoriye bağlı reçete var mı kontrol et
    recipe_count = Recipe.query.filter_by(category_id=id).count()
    if recipe_count > 0:
        flash(f'{category.name} hattında {recipe_count} reçete bulunuyor. Önce reçeteleri silin veya başka bir hatta taşıyın.', 'error')
        return redirect(url_for('production.index'))
    
    name = category.name
    db.session.delete(category)
    db.session.commit()
    flash(f'{name} üretim hattı başarıyla silindi.', 'success')
    return redirect(url_for('production.index'))


# ===== REÇETE YÖNETİMİ =====

@production_bp.route('/recipes')
@login_required
@roles_required('Genel', 'Yönetici')
def recipes():
    """Tüm reçeteleri listele"""
    if current_user.is_admin():
        recipes = Recipe.query.order_by(Recipe.name).all()
    else:
        recipes = Recipe.query.filter_by(is_active=True).order_by(Recipe.name).all()
    return render_template('production/recipes.html', recipes=recipes)


@production_bp.route('/recipes/import_bom', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def import_bom():
    """Excel'den Ürün Ağacı (BOM) İçe Aktarma"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Dosya seçilmedi', 'error')
            return redirect(url_for('production.import_bom'))
            
        file = request.files['file']
        if file.filename == '':
            flash('Dosya seçilmedi', 'error')
            return redirect(url_for('production.import_bom'))
            
        main_product_name = request.form.get('main_product_name', '').strip()
        category_id = request.form.get('category_id', type=int)
        
        if not main_product_name or not category_id:
            flash('Lütfen Ana Mamül adını ve Kategori/Hattı belirleyin.', 'error')
            return redirect(url_for('production.import_bom'))
        
        if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            try:
                # Excel'i ayrıştır
                success_list, error_list = parse_bom_excel(file, main_product_name)
                
                if error_list:
                    flash(f"Excel okunurken hatalar oluştu: {error_list[0]['error']}", 'error')
                    return redirect(url_for('production.import_bom'))
                    
                if not success_list:
                    flash("Excel dosyasından geçerli veri çıkarılamadı.", 'warning')
                    return redirect(url_for('production.import_bom'))
                
                # BOM Verisini DB'ye Aktar
                # 1. Tüm eşsiz bileşenleri topla (Parent veya Child olarak geçenler)
                all_component_names = set([item['name'] for item in success_list] + [item['parent_name'] for item in success_list])
                
                # İsimlere göre kod üret (Basitçe büyük harf yap, boşlukları sil ve benzersiz bir ID ekle)
                import uuid
                import re
                def generate_code(name):
                    base = name.upper().replace(' ', '')
                    base = re.sub(r'[^A-Z0-9]', '', base)[:10] 
                    unique_suffix = str(uuid.uuid4()).split('-')[0][:4].upper()
                    return f'BOM-{base}-{unique_suffix}'
                
                # Veritabanında olanları ve olmayanları bul, olmayanları ekle
                product_map = {} # name -> Product nesnesi
                
                for name in all_component_names:
                    # Mevcut ürünü veya var olan aynı isimli ürünü ara
                    comp = Product.query.filter(Product.name.ilike(name)).first()
                    if not comp:
                        # Ürün yok, oluştur. Parent olanlar yarımamül, yaprağı olanlar hammadde.
                        # Hangi ürün parent'tır?
                        is_parent = any(item['parent_name'] == name for item in success_list)
                        is_main = name == main_product_name
                        
                        p_type = 'mamul' if is_main else ('yarimamul' if is_parent else 'hammadde')
                        
                        # Birim tipi bul
                        unit = 'adet'
                        for item in success_list:
                            if item['name'] == name:
                                unit = item['unit_type']
                                break
                                
                        comp = Product(
                            code=f"BOM-{generate_code(name)}",
                            name=name,
                            category_id=category_id,
                            type=p_type,
                            unit_type=unit,
                            current_stock=0,
                            minimum_stock=0
                        )
                        db.session.add(comp)
                        db.session.flush() # ID almak için
                    
                    product_map[name] = comp
                
                db.session.commit()
                
                # 2. Reçeteleri Oluştur
                # Hangi parent'ların reçetesi oluşturulacak?
                parent_names = set([item['parent_name'] for item in success_list])
                created_recipes = 0
                
                for parent_name in parent_names:
                    parent_product = product_map[parent_name]
                    
                    # Zaten bir reçetesi var mı?
                    existing_recipe = Recipe.query.filter_by(target_product_id=parent_product.id).first()
                    if not existing_recipe:
                        new_recipe = Recipe(
                            name=f"{parent_name} Üretim",
                            category_id=category_id,
                            target_product_id=parent_product.id,
                            description='Excel İçeri Aktarım (BOM Otomatik)'
                        )
                        db.session.add(new_recipe)
                        db.session.flush()
                        
                        # Child'ları recipe_items olarak ekle
                        for item in success_list:
                            if item['parent_name'] == parent_name:
                                child_prod = product_map[item['name']]
                                # Reçetede var mı kontrolü
                                existing_item = RecipeItem.query.filter_by(recipe_id=new_recipe.id, product_id=child_prod.id).first()
                                if not existing_item:
                                    r_item = RecipeItem(
                                        recipe_id=new_recipe.id,
                                        product_id=child_prod.id,
                                        quantity=item['quantity'],
                                    )
                                    db.session.add(r_item)
                        
                        created_recipes += 1
                        
                db.session.commit()
                flash(f'BOM başarıyla içe aktarıldı. Toplam {len(product_map)} parça tespit edildi, {created_recipes} alt reçete oluşturuldu.', 'success')
                return redirect(url_for('production.recipes'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Beklenmeyen bir hata oluştu: {str(e)}', 'error')
                return redirect(url_for('production.import_bom'))
        else:
            flash('Geçersiz dosya formatı. Lütfen .xlsx veya .xls dosyası yükleyin.', 'error')
            return redirect(url_for('production.import_bom'))
            
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template('production/import_bom.html', categories=categories)


@production_bp.route('/recipes/add', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def add_recipe():
    """Yeni reçete ekle"""
    if request.method == 'POST':
        name = request.form.get('name')
        category_id = request.form.get('category_id', type=int)
        target_product_id = request.form.get('target_product_id', type=int)
        model_variant = request.form.get('model_variant', '')
        description = request.form.get('description', '')
        
        if not name:
            flash('Reçete adı gereklidir.', 'error')
        elif not target_product_id:
            flash('Üretilecek hedef ürün seçilmelidir.', 'error')
        else:
            recipe = Recipe(
                name=name,
                category_id=category_id,
                target_product_id=target_product_id,
                model_variant=model_variant if model_variant else None,
                description=description
            )
            db.session.add(recipe)
            db.session.commit()
            flash('Reçete başarıyla oluşturuldu. Şimdi malzemeleri ekleyebilirsiniz.', 'success')
            return redirect(url_for('production.edit_recipe', id=recipe.id))
    
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    target_products = Product.query.filter(Product.type.in_(['mamul', 'yarimamul']), Product.is_active==True).order_by(Product.name).all()
    return render_template('production/add_recipe.html', categories=categories, target_products=target_products)


@production_bp.route('/recipes/<int:id>')
@login_required
@roles_required('Genel', 'Yönetici')
def view_recipe(id):
    """Reçete detayını görüntüle"""
    recipe = Recipe.query.get_or_404(id)
    return render_template('production/view_recipe.html', recipe=recipe)


@production_bp.route('/recipes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def edit_recipe(id):
    """Reçete düzenle ve malzeme ekle/çıkar"""
    recipe = Recipe.query.get_or_404(id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_info':
            recipe.name = request.form.get('name')
            recipe.category_id = request.form.get('category_id', type=int)
            recipe.target_product_id = request.form.get('target_product_id', type=int)
            recipe.model_variant = request.form.get('model_variant', '') or None
            recipe.description = request.form.get('description', '')
            db.session.commit()
            flash('Reçete bilgileri güncellendi.', 'success')
        
        elif action == 'add_item':
            product_id = request.form.get('product_id', type=int)
            quantity = request.form.get('quantity', type=float)
            note = request.form.get('item_note', '')
            
            if product_id and quantity and quantity > 0:
                # Zaten ekliyse güncelle
                existing = RecipeItem.query.filter_by(recipe_id=id, product_id=product_id).first()
                if existing:
                    existing.quantity = quantity
                    existing.note = note
                    flash('Malzeme miktarı güncellendi.', 'success')
                else:
                    item = RecipeItem(
                        recipe_id=id,
                        product_id=product_id,
                        quantity=quantity,
                        note=note
                    )
                    db.session.add(item)
                    flash('Malzeme reçeteye eklendi.', 'success')
                db.session.commit()
            else:
                flash('Ürün ve miktar seçiniz.', 'error')
        
        elif action == 'remove_item':
            item_id = request.form.get('item_id', type=int)
            item = RecipeItem.query.get(item_id)
            if item and item.recipe_id == id:
                db.session.delete(item)
                db.session.commit()
                flash('Malzeme reçeteden çıkarıldı.', 'success')
        
        return redirect(url_for('production.edit_recipe', id=id))
    
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    target_products = Product.query.filter(Product.type.in_(['mamul', 'yarimamul']), Product.is_active==True).order_by(Product.name).all()
    return render_template('production/edit_recipe.html', 
                          recipe=recipe, 
                          categories=categories,
                          products=products,
                          target_products=target_products)


@production_bp.route('/recipes/<int:id>/delete', methods=['POST'])
@login_required
@roles_required('Yönetici')
def delete_recipe(id):
    """Reçete sil"""
    recipe = Recipe.query.get_or_404(id)
    db.session.delete(recipe)
    db.session.commit()
    flash('Reçete silindi.', 'success')
    return redirect(url_for('production.recipes'))


@production_bp.route('/recipes/<int:id>/produce', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def produce_with_recipe(id):
    """Reçeteye göre üretim yap ve malzemeleri toplu tüket (Recursive)"""
    recipe = Recipe.query.get_or_404(id)
    
    if request.method == 'POST':
        quantity = request.form.get('quantity', type=float, default=1)
        note = request.form.get('note', '')
        
        if quantity <= 0:
            flash('Üretim miktarı sıfırdan büyük olmalıdır.', 'error')
            return redirect(url_for('production.produce_with_recipe', id=id))
        
        # Stok kontrolü (İç içe)
        can_produce, missing_product, available, required = recipe.can_produce(quantity)
        if not can_produce:
            flash(f'Yetersiz stok: {missing_product.name} - Mevcut: {available}, Gereken: {required}', 'error')
            return redirect(url_for('production.produce_with_recipe', id=id))
        
        # Üretim kaydı oluştur
        production = ProductionRecord(
            recipe_id=id,
            quantity=quantity,
            user_id=current_user.id,
            note=note
        )
        db.session.add(production)
        db.session.flush()  # ID almak için
        
        # Malzemeleri recursive olarak tüket
        def consume_recipe_materials(rec, qty, _visited=None):
            if _visited is None:
                _visited = set()
            if rec.id in _visited:
                return
            _visited.add(rec.id)
            
            for item in rec.items:
                req_qty = item.quantity * qty
                
                # Bu malzeme yarımamül/mamül mü ve bir reçetesi var mı?
                if item.product.recipes_as_target and len(item.product.recipes_as_target) > 0:
                    sub_recipe = item.product.recipes_as_target[0]
                    available_now = item.product.current_stock
                    
                    if available_now >= req_qty:
                        # Hazır varsa onu tüket
                        consume_qty = req_qty
                        item.product.current_stock -= consume_qty
                        
                        # Tüketim detayı ve stok hareketi ekle
                        add_consumption_and_movement(item.product.id, consume_qty, rec)
                    else:
                        # Hazır kısmı tüket
                        consume_qty = available_now
                        if consume_qty > 0:
                            item.product.current_stock -= consume_qty
                            add_consumption_and_movement(item.product.id, consume_qty, rec)
                        
                        # Kalan kısmı (eksik) üret
                        shortage_qty = req_qty - available_now
                        consume_recipe_materials(sub_recipe, shortage_qty, _visited)
                else:
                    # Normal hammadde
                    consume_qty = req_qty
                    item.product.current_stock -= consume_qty
                    add_consumption_and_movement(item.product.id, consume_qty, rec)
            
            _visited.remove(rec.id)
            
        def add_consumption_and_movement(p_id, c_qty, r):
            consumption = ProductionConsumption(
                production_id=production.id,
                product_id=p_id,
                quantity=c_qty
            )
            db.session.add(consumption)
            
            movement = StockMovement(
                product_id=p_id,
                movement_type='cikis',
                quantity=c_qty,
                source='Depo',
                destination=f'{r.category.name if r.category else "Üretim"} - {r.name}',
                note=f'Reçete üretimi: {quantity} adet (Kök: {recipe.name})',
                user_id=current_user.id
            )
            db.session.add(movement)
            
        # Recursive tüketimi başlat
        consume_recipe_materials(recipe, quantity)
        
        # Hedef ürünün stoğunu artır
        if recipe.target_product_id:
            target_product = recipe.target_product
            target_product.current_stock += quantity
            
            # Stok hareketi (Giriş)
            movement_in = StockMovement(
                product_id=target_product.id,
                movement_type='giris',
                quantity=quantity,
                source=f'{recipe.category.name if recipe.category else "Üretim Hattı"}',
                destination='Depo',
                note=f'Reçete üretimi: {recipe.name}',
                user_id=current_user.id
            )
            db.session.add(movement_in)

        db.session.commit()
        flash(f'{recipe.name} reçetesinden {quantity} adet üretim yapıldı. Alt malzemeler stoktan düşüldü.', 'success')
        
        if recipe.category:
            return redirect(url_for('production.view_category', id=recipe.category_id))
        return redirect(url_for('production.recipes'))
    
    # Eksik malzemeleri kontrol et
    missing_materials = recipe.get_missing_materials(1)
    
    return render_template('production/produce_with_recipe.html', 
                          recipe=recipe,
                          missing_materials=missing_materials)


@production_bp.route('/category/<int:id>/recipes')
@login_required
@roles_required('Genel', 'Yönetici')
def category_recipes(id):
    """Kategoriye ait reçeteleri listele"""
    category = Category.query.get_or_404(id)
    recipes = Recipe.query.filter_by(category_id=id, is_active=True).order_by(Recipe.name).all()
    return render_template('production/category_recipes.html', category=category, recipes=recipes)


@production_bp.route('/api/check-stock/<int:recipe_id>')
@login_required
@roles_required('Yönetici')
def api_check_stock(recipe_id):
    """Reçete için stok durumunu kontrol et (AJAX)"""
    recipe = Recipe.query.get_or_404(recipe_id)
    quantity = request.args.get('quantity', 1, type=float)
    
    items = []
    can_produce = True
    
    for item in recipe.items:
        required = item.quantity * quantity
        available = item.product.current_stock
        sufficient = available >= required
        
        if not sufficient:
            can_produce = False
        
        items.append({
            'product_id': item.product_id,
            'product_name': item.product.name,
            'required': required,
            'available': available,
            'sufficient': sufficient,
            'shortage': max(0, required - available)
        })
    
    return jsonify({
        'can_produce': can_produce,
        'items': items
    })
