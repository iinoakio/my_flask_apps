import os
import uuid
import sqlite3
from flask import render_template, request, redirect, url_for, session, jsonify, send_file, flash
from .forms import ImageUploadForm  # FlaskFormのインポート
from . import ai_remove_background_bp  # __init__.pyからBlueprintをインポート
from ai_image_analysis.routes import is_jpegfile, save_heif_as_jpeg
from rembg import remove
from PIL import Image
from io import BytesIO
from datetime import datetime
import pytz

UPLOAD_FOLDER = './ai_remove_background/static/uploads/'
RESULT_FOLDER = './ai_remove_background/static/results/'

# データベースのパスを指定
DATABASE = os.path.join(os.path.dirname(__file__), 'history.db')

# 認証に使用するパスワード
HISTORY_PASSWORD = os.environ.get("HISTORY_PASSWORD", "Canon-01")

# 日本標準時 (JST) のタイムゾーンを取得
jst = pytz.timezone('Asia/Tokyo')

# データベースに履歴を保存
def save_history(original_filename, result_filename):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO history (original_filename, result_filename) 
        VALUES (?, ?)
    ''', (original_filename, result_filename))
    conn.commit()
    conn.close()

# データベースの初期化
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # テーブル作成SQL
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            original_filename TEXT,
            result_filename TEXT
        )
    ''')
    conn.commit()
    conn.close()

# サーバー起動時にデータベースを初期化
init_db()

# ルート: 画像アップロードページ
@ai_remove_background_bp.route("/", methods=['GET', 'POST'])
def index():
    form = ImageUploadForm()  # フォームをインスタンス化

    if form.validate_on_submit():
        # 画像がアップロードされた場合の処理
        if not ('file' in request.files):
            return redirect(url_for('ai_remove_background.index'))
        temp_file = request.files['file']
        is_jpeg, is_heif = is_jpegfile(temp_file)
        if not (is_jpeg or is_heif):
            session["error_msg"] = "JPEGまたはHEIFファイルを指定して下さい"
            return jsonify({'error': session["error_msg"]}), 400  # 400 Bad Request

        # UUIDを使ってファイル名を生成
        unique_filename = str(uuid.uuid4()) + '.jpg'
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        if is_heif:
            save_heif_as_jpeg(temp_file, file_path)
        else:
            temp_file.save(file_path)

        # 背景を除去する処理
        output_filename = str(uuid.uuid4()) + '.png'
        output_path = os.path.join(RESULT_FOLDER, output_filename)

        # 背景除去の実行
        with open(file_path, 'rb') as input_file:
            input_data = input_file.read()
            result_data = remove(input_data)

        # 結果を保存
            img = Image.open(BytesIO(result_data))
            img.save(output_path)

        # 履歴を保存
        save_history(unique_filename, output_filename)

        # 背景除去前の画像と後の画像をテンプレートに渡す
        return redirect(url_for('ai_remove_background.result', original_filename=unique_filename, result_filename=output_filename))

    return render_template('ai_remove_background/upload.html', form=form)  # formをテンプレートに渡す

# 管理者ログインページ
@ai_remove_background_bp.route("/admin", methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == HISTORY_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('ai_remove_background.history'))
        else:
            flash('パスワードが正しくありません', 'danger')
    return render_template('ai_remove_background/admin_login.html')

# 履歴管理ページ（認証後）
@ai_remove_background_bp.route("/history")
def history():
    if not session.get('admin_logged_in'):
        return redirect(url_for('ai_remove_background.admin'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, timestamp, original_filename, result_filename FROM history ORDER BY timestamp DESC')
    history_data = c.fetchall()
    conn.close()

    return render_template('ai_remove_background/history.html', history=history_data)

# 結果の表示ページ
@ai_remove_background_bp.route("/result")
def result():
    original_filename = request.args.get('original_filename')
    result_filename = request.args.get('result_filename')

    original_file_url = url_for('ai_remove_background.static', filename='uploads/' + original_filename)
    result_file_url = url_for('ai_remove_background.static', filename='results/' + result_filename)

    return render_template('ai_remove_background/result.html', original_file_url=original_file_url, result_file_url=result_file_url)

# 背景除去後の画像をダウンロードするルート
@ai_remove_background_bp.route("/download/<filename>")
def download(filename):
    file_path = os.path.join(RESULT_FOLDER, filename)
    return send_file(file_path, as_attachment=True)
