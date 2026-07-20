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
