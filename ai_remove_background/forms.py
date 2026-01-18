from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField
from wtforms.validators import DataRequired

class ImageUploadForm(FlaskForm):
    file = FileField('画像ファイルを選択してください', validators=[DataRequired()])
    submit = SubmitField('アップロード')
