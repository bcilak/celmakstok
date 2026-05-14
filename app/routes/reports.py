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

SEARCH_STOPWORDS = {
    'ara', 'arar', 'arama', 'bul', 'bulur', 'getir', 'goster', 'gosterir',
    'nedir', 'ne', 'kadar', 'kac', 'adet', 'stok', 'stogu', 'stokta',
    'maliyet', 'maliyeti', 'fiyat', 'fiyati', 'kdv', 'bilgi', 'detay',
    'urun', 'urunu', 'malzeme', 'malzemesi', 'var', 'mi', 'mu', 'mı', 'mü',
    'icin', 'için', 'olan', 'listele', 'rapor', 'raporu'
}


def _normalize_search_keyword(keyword):
    """Keep likely product/code terms from a natural-language question."""
    import re
    raw = (keyword or '').strip()
    tokens = re.findall(r"[\w\-./]+", raw, flags=re.UNICODE)
    cleaned = []
    for token in tokens:
        normalized = token.strip(" .,:;!?()[]{}'\"").lower()
        if len(normalized) < 2 or normalized in SEARCH_STOPWORDS:
            continue
        cleaned.append(token.strip(" .,:;!?()[]{}'\""))
    return cleaned or ([raw] if raw else [])


def _product_search_query(keyword):
    terms = _normalize_search_keyword(keyword)
    query = Product.query.filter(Product.is_active == True)
    if not terms:
        return query, terms

    filters = []
    for term in terms:
        like = f'%{term}%'
        filters.append(db.or_(
            Product.name.ilike(like),
            Product.code.ilike(like),
            Product.barcode.ilike(like),
            Product.material.ilike(like),
            Product.notes.ilike(like),
            Product.category.has(Category.name.ilike(like)),
        ))

    # Prefer products matching all meaningful words; fall back to any word.
    strict_query = query.filter(*filters)
    if strict_query.first():
        return strict_query, terms
    return query.filter(db.or_(*filters)), terms


def _format_product_for_ai(p, include_cost=True):
    cat_name = p.category.name if p.category else '-'
    cost_info = f"{p.unit_cost} {p.currency}" if p.unit_cost and p.unit_cost > 0 else "Bilinmiyor"
    vat_info = f"%{int(p.vat_rate)}" if p.vat_rate else "Belirtilmemis"
    cost_with_vat = round(p.unit_cost * (1 + p.vat_rate / 100), 2) if p.unit_cost and p.unit_cost > 0 and p.vat_rate else None
    cost_vat_str = f", KDV Dahil: {cost_with_vat} {p.currency}" if cost_with_vat else ""

    loc_info = []
    for ls in p.location_stocks:
        if ls.quantity and ls.quantity > 0:
            loc_name = ls.location.name if ls.location else "Lokasyon"
            loc_info.append(f"{loc_name}: {ls.quantity} {p.unit_type}")
    loc_str = ", ".join(loc_info) if loc_info else "Lokasyon kaydi yok"

    material = f", Malzeme: {p.material}" if p.material else ""
    notes = f", Not: {p.notes}" if p.notes else ""
    cost = f", Birim Maliyet: {cost_info}, KDV: {vat_info}{cost_vat_str}" if include_cost else ""

    return (
        f"Kod: {p.code}, Ad: {p.name}, Tip: {p.type}, Kategori: {cat_name}, "
        f"Toplam Stok: {p.current_stock} {p.unit_type}, Min Stok: {p.minimum_stock}, "
        f"Durum: {p.stock_status}, Lokasyon Dagilimi: [{loc_str}]"
        f"{material}{notes}{cost}"
    )


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


# The definitions below intentionally override the initial AI tool functions.
# They accept natural-language questions more reliably, so Gemini can pass
# phrases like "tamburlu maliyeti ne kadar" and still hit the right product.
def get_critical_stock() -> dict:
    """Return products below minimum stock with shortage details."""
    products = Product.query.filter(
        Product.is_active == True,
        Product.minimum_stock > 0,
        Product.current_stock < Product.minimum_stock
    ).order_by((Product.minimum_stock - Product.current_stock).desc()).limit(50).all()

    if not products:
        return {"result": "Su an kritik stokta veya bitmis urun yok."}

    result = []
    for p in products:
        status = "Bos" if p.current_stock <= 0 else "Kritik"
        shortage = max((p.minimum_stock or 0) - (p.current_stock or 0), 0)
        result.append(f"{_format_product_for_ai(p)}; Eksik Miktar: {shortage} {p.unit_type}; Kritik Durum: {status}")
    return {"result": result}


def search_product(keyword: str) -> dict:
    """Search products by natural-language keyword, code, barcode, material or notes."""
    query, terms = _product_search_query(keyword)
    products = query.order_by(Product.name).limit(20).all()

    if not products:
        term_text = ", ".join(terms) if terms else keyword
        return {"result": f"'{term_text}' aramasina uygun urun bulunamadi."}

    return {"result": [_format_product_for_ai(p) for p in products]}


def get_recent_movements(limit: int = 20) -> dict:
    """Return latest stock movements."""
    limit = max(1, min(int(limit or 20), 100))
    movements = StockMovement.query.order_by(StockMovement.date.desc()).limit(limit).all()
    if not movements:
        return {"result": "Son hareket bulunamadi."}

    result = []
    for m in movements:
        date_str = m.date.strftime('%Y-%m-%d %H:%M') if m.date else ""
        prod_name = m.product.name if m.product else '-'
        unit = m.product.unit_type if m.product else ''
        result.append(
            f"Tarih: {date_str}, Urun: {prod_name}, Kod: {m.product.code if m.product else '-'}, "
            f"Yon/Tip: {m.movement_type}, Miktar: {m.quantity} {unit}, "
            f"Kaynak: {m.source or '-'}, Hedef: {m.destination or '-'}, Aciklama: {m.note or '-'}"
        )
    return {"result": result}


def get_production_info() -> dict:
    """Return production line/category summary."""
    categories = Category.query.filter_by(is_active=True).all()
    if not categories:
        return {"result": "Aktif bir uretim hatti bulunamadi."}

    result = []
    for cat in categories:
        product_count = cat.products.filter_by(is_active=True).count()
        result.append(f"Uretim Hatti/Kategori: {cat.name} (Kod: {cat.code}), Aktif Urun: {product_count}")
    return {"result": result}


def get_product_costs(keyword: str = "") -> dict:
    """Return product costs and VAT. Keyword can be a full natural-language question."""
    if keyword:
        query, terms = _product_search_query(keyword)
    else:
        query = Product.query.filter(Product.is_active == True)
        terms = []

    products = query.order_by(Product.name).limit(50).all()
    if not products:
        term_text = ", ".join(terms) if terms else keyword
        return {"result": f"'{term_text}' icin maliyet bilgisi bulunamadi."}

    return {"result": [_format_product_for_ai(p, include_cost=True) for p in products]}


def get_stock_overview() -> dict:
    """Return overall stock counts and the riskiest products."""
    total = Product.query.filter_by(is_active=True).count()
    empty = Product.query.filter(Product.is_active == True, Product.current_stock <= 0).count()
    critical = Product.query.filter(
        Product.is_active == True,
        Product.minimum_stock > 0,
        Product.current_stock < Product.minimum_stock
    ).count()
    total_stock = db.session.query(func.sum(Product.current_stock)).filter(Product.is_active == True).scalar() or 0
    risky = Product.query.filter(
        Product.is_active == True,
        Product.minimum_stock > 0,
        Product.current_stock < Product.minimum_stock
    ).order_by((Product.minimum_stock - Product.current_stock).desc()).limit(10).all()

    return {
        "result": {
            "toplam_aktif_urun": total,
            "kritik_urun": critical,
            "tukenen_urun": empty,
            "toplam_stok_miktari": total_stock,
            "en_riskli_urunler": [_format_product_for_ai(p, include_cost=False) for p in risky]
        }
    }


def get_product_movements(keyword: str, limit: int = 20) -> dict:
    """Return latest stock movements for a product found by natural-language keyword."""
    product_query, terms = _product_search_query(keyword)
    product = product_query.order_by(Product.name).first()
    if not product:
        term_text = ", ".join(terms) if terms else keyword
        return {"result": f"'{term_text}' icin urun bulunamadi."}

    limit = max(1, min(int(limit or 20), 100))
    movements = StockMovement.query.filter_by(product_id=product.id).order_by(StockMovement.date.desc()).limit(limit).all()
    if not movements:
        return {"result": f"{product.code} - {product.name} icin stok hareketi bulunamadi."}

    rows = []
    for m in movements:
        date_str = m.date.strftime('%Y-%m-%d %H:%M') if m.date else ""
        rows.append(
            f"Tarih: {date_str}, Tip: {m.movement_type}, Miktar: {m.quantity} {product.unit_type}, "
            f"Kaynak: {m.source or '-'}, Hedef: {m.destination or '-'}, Aciklama: {m.note or '-'}"
        )
    return {"result": {"urun": _format_product_for_ai(product), "hareketler": rows}}


def get_bom_costs(keyword: str = "", limit: int = 25) -> dict:
    """Return BOM/product-tree recipe details with calculated approximate costs."""
    import re
    from app.utils.bom_utils import get_bom_tree, list_boms

    limit = max(5, min(int(limit or 25), 80))
    terms = _normalize_search_keyword(keyword)
    keyword_l = (keyword or '').strip().lower()
    bom_id_match = re.search(r'\b(?:bom|recete|reçete|agac|ağaç)?\s*#?\s*(\d+)\b', keyword_l)

    boms = list_boms(db)
    if bom_id_match:
        wanted_id = int(bom_id_match.group(1))
        boms = [b for b in boms if b.get('bom_id') == wanted_id]
    elif terms:
        lowered_terms = [t.lower() for t in terms]
        filtered = []
        for bom in boms:
            haystack = " ".join(str(bom.get(k) or '') for k in ('bom_id', 'root_name', 'category_name')).lower()
            if all(term in haystack for term in lowered_terms):
                filtered.append(bom)
        if not filtered:
            for bom in boms:
                haystack = " ".join(str(bom.get(k) or '') for k in ('bom_id', 'root_name', 'category_name')).lower()
                if any(term in haystack for term in lowered_terms):
                    filtered.append(bom)
        boms = filtered

    if not boms:
        term_text = ", ".join(terms) if terms else keyword
        return {"result": f"'{term_text}' icin urun agaci/recete bulunamadi."}

    def flatten_cost_nodes(nodes, rows):
        for node in nodes:
            rows.append({
                "num": node.get("num"),
                "ad": node.get("name"),
                "kod": node.get("code"),
                "tip": node.get("item_type"),
                "miktar": node.get("quantity"),
                "birim": node.get("unit"),
                "stok": node.get("stock_qty"),
                "birim_maliyet": node.get("unit_cost"),
                "toplam_maliyet": node.get("total_cost"),
                "para_birimi": node.get("currency") or "TRY",
            })
            flatten_cost_nodes(node.get("children") or [], rows)

    results = []
    for bom in boms[:5]:
        tree = get_bom_tree(bom["bom_id"], db)
        roots = tree.get("roots") or []
        components = []
        flatten_cost_nodes(roots, components)
        root = roots[0] if roots else {}
        missing_cost_count = sum(1 for c in components if not c.get("birim_maliyet"))
        results.append({
            "bom_id": bom["bom_id"],
            "urun_agaci": bom.get("root_name"),
            "kategori": bom.get("category_name"),
            "parca_sayisi": bom.get("node_count"),
            "yaklasik_toplam_maliyet": root.get("total_cost"),
            "para_birimi": root.get("currency") or "TRY",
            "maliyeti_eksik_parca_sayisi": missing_cost_count,
            "recete_kalemleri": components[:limit],
        })

    return {"result": results}


def analyze_product_family(keyword: str, limit: int = 12) -> dict:
    """Return an executive-style analysis for a product family keyword."""
    from app.utils.bom_utils import get_bom_tree, list_boms

    query, terms = _product_search_query(keyword)
    products = query.order_by(Product.name).limit(200).all()
    if not products:
        term_text = ", ".join(terms) if terms else keyword
        return {"result": f"'{term_text}' icin urun ailesi bulunamadi."}

    product_ids = [p.id for p in products]
    total_stock = sum((p.current_stock or 0) for p in products)
    empty_count = sum(1 for p in products if (p.current_stock or 0) <= 0)
    critical_count = sum(
        1 for p in products
        if (p.minimum_stock or 0) > 0 and (p.current_stock or 0) < (p.minimum_stock or 0)
    )
    total_inventory_cost = sum((p.current_stock or 0) * (p.unit_cost or 0) for p in products)
    priced_count = sum(1 for p in products if p.unit_cost and p.unit_cost > 0)

    movement_totals = dict(
        db.session.query(StockMovement.movement_type, func.sum(StockMovement.quantity))
        .filter(StockMovement.product_id.in_(product_ids))
        .group_by(StockMovement.movement_type)
        .all()
    )
    total_in = float(movement_totals.get('giris') or 0)
    total_out = float(
        (movement_totals.get('cikis') or 0)
        + (movement_totals.get('transfer') or 0)
        + (movement_totals.get('fire') or 0)
    )

    boms = []
    lowered_terms = [t.lower() for t in terms]
    for bom in list_boms(db):
        haystack = " ".join(str(bom.get(k) or '') for k in ('bom_id', 'root_name', 'category_name')).lower()
        if lowered_terms and not any(term in haystack for term in lowered_terms):
            continue
        tree = get_bom_tree(bom["bom_id"], db)
        roots = tree.get("roots") or []
        if not roots:
            continue
        root = roots[0]
        boms.append({
            "bom_id": bom["bom_id"],
            "urun_agaci": bom.get("root_name"),
            "kategori": bom.get("category_name"),
            "yaklasik_toplam_maliyet": root.get("total_cost"),
            "para_birimi": root.get("currency") or "TRY",
            "kalem_sayisi": bom.get("node_count"),
        })

    boms = sorted(boms, key=lambda b: b.get("yaklasik_toplam_maliyet") or 0, reverse=True)

    top_products = sorted(products, key=lambda p: p.unit_cost or 0, reverse=True)[:limit]
    stock_risks = sorted(
        [
            p for p in products
            if (p.current_stock or 0) <= 0
            or ((p.minimum_stock or 0) > 0 and (p.current_stock or 0) < (p.minimum_stock or 0))
        ],
        key=lambda p: ((p.minimum_stock or 0) - (p.current_stock or 0)),
        reverse=True
    )[:limit]

    return {
        "result": {
            "arama": keyword,
            "bulunan_urun_sayisi": len(products),
            "fiyatli_urun_sayisi": priced_count,
            "toplam_stok_miktari": total_stock,
            "tahmini_stok_maliyeti": total_inventory_cost,
            "kritik_urun_sayisi": critical_count,
            "tukenen_urun_sayisi": empty_count,
            "toplam_giris": total_in,
            "toplam_cikis_sarfiyat_transfer": total_out,
            "urun_agaclari": boms[:5],
            "en_yuksek_birim_maliyetli_urunler": [
                _format_product_for_ai(p, include_cost=True) for p in top_products
            ],
            "stok_riski_olan_urunler": [
                _format_product_for_ai(p, include_cost=True) for p in stock_risks
            ],
            "not": "Cikis/sarfiyat/transfer toplami satis anlamina gelmeyebilir; sistemde ayri satis kaydi yoksa bunu stok cikisi olarak yorumla."
        }
    }


def _fmt_money(value, currency='TRY'):
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_qty(value):
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _is_quota_error(error):
    text = str(error).lower()
    return '429' in text or 'quota' in text or 'rate-limit' in text or 'rate limit' in text


def _should_answer_locally(query):
    q = (query or '').lower()
    terms = _normalize_search_keyword(q)
    local_keywords = [
        'maliyet', 'maliyeti', 'fiyat', 'fiyati', 'stok', 'satış', 'satis',
        'çıkış', 'cikis', 'sarfiyat', 'ürün ağacı', 'urun agaci', 'reçete',
        'recete', 'bom'
    ]
    if any(word in q for word in local_keywords):
        return True
    if 1 <= len(terms) <= 3:
        product_query, _ = _product_search_query(query)
        return product_query.first() is not None
    return False


def _local_analysis_answer(query, quota_limited=False):
    family = analyze_product_family(query).get('result')
    if isinstance(family, str):
        product_result = search_product(query).get('result')
        if isinstance(product_result, list) and product_result:
            prefix = "AI kotasi dolu oldugu icin veritabanindan direkt hesapladim.\n\n" if quota_limited else ""
            return prefix + "\n".join(f"- {item}" for item in product_result[:5])
        return family

    boms = family.get('urun_agaclari') or []
    best_bom = boms[0] if boms else None
    currency = (best_bom or {}).get('para_birimi') or 'TRY'
    bom_cost = (best_bom or {}).get('yaklasik_toplam_maliyet')

    lines = []
    if quota_limited:
        lines.append("AI kotasi dolu oldugu icin Gemini'ye gitmeden veritabanindan direkt analiz ettim.")
        lines.append("")

    lines.append(f"**{query}** icin {family.get('bulunan_urun_sayisi', 0)} kayit buldum.")

    if best_bom:
        lines.append(
            f"En ilgili urun agaci **{best_bom.get('urun_agaci')}**; yaklasik BOM maliyeti "
            f"**{_fmt_money(bom_cost, currency)}**."
        )
    else:
        lines.append(
            f"Urun agaci eslesmesi bulunamadi; stok kartlari uzerinden tahmini stok maliyeti "
            f"**{_fmt_money(family.get('tahmini_stok_maliyeti'), 'TRY')}**."
        )

    lines.append(
        f"Toplam stok miktari **{_fmt_qty(family.get('toplam_stok_miktari'))}**, "
        f"kritik urun **{family.get('kritik_urun_sayisi', 0)}**, "
        f"tukenen urun **{family.get('tukenen_urun_sayisi', 0)}**."
    )
    lines.append(
        f"Sistemdeki toplam giris **{_fmt_qty(family.get('toplam_giris'))}**, "
        f"cikis/sarfiyat/transfer toplamı **{_fmt_qty(family.get('toplam_cikis_sarfiyat_transfer'))}**. "
        "Ayri satis kaydi olmadigi icin bunu kesin satis degil stok cikisi olarak yorumladim."
    )

    risks = family.get('stok_riski_olan_urunler') or []
    if risks:
        lines.append("")
        lines.append("Oncelikli riskler:")
        for item in risks[:3]:
            lines.append(f"- {item}")

    if boms and len(boms) > 1:
        lines.append("")
        lines.append("Diger ilgili urun agaclari:")
        for bom in boms[1:4]:
            lines.append(
                f"- {bom.get('urun_agaci')}: yaklasik **{_fmt_money(bom.get('yaklasik_toplam_maliyet'), bom.get('para_birimi') or 'TRY')}**"
            )

    return "\n".join(lines)


def _local_stock_summary(total_items, critical_items, empty_items, critical_products):
    names = [p.name for p in critical_products[:5]]
    if critical_items or empty_items:
        detail = f" Oncelikli kontrol: {', '.join(names)}." if names else ""
        return (
            f"Stokta **{total_items}** aktif urun var; **{critical_items}** urun kritik seviyede, "
            f"**{empty_items}** urun tamamen bitmis gorunuyor.{detail} "
            "Tedarik veya uretim planinda once biten ve minimum altindaki kalemlere odaklanmak gerekir."
        )
    return (
        f"Stokta **{total_items}** aktif urun var ve kritik ya da biten urun gorunmuyor. "
        "Mevcut tablo genel olarak saglikli; yine de yuksek sarfiyatli urunler periyodik izlenmeli."
    )

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
        if _should_answer_locally(query):
            answer = _local_analysis_answer(query)
            return jsonify({'success': True, 'answer': answer, 'source': 'local'})

        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            answer = _local_analysis_answer(query)
            return jsonify({'success': True, 'answer': answer, 'source': 'local'})

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
- Kısa, net, doğrudan ve analiz gibi cevap ver. Gereksiz tekrar YAPMA.
- Tek bir ürün sorulduğunda madde işareti (•) ile önemli bilgileri alt alta yaz.
- Excel gibi tablo oluşturma. Çok ürün çıksa bile tablo KULLANMA.
- Kullanıcı tek kelime/aile adı yazarsa (örn. "tamburlu") liste dökme; önce özet analiz ver.
- "Maliyet şu kadar, stok şu kadar, çıkış/sarfiyat şu kadar, risk şu" gibi yönetici özeti yaz.
- Çok fazla ürün varsa en önemli 3-5 ürünü veya riski seçip anlat; tamamını sıralama.
- Önemli sayıları **kalın** yap.
- Asla ham json veya liste formatı gösterme, insan dostu yaz.
- Cevaba gereksiz giriş cümlesi ekleme, direkt bilgiyi ver.
        """

        system_instruction += """

EK VERI KURALLARI:
- Genel stok durumu, toplam, kritik veya tukenen urun sorularinda get_stock_overview veya get_critical_stock kullan.
- Urun adi/kodu gecen stok, lokasyon, malzeme veya detay sorularinda search_product kullan.
- Kullanici tek bir urun ailesi/kelime yazarsa veya analiz isterse analyze_product_family kullan; tablo gibi listeleme yapma.
- Bir urunun hareket gecmisi sorulursa get_product_movements kullan.
- Maliyet/fiyat/KDV sorulari icin get_product_costs fonksiyonunu kullan.
- Urun agaci, BOM, recete, parca listesi veya yaklasik urun agaci maliyeti sorularinda get_bom_costs kullan.
- Satis kelimesi gecerse sistemde ayri satis kaydi yoksa stok cikisi/sarfiyat/transfer toplamlarini "cikis/sarfiyat" diye belirt, kesin satis gibi sunma.
- Veritabaniyla ilgili sorularda tahmin etme; once uygun fonksiyonu cagir.
        """

        tools = [
            get_stock_overview,
            get_critical_stock,
            search_product,
            analyze_product_family,
            get_product_movements,
            get_bom_costs,
            get_recent_movements,
            get_production_info,
            get_product_costs,
        ]
        model = genai.GenerativeModel('gemini-2.5-pro', tools=tools, system_instruction=system_instruction)

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
        if _is_quota_error(e):
            answer = _local_analysis_answer(query, quota_limited=True)
            return jsonify({'success': True, 'answer': answer, 'source': 'local_quota_fallback'})
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
    
    if not current_app.config.get('GEMINI_API_KEY'):
        summary = _local_stock_summary(total_items, critical_items, empty_items, critical_products)
        return jsonify({'success': True, 'summary': summary, 'source': 'local'})

    try:
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'success': False, 'message': 'API anahtarı bulunamadı.'})
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')
        
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
        if _is_quota_error(e):
            summary = _local_stock_summary(total_items, critical_items, empty_items, critical_products)
            return jsonify({'success': True, 'summary': summary, 'source': 'local_quota_fallback'})
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
