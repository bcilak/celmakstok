from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models import Product, Category, StockMovement, CountSession, CountItem
from app import db
from sqlalchemy import func

api_bp = Blueprint('api', __name__)

@api_bp.route('/products')
@login_required
def get_products():
    """Ürün listesi API"""
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return jsonify([{
        'id': p.id,
        'code': p.code,
        'name': p.name,
        'category': p.category.name if p.category else None,
        'unit_type': p.unit_type,
        'current_stock': p.current_stock,
        'minimum_stock': p.minimum_stock,
        'status': p.stock_status
    } for p in products])

@api_bp.route('/products/<int:id>')
@login_required
def get_product(id):
    """Tek ürün detayı API"""
    product = Product.query.get_or_404(id)
    return jsonify({
        'id': product.id,
        'code': product.code,
        'name': product.name,
        'category': product.category.name if product.category else None,
        'unit_type': product.unit_type,
        'current_stock': product.current_stock,
        'minimum_stock': product.minimum_stock,
        'total_in': product.total_in,
        'total_out': product.total_out,
        'dimensions': product.dimensions,
        'status': product.stock_status
    })

@api_bp.route('/products/search')
@login_required
def search_products():
    """Ürün arama API"""
    q = request.args.get('q', '')
    
    if len(q) < 2:
        return jsonify([])
    
    products = Product.query.filter(
        Product.is_active == True,
        db.or_(
            Product.name.ilike(f'%{q}%'),
            Product.code.ilike(f'%{q}%'),
            Product.barcode.ilike(f'%{q}%')
        )
    ).limit(20).all()
    
    return jsonify([{
        'id': p.id,
        'code': p.code,
        'name': p.name,
        'unit_type': p.unit_type,
        'current_stock': p.current_stock
    } for p in products])

@api_bp.route('/products/by-qr/<code>')
@login_required
def get_product_by_qr(code):
    """QR koddan ürün bul"""
    product = None
    
    if code.startswith('CELMAK-'):
        parts = code.split('-')
        if len(parts) > 1:
            product_id = parts[1].split('|')[0]
            product = Product.query.get(int(product_id))
    else:
        product = Product.query.filter_by(code=code).first()
        if not product:
            product = Product.query.filter_by(barcode=code).first()
    
    if not product:
        return jsonify({'error': 'Ürün bulunamadı'}), 404
    
    return jsonify({
        'id': product.id,
        'code': product.code,
        'name': product.name,
        'unit_type': product.unit_type,
        'current_stock': product.current_stock,
        'minimum_stock': product.minimum_stock
    })

@api_bp.route('/stock/quick', methods=['POST'])
@login_required
def quick_stock_movement():
    """Hızlı stok hareketi API"""
    data = request.get_json()
    
    product_id = data.get('product_id')
    quantity = data.get('quantity', 0)
    direction = data.get('direction')  # in veya out
    
    if not product_id or not quantity or not direction:
        return jsonify({'error': 'Eksik parametreler'}), 400
    
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Ürün bulunamadı'}), 404
    
    if quantity <= 0:
        return jsonify({'error': 'Miktar sıfırdan büyük olmalı'}), 400
    
    if direction == 'out' and quantity > product.current_stock:
        return jsonify({'error': 'Yetersiz stok'}), 400
    
    if direction == 'in':
        product.current_stock += quantity
        movement_type = 'giris'
    else:
        product.current_stock -= quantity
        movement_type = 'cikis'
    
    movement = StockMovement(
        product_id=product_id,
        movement_type=movement_type,
        quantity=quantity,
        note='API ile hızlı hareket',
        user_id=current_user.id
    )
    db.session.add(movement)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'product': product.name,
        'new_stock': product.current_stock,
        'movement_id': movement.id
    })

@api_bp.route('/categories')
@login_required
def get_categories():
    """Kategori listesi API"""
    categories = Category.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'code': c.code,
        'unit': c.unit,
        'product_count': c.products.count()
    } for c in categories])

@api_bp.route('/production-lines')
@login_required
def get_production_lines():
    """Üretim hatları API (Kategoriler)"""
    lines = Category.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': l.id,
        'code': l.code,
        'name': l.name,
        'unit': l.unit
    } for l in lines])

@api_bp.route('/dashboard/stats')
@login_required
def dashboard_stats():
    """Dashboard istatistikleri API"""
    from datetime import datetime, timedelta
    
    total_products = Product.query.filter_by(is_active=True).count()
    
    critical_count = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock,
        Product.minimum_stock > 0
    ).count()
    
    today = datetime.utcnow().date()
    today_movements = StockMovement.query.filter(
        func.date(StockMovement.date) == today
    ).count()
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_in = db.session.query(func.sum(StockMovement.quantity)).filter(
        StockMovement.date >= week_ago,
        StockMovement.movement_type == 'giris'
    ).scalar() or 0
    
    week_out = db.session.query(func.sum(StockMovement.quantity)).filter(
        StockMovement.date >= week_ago,
        StockMovement.movement_type == 'cikis'
    ).scalar() or 0
    
    return jsonify({
        'total_products': total_products,
        'critical_count': critical_count,
        'today_movements': today_movements,
        'week_in': week_in,
        'week_out': week_out
    })

@api_bp.route('/counting/<int:session_id>/item/<int:item_id>', methods=['POST'])
@login_required
def api_count_item(session_id, item_id):
    """Sayım kalemi güncelleme API"""
    from datetime import datetime
    
    data = request.get_json()
    counted_quantity = data.get('counted_quantity', 0)
    notes = data.get('notes', '')
    
    item = CountItem.query.get_or_404(item_id)
    
    if item.session_id != session_id:
        return jsonify({'error': 'Geçersiz oturum'}), 400
    
    item.counted_quantity = counted_quantity
    item.difference = counted_quantity - item.system_quantity
    item.is_counted = True
    item.counted_by = current_user.id
    item.counted_at = datetime.utcnow()
    item.notes = notes
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'item_id': item.id,
        'difference': item.difference
    })
