from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session, send_file, current_app
from flask_login import login_required, current_user
from app.models import Category, StockMovement, Product, ProductionRecord, ProductionConsumption
from app import db
from sqlalchemy import func, inspect
from datetime import datetime, timedelta
from app.utils.decorators import roles_required
from app.utils import sanitize_part_code
from app.utils.excel_utils import parse_bom_excel, create_bom_tree_excel
from app.utils.bom_utils import (
    parse_bom_excel_v2,
    import_bom_to_db,
    get_bom_tree,
    get_bom_subtree,
    list_boms,
    next_bom_id,
    analyze_bom_for_import,
    compare_bom_update,
    audit_bom_material_links,
    analyze_bom_delete,
    audit_bom_costs,
    explode_bom_materials,
    preview_standardize_name,
    standardize_bom_item_name,
    add_bom_node,
    delete_bom_node,
    move_bom_node,
)
import pickle
import os
import uuid
import json
import urllib.parse
import urllib.request
import urllib.error

production_bp = Blueprint('production', __name__)


def _limited_flash_list(prefix, items, category='error', limit=8):
    shown = list(items[:limit])
    if len(items) > limit:
        shown.append(f'{len(items) - limit} kalem daha var')
    flash(prefix + ' ' + ' | '.join(shown), category)


def _production_records_support_product_id():
    try:
        columns = inspect(db.engine).get_columns('production_records')
    except Exception:
        return False
    return any(column.get('name') == 'product_id' for column in columns)


def _extract_price_payload(payload):
    data = payload.get('data') if isinstance(payload, dict) and isinstance(payload.get('data'), dict) else payload
    if not isinstance(data, dict):
        return None

    cost = (
        data.get('unit_cost')
        or data.get('cost')
        or data.get('price')
        or data.get('unit_price')
        or data.get('last_purchase_price')
    )
    if cost is None and isinstance(data.get('purchasing_info'), dict):
        cost = data['purchasing_info'].get('unit_cost') or data['purchasing_info'].get('price')
    if cost is None:
        return None

    try:
        unit_cost = float(cost)
    except (TypeError, ValueError):
        return None

    return {
        'unit_cost': unit_cost,
        'currency': data.get('currency') or data.get('currency_code') or 'TRY',
        'vat_rate': data.get('vat_rate'),
    }


def _purchasing_headers():
    headers = {'Accept': 'application/json'}
    api_key = current_app.config.get('PURCHASING_API_KEY')
    if api_key:
        headers['X-API-Key'] = api_key
    return headers


def _fetch_purchasing_price_map(product_codes):
    base_url = current_app.config.get('PURCHASING_API_BASE_URL')
    if not base_url:
        raise RuntimeError('PURCHASING_API_BASE_URL tanimli degil')

    url = f'{base_url}/api/v1/products/prices'
    req = urllib.request.Request(url, headers=_purchasing_headers(), method='GET')
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))

    prices = payload.get('prices') if isinstance(payload, dict) else None
    if not isinstance(prices, dict):
        raise RuntimeError('Satinalma API fiyat listesi donmedi')

    result = {}
    for code in product_codes:
        price = _extract_price_payload(prices.get(code))
        if price:
            result[code] = price
    return result


def _fetch_purchasing_price(product_code):
    base_url = current_app.config.get('PURCHASING_API_BASE_URL')
    if not base_url:
        raise RuntimeError('PURCHASING_API_BASE_URL tanımlı değil')

    quoted_code = urllib.parse.quote(str(product_code), safe='')
    urls = [
        f'{base_url}/api/v1/products/{quoted_code}/price',
        f'{base_url}/api/v1/purchasing/product/{quoted_code}',
        f'{base_url}/api/products/{quoted_code}/price',
    ]
    headers = _purchasing_headers()

    last_error = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers, method='GET')
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode('utf-8'))
            price = _extract_price_payload(payload)
            if price:
                return price
            last_error = 'Fiyat alanı bulunamadı'
        except urllib.error.HTTPError as exc:
            last_error = f'HTTP {exc.code}'
            if exc.code not in (404, 405):
                break
        except Exception as exc:
            last_error = str(exc)
            break
    raise RuntimeError(last_error or 'Satınalma API yanıt vermedi')

# BOM import için geçici dosya yönetimi
def _save_bom_temp_data(data):
    """BOM verisini geçici dosyaya kaydet ve ID döndür"""
    temp_id = str(uuid.uuid4())
    temp_dir = os.path.join('instance', 'temp_bom')
    os.makedirs(temp_dir, exist_ok=True)
    temp_file = os.path.join(temp_dir, f'{temp_id}.pkl')
    
    with open(temp_file, 'wb') as f:
        pickle.dump(data, f)
    
    return temp_id

def _load_bom_temp_data(temp_id):
    """Geçici dosyadan BOM verisini yükle"""
    temp_file = os.path.join('instance', 'temp_bom', f'{temp_id}.pkl')
    if not os.path.exists(temp_file):
        return None
    
    with open(temp_file, 'rb') as f:
        data = pickle.load(f)
    
    return data

def _delete_bom_temp_data(temp_id):
    """Geçici BOM dosyasını sil"""
    temp_file = os.path.join('instance', 'temp_bom', f'{temp_id}.pkl')
    if os.path.exists(temp_file):
        os.remove(temp_file)


@production_bp.route('/')
@login_required
@roles_required('Genel', 'Yönetici')
def index():
    """Kategorileri üretim hatları olarak listele"""
    active_categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    
    if current_user.is_admin():
        inactive_categories = Category.query.filter_by(is_active=False).order_by(Category.name).all()
    else:
        inactive_categories = []
    
    all_categories = active_categories + inactive_categories
    
    # Her kategori için istatistikler
    category_stats = {}
    for cat in all_categories:
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
        categories=active_categories,
        inactive_categories=inactive_categories,
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

        if quantity is None:
            flash('Geçerli bir miktar girmelisiniz.', 'error')
        elif quantity <= 0:
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

    
    name = category.name
    db.session.delete(category)
    db.session.commit()
    flash(f'{name} üretim hattı başarıyla silindi.', 'success')
    return redirect(url_for('production.index'))


# ===== BOM V2 — NUMARALANDIRMA BAZLI HİYERARŞİ =====

@production_bp.route('/bom')
@login_required
@roles_required('Genel', 'Yönetici')
def bom_list():
    """Tüm BOM'ları listele."""
    from app.models import Category
    boms = list_boms(db)
    categories = Category.query.order_by(Category.name).all()
    return render_template('production/bom_list.html', boms=boms, categories=categories)



@production_bp.route('/bom/<int:bom_id>/assign_category', methods=['POST'])
@login_required
@roles_required('Yönetici')
def bom_assign_category(bom_id):
    from app.models import BomNode, Product
    category_id = request.form.get('category_id')
    
    root_node = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
    if root_node and root_node.item and root_node.item.product:
        product = root_node.item.product
        if category_id:
            product.category_id = int(category_id)
            flash('BOM başarıyla üretim hattına atandı.', 'success')
        else:
            product.category_id = None
            flash('BOM üretim hattı ataması kaldırıldı.', 'success')
        db.session.commit()
    else:
        flash('Ana ürün bulunamadı!', 'error')
        
    return redirect(url_for('production.bom_list'))


@production_bp.route('/bom/<int:bom_id>/update-name', methods=['POST'])
@login_required
@roles_required('Yönetici')
def bom_update_name(bom_id):
    from app.models import BomNode, BomItem, Product
    
    new_name = request.form.get('root_name', '').strip()
    if not new_name:
        flash('Ürün ismi boş olamaz!', 'error')
        return redirect(url_for('production.bom_list'))
    
    # Root node'u bul
    root_node = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
    if not root_node:
        flash('BOM bulunamadı!', 'error')
        return redirect(url_for('production.bom_list'))
    
    # Display name'i güncelle
    root_node.display_name = new_name
    
    # Eğer BomItem varsa onun adını da güncelle
    if root_node.item:
        root_node.item.name = new_name
        
        # Ürünle bağlantılıysa ürünün adını da güncelle
        if root_node.item.product:
            root_node.item.product.name = new_name
    
    db.session.commit()
    flash('Ana ürün ismi başarıyla güncellendi.', 'success')
    return redirect(url_for('production.bom_list'))


@production_bp.route('/bom/import', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def bom_import_v2():
    """İki aşamalı BOM içe aktarma: 1) Analiz ve önizleme 2) Onay ve import"""
    from app.models import Category
    categories = Category.query.order_by(Category.name).all()
    
    if request.method == 'POST':
        # AŞAMA 2: Kullanıcı onayladı, import yap
        if request.form.get('action') == 'confirm_import':
            try:
                # Geçici dosyadan verileri al
                temp_id = session.get('bom_temp_id')
                if not temp_id:
                    flash('Oturum süresi doldu. Lütfen dosyayı tekrar yükleyin.', 'error')
                    return redirect(url_for('production.bom_import_v2'))
                
                bom_data = _load_bom_temp_data(temp_id)
                if not bom_data:
                    flash('Geçici veri bulunamadı. Lütfen dosyayı tekrar yükleyin.', 'error')
                    return redirect(url_for('production.bom_import_v2'))
                
                rows = bom_data['rows']
                bom_name = bom_data['bom_name']
                category_id = bom_data['category_id']
                
                # Kullanıcı kararlarını al
                conflict_resolutions = {}
                for key in request.form:
                    if key.startswith('conflict_'):
                        product_name = key.replace('conflict_', '')
                        action = request.form.get(key)
                        conflict_resolutions[product_name] = {
                            'action': action,
                            'update_material': request.form.get(f'update_material_{product_name}') == 'on',
                            'update_type': request.form.get(f'update_type_{product_name}') == 'on',
                            'update_unit': request.form.get(f'update_unit_{product_name}') == 'on',
                        }
                
                bom_id = next_bom_id(db)
                stats = import_bom_to_db(rows, bom_id, db, category_id=category_id, 
                                        conflict_resolutions=conflict_resolutions)
                
                # Geçici dosyayı temizle
                _delete_bom_temp_data(temp_id)
                session.pop('bom_temp_id', None)
                
                flash(
                    f'✅ BOM #{bom_id} başarıyla içe aktarıldı! '
                    f'{stats["nodes"]} düğüm | {stats["items"]} parça | '
                    f'{stats["products"]} yeni ürün | {stats["updated"]} güncelleme | '
                    f'{stats["edges"]} ilişki oluşturuldu'
                    + (f' | {stats["prices_set"]} fiyat Excel\'den ayarlandı' if stats.get("prices_set") else '')
                    + (f' | {stats["unresolved_materials"]} hammadde eşleşmedi.' if stats.get("unresolved_materials") else '.'),
                    'success'
                )
                return redirect(url_for('production.bom_tree', bom_id=bom_id))
                
            except Exception as exc:
                db.session.rollback()
                # Hata durumunda da geçici dosyayı temizle
                temp_id = session.get('bom_temp_id')
                if temp_id:
                    _delete_bom_temp_data(temp_id)
                    session.pop('bom_temp_id', None)
                flash(f'Import hatası: {exc}', 'error')
                return redirect(url_for('production.bom_import_v2'))
        
        # AŞAMA 1: Dosya yüklendi, analiz yap ve önizleme göster
        if 'file' not in request.files or request.files['file'].filename == '':
            flash('Dosya seçilmedi.', 'error')
            return redirect(url_for('production.bom_import_v2'))

        file = request.files['file']
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            flash('Geçersiz dosya formatı. Lütfen .xlsx veya .xls yükleyin.', 'error')
            return redirect(url_for('production.bom_import_v2'))

        try:
            bom_name = request.form.get('bom_name', '').strip()
            rows, errors = parse_bom_excel_v2(file, override_root_name=bom_name or None)

            if errors and not rows:
                flash(f'Excel parse hatası: {errors[0]["error"]}', 'error')
                return redirect(url_for('production.bom_import_v2'))

            category_id = request.form.get('category_id')
            cat_id_int = int(category_id) if category_id else None
            
            # Analiz yap
            analysis = analyze_bom_for_import(rows, category_id=cat_id_int)
            
            # Geçici dosyaya kaydet (import için)
            temp_id = _save_bom_temp_data({
                'rows': rows,
                'bom_name': bom_name,
                'category_id': cat_id_int,
            })
            session['bom_temp_id'] = temp_id
            
            # Uyarı mesajları varsa ekle
            warn_msg = ''
            if errors:
                warn_msg = f'{len(errors)} satır atlandı.'
            
            return render_template('production/bom_import_preview.html',
                                 analysis=analysis,
                                 categories=categories,
                                 selected_category_id=cat_id_int,
                                 bom_name=bom_name,
                                 errors=errors,
                                 warn_msg=warn_msg)


        except Exception as exc:
            db.session.rollback()
            flash(f'Beklenmeyen hata: {exc}', 'error')
            return redirect(url_for('production.bom_import_v2'))

    return render_template('production/bom_import_v2.html', categories=categories)


@production_bp.route('/bom/<int:bom_id>/update-excel', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def bom_update_excel(bom_id):
    """Mevcut BOM'u Excel ile karşılaştırır ve onayda yeni revizyon oluşturur."""
    from app.models import Category, BomNode

    categories = Category.query.order_by(Category.name).all()
    root_node = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
    if not root_node:
        flash(f'BOM #{bom_id} bulunamadı.', 'error')
        return redirect(url_for('production.bom_list'))

    root_product = root_node.item.product if root_node.item and root_node.item.product else None
    default_category_id = root_product.category_id if root_product else None

    if request.method == 'POST':
        if request.form.get('action') == 'confirm_update':
            temp_id = session.get('bom_update_temp_id')
            bom_data = _load_bom_temp_data(temp_id) if temp_id else None
            if not bom_data:
                flash('Güncelleme oturumu bulunamadı. Lütfen Excel dosyasını tekrar yükleyin.', 'error')
                return redirect(url_for('production.bom_update_excel', bom_id=bom_id))

            try:
                conflict_resolutions = {}
                for key in request.form:
                    if key.startswith('conflict_'):
                        product_name = key.replace('conflict_', '')
                        conflict_resolutions[product_name] = {
                            'action': request.form.get(key),
                            'update_material': request.form.get(f'update_material_{product_name}') == 'on',
                            'update_type': request.form.get(f'update_type_{product_name}') == 'on',
                            'update_unit': request.form.get(f'update_unit_{product_name}') == 'on',
                        }

                new_bom_id = next_bom_id(db)
                stats = import_bom_to_db(
                    bom_data['rows'],
                    new_bom_id,
                    db,
                    category_id=bom_data.get('category_id'),
                    conflict_resolutions=conflict_resolutions
                )

                _delete_bom_temp_data(temp_id)
                session.pop('bom_update_temp_id', None)

                flash(
                    f'BOM #{bom_id} için yeni revizyon BOM #{new_bom_id} olarak oluşturuldu. '
                    f'{stats["nodes"]} düğüm | {stats["products"]} yeni ürün | '
                    f'{stats["updated"]} güncelleme'
                    + (f' | {stats["prices_set"]} fiyat Excel\'den ayarlandı' if stats.get('prices_set') else '')
                    + (f' | {stats["unresolved_materials"]} hammadde eşleşmedi.' if stats.get('unresolved_materials') else '.'),
                    'success'
                )
                return redirect(url_for('production.bom_tree', bom_id=new_bom_id))
            except Exception as exc:
                db.session.rollback()
                flash(f'Güncelleme import hatası: {exc}', 'error')
                return redirect(url_for('production.bom_update_excel', bom_id=bom_id))

        if 'file' not in request.files or request.files['file'].filename == '':
            flash('Dosya seçilmedi.', 'error')
            return redirect(url_for('production.bom_update_excel', bom_id=bom_id))

        file = request.files['file']
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            flash('Geçersiz dosya formatı. Lütfen .xlsx veya .xls yükleyin.', 'error')
            return redirect(url_for('production.bom_update_excel', bom_id=bom_id))

        try:
            bom_name = request.form.get('bom_name', '').strip()
            rows, errors = parse_bom_excel_v2(file, override_root_name=bom_name or root_node.display_name)
            if errors and not rows:
                flash(f'Excel parse hatası: {errors[0]["error"]}', 'error')
                return redirect(url_for('production.bom_update_excel', bom_id=bom_id))

            category_id = request.form.get('category_id') or default_category_id
            cat_id_int = int(category_id) if category_id else None
            analysis = analyze_bom_for_import(rows, category_id=cat_id_int)
            comparison = compare_bom_update(bom_id, rows, db)

            temp_id = _save_bom_temp_data({
                'rows': rows,
                'source_bom_id': bom_id,
                'bom_name': bom_name or root_node.display_name,
                'category_id': cat_id_int,
            })
            session['bom_update_temp_id'] = temp_id

            warn_msg = f'{len(errors)} satır atlandı.' if errors else ''
            return render_template(
                'production/bom_update_preview.html',
                source_bom_id=bom_id,
                root_name=root_node.display_name,
                analysis=analysis,
                comparison=comparison,
                categories=categories,
                selected_category_id=cat_id_int,
                warn_msg=warn_msg,
                errors=errors
            )
        except Exception as exc:
            db.session.rollback()
            flash(f'Beklenmeyen hata: {exc}', 'error')
            return redirect(url_for('production.bom_update_excel', bom_id=bom_id))

    return render_template(
        'production/bom_update_excel.html',
        bom_id=bom_id,
        root_name=root_node.display_name,
        categories=categories,
        selected_category_id=default_category_id
    )


@production_bp.route('/bom/<int:bom_id>')
@login_required
@roles_required('Genel', 'Yönetici')
def bom_tree(bom_id):
    """BOM ağacını görüntüle."""
    tree = get_bom_tree(bom_id, db)
    if not tree['roots']:
        flash(f'BOM #{bom_id} bulunamadı veya boş.', 'error')
        return redirect(url_for('production.bom_list'))
    return render_template('production/bom_tree.html', tree=tree, bom_id=bom_id)



@production_bp.route('/api/bom_node/<int:node_id>', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici', 'Genel')
def api_bom_node(node_id):
    from app.models import BomNode, Product, BomItem, BomEdge
    node = BomNode.query.get_or_404(node_id)
    item = node.item
    product = item.product if item else None

    if request.method == 'GET':
        return jsonify({
            'id': node.id,
            'name': node.display_name,
            'code': item.code if item else '',
            'material': product.material if product else '',
            'type': product.type if product else 'hammadde',
            'quantity': float(node.quantity) if node.quantity else 0,
            'quantity_net': float(node.quantity_net) if node.quantity_net else 0,
            'piece_count': float(node.piece_count) if getattr(node, 'piece_count', None) is not None else 1,
            'product_code': product.code if product else '',
            'unit_cost': float(product.unit_cost) if product and product.unit_cost is not None else 0,
            'currency': product.currency if product and product.currency else 'TRY',
            'unit': node.unit_type,
            'weight_per_unit': float(node.weight_per_unit) if node.weight_per_unit else 0
        })
    elif request.method == 'POST':
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'Veri alınamadı'})
        
        try:
            if 'name' in data and data['name']:
                node.display_name = data['name']
            if 'quantity' in data:
                node.quantity = data['quantity']
                # node.quantity <-> edge.quantity senkron: üretim sarfiyatı da bu
                # düğüme bağlı kenar(lar)dan güncel miktarı görsün.
                BomEdge.query.filter_by(child_node_id=node.id).update(
                    {'quantity': node.quantity}, synchronize_session=False)
            if 'quantity_net' in data:
                node.quantity_net = data['quantity_net']
            if 'piece_count' in data:
                node.piece_count = data['piece_count']
            if 'unit' in data and data['unit']:
                node.unit_type = str(data['unit']).strip()[:20]
            if 'weight_per_unit' in data:
                wv = data.get('weight_per_unit')
                try:
                    wv = float(wv) if wv not in (None, '') else 0.0
                except (TypeError, ValueError):
                    wv = 0.0
                # 0/boş → temizle (None); pozitif → kaydet. Böylece yanlış/şişik
                # ağırlık elle sıfırlanabilir ya da doğru değere çekilebilir.
                node.weight_per_unit = wv if wv > 0 else None

            if item:
                if 'name' in data and data['name']:
                    item.name = data['name']
                if 'code' in data:
                    item.code = sanitize_part_code(data['code'])
                    
            if product:
                if 'name' in data and data['name']:
                    product.name = data['name']
                if 'material' in data:
                    product.material = data['material']
                if 'type' in data and data['type'] in ['hammadde', 'yarimamul', 'mamul', 'standart_parca', 'hazir_parca']:
                    product.type = data['type']
                if 'unit_cost' in data:
                    unit_cost = float(data.get('unit_cost') or 0)
                    if unit_cost < 0:
                        return jsonify({'success': False, 'error': 'Birim maliyet negatif olamaz!'})
                    product.unit_cost = unit_cost
                if 'currency' in data and data['currency']:
                    product.currency = str(data['currency']).strip().upper()[:10]
                if 'product_code' in data and data['product_code']:
                    sanitized_code = sanitize_part_code(data['product_code'])
                    existing = Product.query.filter(Product.code == sanitized_code, Product.id != product.id).first()
                    if not existing:
                        product.code = sanitized_code
                    else:
                        return jsonify({'success': False, 'error': 'Belirtilen ürün kodu başka bir üründe kullanılıyor!'})
                        
            from app import db
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})


@production_bp.route('/api/bom_tree/<int:bom_id>')

@login_required
def api_bom_tree(bom_id):
    """BOM ağacını JSON olarak döndür."""
    tree = get_bom_tree(bom_id, db)
    return jsonify(tree)


@production_bp.route('/bom/<int:bom_id>/material-audit', methods=['GET', 'POST'])
@login_required
@roles_required('YÃ¶netici', 'Genel')
def bom_material_audit(bom_id):
    from app.models import BomNode
    root_node = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
    if not root_node:
        flash(f'BOM #{bom_id} bulunamadÄ±.', 'error')
        return redirect(url_for('production.bom_list'))

    apply_changes = request.method == 'POST'
    audit = audit_bom_material_links(bom_id, db, apply=apply_changes)
    if apply_changes:
        fixed_nodes = audit['stats'].get('fixed_nodes', 0)
        if fixed_nodes:
            flash(f'{fixed_nodes} BOM satÄ±rÄ±nÄ±n hammadde kartÄ± baÄŸlantÄ±sÄ± gÃ¼ncellendi.', 'success')
        else:
            flash('Uygulanacak otomatik hammadde baÄŸlantÄ± dÃ¼zeltmesi bulunamadÄ±.', 'info')
        return redirect(url_for('production.bom_material_audit', bom_id=bom_id))

    return render_template(
        'production/bom_material_audit.html',
        bom_id=bom_id,
        root_name=root_node.display_name,
        audit=audit
    )


@production_bp.route('/bom/<int:bom_id>/cost-audit')
@login_required
@roles_required('Yönetici', 'Genel')
def bom_cost_audit(bom_id):
    """Her yaprak malzeme için maliyetin hangi kart ve hangi birim dönüşümüyle
    hesaplandığını gösteren döküm — beklenmedik yüksek maliyetlerin kaynağını
    bulmak için kullanılır."""
    from app.models import BomNode
    root_node = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
    if not root_node:
        flash(f'BOM #{bom_id} bulunamadı.', 'error')
        return redirect(url_for('production.bom_list'))

    audit = audit_bom_costs(bom_id, db)
    return render_template(
        'production/bom_cost_audit.html',
        bom_id=bom_id,
        root_name=root_node.display_name,
        audit=audit
    )


@production_bp.route('/weight-audit')
@login_required
@roles_required('Genel', 'Yönetici')
def weight_audit():
    """Tüm ürün ağaçlarını tarayıp üretimde SARF EDİLEMEYECEK parçaları listeler:
    - kartsız (unlinked): bağlı stok kartı yok
    - ağırlık/birim eksik (missing_weight): kart var ama birim uyuşmuyor + fireli ağırlık yok
    Salt-okunur; hiçbir stok/üretim değişikliği yapmaz."""
    from app.models import BomNode

    roots = BomNode.query.filter_by(level=0).all()
    unlinked_map, missing_map = {}, {}
    bom_count = 0
    for root in roots:
        try:
            exp = explode_bom_materials(root.bom_id, root.id, 1, db)
        except Exception:
            continue
        bom_count += 1
        bom_label = root.display_name or f'BOM #{root.bom_id}'
        for u in exp.get('unlinked', []):
            key = (u.get('name') or '').strip().lower()
            e = unlinked_map.setdefault(key, {'name': u.get('name'), 'boms': set()})
            e['boms'].add(bom_label)
        for m in exp.get('missing_weight', []):
            key = (m.get('product_code') or (m.get('name') or '')).strip().lower()
            e = missing_map.setdefault(key, {'name': m.get('name'), 'code': m.get('product_code'), 'boms': set()})
            e['boms'].add(bom_label)

    def _finish(d):
        rows = list(d.values())
        for e in rows:
            e['bom_count'] = len(e['boms'])
            e['boms'] = sorted(e['boms'])[:6]
        return sorted(rows, key=lambda x: -x['bom_count'])

    unlinked = _finish(unlinked_map)
    missing = _finish(missing_map)
    return render_template('production/weight_audit.html',
                           unlinked=unlinked, missing=missing, bom_count=bom_count)


@production_bp.route('/link-audit', methods=['GET', 'POST'])
@login_required
@roles_required('Genel', 'Yönetici')
def link_audit():
    """Yanlış stok kartına bağlı BOM parçalarını bulur.

    ÖNEMLİ: Mevcut per-BOM denetimi (audit_bom_material_links) parçanın 'kaynak'
    metnini önce BAĞLI KARTTAN türetir; parça yanlış karta bağlıysa kart kendini
    doğrular ve hata gizlenir (ör. '2 mm' parça '10 mm' kartına bağlıyken sorunsuz
    görünür). Burada bunun yerine parçanın KENDİ ADI (item.name) imzasını bağlı
    kartın imzasıyla DOĞRUDAN karşılaştırırız; böylece o kaçış yakalanır.

    GET: yalnızca hammadde kartına bağlı, ölçülebilir (sac/lama/profil/boru/mil)
         parçalarda ad↔kart imzası farkını listeler (salt-okunur).
    POST: yalnızca kullanıcının seçtiği kalemleri, imza-doğrulaması yaparak
          önerilen doğru karta bağlar (product_id günceller). Node/edge değişmez."""
    import re as _re
    from app.models import BomNode, BomItem, Product
    from app.utils.bom_utils import (
        _strict_material_signature, _strict_signatures_match,
        _find_matching_raw_material, _costing_unit_family)
    from sqlalchemy.orm import joinedload

    def _sig(product):
        return _strict_material_signature(' '.join([
            product.name or '', getattr(product, 'material', '') or '',
            product.code or '', getattr(product, 'notes', '') or '']))

    def _gen_code(name):
        tr = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')
        s = _re.sub(r'[^A-Za-z0-9]+', '-', (name or '').translate(tr)).strip('-').upper()
        return s[:45] if s else 'OTO-PARCA'

    def _default_unit(item):
        return _costing_unit_family(item.name or '') or (item.unit_type or 'adet')

    # Aktif ürünler + hammadde adayları (öneri, korumalı eşleştiriciyle bulunur)
    products = Product.query.filter(Product.is_active == True).all()
    prod_sig = {p.id: _sig(p) for p in products}
    hammadde_candidates = [p for p in products if p.type == 'hammadde']

    def _suggest(item, exclude_id):
        """Yalnızca GERÇEK ham malzeme kartı önerir: 3TB- (mamul/parça) kodları
        elenir, isim + kalite + ölçü token'ları örtüşmeli, eşik altındaysa None.
        Böylece 'Boğaz İç Sacı' gibi alakasız kartlar asla önerilmez."""
        s = _find_matching_raw_material(
            {'is_auto_hammadde': True, 'name': item.name or '',
             'unit_type': item.unit_type or '', 'weight_per_unit': 0},
            candidates=hammadde_candidates)
        if s and s.id != exclude_id:
            return s
        return None

    linked_items = (BomItem.query
                    .options(joinedload(BomItem.product))
                    .filter(BomItem.product_id.isnot(None)).all())

    # POST: seçili kalemleri (a) önerilen karta bağla ya da (b) yeni kart açıp bağla
    if request.method == 'POST':
        by_id = {it.id: it for it in linked_items}
        fixed_items = fixed_nodes = created = 0
        for raw in request.form.getlist('item_id'):
            try:
                iid = int(raw)
            except (TypeError, ValueError):
                continue
            if request.form.get(f'inc_{iid}') != '1':
                continue
            it = by_id.get(iid) or BomItem.query.get(iid)
            if not it:
                continue
            mode = (request.form.get(f'mode_{iid}') or 'link').strip()

            if mode == 'create':
                name = (request.form.get(f'name_{iid}') or it.name or '').strip()
                if not name:
                    continue
                ptype = (request.form.get(f'type_{iid}') or 'hammadde').strip() or 'hammadde'
                unit = (request.form.get(f'unit_{iid}') or 'adet').strip() or 'adet'
                code = (request.form.get(f'code_{iid}') or '').strip() or _gen_code(name)
                # Aynı adda aktif kart zaten varsa yenisini AÇMA; mevcudu kullan
                existing = Product.query.filter(
                    func.lower(Product.name) == name.lower(),
                    Product.is_active == True).first()
                if existing:
                    target = existing
                else:
                    base, n = code, 1
                    while Product.query.filter_by(code=code).first():
                        n += 1
                        code = f'{base}-{n}'
                    target = Product(code=code, name=name, type=ptype,
                                     unit_type=unit, current_stock=0)
                    db.session.add(target)
                    db.session.flush()
                    created += 1
                if target.id == it.product_id:
                    continue
                it.product_id = target.id
                fixed_items += 1
                fixed_nodes += it.nodes.count()
            else:  # link: mevcut karta bağla (imza yeniden doğrulanır)
                try:
                    tid = int(request.form.get(f'sug_{iid}') or 0)
                except (TypeError, ValueError):
                    continue
                target = Product.query.get(tid)
                if not target or target.id == it.product_id:
                    continue
                nsig = _strict_material_signature(it.name or '')
                if not (nsig and _strict_signatures_match(nsig, _sig(target))):
                    continue
                it.product_id = target.id
                fixed_items += 1
                fixed_nodes += it.nodes.count()

        if fixed_items:
            db.session.commit()
            msg = f'{fixed_items} parça doğru karta bağlandı ({fixed_nodes} BOM satırı etkilendi).'
            if created:
                msg += f' {created} yeni kart oluşturuldu.'
            flash(msg, 'success')
        else:
            db.session.rollback()
            flash('Uygulanacak seçim bulunamadı.', 'info')
        return redirect(url_for('production.link_audit'))

    # GET: yanlış bağlantıları tespit et
    roots = BomNode.query.filter_by(level=0).all()
    bom_label = {r.bom_id: (r.display_name or f'BOM #{r.bom_id}') for r in roots}

    problems = []
    per_bom = {}
    for it in linked_items:
        product = it.product
        if not product or product.type != 'hammadde':
            continue
        nsig = _strict_material_signature(it.name or '')
        psig = prod_sig.get(product.id)
        # Yalnızca her iki taraf da ölçülebilir VE imzalar farklıysa = kesin yanlış bağlantı
        if not (nsig and psig) or _strict_signatures_match(nsig, psig):
            continue
        nodes = it.nodes.all()
        bom_ids = sorted({n.bom_id for n in nodes})
        suggestion = _suggest(it, product.id)
        problems.append({
            'item_id': it.id,
            'name': it.name,
            'unit_type': it.unit_type,
            'current_name': product.name,
            'current_code': product.code,
            'suggested_id': suggestion.id if suggestion else None,
            'suggested_name': suggestion.name if suggestion else None,
            'suggested_code': suggestion.code if suggestion else None,
            'has_suggestion': bool(suggestion),
            # Öneri yoksa: doğru kartı oluşturmak için önceden dolu, düzenlenebilir varsayılanlar
            'new_code': _gen_code(it.name),
            'new_unit': _default_unit(it),
            'affected_nodes': len(nodes),
            'bom_count': len(bom_ids),
            'boms': [bom_label.get(b, f'BOM #{b}') for b in bom_ids][:6],
        })
        for b in bom_ids:
            e = per_bom.setdefault(b, {'bom_id': b, 'label': bom_label.get(b, f'BOM #{b}'), 'count': 0})
            e['count'] += 1

    problems.sort(key=lambda x: (not x['has_suggestion'], x['name'] or ''))
    bom_summary = sorted(per_bom.values(), key=lambda x: -x['count'])
    return render_template('production/link_audit.html',
                           problems=problems, bom_summary=bom_summary,
                           scanned=len(roots), total=len(problems),
                           fixable=sum(1 for p in problems if p['has_suggestion']))


@production_bp.route('/bom/<int:bom_id>/consume-breakdown')
@login_required
@roles_required('Genel', 'Yönetici')
def consume_breakdown(bom_id):
    """Üretim sarfiyatının satır satır dökümü: her yaprak malzemenin düğüm
    miktarı, üst-adet çarpanı ve katkısı (kg/metre/adet). Salt-okunur;
    'toplam neden bu kadar' sorusunu şeffaf gösterir."""
    from collections import defaultdict
    from app.models import BomNode
    root = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
    if not root:
        flash(f'BOM #{bom_id} bulunamadı.', 'error')
        return redirect(url_for('production.bom_list'))
    exp = explode_bom_materials(bom_id, root.id, 1, db)
    q = (request.args.get('q') or '').strip().lower()
    lines = exp.get('breakdown', [])
    if q:
        lines = [l for l in lines
                 if q in (l.get('name') or '').lower() or q in (l.get('code') or '').lower()]
    lines.sort(key=lambda l: ((l.get('code') or ''), (l.get('num') or '')))
    totals = defaultdict(lambda: {'code': '', 'name': '', 'unit': '', 'total': 0.0, 'count': 0})
    for l in lines:
        key = l.get('code') or '—'
        t = totals[key]
        t['code'] = key
        t['name'] = l.get('name')
        t['unit'] = l.get('unit')
        t['total'] += float(l.get('contrib') or 0)
        t['count'] += 1
    total_rows = sorted(totals.values(), key=lambda x: -x['total'])
    return render_template('production/consume_breakdown.html',
                           bom_id=bom_id, root_name=root.display_name,
                           lines=lines, totals=total_rows, q=q)


@production_bp.route('/shared-card-split', methods=['GET', 'POST'])
@login_required
@roles_required('Genel', 'Yönetici')
def shared_card_split():
    """Tek bir stok kartına bağlı FARKLI isimli parçaları ayrıştırır: her farklı
    parçaya kendi kartını açıp bağlar. Böylece bir parçanın kodu/fiyatı ötekileri
    etkilemeden düzenlenebilir. Yeni kartlar fiyatsız (0) açılır; fiyatlar sonra
    'Hızlı Fiyat Girişi' sayfasından girilir. Node/edge/ağaç yapısı değişmez."""
    import re as _re
    from collections import defaultdict
    from app.models import BomItem, Product

    def _gen_code(name):
        tr = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')
        s = _re.sub(r'[^A-Za-z0-9]+', '-', (name or '').translate(tr)).strip('-').upper()
        return ('AYR-' + s)[:45] if s else 'AYR-PARCA'

    def _norm(s):
        return _re.sub(r'\s+', ' ', (s or '').strip()).lower()

    from app.models import BomNode
    from sqlalchemy.orm import joinedload

    # Paylaşım DÜĞÜM seviyesinde olabilir: aynı BomItem/kart, farklı görünen adlı
    # çok sayıda düğümce kullanılır (ör. tek '999-000-1' kartı 10 farklı parçada).
    # Bu yüzden kartın (product_id) altındaki düğümleri GÖRÜNEN ADA göre grupluyoruz.
    nodes = (BomNode.query
             .options(joinedload(BomNode.item).joinedload(BomItem.product))
             .join(BomItem, BomNode.item_id == BomItem.id)
             .filter(BomItem.product_id.isnot(None)).all())

    def _dn(n):
        return _norm(n.display_name or (n.item.name if n.item else ''))

    by_prod = defaultdict(list)   # product_id -> [BomNode, ...]
    for n in nodes:
        by_prod[n.item.product_id].append(n)

    if request.method == 'POST':
        sel = set(request.form.getlist('product_id'))
        created = relinked = 0
        for pid_str in sel:
            try:
                pid = int(pid_str)
            except (TypeError, ValueError):
                continue
            ns = by_prod.get(pid, [])
            shared = Product.query.get(pid)
            if not shared or len({_dn(x) for x in ns}) < 2:
                continue
            groups = defaultdict(list)
            for x in ns:
                groups[_dn(x)].append(x)
            for gnodes in groups.values():
                first = gnodes[0]
                disp = first.display_name or (first.item.name if first.item else 'Parça')
                src_type = (first.item.type if first.item else None) or shared.type or 'hammadde'
                src_unit = first.unit_type or (first.item.unit_type if first.item else None) or shared.unit_type or 'adet'
                code = _gen_code(disp)
                base, k = code, 1
                while Product.query.filter_by(code=code).first():
                    k += 1
                    code = f'{base}-{k}'
                newp = Product(code=code, name=disp, type=src_type,
                               unit_type=src_unit, current_stock=0, unit_cost=0,
                               currency=shared.currency or 'TRY')
                db.session.add(newp)
                db.session.flush()
                newi = BomItem(code=code, name=disp, type=src_type,
                               unit_type=src_unit, product_id=newp.id)
                db.session.add(newi)
                db.session.flush()
                for x in gnodes:
                    x.item_id = newi.id
                created += 1
                relinked += len(gnodes)
        if created:
            db.session.commit()
            flash(f'{created} yeni kart açıldı, {relinked} parça (düğüm) ayrıştırıldı. '
                  f'Şimdi fiyatları hızlıca girebilirsin.', 'success')
            return redirect(url_for('production.card_prices'))
        db.session.rollback()
        flash('Ayrıştırılacak kart seçilmedi.', 'info')
        return redirect(url_for('production.shared_card_split'))

    # GET: bir karta bağlı FARKLI görünen adlı ≥2 düğüm = aşırı paylaşılan kart
    rows = []
    shared_ids = [pid for pid, ns in by_prod.items()
                  if len({_dn(x) for x in ns}) >= 2]
    if shared_ids:
        prods = {p.id: p for p in Product.query.filter(Product.id.in_(shared_ids)).all()}
        for pid in shared_ids:
            p = prods.get(pid)
            if not p:
                continue
            ns = by_prod[pid]
            names, seen = [], set()
            for x in ns:
                key = _dn(x)
                if key not in seen:
                    seen.add(key)
                    names.append(x.display_name or (x.item.name if x.item else ''))
            rows.append({
                'product_id': pid,
                'card_name': p.name, 'card_code': p.code,
                'unit_cost': float(p.unit_cost or 0),
                'distinct': len(names),
                'total_items': len(ns),
                'samples': names[:8],
                'more': max(0, len(names) - 8),
            })
    rows.sort(key=lambda x: -x['distinct'])
    return render_template('production/shared_card_split.html',
                           rows=rows, total=len(rows))


@production_bp.route('/shared-card-split/<int:pid>', methods=['GET', 'POST'])
@login_required
@roles_required('Genel', 'Yönetici')
def shared_card_split_detail(pid):
    """Tek bir ortak kartın altındaki parçaları TEK TEK, doğru kodu girerek
    ayrıştırma. Girilen kod mevcut bir kartla eşleşirse o karta bağlar (yeni
    açmaz); eşleşmezse yeni kart açar. Her parça için yeni BomItem oluşturulup
    ilgili düğümler ona taşınır. Node/edge/ağaç yapısı değişmez."""
    import re as _re
    from collections import defaultdict
    from app.models import BomNode, BomItem, Product
    from sqlalchemy.orm import joinedload

    def _gen_code(name):
        tr = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')
        s = _re.sub(r'[^A-Za-z0-9]+', '-', (name or '').translate(tr)).strip('-').upper()
        return ('AYR-' + s)[:45] if s else 'AYR-PARCA'

    def _norm(s):
        return _re.sub(r'\s+', ' ', (s or '').strip()).lower()

    shared = Product.query.get_or_404(pid)
    nodes = (BomNode.query
             .options(joinedload(BomNode.item))
             .join(BomItem, BomNode.item_id == BomItem.id)
             .filter(BomItem.product_id == pid).all())

    if request.method == 'POST':
        created = reused = relinked = 0
        for i in request.form.getlist('row_index'):
            if request.form.get(f'inc_{i}') != '1':
                continue
            node_ids = [int(x) for x in (request.form.get(f'nodes_{i}') or '').split(',')
                        if x.strip().isdigit()]
            if not node_ids:
                continue
            name = (request.form.get(f'name_{i}') or 'Parça').strip() or 'Parça'
            ptype = (request.form.get(f'type_{i}') or shared.type or 'hammadde').strip()
            unit = (request.form.get(f'unit_{i}') or 'adet').strip() or 'adet'
            code = (request.form.get(f'code_{i}') or '').strip() or _gen_code(name)
            try:
                price = float(request.form.get(f'price_{i}') or 0)
            except (TypeError, ValueError):
                price = 0.0
            existing = Product.query.filter_by(code=code).first()
            if existing:
                target = existing
                reused += 1
            else:
                target = Product(code=code, name=name, type=ptype, unit_type=unit,
                                 current_stock=0, unit_cost=0,
                                 currency=shared.currency or 'TRY')
                db.session.add(target)
                db.session.flush()
                created += 1
            if price > 0:
                target.unit_cost = price  # bu ekranda girilen birim fiyat kartı fiyatlar
            newi = BomItem(code=code, name=name, type=ptype, unit_type=unit,
                           product_id=target.id)
            db.session.add(newi)
            db.session.flush()
            for n in BomNode.query.filter(BomNode.id.in_(node_ids)).all():
                n.item_id = newi.id
                relinked += 1
        if created or reused:
            db.session.commit()
            flash(f'{relinked} parça ayrıştırıldı ({created} yeni kart, '
                  f'{reused} mevcut karta bağlandı).', 'success')
            return redirect(url_for('production.shared_card_split'))
        db.session.rollback()
        flash('Seçim yapılmadı.', 'info')
        return redirect(url_for('production.shared_card_split_detail', pid=pid))

    # GET: parçaları görünen ada göre grupla
    groups = {}
    for n in nodes:
        key = _norm(n.display_name or (n.item.name if n.item else ''))
        g = groups.get(key)
        if not g:
            g = groups[key] = {
                'name': n.display_name or (n.item.name if n.item else 'Parça'),
                'unit': n.unit_type or (n.item.unit_type if n.item else 'adet') or 'adet',
                'type': (n.item.type if n.item else None) or shared.type or 'hammadde',
                'node_ids': [],
            }
        g['node_ids'].append(n.id)
    parts = []
    for g in groups.values():
        parts.append({
            'name': g['name'], 'unit': g['unit'], 'type': g['type'],
            'code': _gen_code(g['name']), 'count': len(g['node_ids']),
            'node_ids': ','.join(str(x) for x in g['node_ids']),
        })
    parts.sort(key=lambda x: x['name'].lower())
    return render_template('production/shared_card_split_detail.html',
                           shared=shared, parts=parts, total=len(parts))


@production_bp.route('/card-prices', methods=['GET', 'POST'])
@login_required
@roles_required('Genel', 'Yönetici')
def card_prices():
    """Fiyatsız (unit_cost<=0) ve BOM'da kullanılan stok kartlarına hızlı toplu
    birim fiyat girişi. Yalnızca değer yazdığın satırlar kaydedilir."""
    from sqlalchemy import or_
    from app.models import Product, BomItem

    if request.method == 'POST':
        updated = 0
        for key, val in request.form.items():
            if not key.startswith('price_'):
                continue
            try:
                pid = int(key[6:])
                price = float(val or 0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            p = Product.query.get(pid)
            if p:
                p.unit_cost = price
                updated += 1
        if updated:
            db.session.commit()
            flash(f'{updated} kartın fiyatı girildi.', 'success')
        else:
            flash('Fiyat girilmedi.', 'info')
        return redirect(url_for('production.card_prices', page=request.args.get('page', 1)))

    used_ids = {row[0] for row in BomItem.query
                .with_entities(BomItem.product_id)
                .filter(BomItem.product_id.isnot(None)).distinct().all()}
    prods = [p for p in Product.query.filter(
                Product.is_active == True,
                or_(Product.unit_cost.is_(None), Product.unit_cost <= 0))
             .order_by(Product.name).all()
             if p.id in used_ids]

    per = 200
    total = len(prods)
    pages = max(1, (total + per - 1) // per)
    page = min(max(1, request.args.get('page', 1, type=int)), pages)
    page_prods = prods[(page - 1) * per: page * per]
    return render_template('production/card_prices.html',
                           prods=page_prods, page=page, pages=pages, total=total)


@production_bp.route('/substitution-audit', methods=['GET', 'POST'])
@login_required
@roles_required('Genel', 'Yönetici')
def substitution_audit():
    """İkame kart denetimi. Kendi geçerli fiyatı OLMAYAN (unit_cost<=0) hammadde
    kalemleri, maliyette başka bir kartın fiyatıyla (İKAME) gösterilir. Bu sayfa
    o kalemleri listeler; kalemin GERÇEK birim fiyatını girip 'ikameyi kaldır' —
    fiyat girilince sistem artık kartın kendi fiyatını kullanır, ikame kalkar."""
    from app.models import BomItem, BomNode, Product
    from app.utils.bom_utils import _find_costing_raw_material
    from sqlalchemy.orm import joinedload

    candidates = Product.query.filter(Product.is_active == True,
                                      Product.type == 'hammadde').all()

    if request.method == 'POST':
        updated = 0
        for raw in request.form.getlist('product_id'):
            try:
                pid = int(raw)
            except (TypeError, ValueError):
                continue
            if request.form.get(f'inc_{pid}') != '1':
                continue
            try:
                price = float(request.form.get(f'price_{pid}') or 0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            p = Product.query.get(pid)
            if not p:
                continue
            p.unit_cost = price
            cur = (request.form.get(f'cur_{pid}') or '').strip().upper()
            if cur:
                p.currency = cur[:10]
            updated += 1
        if updated:
            db.session.commit()
            flash(f'{updated} kartın fiyatı güncellendi; bu kalemlerde ikame kalktı.', 'success')
        else:
            db.session.rollback()
            flash('Uygulanacak fiyat girişi bulunamadı.', 'info')
        return redirect(url_for('production.substitution_audit'))

    # GET: kendi fiyatı olmayan ama ikame ile fiyatlanan hammadde kalemleri
    items = (BomItem.query
             .options(joinedload(BomItem.product))
             .filter(BomItem.type == 'hammadde', BomItem.product_id.isnot(None)).all())
    groups = {}
    for it in items:
        product = it.product
        if not product or (product.unit_cost and product.unit_cost > 0):
            continue  # kartın kendi fiyatı var → ikame yok
        fallback = _find_costing_raw_material({
            'name': it.name, 'unit_type': it.unit_type, 'weight_per_unit': 0,
            'material': (product.material or it.name or ''), 'is_auto_hammadde': True,
        }, exclude_product_id=product.id, candidates=candidates)
        if not (fallback and fallback.unit_cost and fallback.unit_cost > 0):
            continue  # ikame edilmiyorsa listeye alma
        g = groups.get(product.id)
        if not g:
            g = groups[product.id] = {
                'product_id': product.id,
                'own_name': product.name, 'own_code': product.code,
                'own_currency': product.currency or 'TRY',
                'sub_code': fallback.code, 'sub_name': fallback.name,
                'sub_price': float(fallback.unit_cost), 'sub_currency': fallback.currency or 'TRY',
                'items': 0,
            }
        g['items'] += 1

    rows = sorted(groups.values(), key=lambda x: -x['sub_price'])
    return render_template('production/substitution_audit.html',
                           rows=rows, total=len(rows))


@production_bp.route('/unlinked-fix', methods=['GET', 'POST'])
@login_required
@roles_required('Genel', 'Yönetici')
def unlinked_fix():
    """FAZ 1: BOM'da stok kartı olmayan (unlinked) parçalara önizlemeli olarak
    toplu Product kartı oluşturur ve bağlı BomItem satırlarını bağlar."""
    import re as _re
    from app.models import BomItem, Product

    def _gen_code(name):
        tr = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')
        s = _re.sub(r'[^A-Za-z0-9]+', '-', (name or '').translate(tr)).strip('-').upper()
        return ('OTO-' + s)[:45] if s else 'OTO-PARCA'

    if request.method == 'POST':
        created = linked = 0
        for idx in request.form.getlist('row_index'):
            if request.form.get(f'include_{idx}') != '1':
                continue
            name = (request.form.get(f'name_{idx}') or '').strip()
            if not name:
                continue
            ptype = (request.form.get(f'type_{idx}') or 'hammadde').strip() or 'hammadde'
            unit = (request.form.get(f'unit_{idx}') or 'adet').strip() or 'adet'
            code = (request.form.get(f'code_{idx}') or '').strip() or _gen_code(name)
            # kodu benzersizle
            base, n = code, 1
            while Product.query.filter_by(code=code).first():
                n += 1
                code = f'{base}-{n}'
            prod = Product(code=code, name=name, type=ptype, unit_type=unit, current_stock=0)
            db.session.add(prod)
            db.session.flush()
            created += 1
            linked += BomItem.query.filter(
                BomItem.product_id.is_(None), BomItem.name == name
            ).update({'product_id': prod.id, 'type': ptype, 'unit_type': unit},
                     synchronize_session=False)
        db.session.commit()
        flash(f'{created} kart oluşturuldu, {linked} BOM satırı bağlandı.', 'success')
        return redirect(url_for('production.unlinked_fix'))

    # GET: kartsız BomItem'leri isme göre grupla
    items = BomItem.query.filter(BomItem.product_id.is_(None)).all()
    groups = {}
    for it in items:
        name = (it.name or '').strip()
        if not name:
            continue
        g = groups.setdefault(name.lower(), {
            'name': name, 'code': (it.code or '').strip(),
            'type': (it.type or 'hammadde').strip() or 'hammadde',
            'unit': (it.unit_type or 'adet').strip() or 'adet', 'count': 0})
        g['count'] += 1
        if not g['code'] and it.code:
            g['code'] = it.code.strip()

    ph_words = ('yari mamul', 'montaj', 'dolu malzeme', 'sarf malzeme', 'resim')
    rows = []
    for g in sorted(groups.values(), key=lambda x: -x['count']):
        low = g['name'].lower().replace('ı', 'i')
        g['is_placeholder'] = any(w in low for w in ph_words)
        rows.append(g)
    return render_template('production/unlinked_fix.html', rows=rows)


@production_bp.route('/weight-fill', methods=['GET', 'POST'])
@login_required
@roles_required('Genel', 'Yönetici')
def weight_fill():
    """FAZ 2B (elle): Ağırlığı eksik BOM düğümlerine elle parça-başı ağırlık girilir.
    Girilen değer node.weight_per_unit'e yazılır; üretim bunu kg/metre çevriminde kullanır."""
    from app.models import BomNode

    if request.method == 'POST':
        mode = request.form.get('mode', 'piece')  # piece = parça başı, total = satır toplamı ÷ adet
        saved = 0
        for nid in request.form.getlist('node_id'):
            raw = (request.form.get(f'w_{nid}') or '').strip().replace(',', '.')
            if not raw:
                continue
            try:
                val = float(raw)
            except ValueError:
                continue
            if val <= 0:
                continue
            node = BomNode.query.get(int(nid))
            if not node:
                continue
            if mode == 'total':
                pc = float(node.piece_count or node.quantity or 1) or 1.0
                val = val / pc
            node.weight_per_unit = round(val, 4)
            saved += 1
        db.session.commit()
        flash(f'{saved} parçanın ağırlığı kaydedildi.', 'success')
        return redirect(url_for('production.weight_fill'))

    # GET: eksik ağırlıklı düğümleri BOM'a göre grupla
    roots = BomNode.query.filter_by(level=0).all()
    groups, seen = [], set()
    for root in roots:
        try:
            exp = explode_bom_materials(root.bom_id, root.id, 1, db)
        except Exception:
            continue
        rows = []
        for m in exp.get('missing_weight', []):
            nid = m.get('node_id')
            if not nid or nid in seen:
                continue
            seen.add(nid)
            node = BomNode.query.get(nid)
            if not node:
                continue
            prod = node.item.product if node.item else None
            rows.append({
                'node_id': nid, 'num': node.num,
                'name': m.get('name') or node.display_name,
                'code': m.get('product_code') or '',
                'unit': (prod.unit_type if prod else '') or '',
                'adet': float(node.piece_count or node.quantity or 1),
                'current': float(node.weight_per_unit or 0),
            })
        if rows:
            groups.append({'label': root.display_name or f'BOM #{root.bom_id}', 'rows': rows})
    total_rows = sum(len(g['rows']) for g in groups)
    return render_template('production/weight_fill.html', groups=groups, total_rows=total_rows)


@production_bp.route('/bom/<int:bom_id>/sync-prices', methods=['POST'])
@login_required
@roles_required('YÃ¶netici', 'Genel')
def bom_sync_prices(bom_id):
    from app.models import BomNode, BomItem, Product

    try:
        root_node = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
        if not root_node:
            flash(f'BOM #{bom_id} bulunamadi.', 'error')
            return redirect(url_for('production.bom_list'))
        if not current_app.config.get('PURCHASING_API_BASE_URL'):
            flash('Satinalma API adresi tanimli degil. PURCHASING_API_BASE_URL ayarini ekleyin.', 'error')
            return redirect(url_for('production.bom_tree', bom_id=bom_id))

        products = (
            Product.query
            .join(BomItem, BomItem.product_id == Product.id)
            .join(BomNode, BomNode.item_id == BomItem.id)
            .filter(BomNode.bom_id == bom_id, Product.is_active == True)
            .distinct()
            .all()
        )

        product_codes = [product.code for product in products if product.code]
        price_map = {}
        price_map_loaded = False
        try:
            price_map = _fetch_purchasing_price_map(product_codes)
            price_map_loaded = True
        except Exception as exc:
            current_app.logger.warning("Bulk purchasing price fetch failed: %s", exc)
            flash(f'Toplu fiyat listesi alinamadi, urunler tek tek kontrol ediliyor: {exc}', 'warning')

        updated = 0
        failed = []
        skipped = 0
        for product in products:
            if not product.code:
                skipped += 1
                continue
            try:
                price = price_map.get(product.code)
                if not price and price_map_loaded:
                    failed.append(f'{product.code}: Satinalma fiyat kaydi bulunamadi')
                    continue
                if not price:
                    price = _fetch_purchasing_price(product.code)
            except Exception as exc:
                failed.append(f'{product.code}: {exc}')
                continue

            product.unit_cost = price['unit_cost']
            product.currency = price.get('currency') or product.currency or 'TRY'
            if price.get('vat_rate') is not None:
                product.vat_rate = float(price['vat_rate'])
            updated += 1

        if updated:
            db.session.commit()
        else:
            db.session.rollback()

        if updated:
            flash(f'{updated} urunun fiyati satinalma API uzerinden guncellendi.', 'success')
        if skipped:
            flash(f'{skipped} urun kodu olmadigi icin atlandi.', 'warning')
        if failed:
            sample = '; '.join(failed[:5])
            more = f' (+{len(failed) - 5} kayit)' if len(failed) > 5 else ''
            flash(f'{len(failed)} urun icin fiyat alinamadi: {sample}{more}', 'warning')
        if not updated and not skipped and not failed:
            flash('Bu BOM icin guncellenecek bagli urun bulunamadi.', 'info')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("BOM price sync failed")
        flash(f'Fiyat guncelleme sirasinda hata olustu: {exc}', 'error')

    return redirect(url_for('production.bom_tree', bom_id=bom_id))

@production_bp.route('/bom/<int:bom_id>/download_excel')
@production_bp.route('/bom/<int:bom_id>/download_excel/<int:node_id>')
@login_required
@roles_required('Genel', 'Yönetici')
def bom_download_excel(bom_id, node_id=None):
    """
    BOM ağacını veya belirli bir alt ağacı Excel dosyası olarak indir.
    
    Args:
        bom_id: BOM ID
        node_id: (Opsiyonel) Belirli bir düğüm ID'si - verilirse sadece o alt ağaç indirilir
    """
    try:
        if node_id:
            # Belirli bir düğümden başlayan alt ağacı al
            subtree = get_bom_subtree(bom_id, node_id, db)
            
            if not subtree.get('node'):
                flash(f'Düğüm #{node_id} bulunamadı.', 'error')
                return redirect(url_for('production.bom_tree', bom_id=bom_id))
            
            node_info = {
                'id': subtree['node']['id'],
                'num': subtree['node']['num'],
                'name': subtree['node']['name']
            }
            
            excel_file = create_bom_tree_excel(subtree, bom_id, node_info=node_info)
            # Dosya adını düğüm numarasına göre oluştur
            safe_name = subtree['node']['num'].replace('.', '_')
            filename = f'BOM_{bom_id}_{safe_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        else:
            # Tüm ağacı al
            tree = get_bom_tree(bom_id, db)
            
            if not tree.get('roots'):
                flash(f'BOM #{bom_id} bulunamadı veya boş.', 'error')
                return redirect(url_for('production.bom_list'))
            
            excel_file = create_bom_tree_excel(tree, bom_id)
            filename = f'BOM_{bom_id}_Agac_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Excel oluşturulurken hata: {str(e)}', 'error')
        return redirect(url_for('production.bom_tree', bom_id=bom_id))


@production_bp.route('/bom/<int:bom_id>/delete', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def bom_delete(bom_id):
    """Bir BOM'un tüm düğüm ve edge'lerini sil; önce hangi ürünlerin
    güvenle pasifleştirilebileceğini gösteren bir önizleme sunar."""
    from app.models import BomNode, BomEdge, Product

    root_node = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
    if not root_node:
        flash(f'BOM #{bom_id} bulunamadı.', 'error')
        return redirect(url_for('production.bom_list'))

    if request.method == 'POST':
        deactivate_ids = request.form.getlist('deactivate_ids', type=int)
        deactivated_count = 0
        if deactivate_ids:
            deactivated_count = (
                Product.query
                .filter(Product.id.in_(deactivate_ids))
                .update({'is_active': False}, synchronize_session=False)
            )

        BomEdge.query.filter_by(bom_id=bom_id).delete()
        BomNode.query.filter_by(bom_id=bom_id).delete()
        db.session.commit()

        flash(
            f'BOM #{bom_id} silindi.'
            + (f' {deactivated_count} ürün pasifleştirildi.' if deactivated_count else ''),
            'success'
        )
        return redirect(url_for('production.bom_list'))

    analysis = analyze_bom_delete(bom_id, db)
    return render_template(
        'production/bom_delete_preview.html',
        bom_id=bom_id,
        root_name=root_node.display_name,
        analysis=analysis
    )

@production_bp.route('/bom/<int:bom_id>/produce/<int:node_id>', methods=['GET', 'POST'])
@login_required
@roles_required('Yönetici')
def bom_produce(bom_id, node_id):
    from app.models import BomNode, BomEdge
    bom_node = BomNode.query.filter_by(id=node_id, bom_id=bom_id).first_or_404()

    # Kendi ürünü (üretilecek hedef)
    target_product = bom_node.item.product if bom_node.item else None
    if not target_product:
        flash('Bu düğümün bağlı olduğu bir ana ürün(Product) yok. Üretim yapılamaz.', 'error')
        return redirect(url_for('production.bom_tree', bom_id=bom_id))

    has_children = BomEdge.query.filter_by(bom_id=bom_id, parent_node_id=node_id).first() is not None
    if not has_children:
        flash('Bu düğümün hiç alt bileşeni (malzemesi) yok, üretim yapılamaz. Önce BOM detayını içe aktarın.', 'error')
        return redirect(url_for('production.bom_tree', bom_id=bom_id))

    # Kullanıcı sadece "Üret" dediğinde doğrudan üretim formu açılacak.
    # GET: Gerekli malzemeleri göster
    if request.method == 'GET':
        explosion = explode_bom_materials(bom_id, node_id, 1, db)
        materials = []
        for item in explosion['materials']:
            child = item['node']
            c_product = item['product']
            materials.append({
                'child_node': child,
                'product': c_product,
                'req_qty_per_unit': item['quantity'],
                'stock': (c_product.current_stock or 0) if c_product else 0
            })
        return render_template('production/bom_produce.html',
                               bom_node=bom_node,
                               target_product=target_product,
                               materials=materials,
                               unlinked=explosion['unlinked'],
                               missing_weight=explosion['missing_weight'])

    # POST: Üretimi gerçekleştir
    quantity = request.form.get('quantity', type=float, default=1.0)
    note = request.form.get('note', '')

    if quantity <= 0:
        flash('Üretim miktarı sıfırdan büyük olmalıdır.', 'error')
        return redirect(url_for('production.bom_produce', bom_id=bom_id, node_id=node_id))

    explosion = explode_bom_materials(bom_id, node_id, quantity, db)

    # 1. Stok yetiyor mu kontrolü
    insufficient = []
    required_consumptions = [] # [(product, total_req_qty, child_node)]
    for item in explosion['materials']:
        child = item['node']
        c_product = item['product']
        total_req = float(item['quantity'])
        c_stock = float(c_product.current_stock or 0)
        if c_stock < total_req:
            insufficient.append(f"{c_product.name} (Gereken: {total_req:.2f}, Mevcut: {c_stock})")
        else:
            required_consumptions.append((c_product, total_req, child))

    if insufficient:
        _limited_flash_list('Yetersiz stok:', insufficient)
        return redirect(url_for('production.bom_produce', bom_id=bom_id, node_id=node_id))

    if explosion['unlinked']:
        names = [f"{u['num']} {u['name']}" for u in explosion['unlinked']]
        _limited_flash_list(
            'Stok kartı bulunamadığı için sarf edilemeyen malzemeler var (üretim yine de kaydedildi):',
            names, category='warning'
        )

    if explosion['missing_weight']:
        names = [f"{u['num']} {u['name']} ({u['product_code']})" for u in explosion['missing_weight']]
        _limited_flash_list(
            'Ağırlık verisi eksik olduğu için sarf edilemeyen malzemeler var (üretim yine de kaydedildi, bu malzemeleri BOM\'da kontrol edin):',
            names, category='warning'
        )

    # 2. Üretim kaydı oluştur
    production = None
    if _production_records_support_product_id():
        production = ProductionRecord(
            bom_id=bom_id,
            bom_node_id=node_id,
            product_id=target_product.id,
            quantity=quantity,
            user_id=current_user.id,
            note=note
        )
        db.session.add(production)
        db.session.flush()

    # 3. Stoğu Düş ve Tüketim Kaydı oluştur (Kullanılan Alt Bileşenler İçin)
    for c_product, total_req, child_node in required_consumptions:
        # Stoğu düş
        c_product.current_stock = float(c_product.current_stock or 0) - total_req
        
        # Tüketim detayı (Üretim emri ile ilişkilendirme)
        if production:
            consumption = ProductionConsumption(
                production_id=production.id,
                product_id=c_product.id,
                quantity=total_req
            )
            db.session.add(consumption)
        
        # Stok hareketi (Çıkış)
        movement_out = StockMovement(
            product_id=c_product.id,
            movement_type='cikis',
            quantity=total_req,
            source='Depo',
            destination=f'Üretim - {bom_node.display_name}',
            note=f'Yarı Mamul/Mamul Üretimi için harcandı. Üretilen: {bom_node.display_name} ({quantity} adet)',
            user_id=current_user.id
        )
        db.session.add(movement_out)

    # 4. Stoğu Artır (Üretilen Yarı Mamul/Mamul İçin)
    target_product.current_stock = float(target_product.current_stock or 0) + quantity
    movement_in = StockMovement(
        product_id=target_product.id,
        movement_type='giris',
        quantity=quantity,
        source=f'Üretim Hattı - {bom_node.display_name}',
        destination='Depo',
        note=f'Üretim Tamamlandı. Giren Miktar: {quantity}',
        user_id=current_user.id
    )
    db.session.add(movement_in)

    db.session.commit()
    flash(f'Başarıyla {quantity} adet {bom_node.display_name} üretildi ve stoka girdi.', 'success')
    return redirect(url_for('production.bom_tree', bom_id=bom_id))



@production_bp.route('/work_order', methods=['GET', 'POST'])
@login_required
def work_order():
    from app.models import Category, Product, BomNode, BomEdge, ProductionRecord, ProductionConsumption, StockMovement
    from flask_login import current_user
    
    root_nodes = BomNode.query.filter_by(level=0).all()
    categories = Category.query.all()
    
    if request.method == 'GET':
        return render_template('production/work_order.html', 
                               root_nodes=root_nodes, 
                               categories=categories)
                               
    bom_id = request.form.get('bom_id', type=int)
    quantity = request.form.get('quantity', type=float, default=1.0)
    note = request.form.get('note', '')
    
    if quantity <= 0:
        flash('Miktar pozitif olmalı.', 'error')
        return redirect(url_for('production.work_order'))
        
    root_node = BomNode.query.filter_by(bom_id=bom_id, level=0).first()
    if not root_node:
        flash('Geçersiz BOM ID', 'error')
        return redirect(url_for('production.work_order'))
        
    target_product = root_node.item.product if root_node.item else None

    if not target_product:
        flash('Bu BOM ağacında bir ana ürün (Product) eşleşmesi yok.', 'error')
        return redirect(url_for('production.work_order'))

    has_children = BomEdge.query.filter_by(bom_id=bom_id, parent_node_id=root_node.id).first() is not None
    if not has_children:
        flash('Bu BOM ağacının hiç alt bileşeni (malzemesi) yok, üretim yapılamaz. Önce BOM detayını içe aktarın.', 'error')
        return redirect(url_for('production.work_order'))

    explosion = explode_bom_materials(bom_id, root_node.id, quantity, db)

    insufficient = []
    consume_list = []
    for item in explosion['materials']:
        p = item['product']
        req = float(item['quantity'])
        p_stock = float(p.current_stock or 0)
        if p_stock < req:
            insufficient.append(f"{p.name} (Eksik: {req - p_stock:.2f})")
        else:
            consume_list.append((p, req))

    if insufficient:
        _limited_flash_list('Yetersiz stoklar:', insufficient)
        return redirect(url_for('production.work_order'))

    if explosion['unlinked']:
        names = [f"{u['num']} {u['name']}" for u in explosion['unlinked']]
        _limited_flash_list(
            'Stok kartı bulunamadığı için sarf edilemeyen malzemeler var (üretim yine de kaydedildi):',
            names, category='warning'
        )

    if explosion['missing_weight']:
        names = [f"{u['num']} {u['name']} ({u['product_code']})" for u in explosion['missing_weight']]
        _limited_flash_list(
            'Ağırlık verisi eksik olduğu için sarf edilemeyen malzemeler var (üretim yine de kaydedildi, bu malzemeleri BOM\'da kontrol edin):',
            names, category='warning'
        )

    # 1. Deduct Materials
    for p, req in consume_list:
        p.current_stock = float(p.current_stock or 0) - float(req)
        movement = StockMovement(
            product_id=p.id,
            movement_type='cikis',
            quantity=req,
            source='Depo',
            destination=f'Üretim - {root_node.display_name}',
            note=f'Üretim sarfiyatı (BOM #{bom_id}, Miktar: {quantity})',
            user_id=current_user.id
        )
        db.session.add(movement)
        
    # 2. Add Target Product
    target_product.current_stock = float(target_product.current_stock or 0) + quantity
    mov_in = StockMovement(
        product_id=target_product.id,
        movement_type='giris',
        quantity=quantity,
        source=f'Üretim Hattı - {root_node.display_name}',
        destination='Depo',
        note=f'Üretimden giriş (BOM #{bom_id})',
        user_id=current_user.id
    )
    db.session.add(mov_in)
    
    # 3. Production Record
    pr = None
    if _production_records_support_product_id():
        pr = ProductionRecord(
            bom_id=bom_id,
            bom_node_id=root_node.id,
            product_id=target_product.id,
            quantity=quantity,
            note=note,
            user_id=current_user.id
        )
        db.session.add(pr)
        db.session.flush()

    if pr:
        for p, req in consume_list:
            pc = ProductionConsumption(
                production_id=pr.id,
                product_id=p.id,
                quantity=float(req)
            )
            db.session.add(pc)
        
    db.session.commit()
    flash(f"{target_product.name} için {quantity} adet üretim başarıyla tamamlandı.", 'success')
    return redirect(url_for('production.index'))


# ==================== İSİM STANDARTLAŞTIRMA (Aynı kod, farklı isim) ====================

@production_bp.route('/standardize-preview')
@login_required
@roles_required('Yönetici')
def standardize_preview():
    """Bir parça koduna ait isim varyantlarını gösterip kanonik isim seçtirir."""
    code = request.args.get('code', '')
    if not code:
        flash('Kod belirtilmedi.', 'error')
        return redirect(url_for('reports.catalog_consistency'))

    preview = preview_standardize_name(code, db)
    if preview.get('error'):
        flash(preview['error'], 'error')
        return redirect(url_for('reports.catalog_consistency'))

    return render_template('production/standardize_preview.html', preview=preview)


@production_bp.route('/standardize-confirm', methods=['POST'])
@login_required
@roles_required('Yönetici')
def standardize_confirm():
    """Seçilen kanonik ismi, kodun geçtiği tüm BOM düğümlerine uygular.
    Grup birden fazla farklı ürüne dağılmışsa ve kullanıcı onayladıysa,
    o ürünleri de tek üründe birleştirir (başka BOM ağaçlarında kullanılsalar
    bile — birleştirme product_id ilişkisi üzerinden çalışır)."""
    code = request.form.get('code', '')
    canonical_name = request.form.get('canonical_name', '').strip()
    merge_products_too = request.form.get('merge_products') == 'on'
    canonical_product_id = request.form.get('canonical_product_id', type=int)

    if not code or not canonical_name:
        flash('Kod veya kanonik isim eksik.', 'error')
        return redirect(url_for('reports.catalog_consistency'))

    result = standardize_bom_item_name(
        code, canonical_name, db,
        merge_products_too=merge_products_too,
        canonical_product_id=canonical_product_id,
    )
    if result.get('error'):
        flash(result['error'], 'error')
    else:
        message = (
            f'"{canonical_name}" ismi {result["updated_nodes"]} BOM düğümüne uygulandı'
            + (f', {result["merged_items"]} yinelenen kayıt birleştirildi' if result['merged_items'] else '')
            + (', bağlı ürün kartının ismi de güncellendi' if result['product_renamed'] else '')
        )
        mp = result.get('merged_products')
        if mp and not mp.get('error'):
            message += f'. Ayrıca {mp["merged"]} ürün, {mp["canonical_code"]} koduna birleştirildi (başka BOM ağaçlarında da geçerli).'
        else:
            message += '.'
        flash(message, 'success')
    return redirect(url_for('reports.catalog_consistency'))


@production_bp.route('/standardize-bulk', methods=['POST'])
@login_required
@roles_required('Yönetici')
def standardize_bulk():
    """Rapor sayfasında işaretlenen 'basit' (tek ürüne bağlı) kodları, sistemin
    önerdiği kanonik isimle tek işlemde standartlaştırır. Riskli (birden fazla
    farklı ürüne dağılmış) gruplar önizleme ekranında zaten işaretsiz gelir;
    formda gönderilmemişse burada da atlanır — ürün birleştirmesi gerektiren
    gruplar için ürün birleştirme yapılmaz, sadece tek-ürünlü basit gruplar
    işlenir."""
    group_indices = request.form.getlist('group_selected', type=int)

    if not group_indices:
        flash('Standartlaştırılacak kod seçilmedi.', 'warning')
        return redirect(url_for('reports.catalog_consistency'))

    standardized = 0
    skipped = []

    for gi in group_indices:
        code = request.form.get(f'std_{gi}_code', '')
        canonical_name = request.form.get(f'std_{gi}_name', '').strip()

        if not code or not canonical_name:
            skipped.append(gi)
            continue

        result = standardize_bom_item_name(code, canonical_name, db, merge_products_too=False)
        if result.get('error'):
            skipped.append(gi)
        else:
            standardized += 1

    flash(
        f'{standardized} kod standartlaştırıldı.'
        + (f' {len(skipped)} kod atlandı (geçersiz veri).' if skipped else ''),
        'success' if standardized else 'warning'
    )
    return redirect(url_for('reports.catalog_consistency'))


# ==================== BOM DÜZENLEME (parça ekle / çıkar / taşı) ====================

@production_bp.route('/bom/<int:bom_id>/node/<int:parent_node_id>/add', methods=['POST'])
@login_required
@roles_required('Yönetici')
def bom_node_add(bom_id, parent_node_id):
    """Seçili düğümün altına yeni bir parça ekler."""
    data = request.json or {}
    result = add_bom_node(bom_id, parent_node_id, data, db)
    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})
    return jsonify({'success': True, 'node_id': result['node_id'], 'num': result['num']})


@production_bp.route('/bom/<int:bom_id>/node/<int:node_id>/delete-node', methods=['POST'])
@login_required
@roles_required('Yönetici')
def bom_node_delete(bom_id, node_id):
    """Tek bir BOM düğümünü (ve varsa alt ağacını) siler."""
    result = delete_bom_node(bom_id, node_id, db)
    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})
    return jsonify({'success': True, 'deleted_count': result['deleted_count']})


@production_bp.route('/bom/<int:bom_id>/node/<int:node_id>/move', methods=['POST'])
@login_required
@roles_required('Yönetici')
def bom_node_move(bom_id, node_id):
    """Bir düğümü başka bir üst düğümün altına taşır."""
    data = request.json or {}
    new_parent_node_id = data.get('new_parent_node_id')
    if not new_parent_node_id:
        return jsonify({'success': False, 'error': 'Hedef üst düğüm belirtilmedi.'})
    result = move_bom_node(bom_id, node_id, int(new_parent_node_id), db)
    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']})
    return jsonify({'success': True, 'new_num': result['new_num']})
