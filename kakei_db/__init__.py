from flask import Blueprint

# Blueprintの初期化
kakei_db_bp = Blueprint(
    'kakei_db',  # Blueprintの名前
    __name__,  # 現在のモジュールの名前
    template_folder='templates',  # テンプレートファイルの場所
    static_folder='static'  # 静的ファイルの場所
    )

# ルートや他のモジュールをインポート
from . import routes

