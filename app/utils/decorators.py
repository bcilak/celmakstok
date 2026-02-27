from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

def roles_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                # If user is not logged in, redirect to login page
                return redirect(url_for('auth.login', next=request.url))

            # Grant access if user is an Admin
            if current_user.is_admin():
                return f(*args, **kwargs)

            # Check if the user's role is in the list of allowed roles
            if current_user.role not in roles:
                flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
                # Redirect to the previous page or a default page
                referrer = request.referrer
                if referrer and referrer != request.url:
                    return redirect(referrer)
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return wrapper
