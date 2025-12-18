import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'celmak-stok-takip-2024-gizli-anahtar'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///celmak_stok.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uygulama ayarları
    APP_NAME = "ÇELMAK Stok Takip Sistemi"
    ITEMS_PER_PAGE = 25
    
    # QR Kod ayarları
    QR_CODE_VERSION = 1
    QR_CODE_BOX_SIZE = 10
    QR_CODE_BORDER = 4
