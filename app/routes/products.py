from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from app.models import Product, Category, StockMovement
from app import db
from app.utils.qr_generator import generate_qr_code, generate_celmak_label, generate_celmak_label_with_size
from app.utils.excel_utils import create_product_template_simple, parse_product_excel_simple
from app.utils.excel_utils import (
    create_product_template,
    parse_product_excel,
    export_products_to_excel
)
from datetime import datetime
import io
import zipfile

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
                barcode=barcode,
                notes=notes
            )
            db.session.add(product)
            db.session.commit()

            # Başlangıç stoğu için hareket kaydı
            if current_stock > 0:
                movement = StockMovement(
                    product_id=product.id,
                    movement_type='giris',
                    quantity=current_stock,
                    source='AÇILIŞ',
                    note='Açılış stoğu',
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

    # ÇELMAK etiket formatında QR kod oluştur
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    qr_data = f"{base_url}/products/{product.id}"

    img_io = generate_celmak_label(
        qr_data=qr_data,
        part_no=product.code,
        part_name=product.name
    )

    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=False,
        download_name=f'etiket_{product.code}.png'
    )

@products_bp.route('/<int:id>/qr/download')
@login_required
def download_qr(id):
    product = Product.query.get_or_404(id)

    # ÇELMAK etiket formatında QR kod oluştur
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    qr_data = f"{base_url}/products/{product.id}"

    img_io = generate_celmak_label(
        qr_data=qr_data,
        part_no=product.code,
        part_name=product.name
    )

    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'etiket_{product.code}.png'
    )

@products_bp.route('/qr/bulk-download', methods=['POST'])
@login_required
def bulk_download_qr():
    """Seçilen ürünlerin QR kodlarını ZIP olarak indir"""
    product_ids = request.form.getlist('product_ids[]')

    if not product_ids:
        flash('Lütfen en az bir ürün seçin.', 'error')
        return redirect(url_for('products.index'))

    # ZIP dosyası oluştur
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')

        for product_id in product_ids:
            try:
                product = Product.query.get(int(product_id))
                if not product:
                    continue

                # QR etiket oluştur
                qr_data = f"{base_url}/products/{product.id}"
                img_io = generate_celmak_label(
                    qr_data=qr_data,
                    part_no=product.code,
                    part_name=product.name
                )

                # ZIP'e ekle
                filename = f'etiket_{product.code}.png'
                zip_file.writestr(filename, img_io.getvalue())

            except Exception as e:
                print(f"Hata (Ürün {product_id}): {e}")
                continue

    zip_buffer.seek(0)

    # ZIP dosyasını indir
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'qr_etiketleri_{timestamp}.zip'
    )

@products_bp.route('/qr/download-all')
@login_required
def download_all_qr():
    """Tüm aktif ürünlerin QR kodlarını ZIP olarak indir"""
    # Filtreleri al
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
        flash('İndirilecek ürün bulunamadı.', 'warning')
        return redirect(url_for('products.index'))

    # ZIP dosyası oluştur
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')

        for product in products:
            try:
                # QR etiket oluştur
                qr_data = f"{base_url}/products/{product.id}"
                img_io = generate_celmak_label(
                    qr_data=qr_data,
                    part_no=product.code,
                    part_name=product.name
                )

                # ZIP'e ekle
                filename = f'etiket_{product.code}.png'
                zip_file.writestr(filename, img_io.getvalue())

            except Exception as e:
                print(f"Hata (Ürün {product.code}): {e}")
                continue

    zip_buffer.seek(0)

    # ZIP dosyasını indir
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'tum_qr_etiketleri_{timestamp}.zip'

    flash(f'{len(products)} ürünün QR etiketi indirildi.', 'success')

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
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
    note = request.form.get('note', '')

    if Category.query.filter_by(name=name).first():
        flash('Bu kategori adı zaten kullanılıyor.', 'error')
    else:
        category = Category(name=name, note=note)
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


@products_bp.route('/bulk-qr')
@login_required
def bulk_qr():
    """Toplu QR kod yazdırma sayfası"""
    page = request.args.get('page', 1, type=int)
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

    products = query.order_by(Product.name).paginate(page=page, per_page=50)
    categories = Category.query.all()

    return render_template('products/bulk_qr.html',
        products=products,
        categories=categories,
        selected_category=category_id,
        search=search
    )


@products_bp.route('/generate-bulk-qr', methods=['POST'])
@login_required
def generate_bulk_qr():
    """Seçili ürünler için toplu QR kod oluştur ve ZIP olarak indir"""
    product_ids = request.form.getlist('product_ids[]')
    label_size = request.form.get('label_size', 'medium')  # small, medium, large

    if not product_ids:
        flash('Lütfen en az bir ürün seçin.', 'warning')
        return redirect(url_for('products.bulk_qr'))

    # Seçili ürünleri al
    products = Product.query.filter(Product.id.in_(product_ids)).all()

    if not products:
        flash('Seçili ürünler bulunamadı.', 'error')
        return redirect(url_for('products.bulk_qr'))

    # ZIP dosyası oluştur
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for product in products:
            # QR kod verisi
            qr_data = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/products/{product.id}"

            # Etiket oluştur
            label_image = generate_celmak_label_with_size(
                qr_data=qr_data,
                part_no=product.code,
                part_name=product.name,
                size=label_size
            )

            # Dosya adı
            filename = f"{product.code}_{product.name[:30]}.png".replace('/', '_').replace('\\', '_')

            # ZIP'e ekle
            zip_file.writestr(filename, label_image.getvalue())

    zip_buffer.seek(0)

    # ZIP dosyasını indir
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f'qr_etiketleri_{label_size}_{timestamp}.zip'

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=zip_filename,
        mimetype='application/zip'
    )


@products_bp.route('/preview-qr/<int:product_id>')
@login_required
def preview_qr(product_id):
    """Tek ürün için QR kod önizleme"""
    product = Product.query.get_or_404(product_id)
    label_size = request.args.get('size', 'medium')

    qr_data = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/products/{product.id}"

    label_image = generate_celmak_label_with_size(
        qr_data=qr_data,
        part_no=product.code,
        part_name=product.name,
        size=label_size
    )

    return send_file(
        label_image,
        mimetype='image/png',
        as_attachment=False,
        download_name=f'{product.code}_preview.png'
    )


# ==================== YENİ BASIT EXCEL İMPORT ====================

@products_bp.route('/import/simple')
@login_required
def simple_import_page():
    """Basit Excel import sayfası (Kategori web'de seçilir)"""
    if current_user.role not in ['admin', 'yonetici']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('products.index'))

    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template('products/simple_import.html', categories=categories)


@products_bp.route('/import/simple/template')
@login_required
def download_simple_template():
    """Basit Excel şablonunu indir (Kategori ID yok)"""
    template = create_product_template_simple()

    return send_file(
        template,
        as_attachment=True,
        download_name=f'urunler_import_{datetime.now().strftime("%Y%m%d")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@products_bp.route('/import/simple/upload', methods=['POST'])
@login_required
def simple_upload_import():
    """Basit Excel'i yükle ve önizleme sayfasına gönder"""
    if current_user.role not in ['admin', 'yonetici']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('products.index'))

    if 'file' not in request.files:
        flash('Dosya seçilmedi.', 'error')
        return redirect(url_for('products.simple_import_page'))

    file = request.files['file']

    if file.filename == '':
        flash('Dosya seçilmedi.', 'error')
        return redirect(url_for('products.simple_import_page'))

    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Sadece Excel dosyaları yükleyebilirsiniz (.xlsx, .xls)', 'error')
        return redirect(url_for('products.simple_import_page'))

    try:
        # Excel dosyasını parse et
        success_list, error_list = parse_product_excel_simple(file)

        if not success_list:
            if error_list:
                flash(f'Dosya okunamadı: {error_list[0]["error"]}', 'error')
            else:
                flash('Excel dosyasında geçerli ürün bulunamadı.', 'warning')
            return redirect(url_for('products.simple_import_page'))

        # Session'da sakla (önizleme için)
        from flask import session
        session['import_products'] = success_list
        session['import_errors'] = error_list

        flash(f'{len(success_list)} ürün başarıyla okundu. Kategorileri seçin ve kaydedin.', 'success')
        if error_list:
            flash(f'{len(error_list)} satırda hata oluştu.', 'warning')

        return redirect(url_for('products.import_preview'))

    except Exception as e:
        flash(f'Dosya yüklenirken hata oluştu: {str(e)}', 'error')
        return redirect(url_for('products.simple_import_page'))


@products_bp.route('/import/preview')
@login_required
def import_preview():
    """Import önizleme ve kategori seçimi"""
    if current_user.role not in ['admin', 'yonetici']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('products.index'))

    from flask import session

    products = session.get('import_products', [])
    errors = session.get('import_errors', [])

    if not products:
        flash('Önizlenecek ürün bulunamadı. Lütfen önce Excel dosyasını yükleyin.', 'warning')
        return redirect(url_for('products.simple_import_page'))

    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()

    # Mevcut ürün kodlarını kontrol et (güncellenecek mi, eklenecek mi)
    existing_products = {p.code: p for p in Product.query.filter(
        Product.code.in_([prod['code'] for prod in products])
    ).all()}

    # Yeni ve güncelleme sayısını hesapla
    new_count = sum(1 for p in products if p['code'] not in existing_products)
    update_count = len(existing_products)

    return render_template('products/import_preview.html',
        products=products,
        errors=errors,
        categories=categories,
        existing_products=existing_products,
        new_count=new_count,
        update_count=update_count
    )


@products_bp.route('/import/confirm', methods=['POST'])
@login_required
def confirm_import():
    """Önizlenen ürünleri kategorileriyle birlikte kaydet"""
    if current_user.role not in ['admin', 'yonetici']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('products.index'))

    from flask import session

    products_data = session.get('import_products', [])

    if not products_data:
        flash('Kaydedilecek ürün bulunamadı.', 'warning')
        return redirect(url_for('products.simple_import_page'))

    try:
        added_count = 0
        updated_count = 0
        skipped_count = 0

        for idx, product_data in enumerate(products_data):
            # Form'dan kategori ID'yi al
            category_id = request.form.get(f'category_{idx}', type=int)

            if not category_id:
                skipped_count += 1
                continue

            # Kategori kontrolü
            category = Category.query.get(category_id)
            if not category:
                skipped_count += 1
                continue

            product_data['category_id'] = category_id

            # Mevcut ürün kontrolü
            existing_product = Product.query.filter_by(code=product_data['code']).first()

            if existing_product:
                # Güncelle
                existing_product.name = product_data['name']
                existing_product.category_id = product_data['category_id']
                existing_product.unit_type = product_data['unit_type']
                existing_product.minimum_stock = product_data['minimum_stock']
                if product_data.get('barcode'):
                    existing_product.barcode = product_data['barcode']
                if product_data.get('notes'):
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
                    barcode=product_data.get('barcode'),
                    notes=product_data.get('notes')
                )
                db.session.add(new_product)

                # Açılış stoğu hareketi
                if product_data['current_stock'] > 0:
                    from app.models import StockMovement
                    opening_movement = StockMovement(
                        product_id=new_product.id,
                        movement_type='giris',
                        quantity=product_data['current_stock'],
                        source='AÇILIŞ',
                        note='Excel import - Açılış stoğu',
                        user_id=current_user.id
                    )
                    db.session.add(opening_movement)

                added_count += 1

        db.session.commit()

        # Session'ı temizle
        session.pop('import_products', None)
        session.pop('import_errors', None)

        flash(f'✓ {added_count} ürün eklendi, {updated_count} ürün güncellendi.', 'success')
        if skipped_count > 0:
            flash(f'⚠ {skipped_count} ürün atlandı (kategori seçilmemiş).', 'warning')

        return redirect(url_for('products.index'))

    except Exception as e:
        db.session.rollback()
        flash(f'Ürünler kaydedilirken hata oluştu: {str(e)}', 'error')
        return redirect(url_for('products.import_preview'))
