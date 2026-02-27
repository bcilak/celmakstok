from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import Product, Category, StockMovement, CountSession, User
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta
from app.utils.decorators import roles_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
@roles_required('Genel', 'Yönetici', 'Personel')
def dashboard():
    try:
        # Özet istatistikler
        total_products = Product.query.filter_by(is_active=True).count()

        # Kritik stok ürünleri
        critical_products = Product.query.filter(
            Product.is_active == True,
            Product.current_stock < Product.minimum_stock,
            Product.minimum_stock > 0
        ).all()

        # Bugünkü hareketler
        today = datetime.utcnow().date()
        today_movements = StockMovement.query.filter(
            func.date(StockMovement.date) == today
        ).count()

        # Son 7 gün giriş/çıkış
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_in = db.session.query(func.sum(StockMovement.quantity)).filter(
            StockMovement.date >= week_ago,
            StockMovement.movement_type == 'giris'
        ).scalar() or 0

        week_out = db.session.query(func.sum(StockMovement.quantity)).filter(
            StockMovement.date >= week_ago,
            StockMovement.movement_type == 'cikis'
        ).scalar() or 0

        # Üretim hatları (Kategoriler)
        production_lines = Category.query.filter_by(is_active=True).all()

        # Aktif sayım oturumları
        active_counts = CountSession.query.filter(
            CountSession.status == 'active'
        ).count()

        # Kategoriler
        categories = Category.query.all()

        # Son hareketler
        recent_movements = StockMovement.query.order_by(
            StockMovement.date.desc()
        ).limit(10).all()

        return render_template('dashboard.html',
            total_products=total_products,
            critical_products=critical_products,
            critical_count=len(critical_products),
            today_movements=today_movements,
            week_in=week_in,
            week_out=week_out,
            production_lines=production_lines,
            active_counts=active_counts,
            categories=categories,
            recent_movements=recent_movements
        )
    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()

        return render_template('dashboard.html',
            total_products=0,
            critical_products=[],
            critical_count=0,
            today_movements=0,
            week_in=0,
            week_out=0,
            production_lines=[],
            active_counts=0,
            categories=[],
            recent_movements=[]
        )


@main_bp.route('/about')
@login_required
@roles_required('Genel', 'Yönetici', 'Personel')
def about():
    """Proje hakkında sayfası"""
    stats = {
        'products': Product.query.filter_by(is_active=True).count(),
        'categories': Category.query.filter_by(is_active=True).count(),
        'movements': StockMovement.query.count(),
        'users': User.query.filter_by(is_active=True).count()
    }
    
    return render_template('about.html', stats=stats)
