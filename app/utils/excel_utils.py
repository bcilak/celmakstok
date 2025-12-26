"""
Excel/CSV Import/Export Utility Fonksiyonları
ÇELMAK Stok Takip Sistemi
"""

import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import datetime


def create_product_template():
    """
    Ürün import için Excel şablonu oluştur
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Ürün Şablonu"

    # Başlıklar
    headers = [
        'Ürün Kodu*',
        'Ürün Adı*',
        'Kategori ID*',
        'Birim Tipi',
        'Mevcut Stok',
        'Minimum Stok',
        'Barkod',
        'Notlar'
    ]

    # Başlık satırını yaz
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Örnek veri
    example_data = [
        ['ORN-001', 'Örnek Ürün 1', '1', 'adet', '100', '10', '', 'Örnek not'],
        ['ORN-002', 'Örnek Ürün 2', '1', 'kg', '50', '5', '1234567890', ''],
    ]

    for row_num, row_data in enumerate(example_data, 2):
        for col_num, value in enumerate(row_data, 1):
            ws.cell(row=row_num, column=col_num, value=value)

    # Kolon genişliklerini ayarla
    column_widths = [15, 30, 12, 12, 12, 12, 15, 30]
    for col_num, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + col_num)].width = width

    # Açıklama sayfası ekle
    ws_info = wb.create_sheet("Bilgi")
    info_text = [
        ["ÇELMAK STOK TAKİP SİSTEMİ - ÜRÜN İMPORT ŞABLONU", ""],
        ["", ""],
        ["Açıklama:", ""],
        ["* ile işaretli alanlar zorunludur", ""],
        ["", ""],
        ["Alan Açıklamaları:", ""],
        ["Ürün Kodu", "Ürününüzün benzersiz kodu (örn: HM-001, OS-123)"],
        ["Ürün Adı", "Ürünün tam adı"],
        ["Kategori ID", "Kategorinin ID numarası (Kategoriler sayfasından bakabilirsiniz)"],
        ["Birim Tipi", "adet, kg, metre, litre vb."],
        ["Mevcut Stok", "Başlangıç stok miktarı (sayısal değer)"],
        ["Minimum Stok", "Kritik stok seviyesi (sayısal değer)"],
        ["Barkod", "Ürün barkodu (opsiyonel)"],
        ["Notlar", "Ek bilgiler (opsiyonel)"],
    ]

    for row_num, row_data in enumerate(info_text, 1):
        for col_num, value in enumerate(row_data, 1):
            cell = ws_info.cell(row=row_num, column=col_num, value=value)
            if row_num == 1:
                cell.font = Font(bold=True, size=14)
            elif ":" in str(value):
                cell.font = Font(bold=True)

    ws_info.column_dimensions['A'].width = 20
    ws_info.column_dimensions['B'].width = 60

    # BytesIO'ya kaydet
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return output


def parse_product_excel(file_stream):
    """
    Ürün Excel dosyasını parse et

    Returns:
        tuple: (success_list, error_list)
    """
    try:
        df = pd.read_excel(file_stream, sheet_name='Ürün Şablonu')

        # Boş satırları temizle
        df = df.dropna(how='all')

        # Örnek satırları atla
        df = df[~df['Ürün Kodu*'].astype(str).str.startswith('ORN-')]

        success_list = []
        error_list = []

        for index, row in df.iterrows():
            try:
                # Zorunlu alanları kontrol et
                if pd.isna(row['Ürün Kodu*']) or pd.isna(row['Ürün Adı*']) or pd.isna(row['Kategori ID*']):
                    error_list.append({
                        'row': index + 2,
                        'error': 'Zorunlu alanlar boş olamaz (Ürün Kodu, Ürün Adı, Kategori ID)'
                    })
                    continue

                product_data = {
                    'code': str(row['Ürün Kodu*']).strip(),
                    'name': str(row['Ürün Adı*']).strip(),
                    'category_id': int(row['Kategori ID*']),
                    'unit_type': str(row.get('Birim Tipi', 'adet')).strip() if not pd.isna(row.get('Birim Tipi')) else 'adet',
                    'current_stock': float(row.get('Mevcut Stok', 0)) if not pd.isna(row.get('Mevcut Stok')) else 0,
                    'minimum_stock': float(row.get('Minimum Stok', 0)) if not pd.isna(row.get('Minimum Stok')) else 0,
                    'barcode': str(row.get('Barkod', '')).strip() if not pd.isna(row.get('Barkod')) else None,
                    'notes': str(row.get('Notlar', '')).strip() if not pd.isna(row.get('Notlar')) else None,
                }

                success_list.append(product_data)

            except Exception as e:
                error_list.append({
                    'row': index + 2,
                    'error': f'Hata: {str(e)}'
                })

        return success_list, error_list

    except Exception as e:
        return [], [{'row': 0, 'error': f'Dosya okuma hatası: {str(e)}'}]


def export_products_to_excel(products):
    """
    Ürünleri Excel'e dışa aktar
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Ürünler"

    # Başlıklar
    headers = [
        'ID',
        'Ürün Kodu',
        'Ürün Adı',
        'Kategori',
        'Birim',
        'Mevcut Stok',
        'Minimum Stok',
        'Durum',
        'Barkod',
        'Notlar',
        'Oluşturulma Tarihi'
    ]

    # Başlık satırını yaz
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Veri satırlarını yaz
    for row_num, product in enumerate(products, 2):
        ws.cell(row=row_num, column=1, value=product.id)
        ws.cell(row=row_num, column=2, value=product.code)
        ws.cell(row=row_num, column=3, value=product.name)
        ws.cell(row=row_num, column=4, value=product.category.name if product.category else '')
        ws.cell(row=row_num, column=5, value=product.unit_type)
        ws.cell(row=row_num, column=6, value=product.current_stock)
        ws.cell(row=row_num, column=7, value=product.minimum_stock)

        # Stok durumu
        if product.current_stock <= 0:
            status = 'BOŞ'
            status_color = 'FF0000'
        elif product.minimum_stock > 0 and product.current_stock < product.minimum_stock:
            status = 'KRİTİK'
            status_color = 'FFA500'
        else:
            status = 'NORMAL'
            status_color = '00FF00'

        cell = ws.cell(row=row_num, column=8, value=status)
        cell.font = Font(bold=True, color=status_color)

        ws.cell(row=row_num, column=9, value=product.barcode or '')
        ws.cell(row=row_num, column=10, value=product.notes or '')
        ws.cell(row=row_num, column=11, value=product.created_at.strftime('%Y-%m-%d %H:%M') if product.created_at else '')

    # Kolon genişliklerini ayarla
    column_widths = [8, 15, 30, 20, 10, 12, 12, 10, 15, 30, 18]
    for col_num, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + col_num)].width = width

    # BytesIO'ya kaydet
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return output


def export_stock_movements_to_excel(movements):
    """
    Stok hareketlerini Excel'e dışa aktar
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Stok Hareketleri"

    # Başlıklar
    headers = [
        'ID',
        'Tarih',
        'Ürün Kodu',
        'Ürün Adı',
        'Kategori',
        'Hareket Tipi',
        'Miktar',
        'Birim',
        'Önceki Stok',
        'Yeni Stok',
        'Kullanıcı',
        'Açıklama'
    ]

    # Başlık satırını yaz
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="217346", end_color="217346", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Veri satırlarını yaz
    for row_num, movement in enumerate(movements, 2):
        ws.cell(row=row_num, column=1, value=movement.id)
        ws.cell(row=row_num, column=2, value=movement.date.strftime('%Y-%m-%d %H:%M'))
        ws.cell(row=row_num, column=3, value=movement.product.code if movement.product else '')
        ws.cell(row=row_num, column=4, value=movement.product.name if movement.product else '')
        ws.cell(row=row_num, column=5, value=movement.product.category.name if movement.product and movement.product.category else '')
        ws.cell(row=row_num, column=6, value=movement.movement_type)
        ws.cell(row=row_num, column=7, value=movement.quantity)
        ws.cell(row=row_num, column=8, value=movement.product.unit_type if movement.product else '')
        ws.cell(row=row_num, column=9, value=movement.previous_stock)
        ws.cell(row=row_num, column=10, value=movement.new_stock)
        ws.cell(row=row_num, column=11, value=movement.user.name if movement.user else '')
        ws.cell(row=row_num, column=12, value=movement.description or '')

    # Kolon genişliklerini ayarla
    column_widths = [8, 16, 15, 30, 20, 15, 10, 10, 12, 12, 15, 30]
    for col_num, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + col_num)].width = width

    # BytesIO'ya kaydet
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return output
