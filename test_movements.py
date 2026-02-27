import os
from app import create_app, db
from app.models import StockMovement

app = create_app()

with app.app_context():
    try:
        query = StockMovement.query
        movements = query.order_by(StockMovement.date.desc()).all()
        total_in = sum(m.quantity for m in movements if m.movement_type == 'giris')
        total_out = sum(m.quantity for m in movements if m.movement_type == 'cikis')
        print(f"Success! Total In: {total_in}, Total Out: {total_out}, Records: {len(movements)}")
        for m in movements[:10]:
            _ = m.product.name if m.product else '-'
            _ = m.date.strftime('%d.%m.%Y') if m.date else '-'
            
    except Exception as e:
        import traceback
        traceback.print_exc()
