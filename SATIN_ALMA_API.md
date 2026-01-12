# Satın Alma Birimi API Dokümantasyonu

## 🎯 Senaryo

Satın alma birimi, ÇELMAK Stok Takip sistemindeki kritik stok seviyelerini takip eder ve otomatik sipariş önerileri alır.

---

## 📡 Yeni Eklenen Endpoint'ler

### 1. Kritik Stok Listesi

#### `GET /api/v1/purchasing/critical-stock`

Minimum stok seviyesinin altındaki tüm ürünleri listeler.

**Özellikler:**
- ✅ Aciliyet seviyesi (critical/medium/low)
- ✅ Haftalık tüketim analizi
- ✅ Stok bitişi tahmini (kaç gün sonra tükenir)
- ✅ Eksik miktar hesaplaması

**Request:**
```bash
curl http://localhost:5000/api/v1/purchasing/critical-stock \
  -H "Cookie: session=..."
```

**Response:**
```json
{
  "success": true,
  "count": 15,
  "data": [
    {
      "product_id": 5,
      "code": "CM-005",
      "name": "Somun M10",
      "category_name": "Bağlantı Elemanları",
      "current_stock": 20.0,
      "minimum_stock": 50.0,
      "shortage": 30.0,
      "unit_type": "adet",
      "barcode": "123456",
      "urgency_level": "medium",
      "weekly_consumption": 45.0,
      "daily_avg_consumption": 6.43,
      "days_remaining": 3,
      "notes": null
    }
  ],
  "generated_at": "2026-01-12T15:30:00"
}
```

**Aciliyet Seviyeleri:**
- `critical`: Stok tükendi (current_stock <= 0)
- `medium`: Eksik miktar > %30
- `low`: Eksik miktar < %30

---

### 2. Sipariş Önerileri

#### `GET /api/v1/purchasing/reorder-suggestions`

Hangi üründen ne kadar sipariş verilmesi gerektiğini önerir.

**Hesaplama Mantığı:**
```
Önerilen Sipariş = (Minimum Stok - Mevcut Stok) + Aylık Tüketim (Güvenlik Stoğu)
Ekonomik Sipariş = Yuvarlanmış miktar (10'un katları)
```

**Request:**
```bash
curl http://localhost:5000/api/v1/purchasing/reorder-suggestions
```

**Response:**
```json
{
  "success": true,
  "count": 12,
  "data": [
    {
      "product_id": 5,
      "code": "CM-005",
      "name": "Somun M10",
      "category_name": "Bağlantı Elemanları",
      "current_stock": 20.0,
      "minimum_stock": 50.0,
      "shortage": 30.0,
      "monthly_consumption": 180.0,
      "suggested_order_quantity": 210.0,
      "economic_order_quantity": 220.0,
      "unit_type": "adet",
      "priority": "high"
    }
  ],
  "generated_at": "2026-01-12T15:30:00"
}
```

**Öncelik Seviyeleri:**
- `high`: Stok tükendi
- `medium`: Stok < Minimum Stok * 0.5
- `low`: Diğer durumlar

---

### 3. Ürün Satın Alma Detayı

#### `GET /api/v1/purchasing/product/{product_id}/details`

Belirli bir ürün için detaylı satın alma analizi.

**Özellikler:**
- Son 30 günlük tüketim analizi
- Günlük ortalama tüketim
- Stok bitişi tahmini
- Son alım bilgileri
- Son hareketler

**Request:**
```bash
curl http://localhost:5000/api/v1/purchasing/product/5/details
```

**Response:**
```json
{
  "success": true,
  "data": {
    "product": {
      "id": 5,
      "code": "CM-005",
      "name": "Somun M10",
      "category": "Bağlantı Elemanları",
      "current_stock": 20.0,
      "minimum_stock": 50.0,
      "unit_type": "adet",
      "barcode": "123456",
      "status": "critical"
    },
    "consumption_analysis": {
      "last_30_days_in": 100.0,
      "last_30_days_out": 180.0,
      "daily_avg_consumption": 6.0,
      "days_until_stockout": 3
    },
    "purchasing_info": {
      "shortage": 30.0,
      "suggested_order": 210.0,
      "last_purchase_date": "2026-01-05T10:00:00",
      "last_purchase_quantity": 100.0,
      "last_purchase_source": "ABC Tedarik Ltd."
    },
    "recent_movements": [
      {
        "date": "2026-01-12T14:00:00",
        "type": "cikis",
        "quantity": 12.0,
        "source": "DEPO",
        "destination": "Tambur Hattı"
      }
    ]
  }
}
```

---

### 4. Bildirim Oluştur (Webhook)

#### `POST /api/v1/purchasing/notify`

Kritik stok bildirimi gönderir (webhook desteği).

**Request:**
```bash
curl -X POST http://localhost:5000/api/v1/purchasing/notify \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "https://your-app.com/webhook"}'
```

**Response:**
```json
{
  "success": true,
  "message": "Bildirim gönderildi",
  "critical_product_count": 15,
  "timestamp": "2026-01-12T15:30:00"
}
```

---

## 🚀 Kullanım Örnekleri

### Senaryo 1: Günlük Kritik Stok Kontrolü

```python
import requests

session = requests.Session()
# Login...

# Kritik stokları al
response = session.get('http://localhost:5000/api/v1/purchasing/critical-stock')
data = response.json()

# Sadece ACİL olanları filtrele
critical = [p for p in data['data'] if p['urgency_level'] == 'critical']

for product in critical:
    print(f"⚠️ ACİL: {product['name']} - Stok tükendi!")
    print(f"   Minimum: {product['minimum_stock']} {product['unit_type']}")
```

### Senaryo 2: Otomatik Sipariş Listesi Oluştur

```python
# Sipariş önerilerini al
response = session.get('http://localhost:5000/api/v1/purchasing/reorder-suggestions')
data = response.json()

# Yüksek öncelikli siparişler
high_priority = [p for p in data['data'] if p['priority'] == 'high']

# Excel'e export veya ERP sistemine gönder
for product in high_priority:
    print(f"SİPARİŞ: {product['code']} - {product['economic_order_quantity']} {product['unit_type']}")
```

### Senaryo 3: Periyodik Webhook Bildirimi

```python
import schedule
import time

def check_critical_stock():
    response = session.post(
        'http://localhost:5000/api/v1/purchasing/notify',
        json={'webhook_url': 'https://your-slack-webhook.com'}
    )
    print(f"Bildirim gönderildi: {response.json()['critical_product_count']} kritik ürün")

# Her gün saat 09:00'da kontrol et
schedule.every().day.at("09:00").do(check_critical_stock)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## 💻 Tam Entegre Örnek: Satın Alma Uygulaması

`purchasing_app_example.py` dosyasını çalıştırın:

```bash
python purchasing_app_example.py
```

**Özellikler:**
- İnteraktif menü sistemi
- Kritik stok listesi görüntüleme
- Sipariş önerileri
- Ürün detay analizi
- CSV export

---

## 📊 Veri Akışı

```
ÇELMAK Stok Sistemi
        ↓
   API Endpoint
        ↓
Satın Alma Uygulaması
        ↓
Otomatik Sipariş/Bildirim
```

### Örnek Entegrasyon Senaryosu:

1. **Sabah 09:00**: Otomatik cron job çalışır
2. **API Çağrısı**: `/v1/purchasing/critical-stock`
3. **Kritik Ürün Tespiti**: 15 ürün kritik seviyede
4. **E-posta/Slack Bildirimi**: Satın alma ekibine bildirim
5. **Sipariş Önerileri**: `/v1/purchasing/reorder-suggestions`
6. **ERP Entegrasyonu**: Otomatik sipariş taslağı oluştur

---

## 🔐 Güvenlik

### API Key Kullanımı (Önerilir)

`.env` dosyasına ekleyin:
```env
API_KEY=sk_purchasing_secure_key_12345
```

İsteklerde header ekleyin:
```bash
curl -H "X-API-Key: sk_purchasing_secure_key_12345" \
  http://localhost:5000/api/v1/purchasing/critical-stock
```

---

## 📈 İzleme ve Raporlama

### Günlük Rapor

```python
import pandas as pd

# API'den veri al
response = session.get('http://localhost:5000/api/v1/purchasing/critical-stock')
data = response.json()['data']

# DataFrame'e çevir
df = pd.DataFrame(data)

# Excel'e aktar
df.to_excel(f'kritik_stok_raporu_{datetime.now().strftime("%Y%m%d")}.xlsx', index=False)
```

### Dashboard İçin Metrikler

```python
# Kritik ürün sayısı
critical_count = len([p for p in data if p['urgency_level'] == 'critical'])

# Toplam eksik miktar (parasal değer hesaplanabilir)
total_shortage = sum(p['shortage'] for p in data)

# En acil ürünler (stok bitişi < 3 gün)
urgent = [p for p in data if p['days_remaining'] and p['days_remaining'] < 3]
```

---

## 🔄 Otomatizasyon Örnekleri

### 1. Slack Entegrasyonu

```python
import requests

def send_slack_notification(critical_products):
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

    message = {
        "text": f"⚠️ Kritik Stok Uyarısı: {len(critical_products)} ürün",
        "attachments": [
            {
                "color": "danger",
                "fields": [
                    {
                        "title": p['name'],
                        "value": f"Stok: {p['current_stock']} / Min: {p['minimum_stock']}",
                        "short": False
                    }
                    for p in critical_products[:5]
                ]
            }
        ]
    }

    requests.post(webhook_url, json=message)
```

### 2. E-posta Bildirimi

```python
import smtplib
from email.mime.text import MIMEText

def send_email_alert(critical_products):
    msg = MIMEText(f"Kritik stok uyarısı: {len(critical_products)} ürün")
    msg['Subject'] = '🚨 ÇELMAK - Kritik Stok Uyarısı'
    msg['From'] = 'stok@celmak.com'
    msg['To'] = 'satinalma@celmak.com'

    # SMTP gönder
    # ...
```

---

## ✅ Test Checklist

- [ ] Kritik stok listesi çalışıyor mu?
- [ ] Sipariş önerileri doğru hesaplanıyor mu?
- [ ] Ürün detay analizi bilgileri tam mı?
- [ ] Tüketim analizleri doğru mu?
- [ ] CSV export çalışıyor mu?
- [ ] Webhook bildirimleri gidiyor mu?

---

## 🎯 Sonuç

Evet, senaryonuz **tamamen sağlanıyor**!

✅ Kritik stok takibi
✅ Otomatik sipariş önerileri
✅ Tüketim analizi
✅ Stok bitişi tahmini
✅ Webhook/bildirim desteği
✅ CSV/Excel export

Satın alma uygulamanız bu API'leri kullanarak:
1. Günlük otomatik kontrol yapabilir
2. Kritik ürünleri listeleyebilir
3. Sipariş miktarlarını hesaplayabilir
4. Ekibinize bildirim gönderebilir

**Başlamak için:**
```bash
python purchasing_app_example.py
```
