# Sunucuda Çalıştırılacak Komutlar

## ✅ Git Push Tamamlandı!

Yerel değişiklikler GitHub'a push edildi. Şimdi sunucudan çekip uygulamayı yeniden başlatın.

---

## 1️⃣ Sunucuya SSH ile Bağlanın

```bash
ssh kullanici@celmak.altikodtech.com.tr
# veya
ssh kullanici@152.53.241.81
```

---

## 2️⃣ Proje Dizinine Gidin

```bash
cd /home/kullanici/celmakstok
# veya projenizin bulunduğu dizin
```

---

## 3️⃣ Git Pull Yapın

```bash
# Mevcut değişiklikleri yedekleyin (eğer varsa)
git stash

# Son değişiklikleri çekin
git pull origin master

# Eğer stash yaptıysanız, geri yükleyin
git stash pop
```

**Beklenen Çıktı:**
```
From https://github.com/bcilak/celmakstok
 * branch            master     -> FETCH_HEAD
Updating 9bf140f..85ea962
Fast-forward
 API_DOCUMENTATION.md          | 580 +++++++++++++++++++++++
 API_OZET.md                   | 457 ++++++++++++++++++
 API_README.md                 | 273 +++++++++++
 BASLATMA_KILAVUZU.md          | 216 +++++++++
 CANLI_API_DEPLOYMENT.md       | 412 ++++++++++++++++
 SATIN_ALMA_API.md             | 429 ++++++++++++++++
 api_test.html                 | 285 +++++++++++
 app/routes/api.py             | 556 +++++++++++++++++++--
 app/routes/products.py        |  45 +-
 example_api_usage.py          | 325 +++++++++++++
 purchasing_app_example.py     | 234 +++++++++
 12 files changed, 4318 insertions(+), 34 deletions(-)
```

---

## 4️⃣ .env Dosyasını Güncelleyin

```bash
nano .env
# veya
vi .env
```

**Şu satırları kontrol edin/ekleyin:**

```env
# Base URL (ÖNEMLI!)
BASE_URL=https://celmak.altikodtech.com.tr

# API Güvenliği (Güçlü bir key oluşturun)
API_KEY=sk_live_celmak_2024_guclu_anahtar_12345
```

**Güçlü API Key oluşturmak için:**
```bash
python3 -c "import secrets; print('sk_live_' + secrets.token_urlsafe(32))"
```

Çıktıyı kopyalayıp `.env` dosyasına yapıştırın.

**Ctrl+O** (Kaydet) → **Enter** → **Ctrl+X** (Çık)

---

## 5️⃣ Python Bağımlılıklarını Kontrol Edin

```bash
# Virtual environment'ı aktifleştirin
source venv/bin/activate  # veya source .venv/bin/activate

# Gerekli paketler yüklü mü kontrol edin
pip list | grep -E "Flask|SQLAlchemy|psycopg"
```

**Eğer eksik paket varsa:**
```bash
pip install -r requirements.txt
```

---

## 6️⃣ Uygulamayı Yeniden Başlatın

### Yöntem 1: Systemd Service (Önerilen)

```bash
sudo systemctl restart celmak-stok
sudo systemctl status celmak-stok
```

**Başarılı çıktı:**
```
● celmak-stok.service - CELMAK Stok Takip Sistemi
   Active: active (running) since ...
```

### Yöntem 2: Gunicorn ile Manuel

```bash
# Mevcut gunicorn process'i öldür
pkill gunicorn

# Yeni gunicorn başlat
gunicorn --bind 0.0.0.0:5000 run:app --daemon --workers 4
```

### Yöntem 3: uWSGI ile

```bash
sudo systemctl restart uwsgi
sudo systemctl status uwsgi
```

### Yöntem 4: Nginx + Passenger

```bash
sudo systemctl restart nginx
# veya
passenger-config restart-app /home/kullanici/celmakstok
```

---

## 7️⃣ API'yi Test Edin

### Test 1: Health Check (Hızlı Test)

```bash
curl https://celmak.altikodtech.com.tr/api/v1/health
```

**Başarılı Çıktı:**
```json
{
  "status": "healthy",
  "version": "1.0",
  "service": "ÇELMAK Stok Takip API"
}
```

### Test 2: Kritik Stok API (Session Gerekli)

Tarayıcıda console açın (F12) ve çalıştırın:

```javascript
// Önce login olun: https://celmak.altikodtech.com.tr
// Sonra console'da:
fetch('/api/v1/purchasing/critical-stock')
  .then(r => r.json())
  .then(d => console.log(d));
```

### Test 3: Python ile Test

```bash
python3 << 'EOF'
import requests

session = requests.Session()
session.post('https://celmak.altikodtech.com.tr/auth/login',
    data={'username': 'admin', 'password': 'admin123'})

response = session.get('https://celmak.altikodtech.com.tr/api/v1/purchasing/critical-stock')
print(response.json())
EOF
```

---

## 8️⃣ Log Kontrolleri

### Uygulama Logları

```bash
# Systemd loglari
sudo journalctl -u celmak-stok -f

# veya
tail -f /var/log/celmak-stok/app.log
```

### Nginx Logları

```bash
sudo tail -f /var/log/nginx/celmak_access.log
sudo tail -f /var/log/nginx/celmak_error.log
```

### Hata Varsa

```bash
# Son 50 satır hatayı göster
sudo journalctl -u celmak-stok -n 50 --no-pager
```

---

## 9️⃣ Firewall/Port Kontrolleri (Gerekirse)

```bash
# Port 5000 açık mı?
sudo netstat -tuln | grep 5000

# veya
sudo ss -tuln | grep 5000
```

**Eğer port kapalıysa:**
```bash
sudo ufw allow 5000/tcp
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
```

---

## 🔟 Performans İyileştirmeleri (Opsiyonel)

### Gunicorn Workers Sayısını Artırın

```bash
# CPU çekirdeği sayısını öğrenin
nproc

# Genelde: workers = (CPU * 2) + 1
# Örnek: 4 core için = (4 * 2) + 1 = 9 workers
gunicorn --bind 0.0.0.0:5000 run:app --workers 9 --daemon
```

### Redis Cache Ekleyin (İleri Seviye)

```bash
sudo apt install redis-server
pip install flask-caching redis
```

---

## ✅ Başarı Kontrol Listesi

Tamamlandıkça işaretleyin:

- [ ] SSH ile sunucuya bağlandım
- [ ] `git pull origin master` ile güncellemeleri çektim
- [ ] `.env` dosyasında `BASE_URL` ve `API_KEY` güncelledim
- [ ] Uygulamayı restart ettim
- [ ] Health check başarılı: `curl https://celmak.altikodtech.com.tr/api/v1/health`
- [ ] Tarayıcıda login yaptım ve API test ettim
- [ ] Log dosyalarında hata yok
- [ ] Kritik stok API çalışıyor

---

## 🚨 Sorun Giderme

### Problem 1: "Module not found" Hatası

```bash
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart celmak-stok
```

### Problem 2: "Permission denied" Hatası

```bash
sudo chown -R kullanici:kullanici /home/kullanici/celmakstok
chmod 600 .env
sudo systemctl restart celmak-stok
```

### Problem 3: API 404 Döndürüyor

```bash
# Blueprint register edildi mi kontrol edin
grep "register_blueprint.*api" app/__init__.py

# Çıktı olmalı:
# app.register_blueprint(api.api_bp, url_prefix='/api')
```

### Problem 4: Database Bağlantı Hatası

```bash
# PostgreSQL çalışıyor mu?
sudo systemctl status postgresql

# Database erişimi test et
psql -U celmak_user -d celmak_stok -h localhost
```

---

## 📱 Satın Alma Uygulamasını Bağlayın

Artık harici satın alma uygulamanızdan şu endpoint'lere erişebilirsiniz:

```python
# config.py (Satın alma uygulamanızda)
CELMAK_API_URL = "https://celmak.altikodtech.com.tr/api"
CELMAK_USERNAME = "admin"
CELMAK_PASSWORD = "admin123"

# Kritik stokları çek
import requests

session = requests.Session()
session.post(f"{CELMAK_API_URL[:-4]}/auth/login",
    data={'username': CELMAK_USERNAME, 'password': CELMAK_PASSWORD})

response = session.get(f"{CELMAK_API_URL}/v1/purchasing/critical-stock")
critical_products = response.json()['data']

for product in critical_products:
    if product['urgency_level'] == 'critical':
        print(f"⚠️ ACİL: {product['name']} - Stok tükendi!")
```

---

## 🎉 Tamamlandı!

API'leriniz artık canlıda çalışıyor. Test etmek için:

**Tarayıcıda:** https://celmak.altikodtech.com.tr/api/v1/health

**Başarılı Yanıt:**
```json
{
  "status": "healthy",
  "version": "1.0",
  "service": "ÇELMAK Stok Takip API"
}
```

---

**Hazırlayan:** Claude
**Tarih:** 2026-01-12
**Proje:** ÇELMAK Stok Takip API - Sunucu Deployment
