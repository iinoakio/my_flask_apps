from flask import Blueprint

ai_image_analysis_bp = Blueprint('ai_image_analysis', __name__,
                                 template_folder='templates',
                                 static_folder='static')

from . import routes
