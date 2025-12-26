# ⚡ HIZLI KURULUM KILAVUZU - Virtualmin

## 🚀 5 Dakikada Kurulum (TL;DR)

### 1. PostgreSQL Hazırlığı
```bash
sudo -u postgres psql
CREATE DATABASE celmak_stok;
CREATE USER celmak_user WITH PASSWORD 'GucluSifre123!';
GRANT ALL PRIVILEGES ON DATABASE celmak_stok TO celmak_user;
\q
```

### 2. Dosyaları Yükle
```bash
sudo mkdir -p /opt/celmakstok
cd /opt/celmakstok
# Dosyalarınızı buraya yükleyin (FTP/Git)
```

### 3. Python Kurulum
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Environment Ayarla
```bash
cp .env.example .env
nano .env
# DATABASE_URL ve SECRET_KEY ayarla
```

### 5. Veritabanı Başlat
```bash
python run.py init
```

### 6. Systemd Servis
```bash
sudo nano /etc/systemd/system/celmakstok.service
# (VIRTUALMIN_DEPLOYMENT.md'deki içeriği kopyala)

sudo systemctl daemon-reload
sudo systemctl enable celmakstok
sudo systemctl start celmakstok
```

### 7. Nginx Yapılandır
```bash
sudo nano /etc/nginx/sites-available/celmakstok
# (VIRTUALMIN_DEPLOYMENT.md'deki içeriği kopyala)

sudo ln -s /etc/nginx/sites-available/celmakstok /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 8. SSL Kurulum
```bash
sudo certbot --nginx -d stok.yourcompany.com
```

## ✅ TAMAM!
**Tarayıcıdan:** https://stok.yourcompany.com
**Giriş:** admin / admin123

---

## 🔧 Sık Kullanılan Komutlar

### Servis Yönetimi
```bash
# Başlat
sudo systemctl start celmakstok

# Durdur
sudo systemctl stop celmakstok

# Yeniden başlat
sudo systemctl restart celmakstok

# Durum
sudo systemctl status celmakstok

# Loglar
sudo journalctl -u celmakstok -f
```

### Yedekleme
```bash
# Manuel yedek
pg_dump -U celmak_user celmak_stok > backup.sql

# Geri yükle
psql -U celmak_user celmak_stok < backup.sql
```

### Güncelleme
```bash
cd /opt/celmakstok
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart celmakstok
```

---

## 📞 Sorun mu var?

1. **502 Error:** `sudo systemctl status celmakstok`
2. **DB Error:** `psql -U celmak_user -d celmak_stok -h localhost`
3. **Logs:** `tail -f /var/log/celmakstok/error.log`

**Detaylı bilgi:** VIRTUALMIN_DEPLOYMENT.md
