from .index import app
from .crm import crm_bp
from .mfa import mfa_bp

app.register_blueprint(crm_bp)
app.register_blueprint(mfa_bp)

__all__ = ["app"]
