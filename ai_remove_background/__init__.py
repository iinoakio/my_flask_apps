from flask import Blueprint

ai_remove_background_bp = Blueprint(
    'ai_remove_background', __name__,
    template_folder='templates',
    static_folder='static'  # staticフォルダを指定
)

# ルートのインポート
from . import routes
