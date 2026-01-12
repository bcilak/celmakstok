import qrcode
import io
import os
from PIL import Image, ImageDraw, ImageFont

def generate_qr_code(data, size=10, border=4):
    """QR kod oluşturur ve BytesIO olarak döndürür"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return img_io

def generate_qr_with_label(data, label, size=10):
    """Etiketli QR kod oluşturur"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=size,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Etiket için alan ekle
    qr_width, qr_height = qr_img.size
    total_height = qr_height + 40

    final_img = Image.new('RGB', (qr_width, total_height), 'white')
    final_img.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(final_img)

    # Basit font kullan
    try:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()

    # Etiketi ortala
    text_bbox = draw.textbbox((0, 0), label, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (qr_width - text_width) // 2

    draw.text((text_x, qr_height + 10), label, fill='black', font=font)

    img_io = io.BytesIO()
    final_img.save(img_io, 'PNG')
    img_io.seek(0)

    return img_io

def generate_celmak_label(qr_data, part_no, part_name):
    """ÇELMAK etiket formatında QR kod oluşturur

    Args:
        qr_data: QR kod için veri
        part_no: Parça numarası
        part_name: Parça adı

    Returns:
        BytesIO: PNG formatında etiket
    """
    # Etiket boyutları (kare format, yüksek çözünürlük)
    label_width = 1000
    label_height = 1000

    # Kırmızı renk (ÇELMAK kırmızısı - referans etiketinden)
    celmak_red = (226, 35, 26)

    # Arka plan oluştur (beyaz + kırmızı şerit)
    label = Image.new('RGB', (label_width, label_height), 'white')
    draw = ImageDraw.Draw(label)

    # Sol tarafta kırmızı şerit (genişlik: ~16% - referans etikete göre)
    red_strip_width = 160
    draw.rectangle([0, 0, red_strip_width, label_height], fill=celmak_red)

    # Fontları yükle
    try:
        # Label fontları (bold) - Sistem fontları dene
        try:
            font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        except:
            font_label = ImageFont.truetype("arialbd.ttf", 32)

        # Value fontları (normal)
        try:
            font_value = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        except:
            font_value = ImageFont.truetype("arial.ttf", 36)
    except:
        font_label = ImageFont.load_default()
        font_value = ImageFont.load_default()

    # Logo dosyalarının yolu
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_logo_path = os.path.join(current_dir, 'static', 'images', 'celmak_logo.png')
    white_logo_path = os.path.join(current_dir, 'static', 'images', 'celmak_logo_white.png')

    # ÜST BÖLÜM: Ana ÇELMAK Logosu (renkli)
    try:
        if os.path.exists(main_logo_path):
            main_logo = Image.open(main_logo_path)

            # Logo boyutunu ayarla - referans etikete göre
            # Yükseklik: ~90px, orijinal oran korunarak
            logo_target_height = 90
            aspect_ratio = main_logo.width / main_logo.height
            logo_target_width = int(logo_target_height * aspect_ratio)

            main_logo = main_logo.resize((logo_target_width, logo_target_height), Image.Resampling.LANCZOS)

            # Logo pozisyonu - referans etikete göre ortalanmış
            # Sağ bölümün ortasına yerleştir
            content_area_width = label_width - red_strip_width
            logo_x = red_strip_width + (content_area_width - logo_target_width) // 2
            logo_y = 55  # Üstten mesafe

            # Logo yapıştır (transparency desteği)
            if main_logo.mode == 'RGBA':
                label.paste(main_logo, (logo_x, logo_y), main_logo)
            else:
                label.paste(main_logo, (logo_x, logo_y))
        else:
            # Fallback: Text olarak ÇELMAK
            try:
                try:
                    font_fallback = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                except:
                    font_fallback = ImageFont.truetype("arial.ttf", 48)
            except:
                font_fallback = ImageFont.load_default()
            draw.text((red_strip_width + 100, 60), "ÇELMAK", fill='black', font=font_fallback)
    except Exception as e:
        print(f"Ana logo yükleme hatası: {e}")

    # SOL ŞERİT: Beyaz ÇELMAK Logosu
    try:
        if os.path.exists(white_logo_path):
            white_logo = Image.open(white_logo_path)

            # Beyaz logo boyutu - kırmızı şeritin genişliğine göre
            # Şeritin %75'i kadar genişlik
            side_logo_width = int(red_strip_width * 0.70)
            aspect_ratio = white_logo.width / white_logo.height
            side_logo_height = int(side_logo_width / aspect_ratio)

            white_logo = white_logo.resize((side_logo_width, side_logo_height), Image.Resampling.LANCZOS)

            # Logo pozisyonu - alttan ~60px yukarıda, ortada
            side_logo_x = (red_strip_width - side_logo_width) // 2
            side_logo_y = label_height - side_logo_height - 60

            # Logo yapıştır
            if white_logo.mode == 'RGBA':
                label.paste(white_logo, (side_logo_x, side_logo_y), white_logo)
            else:
                label.paste(white_logo, (side_logo_x, side_logo_y))
    except Exception as e:
        print(f"Beyaz logo yükleme hatası: {e}")

    # İÇERİK ALANI
    content_x = red_strip_width + 50  # Sol şeritten boşluk
    content_width = label_width - red_strip_width - 100  # Sağ taraftan da boşluk

    # PARÇA NUM / PART NO
    part_no_y = 200
    draw.text((content_x, part_no_y), "PARÇA NUM / PART NO:", fill='black', font=font_label)

    # Alt çizgi
    line_y = part_no_y + 50
    draw.line([(content_x, line_y), (content_x + content_width, line_y)], fill='#CCCCCC', width=2)

    # Parça numarası değeri
    draw.text((content_x, line_y + 15), str(part_no), fill='black', font=font_value)

    # PARÇA ADI / PART NAME
    part_name_y = line_y + 90
    draw.text((content_x, part_name_y), "PARÇA ADI / PART NAME:", fill='black', font=font_label)

    # Alt çizgi
    line2_y = part_name_y + 50
    draw.line([(content_x, line2_y), (content_x + content_width, line2_y)], fill='#CCCCCC', width=2)

    # Parça adı değeri (uzunsa kısalt)
    part_name_display = str(part_name)
    if len(part_name_display) > 28:
        part_name_display = part_name_display[:25] + "..."
    draw.text((content_x, line2_y + 15), part_name_display, fill='black', font=font_value)

    # QR KOD
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")

    # QR kodu boyutlandır ve ortala
    qr_size = 400  # Referans etikete göre büyük QR kod
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

    # QR pozisyonu - içerik alanının ortasında, altta
    qr_x = red_strip_width + (label_width - red_strip_width - qr_size) // 2
    qr_y = line2_y + 120

    label.paste(qr_img, (qr_x, qr_y))

    # Etiketi BytesIO'ya kaydet - yüksek kalite
    img_io = io.BytesIO()
    label.save(img_io, 'PNG', dpi=(300, 300), optimize=False)
    img_io.seek(0)

    return img_io


def generate_celmak_label_with_size(qr_data, part_no, part_name, size='medium'):
    """ÇELMAK etiket formatında QR kod oluşturur - Boyut seçenekleriyle

    Args:
        qr_data: QR kod için veri
        part_no: Parça numarası
        part_name: Parça adı
        size: Etiket boyutu ('small', 'medium', 'large')

    Returns:
        BytesIO: PNG formatında etiket
    """
    # Boyut tanımları (piksel)
    size_configs = {
        'small': {
            'width': 600,
            'height': 600,
            'red_strip': 96,
            'logo_height': 54,
            'font_label_size': 19,
            'font_value_size': 22,
            'qr_size': 240,
            'padding': 30
        },
        'medium': {
            'width': 1000,
            'height': 1000,
            'red_strip': 160,
            'logo_height': 90,
            'font_label_size': 32,
            'font_value_size': 36,
            'qr_size': 400,
            'padding': 50
        },
        'large': {
            'width': 1500,
            'height': 1500,
            'red_strip': 240,
            'logo_height': 135,
            'font_label_size': 48,
            'font_value_size': 54,
            'qr_size': 600,
            'padding': 75
        }
    }

    # Boyut konfigürasyonunu al
    config = size_configs.get(size, size_configs['medium'])

    label_width = config['width']
    label_height = config['height']
    red_strip_width = config['red_strip']

    # Kırmızı renk
    celmak_red = (226, 35, 26)

    # Arka plan oluştur
    label = Image.new('RGB', (label_width, label_height), 'white')
    draw = ImageDraw.Draw(label)

    # Sol tarafta kırmızı şerit
    draw.rectangle([0, 0, red_strip_width, label_height], fill=celmak_red)

    # Fontları yükle
    try:
        try:
            font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", config['font_label_size'])
        except:
            font_label = ImageFont.truetype("arialbd.ttf", config['font_label_size'])

        try:
            font_value = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config['font_value_size'])
        except:
            font_value = ImageFont.truetype("arial.ttf", config['font_value_size'])
    except:
        font_label = ImageFont.load_default()
        font_value = ImageFont.load_default()

    # Logo dosyalarının yolu
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_logo_path = os.path.join(current_dir, 'static', 'images', 'celmak_logo.png')
    white_logo_path = os.path.join(current_dir, 'static', 'images', 'celmak_logo_white.png')

    # Ana logo
    try:
        if os.path.exists(main_logo_path):
            main_logo = Image.open(main_logo_path)
            logo_target_height = config['logo_height']
            aspect_ratio = main_logo.width / main_logo.height
            logo_target_width = int(logo_target_height * aspect_ratio)
            main_logo = main_logo.resize((logo_target_width, logo_target_height), Image.Resampling.LANCZOS)

            content_area_width = label_width - red_strip_width
            logo_x = red_strip_width + (content_area_width - logo_target_width) // 2
            logo_y = int(55 * (label_height / 1000))

            if main_logo.mode == 'RGBA':
                label.paste(main_logo, (logo_x, logo_y), main_logo)
            else:
                label.paste(main_logo, (logo_x, logo_y))
    except Exception as e:
        print(f"Ana logo yükleme hatası: {e}")

    # Beyaz logo (sol şeritte)
    try:
        if os.path.exists(white_logo_path):
            white_logo = Image.open(white_logo_path)
            side_logo_width = int(red_strip_width * 0.70)
            aspect_ratio = white_logo.width / white_logo.height
            side_logo_height = int(side_logo_width / aspect_ratio)
            white_logo = white_logo.resize((side_logo_width, side_logo_height), Image.Resampling.LANCZOS)

            side_logo_x = (red_strip_width - side_logo_width) // 2
            side_logo_y = label_height - side_logo_height - int(60 * (label_height / 1000))

            if white_logo.mode == 'RGBA':
                label.paste(white_logo, (side_logo_x, side_logo_y), white_logo)
            else:
                label.paste(white_logo, (side_logo_x, side_logo_y))
    except Exception as e:
        print(f"Beyaz logo yükleme hatası: {e}")

    # İçerik alanı
    content_x = red_strip_width + config['padding']
    content_width = label_width - red_strip_width - (config['padding'] * 2)

    # PARÇA NUM
    part_no_y = int(200 * (label_height / 1000))
    draw.text((content_x, part_no_y), "PARÇA NUM / PART NO:", fill='black', font=font_label)

    line_y = part_no_y + int(50 * (label_height / 1000))
    draw.line([(content_x, line_y), (content_x + content_width, line_y)], fill='#CCCCCC', width=2)

    draw.text((content_x, line_y + int(15 * (label_height / 1000))), str(part_no), fill='black', font=font_value)

    # PARÇA ADI
    part_name_y = line_y + int(90 * (label_height / 1000))
    draw.text((content_x, part_name_y), "PARÇA ADI / PART NAME:", fill='black', font=font_label)

    line2_y = part_name_y + int(50 * (label_height / 1000))
    draw.line([(content_x, line2_y), (content_x + content_width, line2_y)], fill='#CCCCCC', width=2)

    # Parça adı (uzunsa kısalt)
    part_name_display = str(part_name)
    max_chars = 28 if size == 'medium' else (18 if size == 'small' else 40)
    if len(part_name_display) > max_chars:
        part_name_display = part_name_display[:max_chars-3] + "..."
    draw.text((content_x, line2_y + int(15 * (label_height / 1000))), part_name_display, fill='black', font=font_value)

    # QR KOD
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img = qr_img.resize((config['qr_size'], config['qr_size']), Image.Resampling.LANCZOS)

    qr_x = red_strip_width + (label_width - red_strip_width - config['qr_size']) // 2
    qr_y = line2_y + int(120 * (label_height / 1000))

    label.paste(qr_img, (qr_x, qr_y))

    # Etiketi BytesIO'ya kaydet
    img_io = io.BytesIO()
    label.save(img_io, 'PNG', dpi=(300, 300), optimize=False)
    img_io.seek(0)

    return img_io
