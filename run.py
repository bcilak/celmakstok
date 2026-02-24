
"""
ÇELMAK Stok Takip Sistemi
Ana uygulama başlatma dosyası
"""

# .env yüklemesi (her ortamda çalışsın diye)
import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

import sys
from app import create_app, db
from app.models import User, Category

app = create_app()

def init_database():
    """Veritabanını başlat ve varsayılan verileri ekle"""
    with app.app_context():
        # Veritabanı tablolarını oluştur
        db.create_all()

        # Varsayılan admin kullanıcısı
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                name='Sistem Yöneticisi',
                role='admin',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            print('✓ Admin kullanıcısı oluşturuldu (admin / admin123)')

        db.session.commit()
        print('\n✓ Veritabanı başarıyla başlatıldı!')

def wait_for_db():
    """Veritabanının hazır olmasını bekle (Docker için)"""
    import time
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        try:
            with app.app_context():
                # Basit bir sorgu ile veritabanı bağlantısını test et
                db.session.execute(db.text('SELECT 1'))
                print('✓ Veritabanı bağlantısı başarılı!')
                return True
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                print(f'Veritabanı bağlantısı bekleniyor... ({retry_count}/{max_retries})')
                time.sleep(2)
            else:
                print(f'❌ Veritabanı bağlantısı başarısız: {e}')
                return False

    return False

if __name__ == '__main__':
    # Ortam kontrolü
    is_docker = os.environ.get('DOCKER_CONTAINER', False)
    is_production = os.environ.get('FLASK_ENV', 'development') == 'production'

    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        # Veritabanını başlat
        if is_docker:
            wait_for_db()
        init_database()
    else:
        # Başlangıç bilgisi
        print('='*60)
        print('          ÇELMAK STOK TAKİP SİSTEMİ')
        print('          Maliyetsiz Stok ve Üretim Yönetimi')
        print('='*60)

        # Docker ortamında veritabanını bekle
        if is_docker:
            print('Docker container içinde çalışıyor...')
            if not wait_for_db():
                print('Veritabanı hazır değil, çıkılıyor...')
                sys.exit(1)

            # Veritabanını otomatik başlat
            try:
                init_database()
            except Exception as e:
                print(f'Veritabanı başlatma hatası: {e}')

        if not is_docker:
            print('  İlk kullanım için:  python run.py init')
            print('  Sunucuyu başlat:    python run.py')
            print()
            print('  Tarayıcıda: http://localhost:5000')
            print('  Varsayılan giriş: admin / admin123')

        print('='*60)
        print()

        # Uygulamayı çalıştır
        if is_production:
            # Production modda Gunicorn veya başka bir WSGI server kullanılmalı
            # Ancak basit deployment için Flask'ın kendi sunucusu da kullanılabilir
            print('UYARI: Production modda calisiyor. Gunicorn kullanmaniz onerilir.')
            app.run(host='0.0.0.0', port=5000, debug=False)
        else:
            # Development modu
            port = int(os.environ.get('PORT', 5000))
            app.run(host='0.0.0.0', port=port, debug=True)
