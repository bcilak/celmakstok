"""
ÇELMAK Stok Takip Sistemi
Ana uygulama başlatma dosyası
"""

from app import create_app, db
from app.models import User, Category

app = create_app()

def init_database():
    """Veritabanını başlat ve varsayılan verileri ekle"""
    with app.app_context():
        # Veritabanını oluştur
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

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        # Veritabanını başlat
        init_database()
    else:
        # Uygulamayı çalıştır
        print('''
╔═══════════════════════════════════════════════════════════╗
║          ÇELMAK STOK TAKİP SİSTEMİ                        ║
║          Maliyetsiz Stok ve Üretim Yönetimi               ║
╠═══════════════════════════════════════════════════════════╣
║  İlk kullanım için:  python run.py init                   ║
║  Sunucuyu başlat:    python run.py                        ║
║                                                           ║
║  Tarayıcıda: http://localhost:5000                        ║
║  Varsayılan giriş: admin / admin123                       ║
╚═══════════════════════════════════════════════════════════╝
        ''')
        
        # Veritabanı dosyası yoksa otomatik oluştur
        import os
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'celmak_stok.db')
        if not os.path.exists(db_path):
            print('Veritabanı bulunamadı, oluşturuluyor...')
            init_database()
        
        app.run(debug=True, host='0.0.0.0', port=5000)
