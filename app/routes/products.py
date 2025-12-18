from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from app.models import Product, Category, StockMovement
from app import db
from app.utils.qr_generator import generate_qr_code
import io

products_bp = Blueprint('products', __name__)

@products_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    query = Product.query.filter_by(is_active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search}%'),
                Product.code.ilike(f'%{search}%')
            )
        )
    
    if status == 'critical':
        query = query.filter(Product.current_stock < Product.minimum_stock)
    elif status == 'empty':
        query = query.filter(Product.current_stock <= 0)
    
    products = query.order_by(Product.name).paginate(page=page, per_page=25)
    categories = Category.query.all()
    
    return render_template('products/index.html', 
        products=products, 
        categories=categories,
        selected_category=category_id,
        search=search,
        status=status
    )

@products_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        category_id = request.form.get('category_id', type=int)
        unit_type = request.form.get('unit_type', 'adet')
        minimum_stock = request.form.get('minimum_stock', 0, type=float)
        current_stock = request.form.get('current_stock', 0, type=float)
        dimensions = request.form.get('dimensions', '')
        barcode = request.form.get('barcode', '')
        notes = request.form.get('notes', '')
        
        if Product.query.filter_by(code=code).first():
            flash('Bu ürün kodu zaten kullanılıyor.', 'error')
        else:
            product = Product(
                code=code,
                name=name,
                category_id=category_id,
                unit_type=unit_type,
                minimum_stock=minimum_stock,
                current_stock=current_stock,
                total_in=current_stock,
                dimensions=dimensions,
                barcode=barcode,
                notes=notes
            )
            db.session.add(product)
            db.session.commit()
            
            # QR kod oluştur
            product.qr_code = f"CELMAK-{product.id}"
            db.session.commit()
            
            # Başlangıç stoğu için hareket kaydı
            if current_stock > 0:
                movement = StockMovement(
                    product_id=product.id,
                    movement_type='purchase',
                    direction='in',
                    quantity=current_stock,
                    stock_before=0,
                    stock_after=current_stock,
                    reference_no='AÇILIŞ',
                    notes='Açılış stoğu',
                    user_id=current_user.id
                )
                db.session.add(movement)
                db.session.commit()
            
            flash('Ürün başarıyla eklendi.', 'success')
            return redirect(url_for('products.view', id=product.id))
    
    categories = Category.query.all()
    return render_template('products/add.html', categories=categories)

@products_bp.route('/<int:id>')
@login_required
def view(id):
    product = Product.query.get_or_404(id)
    movements = StockMovement.query.filter_by(product_id=id).order_by(
        StockMovement.date.desc()
    ).limit(20).all()
    
    return render_template('products/view.html', product=product, movements=movements)

@products_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.category_id = request.form.get('category_id', type=int)
        product.unit_type = request.form.get('unit_type', 'adet')
        product.minimum_stock = request.form.get('minimum_stock', 0, type=float)
        product.dimensions = request.form.get('dimensions', '')
        product.barcode = request.form.get('barcode', '')
        product.notes = request.form.get('notes', '')
        
        db.session.commit()
        flash('Ürün başarıyla güncellendi.', 'success')
        return redirect(url_for('products.view', id=product.id))
    
    categories = Category.query.all()
    return render_template('products/edit.html', product=product, categories=categories)

@products_bp.route('/<int:id>/delete')
@login_required
def delete(id):
    if current_user.role not in ['admin']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('products.index'))
    
    product = Product.query.get_or_404(id)
    product.is_active = False
    db.session.commit()
    flash('Ürün başarıyla silindi.', 'success')
    return redirect(url_for('products.index'))

@products_bp.route('/<int:id>/qr')
@login_required
def qr_code(id):
    product = Product.query.get_or_404(id)
    
    # QR kod oluştur
    qr_data = f"CELMAK-{product.id}|{product.code}|{product.name}"
    img_io = generate_qr_code(qr_data)
    
    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=False,
        download_name=f'qr_{product.code}.png'
    )

@products_bp.route('/<int:id>/qr/download')
@login_required
def download_qr(id):
    product = Product.query.get_or_404(id)
    
    qr_data = f"CELMAK-{product.id}|{product.code}|{product.name}"
    img_io = generate_qr_code(qr_data)
    
    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'qr_{product.code}.png'
    )

@products_bp.route('/categories')
@login_required
def categories():
    categories = Category.query.all()
    return render_template('products/categories.html', categories=categories)

@products_bp.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    name = request.form.get('name')
    description = request.form.get('description', '')
    is_production_line = request.form.get('is_production_line') == 'on'
    
    if Category.query.filter_by(name=name).first():
        flash('Bu kategori adı zaten kullanılıyor.', 'error')
    else:
        category = Category(name=name, description=description, is_production_line=is_production_line)
        db.session.add(category)
        db.session.commit()
        flash('Kategori başarıyla eklendi.', 'success')
    
    return redirect(url_for('products.categories'))

@products_bp.route('/categories/<int:id>/delete')
@login_required
def delete_category(id):
    if current_user.role != 'admin':
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('products.categories'))
    
    category = Category.query.get_or_404(id)
    if category.products.count() > 0:
        flash('Bu kategoride ürünler var, silinemez.', 'error')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Kategori başarıyla silindi.', 'success')
    
    return redirect(url_for('products.categories'))
