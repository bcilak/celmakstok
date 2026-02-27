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
    # Product modelinde location_stocks backref'i olacak

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
    
    # Ek bilgiler
    barcode = db.Column(db.String(100))  # Barkod
    notes = db.Column(db.Text)  # Notlar
    
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
    target_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True) # Hangi ürünü üretiyor
    model_variant = db.Column(db.String(50))  # Model varyantı (135'lik, 165'lik, 195'lik vb.)
    description = db.Column(db.Text)  # Açıklama
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    category = db.relationship('Category', backref='recipes')
    target_product = db.relationship('Product', foreign_keys=[target_product_id], backref='recipes_as_target')
    items = db.relationship('RecipeItem', backref='recipe', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def total_items(self):
        return self.items.count()
    
    def can_produce(self, quantity=1):
        """Belirtilen miktar kadar üretim yapılabilir mi kontrol et (Recursive BOM)"""
        missing = self.get_missing_materials(quantity)
        if missing:
            # Sadece örnek olarak ilk eksik malzemeyi dönüyoruz (eski kullanımla uyumlu olmak için)
            return False, missing[0]['product'], missing[0]['available'], missing[0]['required']
        return True, None, 0, 0
    
    def get_missing_materials(self, quantity=1, _visited=None):
        """Hammadde bazında eksik malzemeleri listele (Recursive BOM)"""
        if _visited is None:
            _visited = set()
            
        if self.id in _visited:
            return []  # Döngü önleme
        _visited.add(self.id)
            
        missing_dict = {}  # {product_id: {'product': p, 'required': qty, 'available': qty, 'shortage': qty}}
        
        # 1. Aşama: Bu reçetenin kendi (en alt seviye) hammaddelerini toparla
        def calculate_requirements(recipe, needed_qty):
            for item in recipe.items:
                req_qty = item.quantity * needed_qty
                
                # Bu malzeme yarımamül/mamül mü ve bir reçetesi var mı?
                # Eğer alt reçetesi varsa ve yeterli stoğu yoksa, eksik kalan miktar için ZİNCİRLEME (recursive) hesap yap
                if item.product.recipes_as_target and len(item.product.recipes_as_target) > 0:
                    sub_recipe = item.product.recipes_as_target[0] # İlk reçeteyi varsayılan kabul et
                    available_now = item.product.current_stock
                    
                    if available_now >= req_qty:
                        # Eğer alt yarımamülden elimizde yeterince varsa (stok hazırsa), bunu doğrudan kullanırız, altına inmeyiz.
                        # (Ancak şu anki istenen yapı hammaddeye kadar inip onu düşmek mi? Kullanıcı hammadde dedi.
                        # Yani her zaman hammaddeye ineceğiz. Eğer eldeki stok o yarımamül içinse onu kullansın.)
                        continue  # Elde hazır varsa altına inmeye gerek yok, onu harcayacağız.
                    else:
                        # Hazır stok yetmiyorsa, sadece EKSİK kısım için alt malzemeleri topla.
                        # (Veya basitçe varsa bile hammadde harcansın istenirse `qty_to_build = req_qty` diyebilirdik. 
                        #  Ancak elde hazır yarımamül varsa onu kullanmak daha mantıklıdır)
                        shortage_qty = req_qty - available_now
                        
                        # Eksik kısım için alt reçetenin bileşenlerini topla
                        calculate_requirements(sub_recipe, shortage_qty)
                        
                        # Mevcut stok kadar olan kısmı için stokta ne kadar eksik var diye bakmaya gerek yok, zira stoğunu tüketecek.
                        # (Not: Stok düşme logic'inde de aynı ayrımı yapmalıyız)
                else:
                    # Normal hammadde
                    if item.product.id not in missing_dict:
                        missing_dict[item.product.id] = {
                            'product': item.product,
                            'required': 0,
                            'available': item.product.current_stock,
                            'shortage': 0
                        }
                    missing_dict[item.product.id]['required'] += req_qty
        
        calculate_requirements(self, quantity)
        
        # 2. Aşama: Toplam gereksinimlere göre eksikleri listele
        missing = []
        for pid, data in missing_dict.items():
            if data['available'] < data['required']:
                data['shortage'] = data['required'] - data['available']
                missing.append(data)
                
        _visited.remove(self.id)
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
