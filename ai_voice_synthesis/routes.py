from flask import request, render_template, redirect, url_for, flash, jsonify
import os
import uuid
import sqlite3
from datetime import datetime
import pytz
from .forms import TextToSpeechForm
import openai
from openai import OpenAI, OpenAIError
from . import ai_voice_synthesis_bp  # Blueprintをインポート

# 環境変数からOpenAIのAPIキーを取得
openai.api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI()

# 保存先ディレクトリの設定
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/audio')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# データベースのパスを指定
DATABASE = os.path.join(os.path.dirname(__file__), 'history.db')

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
                  input_text TEXT,
                  audio_file TEXT)''')
    conn.commit()
    conn.close()

init_db()

def save_history(input_text, audio_file):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # 現在の日時をJSTで取得
    current_time = datetime.now(jst)
    c.execute("INSERT INTO history (timestamp, input_text, audio_file) VALUES (?, ?, ?)",
              (current_time, input_text, audio_file))
    
    conn.commit()
    conn.close()

@ai_voice_synthesis_bp.route('/', methods=['GET', 'POST'])
def index():
    form = TextToSpeechForm()
    
    if form.validate_on_submit():
        text = form.text.data
        if not text:
            flash('テキストを入力してください', 'danger')
            return redirect(url_for('ai_voice_synthesis.index'))
                
        voice_gender = form.voice_gender.data  # 選択された性別を取得

        # 音声モデルを選択
        if voice_gender == 'male':
            voice_model = 'alloy'
        else:
            voice_model = 'nova'

        # UUIDを使ってファイル名を生成
        unique_filename = str(uuid.uuid4()) + '.mp3'
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        #print(file_path)
        try:
            # OpenAIのAPIを使ってテキストを音声に変換
            with client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=voice_model,  # 選択された音声モデルを使用
                input=text
            ) as response:
              response.stream_to_file(file_path)
            # 履歴に保存
            save_history(text, unique_filename)
            
            # リダイレクトを使ってGETリクエストで結果を表示
            return redirect(url_for('ai_voice_synthesis.result', filename=unique_filename))
        except OpenAIError as e:
            flash(f"An error occurred while trying to fetch the audio stream: {e}", 'danger')       
            return redirect(url_for('ai_voice_synthesis.index'))
        except Exception as e:
            flash(f'音声合成に失敗しました: {str(e)}', 'danger')
            return redirect(url_for('ai_voice_synthesis.index'))
    
    return render_template('ai_voice_synthesis/upload.html', form=form)

@ai_voice_synthesis_bp.route('/result/<filename>')
def result(filename):
    return render_template('ai_voice_synthesis/result.html', audio_file=filename)

@ai_voice_synthesis_bp.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return jsonify({'download_url': url_for('static', filename='audio/' + filename)})
    else:
        flash('指定されたファイルが見つかりません', 'danger')
        return redirect(url_for('ai_voice_synthesis.index'))

@ai_voice_synthesis_bp.route("/history", methods=['GET', 'POST'])
def history():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == HISTORY_PASSWORD:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("SELECT id, datetime(timestamp, 'localtime'), input_text, audio_file FROM history ORDER BY timestamp DESC")
            history_data = c.fetchall()
            conn.close()
            return render_template('ai_voice_synthesis/history.html', history=history_data)
        else:
            flash("パスワードが正しくありません", "danger")
            return redirect(url_for('ai_voice_synthesis.history'))
    return render_template('ai_voice_synthesis/password_prompt.html')
