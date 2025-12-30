import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class Config:
    # Flask ayarları
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'celmak-stok-takip-2024-gizli-anahtar'

    # Veritabanı ayarları
    # PostgreSQL için DATABASE_URL kullan, yoksa SQLite'a geri dön
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///celmak_stok.db'

    # PostgreSQL için özel ayarlar
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20
    }

    # Uygulama ayarları
    APP_NAME = "ÇELMAK Stok Takip Sistemi"
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 25))
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

    # QR Kod ayarları
    QR_CODE_VERSION = 1
    QR_CODE_BOX_SIZE = 10
    QR_CODE_BORDER = 4

    # Debug mod (production'da False olmalı)
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

    # Session ayarları (HTTPS proxy için)
    SESSION_COOKIE_SECURE = False  # Apache zaten HTTPS yapıyor
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
