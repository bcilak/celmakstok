# ÇELMAK Stok Takip Sistemi - Başlatma Kılavuzu

## 🚀 Hızlı Başlangıç (API Test İçin)

### Adım 1: Flask Uygulamasını Başlatın

Yeni bir terminal/komut satırı açın ve çalıştırın:

```bash
python run.py
```

**Çıktı:**
```
============================================================
          ÇELMAK STOK TAKİP SİSTEMİ
          Maliyetsiz Stok ve Üretim Yönetimi
============================================================

 * Running on http://127.0.0.1:5000
```

⚠️ **ÖNEMLİ:** Bu terminali AÇIK BIRAKIN! Uygulama çalışmaya devam etmeli.

---

### Adım 2: Tarayıcıda Giriş Yapın

1. Tarayıcıda açın: http://localhost:5000
2. Giriş yapın:
   - **Kullanıcı adı:** admin
   - **Şifre:** admin123

✅ Giriş başarılı olduğunda dashboard açılacak.

---

### Adım 3: API'yi Test Edin

#### Yöntem 1: Python Script ile Test

**FARKLI** bir terminal açın ve çalıştırın:

```bash
python example_api_usage.py
```

**Beklenen Çıktı:**
```
======================================================================
   ÇELMAK Stok Takip API - Örnek Kullanım
======================================================================

=== Health Check ===
Status Code: 200
{
  "status": "healthy",
  "version": "1.0",
  "service": "ÇELMAK Stok Takip API"
}

=== Ürün Listesi (150 adet) ===
- CM-001: Hidrolik Silindir (Stok: 45 adet)
...
```

#### Yöntem 2: Tarayıcıda Görselleştirme

1. `api_test.html` dosyasını çift tıklayarak açın
2. **"🔄 Ürün Ağacını Yükle"** butonuna tıklayın
3. İnteraktif network grafiği görüntülenecek

#### Yöntem 3: curl ile Test

```bash
curl http://localhost:5000/api/v1/health
```

**Çıktı:**
```json
{
  "status": "healthy",
  "version": "1.0",
  "service": "ÇELMAK Stok Takip API"
}
```

---

## 🔧 Sorun Giderme

### ❌ "Connection Refused" Hatası

**Sorun:** Flask uygulaması çalışmıyor.

**Çözüm:**
1. İlk terminalde `python run.py` çalıştığından emin olun
2. Çıktıda "Running on http://127.0.0.1:5000" göründüğünü kontrol edin
3. Tarayıcıda http://localhost:5000 açılıyor mu test edin

### ❌ "401 Unauthorized" Hatası

**Sorun:** API authentication başarısız.

**Çözüm:**
1. Tarayıcıda http://localhost:5000 adresine gidin
2. Admin ile giriş yapın (admin/admin123)
3. Giriş yaptıktan sonra API isteklerini tekrar deneyin

### ❌ "ModuleNotFoundError: No module named 'requests'"

**Sorun:** Python kütüphanesi eksik.

**Çözüm:**
```bash
pip install requests
```

---

## 📋 API Endpoint'leri Test Checklist

Sırasıyla test edin:

- [ ] **Health Check**: `curl http://localhost:5000/api/v1/health`
- [ ] **Ürün Listesi**: Tarayıcıda giriş yap → `python example_api_usage.py`
- [ ] **Görselleştirme**: `api_test.html` aç → "Ürün Ağacını Yükle"

---

## 🎯 Başarılı Test Senaryosu

### Terminal 1 (Flask Uygulaması):
```bash
python run.py

# Çıktı:
============================================================
          ÇELMAK STOK TAKİP SİSTEMİ
============================================================
 * Running on http://127.0.0.1:5000
```

### Terminal 2 (API Test):
```bash
python example_api_usage.py

# Çıktı:
=== Health Check ===
Status Code: 200
✓ API Çalışıyor

=== Ürün Listesi (150 adet) ===
- CM-001: Hidrolik Silindir (Stok: 45 adet)
...

✓ Tüm örnekler başarıyla çalıştırıldı!
```

### Tarayıcı (Görselleştirme):
1. `api_test.html` aç
2. "🔄 Ürün Ağacını Yükle" tıkla
3. İnteraktif ağaç grafiği görüntülenir
4. Düğümlerin üzerine gel → Detay tooltip'i görürsün

---

## 🔐 API Key Kullanımı (Opsiyonel)

Dış uygulamalardan güvenli erişim için:

### 1. `.env` dosyasını düzenle:
```env
API_KEY=sk_live_your_secure_api_key_here
```

### 2. İsteklerde API Key kullan:
```bash
curl -H "X-API-Key: sk_live_your_secure_api_key_here" \
  http://localhost:5000/api/v1/products/full
```

### 3. Python'da:
```python
HEADERS = {'X-API-Key': 'sk_live_your_secure_api_key_here'}
response = requests.get(API_URL, headers=HEADERS)
```

**Not:** API_KEY boş bırakılırsa sadece tarayıcı session kontrolü yapılır (mevcut durum).

---

## 📚 Daha Fazla Bilgi

- **Detaylı API Dökümanı**: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
- **Hızlı Başlangıç**: [API_README.md](./API_README.md)
- **Örnek Kodlar**: `example_api_usage.py`
- **Görselleştirme**: `api_test.html`

---

## ⚡ Özet

```bash
# Terminal 1: Flask uygulamasını başlat
python run.py

# Terminal 2: API'yi test et
python example_api_usage.py

# Tarayıcı: Görselleştirme
api_test.html dosyasını aç
```

**Hepsi bu kadar! 🎉**
