from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

# Kullanıcı modeli
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)  # Ad Soyad
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='Personel', nullable=False)  # Roles: Admin, Genel, Yönetici, Personel
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Eski alan adı için uyumluluk
    @property
    def full_name(self):
        return self.name
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role and self.role.lower() == 'admin'

    def is_genel(self):
        return self.role and self.role.lower() == 'genel'

    def is_yonetici(self):
        return self.role and self.role.lower() == 'yönetici'

    def is_personel(self):
        return self.role and self.role.lower() == 'personel'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Kategori/Üretim Hattı modeli (Diyagrama uygun)
class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # Kategori/Hat adı
    code = db.Column(db.String(20), unique=True)  # Hat kodu
    unit = db.Column(db.String(20), default='adet')  # Varsayılan birim (adet, kg, metre)
    note = db.Column(db.Text)  # Notlar
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    products = db.relationship('Product', backref='category', lazy='dynamic')
    
    # Eski alan adı için uyumluluk
    @property
    def description(self):
        return self.note

# Lokasyon / Depo / Hat Modeli
class Location(db.Model):
    __tablename__ = 'locations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Lokasyondaki Ürün Stokları Modeli
class LocationStock(db.Model):
    __tablename__ = 'location_stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    location = db.relationship('Location', backref=db.backref('stocks', lazy='dynamic'))
    product = db.relationship('Product', backref=db.backref('location_stocks', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('location_id', 'product_id', name='uq_location_product'),
    )

# Ürün modeli (Maliyetsiz)
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Ürün kodu
    name = db.Column(db.String(200), nullable=False)  # Malzeme adı
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    
    # MRP Tipleri
    type = db.Column(db.String(50), default='hammadde', nullable=False) # hammadde, yarimamul, mamul
    
    # Birim bilgileri
    unit_type = db.Column(db.String(20), nullable=False, default='adet')  # kg, metre, adet
    
    # Stok bilgileri (Sadece miktar)
    current_stock = db.Column(db.Float, default=0)  # Aktif stok miktarı
    minimum_stock = db.Column(db.Float, default=0)  # Minimum stok seviyesi
    
    # Satın alma & Fiyatlandırma (Gizli alanlar - Dış API'den beslenir)
    unit_cost = db.Column(db.Float, default=0.0)    # Birim maliyet/fiyat
    currency = db.Column(db.String(10), default='TRY') # Para birimi (TRY, USD, EUR vb.)
    vat_rate = db.Column(db.Float, default=0.0)    # KDV oranı (%)
    
    # Ek bilgiler
    barcode = db.Column(db.String(100))  # Barkod
    notes = db.Column(db.Text)  # Notlar
    material = db.Column(db.Text)  # Malzeme özelliği / cinsi (BOM'dan aktarılır)
    image = db.Column(db.String(255))  # Ürün resmi dosya yolu
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    stock_movements = db.relationship('StockMovement', backref='product', lazy='dynamic')
    location_stocks = db.relationship('LocationStock', backref='product_ref', lazy='dynamic')
    
    @property
    def stock_status(self):
        """Stok durumu"""
        if self.current_stock <= 0:
            return 'empty'
        elif self.minimum_stock > 0 and self.current_stock < self.minimum_stock:
            return 'critical'
        return 'normal'
    
    @property
    def total_in(self):
        """Toplam giriş miktarı"""
        from sqlalchemy import func
        result = db.session.query(func.sum(StockMovement.quantity)).filter(
            StockMovement.product_id == self.id,
            StockMovement.movement_type == 'giris'
        ).scalar()
        return result or 0
    
    @property
    def total_out(self):
        """Toplam çıkış miktarı"""
        from sqlalchemy import func
        result = db.session.query(func.sum(StockMovement.quantity)).filter(
            StockMovement.product_id == self.id,
            StockMovement.movement_type.in_(['cikis', 'transfer', 'fire'])
        ).scalar()
        return result or 0

# Stok Durumu modeli (Diyagrama uygun - stock_current)
class StockCurrent(db.Model):
    __tablename__ = 'stock_current'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, unique=True)
    quantity = db.Column(db.Float, default=0)
    
    product = db.relationship('Product', backref='stock_record')

# Stok Hareketi modeli (Diyagrama uygun)
class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Hareket tipi: giris, cikis, sayim, transfer, fire
    movement_type = db.Column(db.String(20), nullable=False)
    
    # Miktar
    quantity = db.Column(db.Float, nullable=False)
    
    # Kaynak ve Hedef (nereden nereye)
    source = db.Column(db.String(100))  # Eski kaynak (tedarikçi, depo, hat adı)
    destination = db.Column(db.String(100))  # Eski hedef (depo, hat adı, müşteri)
    
    # MRP Lokasyon Referansları
    from_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    to_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    
    from_location = db.relationship('Location', foreign_keys=[from_location_id])
    to_location = db.relationship('Location', foreign_keys=[to_location_id])
    
    # Kullanıcı ve tarih
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.Text)
    
    # Relationships
    user = db.relationship('User', backref='movements')
    product = db.relationship('Product', backref='stock_movements')
    
    # Eski alan adları için uyumluluk
    @property
    def created_at(self):
        return self.date
    
    @property
    def notes(self):
        return self.note
    
    @property
    def direction(self):
        if self.movement_type in ['giris', 'sayim_artis']:
            return 'in'
        return 'out'

# Sayım Oturumu modeli
class CountSession(db.Model):
    __tablename__ = 'count_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Sayım adı
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    note = db.Column(db.Text)
    
    user = db.relationship('User', backref='count_sessions')
    items = db.relationship('CountItem', backref='session', lazy='dynamic')
    
    # Eski alan adı için uyumluluk
    @property
    def session_name(self):
        return self.name
    
    @property
    def session_date(self):
        return self.created_at

# Sayım Kalemi modeli
class CountItem(db.Model):
    __tablename__ = 'count_items'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('count_sessions.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    system_quantity = db.Column(db.Float, nullable=False)  # Sistemdeki miktar
    counted_quantity = db.Column(db.Float)  # Sayılan miktar
    difference = db.Column(db.Float)  # Fark
    
    is_counted = db.Column(db.Boolean, default=False)
    counted_at = db.Column(db.DateTime)
    counted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    note = db.Column(db.Text)
    notes = db.Column(db.Text)  # alias for note
    
    product = db.relationship('Product', backref='count_items')
    counter = db.relationship('User', backref='counted_items')


# Reçete modeli (Ürün için gerekli malzemeler)

class ProductionRecord(db.Model):
    __tablename__ = 'production_records'

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, nullable=True) # nullable true for bom
    bom_id = db.Column(db.Integer, nullable=True)
    bom_node_id = db.Column(db.Integer, db.ForeignKey('bom_nodes.id'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    quantity = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    note = db.Column(db.Text)

    user = db.relationship('User', backref='productions')
    bom_node = db.relationship('BomNode', backref='productions_records')
    product = db.relationship('Product', backref='productions_records')

    # Since we removed Recipe model, we remove the relationship to it or keep recipe_id as weak link
    
class ProductionConsumption(db.Model):
    __tablename__ = 'production_consumptions'

    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('production_records.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)

    production = db.relationship('ProductionRecord', backref=db.backref('consumptions', lazy='dynamic', cascade='all, delete-orphan'))
    product = db.relationship('Product', backref='consumptions')

class BomItem(db.Model):
    """
    'items' tablosu - Parçaların usta kaydı.
    Aynı parça kodu farklı BOM'larda tekrar kullanılabilir.
    """
    __tablename__ = 'bom_items'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100))          # Parça kodu (boş olabilir)
    name = db.Column(db.String(255), nullable=False)  # Parça adı
    type = db.Column(db.String(100))          # hammadde, yarimamul, mamul vb.
    unit_type = db.Column(db.String(20), default='adet')  # adet, kg, metre …
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Ana stok kaydıyla bağlantı (Product Master)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product = db.relationship('Product', backref='bom_items')

    nodes = db.relationship('BomNode', backref='item', lazy='dynamic')


class BomNode(db.Model):
    """
    'bom_nodes' tablosu - BOM içindeki her satır/düğüm.
    bom_id ile aynı BOM'a ait düğümler gruplanır.
    """
    __tablename__ = 'bom_nodes'

    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, nullable=False)           # Hangi BOM'a ait
    num = db.Column(db.String(50), nullable=False)            # Örn: "1.1.2."
    level = db.Column(db.Integer, nullable=False)             # 1, 2, 3 …
    item_id = db.Column(db.Integer, db.ForeignKey('bom_items.id'))
    display_name = db.Column(db.String(255))                  # Görünen isim
    quantity = db.Column(db.Numeric(12, 4), default=1)        # Fireli (toplam) adet
    quantity_net = db.Column(db.Numeric(12, 4), nullable=True) # Firesiz (net) adet
    piece_count = db.Column(db.Numeric(12, 4), default=1)      # Parça adedi
    weight_per_unit = db.Column(db.Numeric(12, 4), nullable=True)  # Birim ağırlık
    weight_unit = db.Column(db.String(20), nullable=True)      # Ağırlık birimi (kg…)
    unit_type = db.Column(db.String(20), default='adet')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # İlişkiler
    parent_edges = db.relationship(
        'BomEdge',
        foreign_keys='BomEdge.child_node_id',
        backref='child_node',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    child_edges = db.relationship(
        'BomEdge',
        foreign_keys='BomEdge.parent_node_id',
        backref='parent_node',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )


class BomEdge(db.Model):
    """
    'bom_edges' tablosu - Parent-child ilişkileri.
    ROOT düğümü için parent_node_id NULL'dır.
    """
    __tablename__ = 'bom_edges'

    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, nullable=False)
    parent_node_id = db.Column(db.Integer, db.ForeignKey('bom_nodes.id'), nullable=True)
    child_node_id = db.Column(db.Integer, db.ForeignKey('bom_nodes.id'), nullable=False)
    quantity = db.Column(db.Numeric(12, 4), default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ===== YARDIMCI FONKSİYONLAR =====

def generate_category_code(name):
    """Kategori adından kod oluştur"""
    import re
    # Türkçe karakterleri dönüştür
    tr_map = {'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'İ': 'I', 
              'ö': 'o', 'Ö': 'O', 'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'}
    result = name
    for tr, en in tr_map.items():
        result = result.replace(tr, en)
    # Sadece harf ve rakamları al
    result = re.sub(r'[^A-Za-z0-9]', '', result)
    return result[:8].upper()
