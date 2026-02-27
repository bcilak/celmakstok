from functools import wraps
from flask import request, abort, current_app


def api_key_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not key or key != current_app.config.get('AI_API_KEY'):
            abort(401)

        allowed = current_app.config.get('AI_ALLOWED_IPS') or []
        if allowed:
            remote = request.remote_addr
            if remote not in allowed:
                abort(403)

        return fn(*args, **kwargs)
    return wrapper
