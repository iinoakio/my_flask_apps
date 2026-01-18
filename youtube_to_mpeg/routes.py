from flask import request, render_template, redirect, url_for, flash, jsonify
import os
import uuid
import sqlite3
import pytz
from datetime import datetime
from .forms import YoutubeToMpegForm
from . import youtube_to_mpeg_bp  # Blueprintをインポート
# from pytubefix import YouTube
# from pytubefix.cli import on_progress
# from pytubefix.exceptions import VideoUnavailable
from yt_dlp import YoutubeDL
import urllib.request, urllib.error

# 保存先ディレクトリの設定
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/video')
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
                  video_file TEXT)''')
    conn.commit()
    conn.close()

init_db()

# 既存:
# def ytdlp_download(url: str, outtmpl: str, mode: str = "mp4") -> str:
#     if mode == "mp3":
#         ydl_opts = { ... }
#     else:
#         ydl_opts = { ... }
#     with YoutubeDL(ydl_opts) as ydl: ...

# 置き換え（共通オプションをまとめ、Cookie/IPv4/UA等を追加）
def ytdlp_download(url: str, outtmpl: str, mode: str = "mp4") -> str:
    # 1) cookies.txt の場所（環境変数 > 同階層）
    cookie_path = os.environ.get("YTDLP_COOKIES") or os.path.join(os.path.dirname(__file__), "cookies.txt")
    use_cookie = os.path.exists(cookie_path)

    common_opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "no_warnings": True,

        # 2) IPv4 強制（EC2でIPv6→403回避に効くことが多い）
        "source_address": "0.0.0.0",

        # 3) 実ブラウザに近いHTTPヘッダ
        "http_headers": {
            # 適当な最新Chrome UAでOK（固定化で十分）
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.youtube.com/",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        },

        # 4) ダウンロードの挙動を少し穏やかに
        "sleep_interval": 1,
        "max_sleep_interval": 2,
        "throttledratelimit": 1_000_000,  # 1MB/s程度に抑制（任意）

        # 5) （任意）抽出器ワークアラウンド：最近の403/署名絡みで効くことがある
        #   効かない場合は削ってOK
        "extractor_args": {
            "youtube": {
                "player_client": "default,-tv_html5,-tv_html5_leanback",
            }
        },
    }
    if use_cookie:
        common_opts["cookiefile"] = cookie_path

    if mode == "mp3":
        ydl_opts = {
            **common_opts,
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
            ],
        }
    else:
        ydl_opts = {
            **common_opts,
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
        }

    from yt_dlp import YoutubeDL
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        base, _ = os.path.splitext(path)
        return base + ".mp3" if mode == "mp3" else (base + ".mp4" if os.path.exists(base + ".mp4") else path)


# ② index() 内で選択値を読む & 呼び出しを切替
@youtube_to_mpeg_bp.route('/', methods=['GET', 'POST'])
def index():
    clear_upload_folder()

    form = YoutubeToMpegForm()
    if form.validate_on_submit():
        url_text = form.text.data
        # 追加：UIから出力形式を取得（デフォルトmp4）
        selected_fmt = request.form.get('format', 'mp4')

        try:
            f = urllib.request.urlopen(url_text)
            f.close()
        except:
            flash('有効なURLを指定してください', 'danger')
            return redirect(url_for('youtube_to_mpeg.index'))

        try:
            # 出力テンプレ
            outtmpl = os.path.join(UPLOAD_FOLDER, "%(title)s.%(ext)s")
            # 変更：モードを渡す
            filepath = ytdlp_download(url_text, outtmpl, mode=selected_fmt)

            if not os.path.exists(filepath):
                flash("出力ファイルが見つかりません。", "danger")
                return redirect(url_for('youtube_to_mpeg.index'))

            filename = os.path.basename(filepath)
            save_history(url_text, filename)
            return redirect(url_for('youtube_to_mpeg.result', filename=filename))

        except Exception as e:
            # ここ、原因の一部を出すとデバッグが楽（本番はログにだけ出す等でもOK）
            flash(f"リンク先からダウンロードできません: {str(e)}", 'danger')
            return redirect(url_for('youtube_to_mpeg.index'))

    if form.errors:
        for error in form.errors['text']:
            flash(error, 'danger')
    return render_template('youtube_to_mpeg/upload.html', form=form)


def clear_upload_folder():
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # ファイルを削除
            elif os.path.isdir(file_path):
                os.rmdir(file_path)  # サブフォルダを削除（必要なら再帰処理を追加）
        except Exception as e:
            flash(e, 'danger')
            return redirect(url_for('youtube_to_mpeg.index'))

@youtube_to_mpeg_bp.route('/result/<filename>')
def result(filename):
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        flash(f'指定されたファイルは存在しません:{filename}', 'danger')
        return redirect(url_for('youtube_to_mpeg.index'))
    
    return render_template('youtube_to_mpeg/result.html', video_file=filename)


def save_history(input_text, video_file):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # 現在の日時をJSTで取得
    current_time = datetime.now(jst)
    c.execute("INSERT INTO history (timestamp, input_text, video_file) VALUES (?, ?, ?)",
              (current_time, input_text, video_file))
    
    conn.commit()
    conn.close()

@youtube_to_mpeg_bp.route("/history", methods=['GET', 'POST'])
def history():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == HISTORY_PASSWORD:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("SELECT id, datetime(timestamp, 'localtime'), input_text, video_file FROM history ORDER BY timestamp DESC")
            history_data = c.fetchall()
            conn.close()
            return render_template('youtube_to_mpeg/history.html', history=history_data)
        else:
            flash("パスワードが正しくありません", "danger")
            return redirect(url_for('youtube_to_mpeg.history'))

    return render_template('youtube_to_mpeg/password_prompt.html')
