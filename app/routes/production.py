from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import Category, StockMovement, Product, Recipe, RecipeItem, ProductionRecord, ProductionConsumption
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta

production_bp = Blueprint('production', __name__)

@production_bp.route('/')
@login_required
def index():
    """Kategorileri üretim hatları olarak listele"""
    categories = Category.query.order_by(Category.name).all()
    
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
def view(id):
    """Kategori görünümüne yönlendir"""
    category = Category.query.get_or_404(id)
    return redirect(url_for('production.view_category', id=category.id))

@production_bp.route('/category/<int:id>/consume', methods=['GET', 'POST'])
@login_required
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
def add_line():
    """Yeni kategori/hat ekle"""
    if current_user.role != 'admin':
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('production.index'))
    
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
def edit_line(id):
    """Kategori/hat düzenle"""
    if current_user.role != 'admin':
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('production.index'))
    
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
def toggle_line(id):
    """Kategori/hat aktif/pasif durumu değiştir"""
    if current_user.role != 'admin':
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('production.index'))
    
    category = Category.query.get_or_404(id)
    category.is_active = not category.is_active
    db.session.commit()
    
    status = 'aktif' if category.is_active else 'devre dışı'
    flash(f'{category.name} {status} yapıldı.', 'success')
    return redirect(url_for('production.index'))


@production_bp.route('/lines/<int:id>/delete', methods=['POST'])
@login_required
def delete_line(id):
    """Üretim hattı/kategori sil"""
    if current_user.role != 'admin':
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('production.index'))
    
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
def recipes():
    """Tüm reçeteleri listele"""
    recipes = Recipe.query.order_by(Recipe.name).all()
    return render_template('production/recipes.html', recipes=recipes)


@production_bp.route('/recipes/add', methods=['GET', 'POST'])
@login_required
def add_recipe():
    """Yeni reçete ekle"""
    if request.method == 'POST':
        name = request.form.get('name')
        category_id = request.form.get('category_id', type=int)
        model_variant = request.form.get('model_variant', '')
        description = request.form.get('description', '')
        
        if not name:
            flash('Reçete adı gereklidir.', 'error')
        else:
            recipe = Recipe(
                name=name,
                category_id=category_id,
                model_variant=model_variant if model_variant else None,
                description=description
            )
            db.session.add(recipe)
            db.session.commit()
            flash('Reçete başarıyla oluşturuldu. Şimdi malzemeleri ekleyebilirsiniz.', 'success')
            return redirect(url_for('production.edit_recipe', id=recipe.id))
    
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template('production/add_recipe.html', categories=categories)


@production_bp.route('/recipes/<int:id>')
@login_required
def view_recipe(id):
    """Reçete detayını görüntüle"""
    recipe = Recipe.query.get_or_404(id)
    return render_template('production/view_recipe.html', recipe=recipe)


@production_bp.route('/recipes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe(id):
    """Reçete düzenle ve malzeme ekle/çıkar"""
    recipe = Recipe.query.get_or_404(id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_info':
            recipe.name = request.form.get('name')
            recipe.category_id = request.form.get('category_id', type=int)
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
    return render_template('production/edit_recipe.html', 
                          recipe=recipe, 
                          categories=categories,
                          products=products)


@production_bp.route('/recipes/<int:id>/delete', methods=['POST'])
@login_required
def delete_recipe(id):
    """Reçete sil"""
    if current_user.role != 'admin':
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('production.recipes'))
    
    recipe = Recipe.query.get_or_404(id)
    db.session.delete(recipe)
    db.session.commit()
    flash('Reçete silindi.', 'success')
    return redirect(url_for('production.recipes'))


@production_bp.route('/recipes/<int:id>/produce', methods=['GET', 'POST'])
@login_required
def produce_with_recipe(id):
    """Reçeteye göre üretim yap ve malzemeleri toplu tüket"""
    recipe = Recipe.query.get_or_404(id)
    
    if request.method == 'POST':
        quantity = request.form.get('quantity', type=float, default=1)
        note = request.form.get('note', '')
        
        if quantity <= 0:
            flash('Üretim miktarı sıfırdan büyük olmalıdır.', 'error')
            return redirect(url_for('production.produce_with_recipe', id=id))
        
        # Stok kontrolü
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
        
        # Malzemeleri tüket
        for item in recipe.items:
            consume_qty = item.quantity * quantity
            item.product.current_stock -= consume_qty
            
            # Tüketim detayı
            consumption = ProductionConsumption(
                production_id=production.id,
                product_id=item.product_id,
                quantity=consume_qty
            )
            db.session.add(consumption)
            
            # Stok hareketi
            movement = StockMovement(
                product_id=item.product_id,
                movement_type='cikis',
                quantity=consume_qty,
                source='Depo',
                destination=f'{recipe.category.name if recipe.category else "Üretim"} - {recipe.name}',
                note=f'Reçete üretimi: {quantity} adet',
                user_id=current_user.id
            )
            db.session.add(movement)
        
        db.session.commit()
        flash(f'{recipe.name} reçetesinden {quantity} adet üretim yapıldı. Tüm malzemeler stoktan düşüldü.', 'success')
        
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
def category_recipes(id):
    """Kategoriye ait reçeteleri listele"""
    category = Category.query.get_or_404(id)
    recipes = Recipe.query.filter_by(category_id=id, is_active=True).order_by(Recipe.name).all()
    return render_template('production/category_recipes.html', category=category, recipes=recipes)


@production_bp.route('/api/check-stock/<int:recipe_id>')
@login_required
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
