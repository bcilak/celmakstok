# ÇELMAK Stok Takip Sistemi - API Entegrasyonu

## 🚀 Hızlı Başlangıç

Başka bir uygulama ile ÇELMAK Stok Takip sistemini entegre etmek için hazır API endpoint'leri eklendi.

### Temel Özellikler

✅ **Ürün Listesi** - Tüm ürünleri detaylı bilgileriyle döndürür
✅ **Reçete Listesi** - Tüm reçeteleri ve malzemelerini listeler
✅ **Ürün Ağacı (Hiyerarşik)** - Parent-child ilişkileriyle ağaç yapısı
✅ **Ürün Ağacı (Düz - Graph)** - Network görselleştirme için nodes+edges formatı
✅ **Üretim Kontrol** - Belirli miktar üretim için stok yeterlilik kontrolü
✅ **Eksik Malzemeler** - Üretim için eksik olan malzemeleri listeler

---

## 📋 Eklenen Endpoint'ler

| Endpoint | Metod | Açıklama |
|----------|-------|----------|
| `/api/v1/health` | GET | API sağlık kontrolü |
| `/api/v1/products/full` | GET | Tüm ürünler (detaylı) |
| `/api/v1/recipes` | GET | Tüm reçeteler |
| `/api/v1/recipes/{id}` | GET | Reçete detayı + malzemeler |
| `/api/v1/product-tree` | GET | Ürün ağacı (hiyerarşik) |
| `/api/v1/product-tree/flat` | GET | Ürün ağacı (düz - graph) |
| `/api/v1/recipe/{id}/can-produce` | GET | Üretim yapılabilir mi? |
| `/api/v1/recipe/{id}/missing-materials` | GET | Eksik malzeme listesi |

---

## 🔧 Kurulum ve Kullanım

### 1. API Key Ayarla (Opsiyonel)

`.env` dosyasına ekleyin:
```env
API_KEY=sk_live_your_secure_api_key_here
```

**Not:** API Key boş bırakılırsa sadece Flask-Login session kontrolü yapılır.

### 2. Test Et

#### Health Check:
```bash
curl http://localhost:5000/api/v1/health
```

#### Ürün Ağacı (Graph Format):
```bash
curl http://localhost:5000/api/v1/product-tree/flat \
  -H "X-API-Key: your-api-key"
```

### 3. Tarayıcıda Görselleştir

`api_test.html` dosyasını tarayıcıda açın:
```bash
# Windows
start api_test.html

# Mac/Linux
open api_test.html
```

Bu sayfa D3.js ile ürün ağacını interaktif network grafiği olarak gösterir.

---

## 📖 Dokümantasyon

Detaylı API dokümantasyonu için:
- **[API_DOCUMENTATION.md](./API_DOCUMENTATION.md)** - Tüm endpoint'ler, parametreler, örnekler

---

## 🐍 Python Örneği

`example_api_usage.py` dosyasını çalıştırın:

```bash
python example_api_usage.py
```

Bu script:
- Tüm ürünleri listeler
- Tüm reçeteleri listeler
- Ürün ağacını çeker
- Üretim yapılabilirlik kontrolü yapar
- JSON dosyasına export eder

---

## 🌐 JavaScript Örneği

```javascript
// Ürün ağacını çek
fetch('http://localhost:5000/api/v1/product-tree/flat', {
  headers: {
    'X-API-Key': 'your-api-key'
  }
})
.then(res => res.json())
.then(data => {
  console.log(`Nodes: ${data.node_count}`);
  console.log(`Edges: ${data.edge_count}`);

  // D3.js, Cytoscape.js, vis.js ile görselleştir
  const nodes = data.nodes;
  const edges = data.edges;
});
```

---

## 🎯 Kullanım Senaryoları

### 1. Ürün Ağacı Görselleştirme
- **Araç:** D3.js, Cytoscape.js, vis.js
- **Endpoint:** `/api/v1/product-tree/flat`
- **Format:** Nodes (düğümler) + Edges (bağlantılar)

### 2. BOM (Bill of Materials) Raporu
- **Araç:** Excel, PDF
- **Endpoint:** `/api/v1/recipes` + `/api/v1/recipes/{id}`
- **Format:** Reçete bazlı malzeme listeleri

### 3. Üretim Planlama Uygulaması
- **Araç:** React, Vue, Angular
- **Endpoint:** `/api/v1/recipe/{id}/can-produce`
- **Özellik:** Üretim öncesi stok kontrolü

### 4. Mobil Uygulama
- **Araç:** React Native, Flutter
- **Endpoint:** Tüm v1 endpoint'leri
- **Format:** JSON REST API

---

## 🔐 Güvenlik

### API Key Kullanımı

1. `.env` dosyasında `API_KEY` tanımlayın
2. Her istekte header'a ekleyin:
```bash
curl -H "X-API-Key: your-key" http://localhost:5000/api/v1/products/full
```

### CORS Ayarları (Gerekirse)

Farklı domain'den erişim için Flask-CORS ekleyin:

```python
# app/__init__.py
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

---

## 📊 Response Formatları

### Başarılı Yanıt:
```json
{
  "success": true,
  "count": 150,
  "data": [...]
}
```

### Hata Yanıtı:
```json
{
  "error": "Ürün bulunamadı"
}
```

---

## 🛠️ Dosya Yapısı

```
celmakstok/
├── API_DOCUMENTATION.md      # Detaylı API dökümanı
├── API_README.md             # Bu dosya (hızlı başlangıç)
├── example_api_usage.py      # Python kullanım örneği
├── api_test.html             # Tarayıcı görselleştirme
├── app/
│   └── routes/
│       └── api.py            # API endpoint'leri
└── .env.example              # API_KEY ayarları
```

---

## 🎨 Görselleştirme Örnekleri

### D3.js Network Graph
`api_test.html` - İnteraktif ürün ağacı

### Cytoscape.js
```javascript
fetch('/api/v1/product-tree/flat')
  .then(res => res.json())
  .then(data => {
    const cy = cytoscape({
      container: document.getElementById('cy'),
      elements: {
        nodes: data.nodes.map(n => ({ data: n })),
        edges: data.edges.map(e => ({ data: e }))
      }
    });
  });
```

---

## 📞 Yardım

Sorun mu yaşıyorsunuz?

1. **Health Check** yapın: `curl http://localhost:5000/api/v1/health`
2. **API Key** doğru mu kontrol edin
3. **Flask uygulaması** çalışıyor mu: `python run.py`
4. **Loglara** bakın: Console'da hata mesajları

---

## 📝 Örnek İstekler

### 1. Tüm Ürünleri Çek
```bash
curl http://localhost:5000/api/v1/products/full
```

### 2. Belirli Reçete Detayı
```bash
curl http://localhost:5000/api/v1/recipes/1
```

### 3. 10 Adet Üretim İçin Eksik Malzemeler
```bash
curl "http://localhost:5000/api/v1/recipe/1/missing-materials?quantity=10"
```

### 4. Ürün Ağacı (Graph)
```bash
curl http://localhost:5000/api/v1/product-tree/flat > product_tree.json
```

---

## ✅ Test Checklist

- [ ] Health check çalışıyor mu?
- [ ] Ürün listesi dönüyor mu?
- [ ] Reçete detayları alınabiliyor mu?
- [ ] Ürün ağacı (flat) formatı doğru mu?
- [ ] API Key authentication çalışıyor mu?
- [ ] `api_test.html` görselleştirme açılıyor mu?

---

**Hazırlayan:** Claude (ÇELMAK Stok Takip Sistemi)
**Tarih:** 2026-01-12
**Version:** 1.0
