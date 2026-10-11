from flask import Blueprint

seats_bp = Blueprint(
    'seats', 
    __name__,
    template_folder='templates',
    static_folder=None,
    url_prefix=None
)

# 导入路由
from . import routes