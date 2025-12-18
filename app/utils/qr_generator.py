import qrcode
import io
from PIL import Image

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
    from PIL import ImageDraw, ImageFont
    
    qr_width, qr_height = qr_img.size
    total_height = qr_height + 40
    
    final_img = Image.new('RGB', (qr_width, total_height), 'white')
    final_img.paste(qr_img, (0, 0))
    
    draw = ImageDraw.Draw(final_img)
    
    # Basit font kullan
    try:
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
