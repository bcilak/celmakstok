"""
BOM (Bill of Materials) Utility Fonksiyonları
==============================================
ÇELMAK Ürün Ağacı Excel formatı — iki format desteklenir:

FORMAT A — Numaralandırma Kolonu (ekran görüntüsündeki gerçek format):
  • İlk non-null sütunda "1.1.", "1.1.2." gibi noktalı değerler
  • Bölüm başlıkları: "1. KAFA", "2. GÖVDE" (birleştirilmiş/stillendirilmiş satır)
  • Her bölüm altında bir başlık satırı (Numara | Adlandırması | ... atlanır)
  • Parça adı, kod, malzeme cinsi, adet kolonları

FORMAT B — Kolon Girintisi  (urun_agaci_sablon.xlsx şablonu):
  • Col A: Ana ürün adı (sadece 1. satır)
  • Col B: L1 grup (Kasa, Şase, Dingil…)
  • Col C: L2 alt grup
  • Col D: Parça adı
  • Col H: Adet, Col I: Birim
"""

import re
import openpyxl
from decimal import Decimal


# ---------------------------------------------------------------------------
# Ürün kodu üreteci
# ---------------------------------------------------------------------------

_TR_MAP = {'\u00e7': 'C', '\u00c7': 'C', '\u011f': 'G', '\u011e': 'G', '\u0131': 'I', '\u0130': 'I',
           '\u00f6': 'O', '\u00d6': 'O', '\u015f': 'S', '\u015e': 'S', '\u00fc': 'U', '\u00dc': 'U'}


def _make_product_code(name: str, bom_code: str = '') -> str:
    """Ürün adından veya mevcut BOM kodundan ürün kodu üretir."""
    if bom_code and bom_code.strip():
        s = bom_code.strip()
    else:
        s = name
    for k, v in _TR_MAP.items():
        s = s.replace(k, v)
    s = re.sub(r'[^A-Za-z0-9]', '-', s).upper()
    s = re.sub(r'-+', '-', s).strip('-')
    return s[:20] or 'BOM'


def _unique_product_code(base: str) -> str:
    """Benzersiz ürün kodu döndürür; gerekirsge sayısal sone ekler."""
    from app.models import Product
    code = base
    suffix = 1
    while Product.query.filter_by(code=code).first():
        code = f'{base[:17]}-{suffix:02d}'
        suffix += 1
    return code

# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _c(v) -> str:
    """None → '' temizleyici."""
    return '' if v is None else str(v).strip()


def _float(v, default=1.0) -> float:
    try:
        return float(str(v).replace(',', '.').strip())
    except Exception:
        return default


_NUM_RE = re.compile(r'^\s*\d+(\.\d+)*\.?\s*$')    # "1.", "1.1.", "1.1.2", "10.5.3."
_SEC_RE = re.compile(r'^\s*(\d+)\.\s+\S')          # "1. KAFA", "2. GÖVDE"


def _is_num(v: str) -> bool:
    """Noktalı BOM hiyerarşi numaraları: '1.', '1.1.', '1.1.2.' — en az bir nokta gerekli.
    Sıralı integer sayaçlarını (1, 2, 3...) BOM numarası olarak algılamamak için."""
    return '.' in v and bool(_NUM_RE.match(v))


def _normalize_num(v: str) -> str:
    """Son nokta yoksa ekle: "1.1.2" → "1.1.2." """
    s = v.strip()
    return s if s.endswith('.') else s + '.'


def _calc_level(num: str) -> int:
    """
    "1."       → 1
    "1.1."     → 2
    "1.1.1."   → 3
    """
    return len([p for p in num.split('.') if p.strip()])


def _unit_str(v: str) -> str:
    """Excel birim metnini normalleştirir.
    Desteklenen tipler: adet, kg, gr, ton, metre, cm, mm, m², m³, litre, paket, rulo, takim
    """
    if not v:
        return 'adet'
    ui = v.strip().lower()
    if not ui or ui in ('nan', 'none'):
        return 'adet'
    # Ağırlık
    if 'ton' in ui and 'kilo' not in ui:
        return 'ton'
    if 'kilogram' in ui or ui in ('kg', 'kilo'):
        return 'kg'
    if 'gram' in ui and 'kilo' not in ui:
        return 'gr'
    # Alan / hacim
    if 'metre kare' in ui or 'm2' in ui or 'm²' in ui or 'metrekare' in ui:
        return 'm²'
    if 'metre küp' in ui or 'm3' in ui or 'm³' in ui or 'metreküp' in ui:
        return 'm³'
    # Uzunluk
    if 'santimetre' in ui or ui in ('cm', 'santim'):
        return 'cm'
    if 'milimetre' in ui or ui == 'mm':
        return 'mm'
    if 'metre' in ui or ui in ('mt', 'm'):
        return 'metre'
    # Diğer
    if 'litre' in ui or ui in ('lt', 'l'):
        return 'litre'
    if 'rulo' in ui:
        return 'rulo'
    if 'paket' in ui or ui in ('pkt', 'pk'):
        return 'paket'
    if 'takım' in ui or 'takim' in ui or ui == 'set':
        return 'takım'
    if 'kutu' in ui:
        return 'kutu'
    # Bilinmeyeni olduğu gibi küçük harfle döndür
    return ui


# ---------------------------------------------------------------------------
# FORMAT TESPİTİ
# ---------------------------------------------------------------------------

def _detect_format(ws) -> str:
    """
    İlk 15 dolu satırı inceleyerek formatı belirle.
    ÖNCELİK 1: Eğer noktalı BOM numaraları (1.1.) varsa -> FORMAT A ('numbered')
    ÖNCELİK 2: Fireli/Firesiz başlıkları varsa -> FORMAT C ('formatted_bom')
    ÖNCELİK 3: Aksi halde Format B ('indented')
    """
    num_hits = 0
    for row in ws.iter_rows(max_row=20, values_only=True):
        vals = [_c(v) for v in row]
        if not any(vals):
            continue
        # Tüm hücreleri tara — BOM numarası ilk kolonda olmayabilir
        for v in vals:
            if v and (_is_num(v) or _SEC_RE.match(v)):
                num_hits += 1
                break
    
    if num_hits >= 2:
        return 'numbered'

    # FORMAT C tespiti: ÇOK KESİN — aynı satırda hem "fireli" hem "firesiz"
    for row in ws.iter_rows(max_row=3, values_only=True):
        vals = [_c(v).lower() for v in row if v]
        if len(vals) < 5:
            continue
        has_fireli  = any('fireli' in v for v in vals)
        has_firesiz = any('firesiz' in v for v in vals)
        has_metre_or_parca = any(('metre' in v or 'parça kodu' in v) for v in vals)
        if has_fireli and has_firesiz and has_metre_or_parca:
            return 'formatted_bom'

    return 'indented'


# ---------------------------------------------------------------------------
# FORMAT A — Numaralandırma Kolonu
# ---------------------------------------------------------------------------

def _parse_numbered(ws, override_root_name=None) -> tuple[list[dict], list[dict]]:
    rows   = []
    errors = []
    stack  = {}  # level → current num

    # ROW 1'İ root olarak kaydet (Ana ürün adı ilk dolu hücrede)
    first = list(ws.iter_rows(max_row=1, values_only=True))[0]
    root_name = ''
    for v in first:
        s = _c(v)
        # Tam sayı (0, 1, 2...), BOM numarası (1., 1.1.) ve bölüm başlığı (1. KAFA) dışındaki ilk değer ürn adı
        if s and not _is_num(s) and not _SEC_RE.match(s) and not re.match(r'^\d+$', s):
            root_name = s
            break
    if not root_name:
        root_name = 'ANA ÜRÜN'
    if override_root_name:
        root_name = override_root_name

    rows.append({'num': '0.', 'level': 0, 'name': root_name, 'code': '',
                 'material': '', 'quantity': 1.0, 'unit_type': 'adet',
                 'quantity_net': 1.0, 'piece_count': 1.0, 'weight_per_unit': 0.0, 'weight_unit': '',
                 'parent_num': None, 'excel_row': 1})
    stack[0] = '0.'

    # Başlık satırları — "Numara", "Adlandırması" gibi metinler içeren satırları bul/atla
    _HEADER_WORDS = {'numara', 'adlandırma', 'parca', 'parça', 'malzeme', 'kod',
                     'adet', 'açıklama', 'description', 'item', 'qty'}

    _INT_RE = re.compile(r'^\s*\d+\s*$')   # Sadece tam sayı: "0", "1", "123" — BOM numarası değil

    def _is_header_row(rv: list[str]) -> bool:
        non_empty = [v.lower() for v in rv if v and not re.match(r'^\d+$', v)]
        if not non_empty:
            return False
        return any(any(h in w for h in _HEADER_WORDS) for w in non_empty)

    col_map = {}
    col_map_found = False

    for row_idx, row_vals in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        rv_raw = list(row_vals)
        rv = [_c(v) for v in rv_raw]
        if not any(rv):
            continue

        rv_lower = [str(x).lower().strip() for x in rv]
        if not col_map_found and any('numara' in x for x in rv_lower) and any('adlandır' in x for x in rv_lower):
            col_map_found = True
            for c, val in enumerate(rv_lower):
                if 'numara' in val: col_map['num'] = c
                elif 'adlandır' in val and 'name' not in col_map: col_map['name'] = c
                elif 'cinsi' in val: col_map['type'] = c
                elif 'kodu' in val: col_map['code'] = c
                elif 'özellik' in val or 'ozelligi' in val or 'özelliği' in val: col_map['spec'] = c
                elif 'fireli metre' in val: col_map['fireliM'] = c
                elif 'firesiz metre' in val: col_map['firesizM'] = c
                elif 'fireli ağırlık' in val or 'fireli agirlik' in val: col_map['fireliA'] = c
                elif 'firesiz ağırlık' in val or 'firesiz agirlik' in val: col_map['firesizA'] = c
                elif val == 'adet' or 'toplam adet' in val: col_map['qty'] = c
                elif 'fire miktarı' in val or 'fire miktari' in val or 'fire' in val: col_map['fireM'] = c
            continue

        # BOM numarası içeren ilk hücreyi bul (noktalı format aranır)
        first_val = ''
        first_col = -1
        
        if col_map_found and 'num' in col_map and col_map['num'] < len(rv):
            cv = rv[col_map['num']]
            if cv and (_is_num(cv) or _SEC_RE.match(cv)):
                first_val = cv
                first_col = col_map['num']

        if first_col == -1:
            for ci, v in enumerate(rv):
                if v and _is_num(v):
                    first_val = v
                    first_col = ci
                    break

        if first_col == -1:
            for ci, v in enumerate(rv):
                if v:
                    first_val = v
                    first_col = ci
                    break

        # Bölüm başlığı: "1. KAFA", "2. GÖVDE" — bunları L1 düğüm yap
        sec_m = _SEC_RE.match(first_val)
        if sec_m:
            cnt1 = len([r for r in rows if r['level'] == 1]) + 1
            num = f'{cnt1}.'
            group_name = re.sub(r'^\s*\d+\.\s*', '', first_val).strip() or first_val
            parent_num = stack.get(0)
            stack[1] = num
            for k in [l for l in list(stack) if l > 1]: del stack[k]
            rows.append({'num': num, 'level': 1, 'name': group_name, 'code': '',
                         'material': '', 'quantity': 1.0, 'unit_type': 'adet',
                         'quantity_net': 1.0, 'piece_count': 1.0, 'weight_per_unit': 0.0, 'weight_unit': '',
                         'parent_num': parent_num, 'excel_row': row_idx})
            continue

        # Başlık satırı → atla
        if _is_header_row(rv) and not _is_num(first_val):
            continue

        # Numara hücresi — noktalı BOM numarası olmalı
        if not _is_num(first_val):
            continue  # değer yok veya tanınmıyor

        num = _normalize_num(first_val)
        level = _calc_level(num)

        name = ''
        code = ''
        material = ''
        qty_fireli  = 0.0
        qty_firesiz = 0.0
        unit        = 'adet'
        w_val  = 0.0
        w_unit = ''

        if col_map_found and 'name' in col_map:
            name = _c(rv[col_map['name']]) if col_map['name'] < len(rv) else ''
            typ = _c(rv[col_map['type']]) if 'type' in col_map and col_map['type'] < len(rv) else ''
            spc = _c(rv[col_map['spec']]) if 'spec' in col_map and col_map['spec'] < len(rv) else ''
            # Ölçü (typ = Malzeme Cinsi: Ø76×5) ve Özellik (spc: Sanayi Borusu) birleştir => "Sanayi Borusu Ø76x5"
            if typ and spc:
                material = f"{spc} {typ}".strip()
            else:
                material = typ or spc
            code = _c(rv[col_map['code']]) if 'code' in col_map and col_map['code'] < len(rv) else ''
            
            e_val = _float(rv_raw[col_map['fireliM']], 0.0) if 'fireliM' in col_map and col_map['fireliM'] < len(rv_raw) else 0.0
            f_val = _float(rv_raw[col_map['firesizM']], 0.0) if 'firesizM' in col_map and col_map['firesizM'] < len(rv_raw) else 0.0
            g_val = _float(rv_raw[col_map['fireliA']], 0.0) if 'fireliA' in col_map and col_map['fireliA'] < len(rv_raw) else 0.0
            h_val = _float(rv_raw[col_map['firesizA']], 0.0) if 'firesizA' in col_map and col_map['firesizA'] < len(rv_raw) else 0.0
            i_val = _float(rv_raw[col_map['qty']], 1.0) if 'qty' in col_map and col_map['qty'] < len(rv_raw) else 1.0
            
            if e_val > 0:
                qty_fireli  = e_val
                qty_firesiz = f_val if f_val > 0 else e_val
                unit        = 'metre'
                w_val  = round(g_val / e_val, 4) if g_val > 0 and e_val > 0 else 0.0
                w_unit = 'kg'
                pc_val = i_val
            elif g_val > 0:
                qty_fireli  = g_val
                qty_firesiz = h_val if h_val > 0 else g_val
                unit        = 'kg'
                w_val  = 0.0
                w_unit = 'kg'
                pc_val = i_val
            else:
                qty_fireli  = i_val
                qty_firesiz = i_val
                pc_val = i_val
                unit        = 'adet'
                w_val  = 0.0
                w_unit = ''
                
        else:
            remaining = [(ci, v) for ci, v in enumerate(rv) if ci > first_col and v]
            if remaining:
                name = remaining[0][1]
            candidate_material = _c(rv[first_col + 2]) if len(rv) > first_col + 2 else ''
            candidate_code = _c(rv[first_col + 3]) if len(rv) > first_col + 3 else ''
            code = candidate_code
            material = candidate_material

            if not material and not code and len(remaining) >= 2:
                candidate = remaining[1][1]
                if re.match(r'^[A-Za-z0-9\-]{4,}$', candidate.replace(' ', '')) and ('-' in candidate or any(c.isdigit() for c in candidate)):
                    code = candidate
                    if len(remaining) >= 3:
                        material = remaining[2][1]
                else:
                    material = candidate
                    if len(remaining) >= 3:
                        cand3 = remaining[2][1]
                        if '-' in cand3 or any(d.isdigit() for d in cand3):
                            code = cand3

            qty_raw = None
            for _, v in reversed(remaining):
                f = _float(v, default=-1)
                if 0 < f < 100000:
                    qty_raw = f
                    break
            unit_raw = ''
            for _, v in remaining:
                if v.lower() in ('adet', 'kg', 'kilogram', 'metre', 'mt', 'm2'):
                    unit_raw = v
                    break

            qty_fireli  = qty_raw if qty_raw is not None else 1.0
            qty_firesiz = qty_fireli
            unit = _unit_str(unit_raw)
            pc_val = 1.0  # Default piece count
            w_val = 0.0
            w_unit = ''

        if not name:
            errors.append({'row': row_idx, 'error': f'{num} için ad bulunamadı — atlandı'})
            continue

        for k in [l for l in list(stack) if l > level]: del stack[k]
        parent_num = stack.get(level - 1)
        stack[level] = num

        rows.append({'num': num, 'level': level, 'name': name, 'code': code,
                     'material': material, 'quantity': qty_fireli, 'unit_type': unit,
                     'quantity_net': qty_firesiz, 'weight_per_unit': w_val, 'weight_unit': w_unit,
                         'piece_count': pc_val,
                     'parent_num': parent_num, 'excel_row': row_idx})

    return rows, errors


# ---------------------------------------------------------------------------
# FORMAT B — Kolon Girintisi (ÇELMAK ürün ağacı)
# ---------------------------------------------------------------------------
# Sütun düzeni (GERGEÇ Excel yapısı):
#   A (0): Ana ürün adı   B (1): L1 grup         C (2): L2 alt grup
#   D (3): Parça adı     E (4): Malzeme/Özellik
#   F (5): Birim ağırlık  G (6): Ağırlık birimi (Kilogram)
#   H (7): Firesiz adet  I (8): Birim (Adet)
#   J (9): Toplam ağırlık  K (10): Ağırlık birimi
#   L (11): Fireli adet  M (12): Birim (Adet)
# ---------------------------------------------------------------------------

def _parse_indented(ws, override_root_name=None) -> tuple[list[dict], list[dict]]:
    rows   = []
    errors = []
    stack  = {0: None}
    cnt    = {1: 0, 2: 0, 3: 0}

    # İlk satırdan ana ürün adını al (Col A)
    first = list(ws.iter_rows(max_row=1, values_only=True))[0]
    root_name = _c(first[0]) if first else 'ANA ÜRÜN'
    if not root_name:
        root_name = 'ANA ÜRÜN'
    if override_root_name:
        root_name = override_root_name

    rows.append({'num': '0.', 'level': 0, 'name': root_name, 'code': '',
                 'material': '', 'quantity': 1.0, 'unit_type': 'adet',
                 'quantity_net': 1.0, 'piece_count': 1.0, 'weight_per_unit': 0.0, 'weight_unit': '',
                 'parent_num': None, 'excel_row': 1})
    stack[0] = '0.'

    last_l1 = None
    last_l2 = None

    def emit(level_: int, name_: str,
             qty_fireli: float, qty_firesiz: float,
             unit_: str, mat_: str,
             weight_val: float, weight_u: str, ridx: int):
        nonlocal last_l1, last_l2
        if level_ == 1:
            cnt[1] += 1; cnt[2] = 0; cnt[3] = 0
            num_ = f'{cnt[1]}.'; last_l1 = name_; last_l2 = None
        elif level_ == 2:
            cnt[2] += 1; cnt[3] = 0
            num_ = f'{cnt[1]}.{cnt[2]}.'; last_l2 = name_
        else:
            cnt[3] += 1
            num_ = (f'{cnt[1]}.{cnt[2]}.{cnt[3]}.' if cnt[2] > 0
                    else f'{cnt[1]}.0.{cnt[3]}.')

        # En yakın mütıfar eşleşitir — boşluk olsa bile köke fallback yap
        parent_ = None
        for lv in range(level_ - 1, -1, -1):
            p = stack.get(lv)
            if p is not None:
                parent_ = p
                break
        stack[level_] = num_
        for k in [l for l in list(stack) if l > level_]: del stack[k]

        rows.append({
            'num': num_, 'level': level_, 'name': name_, 'code': '',
            'material': mat_, 'quantity': qty_fireli, 'unit_type': unit_,
            'quantity_net': qty_firesiz,
            'weight_per_unit': weight_val, 'weight_unit': weight_u,
            'parent_num': parent_, 'excel_row': ridx
        })

    for row_idx, row_vals in enumerate(ws.iter_rows(min_row=1, values_only=True), start=1):
        rv = list(row_vals)
        col_b = _c(rv[1])  if len(rv) > 1  else ''   # L1 grup
        col_c = _c(rv[2])  if len(rv) > 2  else ''   # L2 alt grup
        col_d = _c(rv[3])  if len(rv) > 3  else ''   # Parça adı
        col_e = _c(rv[4])  if len(rv) > 4  else ''   # Malzeme / Özellik / Boyut
        col_f = rv[5]      if len(rv) > 5  else None  # Birim ağırlık değeri
        col_g = _c(rv[6])  if len(rv) > 6  else ''   # Ağırlık birimi (Kilogram)
        col_h = rv[7]      if len(rv) > 7  else None  # Firesiz adet
        col_i = _c(rv[8])  if len(rv) > 8  else ''   # Firesiz birimi (Adet/Metre/Kg)
        col_l = rv[11]     if len(rv) > 11 else None  # Fireli (toplam) adet
        col_m = _c(rv[12]) if len(rv) > 12 else ''   # Fireli birimi (ASIL birim — öncelikli)

        if not col_b and not col_c and not col_d:
            continue

        # ------- Miktar: fireli (col L) öncelikli, yoksa firesiz, yoksa 1 -------
        qty_fireli  = _float(col_l, default=0.0) if col_l is not None else 0.0
        qty_firesiz = _float(col_h, default=0.0) if col_h is not None else 0.0
        qty_use     = (qty_fireli  if qty_fireli  > 0 else
                       qty_firesiz if qty_firesiz > 0 else 1.0)

        # ------- Birim: col M (fireli birimi) öncelikli, yoksa col I (firesiz birimi) -------
        # Col M ve Col I farklı olabilir ama çoğunlukla aynıdır.
        # Col M = fireli adede ait birim → asil kullanım birimi
        raw_unit = col_m if (col_m and col_m.lower() not in ('nan', 'none', '')) else col_i
        unit_str = _unit_str(raw_unit)

        # ------- Ağırlık bilgisi -------
        # Col F = birim ağırlık (her zaman kg cinsindendir)
        # Col G = ağırlık birimi (genellikle 'Kilogram')
        # Birim zaten 'kg' ise (ağırlık bazlı ölçüm), col F ayrıca saklanmaz — miktarın kendisi ağırlık
        weight_val = _float(col_f, default=0.0) if col_f is not None else 0.0
        col_g_lo   = col_g.lower()
        weight_u   = ('kg' if ('kilo' in col_g_lo or col_g_lo in ('kg', ''))
                      else _unit_str(col_g))

        if row_idx == 1:
            if col_b and col_b != last_l1:
                emit(1, col_b, 1.0, 1.0, 'adet', '', 0.0, '', row_idx)
            if col_c and col_c != last_l2:
                emit(2, col_c, 1.0, 1.0, 'adet', '', 0.0, '', row_idx)
            if col_d:
                emit(3, col_d, qty_use, qty_firesiz, unit_str, col_e,
                     weight_val, weight_u, row_idx)
            continue

        if col_b and col_b != last_l1:
            emit(1, col_b, 1.0, 1.0, 'adet', '', 0.0, '', row_idx)
        if col_c and col_c != last_l2:
            emit(2, col_c, 1.0, 1.0, 'adet', '', 0.0, '', row_idx)
        if col_d:
            emit(3, col_d, qty_use, qty_firesiz, unit_str, col_e,
                 weight_val, weight_u, row_idx)

    return rows, errors


# ---------------------------------------------------------------------------
# FORMAT C — Başlık Satırlı BOM (Parça Kodu, Fireli/Firesiz Metre & Ağırlık)
# ---------------------------------------------------------------------------
# Sütun düzeni (başlık satırından sonra):
#   A (0): Adlandırılması (parça/montaj adı)
#   B (1): Malzeme Cinsi (e.g., "185x75x4", "4 mm", "Montaj")
#   C (2): Parça Kodu    (e.g., "3TB-P0201-099-50")
#   D (3): Malzeme Özelliği (e.g., "Profil", "Siyah Sac (St3237)")
#   E (4): Toplam Fireli Metre
#   F (5): Toplam Firesiz Metre
#   G (6): Toplam Fireli Ağırlık (kg)
#   H (7): Toplam Firesiz Ağırlık (kg)
#   I (8): Toplam Adet
#   J (9): Toplam Fire
#
# Montaj (assembly) satırı tespiti:
#   1. Sarı/altın renk dolgu (Excel cell fill)
#   2. Fallback: Col B "Montaj" içeriyorsa
#   3. Fallback: Tüm E-H değerleri sıfır ama Col I > 0
# ---------------------------------------------------------------------------

def _cell_is_yellow(cell) -> bool:
    """Hücre dolgusu sarı/altın tonundaysa True."""
    try:
        fill = cell.fill
        if fill.fill_type == 'solid':
            rgb = fill.fgColor.rgb  # ARGB: 'FFRRGGBB'
            if len(rgb) == 8:
                r = int(rgb[2:4], 16)
                g = int(rgb[4:6], 16)
                b = int(rgb[6:8], 16)
                # Sarı/altın/turuncu: yüksek R, orta-yüksek G, düşük B
                if r > 180 and g > 120 and b < 80:
                    return True
    except Exception:
        pass
    return False


def _is_format_c_header(sv: list[str]) -> bool:
    """Bir satırın FORMAT C başlık satırı olup olmadığını kontrol eder."""
    if len([v for v in sv if v]) < 5:
        return False
    vals = [v.lower() for v in sv if v]
    has_fireli  = any('fireli' in v for v in vals)
    has_firesiz = any('firesiz' in v for v in vals)
    has_metre_or_parca = any(('metre' in v or 'parça kodu' in v) for v in vals)
    return has_fireli and has_firesiz and has_metre_or_parca


def _parse_format_c(ws, override_root_name=None) -> tuple[list[dict], list[dict]]:
    rows   = []
    errors = []

    # İlk 3 satırı tara: başlık satırı satır numarasını bul, ürün adını tespit et
    header_row_idx = None
    root_name      = 'ANA ÜRÜN'
    for i, row_vals in enumerate(ws.iter_rows(max_row=3, values_only=True), start=1):
        sv = [_c(v) for v in row_vals]
        if _is_format_c_header(sv):
            header_row_idx = i
            break
        else:
            # Başlık değil → ürün adı adayı
            non_empty = [v for v in sv if v]
            if non_empty:
                root_name = non_empty[0]
                
    if override_root_name:
        root_name = override_root_name

    rows.append({'num': '0.', 'level': 0, 'name': root_name, 'code': '',
                 'material': '', 'quantity': 1.0, 'unit_type': 'adet',
                 'quantity_net': 1.0, 'piece_count': 1.0, 'weight_per_unit': 0.0, 'weight_unit': '',
                 'parent_num': None, 'excel_row': 0})

    l1_cnt = 0
    l2_cnt = 0
    current_l1_num = None

    for row_idx, row in enumerate(ws.iter_rows(min_row=1), start=1):
        rv   = [cell.value for cell in row]
        sv   = [_c(v) for v in rv]

        # Başlık veya başlık öncesi satırları atla
        if header_row_idx is not None and row_idx <= header_row_idx:
            continue
        # Başlık satırı tespit edilemedi ise: ilk karşılaşılan header satırını atla
        if header_row_idx is None and _is_format_c_header(sv):
            header_row_idx = row_idx
            continue

        if not any(sv):
            continue  # boş satır

        col_a = sv[0]  if len(sv) > 0 else ''   # Ad
        col_b = sv[1]  if len(sv) > 1 else ''   # Malzeme Cinsi
        col_c = sv[2]  if len(sv) > 2 else ''   # Parça Kodu
        col_d = sv[3]  if len(sv) > 3 else ''   # Malzeme Özelliği
        e_val = _float(rv[4], 0.0) if len(rv) > 4 and rv[4] is not None else 0.0  # Fireli Metre
        f_val = _float(rv[5], 0.0) if len(rv) > 5 and rv[5] is not None else 0.0  # Firesiz Metre
        g_val = _float(rv[6], 0.0) if len(rv) > 6 and rv[6] is not None else 0.0  # Fireli Ağırlık
        h_val = _float(rv[7], 0.0) if len(rv) > 7 and rv[7] is not None else 0.0  # Firesiz Ağırlık
        i_val = _float(rv[8], 1.0) if len(rv) > 8 and rv[8] is not None else 1.0  # Adet

        if not col_a:
            continue

        # ——— Montaj (assembly) satırı mı? ———
        # Güvenilir göstergeler: sarı hücre dolgusu VEYA col_b = "Montaj"
        # NOT: E-H=0 ve I>0 koşulu adet bazlı bileşenleri de yakalar → kullanılmaz
        is_assembly = _cell_is_yellow(row[0])
        if not is_assembly:
            col_b_low = col_b.lower()
            if col_b_low in ('montaj', 'assembly', 'alt montaj', 'submontaj', 'montage'):
                is_assembly = True

        if is_assembly:
            l1_cnt += 1
            l2_cnt = 0
            current_l1_num = f'{l1_cnt}.'
            adet = i_val if i_val > 0 else 1.0
            rows.append({
                'num': current_l1_num, 'level': 1,
                'name': col_a, 'code': col_c,
                'material': col_b, 'quantity': adet, 'unit_type': 'adet',
                'quantity_net': adet,
                'weight_per_unit': 0.0, 'weight_unit': '',
                'parent_num': '0.', 'excel_row': row_idx
            })
        else:
            # ——— Bileşen satırı ———
            if current_l1_num is None:
                # Henüz montaj başlığı yok → genel grup oluştur
                l1_cnt += 1
                l2_cnt = 0
                current_l1_num = f'{l1_cnt}.'
                rows.append({
                    'num': current_l1_num, 'level': 1,
                    'name': 'Genel', 'code': '',
                    'material': '', 'quantity': 1.0, 'unit_type': 'adet',
                    'quantity_net': 1.0, 'piece_count': 1.0, 'weight_per_unit': 0.0, 'weight_unit': '',
                    'parent_num': '0.', 'excel_row': row_idx
                })

            l2_cnt += 1
            num = f'{l1_cnt}.{l2_cnt}.'

            # ——— Birim ve miktar tespiti ———
            if e_val > 0:
                # Metre bazlı ölçüm
                qty_fireli  = e_val
                qty_firesiz = f_val if f_val > 0 else e_val
                unit        = 'metre'
                # Birim ağırlık = toplam ağırlık / metre
                w_val  = round(g_val / e_val, 4) if g_val > 0 and e_val > 0 else 0.0
                w_unit = 'kg'
                pc_val = i_val
            elif g_val > 0:
                # Ağırlık bazlı ölçüm (sac, levha vb.)
                qty_fireli  = g_val
                qty_firesiz = h_val if h_val > 0 else g_val
                unit        = 'kg'
                w_val  = 0.0
                w_unit = 'kg'
                pc_val = i_val
            else:
                # Adet bazlı (aksesuar, bağlantı elemanı vb.)
                qty_fireli  = i_val
                qty_firesiz = i_val
                pc_val = i_val
                unit        = 'adet'
                w_val  = 0.0
                w_unit = ''

            # material: Özel format (Özellik + Cins) => Örn: "Sanayi Borusu Ø76x5 mm"
            if col_b and col_d and col_b.lower() not in ('montaj', 'assembly', 'alt montaj', 'submontaj', 'montage'):
                mat = f"{col_d} {col_b}".strip()
            else:
                mat = col_d if col_d else col_b

            rows.append({
                'num': num, 'level': 2,
                'name': col_a, 'code': col_c,
                'material': mat, 'quantity': qty_fireli, 'unit_type': unit,
                'quantity_net': qty_firesiz,
                'weight_per_unit': w_val, 'weight_unit': w_unit,
                         'piece_count': pc_val,
                'parent_num': current_l1_num, 'excel_row': row_idx
            })

    return rows, errors


# ---------------------------------------------------------------------------
# ANA GİRİŞ NOKTASI
# ---------------------------------------------------------------------------

def parse_bom_excel_v2(file_stream, override_root_name=None) -> tuple[list[dict], list[dict]]:
    """
    ÇELMAK ürün ağacı Excel dosyasını parse eder.
    Format otomatik tespit edilir (numara kolonlu veya kolon girintili).
    """
    try:
        wb = openpyxl.load_workbook(file_stream, data_only=True)
        ws = wb.active
    except Exception as exc:
        return [], [{'row': 0, 'error': f'Dosya okuma hatası: {exc}'}]

    fmt = _detect_format(ws)

    if fmt == 'formatted_bom':
        rows, errors = _parse_format_c(ws, override_root_name)
    elif fmt == 'numbered':
        rows, errors = _parse_numbered(ws, override_root_name)
    else:
        rows, errors = _parse_indented(ws, override_root_name)

    if len(rows) <= 1:
        return [], [{'row': 0, 'error':
            f'Excel\'den hiç parça çıkarılamadı (format={fmt}). '
            'Numara kolonunu veya kolon yapısını kontrol edin.'}]

    # --- YarıMamül ve Otomatik Hammadde Dönüşümü ---
    transformed_rows = []
    standard_prefixes = {'201', '202', '203', '204', '205', '206', '207', '208', '209', 
                         '210', '211', '212', '213', '214', '216', '217', '219'}

    for r in rows:
        mat_str = str(r.get('material', '')).strip()
        c_prefix = str(r.get('code') or '')[:3]
        
        is_assembly = mat_str.lower() in ('montaj', 'assembly', 'alt montaj', 'submontaj', 'montage')
        is_standard = c_prefix in standard_prefixes or mat_str.lower() == 'standart parça'
        
        # Eğer bir montaj/seviye 0 değilse, standart parça değilse ve malzemesi varsa:
        needs_child = not is_assembly and not is_standard and bool(mat_str) and r['level'] > 0
        
        if is_standard:
            # Standart Parçaların birimi her zaman "adet" olmalıdır
            parent_qty = r.get('piece_count', 1.0)
            r['quantity'] = parent_qty
            r['quantity_net'] = parent_qty
            r['unit_type'] = 'adet'
            transformed_rows.append(r)

        elif needs_child:
            # Yarı Mamul'ün kendi adedi
            parent_qty = r.get('piece_count', 1.0)
            child_qty_fireli = r.get('quantity', parent_qty)
            child_qty_firesiz = r.get('quantity_net', parent_qty)
            child_unit = r.get('unit_type', 'adet')
            
            # Yarı Mamul'ü Adet olarak sabitle
            r['quantity'] = parent_qty
            r['quantity_net'] = parent_qty
            r['unit_type'] = 'adet'
            
            transformed_rows.append(r)
            
            # Hammadde child node oluştur
            child = {
                'num': r['num'] + '1.',
                'level': r['level'] + 1,
                'name': mat_str,  # Malzeme Cinsi + Özelliği
                'code': '',       # Hammaddenin kendi kodu yok, ürün koduna geçmesin
                'material': 'Hammadde',
                'quantity': child_qty_fireli,
                'quantity_net': child_qty_firesiz,
                'unit_type': child_unit,
                'piece_count': 1.0,
                'weight_per_unit': r.get('weight_per_unit', 0.0),
                'weight_unit': r.get('weight_unit', ''),
                'parent_num': r['num'],
                'excel_row': r.get('excel_row', 0),
                'is_auto_hammadde': True
            }
            transformed_rows.append(child)
        else:
            transformed_rows.append(r)

    return transformed_rows, errors


# ---------------------------------------------------------------------------
# BOM Analiz ve Önizleme
# ---------------------------------------------------------------------------

def analyze_bom_for_import(parsed_rows: list[dict], category_id: int = None) -> dict:
    """
    Excel'den parse edilmiş BOM satırlarını analiz eder.
    
    Returns:
        {
            'new_products': [...],      # Yeni eklenecek ürünler
            'existing_products': [...],  # Zaten mevcut ürünler
            'conflicts': [...],          # Çakışma/uyarı gerektiren durumlar
            'stats': {...}               # Özet istatistikler
        }
    """
    from app.models import Product, BomItem
    
    new_products = []
    existing_products = []
    conflicts = []
    
    # Excel dosyasındaki tekrarları (aynı isme sahip aynı parçalar) yakalamak için
    seen_in_excel = {}
    
    standard_prefixes = {'201', '202', '203', '204', '205', '206', '207', '208', '209', 
                        '210', '211', '212', '213', '214', '216', '217', '219'}
    
    for row in parsed_rows:
        code_prefix = str(row.get('code') or '')[:3]
        if code_prefix in standard_prefixes or str(row.get('material', '')).lower() == 'standart parça':
            item_type = 'standart_parca'
        elif row['level'] == 0:
            item_type = 'mamul'
        elif row.get('is_auto_hammadde'): 
            item_type = 'hammadde'
        else:
            item_type = 'yarimamul'
        
        # Mevcut ürünü kontrol et (Adına ve Koda göre)
        excel_code = row.get('code') or ''
        product = Product.query.filter_by(name=row['name']).filter(Product.code == excel_code if excel_code else True).first()
        if not product:
            # Eğer koduyla bulamadıysa ama ismiyle ve boş koduyla varsa falan diye sadece name ile tekrar bakalım, 
            # ancak bu sefer excel_code doluysa ve db_code dolu ve farklıysa BUNLAR FARKLI ÜRÜNDÜR, AYNI SAYMA
            potentials = Product.query.filter_by(name=row['name']).all()
            for p in potentials:
                p_code = p.code or ''
                if not excel_code or not p_code or excel_code == p_code:
                    product = p
                    break
        
        item = BomItem.query.filter_by(name=row['name']).filter(BomItem.code == excel_code if excel_code else True).first()
        if not item:
            potentials_item = BomItem.query.filter_by(name=row['name']).all()
            for i in potentials_item:
                i_code = i.code or ''
                if not excel_code or not i_code or excel_code == i_code:
                    item = i
                    break
        
        entry = {
            'name': row['name'],
            'code': row.get('code') or '',
            'material': row.get('material') or '',
            'unit_type': row['unit_type'],
            'quantity': row['quantity'],
            'item_type': item_type,
            'level': row['level']
        }
        
        # Eğer bu isimli ürün veritabanında yoksa ama bu excel dosyasında daha önce gördüysek, 
        # onu yeni bir ürün olarak tekrar tekrar eklemek yerine "mevcut_excel_tekrarı" gibi değerlendireceğiz.
        
        if not product:
            if row['name'] not in seen_in_excel:
                # Gerçekten yeni ürün
                base_code = _make_product_code(row['name'], row.get('code') or '')
                entry['generated_code'] = _unique_product_code(base_code)
                new_products.append(entry)
                seen_in_excel[row['name']] = True
        else:
            # Mevcut ürün - çakışma kontrolü
            entry['existing_code'] = product.code
            entry['existing_material'] = product.material or ''
            entry['existing_unit_type'] = product.unit_type
            entry['existing_type'] = product.type
            entry['current_stock'] = product.current_stock
            
            # Çakışma tespiti
            issues = []
            updates = []
            
            # Birim tipi farklıysa UYARI
            if product.unit_type != row['unit_type']:
                issues.append({
                    'type': 'unit_mismatch',
                    'message': f"Birim tipi farklı: Mevcut '{product.unit_type}' vs Excel '{row['unit_type']}'"
                })
            
            # Tip farklıysa UYARI
            if product.type != item_type:
                issues.append({
                    'type': 'type_mismatch',
                    'message': f"Ürün tipi farklı: Mevcut '{product.type}' vs Excel '{item_type}'"
                })
            
            # Malzeme bilgisi yoksa eklenecek
            if row.get('material') and not product.material:
                updates.append({
                    'field': 'material',
                    'value': row['material']
                })
            elif row.get('material') and product.material and product.material != row['material']:
                issues.append({
                    'type': 'material_mismatch',
                    'message': f"Malzeme farklı: Mevcut '{product.material}' vs Excel '{row['material']}'"
                })
            
            entry['issues'] = issues
            entry['updates'] = updates
            
            if issues:
                conflicts.append(entry)
            else:
                existing_products.append(entry)
    
    stats = {
        'total': len(parsed_rows),
        'new': len(new_products),
        'existing': len(existing_products),
        'conflicts': len(conflicts),
        'will_update': sum(1 for p in existing_products if p.get('updates'))
    }
    
    return {
        'new_products': new_products,
        'existing_products': existing_products,
        'conflicts': conflicts,
        'stats': stats
    }


# ---------------------------------------------------------------------------
# DB'ye Yükleme
# ---------------------------------------------------------------------------

def import_bom_to_db(parsed_rows: list[dict], bom_id: int, db, category_id: int = None, conflict_resolutions: dict = None) -> dict:
    from app.models import BomItem, BomNode, BomEdge, Product

    num_to_node_id: dict[str, int] = {}
    items_c = nodes_c = edges_c = products_c = 0

    standard_prefixes = {'201', '202', '203', '204', '205', '206', '207', '208', '209', '210', '211', '212', '213', '214', '216', '217', '219'}
    
    # Çakışma çözümlerini hazırla (kullanıcı kararları yoksa default)
    if conflict_resolutions is None:
        conflict_resolutions = {}

    updated_products_c = 0

    for row in parsed_rows:
        code_prefix = str(row.get('code') or '')[:3]
        if code_prefix in standard_prefixes or str(row.get('material', '')).lower() == 'standart parça':
            item_type = 'standart_parca'
        elif row['level'] == 0:
            item_type = 'mamul'
        elif row.get('is_auto_hammadde'):
            item_type = 'hammadde'
        else:
            item_type = 'yarimamul'

        # --- Ağırlık / birim notu oluştur ---
        weight_val  = row.get('weight_per_unit', 0.0) or 0.0
        weight_u    = row.get('weight_unit', '') or ''
        qty_net     = row.get('quantity_net', 0.0) or 0.0
        unit_tp     = row.get('unit_type', 'adet')
        notes_parts = []
        if weight_val > 0:
            # Birim 'kg' ise miktarın kendisi ağırlık, ayrı birim ağırlığı göster
            if unit_tp == 'kg':
                notes_parts.append(f'Miktar ağırlık bazında (ölçüm birimi: {unit_tp})')
            elif unit_tp == 'metre':
                notes_parts.append(f'Birim ağırlık: {weight_val} {weight_u}/m')
            else:
                notes_parts.append(f'Birim ağırlık: {weight_val} {weight_u}')
        if qty_net > 0 and qty_net != row.get('quantity', 0):
            notes_parts.append(f'Firesiz miktar: {qty_net} {unit_tp}')
        product_notes = ' | '.join(notes_parts) or None

        # --- Product Master eşleştirme / oluşturma ---
        excel_code = row.get('code') or ''
        product = Product.query.filter_by(name=row['name']).filter(Product.code == excel_code if excel_code else True).first()
        if not product:
            potentials = Product.query.filter_by(name=row['name']).all()
            for p in potentials:
                p_code = p.code or ''
                if not excel_code or not p_code or excel_code == p_code:
                    product = p
                    break
        
        # Kullanıcı bu ürün için karar verdiyse kontrol et
        resolution = conflict_resolutions.get(row['name'], {})

        if not product:
            base_code = _make_product_code(row['name'], row.get('code') or '')
            code = _unique_product_code(base_code)
            product = Product(
                code=code,
                name=row['name'],
                unit_type=row['unit_type'],
                type=item_type,
                material=row.get('material') or None,
                notes=product_notes,
                category_id=category_id if row['level'] == 0 else None
            )
            db.session.add(product)
            db.session.flush()
            products_c += 1
        else:
            # Mevcut ürün - kullanıcı kararlarına göre güncelle
            product_updated = False
            
            # Malzeme güncellemesi - her zaman güncelle (yeni import değerleri öncelikli)
            if row.get('material') and row['material'] != (product.material or ''):
                product.material = row['material']
                product_updated = True
            
            # Tip güncellemesi
            if resolution.get('update_type', False):
                product.type = item_type
                product_updated = True
            
            # Birim tipi güncellemesi
            if resolution.get('update_unit', False):
                product.unit_type = row['unit_type']
                product_updated = True
            
            # Not bilgisi
            if product_notes and not product.notes:
                product.notes = product_notes
                product_updated = True
            
            if product_updated:
                updated_products_c += 1

        # --- BomItem — name bazlı unique ---
        item = BomItem.query.filter_by(name=row['name']).filter(BomItem.code == excel_code if excel_code else True).first()
        if not item:
            potentials_item = BomItem.query.filter_by(name=row['name']).all()
            for i in potentials_item:
                i_code = i.code or ''
                if not excel_code or not i_code or excel_code == i_code:
                    item = i
                    break

        if not item:
            item = BomItem(
                code=row.get('code') or None,
                name=row['name'],
                unit_type=row['unit_type'],
                type=item_type,
                product_id=product.id,
            )
            db.session.add(item)
            db.session.flush()
            items_c += 1
        else:
            if item.product_id is None:
                item.product_id = product.id
            # Kod varsa ve item'da eksikse güncelle (FORMAT C import)
            if row.get('code') and not item.code:
                item.code = row['code']

        q_net = row.get('quantity_net') or 0.0
        pc_c = row.get('piece_count') or 1.0
        w_val = row.get('weight_per_unit') or 0.0
        w_unt = row.get('weight_unit') or None
        node = BomNode(
            bom_id=bom_id,
            num=row['num'],
            level=row['level'],
            item_id=item.id,
            display_name=row['name'],
            quantity=Decimal(str(row['quantity'])),
            quantity_net=Decimal(str(q_net)) if q_net else None,
            piece_count=Decimal(str(pc_c)) if pc_c else 1,
            weight_per_unit=Decimal(str(w_val)) if w_val else None,
            weight_unit=w_unt,
            unit_type=row['unit_type']
        )
        db.session.add(node)
        db.session.flush()
        nodes_c += 1
        num_to_node_id[row['num']] = node.id

        parent_num = row.get('parent_num')
        parent_node_id = num_to_node_id.get(parent_num) if parent_num else None
        edge = BomEdge(bom_id=bom_id, parent_node_id=parent_node_id,
                       child_node_id=node.id,
                       quantity=Decimal(str(row['quantity'])))
        db.session.add(edge)
        edges_c += 1

    db.session.commit()
    return {
        'nodes': nodes_c, 
        'edges': edges_c, 
        'items': items_c, 
        'products': products_c,
        'updated': updated_products_c
    }


# ---------------------------------------------------------------------------
# Ağaç Sorgulama
# ---------------------------------------------------------------------------

def get_bom_tree(bom_id: int, db) -> dict:
    from app.models import BomNode, BomEdge

    nodes = BomNode.query.filter_by(bom_id=bom_id).order_by(BomNode.num).all()
    edges = BomEdge.query.filter_by(bom_id=bom_id).all()

    if not nodes:
        return {'bom_id': bom_id, 'roots': [],
                'error': 'Bu bom_id için kayıt bulunamadı.'}

    child_to_parent: dict = {}
    child_qty: dict = {}
    for e in edges:
        child_to_parent[e.child_node_id] = e.parent_node_id
        try:    child_qty[e.child_node_id] = float(e.quantity)
        except: child_qty[e.child_node_id] = 1.0

    parent_to_children: dict = {}
    for n in nodes:
        parent_to_children.setdefault(child_to_parent.get(n.id), []).append(n.id)

    node_map = {n.id: n for n in nodes}

    def _num_key(num_str: str) -> tuple:
        """'1.2.3.' → (1, 2, 3) — sayısal sıralama için."""
        try:
            return tuple(int(p) for p in num_str.rstrip('.').split('.') if p)
        except ValueError:
            return (0,)

    def build(nid: int) -> dict:
        n = node_map[nid]
        item    = n.item
        product = item.product if item else None
        children_ids = sorted(parent_to_children.get(nid, []),
                              key=lambda i: _num_key(node_map[i].num))
        # fireli / firesiz
        try:
            q_fireli  = float(n.quantity)     if n.quantity     else child_qty.get(n.id, 1.0)
            q_firesiz = float(n.quantity_net) if n.quantity_net else None
            w_per_unit= float(n.weight_per_unit) if n.weight_per_unit else None
        except Exception:
            q_fireli = child_qty.get(n.id, 1.0)
            q_firesiz = w_per_unit = None

        # Fire oranı (%)
        if q_firesiz and q_fireli and q_firesiz > 0:
            waste_ratio = round((q_fireli - q_firesiz) / q_firesiz * 100, 1)
        else:
            waste_ratio = None

        # item_type: eğer altında çocuk varsa 'yarimamul', yoksa item kaydından al
        has_children = bool(children_ids)
        raw_type = product.type if product and product.type else (item.type if item else 'hammadde')
        
        standard_prefixes = {'201', '202', '203', '204', '205', '206', '207', '208', '209', '210', '211', '212', '213', '214', '216', '217', '219'}
        code_str = str(item.code) if (item and item.code) else (str(product.code) if product else '')
        code_prefix = code_str[:3]
        
        if code_prefix in standard_prefixes:
            display_type = 'standart_parca'
        elif has_children and n.level > 0:
            display_type = 'yarimamul'
        else:
            display_type = raw_type

        built_children = [build(cid) for cid in children_ids]

        if built_children:
            # sum can fail if total_cost is None
            calc_total_cost = sum((c.get('total_cost') or 0.0) for c in built_children)
            
            # Eğer Lama veya hesaplaması kg üzerinden yapılan bir hammaddeyse ve weight_per_unit varsa
            # Üst kırılma da kendi qty_fireli metrajını vs uygulayabilir ancak
            # Alt kırılımların toplamı üst kırılımın 1 ADET (veya toplam) maliyetini oluşturur.
            # q_fireli 'adet' veya 'metre' olabilir. Birim maliyeti bölerken kullanıyoruz:
            calc_unit_cost = (calc_total_cost / q_fireli) if q_fireli and q_fireli > 0 else 0.0
            calc_currency = product.currency if product and product.currency else 'TRY'
        else:
            calc_unit_cost = product.unit_cost if product and product.unit_cost else 0.0
            
            # Eğer "Lama" ise maliyeti KG üzerinden hesaplamalıyız (q_fireli * weight_per_unit)
            material_name = (product.material or '').lower() if product else ''
            is_lama = 'lama' in material_name
            
            # Dışarıdan alınan hazır parça / standart parça (adetle fiyatlanan)
            is_hazir = (raw_type in ['hazir_parca', 'standart_parca'] or display_type in ['hazir_parca', 'standart_parca'])
            
            if is_hazir:
                p_count = float(n.piece_count) if getattr(n, 'piece_count', None) else 1.0
                calc_total_cost = calc_unit_cost * p_count
            elif is_lama and w_per_unit:
                # Toplam ağırlık = metraj (q_fireli) * weight_per_unit
                total_kg = (q_fireli or 0) * (w_per_unit or 0)
                calc_total_cost = (calc_unit_cost * total_kg)
            else:
                calc_total_cost = (calc_unit_cost * q_fireli) if q_fireli else 0.0
            
            calc_currency = product.currency if product and product.currency else 'TRY'

        return {
            'id': n.id, 'num': n.num, 'level': n.level,
            'name': n.display_name,
            'code': item.code if item else None,
            'quantity':   q_fireli,
            'quantity_net': q_firesiz,
            'piece_count': float(n.piece_count) if getattr(n, 'piece_count', None) else 1,
            'waste_ratio':  waste_ratio,
            'weight_per_unit': w_per_unit,
            'weight_unit': n.weight_unit or '',
            'unit': n.unit_type, 'item_id': n.item_id,
            'product_id': item.product_id if item else None,
            'material': product.material if product else None,
            'item_type': display_type,
            'stock_qty': product.current_stock if product else 0,
            'unit_cost': calc_unit_cost,
            'currency': calc_currency,
            'total_cost': calc_total_cost,
            'children': built_children
        }

    root_ids = parent_to_children.get(None, [])
    roots = [build(r) for r in sorted(root_ids, key=lambda i: _num_key(node_map[i].num))]
    return {'bom_id': bom_id, 'roots': roots}


def get_bom_subtree(bom_id: int, node_id: int, db) -> dict:
    """
    Belirli bir düğümden başlayan alt ağacı döndür.
    
    Args:
        bom_id: BOM ID
        node_id: Başlangıç düğüm ID'si
        db: Database session
    
    Returns:
        dict: Tek bir node içeren ağaç yapısı
    """
    # Önce tüm ağacı al
    full_tree = get_bom_tree(bom_id, db)
    
    if not full_tree.get('roots'):
        return {'bom_id': bom_id, 'node': None, 'error': 'BOM bulunamadı'}
    
    # Belirli node'u bul (recursive arama)
    def find_node(nodes, target_id):
        for node in nodes:
            if node['id'] == target_id:
                return node
            if node.get('children'):
                result = find_node(node['children'], target_id)
                if result:
                    return result
        return None
    
    target_node = find_node(full_tree['roots'], node_id)
    
    if not target_node:
        return {'bom_id': bom_id, 'node': None, 'error': 'Düğüm bulunamadı'}
    
    return {
        'bom_id': bom_id,
        'node': target_node,
        'roots': [target_node]  # Excel fonksiyonu için roots formatında
    }


# ---------------------------------------------------------------------------
# Yardımcı Sorgular
# ---------------------------------------------------------------------------

def list_boms(db) -> list[dict]:
    from app.models import BomNode, BomItem, Product, Category
    from sqlalchemy import func
    result = (db.session.query(BomNode.bom_id,
               func.count(BomNode.id).label('node_count'),
               func.min(BomNode.created_at).label('created_at'))
              .group_by(BomNode.bom_id).order_by(BomNode.bom_id).all())
    boms = []
    for r in result:
        root = BomNode.query.filter_by(bom_id=r.bom_id, level=0).first()
        
        # Determine the underlying Product to display Category
        root_product = None
        category_name = None
        if root and root.item and root.item.product:
            root_product = root.item.product
            if root_product.category:
                category_name = root_product.category.name

        boms.append({
            'bom_id': r.bom_id,
            'root_name': root.display_name if root else f'BOM #{r.bom_id}',
            'product_id': root_product.id if root_product else None,
            'category_name': category_name,
            'node_count': r.node_count,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else None
        })
    return boms


def next_bom_id(db) -> int:
    from app.models import BomNode
    from sqlalchemy import func
    return (db.session.query(func.max(BomNode.bom_id)).scalar() or 0) + 1
