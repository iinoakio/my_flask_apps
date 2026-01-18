from flask import request, render_template, redirect, url_for, flash, jsonify
import os
import uuid
import sqlite3
import pytz
from datetime import datetime
from .forms import BakusaiDbForm
from . import bakusai_db_bp  # Blueprintをインポート

# 保存先ディレクトリの設定
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/pdf')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# データベースのパスを指定
DATABASE = os.path.join(os.path.dirname(__file__), 'history.db')

# BAKUSAIデータベースのパスを指定
BAKUSAI_DB = os.path.join(os.path.dirname(__file__), 'Bakusai_New_search.db')

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
                  input_text TEXT) ''')
    conn.commit()
    conn.close()

init_db()

def list_tab_sheets():
    """
    BAKUSAI_DBの全tab_sheet名とデータベースの更新日時を取得
    """
    tab_sheets = []
    updated_at = "不明"

    query = "SELECT DISTINCT tab_sheet FROM data ORDER BY tab_sheet ASC"

    try:
        conn = sqlite3.connect(BAKUSAI_DB)
        cursor = conn.cursor()
        
        # tab_sheet一覧の取得
        cursor.execute(query)
        tab_sheets = [row[0] for row in cursor.fetchall()]

        # データベースの最終更新日時を取得（ファイルのメタ情報から取得）
        if os.path.exists(BAKUSAI_DB):
            updated_at = datetime.fromtimestamp(os.path.getmtime(BAKUSAI_DB)).strftime("%Y-%m-%d %H:%M:%S")

    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        conn.close()

    return tab_sheets, updated_at

@bakusai_db_bp.route('/tab/<db_name>')
def tab_detail(db_name):
    """
    特定の tab_sheet（＝地域・スレッド）内の全データを一覧表示
    """
    try:
        conn = sqlite3.connect(BAKUSAI_DB)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM data
            WHERE tab_sheet = ?
            ORDER BY date ASC, time ASC
        """, (db_name,))
        records = cursor.fetchall()
    except sqlite3.Error as e:
        flash(f"データベースエラー: {e}", 'danger')
        records = []
    finally:
        conn.close()
    
    if not records:
        flash("該当するデータが見つかりませんでした。", "warning")
    
    return render_template('bakusai_db/tab_detail.html', records=records, db_name=db_name)


@bakusai_db_bp.route('/', methods=['GET', 'POST'])
def index():
    # PDFォルダを空にする #
    clear_upload_folder()
    
    form = BakusaiDbForm()
    if form.validate_on_submit():
        search_text = form.text.data.strip()  # 入力された検索語を取得し、前後の空白を削除

        # 検索語が空の場合はDB中のtab_sheet名を列挙
        if not search_text:
            tab_sheets, created_at = list_tab_sheets()
            return render_template('bakusai_db/tab_sheet_list.html', tab_sheets=tab_sheets, created_at=created_at)

        try:
             # 検索語をスペースで区切る
            parts = search_text.split()
            if len(parts) != 2:
                raise ValueError("検索語はスペースで区切られた2つの単語である必要があります。")
            db_name = parts[0]  # 最初の単語をdb_nameに代入
            person = parts[1]  # 2つ目の単語をpersonに代入

            # データベース検索
            results = search_bakusai_db(db_name, person)
            if not results:
                flash("該当するデータが見つかりませんでした。", 'warning')
                return redirect(url_for('bakusai_db.index'))
            
            # 結果を一時ファイルやテンプレートに渡して表示する
            save_history(search_text)
            # リダイレクトを使ってGETリクエストで結果を表示
            return render_template('bakusai_db/result.html', results=results, db_name=db_name, person=person)

        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('bakusai_db.index'))

        
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'danger')
    return render_template('bakusai_db/upload.html', form=form)

@bakusai_db_bp.route('/detail/<db_name>/<id>', methods=['GET'])
def detail(db_name, id):
    """
    特定のDBとIDの詳細情報、および前後15件を表示するエンドポイント
    """
    detail = None
    surrounding_records = []
    try:
        # データベースに接続
        conn = sqlite3.connect(BAKUSAI_DB)
        cursor = conn.cursor()

        # 指定されたIDの詳細情報を取得
        query_detail = """
            SELECT * FROM data
            WHERE tab_sheet = ? AND id = ?
        """
        cursor.execute(query_detail, (db_name, id))
        detail = cursor.fetchone()

        if detail:
            # 前後15件を取得
            query_surrounding = """
                SELECT * FROM data
                WHERE tab_sheet = ?
                ORDER BY date ASC, time ASC
                LIMIT 31 OFFSET (
                    SELECT COUNT(*) FROM data
                    WHERE tab_sheet = ? AND (date < ? OR (date = ? AND time < ?))
                ) - 15
            """
            cursor.execute(query_surrounding, (
                db_name, db_name, detail[2], detail[2], detail[3]
            ))
            surrounding_records = cursor.fetchall()

    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
        detail = None

    finally:
        conn.close()

    if not detail:
        return render_template('bakusai_db/no_result.html', db_name=db_name, id=id)

    return render_template(
        'bakusai_db/detail.html',
        detail=detail,
        surrounding_records=surrounding_records
    )


def search_bakusai_db(db_name, person):
    """
    BAKUSAI_DBを検索し、条件に一致する結果を返す
    """
    results = []
    query = """
        SELECT * FROM data
        WHERE tab_sheet LIKE ? AND text LIKE ?
        ORDER BY date ASC, time ASC
    """

    try:
        # データベースに接続
        conn = sqlite3.connect(BAKUSAI_DB)
        cursor = conn.cursor()

        # クエリ実行
        cursor.execute(query, (f"%{db_name}%", f"%{person}%"))
        results = cursor.fetchall()

    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")

    finally:
        conn.close()
    
    return results

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
            return redirect(url_for('bakusai_db.index'))

def save_history(input_text):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # 現在の日時をJSTで取得
    current_time = datetime.now(jst)
    c.execute("INSERT INTO history (timestamp, input_text) VALUES (?, ?)",
              (current_time, input_text))
    
    conn.commit()
    conn.close()

@bakusai_db_bp.route("/history", methods=['GET', 'POST'])
def history():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == HISTORY_PASSWORD:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("SELECT id, datetime(timestamp, 'localtime'), input_text FROM history ORDER BY timestamp DESC")
            history_data = c.fetchall()
            conn.close()
            return render_template('bakusai_db/history.html', history=history_data)
        else:
            flash("パスワードが正しくありません", "danger")
            return redirect(url_for('bakusai_db.history'))

    return render_template('bakusai_db/password_prompt.html')
