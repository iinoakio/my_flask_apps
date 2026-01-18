from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField, RadioField
from wtforms.validators import DataRequired, Length

class TextToSpeechForm(FlaskForm):
    # テキストフィールドに300文字の制限を追加
    text = TextAreaField('テキストを入力してください', validators=[DataRequired(message="テキストは必須です。"), Length(max=300, message="テキストは300文字以内で入力してください。")])
    
    # 性別選択用のラジオボタンフィールドを追加
    voice_gender = RadioField('音声の性別を選択してください', choices=[('male', '男性'), ('female', '女性')], default='male', validators=[DataRequired(message="性別を選択してください。")])
    
    submit = SubmitField('音声合成を実行')
