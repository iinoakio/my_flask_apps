from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, URL

class YoutubeToMpegForm(FlaskForm):
    # テキストフィールドに300文字の制限を追加
    text = StringField('DLしたいYoutubeのリンクを貼ってください', validators=[DataRequired(message="テキストは必須です。"), Length(max=300, message="テキストは300文字以内で入力してください。")])
    submit = SubmitField('ＤＬを実行')
