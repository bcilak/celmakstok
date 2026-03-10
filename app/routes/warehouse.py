from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import Product, Category, Location, LocationStock, StockMovement
from app import db
from app.utils.decorators import roles_required
from sqlalchemy import func

warehouse_bp = Blueprint('warehouse', __name__)

@warehouse_bp.route('/')
@login_required
@roles_required('Genel', 'Yönetici')
def index():
    # Kritik stoklar
    critical_products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock,
        Product.minimum_stock > 0
    ).order_by(Product.current_stock).all()
    
    # Boş stoklar
    empty_products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock <= 0
    ).all()
    
    # Kategori bazlı stok özeti
    categories = Category.query.filter_by(is_active=True).all()
    category_stats = []
    for cat in categories:
        products = Product.query.filter_by(category_id=cat.id, is_active=True).all()
        total_items = len(products)
        critical_items = sum(1 for p in products if p.minimum_stock > 0 and p.current_stock < p.minimum_stock)
        empty_items = sum(1 for p in products if p.current_stock <= 0)
        total_stock_value = sum(p.current_stock * (p.unit_cost or 0) for p in products)
        category_stats.append({
            'category': cat,
            'total_items': total_items,
            'critical_items': critical_items,
            'empty_items': empty_items,
            'total_value': total_stock_value
        })
    
    # Lokasyon özeti
    locations = Location.query.filter_by(is_active=True).all()
    location_stats = []
    for loc in locations:
        stocks = LocationStock.query.filter_by(location_id=loc.id).all()
        total_products = len(stocks)
        total_quantity = sum(s.quantity for s in stocks)
        location_stats.append({
            'location': loc,
            'total_products': total_products,
            'total_quantity': total_quantity
        })
    
    # Genel istatistikler
    total_products = Product.query.filter_by(is_active=True).count()
    total_stock_value = db.session.query(
        func.sum(Product.current_stock * Product.unit_cost)
    ).filter(Product.is_active == True).scalar() or 0
    
    return render_template('warehouse/index.html',
        critical_products=critical_products,
        empty_products=empty_products,
        category_stats=category_stats,
        location_stats=location_stats,
        total_products=total_products,
        total_stock_value=total_stock_value
    )

@warehouse_bp.route('/critical')
@login_required
@roles_required('Genel', 'Yönetici')
def critical():
    """Kritik stok listesi"""
    products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock,
        Product.minimum_stock > 0
    ).order_by(Product.current_stock).all()
    
    return render_template('warehouse/critical.html', products=products)

# ==================== LOKASYON YÖNETİMİ ====================

@warehouse_bp.route('/locations')
@login_required
@roles_required('Genel', 'Yönetici')
def locations():
    """Lokasyon listesi"""
    active_locations = Location.query.filter_by(is_active=True).order_by(Location.name).all()
    inactive_locations = Location.query.filter_by(is_active=False).order_by(Location.name).all()
    
    # Her lokasyon için stok bilgileri
    location_data = []
    for loc in active_locations:
        stocks = LocationStock.query.filter_by(location_id=loc.id).all()
        total_products = len(stocks)
        total_quantity = sum(s.quantity for s in stocks if s.quantity > 0)
        product_count = sum(1 for s in stocks if s.quantity > 0)
        
        location_data.append({
            'location': loc,
            'total_products': total_products,
            'product_count': product_count,
            'total_quantity': total_quantity
        })
    
    return render_template('warehouse/locations.html',
        location_data=location_data,
        inactive_locations=inactive_locations
    )

@warehouse_bp.route('/locations/add', methods=['POST'])
@login_required
@roles_required('Yönetici')
def location_add():
    """Yeni lokasyon ekle"""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Lokasyon adı gereklidir!', 'error')
        return redirect(url_for('warehouse.locations'))
    
    # Aynı isimde lokasyon var mı kontrol et
    existing = Location.query.filter_by(name=name).first()
    if existing:
        flash(f'"{name}" adında bir lokasyon zaten mevcut!', 'error')
        return redirect(url_for('warehouse.locations'))
    
    location = Location(
        name=name,
        description=description,
        is_active=True
    )
    
    db.session.add(location)
    db.session.commit()
    
    flash(f'Lokasyon "{name}" başarıyla eklendi!', 'success')
    return redirect(url_for('warehouse.locations'))

@warehouse_bp.route('/locations/<int:id>/edit', methods=['POST'])
@login_required
@roles_required('Yönetici')
def location_edit(id):
    """Lokasyon düzenle"""
    location = Location.query.get_or_404(id)
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Lokasyon adı gereklidir!', 'error')
        return redirect(url_for('warehouse.locations'))
    
    # Başka bir lokasyonda aynı isim var mı kontrol et
    existing = Location.query.filter(Location.name == name, Location.id != id).first()
    if existing:
        flash(f'"{name}" adında başka bir lokasyon zaten mevcut!', 'error')
        return redirect(url_for('warehouse.locations'))
    
    location.name = name
    location.description = description
    
    db.session.commit()
    
    flash(f'Lokasyon "{name}" başarıyla güncellendi!', 'success')
    return redirect(url_for('warehouse.locations'))

@warehouse_bp.route('/locations/<int:id>/toggle', methods=['POST'])
@login_required
@roles_required('Yönetici')
def location_toggle(id):
    """Lokasyon aktif/pasif durumunu değiştir"""
    location = Location.query.get_or_404(id)
    location.is_active = not location.is_active
    
    db.session.commit()
    
    status = "aktif" if location.is_active else "pasif"
    flash(f'Lokasyon "{location.name}" {status} hale getirildi!', 'success')
    return redirect(url_for('warehouse.locations'))

@warehouse_bp.route('/locations/<int:id>/delete', methods=['POST'])
@login_required
@roles_required('Yönetici')
def location_delete(id):
    """Lokasyon sil"""
    location = Location.query.get_or_404(id)
    
    # Bu lokasyonda stok var mı kontrol et
    stocks = LocationStock.query.filter_by(location_id=id).filter(LocationStock.quantity > 0).all()
    if stocks:
        flash(f'"{location.name}" lokasyonunda stok bulunduğu için silinemez! Önce stokları başka lokasyona transfer edin.', 'error')
        return redirect(url_for('warehouse.locations'))
    
    # Stok hareketleri var mı kontrol et
    movements = StockMovement.query.filter(
        (StockMovement.from_location_id == id) | 
        (StockMovement.to_location_id == id)
    ).first()
    
    if movements:
        # Sadece pasif yap, silme
        location.is_active = False
        db.session.commit()
        flash(f'"{location.name}" lokasyonunda geçmiş hareketler olduğu için sadece pasif hale getirildi.', 'warning')
    else:
        # Tamamen sil
        db.session.delete(location)
        db.session.commit()
        flash(f'Lokasyon "{location.name}" başarıyla silindi!', 'success')
    
    return redirect(url_for('warehouse.locations'))

@warehouse_bp.route('/locations/<int:id>')
@login_required
@roles_required('Genel', 'Yönetici')
def location_detail(id):
    """Lokasyon detayı ve stok listesi"""
    location = Location.query.get_or_404(id)
    
    # Bu lokasyondaki tüm stoklar
    stocks = LocationStock.query.filter_by(location_id=id).join(Product).filter(
        Product.is_active == True
    ).order_by(Product.name).all()
    
    # İstatistikler
    total_products = len([s for s in stocks if s.quantity > 0])
    total_quantity = sum(s.quantity for s in stocks)
    total_value = sum(s.quantity * (s.product.unit_cost or 0) for s in stocks if s.product)
    
    # Son hareketler
    recent_movements = StockMovement.query.filter(
        (StockMovement.from_location_id == id) | 
        (StockMovement.to_location_id == id)
    ).order_by(StockMovement.date.desc()).limit(20).all()
    
    return render_template('warehouse/location_detail.html',
        location=location,
        stocks=stocks,
        total_products=total_products,
        total_quantity=total_quantity,
        total_value=total_value,
        recent_movements=recent_movements
    )
