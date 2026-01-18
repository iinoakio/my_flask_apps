import os, platform
from flask import Flask, render_template, url_for, request, flash, redirect
from ai_image_analysis import ai_image_analysis_bp
from ai_voice_synthesis import ai_voice_synthesis_bp
# from ai_remove_background import ai_remove_background_bp
from youtube_to_mpeg import youtube_to_mpeg_bp
from bakusai_db import bakusai_db_bp
from kakei_db import kakei_db_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'Canon-01')  # 環境変数から読み込む
APP_PASSWORD = 'Canon-01'  # セキュリティ強化のため環境変数に保存推奨

# Blueprintをアプリケーションに登録
app.register_blueprint(ai_image_analysis_bp, url_prefix='/ai_image_analysis')
app.register_blueprint(ai_voice_synthesis_bp, url_prefix='/ai_voice_synthesis')
# app.register_blueprint(ai_remove_background_bp, url_prefix='/ai_remove_background')
app.register_blueprint(youtube_to_mpeg_bp, url_prefix='/youtube_to_mpeg')
app.register_blueprint(bakusai_db_bp, url_prefix='/bakusai_db')
app.register_blueprint(kakei_db_bp, url_prefix='/kakei_db')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == APP_PASSWORD:
            return redirect(url_for('bakusai_db.index'))
        else:
            #flash('パスワードが間違っています。')
            return render_template('admin_login.html')
    return render_template('admin_login.html')

@app.route('/admin-login2', methods=['GET', 'POST'])
def admin_login2():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == APP_PASSWORD:
            return redirect(url_for('kakei_db.index'))
        else:
            #flash('パスワードが間違っています。')
            return render_template('admin_login.html')
    return render_template('admin_login.html')

if __name__ == '__main__':
    if platform.system() == "Windows":
        app.run(host='0.0.0.0', debug=True)
    else:
        app.run()    
    