# Utils package

def sanitize_part_code(code):
    """Parça/ürün kodundaki '%' karakterini '-' ile değiştirir.

    '%' SQL LIKE joker karakteridir; kod içinde yer alırsa arama
    (ör. Product.code.ilike(f'%{q}%')) sorgularında beklenmeyen
    eşleşmelere/sonuçlara yol açar. Bu nedenle tüm giriş noktalarında
    (Excel import, form, API) kod bu fonksiyondan geçirilmelidir.
    """
    if code is None:
        return code
    text = str(code).strip()
    if not text:
        return text
    return text.replace('%', '-')


def generate_missing_part_code(entity_id) -> str:
    """Parça kodu olmayan kayıtlar için '999-' önekli bir kod üretir."""
    return f'999-{entity_id}'


def tr_lower(v) -> str:
    """Anahtar kelime eşleştirmesi için Türkçe-güvenli küçük harfe çevirme.

    Python'un standart `str.lower()` metodu Türkçe 'İ' harfini (U+0130) tek bir
    ASCII 'i' değil, 'i' + görünmez birleşik nokta (U+0307) olarak küçültür
    (`'İ'.lower() == 'i̇'`, 2 karakter). Bu, "FİRELİ", "ADLANDIRMASI" gibi
    başlıklarda `'fireli' in text.lower()` türü kontrolleri sessizce başarısız
    kılar. Doğru Türkçe kuralı: noktalı 'İ' → 'i', noktasız 'I' → 'ı' — bu
    yüzden 'I'yı da düz 'i'ye çevirmek "AĞIRLIK" gibi kelimeleri de bozar
    ("ağırlık" değil "ağirlik" üretir). Bu fonksiyon her ikisini de doğru
    eşlemeyle çevirir. Excel başlık/anahtar kelime eşleştirmesi yapan her
    yerde (bom_utils.py, excel_utils.py) kullanılmalıdır.
    """
    text = str(v) if v is not None else ''
    return text.replace('İ', 'i').replace('I', 'ı').lower()
