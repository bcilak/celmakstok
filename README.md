# ÇELMAK Stok Takip Sistemi

**Maliyetsiz Stok ve Üretim Yönetim Sistemi**

Bu sistem, ÇELMAK firması için geliştirilmiş bir stok takip uygulamasıdır. Maliyet/fiyat bilgisi takibi içermez, yalnızca miktar bazlı stok kontrolü yapar.

## 🚀 Özellikler

### Ürün Yönetimi
- Ürün ekleme, düzenleme, silme
- Kategorilere göre sınıflandırma
- Birim tipi desteği (Adet, Kg, Metre)
- QR kod üretimi ve okuma
- Minimum stok seviyesi belirleme

### Stok Hareketleri
- Stok girişi
- Stok çıkışı
- Depo arası transfer
- Stok düzeltme
- Üretim tüketimi

### Üretim Hatları
- Hat bazlı ürün tanımlama
- Tüketim takibi
- Kapasite yönetimi

### Depo Yönetimi
- Lokasyon tanımlama
- Bölge ve raf yönetimi
- Depo haritası görüntüleme
- Kritik stok takibi

### Sayım İşlemleri
- Envanter sayımı oturumları
- QR ile hızlı sayım
- Fark analizi
- Otomatik stok düzeltme

### Raporlama
- Stok durumu raporu
- Üretim raporu
- Hareket raporu
- Sayım raporu
- Depo raporu
- Excel dışa aktarma

## 📋 Kurulum

### Gereksinimler
- Python 3.8 veya üzeri
- pip (Python paket yöneticisi)

### Adımlar

1. **Projeyi indirin veya klonlayın:**
```bash
git clone https://github.com/celmak/stok-takip.git
cd stok-takip
```

2. **Sanal ortam oluşturun (önerilen):**
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

3. **Bağımlılıkları yükleyin:**
```bash
pip install -r requirements.txt
```

4. **Veritabanını başlatın:**
```bash
python run.py init
```

5. **Uygulamayı başlatın:**
```bash
python run.py
```

6. **Tarayıcıda açın:**
```
http://localhost:5000
```

## 🔐 Varsayılan Giriş Bilgileri

- **Kullanıcı Adı:** admin
- **Şifre:** admin123

⚠️ İlk girişten sonra şifrenizi değiştirmeniz önerilir.

## 📁 Proje Yapısı

```
celmakstok/
├── app/
│   ├── __init__.py          # Uygulama fabrikası
│   ├── models.py             # Veritabanı modelleri
│   ├── routes/               # Sayfa yönlendirmeleri
│   │   ├── main.py           # Ana sayfa
│   │   ├── auth.py           # Kimlik doğrulama
│   │   ├── products.py       # Ürün işlemleri
│   │   ├── stock.py          # Stok hareketleri
│   │   ├── production.py     # Üretim hatları
│   │   ├── warehouse.py      # Depo yönetimi
│   │   ├── counting.py       # Sayım işlemleri
│   │   ├── reports.py        # Raporlar
│   │   └── api.py            # API uç noktaları
│   ├── templates/            # HTML şablonları
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── auth/
│   │   ├── products/
│   │   ├── stock/
│   │   ├── production/
│   │   ├── warehouse/
│   │   ├── counting/
│   │   └── reports/
│   ├── static/               # Statik dosyalar
│   │   ├── css/
│   │   ├── js/
│   │   └── uploads/
│   └── utils/                # Yardımcı araçlar
│       └── qr_generator.py
├── instance/                 # Veritabanı
│   └── celmak.db
├── config.py                 # Yapılandırma
├── requirements.txt          # Bağımlılıklar
├── run.py                    # Ana başlatma dosyası
└── README.md                 # Bu dosya
```

## 🎨 Kategoriler

Sistem, Excel tablosundaki sayfa isimlerine göre varsayılan kategorilerle gelir:

- TALAŞLI İMALAT
- TAMBURLU
- MONTAJ
- LAZER
- ABKANT
- KAYNAK
- BOYA
- HAMMADDE
- SARF MALZEME
- YEDEK PARÇA

## 🔧 API Kullanımı

### Ürün Arama
```
GET /api/products/search?q=ürün_adı
```

### Ürün Bilgisi (QR ile)
```
GET /api/products/by-code/URUN001
```

### Hızlı Stok Güncelleme
```
POST /api/quick-stock
{
    "code": "URUN001",
    "quantity": 10,
    "type": "in"
}
```

## 📱 Mobil Kullanım

Sistem, Bootstrap 5 ile responsive tasarıma sahiptir. Mobil cihazlardan da rahatlıkla kullanılabilir. QR kod tarama özelliği cihazın kamerasını kullanır.

## 🛡️ Güvenlik

- Şifreler bcrypt ile hash'lenir
- Session bazlı kimlik doğrulama
- Rol tabanlı yetkilendirme (Admin/User)
- CSRF koruması

## 📊 Veritabanı

SQLite veritabanı kullanılmaktadır. Veritabanı dosyası `instance/celmak.db` konumundadır.

### Yedekleme
```bash
# Windows
copy instance\celmak.db backup\celmak_backup_%date%.db

# Linux/Mac
cp instance/celmak.db backup/celmak_backup_$(date +%Y%m%d).db
```

## 🐛 Sorun Giderme

### Veritabanı hatası
```bash
python run.py init
```

### Bağlantı problemi
- Port 5000'in kullanımda olmadığından emin olun
- Firewall ayarlarını kontrol edin

### QR kod tarama çalışmıyor
- HTTPS veya localhost gereklidir
- Kamera izni verdiğinizden emin olun

## 📞 Destek

Sorularınız için: destek@celmak.com

## 📄 Lisans

Bu yazılım ÇELMAK için özel olarak geliştirilmiştir. Tüm hakları saklıdır.

---

**Geliştirici:** ÇELMAK IT Ekibi  
**Versiyon:** 1.0.0  
**Tarih:** 2024
