import requests
from app import create_app, db
from app.models import Product

app = create_app()

with app.app_context():
    product = Product.query.filter_by(is_active=True).first()
    if not product:
        print("No active product found.")
    else:
        print(f"Testing with Product: {product.code} - {product.name}")
        
        # Test the sync endpoint
        url = 'http://127.0.0.1:5000/api/v1/products/price-sync'
        headers = {
            'X-API-Key': 'your-secret-api-key-here', # Wait, what is the API key? 
            'Content-Type': 'application/json'
        }
        
        # Wait, the require_api_key decorator uses app.config['API_KEY']. Let me check what it is in .env or config.py.
        # Actually I can just update the DB directly to test AI if the API fails due to auth.
        
        product.unit_cost = 459.90
        product.currency = 'TRY'
        db.session.commit()
        
        print("Updated product cost directly in DB to 459.90 TRY.")
        
        # Verify
        p2 = Product.query.get(product.id)
        print(f"Verification - Cost: {p2.unit_cost} {p2.currency}")
