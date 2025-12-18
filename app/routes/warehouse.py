from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Product, Category
from app import db

warehouse_bp = Blueprint('warehouse', __name__)

@warehouse_bp.route('/')
@login_required
def index():
    # Kritik stoklar
    critical_products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock,
        Product.minimum_stock > 0
    ).order_by(Product.current_stock).all()
    
    # Boş stoklar
    empty_products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock <= 0
    ).all()
    
    # Kategori bazlı stok özeti
    categories = Category.query.all()
    category_stats = []
    for cat in categories:
        products = Product.query.filter_by(category_id=cat.id, is_active=True).all()
        total_items = len(products)
        critical_items = sum(1 for p in products if p.minimum_stock > 0 and p.current_stock < p.minimum_stock)
        category_stats.append({
            'category': cat,
            'total_items': total_items,
            'critical_items': critical_items
        })
    
    return render_template('warehouse/index.html',
        critical_products=critical_products,
        empty_products=empty_products,
        category_stats=category_stats
    )

@warehouse_bp.route('/critical')
@login_required
def critical():
    """Kritik stok listesi"""
    products = Product.query.filter(
        Product.is_active == True,
        Product.current_stock < Product.minimum_stock,
        Product.minimum_stock > 0
    ).order_by(Product.current_stock).all()
    
    return render_template('warehouse/critical.html', products=products)
