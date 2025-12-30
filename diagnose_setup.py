import time
import os
import sys

# Proje dizinini path'e ekle
sys.path.append(os.getcwd())

print("--- Celmak Stok Tanılama Aracı ---")

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[OK] .env dosyası yüklendi.")
except Exception as e:
    print(f"[!] .env yüklenirken hata: {e}")

try:
    from app import create_app, db
    from app.models import User
    from werkzeug.security import generate_password_hash, check_password_hash
    print("[OK] Flask ve Modeller yüklendi.")
except Exception as e:
    print(f"[X] Import hatası: {e}")
    sys.exit(1)

app = create_app()

def test_db():
    print("\n1. Veritabanı Bağlantı Testi...")
    start = time.time()
    try:
        with app.app_context():
            # Basit bir sorgu
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            print(f"[OK] Veritabanı bağlantısı başarılı. (Süre: {time.time() - start:.4f}s)")
            
            # Kullanıcı sorgusu testi
            print("2. Kullanıcı Sorgu Testi...")
            start = time.time()
            user = User.query.filter_by(username='admin').first()
            if user:
                print(f"[OK] 'admin' kullanıcısı bulundu. (Süre: {time.time() - start:.4f}s)")
            else:
                print(f"[!] 'admin' kullanıcısı bulunamadı! (Süre: {time.time() - start:.4f}s)")
    except Exception as e:
        print(f"[X] Veritabanı hatası: {e}")
        print(f"URL: {os.environ.get('DATABASE_URL')}")

def test_hashing():
    print("\n3. Şifre Hashing (CPU/Entropy) Testi...")
    password = "admin123"
    start = time.time()
    h = generate_password_hash(password)
    print(f"[OK] Hash oluşturuldu. (Süre: {time.time() - start:.4f}s)")
    
    start = time.time()
    check_password_hash(h, password)
    print(f"[OK] Hash doğrulandı. (Süre: {time.time() - start:.4f}s)")

if __name__ == "__main__":
    test_db()
    test_hashing()
    print("\n--- Tanılama Tamamlandı ---")
