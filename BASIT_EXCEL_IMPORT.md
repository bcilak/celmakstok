# Basitleştirilmiş Excel Import - Kullanım Kılavuzu

## 🎯 Özellik

Web üzerinden kategori seçimi ile **kolay ve hızlı** toplu ürün aktarımı.

### Farkı Nedir?

**Eski Yöntem:**
- Excel'de Kategori ID yazmak zorunluydu
- Kategori ID'leri ezberlemeniz gerekiyordu
- Hata riski yüksekti

**Yeni Yöntem (Bu):**
- ✅ Excel'de sadece ürün bilgileri
- ✅ Kategoriler web'de dropdown'dan seçilir
- ✅ Önizleme ile kontrol
- ✅ Onayladıktan sonra kayıt

---

## 📖 Kullanım Adımları

### Adım 1: Excel'den Aktar Sayfasına Gidin

Sol menüden: **Excel'den Aktar** (Sadece Admin ve Yönetici görür)

Veya URL: `https://celmak.altikodtech.com.tr/products/import/simple`

---

### Adım 2: Basit Şablonu İndirin

"Şablon İndir" butonuna tıklayın.

**İndirilen dosya:** `urun_import_sablonu_basit_YYYYMMDD.xlsx`

#### Şablon İçeriği:

| Ürün Kodu* | Ürün Adı* | Birim Tipi | Mevcut Stok | Minimum Stok | Barkod | Notlar |
|------------|-----------|------------|-------------|--------------|--------|--------|
| HM-001 | Çelik Levha 2mm | m2 | 50 | 10 | | Hammadde |
| HM-002 | Paslanmaz Boru | metre | 120 | 20 | 5901234123457 | |
| BE-100 | Somun M8 | adet | 500 | 100 | | Bağlantı |

**DİKKAT:** Kategori ID sütunu YOK! Kategorileri bir sonraki adımda seçeceksiniz.

---

### Adım 3: Excel'i Doldurun

Excel'de örnek satırları silin veya üzerine yazın:

```
Ürün Kodu*    Ürün Adı*          Birim Tipi  Mevcut Stok  Minimum Stok  Barkod         Notlar
CM-001        Hidrolik Silindir  adet        15           3
CM-002        Vida M8x20         adet        800          150
CM-003        Kesme Yağı         litre       25           5             5901234567890  Yeşil teneke
HM-050        Alüminyum Profil   metre       60           10                           20x40mm
```

**Zorunlu Alanlar:**
- ✅ Ürün Kodu
- ✅ Ürün Adı

**Opsiyonel Alanlar:**
- Birim Tipi (varsayılan: "adet")
- Mevcut Stok (varsayılan: 0)
- Minimum Stok (varsayılan: 0)
- Barkod
- Notlar

---

### Adım 4: Excel'i Yükleyin

1. Doldurduğunuz Excel'i kaydedin
2. "Excel Dosyası Seçin" alanına tıklayın
3. Dosyanızı seçin (.xlsx veya .xls)
4. "Yükle ve Önizle" butonuna tıklayın

**Sistem Kontrolü:**
- ✅ Dosya boyutu max 10MB
- ✅ Format .xlsx veya .xls
- ✅ Ürün Kodu ve Ürün Adı dolu mu
- ✅ Sayısal alanlar sayı mı

---

### Adım 5: Önizleme ve Kategori Seçimi

Excel yüklendikten sonra **önizleme sayfası** açılır.

#### Özet Kartlar:
```
┌─────────────────┬─────────────────┬─────────────────┐
│ 📋 Toplam Ürün  │ ➕ Yeni Eklene  │ 🔄 Güncellenecek│
│      15         │      12         │       3         │
└─────────────────┴─────────────────┴─────────────────┘
```

#### Ürün Tablosu:

Her satırda:
- **Durum Badge:**
  - 🟢 Yeni - Sistemde yok, yeni eklenecek
  - 🟡 Güncelleme - Ürün kodu mevcut, güncellenecek
- **Ürün Bilgileri:** Kod, ad, birim, stok bilgileri
- **Kategori Dropdown:** 🔴 ZORUNLU - Her ürün için seçilmeli

**Örnek Tablo:**
```
# | Durum      | Kod    | Adı               | Kategori Seçin ▼      | Birim | Stok
1 | 🟢 Yeni    | CM-001 | Hidrolik Silindir | [Ana Ürünler      ▼] | adet  | 15
2 | 🟡 Güncelleme | CM-002 | Vida M8x20    | [Bağlantı Elem.   ▼] | adet  | 800
3 | 🟢 Yeni    | CM-003 | Kesme Yağı        | [Kimyasallar      ▼] | litre | 25
```

**Güncelleme Satırları (Sarı):**
- Mevcut kategori gösterilir: "Mevcut: Bağlantı Elemanları"
- Mevcut stoklar gösterilir
- İsterseniz kategoriyi değiştirebilirsiniz

---

### Adım 6: Kategorileri Seçin

**Her ürün için dropdown'dan kategori seçin:**

1. Dropdown'a tıklayın
2. Listeden doğru kategoriyi seçin
3. Hepsi için tekrarlayın

**Hızlı Seçim İpucu:**
- Aynı kategorideki ürünleri Excel'de yanyana yazın
- Önizlemede hepsini aynı kategori seçebilirsiniz

---

### Adım 7: Onaylayın ve Kaydedin

1. Tüm kategorileri seçtiğinizden emin olun
2. Alttaki onay kutusunu işaretleyin:
   - ☑️ "Yukarıdaki bilgileri kontrol ettim ve kategorileri seçtim. İşlemi onaylıyorum."
3. "Onayla ve Kaydet" butonuna tıklayın

**Sistem Kontrolü:**
- ✅ Tüm kategoriler seçili mi?
- ✅ Onay kutusu işaretli mi?
- ⛔ Eksiklik varsa uyarı verir

**Başarılı İşlem:**
```
✓ 12 ürün eklendi
✓ 3 ürün güncellendi
Toplam 15 ürün işleme alındı.
```

Otomatik olarak ürünler sayfasına yönlendirilirsiniz.

---

## 🔄 Güncelleme Mantığı

### Yeni Ürün (Yeşil Badge):
- Ürün kodu sistemde **YOK**
- Yeni kayıt oluşturulur
- Seçtiğiniz kategori atanır
- Excel'deki stok bilgileri kaydedilir

### Güncelleme (Sarı Badge):
- Ürün kodu sistemde **VAR**
- Mevcut kayıt güncellenir
- Şu bilgiler güncellenir:
  - Ürün Adı
  - Kategori (değiştirdiyseniz)
  - Birim Tipi
  - Mevcut Stok
  - Minimum Stok
  - Barkod
  - Notlar
- Stok hareketleri **korunur**
- QR kod **değişmez**

---

## 💡 Kullanım Senaryoları

### Senaryo 1: İlk Kurulum (Sıfırdan 100 Ürün)

```
1. Şablonu indirin
2. Excel'de 100 ürünü doldurun (kategori yazmayın!)
3. Yükleyin
4. Önizlemede hepsi yeşil (yeni) görünür
5. Her ürün için kategori seçin (dropdown)
6. Onayla → ✓ 100 ürün eklendi
```

**Zaman:** ~10 dakika (Excel doldurma hariç)

---

### Senaryo 2: ERP'den Veri Aktarma

```
1. ERP'den ürün listesini Excel'e aktarın
2. Sütun isimlerini şablona uygun yapın:
   - "Stok Kodu" → "Ürün Kodu*"
   - "Stok Adı" → "Ürün Adı*"
   - "Birim" → "Birim Tipi"
3. Kategori sütununu SİLİN (gerek yok)
4. Yükleyin
5. Web'de kategorileri seçin
6. Kaydedin
```

---

### Senaryo 3: Tedarikçi Listesi Ekleme

```
1. Tedarikçiden ürün listesi (Excel/PDF) alın
2. Copy-paste ile şablona yapıştırın
3. Ürün kodlarını düzenleyin (örn: TD-001, TD-002...)
4. Yükleyin
5. Önizlemede hepsi yeni görünür
6. Tüm ürünlere aynı kategori: "Tedarikçi - ABC Firma"
7. Kaydedin
```

---

### Senaryo 4: Toplu Kategori Değiştirme

```
1. Mevcut ürünleri "Excel'e Aktar" (ürünler sayfasından)
2. İndirilen Excel'de sadece değiştirmek istediklerinizi bırakın
3. Kategori sütununu SİLİN
4. Yükleyin
5. Önizlemede hepsi sarı (güncelleme) görünür
6. Yeni kategorileri dropdown'dan seçin
7. Kaydedin → Kategoriler güncellenir
```

---

## 🐛 Yaygın Hatalar ve Çözümleri

### Hata 1: "Lütfen bir Excel dosyası seçin"
**Sebep:** Dosya seçmediniz.

**Çözüm:** "Excel Dosyası Seçin" butonuna tıklayıp dosya seçin.

---

### Hata 2: "Dosya boyutu 10MB'dan büyük"
**Sebep:** Excel dosyası çok büyük.

**Çözüm:**
1. Ürünleri 200'lük gruplara bölün
2. Ayrı ayrı yükleyin
3. Veya gereksiz sütunları silin

---

### Hata 3: "Sadece Excel dosyaları (.xlsx veya .xls) yükleyebilirsiniz"
**Sebep:** CSV veya başka format yüklemeye çalıştınız.

**Çözüm:**
1. CSV ise Excel'de açın
2. "Farklı Kaydet" → .xlsx
3. Tekrar yükleyin

---

### Hata 4: "X ürün için kategori seçilmedi"
**Sebep:** Önizlemede bazı ürünlerin kategorisi boş.

**Çözüm:**
1. Sayfayı aşağı kaydırın
2. Kırmızı kenarlı dropdown'ları bulun
3. Her biri için kategori seçin
4. Tekrar "Onayla ve Kaydet"

---

### Hata 5: "Satır X: Ürün kodu boş"
**Sebep:** Excel'de bazı satırların Ürün Kodu kolonu boş.

**Çözüm:**
1. Excel'i açın
2. Boş satırları doldurun veya silin
3. Tekrar yükleyin

---

## 📊 Performans ve Limitler

| Ürün Sayısı | Yükleme | Önizleme | Kayıt | Toplam |
|-------------|---------|----------|-------|--------|
| 1-50        | ~2 sn   | Anında   | ~3 sn | ~5 sn  |
| 51-100      | ~3 sn   | Anında   | ~6 sn | ~9 sn  |
| 101-200     | ~5 sn   | Anında   | ~12 sn| ~17 sn |
| 201-500     | ~10 sn  | ~2 sn    | ~30 sn| ~42 sn |

**Tavsiye:**
- ✅ İdeal: 50-100 ürün/işlem
- ⚠️ 200+ ürün: Sayfalara bölün

---

## 🔐 Güvenlik ve Yetki

**Kim Kullanabilir:**
- ✅ Admin
- ✅ Yönetici

**Kim Kullanamaz:**
- ❌ Kullanıcı
- ❌ Depo Personeli

**Session Güvenliği:**
- Yüklenen veriler session'da tutulur
- Sadece o kullanıcı görebilir
- Çıkış yapınca silinir
- Max 1 saat geçerli

---

## ✅ İyi Uygulamalar

### 1. Excel Hazırlık

```
✅ DOĞRU:
- Her ürün için kod ve ad dolu
- Sayısal alanlar sayı (0 da olabilir)
- Barkod metin olarak ('1234567890)
- Örnek satırlar silindi

❌ YANLIŞ:
- Ürün kodu boş
- Stok: "yok" (sayı değil)
- Barkod: 00012345 (sıfırlar kaybolur)
- Örnek satırlar kaldı (ORN- ile başlayanlar)
```

---

### 2. Kategori Seçimi

```
✅ İPUÇLARI:
- Aynı kategorideki ürünleri Excel'de grupla
- Önizlemede hızlıca aynı kategoriyi seç
- Güncelleme satırlarında mevcut kategori gösterilir
- Emin değilseniz kategorileri önceden not alın
```

---

### 3. Güncelleme Yaparken

```
✅ DİKKAT:
- Güncelleme satırları SARI görünür
- Mevcut stok bilgileri gösterilir
- Kategoriyi değiştirirseniz güncellenir
- Stok hareketleri kaybolmaz
```

---

### 4. Test ve Doğrulama

```
1. İlk kez kullanıyorsanız 5 ürünle test edin
2. Önizlemede kontrol edin
3. Başarılı olunca gerçek listeyi yükleyin
```

---

## 🆚 Eski vs Yeni Import Karşılaştırması

| Özellik | Eski Yöntem | Yeni Yöntem (Bu) |
|---------|-------------|------------------|
| Kategori ID | Excel'de yazılmalı | Web'de seçilir |
| Zorluk | Orta-Zor | Kolay |
| Hata Riski | Yüksek (yanlış ID) | Düşük (dropdown) |
| Önizleme | Yok | Var |
| Güncelleme Görünümü | Yok | Var (sarı badge) |
| Onay Adımı | Yok (direkt kaydeder) | Var |
| Kategori ID Ezberleme | Gerekli | Gereksiz |
| Kullanıcı Dostu | ⭐⭐ | ⭐⭐⭐⭐⭐ |

**Sonuç:** Yeni yöntem çok daha kullanıcı dostu!

---

## 🚀 Gelişmiş Özellikler

### Toplu Kategori Atama (Gelecek Sürüm)

Planlanan özellikler:
- [ ] "Tüm görünenlere aynı kategori" butonu
- [ ] Kategori önerisi (ürün adına göre AI tahmini)
- [ ] Son kullanılan kategoriler
- [ ] Favori kategoriler

### Excel İçe/Dışa Aktarma İyileştirmeleri

- [ ] CSV desteği
- [ ] Şablon özelleştirme (web'de)
- [ ] Excel'e fotoğraf URL ekleme
- [ ] Validation önizleme

---

## 📞 Sık Sorulan Sorular

### S1: Kategorileri sonradan değiştirebilir miyim?
**C:** Evet, ürün düzenleme sayfasından her zaman değiştirebilirsiniz.

### S2: Aynı ürün kodunu tekrar yüklersem ne olur?
**C:** Güncelleme olarak işlem görür (sarı badge). Mevcut ürün güncellenir, yeni ürün eklenmez.

### S3: Excel'de kategori sütunu var, sorun olur mu?
**C:** Hayır, sistem sadece tanıdığı sütunları okur. Fazla sütunlar görmezden gelinir.

### S4: Önizlemeden çıkarsam veriler kaybolur mu?
**C:** Evet, session temizlenir. Tekrar yüklemeniz gerekir. O yüzden önizlemede onaylamadan çıkmayın.

### S5: Binlerce ürünü tek seferde yükleyebilir miyim?
**C:** Teknik olarak evet ama tavsiye etmiyoruz. 200'lük paketler halinde yükleyin.

---

## 🎓 Video Eğitim (Yakında)

Planlanan video içerikler:
1. Basit Excel Import - Temel Kullanım (5 dk)
2. Toplu Ürün Ekleme - İlk Kurulum (10 dk)
3. ERP'den Veri Aktarma (15 dk)
4. Kategori Yönetimi ve Güncelleme (8 dk)

---

## 📝 Özet Checklist

**Excel Hazırlık:**
- [ ] Şablonu indirdim
- [ ] Ürün Kodu ve Ürün Adı doldurdum
- [ ] Örnek satırları sildim
- [ ] Dosyayı kaydettim (.xlsx)

**Yükleme:**
- [ ] Excel'i seçtim
- [ ] "Yükle ve Önizle" tıkladım
- [ ] Hata yoksa önizleme açıldı

**Önizleme:**
- [ ] Özet kartları kontrol ettim
- [ ] Yeni/Güncelleme sayılarını gördüm
- [ ] Her ürün için kategori seçtim
- [ ] Onay kutusunu işaretledim

**Kayıt:**
- [ ] "Onayla ve Kaydet" tıkladım
- [ ] Başarı mesajı gördüm
- [ ] Ürünler sayfasına yönlendirildim
- [ ] Ürünleri kontrol ettim

---

**Hazırlayan:** Claude
**Tarih:** 2026-01-12
**Versiyon:** 1.0 (Basitleştirilmiş)
**Proje:** ÇELMAK Stok Takip Sistemi

---

## 🔗 İlgili Dokümantasyon

- [Excel Import (Detaylı)](EXCEL_IMPORT_KULLANIM.md) - Eski yöntem
- [Toplu QR Yazdırma](TOPLU_QR_KULLANIM.md)
- [API Kullanımı](API_OZET.md)
