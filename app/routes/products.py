from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from app.models import Product, Category, StockMovement
from app import db
from app.utils.qr_generator import generate_qr_code
from app.utils.excel_utils import (
    create_product_template,
    parse_product_excel,
    export_products_to_excel
)
from datetime import datetime
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

# Excel Import/Export Routes

@products_bp.route('/import')
@login_required
def import_page():
    """Excel import sayfası"""
    if current_user.role not in ['admin', 'yonetici']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('products.index'))
    
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template('products/import.html', categories=categories)


@products_bp.route('/import/template')
@login_required
def download_template():
    """Excel şablonunu indir"""
    template = create_product_template()
    
    return send_file(
        template,
        as_attachment=True,
        download_name=f'urun_import_sablonu_{datetime.now().strftime("%Y%m%d")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@products_bp.route('/import/upload', methods=['POST'])
@login_required
def upload_import():
    """Excel dosyasını yükle ve import et"""
    if current_user.role not in ['admin', 'yonetici']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('products.index'))
    
    if 'file' not in request.files:
        flash('Dosya seçilmedi.', 'error')
        return redirect(url_for('products.import_page'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('Dosya seçilmedi.', 'error')
        return redirect(url_for('products.import_page'))
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Sadece Excel dosyaları yükleyebilirsiniz (.xlsx, .xls)', 'error')
        return redirect(url_for('products.import_page'))
    
    try:
        # Excel dosyasını parse et
        success_list, error_list = parse_product_excel(file)
        
        if not success_list and error_list:
            flash(f'Dosya okunamadı: {error_list[0]["error"]}', 'error')
            return redirect(url_for('products.import_page'))
        
        # Ürünleri ekle
        added_count = 0
        updated_count = 0
        skipped_count = 0
        
        for product_data in success_list:
            # Kategori kontrolü
            category = Category.query.get(product_data['category_id'])
            if not category:
                error_list.append({
                    'row': 'N/A',
                    'error': f'Kategori bulunamadı: {product_data["category_id"]} (Ürün: {product_data["code"]})'
                })
                skipped_count += 1
                continue
            
            # Mevcut ürün kontrolü
            existing_product = Product.query.filter_by(code=product_data['code']).first()
            
            if existing_product:
                # Güncelle
                existing_product.name = product_data['name']
                existing_product.category_id = product_data['category_id']
                existing_product.unit_type = product_data['unit_type']
                existing_product.current_stock = product_data['current_stock']
                existing_product.minimum_stock = product_data['minimum_stock']
                existing_product.barcode = product_data['barcode']
                existing_product.notes = product_data['notes']
                updated_count += 1
            else:
                # Yeni ekle
                new_product = Product(
                    code=product_data['code'],
                    name=product_data['name'],
                    category_id=product_data['category_id'],
                    unit_type=product_data['unit_type'],
                    current_stock=product_data['current_stock'],
                    minimum_stock=product_data['minimum_stock'],
                    barcode=product_data['barcode'],
                    notes=product_data['notes']
                )
                db.session.add(new_product)
                added_count += 1
        
        db.session.commit()
        
        # Sonuç mesajı
        messages = []
        if added_count > 0:
            messages.append(f'{added_count} ürün eklendi')
        if updated_count > 0:
            messages.append(f'{updated_count} ürün güncellendi')
        if skipped_count > 0:
            messages.append(f'{skipped_count} ürün atlandı')
        if error_list:
            messages.append(f'{len(error_list)} hata')
        
        if added_count > 0 or updated_count > 0:
            flash(f'İşlem tamamlandı: {", ".join(messages)}', 'success')
        else:
            flash(f'İşlem tamamlandı ancak hiç ürün eklenmedi/güncellenmedi.', 'warning')
        
        if error_list:
            for error in error_list[:5]:  # İlk 5 hatayı göster
                flash(f'Satır {error["row"]}: {error["error"]}', 'error')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Import sırasında hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('products.import_page'))


@products_bp.route('/export')
@login_required
def export_products():
    """Ürünleri Excel'e aktar"""
    category_id = request.args.get('category', type=int)
    search = request.args.get('search', '')
    
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
    
    products = query.order_by(Product.name).all()
    
    if not products:
        flash('Dışa aktarılacak ürün bulunamadı.', 'warning')
        return redirect(url_for('products.index'))
    
    excel_file = export_products_to_excel(products)
    
    filename = f'urunler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    return send_file(
        excel_file,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
