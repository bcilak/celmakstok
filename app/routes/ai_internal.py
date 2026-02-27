from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload
from app.utils.api_auth import api_key_required
from app.models import StockMovement, ProductionRecord, CountSession

ai_bp = Blueprint('ai_internal', __name__)


def serialize_movement(m):
    return {
        'id': m.id,
        'date': m.date.isoformat() if m.date else None,
        'product_id': m.product_id,
        'product_name': m.product.name if getattr(m, 'product', None) else None,
        'type': m.movement_type,
        'quantity': m.quantity,
        'source': m.source,
        'destination': m.destination,
        'note': m.note,
    }


def serialize_production(p):
    return {
        'id': p.id,
        'date': p.date.isoformat() if p.date else None,
        'recipe_id': p.recipe_id,
        'recipe_name': p.recipe.name if getattr(p, 'recipe', None) else None,
        'quantity': p.quantity,
        'note': p.note,
    }


def serialize_session(s):
    return {
        'id': s.id,
        'name': s.name,
        'created_at': s.created_at.isoformat() if s.created_at else None,
        'status': s.status,
    }


@ai_bp.route('/user_activity/<int:user_id>')
@api_key_required
def user_activity(user_id):
    # params: limit, since, until
    limit = min(int(request.args.get('limit', 200)), 1000)
    since = request.args.get('since')
    until = request.args.get('until')

    qm = StockMovement.query.options(joinedload(StockMovement.product)).filter_by(user_id=user_id)
    qp = ProductionRecord.query.options(joinedload(ProductionRecord.recipe)).filter_by(user_id=user_id)
    qs = CountSession.query.filter_by(user_id=user_id)

    if since:
        try:
            from dateutil import parser
            since_dt = parser.isoparse(since)
            qm = qm.filter(StockMovement.date >= since_dt)
            qp = qp.filter(ProductionRecord.date >= since_dt)
            qs = qs.filter(CountSession.created_at >= since_dt)
        except Exception:
            pass

    if until:
        try:
            from dateutil import parser
            until_dt = parser.isoparse(until)
            qm = qm.filter(StockMovement.date <= until_dt)
            qp = qp.filter(ProductionRecord.date <= until_dt)
            qs = qs.filter(CountSession.created_at <= until_dt)
        except Exception:
            pass

    movements = qm.order_by(StockMovement.date.desc()).limit(limit).all()
    productions = qp.order_by(ProductionRecord.date.desc()).limit(limit).all()
    sessions = qs.order_by(CountSession.created_at.desc()).limit(limit).all()

    return jsonify({
        'movements': [serialize_movement(m) for m in movements],
        'productions': [serialize_production(p) for p in productions],
        'sessions': [serialize_session(s) for s in sessions]
    })
