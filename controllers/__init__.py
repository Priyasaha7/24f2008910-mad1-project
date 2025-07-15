from .auth import auth
from .admin import admin
from .user import user

def register_blueprints(app):
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(admin)
    app.register_blueprint(user)