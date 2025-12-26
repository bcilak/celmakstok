# 🚀 Virtualmin Üzerinden ÇELMAK Stok Takip Sistemi Kurulumu

## 📋 İçindekiler
1. [Gereksinimler](#gereksinimler)
2. [Virtualmin'de Virtual Server Oluşturma](#1-virtualmin-virtual-server-oluşturma)
3. [PostgreSQL Kurulumu](#2-postgresql-kurulumu)
4. [Python ve Sanal Ortam Kurulumu](#3-python-kurulumu)
5. [Uygulamayı Sunucuya Yükleme](#4-uygulamayı-yükleme)
6. [Systemd Servis Oluşturma](#5-systemd-servis)
7. [Nginx/Apache Yapılandırma](#6-web-server-yapılandırma)
8. [SSL Sertifikası](#7-ssl-sertifikası)
9. [Test ve Doğrulama](#8-test)
10. [Sorun Giderme](#sorun-giderme)

---

## 🔧 Gereksinimler

### Sunucu Gereksinimleri:
- ✅ **İşletim Sistemi:** Ubuntu 20.04+ / CentOS 7+ / Debian 10+
- ✅ **RAM:** Minimum 2GB (4GB önerilir)
- ✅ **Disk:** 10GB boş alan
- ✅ **Virtualmin:** Kurulu ve çalışır durumda
- ✅ **Root/Sudo erişimi**

### Gerekli Paketler:
```bash
- Python 3.9+
- PostgreSQL 12+
- Nginx veya Apache
- Git
```

---

## 1️⃣ Virtualmin'de Virtual Server Oluşturma

### Adım 1.1: Yeni Virtual Server Oluşturun

1. Virtualmin panel'e giriş yapın
2. Sol menüden **"Create Virtual Server"** seçin
3. Aşağıdaki bilgileri girin:

```
Domain name: stok.yourcompany.com
Description: ÇELMAK Stok Takip Sistemi
Administration password: [güçlü bir şifre]
Administration username: celmak_admin
```

4. **"Create Server"** butonuna tıklayın

### Adım 1.2: SSH Erişimini Etkinleştirin

```bash
# Virtualmin panelden:
# Edit Virtual Server → Enabled features →
# ✅ SSH access to server enabled
```

---

## 2️⃣ PostgreSQL Kurulumu

### Adım 2.1: PostgreSQL'i Kurun

```bash
# Ubuntu/Debian için
sudo apt update
sudo apt install postgresql postgresql-contrib -y

# CentOS/RHEL için
sudo yum install postgresql-server postgresql-contrib -y
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Adım 2.2: PostgreSQL Kullanıcı ve Veritabanı Oluşturun

```bash
# PostgreSQL kullanıcısına geçin
sudo -u postgres psql

# SQL komutları (PostgreSQL içinde):
CREATE DATABASE celmak_stok;
CREATE USER celmak_user WITH PASSWORD 'GucluSifre123!';
ALTER USER celmak_user WITH SUPERUSER;
GRANT ALL PRIVILEGES ON DATABASE celmak_stok TO celmak_user;
\q
```

### Adım 2.3: PostgreSQL Uzaktan Bağlantıya İzin Ver

```bash
# pg_hba.conf dosyasını düzenle
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Aşağıdaki satırı ekleyin:
# local   all             celmak_user                              md5
# host    celmak_stok     celmak_user     127.0.0.1/32            md5

# PostgreSQL'i yeniden başlat
sudo systemctl restart postgresql
```

### Adım 2.4: Bağlantıyı Test Edin

```bash
psql -U celmak_user -d celmak_stok -h localhost
# Şifre sorduğunda: GucluSifre123!
# Başarılı ise: celmak_stok=#
\q
```

---

## 3️⃣ Python Kurulumu

### Adım 3.1: Python 3.11 Kurun

```bash
# Ubuntu/Debian için
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip python3.11-dev libpq-dev gcc -y

# CentOS/RHEL için
sudo yum install python3.11 python3.11-devel gcc postgresql-devel -y
```

### Adım 3.2: Python Versiyonunu Kontrol Edin

```bash
python3.11 --version
# Output: Python 3.11.x
```

---

## 4️⃣ Uygulamayı Yükleme

### Adım 4.1: Proje Dizinini Oluşturun

```bash
# Virtual server'ın home dizinine geçin
cd /home/celmak_admin

# Uygulama dizini oluştur
sudo mkdir -p /opt/celmakstok
sudo chown celmak_admin:celmak_admin /opt/celmakstok
cd /opt/celmakstok
```

### Adım 4.2: Dosyaları Yükleyin

**Seçenek 1: Git ile (Önerilir)**

```bash
# GitHub'a yüklediyseniz
git clone https://github.com/yourcompany/celmakstok.git .

# Veya private repo ise
git clone https://yourusername@github.com/yourcompany/celmakstok.git .
```

**Seçenek 2: FTP/SFTP ile**

```bash
# FileZilla veya WinSCP ile dosyaları yükleyin
# Hedef dizin: /opt/celmakstok
```

**Seçenek 3: SCP ile (Windows PowerShell'den)**

```powershell
# Yerel makinenizden
scp -r C:\Users\Baris\Desktop\Dosyalar\Kod Klasörleri\celmakstok\* celmak_admin@your-server-ip:/opt/celmakstok/
```

### Adım 4.3: Dosya İzinlerini Ayarlayın

```bash
cd /opt/celmakstok
sudo chown -R celmak_admin:celmak_admin .
chmod -R 755 .
```

### Adım 4.4: Python Sanal Ortamı Oluşturun

```bash
cd /opt/celmakstok

# Sanal ortam oluştur
python3.11 -m venv venv

# Sanal ortamı aktif et
source venv/bin/activate

# Pip'i güncelle
pip install --upgrade pip

# Gereksinimleri yükle
pip install -r requirements.txt
```

### Adım 4.5: Environment Dosyasını Ayarlayın

```bash
# .env dosyası oluştur
cp .env.example .env
nano .env
```

**.env dosyası içeriği:**

```env
# Flask Ayarları
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=BURAYA_RASTGELE_UZUN_BIR_ANAHTAR_URET

# Veritabanı
DATABASE_URL=postgresql://celmak_user:GucluSifre123!@localhost:5432/celmak_stok

# Güvenlik
DEBUG=False
TESTING=False
WTF_CSRF_ENABLED=True
```

**Secret Key Üretme:**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Adım 4.6: Veritabanını Başlatın

```bash
# Sanal ortamın aktif olduğundan emin olun
source venv/bin/activate

# Veritabanını oluştur
python run.py init

# Başarılı mesaj görmelisiniz:
# ✓ Admin kullanıcısı oluşturuldu (admin / admin123)
# ✓ Veritabanı başarıyla başlatıldı!
```

---

## 5️⃣ Systemd Servis Oluşturma

### Adım 5.1: Gunicorn Yükleyin

```bash
source /opt/celmakstok/venv/bin/activate
pip install gunicorn
```

### Adım 5.2: Systemd Servis Dosyası Oluşturun

```bash
sudo nano /etc/systemd/system/celmakstok.service
```

**Dosya içeriği:**

```ini
[Unit]
Description=ÇELMAK Stok Takip Sistemi
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=celmak_admin
Group=celmak_admin
WorkingDirectory=/opt/celmakstok
Environment="PATH=/opt/celmakstok/venv/bin"
EnvironmentFile=/opt/celmakstok/.env
ExecStart=/opt/celmakstok/venv/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --timeout 120 \
    --bind unix:/opt/celmakstok/celmakstok.sock \
    --access-logfile /var/log/celmakstok/access.log \
    --error-logfile /var/log/celmakstok/error.log \
    --log-level info \
    run:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Adım 5.3: Log Dizini Oluşturun

```bash
sudo mkdir -p /var/log/celmakstok
sudo chown celmak_admin:celmak_admin /var/log/celmakstok
```

### Adım 5.4: Servisi Başlatın

```bash
# Systemd'yi yeniden yükle
sudo systemctl daemon-reload

# Servisi etkinleştir (otomatik başlama)
sudo systemctl enable celmakstok

# Servisi başlat
sudo systemctl start celmakstok

# Durumu kontrol et
sudo systemctl status celmakstok

# Logları izle
sudo journalctl -u celmakstok -f
```

---

## 6️⃣ Web Server Yapılandırma

### SEÇENEK A: Nginx Yapılandırma (Önerilir)

#### Adım 6A.1: Nginx Kurun

```bash
# Ubuntu/Debian
sudo apt install nginx -y

# CentOS/RHEL
sudo yum install nginx -y

# Başlat
sudo systemctl start nginx
sudo systemctl enable nginx
```

#### Adım 6A.2: Nginx Yapılandırma Dosyası

```bash
sudo nano /etc/nginx/sites-available/celmakstok
```

**Dosya içeriği:**

```nginx
upstream celmakstok_app {
    server unix:/opt/celmakstok/celmakstok.sock fail_timeout=0;
}

server {
    listen 80;
    server_name stok.yourcompany.com;

    client_max_body_size 100M;

    access_log /var/log/nginx/celmakstok-access.log;
    error_log /var/log/nginx/celmakstok-error.log;

    # Statik dosyalar
    location /static {
        alias /opt/celmakstok/app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Upload dosyaları
    location /static/uploads {
        alias /opt/celmakstok/app/static/uploads;
        expires 1h;
    }

    # Ana uygulama
    location / {
        proxy_pass http://celmakstok_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

#### Adım 6A.3: Nginx'i Etkinleştirin

```bash
# Symbolic link oluştur
sudo ln -s /etc/nginx/sites-available/celmakstok /etc/nginx/sites-enabled/

# Yapılandırmayı test et
sudo nginx -t

# Nginx'i yeniden başlat
sudo systemctl restart nginx
```

### SEÇENEK B: Apache Yapılandırma (Virtualmin Varsayılan)

#### Adım 6B.1: Proxy Modüllerini Aktifleştirin

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod headers
sudo systemctl restart apache2
```

#### Adım 6B.2: Virtualmin'den Virtual Host Düzenleyin

```bash
# Virtualmin Panel → Select Server → Services → Configure Website
```

**Veya manuel olarak:**

```bash
sudo nano /etc/apache2/sites-available/stok.yourcompany.com.conf
```

**Aşağıdaki satırları ekleyin:**

```apache
<VirtualHost *:80>
    ServerName stok.yourcompany.com
    ServerAlias www.stok.yourcompany.com

    DocumentRoot /opt/celmakstok/app/static

    # Gunicorn proxy
    ProxyPreserveHost On
    ProxyPass /static !
    ProxyPass / unix:/opt/celmakstok/celmakstok.sock|http://127.0.0.1/
    ProxyPassReverse / unix:/opt/celmakstok/celmakstok.sock|http://127.0.0.1/

    # Statik dosyalar
    Alias /static /opt/celmakstok/app/static
    <Directory /opt/celmakstok/app/static>
        Require all granted
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/celmakstok-error.log
    CustomLog ${APACHE_LOG_DIR}/celmakstok-access.log combined
</VirtualHost>
```

```bash
# Apache'yi yeniden başlat
sudo systemctl restart apache2
```

---

## 7️⃣ SSL Sertifikası (Let's Encrypt)

### Adım 7.1: Certbot Kurun

```bash
# Ubuntu/Debian
sudo apt install certbot python3-certbot-nginx -y

# Nginx için
sudo certbot --nginx -d stok.yourcompany.com

# Apache için
sudo apt install certbot python3-certbot-apache -y
sudo certbot --apache -d stok.yourcompany.com
```

### Adım 7.2: Otomatik Yenileme

```bash
# Test et
sudo certbot renew --dry-run

# Cron job zaten otomatik oluşturulur
sudo systemctl status certbot.timer
```

---

## 8️⃣ Test ve Doğrulama

### Adım 8.1: Servisleri Kontrol Edin

```bash
# PostgreSQL
sudo systemctl status postgresql

# Uygulama servisi
sudo systemctl status celmakstok

# Web server
sudo systemctl status nginx  # veya apache2
```

### Adım 8.2: Logları Kontrol Edin

```bash
# Uygulama logları
tail -f /var/log/celmakstok/error.log
tail -f /var/log/celmakstok/access.log

# Nginx logları
tail -f /var/log/nginx/celmakstok-error.log

# Systemd logları
sudo journalctl -u celmakstok -n 100
```

### Adım 8.3: Tarayıcıdan Test Edin

```
http://stok.yourcompany.com
https://stok.yourcompany.com (SSL sonrası)

Kullanıcı: admin
Şifre: admin123
```

### Adım 8.4: İlk Giriş Sonrası

```
1. Admin şifresini değiştirin
2. Yeni kullanıcılar ekleyin
3. Kategorileri kontrol edin
4. Ürünleri kontrol edin
```

---

## 🔥 Firewall Ayarları

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status

# FirewallD (CentOS/RHEL)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## 💾 Yedekleme Sistemi

### Otomatik Veritabanı Yedeği

```bash
# Yedek scripti oluştur
sudo nano /opt/celmakstok/backup.sh
```

**Script içeriği:**

```bash
#!/bin/bash
BACKUP_DIR="/opt/celmakstok/backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="celmak_backup_$DATE.sql.gz"

mkdir -p $BACKUP_DIR

# PostgreSQL dump
pg_dump -U celmak_user -h localhost celmak_stok | gzip > "$BACKUP_DIR/$FILENAME"

# Eski yedekleri sil (30 günden eski)
find $BACKUP_DIR -name "celmak_backup_*.sql.gz" -mtime +30 -delete

echo "Yedek alındı: $FILENAME"
```

```bash
# İzin ver
chmod +x /opt/celmakstok/backup.sh

# Cron job ekle
crontab -e

# Her gün saat 02:00'de yedek al
0 2 * * * /opt/celmakstok/backup.sh >> /var/log/celmakstok/backup.log 2>&1
```

---

## 🔄 Güncelleme Prosedürü

```bash
# 1. Yedek al
/opt/celmakstok/backup.sh

# 2. Uygulamayı durdur
sudo systemctl stop celmakstok

# 3. Yeni kodu çek (Git kullanıyorsanız)
cd /opt/celmakstok
git pull origin main

# 4. Bağımlılıkları güncelle
source venv/bin/activate
pip install -r requirements.txt

# 5. Database migration (varsa)
# python migrate.py

# 6. Servisi başlat
sudo systemctl start celmakstok

# 7. Durumu kontrol et
sudo systemctl status celmakstok
```

---

## ⚠️ Sorun Giderme

### Problem 1: "502 Bad Gateway"

```bash
# Servis çalışıyor mu?
sudo systemctl status celmakstok

# Socket dosyası var mı?
ls -la /opt/celmakstok/celmakstok.sock

# Logları kontrol et
tail -f /var/log/celmakstok/error.log
```

### Problem 2: "Database connection error"

```bash
# PostgreSQL çalışıyor mu?
sudo systemctl status postgresql

# Bağlantıyı test et
psql -U celmak_user -d celmak_stok -h localhost

# .env dosyasını kontrol et
cat /opt/celmakstok/.env | grep DATABASE_URL
```

### Problem 3: "Permission denied"

```bash
# Dizin izinlerini düzelt
sudo chown -R celmak_admin:celmak_admin /opt/celmakstok
chmod -R 755 /opt/celmakstok

# Socket izinleri
sudo chmod 777 /opt/celmakstok/celmakstok.sock
```

### Problem 4: Statik dosyalar yüklenmiyor

```bash
# Nginx için
sudo chmod -R 755 /opt/celmakstok/app/static

# SELinux (CentOS/RHEL)
sudo chcon -Rt httpd_sys_content_t /opt/celmakstok/app/static
```

---

## 📊 Monitoring

### Sistem Kaynaklarını İzleme

```bash
# CPU ve RAM kullanımı
htop

# Disk kullanımı
df -h

# Uygulama logları (canlı)
sudo journalctl -u celmakstok -f
```

---

## ✅ Son Kontrol Listesi

- [ ] PostgreSQL kurulu ve çalışıyor
- [ ] Python 3.11 kurulu
- [ ] Uygulama /opt/celmakstok dizininde
- [ ] Sanal ortam oluşturuldu ve paketler yüklendi
- [ ] .env dosyası düzenlendi
- [ ] Veritabanı oluşturuldu ve test edildi
- [ ] Systemd servisi oluşturuldu ve çalışıyor
- [ ] Nginx/Apache yapılandırıldı
- [ ] SSL sertifikası kuruldu
- [ ] Firewall ayarları yapıldı
- [ ] Yedekleme sistemi kuruldu
- [ ] Tarayıcıdan erişim test edildi
- [ ] Admin şifresi değiştirildi

---

**🎉 Tebrikler! ÇELMAK Stok Takip Sistemi canlıda!**

**Destek:** support@yourcompany.com
**Dokümantasyon:** https://stok.yourcompany.com/docs
