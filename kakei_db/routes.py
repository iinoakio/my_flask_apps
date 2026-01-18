from flask import request, render_template, redirect, url_for, flash, jsonify
import os
import uuid
import sqlite3
import pytz
from datetime import datetime, timedelta

from .forms import KakeiDbForm
from . import kakei_db_bp  # Blueprintをインポート

# 保存先ディレクトリの設定
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# データベースのパスを指定
DATABASE = os.path.join(os.path.dirname(__file__), 'history.db')

# KAKEIデータベースのパスを指定
KAKEI_DB = os.path.join(os.path.dirname(__file__), 'Kakei.db')

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


@kakei_db_bp.route('/', methods=['GET', 'POST'])
def index():
    clear_upload_folder()
    form = KakeiDbForm()

    # 大項目・中項目のマスタを取得
    categories, subcategories_map = get_categories_from_db()    

    if form.validate_on_submit():

        period = request.form.get('period', 'this_month')
        same_month = request.form.get('same_month', datetime.now().strftime('%m'))

        # ✅ 大項目・中項目の選択（複数可）
        selected_categories = request.form.getlist('categories')
        selected_subcategories = request.form.getlist('subcategory')

        # 月名の取得用（例: March）
        month_int = int(same_month)
        label = ""
        if period == "same_month_past":
            month_jp = f"{month_int}月"
            label = f"{month_jp}の過去データ"
        elif period == "this_month":
            label = "当月のデータ"
        elif period == "past_3_months":
            label = "過去3か月のデータ"
        elif period == "past_1_year":
            label = "過去1年のデータ"
        elif period == "past_2_years":
            label = "過去2年のデータ"
        elif period == "all":
            label = "全期間のデータ"

        try:
            # ✅ 検索関数に条件を渡す
            results = search_kakei_db(
                period=period,
                same_month=same_month,
                categories=selected_categories,
                subcategories=selected_subcategories
            )

            if not results:
                flash("該当するデータが見つかりませんでした。", 'warning')
                return redirect(url_for('kakei_db.index'))

            label = f"集計期間: {period} / 大項目: {', '.join(selected_categories) or 'すべて'} / 中項目: {', '.join(selected_subcategories) or 'すべて'}"

            save_history(f"期間: {period}")
            return render_template(
               "kakei_db/result.html",
                results=results,
                label=label,
                selected_majors=selected_categories,      # 追加
                selected_minors=selected_subcategories    # 追加
            )
        
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('kakei_db.index'))

    # 初期表示（GET時）
    return render_template('kakei_db/upload.html',
                           form=form,
                           categories=categories,
                           subcategories_map=subcategories_map)

def get_categories_from_db():
    conn = sqlite3.connect(KAKEI_DB)
    cursor = conn.cursor()

    # 大項目一覧
    cursor.execute('SELECT DISTINCT "大項目" FROM kakeibo WHERE "大項目" IS NOT NULL')
    categories = [row[0] for row in cursor.fetchall()]

    # 大項目ごとの中項目一覧
    cursor.execute('SELECT DISTINCT "大項目", "中項目" FROM kakeibo WHERE "大項目" IS NOT NULL AND "中項目" IS NOT NULL')
    mapping = {}
    for cat, sub in cursor.fetchall():
        mapping.setdefault(cat, []).append(sub)

    conn.close()
    return categories, mapping

def search_kakei_db(period, same_month=None, categories=None, subcategories=None):
    results = []
    today = datetime.now()
    end_date = today.strftime('%Y-%m-%d')

    base_query = """
        SELECT 
            SUBSTR("日付", 1, 4) AS year,
            SUBSTR("日付", 6, 2) AS month,
            SUM("金額（円）") AS total
        FROM kakeibo
        WHERE 1=1
    """
    params = []

    # ✅ 同月過去（特別処理：月だけでフィルタ）
    if period == "same_month_past":
        base_query += ' AND strftime("%m", "日付") = ?'
        params.append(same_month)

    # ✅ 通常の期間（BETWEEN 日付指定）
    else:
        start_date = "1900-01-01"
        if period == "this_month":
            start_date = today.replace(day=1).strftime('%Y-%m-%d')
        elif period == "past_3_months":
            year = today.year
            month = today.month - 2
            if month <= 0:
                year -= 1
                month += 12
            start_date = datetime(year, month, 1).strftime('%Y-%m-%d')
        elif period == "past_1_year":
            year = today.year - 1
            month = today.month + 1
            if month > 12:
                year += 1
                month = 1
            start_date = datetime(year, month, 1).strftime('%Y-%m-%d')
        elif period == "past_2_years":
            year = today.year - 2
            month = today.month + 1
            if month > 12:
                year += 1
                month = 1
            start_date = datetime(year, month, 1).strftime('%Y-%m-%d')

        base_query += ' AND "日付" BETWEEN ? AND ?'
        params.extend([start_date, end_date])

    # ✅ 大項目フィルタ（複数選択可）
    if categories:
        placeholders = ','.join(['?'] * len(categories))
        base_query += f' AND "大項目" IN ({placeholders})'
        params.extend(categories)

    # ✅ 中項目フィルタ（複数選択可）
    if subcategories:
        placeholders = ','.join(['?'] * len(subcategories))
        base_query += f' AND "中項目" IN ({placeholders})'
        params.extend(subcategories)

    # ✅ 集計・並び順
    base_query += """
        GROUP BY year, month
        ORDER BY year ASC, CAST(month AS INTEGER) ASC
    """

    # ✅ 実行
    try:
        conn = sqlite3.connect(KAKEI_DB)
        cursor = conn.cursor()
        cursor.execute(base_query, params)
        results = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        conn.close()

    return results

@kakei_db_bp.route("/details")
def details():
    """
    指定の 年・月（＋任意の大項目/中項目）で内訳をJSONで返す。
    例:
      GET /details?year=2025&month=07
      GET /details?year=2025&month=07&major=食費&minor=外食&minor=カフェ
    """
    year  = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    majors = request.args.getlist("major")  # 大項目（複数可）
    minors = request.args.getlist("minor")  # 中項目（複数可）

    if not year or not month:
        return jsonify({"ok": False, "error": "year/month is required"}), 400

    # 年・月で絞る
    where = ['strftime("%Y", "日付") = ?', 'strftime("%m", "日付") = ?']
    params = [f"{year:04d}", f"{month:02d}"]

    # 大項目・中項目の任意フィルタ
    if majors:
        where.append('"大項目" IN (%s)' % ",".join(["?"] * len(majors)))
        params.extend(majors)
    if minors:
        where.append('"中項目" IN (%s)' % ",".join(["?"] * len(minors)))
        params.extend(minors)

    sql = f"""
        SELECT
            "日付"        AS date,
            "内容"        AS content,
            "大項目"      AS major,
            "中項目"      AS minor,
            "金額（円）"  AS amount
        FROM kakeibo
        WHERE {' AND '.join(where)}
        ORDER BY "日付" ASC, "金額（円）" DESC
    """

    # 実行
    conn = sqlite3.connect(KAKEI_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    # JSON 整形（金額は数値保証）
    items = []
    for r in rows:
        amt = r["amount"]
        if isinstance(amt, (int, float)):
            amount_num = int(amt)
        else:
            s = (str(amt) if amt is not None else "").replace(",", "").replace("¥", "").replace("円", "")
            try:
                amount_num = int(float(s)) if s else 0
            except Exception:
                amount_num = 0
        items.append({
            "date":   r["date"],
            "content": r["content"],
            "major":  r["major"],
            "minor":  r["minor"],
            "amount": amount_num
        })

    return jsonify({"ok": True, "items": items, "count": len(items)})

@kakei_db_bp.route("/drilldown")
def drilldown():
    # ---- 入力取得・正規化 ----
    year  = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    level = (request.args.get("level") or "").strip().lower()
    major = request.args.get("major")
    minor = request.args.get("minor")

    # 画面で選ばれた事前フィルタ（複数）
    majors_selected = request.args.getlist("majors")  # ?majors=食費&majors=日用品...
    minors_selected = request.args.getlist("minors")  # ?minors=外食&minors=カフェ...

    # ---- バリデーション（必ず return する）----
    if not year or not month:
        return jsonify({"ok": False, "error": "year/month required"}), 400
    if level not in {"major", "minor", "detail"}:
        return jsonify({"ok": False, "error": "invalid level"}), 400

    y = f"{year:04d}"
    m = f"{month:02d}"

    base_where = ['strftime("%Y","日付")=?', 'strftime("%m","日付")=?']
    params = [y, m]

    # 事前選択フィルタ（ある場合のみ適用）
    if majors_selected:
        base_where.append('"大項目" IN ({})'.format(",".join(["?"] * len(majors_selected))))
        params.extend(majors_selected)
    if minors_selected:
        base_where.append('"中項目" IN ({})'.format(",".join(["?"] * len(minors_selected))))
        params.extend(minors_selected)

    # ---- レベル別のSQLを用意（どの分岐でも sql/params を必ず用意）----
    if level == "major":
        sql = f"""
            SELECT "大項目" AS major, SUM("金額（円）") AS amount
            FROM kakeibo
            WHERE {' AND '.join(base_where)}
            GROUP BY "大項目"
            ORDER BY amount DESC
        """

    elif level == "minor":
        if not major:
            return jsonify({"ok": False, "error": "major required"}), 400
        sql = f"""
            SELECT "中項目" AS minor, SUM("金額（円）") AS amount
            FROM kakeibo
            WHERE {' AND '.join(base_where)} AND "大項目"=?
            GROUP BY "中項目"
            ORDER BY amount DESC
        """
        params.append(major)

    else:  # detail
        if not (major and minor):
            return jsonify({"ok": False, "error": "major/minor required"}), 400
        sql = f"""
            SELECT
                "日付"       AS date,
                "内容"       AS content,
                "大項目"     AS major,
                "中項目"     AS minor,
                "金額（円）" AS amount
            FROM kakeibo
            WHERE {' AND '.join(base_where)} AND "大項目"=? AND "中項目"=?
            ORDER BY "日付" ASC, "金額（円）" DESC
        """
        params.extend([major, minor])

    # ---- 実行（例外時も必ず return）----
    conn = None
    try:
        conn = sqlite3.connect(KAKEI_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
    except Exception as e:
        if conn:
            conn.close()
        # ここで必ず return
        return jsonify({"ok": False, "error": f"query failed: {e}"}), 500
    finally:
        if conn:
            conn.close()

    # ---- 整形して返す（必ず return）----
    def to_int(v):
        if isinstance(v, (int, float)):
            return int(v)
        s = (str(v) if v is not None else "").replace(",", "").replace("¥", "").replace("円", "")
        try:
            return int(float(s)) if s else 0
        except Exception:
            return 0

    if level == "major":
        items = [{"major": r["major"], "amount": to_int(r["amount"])} for r in rows]
    elif level == "minor":
        items = [{"minor": r["minor"], "amount": to_int(r["amount"])} for r in rows]
    else:
        items = [{
            "date": r["date"], "content": r["content"],
            "major": r["major"], "minor": r["minor"],
            "amount": to_int(r["amount"])
        } for r in rows]

    return jsonify({"ok": True, "level": level, "items": items, "count": len(items)})


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
            return redirect(url_for('kakei_db.index'))

def save_history(input_text):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # 現在の日時をJSTで取得
    current_time = datetime.now(jst)
    c.execute("INSERT INTO history (timestamp, input_text) VALUES (?, ?)",
              (current_time, input_text))
    
    conn.commit()
    conn.close()

@kakei_db_bp.route("/history", methods=['GET', 'POST'])
def history():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == HISTORY_PASSWORD:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("SELECT id, datetime(timestamp, 'localtime'), input_text FROM history ORDER BY timestamp DESC")
            history_data = c.fetchall()
            conn.close()
            return render_template('kakei_db/history.html', history=history_data)
        else:
            flash("パスワードが正しくありません", "danger")
            return redirect(url_for('kakei_db.history'))

    return render_template('kakei_db/password_prompt.html')
