from flask import render_template, Blueprint


bp = Blueprint('renderers', __name__)


@bp.route('/addAuction')
def addAuction():
    return render_template("add-auction.html")

@bp.route('/addSingles')
def addSingles():
    return render_template("add-singles.html")

@bp.route('/collection')
def renderCollection():
    return render_template("collection.html")

@bp.route('/')
def renderAuctions():
    return render_template("index.html")

@bp.route('/renderAddCardsToCollection')
def renderAddCardsToCollection():
    return render_template("addCardsToCollection.html")


@bp.route('/sold')
def sold():
    return render_template("sold.html")