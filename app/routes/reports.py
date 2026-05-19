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
    'icin', 'için', 'olan', 'listele', 'rapor', 'raporu', 'kaç', 'tane',
    'elimde', 'elde', 'sattim', 'sattik', 'sattık', 'satildi', 'satıldı',
    'bu', 'hafta', 'ay', 'yil', 'yıl'
}

SEARCH_STOPWORDS.update({
    'urunler', 'urunleri', 'ürünler', 'ürünleri', 'neler', 'hangileri',
    'durumu', 'durum', 'biten', 'tukenen', 'tükenen', 'stoksuz'
})


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


def _fold_search_text(value):
    import unicodedata

    text = str(value or '').lower()
    text = (
        text.replace('ı', 'i')
        .replace('İ'.lower(), 'i')
        .replace('ğ', 'g')
        .replace('ü', 'u')
        .replace('ş', 's')
        .replace('ö', 'o')
        .replace('ç', 'c')
    )
    text = text.translate(str.maketrans('ıİğĞüÜşŞöÖçÇ', 'iIgGuUsSoOcC')).lower()
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')


def _search_haystack(*values):
    raw = " ".join(str(value or '') for value in values).lower()
    return f"{raw} {_fold_search_text(raw)}"


def _search_terms(terms):
    expanded = []
    for term in terms or []:
        raw = str(term or '').lower()
        folded = _fold_search_text(raw)
        expanded.append(folded or raw)
    return expanded


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

    loose_query = query.filter(db.or_(*filters))
    if loose_query.first():
        return loose_query, terms

    folded_terms = _search_terms(terms)
    scored = []
    for product in query.limit(2000).all():
        haystack = _search_haystack(
            product.name,
            product.code,
            product.barcode,
            product.material,
            product.notes,
            product.category.name if product.category else '',
        )
        score = sum(1 for term in folded_terms if term and term in haystack)
        if score:
            scored.append((score, product.id))

    if scored:
        ids = [product_id for _, product_id in sorted(scored, reverse=True)[:100]]
        return query.filter(Product.id.in_(ids)), terms

    return loose_query, terms


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
        lowered_terms = _search_terms(terms)
        filtered = []
        for bom in boms:
            haystack = _search_haystack(*(bom.get(k) for k in ('bom_id', 'root_name', 'category_name')))
            if all(term in haystack for term in lowered_terms):
                filtered.append(bom)
        if not filtered:
            for bom in boms:
                haystack = _search_haystack(*(bom.get(k) for k in ('bom_id', 'root_name', 'category_name')))
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

    product_ids = [p.id for p in products]
    total_stock = sum((p.current_stock or 0) for p in products)
    empty_count = sum(1 for p in products if (p.current_stock or 0) <= 0)
    critical_count = sum(
        1 for p in products
        if (p.minimum_stock or 0) > 0 and (p.current_stock or 0) < (p.minimum_stock or 0)
    )
    total_inventory_cost = sum((p.current_stock or 0) * (p.unit_cost or 0) for p in products)
    priced_count = sum(1 for p in products if p.unit_cost and p.unit_cost > 0)

    movement_totals = {}
    if product_ids:
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
    lowered_terms = _search_terms(terms)
    for bom in list_boms(db):
        haystack = _search_haystack(*(bom.get(k) for k in ('bom_id', 'root_name', 'category_name')))
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
            "product_id": bom.get("product_id"),
            "kategori": bom.get("category_name"),
            "yaklasik_toplam_maliyet": root.get("total_cost"),
            "para_birimi": root.get("currency") or "TRY",
            "kalem_sayisi": bom.get("node_count"),
            "match_score": sum(1 for term in lowered_terms if term in haystack),
        })

    if not boms and lowered_terms:
        for bom in list_boms(db):
            tree = get_bom_tree(bom["bom_id"], db)
            roots = tree.get("roots") or []
            if not roots:
                continue
            node_haystack = _search_haystack(
                *(
                    " ".join(str(node.get(k) or '') for k in ('num', 'name', 'code', 'material', 'item_type'))
                    for node in _iter_bom_nodes(roots)
                )
            )
            match_score = sum(1 for term in lowered_terms if term in node_haystack)
            if not match_score:
                continue
            root = roots[0]
            boms.append({
                "bom_id": bom["bom_id"],
                "urun_agaci": bom.get("root_name"),
                "product_id": bom.get("product_id"),
                "kategori": bom.get("category_name"),
                "yaklasik_toplam_maliyet": root.get("total_cost"),
                "para_birimi": root.get("currency") or "TRY",
                "kalem_sayisi": bom.get("node_count"),
                "match_score": match_score,
            })

    if not products and not boms:
        term_text = ", ".join(terms) if terms else keyword
        return {"result": f"'{term_text}' icin urun ailesi bulunamadi."}

    boms = sorted(
        boms,
        key=lambda b: (b.get("match_score") or 0, b.get("yaklasik_toplam_maliyet") or 0),
        reverse=True
    )

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


def _format_risk_product(p):
    shortage = max((p.minimum_stock or 0) - (p.current_stock or 0), 0)
    if (p.current_stock or 0) <= 0:
        status = "tukenmis"
    elif shortage > 0:
        status = f"{_fmt_qty(shortage)} {p.unit_type} eksik"
    else:
        status = "normal"
    cost = _fmt_money(p.unit_cost, p.currency) if p.unit_cost and p.unit_cost > 0 else "maliyet yok"
    return f"**{p.name}** - stok **{_fmt_qty(p.current_stock)} {p.unit_type}**, {status}, birim maliyet {cost}"


def _period_starts():
    now = datetime.utcnow()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return week_start, month_start, year_start


def _movement_total(product_id, movement_types, since=None):
    query = db.session.query(func.sum(StockMovement.quantity)).filter(
        StockMovement.product_id == product_id,
        StockMovement.movement_type.in_(movement_types)
    )
    if since:
        query = query.filter(StockMovement.date >= since)
    return float(query.scalar() or 0)


def _select_main_product(query, family):
    terms = _search_terms(_normalize_search_keyword(query))
    boms = family.get('urun_agaclari') or []
    for bom in boms:
        if len(terms) > 1 and (bom.get('match_score') or 0) < len(terms):
            continue
        product_id = bom.get('product_id')
        if product_id:
            product = Product.query.get(product_id)
            if product:
                return product, bom

    product_query, _ = _product_search_query(query)
    products = product_query.order_by(Product.name).limit(100).all()
    if len(terms) > 1:
        def matches_all(product):
            haystack = _search_haystack(*[
                product.name or '',
                product.code or '',
                product.barcode or '',
                product.material or '',
                product.notes or '',
                product.category.name if product.category else '',
            ])
            return all(term in haystack for term in terms)

        strict_products = [product for product in products if matches_all(product)]
        if strict_products:
            products = strict_products

    type_order = {'mamul': 0, 'mamul ': 0, 'yarimamul': 1, 'hazir_parca': 2, 'hammadde': 3}
    if products:
        product = sorted(products, key=lambda p: type_order.get((p.type or '').strip().lower(), 9))[0]
        return product, None
    return None, None


def _iter_bom_nodes(nodes):
    for node in nodes or []:
        yield node
        yield from _iter_bom_nodes(node.get('children') or [])


def _node_sort_key(node):
    try:
        return float(node.get('total_cost') or 0)
    except (TypeError, ValueError):
        return 0.0


def _location_summary(product, limit=3):
    locations = []
    try:
        stocks = product.location_stocks
    except Exception:
        stocks = []
    for ls in stocks:
        if not ls.quantity or ls.quantity <= 0:
            continue
        loc_name = ls.location.name if ls.location else "Lokasyon"
        locations.append(f"{loc_name}: {_fmt_qty(ls.quantity)} {product.unit_type}")
    return locations[:limit]


def _verified_product_snapshot(query, family):
    from app.utils.bom_utils import audit_bom_material_links, get_bom_tree

    product, best_bom = _select_main_product(query, family)
    if not product:
        return None

    currency = product.currency or 'TRY'
    unit_cost = float(product.unit_cost or 0)
    cost_source = "urun karti"
    bom_nodes = []
    bom_root = None
    top_components = []
    missing_cost_nodes = []
    link_audit = None

    if best_bom:
        tree = get_bom_tree(best_bom.get("bom_id"), db)
        roots = tree.get("roots") or []
        bom_root = roots[0] if roots else None
        if bom_root:
            bom_nodes = list(_iter_bom_nodes(roots))
            root_cost = bom_root.get("total_cost")
            if root_cost is not None:
                unit_cost = float(root_cost or 0)
                currency = bom_root.get("currency") or best_bom.get("para_birimi") or currency
                cost_source = f"BOM #{best_bom.get('bom_id')}"

            first_level = bom_root.get("children") or []
            top_components = sorted(
                [node for node in first_level if (node.get("total_cost") or 0) > 0],
                key=_node_sort_key,
                reverse=True
            )[:5]

            leaf_nodes = [node for node in bom_nodes if not node.get("children")]
            missing_cost_nodes = [
                node for node in leaf_nodes
                if not (node.get("unit_cost") and node.get("unit_cost") > 0)
                and not (node.get("total_cost") and node.get("total_cost") > 0)
            ]

        try:
            link_audit = audit_bom_material_links(best_bom.get("bom_id"), db, apply=False)
        except Exception:
            link_audit = None

    week_start, month_start, year_start = _period_starts()
    out_types = ['cikis', 'transfer', 'fire']
    movement = {
        "week_out": _movement_total(product.id, out_types, week_start),
        "month_out": _movement_total(product.id, out_types, month_start),
        "year_out": _movement_total(product.id, out_types, year_start),
        "total_out": _movement_total(product.id, out_types),
        "month_in": _movement_total(product.id, ['giris'], month_start),
    }

    audit_stats = (link_audit or {}).get("stats") or {}
    issue_count = (
        len(missing_cost_nodes)
        + int(audit_stats.get("mismatch") or 0)
        + int(audit_stats.get("missing") or 0)
        + int(audit_stats.get("suggested") or 0)
    )
    confidence = "Yuksek" if issue_count == 0 and unit_cost > 0 else ("Orta" if unit_cost > 0 else "Dusuk")

    return {
        "product": product,
        "bom": best_bom,
        "bom_root": bom_root,
        "unit_cost": unit_cost,
        "currency": currency,
        "cost_source": cost_source,
        "stock_value": float(product.current_stock or 0) * unit_cost,
        "movement": movement,
        "top_components": top_components,
        "missing_cost_nodes": missing_cost_nodes,
        "link_audit_stats": audit_stats,
        "confidence": confidence,
        "issue_count": issue_count,
        "locations": _location_summary(product),
    }


def _is_quota_error(error):
    text = str(error).lower()
    return '429' in text or 'quota' in text or 'rate-limit' in text or 'rate limit' in text


def _should_answer_locally(query):
    q = (query or '').lower()
    terms = _normalize_search_keyword(q)
    local_keywords = [
        'maliyet', 'maliyeti', 'fiyat', 'fiyati', 'stok', 'satış', 'satis',
        'çıkış', 'cikis', 'sarfiyat', 'ürün ağacı', 'urun agaci', 'reçete',
        'recete', 'bom', 'analiz', 'rapor', 'uretim', 'giris', 'cikti', 'cikan',
        'elde', 'kac tane', 'kaç tane'
    ]
    local_keywords.extend([
        'kritik', 'biten', 'stoksuz', 'tukenen', 'tukenmis', 'son hareket',
        'hareketler', 'envanter', 'yardim', 'help', 'sorabilirim'
    ])
    if any(word in q for word in local_keywords):
        return True
    if 1 <= len(terms) <= 3:
        product_query, _ = _product_search_query(query)
        if product_query.first() is not None:
            return True
        folded_terms = _search_terms(terms)
        try:
            from app.utils.bom_utils import list_boms
            for bom in list_boms(db):
                haystack = _search_haystack(*(bom.get(k) for k in ('bom_id', 'root_name', 'category_name')))
                if any(term in haystack for term in folded_terms):
                    return True
        except Exception:
            pass
    return False


def _product_line(product, include_cost=True):
    cost = ""
    if include_cost:
        cost = f", maliyet **{_fmt_money(product.unit_cost, product.currency)}**" if product.unit_cost and product.unit_cost > 0 else ", maliyet yok"
    return f"- **{product.name}** ({product.code}): stok **{_fmt_qty(product.current_stock)} {product.unit_type}**{cost}"


def _local_quick_answer(query):
    q = _fold_search_text(query)

    if any(word in q for word in ['yardim', 'help', 'ne sorabilirim', 'neler sorabilirim', 'sorabilirim', 'ornek soru']):
        return (
            "**Hizli sorular**\n"
            "- Stokta biten urunler neler?\n"
            "- Kritik stokta neler var?\n"
            "- Toplam stok degeri ne kadar?\n"
            "- Son stok hareketleri neler?\n"
            "- 165 tamburlu maliyeti nedir?\n"
            "- Elimde 165 tamburlu kac tane var?\n"
            "- Uretim durumu nedir?"
        )

    if any(word in q for word in ['kritik', 'stoksuz', 'biten', 'tukenen', 'tukenmis']):
        only_empty = any(word in q for word in ['stoksuz', 'biten', 'tukenen', 'tukenmis'])
        product_query = Product.query.filter(Product.is_active == True)
        if only_empty:
            products = product_query.filter(Product.current_stock <= 0).order_by(Product.name).limit(12).all()
            title = "Stokta biten urunler"
        else:
            products = product_query.filter(
                db.or_(
                    Product.current_stock <= 0,
                    db.and_(Product.minimum_stock > 0, Product.current_stock < Product.minimum_stock)
                )
            ).order_by((Product.minimum_stock - Product.current_stock).desc()).limit(12).all()
            title = "Kritik stok ozeti"
        if not products:
            return f"**{title}**\nSu an bu kritere giren urun gorunmuyor."
        total_count = Product.query.filter(Product.is_active == True, Product.current_stock <= 0).count() if only_empty else len(products)
        lines = [f"**{title}**", f"Ilk {len(products)} kaydi gosteriyorum."]
        lines.extend(_product_line(p, include_cost=False) for p in products)
        if only_empty:
            lines.append(f"Toplam stoksuz urun sayisi: **{total_count}**")
        return "\n".join(lines)

    if 'stok deger' in q or 'stok maliyet' in q or 'envanter' in q:
        products = Product.query.filter(Product.is_active == True).all()
        total_value = sum(float(p.current_stock or 0) * float(p.unit_cost or 0) for p in products)
        priced = [p for p in products if p.unit_cost and p.unit_cost > 0]
        missing = len(products) - len(priced)
        top = sorted(priced, key=lambda p: (p.current_stock or 0) * (p.unit_cost or 0), reverse=True)[:5]
        lines = [
            "**Toplam stok degeri**",
            f"- Hesaplanan stok degeri: **{_fmt_money(total_value, 'TRY')}**",
            f"- Fiyatli urun karti: **{len(priced)}**",
            f"- Fiyati olmayan urun karti: **{missing}**",
        ]
        if top:
            lines.append("")
            lines.append("**Degeri en yuksek kalemler**")
            lines.extend(
                f"- {p.name}: **{_fmt_money((p.current_stock or 0) * (p.unit_cost or 0), p.currency)}**"
                for p in top
            )
        return "\n".join(lines)

    if 'son hareket' in q or 'hareketler' in q:
        movements = StockMovement.query.order_by(StockMovement.date.desc()).limit(8).all()
        if not movements:
            return "Son stok hareketi bulunamadi."
        lines = ["**Son stok hareketleri**"]
        for m in movements:
            product = m.product
            date_str = m.date.strftime('%d.%m.%Y %H:%M') if m.date else "-"
            unit = product.unit_type if product else ''
            name = product.name if product else '-'
            lines.append(f"- {date_str}: **{name}**, {m.movement_type}, **{_fmt_qty(m.quantity)} {unit}**")
        return "\n".join(lines)

    if 'uretim' in q or 'üretim' in query.lower():
        categories = Category.query.filter_by(is_active=True).all()
        if not categories:
            return "Aktif uretim hatti/kategori bulunamadi."
        lines = ["**Uretim durumu**"]
        for cat in categories[:10]:
            product_count = cat.products.filter_by(is_active=True).count()
            lines.append(f"- {cat.name}: **{product_count}** aktif urun")
        return "\n".join(lines)

    return None


def _not_found_answer(query):
    terms = _normalize_search_keyword(query)
    sample = Product.query.filter(Product.is_active == True).order_by(Product.name).limit(5).all()
    lines = [f"'{query}' icin net eslesme cikmadi; en yakin kayitlara gore ilerleyebilirim."]
    if terms:
        lines.append(f"Aradigim anahtar kelimeler: **{', '.join(terms)}**")
    if sample:
        lines.append("Daha net yakalamam icin kod/ad parcasiyla sorabilirsin. Ornek kayitlar:")
        lines.extend(f"- {p.code} - {p.name}" for p in sample)
    return "\n".join(lines)


def _local_analysis_answer(query, quota_limited=False):
    quick_answer = _local_quick_answer(query)
    if quick_answer:
        return quick_answer

    family = analyze_product_family(query).get('result')
    if isinstance(family, str):
        product_result = search_product(query).get('result')
        if isinstance(product_result, list) and product_result:
            prefix = "AI kotasi dolu oldugu icin veritabanindan direkt hesapladim.\n\n" if quota_limited else ""
            return prefix + "\n".join(f"- {item}" for item in product_result[:5])
        return _not_found_answer(query)

    snapshot = _verified_product_snapshot(query, family)
    if not snapshot:
        return _not_found_answer(query)

    product = snapshot["product"]
    best_bom = snapshot.get("bom")
    currency = snapshot["currency"]
    unit_cost = snapshot["unit_cost"]
    movement = snapshot["movement"]

    lines = []
    if quota_limited:
        lines.append("AI kotasi dolu oldugu icin Gemini'ye gitmeden veritabanindan direkt analiz ettim.")
        lines.append("")

    lines.append(f"### {product.name}")
    lines.append(f"Kod: **{product.code}** | Tip: **{product.type or 'mamul'}**")
    lines.append("")

    lines.append(f"- Yaklasik birim maliyet: **{_fmt_money(unit_cost, currency)}**")
    lines.append(f"- Elimizdeki mamul stogu: **{_fmt_qty(product.current_stock)} {product.unit_type}**")
    lines.append(f"- Eldeki stok maliyeti: **{_fmt_money(snapshot['stock_value'], currency)}**")
    lines.append(f"- Maliyet kaynagi: **{snapshot['cost_source']}**")
    if best_bom:
        lines.append(f"- Secilen urun agaci: **{best_bom.get('urun_agaci')}**")
    if snapshot.get("locations"):
        lines.append(f"- Stok lokasyonlari: {', '.join(snapshot['locations'])}")

    lines.append("")
    lines.append("Son hareketler:")
    lines.append(f"- Bu hafta: **{_fmt_qty(movement['week_out'])} {product.unit_type}**")
    lines.append(f"- Bu ay: **{_fmt_qty(movement['month_out'])} {product.unit_type}**")
    lines.append(f"- Bu yil: **{_fmt_qty(movement['year_out'])} {product.unit_type}**")
    lines.append(f"- Toplam kayitli cikis: **{_fmt_qty(movement['total_out'])} {product.unit_type}**")
    lines.append(f"- Bu ay giris/uretim: **{_fmt_qty(movement['month_in'])} {product.unit_type}**")

    if snapshot.get("top_components"):
        lines.append("")
        lines.append("Ana maliyet kirilimlari:")
        for node in snapshot["top_components"][:3]:
            lines.append(
                f"- {node.get('name')}: **{_fmt_money(node.get('total_cost'), node.get('currency') or currency)}**"
            )

    audit_stats = snapshot.get("link_audit_stats") or {}
    warnings = []
    if unit_cost <= 0:
        warnings.append("mamul maliyeti hesaplanamadi")
    if snapshot.get("missing_cost_nodes"):
        warnings.append(f"{len(snapshot['missing_cost_nodes'])} alt kalemde fiyat/maliyet yok")
    link_issue_count = int(audit_stats.get("mismatch") or 0) + int(audit_stats.get("missing") or 0)
    suggested_count = int(audit_stats.get("suggested") or 0)
    if link_issue_count:
        warnings.append(f"{link_issue_count} hammadde baglantisi hatali/eksik")
    if suggested_count:
        warnings.append(f"{suggested_count} hammadde icin daha iyi eslesme onerisi var")

    if warnings:
        lines.append("")
        lines.append(f"Not: {', '.join(warnings)}. Bu nedenle maliyet kontrol edilmeli.")
    lines.append("")
    lines.append("> Satis modulu ayri olmadigi icin satis bilgisini stok cikisi/transfer/fire hareketlerinden okudum.")

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
            return jsonify({'success': True, 'answer': answer, 'source': 'local_verified'})

        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            answer = _local_analysis_answer(query)
            return jsonify({'success': True, 'answer': answer, 'source': 'local_verified'})

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

BIG BOSS KURALLARI:
- Mamul sorularinda alt parcalari listeleme; sadece mamul seviyesi onemli bilgileri ver.
- Oncelik sirasi: yaklasik maliyet, eldeki stok, bu hafta/ay/yil satis veya stok cikisi.
- Cok fazla eslesme varsa mamul/BOM kokunu sec; tum urunleri ve parcalari siralama.
- BOM ve recete bilgisini sadece sonuc maliyeti hesaplamak icin kullan.
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
            return jsonify({'success': True, 'answer': answer, 'source': 'local_verified_quota_fallback'})
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


def _cost_report_analysis(stats):
    notes = []
    if stats['missing_cost_count']:
        notes.append(
            f"{stats['missing_cost_count']} aktif urunde birim maliyet yok. Bu kalemler stok degeri ve BOM maliyetini dusuk gosterir."
        )
    if stats['priced_count'] and stats['total_products']:
        coverage = (stats['priced_count'] / stats['total_products']) * 100
        notes.append(f"Fiyat kapsami %{coverage:.1f}; fiyat kartlari tamamlandikca rapor daha guvenilir olur.")
    if stats['top_inventory']:
        leader = stats['top_inventory'][0]
        notes.append(
            f"Stok degerinde en buyuk kalem {leader['name']} ({_fmt_money(leader['value'], leader['currency'])})."
        )
    if stats['bom_missing_cost_count']:
        notes.append(
            f"Urun agaclarinda {stats['bom_missing_cost_count']} yaprak kalemde maliyet eksigi var; once bu kalemler fiyatlandirilmali."
        )
    if not notes:
        notes.append("Maliyet verisi genel olarak tamam gorunuyor; duzenli fiyat guncellemesiyle takip edilebilir.")
    return notes


@reports_bp.route('/costs')
@login_required
@roles_required('Genel')
def cost_report():
    """Maliyet raporu ve analizleri"""
    from app.utils.bom_utils import get_bom_tree, list_boms

    products = Product.query.filter_by(is_active=True).all()
    priced_products = [p for p in products if p.unit_cost and p.unit_cost > 0]
    missing_cost_products = [p for p in products if not (p.unit_cost and p.unit_cost > 0)]

    total_inventory_value = sum(float(p.current_stock or 0) * float(p.unit_cost or 0) for p in products)
    total_stock_qty = sum(float(p.current_stock or 0) for p in products)

    by_type = {}
    by_category = {}
    by_category_count = {}
    for p in products:
        value = float(p.current_stock or 0) * float(p.unit_cost or 0)
        ptype = p.type or 'belirsiz'
        by_type.setdefault(ptype, {'count': 0, 'value': 0.0})
        by_type[ptype]['count'] += 1
        by_type[ptype]['value'] += value

        category_name = p.category.name if p.category else 'Kategorisiz'
        by_category.setdefault(category_name, 0.0)
        by_category[category_name] += value
        by_category_count.setdefault(category_name, 0)
        by_category_count[category_name] += 1

    top_inventory = sorted(
        [
            {
                'code': p.code,
                'name': p.name,
                'stock': float(p.current_stock or 0),
                'unit': p.unit_type,
                'unit_cost': float(p.unit_cost or 0),
                'currency': p.currency or 'TRY',
                'value': float(p.current_stock or 0) * float(p.unit_cost or 0),
            }
            for p in priced_products
            if (p.current_stock or 0) > 0
        ],
        key=lambda row: row['value'],
        reverse=True
    )[:10]

    top_unit_costs = sorted(
        [
            {
                'code': p.code,
                'name': p.name,
                'type': p.type,
                'unit_cost': float(p.unit_cost or 0),
                'currency': p.currency or 'TRY',
                'unit': p.unit_type,
            }
            for p in priced_products
        ],
        key=lambda row: row['unit_cost'],
        reverse=True
    )[:10]

    bom_costs = []
    bom_missing_cost_count = 0
    for bom in list_boms(db):
        tree = get_bom_tree(bom['bom_id'], db)
        roots = tree.get('roots') or []
        if not roots:
            continue
        nodes = list(_iter_bom_nodes(roots))
        leaf_nodes = [node for node in nodes if not node.get('children')]
        missing = sum(
            1 for node in leaf_nodes
            if not (node.get('unit_cost') and node.get('unit_cost') > 0)
            and not (node.get('total_cost') and node.get('total_cost') > 0)
        )
        bom_missing_cost_count += missing
        root = roots[0]
        bom_costs.append({
            'bom_id': bom['bom_id'],
            'name': bom.get('root_name') or f"BOM #{bom['bom_id']}",
            'total_cost': float(root.get('total_cost') or 0),
            'currency': root.get('currency') or 'TRY',
            'node_count': bom.get('node_count') or len(nodes),
            'missing_cost_count': missing,
        })

    bom_costs = sorted(bom_costs, key=lambda row: row['total_cost'], reverse=True)[:10]

    stats = {
        'total_products': len(products),
        'priced_count': len(priced_products),
        'missing_cost_count': len(missing_cost_products),
        'total_inventory_value': total_inventory_value,
        'total_stock_qty': total_stock_qty,
        'by_type': by_type,
        'by_category': dict(sorted(by_category.items(), key=lambda item: item[1], reverse=True)[:8]),
        'by_category_count': dict(sorted(by_category_count.items(), key=lambda item: item[1], reverse=True)[:8]),
        'top_inventory': top_inventory,
        'top_unit_costs': top_unit_costs,
        'bom_costs': bom_costs,
        'bom_missing_cost_count': bom_missing_cost_count,
        'analysis': [],
    }
    stats['analysis'] = _cost_report_analysis(stats)

    return render_template('reports/costs.html', stats=stats)


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
