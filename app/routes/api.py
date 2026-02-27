from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models import Product, Category, StockMovement, CountSession, CountItem, Recipe, RecipeItem
from app import db
from sqlalchemy import func
from functools import wraps
from datetime import datetime, timedelta
from app.utils.decorators import roles_required

api_bp = Blueprint('api', __name__)

# API Key Authentication (Opsiyonel)
def require_api_key(f):
    """API Key kontrolü (opsiyonel - güvenlik için)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Header'dan API key al
        api_key = request.headers.get('X-API-Key')

        # .env'den API_KEY varsa kontrol et, yoksa login_required gibi çalış
        import os
        expected_key = os.environ.get('API_KEY')

        if expected_key:
            if not api_key or api_key != expected_key:
                return jsonify({'error': 'Geçersiz veya eksik API key'}), 401

        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/products')
@login_required
@roles_required('Genel', 'Yönetici', 'Personel')
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
@roles_required('Genel', 'Yönetici', 'Personel')
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
@roles_required('Genel', 'Yönetici', 'Personel')
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
@roles_required('Genel', 'Yönetici', 'Personel')
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
@roles_required('Yönetici')
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
@roles_required('Genel', 'Yönetici', 'Personel')
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
@roles_required('Genel', 'Yönetici')
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
@roles_required('Genel', 'Yönetici', 'Personel')
def dashboard_stats():
    """Dashboard istatistikleri API"""
    
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
@roles_required('Yönetici')
def api_count_item(session_id, item_id):
    """Sayım kalemi güncelleme API"""

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

# ================== ÜRÜN AĞACI API'LERİ ==================

@api_bp.route('/v1/products/full', methods=['GET'])
@require_api_key
def api_products_full():
    """
    Tüm Ürün Listesi (Detaylı)
    Dış uygulama entegrasyonu için tam ürün listesi
    ---
    tags:
      - Ürünler (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - name: category_id
        in: query
        type: integer
        required: false
        description: Belirli bir kategoriye ait ürünleri getir
      - name: include_inactive
        in: query
        type: string
        required: false
        description: Pasif ürünleri de dahil et ('true' veya 'false')
    responses:
      200:
        description: Başarılı ürün listesi
    """
    category_id = request.args.get('category_id', type=int)
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

    query = Product.query

    if not include_inactive:
        query = query.filter_by(is_active=True)

    if category_id:
        query = query.filter_by(category_id=category_id)

    products = query.order_by(Product.code).all()

    result = []
    for p in products:
        result.append({
            'id': p.id,
            'code': p.code,
            'name': p.name,
            'category_id': p.category_id,
            'category_name': p.category.name if p.category else None,
            'unit_type': p.unit_type,
            'current_stock': float(p.current_stock),
            'minimum_stock': float(p.minimum_stock),
            'barcode': p.barcode,
            'notes': p.notes,
            'status': p.stock_status,
            'is_active': p.is_active,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'updated_at': p.updated_at.isoformat() if p.updated_at else None
        })

    return jsonify({
        'success': True,
        'count': len(result),
        'data': result
    })


@api_bp.route('/v1/recipes', methods=['GET'])
@require_api_key
def api_recipes_list():
    """
    Tüm Reçete Listesi
    Dış uygulama entegrasyonu için reçeteler
    ---
    tags:
      - Reçeteler (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - name: category_id
        in: query
        type: integer
        required: false
      - name: include_inactive
        in: query
        type: string
        required: false
    responses:
      200:
        description: Başarılı yanıt
    """
    category_id = request.args.get('category_id', type=int)
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

    query = Recipe.query

    if not include_inactive:
        query = query.filter_by(is_active=True)

    if category_id:
        query = query.filter_by(category_id=category_id)

    recipes = query.order_by(Recipe.name).all()

    result = []
    for r in recipes:
        result.append({
            'id': r.id,
            'name': r.name,
            'category_id': r.category_id,
            'category_name': r.category.name if r.category else None,
            'model_variant': r.model_variant,
            'description': r.description,
            'is_active': r.is_active,
            'total_items': r.total_items,
            'created_at': r.created_at.isoformat() if r.created_at else None,
            'updated_at': r.updated_at.isoformat() if r.updated_at else None
        })

    return jsonify({
        'success': True,
        'count': len(result),
        'data': result
    })


@api_bp.route('/v1/recipes/<int:recipe_id>', methods=['GET'])
@require_api_key
def api_recipe_detail(recipe_id):
    """
    Reçete Detayı ve Malzeme Listesi
    Spesifik bir reçetenin içerdiği malzemeler
    ---
    tags:
      - Reçeteler (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - name: recipe_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Reçete detayları
    """
    recipe = Recipe.query.get_or_404(recipe_id)

    items = []
    for item in recipe.items:
        items.append({
            'id': item.id,
            'product_id': item.product_id,
            'product_code': item.product.code,
            'product_name': item.product.name,
            'quantity': float(item.quantity),
            'unit_type': item.product.unit_type,
            'current_stock': float(item.product.current_stock),
            'note': item.note
        })

    return jsonify({
        'success': True,
        'data': {
            'id': recipe.id,
            'name': recipe.name,
            'category_id': recipe.category_id,
            'category_name': recipe.category.name if recipe.category else None,
            'model_variant': recipe.model_variant,
            'description': recipe.description,
            'is_active': recipe.is_active,
            'items': items,
            'created_at': recipe.created_at.isoformat() if recipe.created_at else None,
            'updated_at': recipe.updated_at.isoformat() if recipe.updated_at else None
        }
    })


@api_bp.route('/v1/product-tree', methods=['GET'])
@require_api_key
def api_product_tree():
    """
    Ürün Ağacı (Hiyerarşik)
    Tüm reçeteleri ve malzemeleri hiyerarşik yapıda döndürür
    ---
    tags:
      - Ürün Ağacı (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - name: include_inactive
        in: query
        type: string
        required: false
    responses:
      200:
        description: Başarılı ağaç yapısı
    """
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

    # Tüm reçeteleri al
    query = Recipe.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    recipes = query.all()

    tree = []

    for recipe in recipes:
        # Reçete düğümü
        recipe_node = {
            'type': 'recipe',
            'id': recipe.id,
            'name': recipe.name,
            'category_id': recipe.category_id,
            'category_name': recipe.category.name if recipe.category else None,
            'model_variant': recipe.model_variant,
            'description': recipe.description,
            'is_active': recipe.is_active,
            'children': []
        }

        # Reçete malzemeleri (çocuk düğümler)
        for item in recipe.items:
            product_node = {
                'type': 'product',
                'id': item.product_id,
                'code': item.product.code,
                'name': item.product.name,
                'quantity_required': float(item.quantity),
                'unit_type': item.product.unit_type,
                'current_stock': float(item.product.current_stock),
                'minimum_stock': float(item.product.minimum_stock),
                'status': item.product.stock_status,
                'note': item.note,
                'category_id': item.product.category_id,
                'category_name': item.product.category.name if item.product.category else None
            }

            recipe_node['children'].append(product_node)

        tree.append(recipe_node)

    return jsonify({
        'success': True,
        'count': len(tree),
        'data': tree
    })


@api_bp.route('/v1/product-tree/flat', methods=['GET'])
@require_api_key
def api_product_tree_flat():
    """
    Ürün Ağacı (Düz / Graph)
    İlişkileri ID referanslarıyla döndürür
    ---
    tags:
      - Ürün Ağacı (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - name: include_inactive
        in: query
        type: string
        required: false
    responses:
      200:
        description: Nodes ve edges döner
    """
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

    # Düğümler
    nodes = []

    # Tüm reçeteler - nodes
    query = Recipe.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    recipes = query.all()

    for recipe in recipes:
        nodes.append({
            'id': f'recipe_{recipe.id}',
            'type': 'recipe',
            'data': {
                'recipe_id': recipe.id,
                'name': recipe.name,
                'category': recipe.category.name if recipe.category else None,
                'model_variant': recipe.model_variant
            }
        })

    # Tüm ürünler - nodes
    product_query = Product.query
    if not include_inactive:
        product_query = product_query.filter_by(is_active=True)
    products = product_query.all()

    for product in products:
        nodes.append({
            'id': f'product_{product.id}',
            'type': 'product',
            'data': {
                'product_id': product.id,
                'code': product.code,
                'name': product.name,
                'current_stock': float(product.current_stock),
                'unit_type': product.unit_type,
                'status': product.stock_status
            }
        })

    # Kenarlar (ilişkiler)
    edges = []

    for recipe in recipes:
        for item in recipe.items:
            edges.append({
                'source': f'recipe_{recipe.id}',
                'target': f'product_{item.product_id}',
                'quantity': float(item.quantity),
                'label': f'{item.quantity} {item.product.unit_type}'
            })

    return jsonify({
        'success': True,
        'nodes': nodes,
        'edges': edges,
        'node_count': len(nodes),
        'edge_count': len(edges)
    })


@api_bp.route('/v1/recipe/<int:recipe_id>/can-produce', methods=['GET'])
@require_api_key
def api_can_produce(recipe_id):
    """
    Üretilebilirlik Kontrolü
    Makine/Reçete için üretim yapılabilir mi kontrol et
    ---
    tags:
      - Üretim (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - name: recipe_id
        in: path
        type: integer
        required: true
      - name: quantity
        in: query
        type: integer
        required: false
    responses:
      200:
        description: Kontrol sonucu
    """
    recipe = Recipe.query.get_or_404(recipe_id)
    quantity = request.args.get('quantity', 1, type=int)

    can_produce, missing_product, available, required = recipe.can_produce(quantity)

    if can_produce:
        return jsonify({
            'success': True,
            'can_produce': True,
            'quantity': quantity,
            'message': f'{quantity} adet üretim için tüm malzemeler mevcut'
        })
    else:
        return jsonify({
            'success': True,
            'can_produce': False,
            'quantity': quantity,
            'missing_material': {
                'product_id': missing_product.id,
                'product_code': missing_product.code,
                'product_name': missing_product.name,
                'required': float(required),
                'available': float(available),
                'shortage': float(required - available),
                'unit_type': missing_product.unit_type
            },
            'message': f'Yetersiz stok: {missing_product.name}'
        })


@api_bp.route('/v1/recipe/<int:recipe_id>/missing-materials', methods=['GET'])
@require_api_key
def api_missing_materials(recipe_id):
    """
    Eksik Malzemeler
    Reçete için eksik malzemeleri listele
    ---
    tags:
      - Üretim (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - name: recipe_id
        in: path
        type: integer
        required: true
      - name: quantity
        in: query
        type: integer
        required: false
    responses:
      200:
        description: Başarılı
    """
    recipe = Recipe.query.get_or_404(recipe_id)
    quantity = request.args.get('quantity', 1, type=int)

    missing_list = recipe.get_missing_materials(quantity)

    result = []
    for item in missing_list:
        result.append({
            'product_id': item['product'].id,
            'product_code': item['product'].code,
            'product_name': item['product'].name,
            'required': float(item['required']),
            'available': float(item['available']),
            'shortage': float(item['shortage']),
            'unit_type': item['product'].unit_type
        })

    return jsonify({
        'success': True,
        'recipe_id': recipe_id,
        'recipe_name': recipe.name,
        'quantity': quantity,
        'missing_count': len(result),
        'missing_materials': result
    })


@api_bp.route('/v1/health', methods=['GET'])
def api_health():
    """API sağlık kontrolü - authentication gerektirmez"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0',
        'service': 'ÇELMAK Stok Takip API'
    })


# ================== SATIN ALMA BİRİMİ API'LERİ ==================

@api_bp.route('/v1/purchasing/critical-stock', methods=['GET'])
@require_api_key
def api_critical_stock_for_purchasing():
    """
    Satın alma birimi için kritik stok listesi
    Minimum stok seviyesinin altındaki veya biten ürünler
    """
    # Tüm aktif ürünleri getir (Artık sadece kritik değil, hepsi isteniyor)
    all_products = Product.query.filter(
        Product.is_active == True
    ).order_by(Product.name).all()

    result = []
    for p in all_products:
        # Eksik miktar hesapla (0'ın altına düşürme)
        shortage = max(0, p.minimum_stock - p.current_stock)
        
        # Lokasyon bilgisi
        locations = []
        for ls in p.location_stocks:
            if ls.quantity > 0 and getattr(ls, 'location', None):
                locations.append({
                    'location_id': ls.location.id,
                    'location_name': ls.location.name,
                    'quantity': float(ls.quantity)
                })

        # Son hareketleri al (son çıkış hızını analiz için)
        week_ago = datetime.utcnow() - timedelta(days=7)

        weekly_consumption = db.session.query(func.sum(StockMovement.quantity)).filter(
            StockMovement.product_id == p.id,
            StockMovement.movement_type == 'cikis',
            StockMovement.date >= week_ago
        ).scalar() or 0

        # Günlük ortalama tüketim
        daily_avg = weekly_consumption / 7 if weekly_consumption > 0 else 0

        # Kaç gün dayanır (stok bitişi tahmini)
        days_remaining = (p.current_stock / daily_avg) if daily_avg > 0 else 999

        result.append({
            'product_id': p.id,
            'code': p.code,
            'name': p.name,
            'category_id': p.category_id,
            'category_name': p.category.name if p.category else None,
            'current_stock': float(p.current_stock),
            'minimum_stock': float(p.minimum_stock),
            'shortage': float(shortage),
            'unit_type': p.unit_type,
            'barcode': p.barcode,
            'urgency_level': 'critical' if p.current_stock <= 0 else 'low' if shortage < p.minimum_stock * 0.3 else 'medium',
            'weekly_consumption': float(weekly_consumption),
            'daily_avg_consumption': float(daily_avg),
            'days_remaining': int(days_remaining) if days_remaining < 999 else None,
            'notes': p.notes,
            'locations': locations
        })

    return jsonify({
        'success': True,
        'count': len(result),
        'data': result,
        'generated_at': datetime.utcnow().isoformat()
    })


@api_bp.route('/v1/purchasing/critical-products', methods=['GET'])
@require_api_key
def api_critical_products():
    """
    Satın alma birimi için kritik stok listesi (alias endpoint)
    /v1/purchasing/critical-stock ile aynı veriyi döndürür
    """
    # Tüm aktif ürünleri al
    all_products = Product.query.filter(
        Product.is_active == True
    ).order_by(Product.name).all()

    result = []
    for p in all_products:
        # Eksik miktar
        shortage = max(0, p.minimum_stock - p.current_stock)
        
        # Lokasyon bilgisi
        locations = []
        for ls in p.location_stocks:
            if ls.quantity > 0 and getattr(ls, 'location', None):
                locations.append({
                    'location_id': ls.location.id,
                    'location_name': ls.location.name,
                    'quantity': float(ls.quantity)
                })
        
        # Son 30 gün tüketim
        month_ago = datetime.utcnow() - timedelta(days=30)
        
        monthly_consumption = db.session.query(func.sum(StockMovement.quantity)).filter(
            StockMovement.product_id == p.id,
            StockMovement.movement_type == 'cikis',
            StockMovement.date >= month_ago
        ).scalar() or 0
        
        # Önerilen sipariş = Eksik + 1 aylık tüketim
        suggested_order = shortage + monthly_consumption
        
        result.append({
            'id': p.id,
            'code': p.code,
            'name': p.name,
            'category': p.category.name if p.category else None,
            'current_stock': float(p.current_stock),
            'minimum_stock': float(p.minimum_stock),
            'shortage': float(shortage),
            'unit_type': p.unit_type,
            'suggested_order': float(suggested_order),
            'monthly_consumption': float(monthly_consumption),
            'locations': locations
        })

    return jsonify({
        'success': True,
        'count': len(result),
        'products': result,
        'timestamp': datetime.utcnow().isoformat()
    })


@api_bp.route('/v1/purchasing/reorder-suggestions', methods=['GET'])
@require_api_key
def api_reorder_suggestions():
    """
    Satın alma önerileri - Hangi üründen ne kadar sipariş verilmeli
    Minimum stok + güvenlik stoğu hesaplaması
    """

    # Kritik ürünleri al
    critical_products = Product.query.filter(
        Product.is_active == True,
        Product.minimum_stock > 0,
        Product.current_stock < Product.minimum_stock
    ).order_by(Product.current_stock).all()

    month_ago = datetime.utcnow() - timedelta(days=30)

    result = []
    for p in critical_products:
        # Aylık ortalama tüketim
        monthly_consumption = db.session.query(func.sum(StockMovement.quantity)).filter(
            StockMovement.product_id == p.id,
            StockMovement.movement_type == 'cikis',
            StockMovement.date >= month_ago
        ).scalar() or 0

        # Önerilen sipariş miktarı
        # = (Minimum Stok - Mevcut Stok) + Güvenlik Stoğu (1 aylık tüketim)
        suggested_order = (p.minimum_stock - p.current_stock) + monthly_consumption

        # Ekonomik sipariş miktarı (en yakın paket/koli miktarına yuvarla)
        # Örnek: 10'un katları şeklinde
        if suggested_order > 0:
            economic_order = ((suggested_order // 10) + 1) * 10
        else:
            economic_order = 0

        result.append({
            'product_id': p.id,
            'code': p.code,
            'name': p.name,
            'category_name': p.category.name if p.category else None,
            'current_stock': float(p.current_stock),
            'minimum_stock': float(p.minimum_stock),
            'shortage': float(p.minimum_stock - p.current_stock),
            'monthly_consumption': float(monthly_consumption),
            'suggested_order_quantity': float(suggested_order),
            'economic_order_quantity': float(economic_order),
            'unit_type': p.unit_type,
            'priority': 'high' if p.current_stock <= 0 else 'medium' if p.current_stock < p.minimum_stock * 0.5 else 'low'
        })

    return jsonify({
        'success': True,
        'count': len(result),
        'data': result,
        'generated_at': datetime.utcnow().isoformat()
    })


@api_bp.route('/v1/purchasing/product/<int:product_id>/details', methods=['GET'])
@require_api_key
def api_product_purchasing_details(product_id):
    """
    Belirli bir ürün için satın alma detayları
    Tüketim analizi, sipariş önerisi, tedarikçi bilgileri
    """

    product = Product.query.get_or_404(product_id)

    # Son 30 günlük hareketler
    month_ago = datetime.utcnow() - timedelta(days=30)
    movements = StockMovement.query.filter(
        StockMovement.product_id == product_id,
        StockMovement.date >= month_ago
    ).order_by(StockMovement.date.desc()).all()

    # Giriş/Çıkış toplamları
    total_in = sum(m.quantity for m in movements if m.movement_type == 'giris')
    total_out = sum(m.quantity for m in movements if m.movement_type == 'cikis')

    # Günlük ortalama tüketim
    daily_consumption = total_out / 30 if total_out > 0 else 0

    # Stok bitişi tahmini
    if daily_consumption > 0 and product.current_stock > 0:
        days_until_stockout = int(product.current_stock / daily_consumption)
    else:
        days_until_stockout = None

    # Son alım bilgisi
    last_purchase = StockMovement.query.filter(
        StockMovement.product_id == product_id,
        StockMovement.movement_type == 'giris'
    ).order_by(StockMovement.date.desc()).first()

    return jsonify({
        'success': True,
        'data': {
            'product': {
                'id': product.id,
                'code': product.code,
                'name': product.name,
                'category': product.category.name if product.category else None,
                'current_stock': float(product.current_stock),
                'minimum_stock': float(product.minimum_stock),
                'unit_type': product.unit_type,
                'barcode': product.barcode,
                'status': product.stock_status
            },
            'consumption_analysis': {
                'last_30_days_in': float(total_in),
                'last_30_days_out': float(total_out),
                'daily_avg_consumption': float(daily_consumption),
                'days_until_stockout': days_until_stockout
            },
            'purchasing_info': {
                'shortage': float(max(0, product.minimum_stock - product.current_stock)),
                'suggested_order': float(max(0, product.minimum_stock - product.current_stock + (daily_consumption * 30))),
                'last_purchase_date': last_purchase.date.isoformat() if last_purchase else None,
                'last_purchase_quantity': float(last_purchase.quantity) if last_purchase else None,
                'last_purchase_source': last_purchase.source if last_purchase else None
            },
            'recent_movements': [
                {
                    'date': m.date.isoformat(),
                    'type': m.movement_type,
                    'quantity': float(m.quantity),
                    'source': m.source,
                    'destination': m.destination
                } for m in movements[:10]  # Son 10 hareket
            ]
        }
    })


@api_bp.route('/v1/purchasing/notify', methods=['POST'])
@login_required
@roles_required('Yönetici')
def api_purchasing_notify():
    """
    Kritik stok bildirimi oluştur
    Satın alma uygulamasına webhook/notification gönderebilir
    """
    data = request.get_json()

    # Kritik ürünleri al
    critical_count = Product.query.filter(
        Product.is_active == True,
        Product.minimum_stock > 0,
        Product.current_stock < Product.minimum_stock
    ).count()

    # Burada webhook URL'e POST yapabilirsiniz
    # webhook_url = data.get('webhook_url')
    # if webhook_url:
    #     requests.post(webhook_url, json={'critical_count': critical_count})

    return jsonify({
        'success': True,
        'message': 'Bildirim gönderildi',
        'critical_product_count': critical_count,
        'timestamp': datetime.utcnow().isoformat()
    })


@api_bp.route('/v1/purchasing/product/<product_code>', methods=['GET'])
@require_api_key
def api_product_by_code(product_code):
    """
    Ürün koduna göre detaylı bilgi (satın alma için)
    """
    
    product = Product.query.filter_by(code=product_code, is_active=True).first_or_404()
    
    # Son 30 günlük hareketler
    month_ago = datetime.utcnow() - timedelta(days=30)
    movements = StockMovement.query.filter(
        StockMovement.product_id == product.id,
        StockMovement.date >= month_ago
    ).order_by(StockMovement.date.desc()).all()
    
    # Giriş/Çıkış analizi
    total_in = sum(m.quantity for m in movements if m.movement_type == 'giris')
    total_out = sum(m.quantity for m in movements if m.movement_type == 'cikis')
    daily_consumption = total_out / 30 if total_out > 0 else 0
    
    # Son satın alma
    last_purchase = StockMovement.query.filter(
        StockMovement.product_id == product.id,
        StockMovement.movement_type == 'giris'
    ).order_by(StockMovement.date.desc()).first()
    
    return jsonify({
        'success': True,
        'product': {
            'id': product.id,
            'code': product.code,
            'name': product.name,
            'category': product.category.name if product.category else None,
            'current_stock': float(product.current_stock),
            'minimum_stock': float(product.minimum_stock),
            'unit_type': product.unit_type,
            'barcode': product.barcode,
            'status': product.stock_status
        },
        'consumption_analysis': {
            'last_30_days_in': float(total_in),
            'last_30_days_out': float(total_out),
            'daily_avg_consumption': float(daily_consumption)
        },
        'purchasing_info': {
            'shortage': float(max(0, product.minimum_stock - product.current_stock)),
            'suggested_order': float(max(0, product.minimum_stock - product.current_stock + (daily_consumption * 30))),
            'last_purchase_date': last_purchase.date.isoformat() if last_purchase else None,
            'last_purchase_quantity': float(last_purchase.quantity) if last_purchase else None
        }
    })

@api_bp.route('/v1/stock/sync', methods=['POST'])
@require_api_key
def api_stock_sync():
    """
    Toplu Stok Senkronizasyonu
    Dış sistemlerden gelen verilerle stok adetlerini günceller (Sayım/Düzeltme hareketi oluşturarak)
    ---
    tags:
      - Stok (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            items:
              type: array
              items:
                type: object
                properties:
                  product_code:
                    type: string
                  stock_quantity:
                    type: number
                  note:
                    type: string
    responses:
      200:
        description: Senkronizasyon sonucu
    """
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'success': False, 'message': 'Eksik veya hatalı veri. items dizisi gereklidir.'}), 400

    items = data.get('items', [])
    results = []
    
    for item in items:
        code = item.get('product_code')
        new_quantity = item.get('stock_quantity')
        note = item.get('note', 'API Senkronizasyonu')
        
        if not code or new_quantity is None:
            results.append({'code': code, 'status': 'error', 'message': 'Eksik veri'})
            continue
            
        product = Product.query.filter_by(code=code, is_active=True).first()
        if not product:
            results.append({'code': code, 'status': 'error', 'message': 'Ürün bulunamadı'})
            continue
            
        old_quantity = product.current_stock
        difference = new_quantity - old_quantity
        
        if difference == 0:
            results.append({'code': code, 'status': 'skipped', 'message': 'Stok zaten güncel'})
            continue
            
        movement_type = 'giris' if difference > 0 else 'cikis'
        
        movement = StockMovement(
            product_id=product.id,
            movement_type=movement_type,
            quantity=abs(difference),
            source='Sistem Senkronizasyonu' if difference > 0 else 'Depo',
            destination='Depo' if difference > 0 else 'Sistem Senkronizasyonu',
            note=note,
            # Sistem kullanıcısı id'si yok, o yüzden user_id null kalabilir. 
            # API ile eklendiğini kaynak/notlardan anlayacağız.
        )
        
        product.current_stock = new_quantity
        db.session.add(movement)
        
        results.append({
            'code': code, 
            'status': 'success', 
            'old_stock': float(old_quantity), 
            'new_stock': float(new_quantity)
        })
        
    db.session.commit()
    
    return jsonify({
        'success': True,
        'processed_count': len(items),
        'results': results
    })

@api_bp.route('/v1/products/price-sync', methods=['POST'])
@require_api_key
def api_product_price_sync():
    """
    Satın Alma Fiyat Senkronizasyonu
    Dış satın alma uygulamasından gelen güncel fiyatları ürünlere işler. Gizli alanlardır.
    ---
    tags:
      - Ürünler (Entegrasyon)
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            items:
              type: array
              items:
                type: object
                properties:
                  code:
                    type: string
                  cost:
                    type: number
                  currency:
                    type: string
    responses:
      200:
        description: Fiyat senkronizasyonu sonucu
    """
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'success': False, 'message': 'Eksik veya hatalı veri. items dizisi gereklidir.'}), 400

    items = data.get('items', [])
    results = []
    
    for item in items:
        code = item.get('code')
        cost = item.get('cost')
        currency = item.get('currency', 'TRY')
        
        if not code or cost is None:
            results.append({'code': code, 'status': 'error', 'message': 'Eksik veri (code veya cost)'})
            continue
            
        product = Product.query.filter_by(code=code, is_active=True).first()
        if not product:
            results.append({'code': code, 'status': 'error', 'message': 'Ürün bulunamadı'})
            continue
            
        product.unit_cost = float(cost)
        product.currency = currency
        
        results.append({
            'code': code, 
            'status': 'success', 
            'new_cost': float(cost), 
            'currency': currency
        })
        
    db.session.commit()
    
    return jsonify({
        'success': True,
        'processed_count': len(items),
        'results': results
    })
