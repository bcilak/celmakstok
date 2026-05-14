from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session, send_file
from flask_login import login_required, current_user
from app.models import Category, StockMovement, Product, ProductionRecord, ProductionConsumption
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta
from app.utils.decorators import roles_required
from app.utils.excel_utils import parse_bom_excel, create_bom_tree_excel
from app.utils.bom_utils import (
    parse_bom_excel_v2,
    import_bom_to_db,
    get_bom_tree,
    get_bom_subtree,
    list_boms,
    next_bom_id,
    analyze_bom_for_import,
)
import pickle
import os
import uuid

production_bp = Blueprint('production', __name__)

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
                    f'{stats["edges"]} ilişki oluşturuldu.',
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
    from app.models import BomNode, Product, BomItem
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
            'unit': node.unit_type
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
            if 'quantity_net' in data:
                node.quantity_net = data['quantity_net']
            if 'piece_count' in data:
                node.piece_count = data['piece_count']
            
            if item:
                if 'name' in data and data['name']:
                    item.name = data['name']
                if 'code' in data:
                    item.code = data['code']
                    
            if product:
                if 'name' in data and data['name']:
                    product.name = data['name']
                if 'material' in data:
                    product.material = data['material']
                if 'type' in data and data['type'] in ['hammadde', 'yarimamul', 'mamul', 'standart_parca', 'hazir_parca']:
                    product.type = data['type']
                if 'product_code' in data and data['product_code']:
                    existing = Product.query.filter(Product.code == data['product_code'], Product.id != product.id).first()
                    if not existing:
                        product.code = data['product_code']
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


@production_bp.route('/bom/<int:bom_id>/delete', methods=['POST'])
@login_required
@roles_required('Yönetici')
def bom_delete(bom_id):
    """Bir BOM'un tüm düğüm ve edge'lerini sil."""
    from app.models import BomNode, BomEdge
    BomEdge.query.filter_by(bom_id=bom_id).delete()
    BomNode.query.filter_by(bom_id=bom_id).delete()
    db.session.commit()
    flash(f'BOM #{bom_id} silindi.', 'success')
    return redirect(url_for('production.bom_list'))

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

    # Alt bileşenleri bul (Sadece 1 alt kademe)
    edges = BomEdge.query.filter_by(parent_node_id=node_id, bom_id=bom_id).all()
    
    # Kullanıcı sadece "Üret" dediğinde doğrudan üretim formu açılacak.
    # GET: Gerekli malzemeleri göster
    if request.method == 'GET':
        materials = []
        for edge in edges:
            child = edge.child_node
            c_product = child.item.product if child.item else None
            # brüt miktar (varsa edge.quantity, yoksa node.quantity)
            req_q = edge.quantity
            materials.append({
                'child_node': child,
                'product': c_product,
                'req_qty_per_unit': req_q,
                'stock': c_product.current_stock if c_product else 0
            })
        return render_template('production/bom_produce.html', 
                               bom_node=bom_node, 
                               target_product=target_product,
                               materials=materials)

    # POST: Üretimi gerçekleştir
    quantity = request.form.get('quantity', type=float, default=1.0)
    note = request.form.get('note', '')

    if quantity <= 0:
        flash('Üretim miktarı sıfırdan büyük olmalıdır.', 'error')
        return redirect(url_for('production.bom_produce', bom_id=bom_id, node_id=node_id))

    # 1. Stok yetiyor mu kontrolü
    insufficient = []
    required_consumptions = [] # [(product, total_req_qty, child_node)]
    for edge in edges:
        child = edge.child_node
        c_product = child.item.product if child and child.item else None
        if not c_product:
            continue
        
        total_req = float(edge.quantity) * quantity
        if c_product.current_stock < total_req:
            insufficient.append(f"{c_product.name} (Gereken: {total_req}, Mevcut: {c_product.current_stock})")
        else:
            required_consumptions.append((c_product, total_req, child))

    if insufficient:
        flash('Yetersiz stok: ' + ' | '.join(insufficient), 'error')
        return redirect(url_for('production.bom_produce', bom_id=bom_id, node_id=node_id))

    # 2. Üretim kaydı oluştur
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
        c_product.current_stock -= total_req
        
        # Tüketim detayı (Üretim emri ile ilişkilendirme)
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
    target_product.current_stock += quantity
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
        
    edges = BomEdge.query.filter_by(bom_id=bom_id).all()
    child_edges = {}
    for e in edges:
        child_edges.setdefault(e.parent_node_id, []).append(e)
        
    required_materials = {}
    
    def explode(node_id, current_qty):
        subs = child_edges.get(node_id, [])
        if not subs:
            # Leave node -> Hammadde
            n = BomNode.query.get(node_id)
            p = n.item.product if n.item else None
            # If no product linked, we just ignore it for stock (or should we raise error?)
            if p:
                required_materials[p.id] = required_materials.get(p.id, 0.0) + current_qty
        else:
            for sub in subs:
                try:    eq = float(sub.quantity)
                except: eq = 1.0
                explode(sub.child_node_id, current_qty * eq)
                
    explode(root_node.id, quantity)
    
    insufficient = []
    consume_list = []
    for pid, req in required_materials.items():
        p = Product.query.get(pid)
        if p.current_stock < req:
            insufficient.append(f"{p.name} (Eksik: {req - p.current_stock:.2f})")
        else:
            consume_list.append((p, req))
            
    if insufficient:
        flash('Yetersiz stoklar: ' + ', '.join(insufficient), 'error')
        return redirect(url_for('production.work_order'))
        
    # 1. Deduct Materials
    for p, req in consume_list:
        p.current_stock -= float(req)
        movement = StockMovement(
            product_id=p.id,
            movement_type='out',
            quantity=req,
            reason=f'Üretim Sarfiyatı (BOM #{bom_id}, Miktar: {quantity})'
        )
        db.session.add(movement)
        
    # 2. Add Target Product
    target_product.current_stock += quantity
    mov_in = StockMovement(
        product_id=target_product.id,
        movement_type='in',
        quantity=quantity,
        reason=f"Üretimden Giriş (BOM #{bom_id})"
    )
    db.session.add(mov_in)
    
    # 3. Production Record
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
