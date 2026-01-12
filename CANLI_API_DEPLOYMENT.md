# Canlı Sunucuya API Deployment Kılavuzu

## Mevcut Durum
- **Canlı Domain:** https://celmak.altikodtech.com.tr
- **Sunucu:** Zaten çalışıyor
- **Hedef:** API endpoint'lerini canlıya eklemek

---

## Adım 1: Canlı Sunucuya Bağlanın

```bash
ssh kullanici@sunucu-ip
# veya Virtualmin panelden File Manager kullanın
```

---

## Adım 2: Dosyaları Yükleyin

Aşağıdaki dosyaları canlı sunucuya yüklemeniz gerekiyor:

### Güncellenmiş Dosyalar:
```
app/routes/api.py          # API endpoint'leri (12 yeni endpoint)
.env                       # BASE_URL güncellemesi
```

### Yeni Dosyalar (Opsiyonel - Dokümantasyon):
```
API_DOCUMENTATION.md
API_README.md
BASLATMA_KILAVUZU.md
SATIN_ALMA_API.md
API_OZET.md
example_api_usage.py       # Test için
purchasing_app_example.py  # Satın alma test için
api_test.html              # Görselleştirme
```

---

## Adım 3: .env Dosyasını Güncelleyin (Canlı Sunucuda)

`/home/kullanici/celmakstok/.env` dosyasını açın ve şunları kontrol edin:

```env
# Flask Configuration
SECRET_KEY=celmak-stok-takip-2024-gizli-anahtar-super-secret
FLASK_ENV=production
FLASK_APP=run.py

# Database Configuration
DATABASE_URL=postgresql+psycopg://celmak_user:CelmakStok2024!@localhost:5432/celmak_stok

# App Settings
ITEMS_PER_PAGE=25

# API Güvenliği
API_KEY=sk_live_celmak_2024_guclu_anahtar_buraya

# Base URL (ÖNEMLI!)
BASE_URL=https://celmak.altikodtech.com.tr
```

**ÖNEMLİ:** `API_KEY` değerini güçlü bir şifre ile değiştirin:
```bash
# Güçlü API key oluşturmak için:
openssl rand -hex 32
# veya
python3 -c "import secrets; print('sk_live_' + secrets.token_urlsafe(32))"
```

---

## Adım 4: Flask Uygulamasını Yeniden Başlatın

### Yöntem 1: Systemd ile (Önerilen)
```bash
sudo systemctl restart celmak-stok
sudo systemctl status celmak-stok
```

### Yöntem 2: Gunicorn/uWSGI Manuel Restart
```bash
# Gunicorn kullanıyorsanız:
pkill gunicorn
gunicorn --bind 0.0.0.0:5000 run:app --daemon

# uWSGI kullanıyorsanız:
sudo systemctl restart uwsgi
```

### Yöntem 3: Virtualmin Panel
1. Virtualmin → Services → Restart Web Server
2. Veya Python aplikasyon yöneticisinden restart

---

## Adım 5: API'yi Test Edin

### Test 1: Health Check (Authentication Gerektirmez)
```bash
curl https://celmak.altikodtech.com.tr/api/v1/health
```

**Beklenen Çıktı:**
```json
{
  "status": "healthy",
  "version": "1.0",
  "service": "ÇELMAK Stok Takip API"
}
```

### Test 2: Kritik Stok (Session Authentication Gerekir)
```bash
# Önce tarayıcıda login olun: https://celmak.altikodtech.com.tr
# Sonra tarayıcı console'da:
fetch('/api/v1/purchasing/critical-stock')
  .then(r => r.json())
  .then(d => console.log(d));
```

### Test 3: API Key ile Test (Python)
```python
import requests

API_KEY = "sk_live_celmak_2024_guclu_anahtar_buraya"
BASE_URL = "https://celmak.altikodtech.com.tr/api"

# Health check
response = requests.get(f"{BASE_URL}/v1/health")
print(response.json())

# Session oluştur
session = requests.Session()
login_data = {'username': 'admin', 'password': 'admin123'}
session.post("https://celmak.altikodtech.com.tr/auth/login", data=login_data)

# Kritik stok çek
response = session.get(f"{BASE_URL}/v1/purchasing/critical-stock")
print(response.json())
```

---

## Adım 6: Güvenlik Kontrolleri

### 1. HTTPS Kontrolü
```bash
curl -I https://celmak.altikodtech.com.tr
# Response'da "HTTP/2 200" veya "HTTPS" görmelisiniz
```

### 2. API Key Güvenliği
- `.env` dosyasının izinleri: `chmod 600 .env`
- API_KEY'i asla Git'e commit etmeyin
- Her harici uygulama için farklı API key kullanın (gelecekte)

### 3. CORS Ayarları (Gerekirse)
Eğer farklı domain'den API erişimi gerekiyorsa:

```python
# app/__init__.py içine ekleyin:
from flask_cors import CORS

# Sadece belirli origin'lere izin ver
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://satin-alma-uygulamasi.com"],
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type", "X-API-Key"]
    }
})
```

---

## Adım 7: Satın Alma Uygulamasını Entegre Edin

Satın alma uygulamanızda şu ayarları yapın:

```python
# config.py (Satın Alma Uygulamanızda)
CELMAK_API_URL = "https://celmak.altikodtech.com.tr/api"
CELMAK_USERNAME = "admin"  # veya satın alma kullanıcısı
CELMAK_PASSWORD = "güvenli_şifre"

# Kullanım
import requests

session = requests.Session()

# Login
login_response = session.post(
    "https://celmak.altikodtech.com.tr/auth/login",
    data={'username': CELMAK_USERNAME, 'password': CELMAK_PASSWORD}
)

# Kritik stok al
critical_stock = session.get(f"{CELMAK_API_URL}/v1/purchasing/critical-stock")
data = critical_stock.json()

for product in data['data']:
    if product['urgency_level'] == 'critical':
        print(f"⚠️ ACİL: {product['name']} - Stok: {product['current_stock']}")
```

---

## Adım 8: Otomatik Bildirim Kurulumu (Opsiyonel)

### Cron Job ile Günlük Kontrol
```bash
# Crontab düzenle
crontab -e

# Her gün sabah 9'da kritik stok kontrolü
0 9 * * * cd /home/kullanici/celmakstok && /usr/bin/python3 purchasing_app_example.py >> /var/log/celmak-critical-stock.log 2>&1
```

### Slack Webhook Entegrasyonu
```python
# critical_stock_notifier.py
import requests
import os

SLACK_WEBHOOK = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
API_URL = "https://celmak.altikodtech.com.tr/api"

# Login
session = requests.Session()
session.post("https://celmak.altikodtech.com.tr/auth/login",
    data={'username': os.getenv('CELMAK_USER'), 'password': os.getenv('CELMAK_PASS')})

# Kritik stok al
response = session.get(f"{API_URL}/v1/purchasing/critical-stock")
data = response.json()

critical = [p for p in data['data'] if p['urgency_level'] == 'critical']

if critical:
    message = {
        "text": f"⚠️ ÇELMAK Kritik Stok Uyarısı: {len(critical)} ürün stokta yok!",
        "attachments": [
            {
                "color": "danger",
                "fields": [
                    {"title": p['name'], "value": f"Stok: {p['current_stock']}", "short": True}
                    for p in critical[:5]
                ]
            }
        ]
    }
    requests.post(SLACK_WEBHOOK, json=message)
```

---

## Sorun Giderme

### Problem 1: 404 Not Found
**Sorun:** `/api/v1/health` endpoint'i bulunamıyor

**Çözüm:**
```bash
# Blueprint'in register edildiğinden emin olun
# app/__init__.py kontrol edin:
from app.routes import api
app.register_blueprint(api.api_bp, url_prefix='/api')
```

### Problem 2: 500 Internal Server Error
**Sorun:** API çağrıları 500 hatası veriyor

**Çözüm:**
```bash
# Log dosyalarını kontrol edin
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/uwsgi/celmak-stok.log

# Veya Flask logları:
sudo journalctl -u celmak-stok -f
```

### Problem 3: CORS Hatası
**Sorun:** "Access-Control-Allow-Origin" hatası

**Çözüm:**
```bash
pip install flask-cors
# Sonra app/__init__.py'ye CORS ekleyin (yukarıda belirtildiği gibi)
```

### Problem 4: Session/Cookie Çalışmıyor
**Sorun:** Login yapılıyor ama API endpoint'leri 401 dönüyor

**Çözüm:**
```python
# Session cookie ayarlarını kontrol edin
# app/__init__.py veya config.py
app.config['SESSION_COOKIE_DOMAIN'] = '.altikodtech.com.tr'
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS için
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

---

## Checklist

Deployment öncesi kontrol listesi:

- [ ] `app/routes/api.py` dosyası canlı sunucuya yüklendi
- [ ] `.env` dosyasında `BASE_URL=https://celmak.altikodtech.com.tr` olarak ayarlandı
- [ ] `.env` dosyasında güçlü `API_KEY` tanımlandı
- [ ] Flask uygulaması restart edildi
- [ ] Health check başarılı: `curl https://celmak.altikodtech.com.tr/api/v1/health`
- [ ] Tarayıcıda login yapıldı ve API test edildi
- [ ] Satın alma uygulaması config dosyası güncellendi
- [ ] HTTPS çalışıyor (SSL sertifikası geçerli)
- [ ] Log dosyaları kontrol edildi, hata yok

---

## Özet

Artık canlı sisteminizdeki API'ler şu adresten erişilebilir:

```
Base URL: https://celmak.altikodtech.com.tr/api

Endpoints:
✅ GET  /v1/health
✅ GET  /v1/products/full
✅ GET  /v1/recipes
✅ GET  /v1/recipes/{id}
✅ GET  /v1/product-tree
✅ GET  /v1/product-tree/flat
✅ GET  /v1/recipe/{id}/can-produce
✅ GET  /v1/recipe/{id}/missing-materials
✅ GET  /v1/purchasing/critical-stock
✅ GET  /v1/purchasing/reorder-suggestions
✅ GET  /v1/purchasing/product/{id}/details
✅ POST /v1/purchasing/notify
```

Satın alma uygulamanız artık bu API'leri kullanarak otomatik stok kontrolü yapabilir!

---

**Hazırlayan:** Claude
**Tarih:** 2026-01-12
**Proje:** ÇELMAK Stok Takip API - Canlı Deployment
