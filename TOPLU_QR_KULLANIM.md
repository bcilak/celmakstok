# Toplu QR Etiket Yazdırma - Kullanım Kılavuzu

## 🎯 Özellikler

✅ **3 Farklı Etiket Boyutu:**
- **Küçük:** 6x6 cm (600x600 piksel) - Küçük parçalar için
- **Orta:** 10x10 cm (1000x1000 piksel) - Standart kullanım
- **Büyük:** 15x15 cm (1500x1500 piksel) - Büyük ürünler veya uzaktan okuma

✅ **Toplu İşlem:**
- 50 ürüne kadar tek sayfada görüntüleme
- Checkbox ile çoklu seçim
- "Tümünü Seç" / "Seçimi Temizle" butonları
- Seçili ürün sayısı göstergesi

✅ **Filtre ve Arama:**
- Kategori bazlı filtreleme
- Ürün kodu/adı ile arama
- Sayfalama desteği

✅ **Önizleme:**
- Her ürün için önizleme butonu
- Modal ile büyük görüntüleme
- Boyut değiştirme özelliği
- Tek etiket indirme

✅ **ZIP İndirme:**
- Seçili tüm etiketler tek ZIP dosyasında
- Dosya adı: `qr_etiketleri_{boyut}_{tarih}.zip`
- Her etiket: `{UrunKodu}_{UrunAdi}.png`

---

## 📖 Kullanım Adımları

### 1. Toplu QR Sayfasına Gidin

Sol menüden: **Toplu QR Yazdır**

Veya URL: `https://celmak.altikodtech.com.tr/products/bulk-qr`

---

### 2. Ürünleri Filtreleyin (Opsiyonel)

**Kategori Seçin:**
- Dropdown'dan kategori seçin
- Sadece o kategorideki ürünler listelenir

**Ürün Arayın:**
- Ürün kodu veya adı yazın
- "Filtrele" butonuna tıklayın

---

### 3. Etiket Boyutunu Seçin

Sayfanın üstündeki dropdown'dan boyut seçin:
- **Küçük** - Minik parçalar, raf etiketleri
- **Orta** - Genel kullanım (varsayılan)
- **Büyük** - Paletler, büyük kutular

---

### 4. Ürünleri Seçin

**Tek Tek Seçim:**
- İstediğiniz ürünlerin solundaki checkbox'ı işaretleyin

**Toplu Seçim:**
- "Tümünü Seç" butonu - Sayfadaki tüm ürünleri seçer
- "Seçimi Temizle" butonu - Tüm seçimleri kaldırır

**Seçili Sayı:**
- Üstteki mavi alan seçili ürün sayısını gösterir
- Örnek: "15 ürün seçildi"

---

### 5. Önizleme (Opsiyonel)

Bir ürünün "Önizle" butonuna tıklayın:

- Modal açılır
- Varsayılan boyutta etiket gösterilir
- Boyut değiştirme:
  - Dropdown'dan başka boyut seçin
  - Önizleme otomatik güncellenir
- "İndir" butonu - Tek etiketi PNG olarak indirir

---

### 6. ZIP Dosyasını İndirin

1. En az 1 ürün seçili olmalı
2. "ZIP İndir" butonuna tıklayın
3. Tarayıcınız ZIP dosyasını indirecek

**İndirilen Dosya:**
```
qr_etiketleri_medium_20260112_154530.zip
├── CM-001_Hidrolik Silindir.png
├── CM-002_Somun M10.png
├── CM-003_Vida M8.png
└── ...
```

---

## 🖨️ Yazdırma Önerileri

### Küçük Etiketler (6x6 cm)
- **Yazıcı Ayarı:** 300 DPI
- **Kağıt:** Etiket kağıdı 50x30 mm
- **Kullanım:** Küçük parçalar, raf etiketleri

### Orta Etiketler (10x10 cm)
- **Yazıcı Ayarı:** 300 DPI
- **Kağıt:** A4 etiket kağıdı (6 etiket/sayfa)
- **Kullanım:** Genel amaçlı

### Büyük Etiketler (15x15 cm)
- **Yazıcı Ayarı:** 300 DPI
- **Kağıt:** A4 tam sayfa veya büyük etiket
- **Kullanım:** Paletler, konteynerler

---

## 💡 İpuçları

### Hızlı Toplu İşlem
```
1. Kategori seçin (örn: "Bağlantı Elemanları")
2. "Tümünü Seç" butonuna tıklayın
3. Boyut seçin (örn: "Küçük")
4. "ZIP İndir" butonuna tıklayın
```

### Özel Seçim
```
1. Arama kutusuna "VIDA" yazın
2. Filtrele
3. İstediğiniz vidaları seçin
4. Önizleme ile kontrol edin
5. ZIP indirin
```

### Farklı Boyutlarda Aynı Ürünler
```
1. Seçim yapın
2. Küçük boyut seçip ZIP indirin
3. Geri gelin (seçimler korunur)
4. Orta boyut seçip tekrar ZIP indirin
```

---

## 🔧 Teknik Detaylar

### Etiket İçeriği
- **Sol Şerit:** ÇELMAK logosu (beyaz)
- **Üst:** Ana ÇELMAK logosu (renkli)
- **Parça Numarası:** Bold font
- **Parça Adı:** Normal font
- **QR Kod:** High error correction (H seviye)

### Dosya Formatı
- **Format:** PNG
- **DPI:** 300 (baskı kalitesi)
- **Renk:** RGB
- **Şeffaflık:** Yok (beyaz arka plan)

### Performans
- 50 etiket: ~5-10 saniye
- ZIP boyutu: ~2-5 MB (50 etiket için)
- Maksimum: 50 ürün/işlem (sayfa başına)

---

## 📱 Mobil ve Tablet Uyumluluğu

Sayfa responsive tasarıma sahip:
- Tablet'te yan yana sütunlar
- Mobil'de tek sütun
- Checkbox'lar dokunmatik uyumlu
- Modal'lar tam ekran açılır

---

## 🐛 Sorun Giderme

### Problem: "Lütfen en az bir ürün seçin" Hatası
**Çözüm:** Herhangi bir checkbox'ı işaretleyin.

### Problem: ZIP İndirmiyor
**Çözüm:**
1. Tarayıcınızın popup blocker'ını kontrol edin
2. İndirmeler klasörünü kontrol edin
3. Console'da hata var mı bakın (F12)

### Problem: Önizleme Boş Görünüyor
**Çözüm:**
1. Logo dosyaları sunucuda var mı kontrol edin
2. Font dosyaları yüklü mü kontrol edin
3. Apache/Gunicorn restart edin

### Problem: QR Kod Okumuyor
**Çözüm:**
1. QR kod yeterince büyük mü? (en az Orta boyut)
2. Baskı kalitesi 300 DPI mi?
3. Kağıt mat mı parlak mı? (mat tercih edilir)

---

## 🎨 Özelleştirme (Geliştiriciler İçin)

### Yeni Boyut Eklemek

`app/utils/qr_generator.py` içinde `size_configs` sözlüğüne ekleyin:

```python
'xlarge': {
    'width': 2000,
    'height': 2000,
    'red_strip': 320,
    'logo_height': 180,
    'font_label_size': 64,
    'font_value_size': 72,
    'qr_size': 800,
    'padding': 100
}
```

Template'te dropdown'a seçenek ekleyin:
```html
<option value="xlarge">Çok Büyük (20x20 cm)</option>
```

### Logo Değiştirmek

Logo dosyalarını `app/static/images/` klasörüne koyun:
- `celmak_logo.png` - Ana logo (renkli)
- `celmak_logo_white.png` - Beyaz logo (sol şerit için)

**Logo Gereksinimleri:**
- Format: PNG (şeffaf arka plan)
- Oran: ~3:1 (genişlik:yükseklik)
- Çözünürlük: En az 300 DPI

---

## 📊 Örnek Kullanım Senaryoları

### Senaryo 1: Yeni Ürünler İçin Etiket Basımı
```
1. Son 1 haftada eklenen ürünleri filtrele
2. "Tümünü Seç"
3. Orta boyut
4. ZIP indir
5. Yazıcıdan bas
6. Ürünlere yapıştır
```

### Senaryo 2: Kritik Stok Etiketleri
```
1. Ana sayfadan "Kritik Stok" filtresine git
2. "Toplu QR Yazdır" linkine tıkla
3. Kritik ürünler otomatik filtrelenmiş olarak gelir
4. "Tümünü Seç"
5. Küçük boyut (raf etiketi için)
6. ZIP indir
```

### Senaryo 3: Kategori Bazlı Etiketleme
```
1. Kategori: "Bağlantı Elemanları" seç
2. "Tümünü Seç"
3. Büyük boyut (depo rafları için)
4. ZIP indir
5. A4 tam sayfa olarak bas
6. Raflara asıl
```

---

## ✅ Checklist: İlk Kullanım

- [ ] Logo dosyaları sunucuya yüklendi
- [ ] Font dosyaları kurulu (DejaVu Sans)
- [ ] BASE_URL .env'de doğru
- [ ] Toplu QR sayfası açılıyor
- [ ] Önizleme çalışıyor
- [ ] ZIP indirme çalışıyor
- [ ] QR kodlar taranabiliyor
- [ ] Yazıcı ayarları 300 DPI

---

## 🚀 Gelecek Özellikler

Planlanan iyileştirmeler:
- [ ] PDF export (tek PDF'te tüm etiketler)
- [ ] Excel import (toplu yazdırma listesi)
- [ ] Barkod desteği (QR + Barkod)
- [ ] Özel etiket tasarımcısı
- [ ] Yazıcı profilleri (Brother, Zebra vb.)

---

**Hazırlayan:** Claude
**Tarih:** 2026-01-12
**Versiyon:** 1.0
**Proje:** ÇELMAK Stok Takip Sistemi
