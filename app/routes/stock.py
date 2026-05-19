from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import Product, StockMovement, Category, Location, LocationStock, ProductionRecord
from app import db
from datetime import datetime, date
import json
from app.utils.decorators import roles_required

stock_bp = Blueprint('stock', __name__)


def _product_payload(product):
    return {
        'id': product.id,
        'code': product.code or '',
        'name': product.name or '',
        'stock': float(product.current_stock or 0),
        'unit': product.unit_type or 'adet',
        'type': product.type or '',
    }

@stock_bp.route('/')
@login_required
@roles_required('Genel', 'Yönetici')
def index():
    page = request.args.get('page', 1, type=int)
    movement_type = request.args.get('type', '')
    product_id = request.args.get('product', type=int)
    category_id = request.args.get('category', type=int)
    
    query = StockMovement.query
    
    if movement_type:
        query = query.filter_by(movement_type=movement_type)
    if product_id:
        query = query.filter_by(product_id=product_id)
    if category_id:
        category = Category.query.get(category_id)
        if category:
            query = query.filter(StockMovement.destination == category.name)
    
    movements = query.order_by(StockMovement.date.desc()).paginate(page=page, per_page=50)
    
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    categories = Category.query.filter_by(is_active=True).all()
    
    return render_template('stock/index.html', 
        movements=movements, 
        products=products,
        categories=categories,
        selected_type=movement_type,
        selected_product=product_id,
        selected_category=category_id
    )

@stock_bp.route('/in', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici', 'Personel')
def stock_in():
    """Stok girişi"""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', type=float)
        movement_type = request.form.get('movement_type', 'satin_alma')
        notes = request.form.get('notes', '')
        location_id = request.form.get('location_id', type=int)
        
        product = Product.query.get_or_404(product_id)
        
        if quantity <= 0:
            flash('Miktar sıfırdan büyük olmalıdır.', 'error')
        elif not location_id:
            flash('Lütfen giriş yapılacak lokasyonu seçin.', 'error')
        else:
            product.current_stock += quantity
            
            # Lokasyon stoğunu güncelle
            from app.models import LocationStock
            loc_stock = LocationStock.query.filter_by(location_id=location_id, product_id=product_id).first()
            if not loc_stock:
                loc_stock = LocationStock(location_id=location_id, product_id=product_id, quantity=0)
                db.session.add(loc_stock)
            loc_stock.quantity += quantity
            
            # Kaynak belirle
            source_map = {
                'satin_alma': 'Tedarikçi',
                'iade': 'Hatlardan İade',
                'uretimden_donen': 'Üretimden Dönen',
                'sayim_fazlasi': 'Sayım Fazlası',
                'diger': 'Diğer'
            }
            source = source_map.get(movement_type, 'Tedarikçi')
            
            movement = StockMovement(
                product_id=product_id,
                movement_type='giris',
                quantity=quantity,
                source=source,
                destination='Depo',
                to_location_id=location_id,
                note=notes,
                user_id=current_user.id
            )
            db.session.add(movement)
            db.session.commit()
            
            flash(f'{product.name} için {quantity} {product.unit_type} giriş yapıldı.', 'success')
            return redirect(url_for('stock.index'))
    
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
    # URL'den gelen ürün ID'si
    selected_product_id = request.args.get('product', type=int)
    selected_product = None
    if selected_product_id:
        selected_product = Product.query.get(selected_product_id)
    
    # Giriş türleri
    movement_types = [
        ('satin_alma', 'Satın Alma'),
        ('iade', 'Hatlardan İade'),
        ('uretimden_donen', 'Üretimden Dönen'),
        ('sayim_fazlasi', 'Sayım Fazlası'),
        ('diger', 'Diğer'),
    ]
    
    from app.models import Location
    locations = Location.query.filter_by(is_active=True).all()
    
    return render_template('stock/stock_in.html', products=products, movement_types=movement_types, selected_product=selected_product, locations=locations)

@stock_bp.route('/out', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici', 'Personel')
def stock_out():
    """Stok çıkışı"""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', type=float)
        movement_type = request.form.get('movement_type', 'cikis')
        category_id = request.form.get('category_id', type=int)
        location_id = request.form.get('location_id', type=int)
        notes = request.form.get('notes', '')
        
        product = Product.query.get_or_404(product_id)
        
        if quantity <= 0:
            flash('Miktar sıfırdan büyük olmalıdır.', 'error')
        elif not location_id:
            flash('Lütfen çıkış yapılacak lokasyonu seçin.', 'error')
        else:
            from app.models import LocationStock
            loc_stock = LocationStock.query.filter_by(location_id=location_id, product_id=product_id).first()
            
            if not loc_stock or loc_stock.quantity < quantity:
                available = loc_stock.quantity if loc_stock else 0
                flash(f'Seçili lokasyonda yetersiz stok! Mevcut: {available} {product.unit_type}', 'error')
            elif quantity > product.current_stock:
                flash(f'Yetersiz toplam stok! Mevcut: {product.current_stock} {product.unit_type}', 'error')
            else:
                product.current_stock -= quantity
                loc_stock.quantity -= quantity
                
                destination = 'Dış'
                if category_id:
                    category = Category.query.get(category_id)
                    if category:
                        destination = category.name
                
                movement = StockMovement(
                    product_id=product_id,
                    movement_type=movement_type,
                    quantity=quantity,
                    source='Depo',
                    destination=destination,
                    from_location_id=location_id,
                    note=notes,
                    user_id=current_user.id
                )
                db.session.add(movement)
                db.session.commit()
                
                flash(f'{product.name} için {quantity} {product.unit_type} çıkış yapıldı.', 'success')
                return redirect(url_for('stock.index'))
    
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    categories = Category.query.filter_by(is_active=True).all()
    
    # URL'den gelen ürün ID'si
    selected_product_id = request.args.get('product', type=int)
    selected_product = None
    if selected_product_id:
        selected_product = Product.query.get(selected_product_id)
    
    movement_types = [
        ('cikis', 'Üretimde Kullanım'),
        ('transfer', 'Hatlara Sevk'),
        ('fire', 'Fire'),
    ]
    
    from app.models import Location
    locations = Location.query.filter_by(is_active=True).all()
    
    return render_template('stock/stock_out.html', 
        products=products, 
        categories=categories,
        movement_types=movement_types,
        selected_product=selected_product,
        locations=locations
    )

@stock_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def transfer():
    """Hatlar arası transfer"""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', type=float)
        from_category_id = request.form.get('from_category_id', type=int)
        to_category_id = request.form.get('to_category_id', type=int)
        notes = request.form.get('notes', '')
        
        product = Product.query.get_or_404(product_id)
        
        if quantity <= 0:
            flash('Miktar sıfırdan büyük olmalıdır.', 'error')
        elif from_category_id == to_category_id:
            flash('Kaynak ve hedef hat aynı olamaz.', 'error')
        else:
            from_cat = Category.query.get(from_category_id)
            to_cat = Category.query.get(to_category_id)
            
            # Transfer kaydı
            movement = StockMovement(
                product_id=product_id,
                movement_type='transfer',
                quantity=quantity,
                source=from_cat.name if from_cat else 'Depo',
                destination=to_cat.name if to_cat else 'Depo',
                note=f'Transfer: {notes}',
                user_id=current_user.id
            )
            
            db.session.add(movement)
            db.session.commit()
            
            flash(f'{product.name} için transfer tamamlandı.', 'success')
            return redirect(url_for('stock.index'))
    
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    categories = Category.query.filter_by(is_active=True).all()
    
    return render_template('stock/transfer.html', products=products, categories=categories)

@stock_bp.route('/quick', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def quick_movement():
    """Hızlı stok hareketi"""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', type=float)
        direction = request.form.get('direction')
        
        product = Product.query.get_or_404(product_id)
        
        if quantity <= 0:
            flash('Miktar sıfırdan büyük olmalıdır.', 'error')
        elif direction == 'out' and quantity > product.current_stock:
            flash(f'Yetersiz stok! Mevcut: {product.current_stock} {product.unit_type}', 'error')
        else:
            if direction == 'in':
                product.current_stock += quantity
                movement_type = 'giris'
                source = 'Tedarikçi'
                destination = 'Depo'
            else:
                product.current_stock -= quantity
                movement_type = 'cikis'
                source = 'Depo'
                destination = 'Üretim'
            
            movement = StockMovement(
                product_id=product_id,
                movement_type=movement_type,
                quantity=quantity,
                source=source,
                destination=destination,
                note='Hızlı hareket',
                user_id=current_user.id
            )
            db.session.add(movement)
            db.session.commit()
            
            action = 'giriş' if direction == 'in' else 'çıkış'
            flash(f'{product.name} için {quantity} {product.unit_type} {action} yapıldı.', 'success')
            return redirect(url_for('stock.quick_movement'))
    
    # Tüm aktif ürünler (JavaScript için)
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
    # Ürünleri JSON formatında hazırla
    products_json = json.dumps([{
        'id': p.id,
        'code': p.code or '',
        'name': p.name or '',
        'stock': p.current_stock or 0,
        'min': p.minimum_stock or 0,
        'unit': p.unit_type or 'Adet'
    } for p in products], ensure_ascii=False)
    
    # Bugünkü son hareketler
    today = date.today()
    recent_movements = StockMovement.query.filter(
        db.func.date(StockMovement.date) == today
    ).order_by(StockMovement.date.desc()).limit(10).all()
    
    return render_template('stock/quick.html', products=products, products_json=products_json, recent_movements=recent_movements)


@stock_bp.route('/bulk-entry', methods=['GET', 'POST'])
@login_required
@roles_required('Genel', 'Yönetici', 'Personel')
def bulk_entry():
    """Uretim ve sevkiyat icin toplu stok giris/cikis ekrani."""
    if request.method == 'POST':
        operation = request.form.get('operation', 'production')
        location_id = request.form.get('location_id', type=int)
        note = (request.form.get('note') or '').strip()
        raw_items = request.form.get('items_json') or '[]'

        try:
            items = json.loads(raw_items)
        except json.JSONDecodeError:
            items = []

        if operation not in ['production', 'shipment']:
            flash('Islem tipi gecersiz.', 'error')
            return redirect(url_for('stock.bulk_entry'))
        if not isinstance(items, list) or not items:
            flash('En az bir urun satiri eklemelisin.', 'error')
            return redirect(url_for('stock.bulk_entry'))

        location = Location.query.get(location_id) if location_id else None
        if location_id and (not location or not location.is_active):
            flash('Secilen lokasyon bulunamadi.', 'error')
            return redirect(url_for('stock.bulk_entry'))

        valid_rows = []
        errors = []
        for index, item in enumerate(items, start=1):
            try:
                product_id = int(item.get('product_id'))
                quantity = float(item.get('quantity'))
            except (TypeError, ValueError):
                errors.append(f'{index}. satirda urun veya miktar gecersiz.')
                continue

            if quantity <= 0:
                errors.append(f'{index}. satirda miktar sifirdan buyuk olmali.')
                continue

            product = Product.query.filter_by(id=product_id, is_active=True).first()
            if not product:
                errors.append(f'{index}. satirdaki urun bulunamadi.')
                continue

            loc_stock = None
            if location:
                loc_stock = LocationStock.query.filter_by(location_id=location.id, product_id=product.id).first()
            available_location = float(loc_stock.quantity or 0) if loc_stock else 0
            available_total = float(product.current_stock or 0)
            if operation == 'shipment' and quantity > available_total:
                errors.append(
                    f'{product.code} - {product.name}: toplam stok yetersiz '
                    f'(toplam {available_total:g}).'
                )
                continue
            if operation == 'shipment' and location and quantity > available_location:
                errors.append(
                    f'{product.code} - {product.name}: stok yetersiz '
                    f'(lokasyon {available_location:g}, toplam {available_total:g}).'
                )
                continue

            valid_rows.append((product, loc_stock, quantity))

        if errors:
            for message in errors[:8]:
                flash(message, 'error')
            if len(errors) > 8:
                flash(f'{len(errors) - 8} hata daha var.', 'error')
            return redirect(url_for('stock.bulk_entry'))

        movement_type = 'giris' if operation == 'production' else 'cikis'
        source = 'Uretim' if operation == 'production' else (location.name if location else 'Genel Stok')
        destination = (location.name if location else 'Genel Stok') if operation == 'production' else 'Sevkiyat'
        total_quantity = 0

        for product, loc_stock, quantity in valid_rows:
            if operation == 'production':
                product.current_stock = float(product.current_stock or 0) + quantity
                if location and not loc_stock:
                    loc_stock = LocationStock(location_id=location.id, product_id=product.id, quantity=0)
                    db.session.add(loc_stock)
                if loc_stock:
                    loc_stock.quantity = float(loc_stock.quantity or 0) + quantity
                movement = StockMovement(
                    product_id=product.id,
                    movement_type=movement_type,
                    quantity=quantity,
                    source=source,
                    destination=destination,
                    to_location_id=location.id if location else None,
                    note=note or 'Toplu uretim girisi',
                    user_id=current_user.id
                )
                production = ProductionRecord(
                    product_id=product.id,
                    quantity=quantity,
                    user_id=current_user.id,
                    note=note or 'Toplu uretim girisi'
                )
                db.session.add(production)
            else:
                product.current_stock = float(product.current_stock or 0) - quantity
                if loc_stock:
                    loc_stock.quantity = float(loc_stock.quantity or 0) - quantity
                movement = StockMovement(
                    product_id=product.id,
                    movement_type=movement_type,
                    quantity=quantity,
                    source=source,
                    destination=destination,
                    from_location_id=location.id if location else None,
                    note=note or 'Toplu sevkiyat cikisi',
                    user_id=current_user.id
                )
            db.session.add(movement)
            total_quantity += quantity

        db.session.commit()
        label = 'uretim girisi' if operation == 'production' else 'sevkiyat cikisi'
        flash(f'{len(valid_rows)} satir kaydedildi, toplam {total_quantity:g} miktar {label} islendi.', 'success')
        return redirect(url_for('stock.bulk_entry'))

    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    locations = Location.query.filter_by(is_active=True).order_by(Location.name).all()
    recent_movements = StockMovement.query.order_by(StockMovement.date.desc()).limit(12).all()
    products_json = json.dumps([_product_payload(product) for product in products], ensure_ascii=False)

    return render_template(
        'stock/bulk_entry.html',
        products=products,
        products_json=products_json,
        locations=locations,
        recent_movements=recent_movements
    )


@stock_bp.route('/api/search-products')
@login_required
@roles_required('Genel', 'Yönetici')
def search_products():
    """Ürün arama API'si"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    products = Product.query.filter(
        Product.is_active == True,
        Product.name.ilike(f'%{query}%')
    ).order_by(Product.name).limit(20).all()
    
    result = []
    for p in products:
        category_name = p.category.name if p.category else 'Kategori Yok'
        result.append({
            'id': p.id,
            'name': p.name,
            'code': p.code or '',
            'current_stock': p.current_stock,
            'minimum_stock': p.minimum_stock,
            'unit_type': p.unit_type,
            'category': category_name
        })
    
    return jsonify(result)
