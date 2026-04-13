from flask import render_template, Blueprint


bp = Blueprint('renderers', __name__)


@bp.route('/addAuction')
@verify_token
def addAuction():
    return render_template("add-auction.html")

@bp.route('/addSingles')
@verify_token
def addSingles():
    return render_template("add-singles.html")

@bp.route('/collection')
@verify_token
def renderCollection():
    return render_template("collection.html")

@bp.route('/')
@verify_token
def renderAuctions():
    return render_template("index.html")

@bp.route('/renderAddCardsToCollection')
@verify_token
def renderAddCardsToCollection():
    return render_template("addCardsToCollection.html")


@bp.route('/sold')
@verify_token
def sold():
    return render_template("sold.html")
