from flask import request, session, redirect, render_template, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
import pytz
import uuid
import openai
import os
import platform
from .forms import FileRegisterForm
from PIL import Image
import pillow_heif
import sqlite3
from . import ai_image_analysis_bp  # Blueprintをインポート


IMAGE_URL = 'http://18.181.162.5:5000/ai_image_analysis/static/images/'
IMAGE_URL2 = 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg'
UPLOAD_FOLDER = './ai_image_analysis/static/images/'

# データベースのパスを指定
DATABASE = os.path.join(os.path.dirname(__file__), 'history.db')

# OpenAI APIキーの設定
openai.api_key = os.environ["OPENAI_API_KEY"]
client = openai.OpenAI()

# 認証に使用するパスワード
HISTORY_PASSWORD = os.environ.get("HISTORY_PASSWORD", "Canon-01")

# 日本標準時 (JST) のタイムゾーンを取得
jst = pytz.timezone('Asia/Tokyo')

# データベースの初期化
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  image_name TEXT,
                  image_url TEXT,
                  ai_analysis TEXT)''')
    conn.commit()
    conn.close()

init_db()

def save_history(image_name, image_url, ai_analysis):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # 現在の日時をJSTで取得
    current_time = datetime.now(jst)
    
    c.execute("INSERT INTO history (timestamp, image_name, image_url, ai_analysis) VALUES (?, ?, ?, ?)",
              (current_time, image_name, image_url, ai_analysis))
    
    conn.commit()
    conn.close()

@ai_image_analysis_bp.route("/", methods=['GET', 'POST'])
def index():
    form = FileRegisterForm()
    if form.validate_on_submit():
        if not ('file' in request.files):
            return redirect(url_for('ai_image_analysis.index'))
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
        
        #session["file"] = file_path

        # TEST_FLAGに基づいてURLを設定
        if platform.system() == "Windows":
            session["image_url"] = IMAGE_URL2
        else:
            session["image_url"] = IMAGE_URL +  unique_filename
        # OpenAIによる分析
        #print("akio" + session["image_url"])
        ai_msg = get_ai_img(session["image_url"])
        # 履歴を保存
        save_history(unique_filename, session["image_url"], ai_msg)

        return redirect(url_for('ai_image_analysis.user_maintenance'))
    return render_template("upload.html", form=form)

@ai_image_analysis_bp.route("/user_maintenance")
def user_maintenance():
    return render_template("user_maintenance.html")

@ai_image_analysis_bp.route("/get_ai_analysis")
def get_ai_analysis():
    try:
        ai_msg = get_ai_img(session['image_url'])
        if ai_msg is None:
            return jsonify({'error': 'OpenAI APIでエラーが発生しました'})
        return jsonify({'result': ai_msg})
    except Exception as e:
        return jsonify({'error': f"エラーが発生しました: {str(e)}"})

@ai_image_analysis_bp.route("/history", methods=['GET', 'POST'])
def history():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == HISTORY_PASSWORD:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("SELECT id, datetime(timestamp, 'localtime'), image_name, image_url, ai_analysis FROM history ORDER BY timestamp DESC")
            history_data = c.fetchall()
            conn.close()
            return render_template('history.html', history=history_data)
        else:
            flash("パスワードが正しくありません", "danger")
            return redirect(url_for('ai_image_analysis.history'))
    return render_template('password_prompt.html')


@ai_image_analysis_bp.route('/error_msg')
def error_msg():
    return render_template('message.html')

def is_jpegfile(file):
    header = file.read(12)
    file.seek(0)  # ファイルポインタを元に戻す

    # JPEG判定
    is_jpeg = header[:2] == b'\xff\xd8'

    # HEIF/HEIC判定
    heif_formats = [
        b'ftypheic', b'ftypheix', b'ftyphevc', b'ftyphevx',
        b'ftypmif1', b'ftypmsf1'
    ]
    is_heif = any(header[4:12] == heif for heif in heif_formats)

    return is_jpeg, is_heif

def save_heif_as_jpeg(heif_file, output_path):
    heif_file.seek(0)
    image = Image.open(heif_file)
    image = image.convert("RGB")  # RGBに変換
    image.save(output_path, "JPEG")

def get_ai_img(url):
    try:
        completion = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "写真を分析して、日本語で説明してください"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": url
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        return completion.choices[0].message.content
    except Exception:
        return None

