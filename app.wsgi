#!/usr/bin/env python3
"""
ÇELMAK Stok Takip Sistemi - WSGI Giriş Noktası
Apache mod_wsgi için bu dosyayı kullanın.
"""

import sys
import os

# Proje dizinini Python path'e ekle
APP_DIR = '/home/altikodtech/domains/celmak.altikodtech.com.tr/public_html/celmakstok'
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# .env dosyasını yükle
from dotenv import load_dotenv
dotenv_path = os.path.join(APP_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Flask uygulamasını oluştur
from app import create_app
application = create_app()
