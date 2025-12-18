from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import Product, CountSession, CountItem, StockMovement
from app import db
from datetime import datetime, date

counting_bp = Blueprint('counting', __name__)

@counting_bp.route('/')
@login_required
def index():
    sessions = CountSession.query.order_by(CountSession.created_at.desc()).all()
    return render_template('counting/index.html', sessions=sessions)

@counting_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_session():
    if request.method == 'POST':
        session_name = request.form.get('session_name')
        notes = request.form.get('notes', '')
        
        session = CountSession(
            name=session_name,
            user_id=current_user.id,
            note=notes,
            status='active'
        )
        db.session.add(session)
        db.session.commit()
        
        # Tüm aktif ürünleri sayım listesine ekle
        products = Product.query.filter_by(is_active=True).all()
        for product in products:
            item = CountItem(
                session_id=session.id,
                product_id=product.id,
                system_quantity=product.current_stock
            )
            db.session.add(item)
        
        db.session.commit()
        flash('Sayım oturumu başarıyla oluşturuldu.', 'success')
        return redirect(url_for('counting.view', id=session.id))
    
    today = date.today().strftime('%Y-%m-%d')
    return render_template('counting/new_session.html', today=today)

@counting_bp.route('/<int:id>')
@login_required
def view(id):
    session = CountSession.query.get_or_404(id)
    
    # Filtreleme
    filter_status = request.args.get('status', '')
    
    query = CountItem.query.filter_by(session_id=id)
    
    if filter_status == 'counted':
        query = query.filter_by(is_counted=True)
    elif filter_status == 'pending':
        query = query.filter_by(is_counted=False)
    elif filter_status == 'difference':
        query = query.filter(CountItem.difference != 0, CountItem.is_counted == True)
    
    items = query.join(Product).order_by(Product.name).all()
    
    # İstatistikler
    total_items = CountItem.query.filter_by(session_id=id).count()
    counted_items = CountItem.query.filter_by(session_id=id, is_counted=True).count()
    items_with_diff = CountItem.query.filter(
        CountItem.session_id == id,
        CountItem.is_counted == True,
        CountItem.difference != 0
    ).count()
    
    return render_template('counting/view.html', 
        session=session, 
        items=items,
        total_items=total_items,
        counted_items=counted_items,
        items_with_diff=items_with_diff,
        filter_status=filter_status
    )

@counting_bp.route('/<int:id>/count', methods=['GET', 'POST'])
@login_required
def count(id):
    """QR ile sayım ekranı"""
    session = CountSession.query.get_or_404(id)
    
    if session.status == 'completed':
        flash('Bu sayım oturumu tamamlanmış.', 'error')
        return redirect(url_for('counting.view', id=id))
    
    product = None
    item = None
    product_code = request.args.get('code', '')
    
    if product_code:
        # QR koddan ürün bul
        if product_code.startswith('CELMAK-'):
            parts = product_code.split('-')
            if len(parts) > 1:
                product_id = parts[1].split('|')[0]
                product = Product.query.get(int(product_id))
        else:
            product = Product.query.filter_by(code=product_code).first()
        
        if product:
            item = CountItem.query.filter_by(session_id=id, product_id=product.id).first()
    
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        counted_quantity = request.form.get('counted_quantity', type=float)
        notes = request.form.get('notes', '')
        
        item = CountItem.query.get_or_404(item_id)
        
        item.counted_quantity = counted_quantity
        item.difference = counted_quantity - item.system_quantity
        item.is_counted = True
        item.counted_by = current_user.id
        item.counted_at = datetime.utcnow()
        item.notes = notes
        
        db.session.commit()
        
        flash(f'{item.product.name} sayımı kaydedildi.', 'success')
        return redirect(url_for('counting.count', id=id))
    
    # Sayılmamış ürünler
    pending_items = CountItem.query.filter_by(
        session_id=id,
        is_counted=False
    ).join(Product).order_by(Product.name).limit(10).all()
    
    return render_template('counting/count.html', 
        session=session, 
        product=product,
        item=item,
        pending_items=pending_items
    )

@counting_bp.route('/<int:id>/item/<int:item_id>/count', methods=['POST'])
@login_required
def count_item(id, item_id):
    """Tek ürün sayımı"""
    session = CountSession.query.get_or_404(id)
    item = CountItem.query.get_or_404(item_id)
    
    counted_quantity = request.form.get('counted_quantity', type=float)
    notes = request.form.get('notes', '')
    
    item.counted_quantity = counted_quantity
    item.difference = counted_quantity - item.system_quantity
    item.is_counted = True
    item.counted_by = current_user.id
    item.counted_at = datetime.utcnow()
    item.notes = notes
    
    db.session.commit()
    
    flash(f'{item.product.name} sayımı kaydedildi.', 'success')
    return redirect(url_for('counting.view', id=id))

@counting_bp.route('/<int:id>/complete', methods=['POST'])
@login_required
def complete_session(id):
    """Sayımı tamamla"""
    session = CountSession.query.get_or_404(id)
    
    session.status = 'completed'
    session.completed_at = datetime.utcnow()
    
    db.session.commit()
    flash('Sayım oturumu tamamlandı.', 'success')
    return redirect(url_for('counting.view', id=id))

@counting_bp.route('/<int:id>/apply', methods=['POST'])
@login_required
def apply_differences(id):
    """Sayım farklarını sisteme uygula"""
    session = CountSession.query.get_or_404(id)
    
    if current_user.role not in ['admin']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('counting.view', id=id))
    
    # Farkı olan kalemleri bul
    items = CountItem.query.filter(
        CountItem.session_id == id,
        CountItem.is_counted == True,
        CountItem.difference != 0
    ).all()
    
    for item in items:
        product = item.product
        
        # Stoku güncelle
        product.current_stock = item.counted_quantity
        
        # Hareket kaydı oluştur
        if item.difference > 0:
            movement_type = 'sayim_artis'
        else:
            movement_type = 'sayim_azalis'
        
        movement = StockMovement(
            product_id=product.id,
            movement_type=movement_type,
            quantity=abs(item.difference),
            source=f'Sayım #{session.id}',
            destination='Düzeltme',
            note=f'Sayım düzeltmesi: {session.name}',
            user_id=current_user.id
        )
        db.session.add(movement)
    
    db.session.commit()
    flash(f'{len(items)} ürün için sayım farkları uygulandı.', 'success')
    return redirect(url_for('counting.view', id=id))

@counting_bp.route('/<int:id>/cancel')
@login_required
def cancel_session(id):
    """Sayımı iptal et"""
    session = CountSession.query.get_or_404(id)
    
    if current_user.role not in ['admin']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('counting.view', id=id))
    
    session.status = 'cancelled'
    db.session.commit()
    flash('Sayım oturumu iptal edildi.', 'info')
    return redirect(url_for('counting.index'))
