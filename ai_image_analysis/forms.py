from wtforms import ValidationError, StringField, PasswordField, SubmitField, FileField
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Email, EqualTo


"""
class UserRegisterForm(FlaskForm):
  email = StringField('メールアドレス', validators=[DataRequired(), Email(message='正しいメールアドレスを入力してください')])
  username = StringField('ユーザー名', validators=[DataRequired()])
  password = PasswordField('パスワード', validators=[DataRequired(), EqualTo("pass_confirm", message='パスワードが一致していません')])
  pass_confirm = PasswordField('パスワード(確認)', validators=[DataRequired()])
  file = FileField('送信ファイル',validators=[DataRequired()])
  submit = SubmitField('登録')   
"""

class FileRegisterForm(FlaskForm):
  file = FileField('分析する画像ファイル',validators=[DataRequired()])
  submit = SubmitField('分析')     