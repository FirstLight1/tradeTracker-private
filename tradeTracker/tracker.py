from flask import url_for, Flask, request, g, render_template, Blueprint
import sqlite3

bp = Blueprint('track', __name__)


@bp.route('/')
def index():
    return render_template("index.html")