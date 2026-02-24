from flask import Blueprint, render_template, request, Response, current_app, jsonify
from flask_login import login_required
from app.models import Product, Category, StockMovement, CountSession, CountItem, ProductionRecord, Recipe
from app import db
from sqlalchemy import func, text
from datetime import datetime, timedelta
import csv
import io
import google.genai as genai

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

@reports_bp.route('/ai-assistant', methods=['GET', 'POST'])
@login_required
def ai_assistant():
    answer = None
    query = None
    if request.method == 'POST':
        query = request.form.get('query')
        
        if query:
            try:
                api_key = current_app.config.get('GEMINI_API_KEY')
                if not api_key:
                    raise ValueError("GEMINI_API_KEY is not set in the configuration.")

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name='gemini-2.5-pro')
                
                db_schema = get_db_schema()
                prompt = f"""
                You are a helpful AI assistant for a stock management application.
                Your goal is to answer user questions based on the data in the database.
                You can do this by generating a SQL query based on the user's question and the database schema.
                
                Here is the database schema:
                {db_schema}

                The user's question is: "{query}"

                Based on this, generate a syntactically correct SQLite SQL query to answer the question.
                Only return the SQL query, nothing else.
                For example: SELECT * FROM Product WHERE current_stock < 10;
                If you cannot generate a query, return "I can't answer that question."
                """

                response = model.generate_content(prompt)
                sql_query = response.text.strip()

                if "can't answer" in sql_query:
                    answer = "Bu soruya cevap veremiyorum."
                else:
                    # SQL sorgusunu çalıştır
                    result = db.session.execute(text(sql_query))
                    
                    # Sonuçları işle
                    columns = result.keys()
                    rows = result.fetchall()
                    
                    # Sonucu bir metin olarak formatla
                    if rows:
                        answer = "Sorgu Sonuçları:\n"
                        answer += ", ".join(columns) + "\n"
                        for row in rows:
                            answer += ", ".join(map(str, row)) + "\n"
                    else:
                        answer = "Sorgu sonuç döndürmedi."

            except Exception as e:
                answer = f"Bir hata oluştu: {e}"

    return render_template('reports/ai_assistant.html', query=query, answer=answer)


@reports_bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')


# ================== STOK RAPORLARI ==================

@reports_bp.route('/stock')
@login_required
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
    
    # AI ile özet/yorum üret
    ai_summary = None
    try:
        api_key = current_app.config.get('GEMINI_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name='gemini-2.5-pro')
            # Sadece temel sayısal özetleri gönder
            summary_prompt = f"""
            Aşağıda bir stok raporunun özet verileri var:
            - Toplam ürün: {total_items}
            - Kritik stok: {critical_items}
            - Tükenen ürün: {empty_items}
            Kısa ve anlaşılır bir şekilde, stok durumu hakkında yöneticilere öneri ve analiz sunan bir özet yaz. (Türkçe)
            """
            response = model.generate_content(summary_prompt)
            ai_summary = response.text.strip()
    except Exception as e:
        ai_summary = f"AI özet üretilemedi: {e}"

    return render_template('reports/stock.html',
        products=products,
        categories=categories,
        selected_category=category_id,
        total_items=total_items,
        critical_items=critical_items,
        empty_items=empty_items,
        ai_summary=ai_summary
    )

@reports_bp.route('/stock/export')
@login_required
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
def production_report():
    """Üretim raporu - Reçetelerden yapılan üretimler"""
    category_id = request.args.get('category', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    categories = Category.query.filter_by(is_active=True).all()
    
    # Üretim kayıtlarını sorgula
    query = ProductionRecord.query
    
    if category_id:
        query = query.join(Recipe).filter(Recipe.category_id == category_id)
    
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
        cat_productions = [p for p in productions if p.recipe and p.recipe.category_id == cat.id]
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
def counting_report():
    """Sayım raporları"""
    sessions = CountSession.query.filter_by(status='completed').order_by(
        CountSession.completed_at.desc()
    ).all()
    
    return render_template('reports/counting.html', sessions=sessions)

@reports_bp.route('/counting/<int:id>')
@login_required
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
def movement_report():
    """Stok hareketleri raporu (alternatif URL)"""
    return movements_report()

# ================== DIŞA AKTARMA ==================

@reports_bp.route('/export/products')
@login_required
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
