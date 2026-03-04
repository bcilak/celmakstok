from flask import Blueprint, render_template, request, Response, current_app, jsonify, session, redirect, url_for
from flask_login import login_required, current_user
from app.models import Product, Category, StockMovement, CountSession, CountItem, ProductionRecord
from app import db
from sqlalchemy import func, text
from datetime import datetime, timedelta
import csv
import io
import google.generativeai as genai
from app.utils.decorators import roles_required

reports_bp = Blueprint('reports', __name__)

def get_db_schema():
    """Veritabanı şemasını ve tablolar hakkında bilgi döndürür."""
    table_info = ""
    for table in db.metadata.sorted_tables:
        table_info += f"Table '{table.name}':\n"
        for column in table.columns:
            table_info += f"  - {column.name} ({column.type})\n"
        table_info += "\n"
    return table_info

def get_critical_stock() -> dict:
    """Stok seviyesi kritik olan veya tamamen biten ürünlerin listesini getirir."""
    products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock
    ).limit(50).all()
    
    if not products:
        return {"result": "Şu an kritik stokta veya bitmiş ürün yok."}
        
    result = []
    for p in products:
        status = "Boş" if p.current_stock <= 0 else "Kritik"
        cat_name = p.category.name if p.category else '-'
        cost_info = f"{p.unit_cost} {p.currency}" if p.unit_cost > 0 else "Bilinmiyor"
        vat_info = f"%{int(p.vat_rate)}" if p.vat_rate else "Belirtilmemiş"
        cost_with_vat = round(p.unit_cost * (1 + p.vat_rate / 100), 2) if p.unit_cost > 0 and p.vat_rate else None
        cost_vat_str = f", KDV Dahil: {cost_with_vat} {p.currency}" if cost_with_vat else ""
        
        loc_info = []
        for ls in p.location_stocks:
            if ls.quantity > 0:
                loc_info.append(f"{ls.location.name}: {ls.quantity}")
        loc_str = ", ".join(loc_info) if loc_info else "Depo/Belirsiz"
        
        result.append(f"Kod: {p.code}, Ad: {p.name} (Tip: {p.type}), Kategori: {cat_name}, Toplam Stok: {p.current_stock} {p.unit_type}, Min Stok: {p.minimum_stock}, Durum: {status}, Lokasyon Dağılımı: [{loc_str}], Birim Maliyet: {cost_info}, KDV: {vat_info}{cost_vat_str}")
    
    return {"result": result}

def search_product(keyword: str) -> dict:
    """Verilen anahtar kelimeye (keyword) göre veritabanında ürün arar ve son stoklarını getirir."""
    products = Product.query.filter(
        Product.is_active == True,
        (Product.name.ilike(f'%{keyword}%') | Product.code.ilike(f'%{keyword}%'))
    ).limit(20).all()
    
    if not products:
        return {"result": f"'{keyword}' aramasına uygun ürün bulunamadı."}
        
    result = []
    for p in products:
        cat_name = p.category.name if p.category else '-'
        cost_info = f"{p.unit_cost} {p.currency}" if p.unit_cost > 0 else "Bilinmiyor"
        vat_info = f"%{int(p.vat_rate)}" if p.vat_rate else "Belirtilmemiş"
        cost_with_vat = round(p.unit_cost * (1 + p.vat_rate / 100), 2) if p.unit_cost > 0 and p.vat_rate else None
        cost_vat_str = f", KDV Dahil: {cost_with_vat} {p.currency}" if cost_with_vat else ""
        
        loc_info = []
        for ls in p.location_stocks:
            if ls.quantity > 0:
                loc_info.append(f"{ls.location.name}: {ls.quantity}")
        loc_str = ", ".join(loc_info) if loc_info else "Depo/Belirsiz"
        
        result.append(f"Kod: {p.code}, Ad: {p.name} (Tip: {p.type}), Kategori: {cat_name}, Toplam Stok: {p.current_stock} {p.unit_type}, Min Stok: {p.minimum_stock}, Lokasyon Dağılımı: [{loc_str}], Birim Maliyet: {cost_info}, KDV: {vat_info}{cost_vat_str}")
    
    return {"result": result}

def get_recent_movements(limit: int = 20) -> dict:
    """Sisteme girilen en son stok hareketlerini (giriş, çıkış, referans belgeleri vs) getirir."""
    movements = StockMovement.query.order_by(StockMovement.date.desc()).limit(limit).all()
    if not movements:
        return {"result": "Son hareket bulunamadı."}
        
    result = []
    for m in movements:
        date_str = m.date.strftime('%Y-%m-%d %H:%M') if m.date else ""
        prod_name = m.product.name if m.product else '-'
        result.append(f"Tarih: {date_str}, Ürün: {prod_name}, Yön/Tip: {m.movement_type}, Miktar: {m.quantity}, Kaynak: {m.source or '-'}, Hedef: {m.destination or '-'}, Açıklama: {m.note or '-'}")
    return {"result": result}

def get_production_info() -> dict:
    """Veritabanındaki üretim hatları (kategoriler) ve bu hatlarda üretilebilecek makine reçeteleri hakkında özet bilgi getirir."""
    categories = Category.query.filter_by(is_active=True).all()
    if not categories:
        return {"result": "Aktif bir üretim hattı bulunamadı."}
        
    result = []
    for cat in categories:
        result.append(f"Üretim Hattı: {cat.name} (Kod: {cat.code})")
    
    return {"result": result}

def get_product_costs(keyword: str = "") -> dict:
    """Ürünlerin birim maliyetlerini ve KDV bilgilerini getirir. İsteğe bağlı olarak isim veya koda göre filtreler."""
    query = Product.query.filter(Product.is_active == True)
    if keyword:
        query = query.filter((Product.name.ilike(f'%{keyword}%')) | (Product.code.ilike(f'%{keyword}%')))
    
    products = query.limit(50).all()
    
    if not products:
        return {"result": "Maliyet bilgisi bulunamadı."}
        
    result = []
    for p in products:
        cost = f"{p.unit_cost} {p.currency}" if p.unit_cost > 0 else "Bilinmiyor"
        vat = f"%{int(p.vat_rate)}" if p.vat_rate else "Belirtilmemiş"
        result.append(f"Kod: {p.code}, Ad: {p.name}, Maliyet: {cost}, KDV: {vat}")
        
    return {"result": result}

@reports_bp.route('/ai-assistant')
@login_required
@roles_required('Genel')
def ai_assistant():
    return render_template('reports/ai_assistant.html')

@reports_bp.route('/ai-assistant/ask', methods=['POST'])
@login_required
@roles_required('Genel')
def ai_assistant_ask():
    """AJAX endpoint - AI sohbet sorgusu"""
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({'success': False, 'error': 'Soru boş olamaz.'}), 400

    query = data['query']
    # Client tarafından gelen son sohbet geçmişi (session'a yazmıyoruz)
    client_history = data.get('history', [])

    try:
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in the configuration.")

        genai.configure(api_key=api_key)

        system_instruction = """
Sen ÇELMAK firmasının Stok ve Üretim Takip sisteminde (MRP) çalışan, Türkçe konuşan Raporlama Asistanısın.

VERİ ÇEKME:
- Kullanıcı veritabanı hakkında soru sorduğunda fonksiyonları (tools) kullan.
- Maliyet/fiyat soruları için get_product_costs fonksiyonunu kullan.
- Fonksiyonları sadece gerektiğinde çağır, gereksiz yere çağırma.

SİSTEM BİLGİLERİ:
- Ürün Tipleri: "hammadde" (dışarıdan alınan), "yarimamul" (atölyede işlenen), "mamul" (bitmiş/satılabilir)
- Stoklar lokasyonlara bölünmüştür (üretim hattı, depo vb.)
- Birim Maliyet satın alma uygulamasından senkronize edilir
- KDV Dahil = Birim Maliyet × (1 + KDV/100)

CEVAP FORMATI:
- Kısa, net, doğrudan cevap ver. Gereksiz tekrar YAPMA.
- Tek bir ürün sorulduğunda madde işareti (•) ile önemli bilgileri alt alta yaz.
- 5'ten AZ ürün varsa madde işaretleri ile listele, tablo KULLANMA.
- 5'ten FAZLA ürün listelerken tablo kullanabilirsin.
- Önemli sayıları **kalın** yap.
- Asla ham json veya liste formatı gösterme, insan dostu yaz.
- Cevaba gereksiz giriş cümlesi ekleme, direkt bilgiyi ver.
        """

        tools = [get_critical_stock, search_product, get_recent_movements, get_production_info, get_product_costs]
        model = genai.GenerativeModel('gemini-2.5-flash', tools=tools, system_instruction=system_instruction)

        # Son 6 mesajı bağlam olarak kullan
        context = ""
        recent = client_history[-6:] if len(client_history) > 6 else client_history
        if recent:
            context = "Geçmiş Sohbet:\n"
            for msg in recent:
                role_name = "Kullanıcı" if msg.get('role') == 'user' else "Araç/Asistan"
                content = msg.get('content', '')[:300]  # Bağlamı kısa tut
                context += f"{role_name}: {content}\n"
            context += f"\nKullanıcının Yeni Sorusu: {query}"
        else:
            context = query

        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(context)

        try:
            answer = response.text.strip()
            if not answer:
                answer = "Veriler analiz edildi ancak sistem metin üretemedi."
        except ValueError:
            answer = "Veriler analiz edildi ancak gösterilebilir bir rapor oluşturulamadı."

        return jsonify({'success': True, 'answer': answer})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Bir hata oluştu: {str(e)}'}), 500


@reports_bp.route('/ai-assistant/clear', methods=['POST'])
@login_required
@roles_required('Genel')
def ai_assistant_clear():
    """Sohbet geçmişini temizle (eski session verisini de siler)"""
    history_key = f'chat_history_{current_user.id}'
    if history_key in session:
        del session[history_key]
        session.modified = True
    return jsonify({'success': True})


@reports_bp.route('/')
@login_required
@roles_required('Genel')
def index():
    return render_template('reports/index.html')


# ================== STOK RAPORLARI ==================

@reports_bp.route('/stock')
@login_required
@roles_required('Genel')
def stock_report():
    """Mevcut stok listesi"""
    category_id = request.args.get('category', type=int)
    
    query = Product.query.filter_by(is_active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    products = query.order_by(Product.name).all()
    categories = Category.query.all()
    
    # Özet
    total_items = len(products)
    critical_items = sum(1 for p in products if p.current_stock < p.minimum_stock)
    empty_items = sum(1 for p in products if p.current_stock <= 0)
    
    # AI summary will be fetched asynchronously.
    ai_summary = None

    return render_template('reports/stock.html',
        products=products,
        categories=categories,
        selected_category=category_id,
        total_items=total_items,
        critical_items=critical_items,
        empty_items=empty_items,
        ai_summary=ai_summary
    )

@reports_bp.route('/api/stock-summary', methods=['POST'])
@login_required
@roles_required('Genel')
def api_stock_summary():
    """Stok sayfası için asenkron AI özetini üretir"""
    data = request.json or {}
    total_items = data.get('total_items', 0)
    critical_items = data.get('critical_items', 0)
    empty_items = data.get('empty_items', 0)
    
    # Gerçek ürün isimlerini çekmek için (maksimum 15 tane kritik ürün)
    critical_products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock
    ).limit(15).all()
    
    critical_productsList = [f"{p.name} (Stok: {p.current_stock}, Min: {p.minimum_stock})" for p in critical_products]
    
    try:
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'success': False, 'message': 'API anahtarı bulunamadı.'})
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        summary_prompt = f"""
        Sen şirketin stok yöneticisisin. Aşağıda mevcut stok raporunun gerçek verileri var:
        - Toplam ürün çeşidi: {total_items}
        - Kritik stok seviyesine düşenler: {critical_items}
        - Tamamen tükenenler: {empty_items}
        
        Örnek bazı kritik/tükenen ürünler:
        {', '.join(critical_productsList) if critical_productsList else 'Kritik ürün yok!'}
        
        Lütfen yöneticilere stok durumu hakkında durum tespiti yapan ve aksiyona dönük ÖZET bir stratejik değerlendirme yaz. (En fazla 3-4 cümle, Türkçe). Çok profesyonel ol. Tablo ekleme, sadece metin.
        """
        response = model.generate_content(summary_prompt)
        ai_summary = response.text.strip()
        return jsonify({'success': True, 'summary': ai_summary})
    except Exception as e:
        return jsonify({'success': False, 'message': f"AI özet üretilemedi: {str(e)}"})

@reports_bp.route('/stock/export')
@login_required
@roles_required('Genel')
def export_stock():
    """Stok listesini CSV olarak dışa aktar"""
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Başlık
    writer.writerow(['Kod', 'Ürün Adı', 'Kategori', 'Birim', 'Mevcut Stok', 'Minimum Stok', 'Durum'])
    
    for p in products:
        status = 'Normal'
        if p.current_stock <= 0:
            status = 'Boş'
        elif p.current_stock < p.minimum_stock:
            status = 'Kritik'
        
        writer.writerow([
            p.code,
            p.name,
            p.category.name if p.category else '',
            p.unit_type,
            p.current_stock,
            p.minimum_stock,
            status
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=stok_listesi.csv'}
    )

@reports_bp.route('/critical')
@login_required
@roles_required('Genel')
def critical_report():
    """Kritik stok raporu"""
    products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock
    ).order_by(Product.current_stock).all()
    
    return render_template('reports/critical.html', products=products)

# ================== HAREKET RAPORLARI ==================

@reports_bp.route('/movements')
@login_required
@roles_required('Genel')
def movements_report():
    """Stok hareketleri raporu"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    movement_type = request.args.get('type', '')
    
    query = StockMovement.query
    
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(StockMovement.date >= start)
    
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(StockMovement.date < end)
    
    if movement_type:
        query = query.filter_by(movement_type=movement_type)
    
    movements = query.order_by(StockMovement.date.desc()).all()
    
    # Toplam giriş/çıkış
    total_in = sum(m.quantity for m in movements if m.movement_type == 'giris')
    total_out = sum(m.quantity for m in movements if m.movement_type == 'cikis')
    
    return render_template('reports/movements.html',
        movements=movements,
        start_date=start_date,
        end_date=end_date,
        movement_type=movement_type,
        total_in=total_in,
        total_out=total_out
    )

@reports_bp.route('/monthly')
@login_required
@roles_required('Genel')
def monthly_report():
    """Aylık giriş/çıkış raporu"""
    year = request.args.get('year', datetime.utcnow().year, type=int)
    month = request.args.get('month', datetime.utcnow().month, type=int)
    
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    # Günlük özet
    daily_stats = db.session.query(
        func.date(StockMovement.date).label('date'),
        StockMovement.movement_type,
        func.sum(StockMovement.quantity).label('total')
    ).filter(
        StockMovement.date >= start_date,
        StockMovement.date < end_date
    ).group_by(
        func.date(StockMovement.date),
        StockMovement.movement_type
    ).all()
    
    # Ürün bazlı özet
    product_stats = db.session.query(
        Product.id,
        Product.name,
        Product.unit_type,
        StockMovement.movement_type,
        func.sum(StockMovement.quantity).label('total')
    ).join(StockMovement).filter(
        StockMovement.date >= start_date,
        StockMovement.date < end_date
    ).group_by(
        Product.id,
        StockMovement.movement_type
    ).all()
    
    # Toplam
    total_in = db.session.query(func.sum(StockMovement.quantity)).filter(
        StockMovement.date >= start_date,
        StockMovement.date < end_date,
        StockMovement.movement_type == 'giris'
    ).scalar() or 0
    
    total_out = db.session.query(func.sum(StockMovement.quantity)).filter(
        StockMovement.date >= start_date,
        StockMovement.date < end_date,
        StockMovement.movement_type == 'cikis'
    ).scalar() or 0
    
    return render_template('reports/monthly.html',
        year=year,
        month=month,
        daily_stats=daily_stats,
        product_stats=product_stats,
        total_in=total_in,
        total_out=total_out
    )

# ================== ÜRETİM HATTI RAPORLARI ==================

@reports_bp.route('/production')
@login_required
@roles_required('Genel')
def production_report():
    """Üretim raporu - Reçetelerden yapılan üretimler"""
    category_id = request.args.get('category', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    categories = Category.query.filter_by(is_active=True).all()
    
    # Üretim kayıtlarını sorgula
    query = ProductionRecord.query
    
    if category_id:
        pass
    
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(ProductionRecord.date >= start)
    
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(ProductionRecord.date < end)
    
    productions = query.order_by(ProductionRecord.date.desc()).all()
    
    # Kategori bazlı üretim toplamları
    category_totals = {}
    for cat in categories:
        cat_productions = productions
        category_totals[cat.id] = {
            'name': cat.name,
            'count': len(cat_productions),
            'total': sum(p.quantity for p in cat_productions)
        }
    
    # Özet istatistikler
    total_productions = len(productions)
    total_quantity = sum(p.quantity for p in productions)
    
    return render_template('reports/production.html',
        categories=categories,
        productions=productions,
        category_totals=category_totals,
        selected_category=category_id,
        start_date=start_date,
        end_date=end_date,
        total_productions=total_productions,
        total_quantity=total_quantity
    )

@reports_bp.route('/top-consumption')
@login_required
@roles_required('Genel')
def top_consumption():
    """En çok tüketilen ürünler"""
    days = request.args.get('days', 30, type=int)
    limit = request.args.get('limit', 20, type=int)
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    top_products = db.session.query(
        Product.id,
        Product.code,
        Product.name,
        Product.unit_type,
        func.sum(StockMovement.quantity).label('total')
    ).join(StockMovement).filter(
        StockMovement.movement_type == 'cikis',
        StockMovement.date >= start_date
    ).group_by(Product.id).order_by(
        func.sum(StockMovement.quantity).desc()
    ).limit(limit).all()
    
    return render_template('reports/top_consumption.html',
        products=top_products,
        days=days,
        limit=limit
    )

# ================== SAYIM RAPORLARI ==================

@reports_bp.route('/counting')
@login_required
@roles_required('Genel')
def counting_report():
    """Sayım raporları"""
    sessions = CountSession.query.filter_by(status='completed').order_by(
        CountSession.completed_at.desc()
    ).all()
    
    return render_template('reports/counting.html', sessions=sessions)

@reports_bp.route('/counting/<int:id>')
@login_required
@roles_required('Genel')
def counting_detail(id):
    """Sayım detay raporu"""
    session = CountSession.query.get_or_404(id)
    
    # Farkı olan kalemler
    items_with_diff = CountItem.query.filter(
        CountItem.session_id == id,
        CountItem.is_counted == True,
        CountItem.difference != 0
    ).join(Product).order_by(Product.name).all()
    
    # Özet
    total_items = CountItem.query.filter_by(session_id=id).count()
    counted_items = CountItem.query.filter_by(session_id=id, is_counted=True).count()
    
    positive_diff = sum(i.difference for i in items_with_diff if i.difference > 0)
    negative_diff = sum(i.difference for i in items_with_diff if i.difference < 0)
    
    return render_template('reports/counting_detail.html',
        session=session,
        items=items_with_diff,
        total_items=total_items,
        counted_items=counted_items,
        positive_diff=positive_diff,
        negative_diff=negative_diff
    )

# ================== DEPO RAPORLARI ==================

@reports_bp.route('/warehouse')
@login_required
@roles_required('Genel')
def warehouse_report():
    """Depo durumu raporu"""
    categories = Category.query.all()
    
    # Kategori bazlı stok durumu
    category_stats = []
    for cat in categories:
        products = Product.query.filter_by(category_id=cat.id, is_active=True).all()
        total_items = len(products)
        total_stock = sum(p.current_stock for p in products)
        critical_items = sum(1 for p in products if p.minimum_stock > 0 and p.current_stock < p.minimum_stock)
        empty_items = sum(1 for p in products if p.current_stock <= 0)
        
        category_stats.append({
            'category': cat,
            'total_items': total_items,
            'total_stock': total_stock,
            'critical_items': critical_items,
            'empty_items': empty_items
        })
    
    # Genel özet
    total_products = Product.query.filter_by(is_active=True).count()
    total_critical = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock,
        Product.minimum_stock > 0
    ).count()
    total_empty = Product.query.filter(
        Product.is_active == True,
        Product.current_stock <= 0
    ).count()
    
    return render_template('reports/warehouse.html',
        category_stats=category_stats,
        total_products=total_products,
        total_critical=total_critical,
        total_empty=total_empty
    )

# ================== HAREKET RAPORU (Alternatif İsim) ==================

@reports_bp.route('/movement')
@login_required
@roles_required('Genel')
def movement_report():
    """Stok hareketleri raporu (alternatif URL)"""
    return movements_report()

# ================== DIŞA AKTARMA ==================

@reports_bp.route('/export/products')
@login_required
@roles_required('Genel')
def export_products():
    """Ürün listesini CSV olarak dışa aktar"""
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Kod', 'Ürün Adı', 'Kategori', 'Birim', 'Mevcut Stok', 'Minimum Stok'])
    
    for p in products:
        writer.writerow([
            p.code,
            p.name,
            p.category.name if p.category else '',
            p.unit_type,
            p.current_stock,
            p.minimum_stock
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=urunler.csv'}
    )

@reports_bp.route('/export/movements')
@login_required
@roles_required('Genel')
def export_movements():
    """Stok hareketlerini CSV olarak dışa aktar"""
    movements = StockMovement.query.order_by(StockMovement.date.desc()).limit(1000).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Tarih', 'Ürün', 'Hareket Tipi', 'Miktar', 'Kaynak', 'Hedef', 'Not'])
    
    for m in movements:
        writer.writerow([
            m.date.strftime('%Y-%m-%d %H:%M') if m.date else '',
            m.product.name if m.product else '',
            m.movement_type,
            m.quantity,
            m.source or '',
            m.destination or '',
            m.note or ''
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=hareketler.csv'}
    )

# ================== ORTAK ÜRÜNLER RAPORU ==================

@reports_bp.route('/common-products')
@login_required
@roles_required('Genel')
def common_products():
    """Tüm üretim hatlarında ortak kullanılan ürünler (somun, civata vs)"""
    # Ortak ürünleri bulmak için anahtar kelimeler
    common_keywords = ['somun', 'civata', 'pul', 'rondela', 'cıvata', 'vida', 'saplama', 
                       'perçin', 'pim', 'segman', 'conta', 'oring', 'kaynak', 'elektrot',
                       'boya', 'tiner', 'gres', 'yağ', 'zincir', 'rulman', 'bilyalı']
    
    # Her anahtar kelime için ürünleri ara
    common_products = []
    for keyword in common_keywords:
        products = Product.query.filter(
            Product.is_active == True,
            Product.name.ilike(f'%{keyword}%')
        ).all()
        common_products.extend(products)
    
    # Tekrarları kaldır ve ürünleri listele
    seen_ids = set()
    unique_products = []
    for p in common_products:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            unique_products.append(p)
    
    # Stok durumuna göre sırala (düşük stok önce)
    unique_products.sort(key=lambda x: x.current_stock)
    
    # Özet bilgiler
    total_count = len(unique_products)
    critical_count = sum(1 for p in unique_products if p.minimum_stock > 0 and p.current_stock < p.minimum_stock)
    empty_count = sum(1 for p in unique_products if p.current_stock <= 0)
    
    return render_template('reports/common_products.html',
        products=unique_products,
        total_count=total_count,
        critical_count=critical_count,
        empty_count=empty_count,
        keywords=common_keywords
    )
