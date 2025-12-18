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
    role = db.Column(db.String(20), default='depo')  # admin, depo, uretim, misafir, yonetici
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

# Ürün modeli (Maliyetsiz)
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Ürün kodu
    name = db.Column(db.String(200), nullable=False)  # Malzeme adı
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    
    # Birim bilgileri
    unit_type = db.Column(db.String(20), nullable=False, default='adet')  # kg, metre, adet
    
    # Stok bilgileri (Sadece miktar)
    current_stock = db.Column(db.Float, default=0)  # Aktif stok miktarı
    minimum_stock = db.Column(db.Float, default=0)  # Minimum stok seviyesi
    
    # Ek bilgiler
    barcode = db.Column(db.String(100))  # Barkod
    notes = db.Column(db.Text)  # Notlar
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    stock_movements = db.relationship('StockMovement', backref='product', lazy='dynamic')
    
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
    source = db.Column(db.String(100))  # Kaynak (tedarikçi, depo, hat adı)
    destination = db.Column(db.String(100))  # Hedef (depo, hat adı, müşteri)
    
    # Kullanıcı ve tarih
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.Text)
    
    user = db.relationship('User', backref='movements')
    
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
class Recipe(db.Model):
    __tablename__ = 'recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # Reçete adı (örn: "TAMBURLU 135'lik")
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))  # Hangi üretim hattı
    model_variant = db.Column(db.String(50))  # Model varyantı (135'lik, 165'lik, 195'lik vb.)
    description = db.Column(db.Text)  # Açıklama
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    category = db.relationship('Category', backref='recipes')
    items = db.relationship('RecipeItem', backref='recipe', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def total_items(self):
        return self.items.count()
    
    def can_produce(self, quantity=1):
        """Belirtilen miktar kadar üretim yapılabilir mi kontrol et"""
        for item in self.items:
            required = item.quantity * quantity
            if item.product.current_stock < required:
                return False, item.product, item.product.current_stock, required
        return True, None, 0, 0
    
    def get_missing_materials(self, quantity=1):
        """Eksik malzemeleri listele"""
        missing = []
        for item in self.items:
            required = item.quantity * quantity
            if item.product.current_stock < required:
                missing.append({
                    'product': item.product,
                    'required': required,
                    'available': item.product.current_stock,
                    'shortage': required - item.product.current_stock
                })
        return missing


# Reçete Kalemi modeli
class RecipeItem(db.Model):
    __tablename__ = 'recipe_items'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # 1 adet üretim için gereken miktar
    note = db.Column(db.String(200))  # Opsiyonel not
    
    product = db.relationship('Product', backref='recipe_usages')
    
    __table_args__ = (
        db.UniqueConstraint('recipe_id', 'product_id', name='unique_recipe_product'),
    )


# Üretim Kaydı modeli (Hangi reçeteden ne kadar üretildi)
class ProductionRecord(db.Model):
    __tablename__ = 'production_records'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # Üretilen miktar
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.Text)
    
    recipe = db.relationship('Recipe', backref='productions')
    user = db.relationship('User', backref='productions')
    consumptions = db.relationship('ProductionConsumption', backref='production', lazy='dynamic')


# Üretim Tüketim Detayı (Hangi malzemeden ne kadar tüketildi)
class ProductionConsumption(db.Model):
    __tablename__ = 'production_consumptions'
    
    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('production_records.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    
    product = db.relationship('Product', backref='production_consumptions')


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
