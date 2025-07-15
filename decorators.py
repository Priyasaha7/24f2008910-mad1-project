from flask import redirect, session, url_for, flash, abort
from functools import wraps
from models import User


# Helper: Admin-only access decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login required')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# authenthication required for the users
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login required')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function



