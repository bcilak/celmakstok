# ÇELMAK Stok Takip Sistemi - API Dokümantasyonu

## Genel Bilgi

**Base URL:** `http://your-domain.com/api`
**Authentication:** Flask-Login Session veya API Key (opsiyonel)
**Response Format:** JSON
**API Version:** v1

---

## Authentication

### Yöntem 1: Session-based (Flask-Login)
Tarayıcı üzerinden giriş yapıldıktan sonra session cookie ile erişim.

### Yöntem 2: API Key (Opsiyonel)
```bash
X-API-Key: your-api-key-here
```

`.env` dosyasına ekleyin:
```
API_KEY=your-secure-api-key-here
```

---

## Endpoint'ler

### 1. Sağlık Kontrolü

#### `GET /api/v1/health`

API'nin çalışır durumda olup olmadığını kontrol eder. Authentication gerektirmez.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0",
  "service": "ÇELMAK Stok Takip API"
}
```

---

### 2. Ürün Listesi (Tam Detay)

#### `GET /api/v1/products/full`

Tüm ürünleri detaylı bilgileriyle döndürür.

**Query Parameters:**
- `category_id` (optional): Kategori ID ile filtrele
- `include_inactive` (optional): Pasif ürünleri dahil et (true/false, varsayılan: false)

**Request:**
```bash
curl -X GET "http://localhost:5000/api/v1/products/full?category_id=1" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "success": true,
  "count": 150,
  "data": [
    {
      "id": 1,
      "code": "CM-001",
      "name": "Hidrolik Silindir",
      "category_id": 1,
      "category_name": "Hidrolik",
      "unit_type": "adet",
      "current_stock": 45.0,
      "minimum_stock": 10.0,
      "barcode": "1234567890",
      "notes": "Ana ürün",
      "status": "normal",
      "is_active": true,
      "created_at": "2024-01-01T10:00:00",
      "updated_at": "2024-01-15T14:30:00"
    }
  ]
}
```

---

### 3. Reçete Listesi

#### `GET /api/v1/recipes`

Tüm reçeteleri listeler.

**Query Parameters:**
- `category_id` (optional): Kategori ID ile filtrele
- `include_inactive` (optional): Pasif reçeteleri dahil et

**Request:**
```bash
curl -X GET "http://localhost:5000/api/v1/recipes" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "success": true,
  "count": 25,
  "data": [
    {
      "id": 1,
      "name": "TAMBURLU 135'lik",
      "category_id": 1,
      "category_name": "Tambur Hattı",
      "model_variant": "135",
      "description": "135'lik tambur üretimi",
      "is_active": true,
      "total_items": 15,
      "created_at": "2024-01-01T10:00:00",
      "updated_at": "2024-01-15T14:30:00"
    }
  ]
}
```

---

### 4. Reçete Detayı

#### `GET /api/v1/recipes/{recipe_id}`

Belirli bir reçetenin detaylarını ve malzeme listesini döndürür.

**Request:**
```bash
curl -X GET "http://localhost:5000/api/v1/recipes/1" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "TAMBURLU 135'lik",
    "category_id": 1,
    "category_name": "Tambur Hattı",
    "model_variant": "135",
    "description": "135'lik tambur üretimi",
    "is_active": true,
    "items": [
      {
        "id": 1,
        "product_id": 5,
        "product_code": "CM-005",
        "product_name": "Somun M10",
        "quantity": 12.0,
        "unit_type": "adet",
        "current_stock": 500.0,
        "note": "Ana bağlantı"
      },
      {
        "id": 2,
        "product_id": 8,
        "product_code": "CM-008",
        "product_name": "Civata M10x50",
        "quantity": 8.0,
        "unit_type": "adet",
        "current_stock": 300.0,
        "note": null
      }
    ],
    "created_at": "2024-01-01T10:00:00",
    "updated_at": "2024-01-15T14:30:00"
  }
}
```

---

### 5. Ürün Ağacı (Hiyerarşik)

#### `GET /api/v1/product-tree`

Tüm reçeteleri ve malzemelerini hiyerarşik ağaç yapısında döndürür.

**Query Parameters:**
- `include_inactive` (optional): Pasif kayıtları dahil et

**Request:**
```bash
curl -X GET "http://localhost:5000/api/v1/product-tree" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "success": true,
  "count": 25,
  "data": [
    {
      "type": "recipe",
      "id": 1,
      "name": "TAMBURLU 135'lik",
      "category_id": 1,
      "category_name": "Tambur Hattı",
      "model_variant": "135",
      "description": "135'lik tambur üretimi",
      "is_active": true,
      "children": [
        {
          "type": "product",
          "id": 5,
          "code": "CM-005",
          "name": "Somun M10",
          "quantity_required": 12.0,
          "unit_type": "adet",
          "current_stock": 500.0,
          "minimum_stock": 50.0,
          "status": "normal",
          "note": "Ana bağlantı",
          "category_id": 2,
          "category_name": "Bağlantı Elemanları"
        }
      ]
    }
  ]
}
```

**Kullanım Senaryosu:**
- Tree view görselleştirme
- Reçete detay ekranları
- Malzeme listesi gösterimi

---

### 6. Ürün Ağacı (Düz - Graph Format)

#### `GET /api/v1/product-tree/flat`

Ürün ağacını düz formatta (nodes + edges) döndürür. Network/graph görselleştirmeleri için idealdir.

**Request:**
```bash
curl -X GET "http://localhost:5000/api/v1/product-tree/flat" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "success": true,
  "nodes": [
    {
      "id": "recipe_1",
      "type": "recipe",
      "data": {
        "recipe_id": 1,
        "name": "TAMBURLU 135'lik",
        "category": "Tambur Hattı",
        "model_variant": "135"
      }
    },
    {
      "id": "product_5",
      "type": "product",
      "data": {
        "product_id": 5,
        "code": "CM-005",
        "name": "Somun M10",
        "current_stock": 500.0,
        "unit_type": "adet",
        "status": "normal"
      }
    }
  ],
  "edges": [
    {
      "source": "recipe_1",
      "target": "product_5",
      "quantity": 12.0,
      "label": "12.0 adet"
    }
  ],
  "node_count": 176,
  "edge_count": 423
}
```

**Kullanım Senaryosu:**
- D3.js, Cytoscape.js, vis.js ile network görselleştirme
- Graph analizleri
- BOM (Bill of Materials) çizelgesi

**Örnek Görselleştirme Kodu (D3.js):**
```javascript
fetch('http://localhost:5000/api/v1/product-tree/flat')
  .then(res => res.json())
  .then(data => {
    // D3.js ile çiz
    const simulation = d3.forceSimulation(data.nodes)
      .force("link", d3.forceLink(data.edges).id(d => d.id))
      .force("charge", d3.forceManyBody())
      .force("center", d3.forceCenter(width / 2, height / 2));
  });
```

---

### 7. Üretim Yapılabilirlik Kontrolü

#### `GET /api/v1/recipe/{recipe_id}/can-produce`

Belirli bir reçete için üretim yapılıp yapılamayacağını kontrol eder.

**Query Parameters:**
- `quantity` (optional): Üretilecek miktar (varsayılan: 1)

**Request:**
```bash
curl -X GET "http://localhost:5000/api/v1/recipe/1/can-produce?quantity=5" \
  -H "X-API-Key: your-api-key"
```

**Response (Başarılı):**
```json
{
  "success": true,
  "can_produce": true,
  "quantity": 5,
  "message": "5 adet üretim için tüm malzemeler mevcut"
}
```

**Response (Yetersiz Stok):**
```json
{
  "success": true,
  "can_produce": false,
  "quantity": 5,
  "missing_material": {
    "product_id": 8,
    "product_code": "CM-008",
    "product_name": "Civata M10x50",
    "required": 40.0,
    "available": 25.0,
    "shortage": 15.0,
    "unit_type": "adet"
  },
  "message": "Yetersiz stok: Civata M10x50"
}
```

---

### 8. Eksik Malzeme Listesi

#### `GET /api/v1/recipe/{recipe_id}/missing-materials`

Üretim için eksik olan tüm malzemeleri listeler.

**Query Parameters:**
- `quantity` (optional): Üretilecek miktar (varsayılan: 1)

**Request:**
```bash
curl -X GET "http://localhost:5000/api/v1/recipe/1/missing-materials?quantity=10" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "success": true,
  "recipe_id": 1,
  "recipe_name": "TAMBURLU 135'lik",
  "quantity": 10,
  "missing_count": 3,
  "missing_materials": [
    {
      "product_id": 8,
      "product_code": "CM-008",
      "product_name": "Civata M10x50",
      "required": 80.0,
      "available": 30.0,
      "shortage": 50.0,
      "unit_type": "adet"
    },
    {
      "product_id": 12,
      "product_code": "CM-012",
      "product_name": "Pul 10mm",
      "required": 160.0,
      "available": 100.0,
      "shortage": 60.0,
      "unit_type": "adet"
    }
  ]
}
```

---

## Mevcut Endpoint'ler (Eski API)

### Ürün İşlemleri

#### `GET /api/products`
Basit ürün listesi

#### `GET /api/products/{id}`
Tek ürün detayı

#### `GET /api/products/search?q={query}`
Ürün arama

#### `GET /api/products/by-qr/{code}`
QR kodu ile ürün bulma

### Stok İşlemleri

#### `POST /api/stock/quick`
Hızlı stok hareketi

**Request Body:**
```json
{
  "product_id": 1,
  "quantity": 10,
  "direction": "in"  // "in" veya "out"
}
```

### Kategori İşlemleri

#### `GET /api/categories`
Kategori listesi

#### `GET /api/production-lines`
Üretim hatları listesi

### Dashboard

#### `GET /api/dashboard/stats`
Dashboard istatistikleri

---

## Hata Kodları

| HTTP Status | Açıklama |
|------------|----------|
| 200 | Başarılı |
| 400 | Geçersiz istek |
| 401 | Kimlik doğrulama hatası |
| 404 | Kaynak bulunamadı |
| 500 | Sunucu hatası |

**Örnek Hata Response:**
```json
{
  "error": "Ürün bulunamadı"
}
```

---

## Örnek Kullanım Senaryoları

### 1. Ürün Ağacı Görselleştirme Uygulaması

```python
import requests

# API'den veri çek
response = requests.get(
    'http://localhost:5000/api/v1/product-tree/flat',
    headers={'X-API-Key': 'your-key'}
)

data = response.json()

# Nodes ve edges'i kullanarak graph çiz
nodes = data['nodes']
edges = data['edges']

# Cytoscape.js, D3.js, vis.js vb. ile görselleştir
```

### 2. Üretim Planlama Uygulaması

```python
import requests

recipe_id = 1
quantity = 50

# Üretim yapılabilir mi kontrol et
response = requests.get(
    f'http://localhost:5000/api/v1/recipe/{recipe_id}/can-produce',
    params={'quantity': quantity},
    headers={'X-API-Key': 'your-key'}
)

result = response.json()

if result['can_produce']:
    print(f"✓ {quantity} adet üretim yapılabilir")
else:
    # Eksik malzemeleri al
    missing_response = requests.get(
        f'http://localhost:5000/api/v1/recipe/{recipe_id}/missing-materials',
        params={'quantity': quantity},
        headers={'X-API-Key': 'your-key'}
    )

    missing_data = missing_response.json()
    print(f"✗ Eksik malzemeler:")
    for item in missing_data['missing_materials']:
        print(f"  - {item['product_name']}: {item['shortage']} {item['unit_type']}")
```

### 3. BOM (Bill of Materials) Raporu

```python
import requests
import pandas as pd

# Tüm reçeteleri al
recipes_response = requests.get(
    'http://localhost:5000/api/v1/recipes',
    headers={'X-API-Key': 'your-key'}
)

recipes = recipes_response.json()['data']

# Her reçete için malzeme listesi
bom_data = []

for recipe in recipes:
    recipe_detail = requests.get(
        f'http://localhost:5000/api/v1/recipes/{recipe["id"]}',
        headers={'X-API-Key': 'your-key'}
    ).json()['data']

    for item in recipe_detail['items']:
        bom_data.append({
            'Reçete': recipe['name'],
            'Malzeme Kodu': item['product_code'],
            'Malzeme Adı': item['product_name'],
            'Miktar': item['quantity'],
            'Birim': item['unit_type'],
            'Mevcut Stok': item['current_stock']
        })

# Pandas DataFrame'e çevir ve Excel'e aktar
df = pd.DataFrame(bom_data)
df.to_excel('bom_raporu.xlsx', index=False)
```

---

## Güvenlik Notları

1. **Production ortamında API Key kullanımı önerilir**
2. **HTTPS kullanın** - HTTP yerine HTTPS tercih edin
3. **Rate Limiting** - Flask-Limiter ile istek sınırlaması ekleyin
4. **CORS** - Gerekirse Flask-CORS ile cross-origin ayarları yapın

**.env Örneği:**
```env
API_KEY=sk_live_1234567890abcdef
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://...
```

---

## Test

### Health Check
```bash
curl http://localhost:5000/api/v1/health
```

### Ürün Listesi
```bash
curl -X GET http://localhost:5000/api/v1/products/full \
  -H "X-API-Key: your-api-key"
```

### Ürün Ağacı
```bash
curl -X GET http://localhost:5000/api/v1/product-tree \
  -H "X-API-Key: your-api-key" | jq '.'
```

---

## İletişim

Sorularınız için: [GitHub Issues](https://github.com/your-repo/issues)

**API Version:** 1.0
**Son Güncelleme:** 2026-01-12
