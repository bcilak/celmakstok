# Excel'den Toplu Ürün Aktarma - Kullanım Kılavuzu

## 🎯 Özellik

Excel dosyasından tek seferde **100'lerce ürün** ekleyebilir veya güncelleyebilirsiniz.

---

## 📖 Adım Adım Kullanım

### 1️⃣ Excel'den Aktar Sayfasına Gidin

Sol menüden: **Excel'den Aktar** (Sadece Admin ve Yönetici görür)

Veya URL: `https://celmak.altikodtech.com.tr/products/import`

---

### 2️⃣ Excel Şablonunu İndirin

"Şablon İndir" butonuna tıklayın.

**İndirilen dosya:** `urun_import_sablonu_20260112.xlsx`

#### Şablon İçeriği:

| Ürün Kodu* | Ürün Adı* | Kategori ID* | Birim Tipi | Mevcut Stok | Minimum Stok | Barkod | Notlar |
|------------|-----------|--------------|------------|-------------|--------------|--------|--------|
| ORN-001 | Örnek Ürün 1 | 1 | adet | 100 | 10 | | Örnek not |
| ORN-002 | Örnek Ürün 2 | 1 | kg | 50 | 5 | 1234567890 | |

**`*` ile işaretli alanlar zorunludur!**

#### Şablon Özellikleri:
- ✅ **2 sayfa:**
  - Sayfa 1: "Ürün Şablonu" (veri girişi burada)
  - Sayfa 2: "Bilgi" (alan açıklamaları)
- ✅ **Örnek veriler** (ORN- ile başlayanlar otomatik atlanır)
- ✅ **Renkli başlıklar** (mavi)
- ✅ **Geniş kolonlar**

---

### 3️⃣ Excel'i Doldurun

#### A. Kategori ID'lerini Öğrenin

**Yöntem 1:** Kategoriler sayfasından ID'leri not alın
- Sol menüden "Üretim" → "Kategoriler"
- Her kategorinin ID'si tabloda görünür

**Yöntem 2:** Mevcut ürünleri dışa aktarıp bakın
- Ürünler sayfasından "Excel'e Aktar"
- "Kategori ID" sütununa bakın

**Yaygın Kategoriler (Örnek):**
```
1 - Hammaddeler
2 - Yardımcı Malzemeler
3 - Bağlantı Elemanları
4 - Kimyasallar
5 - Ana Ürünler
```

#### B. Ürünleri Ekleyin

Excel'de örnek satırları silin veya üzerine yazın:

```
Ürün Kodu*    Ürün Adı*          Kategori ID*  Birim Tipi  Mevcut Stok  Minimum Stok  Barkod       Notlar
HM-001        Çelik Levha 2mm    1             m2          50           10
HM-002        Paslanmaz Boru     1             metre       120          20            5901234123457
YM-100        Kesme Yağı         4             litre       25           5                          Yeşil teneke
BE-045        Somun M8           3             adet        500          100
BE-046        Vida M8x20         3             adet        800          150
AU-TAM001     Tambur 150mm       5             adet        15           3                          Mamul ürün
```

#### C. Dikkat Edilecekler

**✅ Doğru:**
```
Ürün Kodu: HM-001, CM-045, YM-100
Kategori ID: 1, 2, 3 (sayı)
Birim Tipi: adet, kg, metre, litre, m2, m3
Stok: 100, 50.5, 0 (sayı)
Barkod: 1234567890123 (metin)
```

**❌ Yanlış:**
```
Ürün Kodu: (boş)
Kategori ID: "Hammaddeler" (isim değil, ID olmalı!)
Birim Tipi: (boş) - en azından "adet" yazın
Stok: "yüz adet" (metin değil, sayı)
```

---

### 4️⃣ Excel'i Yükleyin

1. Doldurduğunuz Excel'i kaydedin
2. "Excel Dosyası Seçin" butonuna tıklayın
3. Dosyanızı seçin (.xlsx veya .xls)
4. "Aktar ve Kaydet" butonuna tıklayın

---

### 5️⃣ Sonuçları Kontrol Edin

#### Başarılı İşlem:
```
✓ 15 ürün eklendi
✓ 3 ürün güncellendi
⚠ 2 ürün atlandı

Atlayanlar:
- Satır 7: Kategori bulunamadı: 99
- Satır 12: Ürün kodu boş
```

#### Hata Durumu:
```
✗ Dosya okunamadı: Zorunlu alan boş (Satır 5)
```

---

## 🔄 Güncelleme (Update) Modu

Eğer Excel'de **mevcut bir ürün kodu** varsa:
- ✅ Ürün güncellenir (yeni ürün eklenmez)
- ✅ Sadece verdiğiniz alanlar değişir
- ✅ Stok hareketleri korunur

**Örnek:**
```
Sistemde zaten var: HM-001 (Çelik Levha)
Excel'de: HM-001 | Çelik Levha 2mm (yeni isim)

Sonuç: Ürün adı "Çelik Levha 2mm" olarak güncellenir
```

---

## 💡 Kullanım Senaryoları

### Senaryo 1: İlk Kurulum (Sıfırdan Ürün Girişi)

```
1. Şablonu indirin
2. Excel'de 150 ürünü doldurun
3. Kategori ID'lerini doğru girin
4. Yükleyin → ✓ 150 ürün eklendi
```

### Senaryo 2: ERP'den Veri Aktarma

```
1. ERP'nizden ürün listesini Excel'e aktarın
2. Sütun isimlerini şablona uygun hale getirin:
   - "Stok Kodu" → "Ürün Kodu*"
   - "Stok Adı" → "Ürün Adı*"
   - "Kategori" → "Kategori ID*" (ID'ye çevirin)
3. Şablon formatına dönüştürün
4. Yükleyin
```

### Senaryo 3: Toplu Güncelleme

```
1. Mevcut ürünleri "Excel'e Aktar"
2. İndirilen Excel'de değişiklik yapın:
   - Minimum stokları güncelleyin
   - Barkod ekleyin
   - Notları düzenleyin
3. Tekrar yükleyin → Mevcut ürünler güncellenir
```

### Senaryo 4: Yeni Tedarikçiden Ürün Listesi

```
1. Tedarikçiden ürün listesi (Excel/PDF) alın
2. Copy-paste ile şablona yapıştırın
3. Kategori ID'lerini atayın
4. Minimum stok değerlerini belirleyin
5. Yükleyin
```

---

## 🐛 Yaygın Hatalar ve Çözümleri

### Hata 1: "Kategori bulunamadı: 99"
**Sebep:** Yanlış Kategori ID girdiniz.

**Çözüm:**
1. Kategoriler sayfasından doğru ID'yi öğrenin
2. Excel'de düzeltin
3. Tekrar yükleyin

---

### Hata 2: "Zorunlu alan boş"
**Sebep:** Ürün Kodu, Ürün Adı veya Kategori ID boş.

**Çözüm:**
1. Excel'de boş hücreleri doldurun
2. `*` işaretli alanların hepsi dolu olmalı

---

### Hata 3: "Dosya okunamadı"
**Sebep:** Excel formatı bozuk veya şablon değiştirilmiş.

**Çözüm:**
1. Şablonu yeniden indirin
2. Verilerinizi yeni şablona kopyalayın
3. "Ürün Şablonu" sayfası silinmemeli

---

### Hata 4: "Sadece Excel dosyaları yükleyebilirsiniz"
**Sebep:** CSV veya başka format yüklemeye çalıştınız.

**Çözüm:**
1. Dosya uzantısı .xlsx veya .xls olmalı
2. CSV ise Excel'de açıp "Farklı Kaydet" → .xlsx

---

## 📊 Performans

| Ürün Sayısı | İşlem Süresi | Tavsiye |
|-------------|--------------|---------|
| 1-50 | ~5 saniye | ✅ İdeal |
| 51-200 | ~15 saniye | ✅ Normal |
| 201-500 | ~45 saniye | ⚠️ Sayfalara bölün |
| 500+ | Uzun sürer | ❌ 200'lük paketler halinde yükleyin |

**İpucu:** Çok ürün varsa 200'lük gruplara bölün.

---

## 🔐 Yetki Kontrolü

Bu özellik sadece şu kullanıcılar tarafından kullanılabilir:
- ✅ **Admin**
- ✅ **Yönetici**

Diğer roller (Kullanıcı, Depo Personeli) bu sayfayı göremez.

---

## 📝 Excel Şablon Özelleştirme

### Varsayılan Değerler Değiştirmek

`app/utils/excel_utils.py` dosyasında:

```python
# Örnek verileri değiştirin
example_data = [
    ['KM-001', 'Kırmızı Boya', '4', 'litre', '50', '10', '', 'Parlak'],
    ['KM-002', 'Yeşil Boya', '4', 'litre', '30', '5', '1234567', ''],
]
```

### Yeni Sütun Eklemek

1. `create_product_template()` içinde `headers` listesine ekleyin
2. `parse_product_excel()` içinde parse mantığı ekleyin
3. Veritabanı modelinde alan varsa kaydedin

---

## ✅ İyi Uygulamalar

### 1. Excel'i Yedekleyin
```
1. Şablonu doldurduktan sonra kaydedin
2. Yüklemeden önce "Farklı Kaydet" ile yedek alın
3. Tarih ekleyerek saklayın: "urunler_20260112.xlsx"
```

### 2. Küçük Testler Yapın
```
1. Önce 5-10 ürünle test edin
2. Başarılı olunca tam listeyi yükleyin
```

### 3. Kategori Mapping Tablosu Tutun
```
Excel'de ayrı bir sayfa oluşturun:

Kategori Adı        | ID
--------------------|----
Hammaddeler         | 1
Yardımcı Malzeme    | 2
Bağlantı Elemanları | 3
...
```

### 4. Barkod Kontrolü
```
1. Barkod numaraları metin olarak girin (başına ' ekleyin)
2. Örnek: '1234567890123
3. Yoksa sıfırlar kaybolabilir
```

---

## 🎨 Excel Düzenleme İpuçları

### Hızlı Doldurma
```
1. İlk satıra veri girin
2. Sağ alt köşedeki küçük kareyi aşağı sürükleyin (otomatik doldurma)
3. Ürün kodları otomatik artar: HM-001, HM-002, HM-003...
```

### Formül Kullanımı
```
Birim fiyat hesaplama (sonra başka sütuna kopyala):
=B2*C2

Stok değeri hesaplama:
=E2*birim_fiyat
```

### Filtre ile Düzenleme
```
1. Başlık satırını seçin
2. Veri → Filtre
3. Kategori ID'ye göre grupla
4. Toplu düzenleme yap
```

---

## 🚀 Gelecek Özellikler

Planlanan iyileştirmeler:
- [ ] CSV desteği
- [ ] Kategori adıyla import (ID yerine)
- [ ] Otomatik kategori eşleştirme
- [ ] Fotoğraf URL'si ile toplu görsel ekleme
- [ ] Validation önizleme (yüklemeden kontrol)
- [ ] Excel template builder (web'de şablon oluştur)

---

## 📞 Destek

### Sorun mu yaşıyorsunuz?

1. **Şablonu kontrol edin** - Doğru sayfa adı "Ürün Şablonu"
2. **Kategori ID'leri doğru mu** - Kategoriler sayfasından kontrol edin
3. **Zorunlu alanlar dolu mu** - `*` işaretli alanlar boş olmamalı
4. **Dosya formatı .xlsx mi** - CSV veya .xls yerine .xlsx kullanın

Hala çözülmediyse log dosyalarını kontrol edin:
```bash
sudo tail -f /var/log/apache2/error.log
```

---

**Hazırlayan:** Claude
**Tarih:** 2026-01-12
**Versiyon:** 1.0
**Proje:** ÇELMAK Stok Takip Sistemi
