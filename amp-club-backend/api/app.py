from .index import app
from .crm import crm_bp

app.register_blueprint(crm_bp)

__all__ = ["app"]
