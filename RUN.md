# ÇELMAK Stok Takip - Çalıştırma ve Yayına Alma Rehberi

Bu dosya, projenin yerel ve sunucu ortamlarında sorunsuz bir şekilde kurulması, çalıştırılması ve yönetilmesi için gerekli olan tüm adımları içermektedir.

## 1. Yerel Kurulum (Local Setup)

### Gereksinimler
- Python 3.13+
- Sanal Ortam (venv)

### Adımlar
1. **Dosyaları Hazırlayın:**
   ```bash
   git clone https://github.com/bcilak/celmakstok.git
   cd celmakstok
   ```

2. **Bağımlılıkları Yükleyin:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   *Not: Python 3.13 uyumluluğu için pandas ve diğer paketlerin versiyon kısıtlamaları esnetilmiştir.*

3. **Çevre Değişkenlerini Ayarlayın:**
   `.env.example` dosyasını `.env` olarak kopyalayın ve düzenleyin.
   ```bash
   cp .env.example .env
   ```
   *Yerel test için `DATABASE_URL`'i yorum satırı yaparsanız uygulama otomatik olarak SQLite kullanacaktır.*

4. **Veritabanını Başlatın:**
   ```bash
   python run.py init
   # Varsayılan Admin: admin / admin123
   ```

5. **Uygulamayı Çalıştırın:**
   ```bash
   python run.py
   # Farklı port kullanmak isterseniz: PORT=5001 python run.py
   ```

---

## 2. Sunucu Kurulumu (Gunicorn Deployment)

Sunucuda uygulamanın sürekli çalışması için **Gunicorn** ve **Systemd** kullanılmalıdır.

### Gunicorn Servis Konfigürasyonu
Servis dosyası: `/etc/systemd/system/celmakstok.service`

```ini
[Unit]
Description=Celmak Stok Gunicorn Servisi
After=network.target

[Service]
User=altikodtech
Group=altikodtech
WorkingDirectory=/home/altikodtech/domains/celmak.altikodtech.com.tr/public_html/celmakstok
Environment="PATH=/home/altikodtech/domains/celmak.altikodtech.com.tr/public_html/celmakstok/venv/bin"
EnvironmentFile=/home/altikodtech/domains/celmak.altikodtech.com.tr/public_html/celmakstok/.env

ExecStart=/home/altikodtech/domains/celmak.altikodtech.com.tr/public_html/celmakstok/venv/bin/gunicorn \
    --workers 3 \
    --timeout 90 \
    --bind 127.0.0.1:5000 \
    --access-logfile /home/altikodtech/domains/celmak.altikodtech.com.tr/public_html/celmakstok/gunicorn_access.log \
    --error-logfile /home/altikodtech/domains/celmak.altikodtech.com.tr/public_html/celmakstok/gunicorn_error.log \
    run:app

Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 3. Apache (Reverse Proxy) Yapılandırması

Uygulamanın dış dünyaya açılması ve SSL desteği için Apache ayarları aşağıdaki gibi olmalıdır:

- **DocumentRoot:** `/home/altikodtech/domains/celmak.altikodtech.com.tr/public_html` (SSL sertifikası yenileme sorunu yaşamamak için).
- **Statik Dosyalar:** Apache üzerinden servis edilmelidir (`Alias /static ...`).
- **Proxy:** Geri kalan tüm istekler `127.0.0.1:5000`'e yönlendirilmelidir.
- **PHP Devre Dışı:** `FilesMatch \.php` için `SetHandler None` yapılarak bot taramalarından kaynaklanan hatalar engellenmelidir.

---

## 4. Kritik Sorun Giderme (Troubleshooting)

### Port Çakışması (Address already in use)
Port 5000 başka bir süreç tarafından işgal ediliyorsa:
```bash
sudo fuser -k 5000/tcp
```

### Worker Timeout (Gunicorn Çökmesi)
Gunicorn loglarında "Worker Timeout" görülüyorsa:
1. `.env` dosyasında `DATABASE_URL` için `localhost` yerine `127.0.0.1` kullanın (IPv6 gecikmelerini önler).
2. Gunicorn `--timeout` değerini artırın.
3. `diagnose_setup.py` scriptini çalıştırarak veritabanı bağlantı hızını ölçün.

### İzin Sorunları (Permission Denied)
Gunicorn'u asla **root** olarak çalıştırmayın. Eğer çalıştırıldıysa, dosya sahipliğini düzeltin:
```bash
sudo chown -R altikodtech:altikodtech /path/to/project
```

### Log Takibi
- Gunicorn Logları: `tail -f gunicorn_error.log`
- Apache Logları: `tail -f /var/log/virtualmin/celmak.altikodtech.com.tr_error_log`
- Sistem Logları: `journalctl -u celmakstok -f`

---

**Geliştirici Notu:** Uygulamayı ayağa kaldırırken `diagnose_setup.py` scriptini kullanmak her zaman en sağlıklı yoldur, çünkü bileşenleri (DB, Hashing vs.) tek tek test eder.
