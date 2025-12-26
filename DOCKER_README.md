# 🐳 ÇELMAK Stok Takip Sistemi - Docker Deployment

## 📋 İçindekiler
- [Gereksinimler](#gereksinimler)
- [Hızlı Başlangıç](#hızlı-başlangıç)
- [Docker Compose Kullanımı](#docker-compose-kullanımı)
- [Production Deployment](#production-deployment)
- [Yedekleme ve Geri Yükleme](#yedekleme-ve-geri-yükleme)

---

## 🔧 Gereksinimler

- Docker (v20.10+)
- Docker Compose (v2.0+)
- En az 2GB RAM
- En az 5GB disk alanı

---

## ⚡ Hızlı Başlangıç

### 1. `.env` Dosyasını Oluşturun

``bash
cp .env.example .env
```

`.env` dosyasını düzenleyin ve güvenli şifreler ayarlayın:

```env
DB_PASSWORD=super-guvenli-sifre-buraya
SECRET_KEY=flask-icin-rastgele-secret-key
```

### 2. Docker Compose ile Başlatın

```bash
# Tüm servisleri başlat (db, web, nginx)
docker-compose up -d

# Logları izle
docker-compose logs -f

# Sadece web ve db başlat (nginx olmadan)
docker-compose up -d db web
```

### 3. Tarayıcıda Açın

- **Nginx ile:** http://localhost
- **Doğrudan Flask:** http://localhost:5000

**Varsayılan Giriş:**
- Kullanıcı: `admin`
- Şifre: `admin123`

---

## 🐳 Docker Compose Kullanımı

### Servisler

| Servis | Port | Açıklama |
|--------|------|----------|
| `db` | 5432 | PostgreSQL veritabanı |
| `web` | 5000 | Flask uygulaması |
| `nginx` | 80, 443 | Reverse proxy (opsiyonel) |

### Temel Komutlar

```bash
# Servisleri başlat
docker-compose up -d

# Servisleri durdur
docker-compose stop

# Servisleri durdur ve sil
docker-compose down

# Servisleri ve volumeleri sil (DİKKAT: Veri kaybı!)
docker-compose down -v

# Logları görüntüle
docker-compose logs -f web

# Sadece veritabanı logları
docker-compose logs -f db

# Container içine gir
docker-compose exec web bash
docker-compose exec db psql -U celmak_user -d celmak_stok

# Servisleri yeniden başlat
docker-compose restart web

# Image'ları yeniden build et
docker-compose build --no-cache
docker-compose up -d --build
```

---

## 🚀 Production Deployment

### 1. Environment Değişkenlerini Ayarlayın

```env
FLASK_ENV=production
SECRET_KEY=uzun-ve-rastgele-bir-secret-key-uret
DB_PASSWORD=cok-guclu-bir-veritabani-sifresi
```

### 2. Nginx ile SSL/TLS Ekleyin

`nginx.conf` dosyasına SSL sertifikası ekleyin:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # ... diğer ayarlar
}
```

### 3. Production için Öneriler

✅ **Güvenlik:**
- Güçlü şifreler kullanın
- `SECRET_KEY` değerini değiştirin
- Firewall kuralları ekleyin
- SSL/TLS sertifikası kullanın

✅ **Performans:**
- Gunicorn veya uWSGI kullanın (Flask production server yerine)
- Redis cache ekleyin
- Database connection pooling yapılandırın

✅ **Monitoring:**
- Log toplama (ELK Stack, Graylog)
- Metrik izleme (Prometheus, Grafana)
- Uptime monitoring

### 4. Gunicorn ile Çalıştırma

`requirements.txt` dosyasına ekleyin:
```
gunicorn==21.2.0
```

`Dockerfile` içinde CMD satırını değiştirin:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "run:app"]
```

---

## 💾 Yedekleme ve Geri Yükleme

### Veritabanı Yedeği Alma

```bash
# Backup oluştur
docker-compose exec db pg_dump -U celmak_user celmak_stok > backup_$(date +%Y%m%d).sql

# Sıkıştırılmış backup
docker-compose exec db pg_dump -U celmak_user celmak_stok | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Veritabanını Geri Yükleme

```bash
# SQL dosyasından geri yükle
cat backup_20231226.sql | docker-compose exec -T db psql -U celmak_user celmak_stok

# Sıkıştırılmış dosyadan
gunzip < backup_20231226.sql.gz | docker-compose exec -T db psql -U celmak_user celmak_stok
```

### Otomatik Yedekleme (Cron)

```bash
# crontab -e
# Her gün saat 02:00'de yedek al
0 2 * * * cd /path/to/celmakstok && docker-compose exec -T db pg_dump -U celmak_user celmak_stok | gzip > /backups/celmak_$(date +\%Y\%m\%d).sql.gz
```

---

## 🔍 Sorun Giderme

### Container Loglarını Kontrol Edin

```bash
# Web container logları
docker-compose logs --tail=100 -f web

# Veritabanı logları
docker-compose logs --tail=100 -f db
```

### Veritabanı Bağlantı Sorunu

```bash
# Veritabanının hazır olup olmadığını kontrol edin
docker-compose exec db pg_isready -U celmak_user

# Veritabanına bağlanın
docker-compose exec db psql -U celmak_user -d celmak_stok
```

### Container İçinde Komut Çalıştırma

```bash
# Python shell
docker-compose exec web python

# Flask shell
docker-compose exec web flask shell

# Veritabanını sıfırla (DİKKAT!)
docker-compose exec web python run.py init
```

### Tüm Sistemi Sıfırlama

```bash
# DİKKAT: Tüm veriler silinir!
docker-compose down -v
docker-compose up -d
```

---

## 📊 Monitoring

### Container Durumunu İzleme

```bash
# Container durumları
docker-compose ps

# Kaynak kullanımı
docker stats

# Sağlık durumu
docker-compose exec web curl http://localhost:5000/health
```

---

## 🔐 Güvenlik İpuçları

1. **Şifreleri Değiştirin:** Varsayılan `admin/admin123` şifresini ilk girişte değiştirin
2. **Environment Variables:** `.env` dosyasını git'e eklemeyin
3. **SSL/TLS:** Production'da mutlaka HTTPS kullanın
4. **Firewall:** Sadece gerekli portları açık tutun
5. **Updates:** Docker image'larını düzenli güncelleyin
6. **Backups:** Otomatik yedekleme sistemi kurun

---

## 📝 Notlar

- İlk çalıştırmada veritabanı otomatik olarak oluşturulur
- Admin kullanıcısı otomatik olarak oluşturulur
- Statik dosyalar `/app/static/uploads` dizininde saklanır
- PostgreSQL verileri `postgres_data` volume'unda kalıcıdır

---

## 🆘 Destek

Sorun yaşarsanız:
1. Container loglarını kontrol edin
2. Veritabanı bağlantısını test edin
3. Docker ve Docker Compose sürümlerini kontrol edin

---

**Hazırlayan:** ÇELMAK Geliştirme Ekibi
**Tarih:** Aralık 2025
**Versiyon:** 1.0
