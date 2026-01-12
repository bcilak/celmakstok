# Sunucu Git Conflict Çözümü

## Hata Mesajı
```
error: Your local changes would be overwritten by merge
Please commit your changes or stash them before you merge.
```

Bu, sunucuda yerel değişiklikler olduğu anlamına geliyor.

---

## Hızlı Çözüm (Önerilen)

Sunucuda şu komutları sırayla çalıştırın:

### 1. Mevcut değişiklikleri yedekleyin
```bash
cd /home/kullanici/celmakstok  # veya proje dizininiz
git stash save "Sunucu yerel değişiklikleri - $(date +%Y%m%d-%H%M%S)"
```

### 2. GitHub'dan çekin
```bash
git pull origin master
```

### 3. .env dosyasını manuel kontrol edin
```bash
cat .env
```

Eğer `.env` içinde `BASE_URL=http://localhost:5000` varsa, düzeltin:
```bash
nano .env
```

Şunu bulun:
```env
BASE_URL=http://localhost:5000
```

Şununla değiştirin:
```env
BASE_URL=https://celmak.altikodtech.com.tr
```

Kaydedin: **Ctrl+O** → **Enter** → **Ctrl+X**

### 4. API_KEY ekleyin (eğer yoksa)
```bash
nano .env
```

En alta ekleyin:
```env
API_KEY=sk_live_celmak_2024_guclu_anahtar_12345
```

**Güçlü API key oluşturmak için:**
```bash
python3 -c "import secrets; print('sk_live_' + secrets.token_urlsafe(32))"
```

Kaydedin: **Ctrl+O** → **Enter** → **Ctrl+X**

### 5. Uygulamayı restart edin
```bash
sudo systemctl restart celmak-stok
```

### 6. Test edin
```bash
curl https://celmak.altikodtech.com.tr/api/v1/health
```

**Başarılı yanıt:**
```json
{
  "status": "healthy",
  "version": "1.0",
  "service": "ÇELMAK Stok Takip API"
}
```

---

## Alternatif: Sunucu Değişikliklerini Saklamak

Eğer sunucudaki değişiklikleri korumak istiyorsanız:

```bash
# 1. Yerel değişiklikleri commit edin
git add -A
git commit -m "Sunucu yerel değişiklikleri"

# 2. Remote'dan çekin (merge)
git pull origin master

# 3. Eğer conflict varsa, çözün
git status  # Conflicted dosyaları gösterir
```

### Conflict Çözme
```bash
# Her conflicted dosya için:
nano <dosya_adı>

# Şu işaretleri bulun:
<<<<<<< HEAD
... sunucudaki kod ...
=======
... GitHub'daki kod ...
>>>>>>> origin/master

# Doğru kodu seçin, işaretleri silin
# Kaydedin ve:
git add <dosya_adı>

# Tüm conflictler çözüldükten sonra:
git commit -m "Sunucu conflict çözüldü"
```

---

## .htaccess Hatası

Eğer `.htaccess` hatası alıyorsanız:

```bash
# .htaccess dosyasını yedekleyin
mv .htaccess .htaccess.backup

# Şimdi tekrar pull yapın
git pull origin master

# Eğer gerekirse .htaccess'i geri yükleyin
```

---

## En Basit Yöntem (Yeni Baştan)

**UYARI:** Bu yöntem sunucudaki tüm yerel değişiklikleri siler!

```bash
# 1. Proje klasörünü yedekleyin
cd /home/kullanici
cp -r celmakstok celmakstok_backup_$(date +%Y%m%d_%H%M%S)

# 2. Eski klasörü silin
rm -rf celmakstok

# 3. Yeniden clone edin
git clone https://github.com/bcilak/celmakstok.git
cd celmakstok

# 4. .env dosyasını oluşturun
cp .env.example .env
nano .env

# 5. Şunları düzenleyin:
BASE_URL=https://celmak.altikodtech.com.tr
API_KEY=sk_live_guclu_anahtar_12345
DATABASE_URL=postgresql+psycopg://celmak_user:CelmakStok2024!@localhost:5432/celmak_stok

# 6. Virtual environment oluşturun
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 7. Uygulamayı başlatın
sudo systemctl restart celmak-stok
```

---

## Önerilen: Güvenli Yedekleme + Pull

```bash
# 1. Önemli dosyaları yedekleyin
cp .env .env.backup
cp config.py config.py.backup 2>/dev/null || true

# 2. Git'i sıfırlayın ve çekin
git fetch origin
git reset --hard origin/master

# 3. .env'i geri yükleyin ve düzeltin
cp .env.backup .env
nano .env

# 4. BASE_URL'yi kontrol edin
grep BASE_URL .env

# Eğer yanlışsa düzeltin:
sed -i 's|BASE_URL=http://localhost:5000|BASE_URL=https://celmak.altikodtech.com.tr|g' .env

# 5. API_KEY ekleyin (yoksa)
echo "API_KEY=sk_live_celmak_2024_guclu_anahtar_12345" >> .env

# 6. Restart
sudo systemctl restart celmak-stok
```

---

## Doğrulama

Pull işleminden sonra şunları kontrol edin:

### 1. API dosyası güncel mi?
```bash
grep "v1/purchasing/critical-stock" app/routes/api.py
```

**Çıktı olmalı:** `@api_bp.route('/v1/purchasing/critical-stock', methods=['GET'])`

### 2. .env doğru mu?
```bash
cat .env | grep -E "BASE_URL|API_KEY"
```

**Çıktı olmalı:**
```
BASE_URL=https://celmak.altikodtech.com.tr
API_KEY=sk_live_...
```

### 3. Uygulama çalışıyor mu?
```bash
sudo systemctl status celmak-stok
```

**Çıktı:** `Active: active (running)`

### 4. API endpoint'ler var mı?
```bash
curl https://celmak.altikodtech.com.tr/api/v1/health
```

**Başarılı:** `{"status": "healthy", ...}`

---

## Özet Komut Sırası

```bash
# Sunucuda çalıştırın:
cd /home/kullanici/celmakstok
git stash
git pull origin master
nano .env  # BASE_URL ve API_KEY kontrol et
sudo systemctl restart celmak-stok
curl https://celmak.altikodtech.com.tr/api/v1/health
```

Başarılı! 🎉

---

**Hazırlayan:** Claude
**Tarih:** 2026-01-12
**Proje:** ÇELMAK Stok Takip - Git Conflict Çözümü
