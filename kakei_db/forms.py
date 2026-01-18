from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, URL

class KakeiDbForm(FlaskForm):
    # テキストフィールドに300文字の制限を追加
    submit = SubmitField('ＤＢを生成')
