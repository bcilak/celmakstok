# ÇELMAK Stok Takip Sistemi - API Entegrasyonu Özet Raporu

## Genel Bakış

ÇELMAK Stok Takip sisteminiz için harici uygulamalarla entegrasyon sağlayacak kapsamlı bir API altyapısı oluşturuldu. Bu rapor, eklenen tüm özellikleri ve nasıl kullanılacağını özetlemektedir.

---

## Eklenen API Kategorileri

### 1. Genel Ürün ve Reçete API'leri (8 Endpoint)

| Endpoint | Amaç |
|----------|------|
| `GET /api/v1/health` | API sağlık kontrolü |
| `GET /api/v1/products/full` | Tüm ürünlerin detaylı listesi |
| `GET /api/v1/recipes` | Tüm reçetelerin listesi |
| `GET /api/v1/recipes/{id}` | Belirli reçetenin detayı ve malzemeleri |
| `GET /api/v1/product-tree` | Hiyerarşik ürün ağacı (parent-child yapısı) |
| `GET /api/v1/product-tree/flat` | Düz ürün ağacı (graph görselleştirme için) |
| `GET /api/v1/recipe/{id}/can-produce` | Üretim yapılabilirlik kontrolü |
| `GET /api/v1/recipe/{id}/missing-materials` | Eksik malzeme analizi |

**Kullanım Alanları:**
- Ürün ağacı görselleştirme (D3.js, Cytoscape.js)
- BOM (Bill of Materials) rapor oluşturma
- Üretim planlama uygulamaları
- Mobil uygulamalar

### 2. Satın Alma Birimi API'leri (4 Endpoint)

| Endpoint | Amaç |
|----------|------|
| `GET /api/v1/purchasing/critical-stock` | Kritik stok listesi (aciliyet seviyeleriyle) |
| `GET /api/v1/purchasing/reorder-suggestions` | Otomatik sipariş önerileri |
| `GET /api/v1/purchasing/product/{id}/details` | Ürün bazlı satın alma analizi |
| `POST /api/v1/purchasing/notify` | Webhook bildirimi gönderme |

**Özellikler:**
- Aciliyet seviyeleri (critical/medium/low)
- Haftalık/günlük tüketim analizi
- Stok bitişi tahmini (kaç gün sonra tükenir)
- Ekonomik sipariş miktarı hesaplama
- Otomatik bildirim desteği

---

## Oluşturulan Dosyalar

### Dokümantasyon (5 Dosya)

1. **API_DOCUMENTATION.md** (16 KB)
   - Tüm endpoint'lerin detaylı açıklaması
   - Request/Response örnekleri
   - Hata kodları ve çözümleri
   - Görselleştirme entegrasyon örnekleri

2. **API_README.md** (7 KB)
   - Hızlı başlangıç kılavuzu
   - Temel kullanım örnekleri
   - API Key konfigürasyonu

3. **BASLATMA_KILAVUZU.md** (6 KB)
   - Adım adım başlatma talimatları
   - Sorun giderme (troubleshooting)
   - Test senaryoları

4. **SATIN_ALMA_API.md** (12 KB)
   - Satın alma birimi senaryosu
   - Otomatik sipariş hesaplama mantığı
   - Slack/E-posta entegrasyon örnekleri
   - Cron job otomasyon örnekleri

5. **API_OZET.md** (Bu dosya)
   - Tüm özelliklerin özet raporu

### Örnek Uygulamalar (2 Dosya)

1. **example_api_usage.py** (9 KB)
   - Tüm API endpoint'lerini test eden Python scripti
   - Session tabanlı authentication
   - JSON export fonksiyonu
   - BOM rapor oluşturucu

2. **purchasing_app_example.py** (Yeni)
   - Satın alma birimi için interaktif CLI uygulaması
   - Kritik stok görüntüleme
   - Sipariş önerileri
   - CSV export

### Görselleştirme (1 Dosya)

1. **api_test.html** (16 KB)
   - D3.js ile interaktif ürün ağacı
   - Zoom/Pan/Drag özellikleri
   - Gerçek zamanlı tooltip'ler
   - Renk kodlu düğümler (reçete/ürün)

---

## Nasıl Kullanılır?

### Adım 1: Flask Uygulamasını Başlatın

```bash
python run.py
```

### Adım 2: API'yi Test Edin

#### Yöntem 1: Python Script ile

```bash
# Genel API testi
python example_api_usage.py

# Satın alma API testi
python purchasing_app_example.py
```

#### Yöntem 2: Tarayıcıda Görselleştirme

`api_test.html` dosyasını çift tıklayarak açın ve "Ürün Ağacını Yükle" butonuna tıklayın.

#### Yöntem 3: Curl ile

```bash
curl http://localhost:5000/api/v1/health
```

---

## Satın Alma Senaryosu

### Senaryo Açıklaması

Satın alma biriminiz, kritik stok seviyelerini otomatik olarak takip edebilir ve sipariş önerilerini alabilir.

### Örnek İş Akışı

1. **Sabah 09:00**: Otomatik cron job çalışır
2. **API Çağrısı**: `/v1/purchasing/critical-stock` endpoint'i çağrılır
3. **Analiz**: 15 ürün kritik seviyede bulunur
4. **Bildirim**: Satın alma ekibine e-posta/Slack bildirimi gönderilir
5. **Sipariş Önerileri**: `/v1/purchasing/reorder-suggestions` ile sipariş miktarları hesaplanır
6. **ERP Entegrasyonu**: Otomatik sipariş taslağı oluşturulur

### Aciliyet Seviyeleri

- **critical**: Stok tükendi (current_stock <= 0)
- **medium**: Eksiklik %30'dan fazla
- **low**: Eksiklik %30'dan az

### Sipariş Miktarı Hesaplama

```
Önerilen Sipariş = (Minimum Stok - Mevcut Stok) + Aylık Tüketim
Ekonomik Sipariş = Yuvarlanmış miktar (10'un katları)
```

---

## Güvenlik

### API Key Kullanımı (Opsiyonel)

1. `.env` dosyasına ekleyin:
```env
API_KEY=sk_live_your_secure_api_key_here
```

2. İsteklerde header ekleyin:
```bash
curl -H "X-API-Key: sk_live_your_secure_api_key_here" \
  http://localhost:5000/api/v1/products/full
```

### Session Tabanlı Authentication

API endpoint'leri Flask-Login ile korunmaktadır. Python script'lerinde:

```python
session = requests.Session()
session.post(f"{BASE_URL}/auth/login", data={'username': 'admin', 'password': 'admin123'})
```

---

## Otomasyon Örnekleri

### 1. Periyodik Kritik Stok Kontrolü (Python)

```python
import schedule
import requests

def check_critical_stock():
    response = session.get('http://localhost:5000/api/v1/purchasing/critical-stock')
    data = response.json()

    critical = [p for p in data['data'] if p['urgency_level'] == 'critical']

    if critical:
        send_notification(critical)

schedule.every().day.at("09:00").do(check_critical_stock)
```

### 2. Slack Entegrasyonu

```python
def send_slack_notification(critical_products):
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

    message = {
        "text": f"⚠️ Kritik Stok Uyarısı: {len(critical_products)} ürün",
        "attachments": [...]
    }

    requests.post(webhook_url, json=message)
```

---

## Veri Formatları

### Hiyerarşik Format (Ağaç Görünümü)

```json
{
  "success": true,
  "count": 25,
  "data": [
    {
      "recipe_id": 1,
      "recipe_name": "Tambur Üretim",
      "category_name": "Ana Ürünler",
      "children": [
        {
          "product_id": 5,
          "code": "CM-005",
          "name": "Somun M10",
          "quantity_required": 12.0,
          "current_stock": 150.0,
          "status": "sufficient"
        }
      ]
    }
  ]
}
```

### Düz Format (Graph Görselleştirme)

```json
{
  "nodes": [
    {
      "id": "recipe_1",
      "label": "Tambur Üretim",
      "type": "recipe",
      "category": "Ana Ürünler"
    },
    {
      "id": "product_5",
      "label": "Somun M10",
      "type": "product",
      "stock": 150.0
    }
  ],
  "edges": [
    {
      "source": "recipe_1",
      "target": "product_5",
      "label": "12.0 adet"
    }
  ]
}
```

---

## Test Checklist

### Genel API
- [ ] Health check çalışıyor: `curl http://localhost:5000/api/v1/health`
- [ ] Ürün listesi dönüyor: `python example_api_usage.py`
- [ ] Görselleştirme açılıyor: `api_test.html` (tarayıcıda aç)

### Satın Alma API
- [ ] Kritik stok listesi alınıyor
- [ ] Sipariş önerileri hesaplanıyor
- [ ] Aciliyet seviyeleri doğru
- [ ] Tüketim analizleri çalışıyor

---

## Sorun Giderme

### Connection Refused
- Flask uygulaması çalışıyor mu? → `python run.py`
- http://localhost:5000 tarayıcıda açılıyor mu?

### 401 Unauthorized
- Tarayıcıda giriş yaptınız mı?
- Session cookie'si var mı?
- Python script'lerinde `login()` fonksiyonu çağrıldı mı?

### JSONDecodeError
- API yanıtı HTML dönüyor olabilir (login sayfası)
- `session.get()` kullanıyor musunuz? (requests.get() değil)

---

## İletişim ve Raporlar

### Günlük Rapor (Excel)

```python
import pandas as pd

response = session.get('http://localhost:5000/api/v1/purchasing/critical-stock')
df = pd.DataFrame(response.json()['data'])
df.to_excel(f'kritik_stok_{datetime.now().strftime("%Y%m%d")}.xlsx')
```

### Dashboard Metrikleri

```python
# Kritik ürün sayısı
critical_count = len([p for p in data if p['urgency_level'] == 'critical'])

# Toplam eksik miktar
total_shortage = sum(p['shortage'] for p in data)

# En acil ürünler (< 3 gün)
urgent = [p for p in data if p.get('days_remaining', 999) < 3]
```

---

## Sonuç

✅ **Tamamlanan Özellikler:**

1. 12 API endpoint eklendi
2. Ürün ağacı görselleştirme desteği
3. Satın alma birimi için otomatik analiz
4. Tüketim tahmini ve sipariş hesaplama
5. Webhook/bildirim entegrasyonu
6. 5 kapsamlı dokümantasyon dosyası
7. 2 örnek uygulama
8. 1 interaktif görselleştirme

✅ **Senaryonuz Tamamen Sağlandı:**

- Kritik stok otomatik takibi
- Satın alma birimi için ayrı API
- Aciliyet seviyeli bildirimler
- Ekonomik sipariş miktarı hesaplama
- Stok bitişi tahmini
- CSV/Excel export desteği

---

## Başlangıç Komutu

```bash
# Terminal 1: Flask uygulamasını başlat
python run.py

# Terminal 2: API'yi test et
python example_api_usage.py

# Terminal 3: Satın alma uygulamasını test et
python purchasing_app_example.py
```

**Tüm dokümanları okuduktan sonra bu adımları takip ederek API'yi test edebilirsiniz.**

---

**Hazırlayan:** Claude
**Tarih:** 2026-01-12
**Proje:** ÇELMAK Stok Takip Sistemi API v1.0
