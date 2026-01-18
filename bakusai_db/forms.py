from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, URL

class BakusaiDbForm(FlaskForm):
    # テキストフィールドに300文字の制限を追加
    text = StringField('DBを生成するための検索ワードを設定してください')
    submit = SubmitField('ＤＢを生成')
