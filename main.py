import os
import sqlite3

from flask import Flask, render_template, request, redirect, url_for, make_response
import dotenv

from flask_dance.contrib.discord import make_discord_blueprint, discord
from flask_dance.consumer import oauth_authorized

from oauthlib import oauth2

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

dotenv.load_dotenv('.env')
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_DANCE_SECRET")


blueprint = make_discord_blueprint(
    client_id=os.getenv('CLIENT_ID'),
    client_secret=os.getenv('CLIENT_SECRET'),
    scope=["identify", "guilds"],
    redirect_url="http://127.0.0.1:5000/login/dashboard/authexit",
    authorized_url="/dashboard/authexit",
)
app.register_blueprint(blueprint, url_prefix="/login")


@app.errorhandler(oauth2.MismatchingStateError)
def handle_user_cancel(e):
    return redirect(url_for("home"))


@app.route('/error')
def error():
    title = request.args.get('title')
    desc = request.args.get('desc')
    return render_template("error.html", title=title, desc=desc)


@app.route("/")
def home():
    return "welcome to aeon funny :sunglass:<br>currently doesnt work"


@app.route("/dashboard/")
def hello():
    if not discord.authorized:
        return redirect(url_for("discord.login"))

    return redirect(url_for("servers_list"))


@app.route("/dashboard/servers/")
def servers_list():
    if not discord.authorized:
        return redirect(url_for("discord.login"))

    allowed_servers = []
    partial_servers = []

    allowed_servers.sort(key=lambda x: x["id"])
    return render_template("servers.html", servers=allowed_servers, partial=partial_servers)


@app.route('/dashboard/edit/')
def edit_guild():
    if not discord.authorized:
        return redirect(url_for("discord.login"))
    
    guild = request.args.get('server')

    try:
        guild = abs(int(guild))
    except Exception:
        guild = None

    if not guild or len(str(guild)) != 18:
        return "bruh"

    con = sqlite3.connect('../Aeon-Bot/db/database.sqlite3')
    cur = con.cursor()

    with con:
        cur.execute('SELECT * FROM config WHERE id = :id', {'id': str(guild)})
        tags = cur.fetchone()

    return str(tags)


@app.route("/dashboard/logout/")
def logout():
    if not discord.authorized:
        return redirect(url_for('error', title="You are not logged in", desc="You need to be logged in to log out."))

    resp = make_response(redirect(url_for('home')))
    resp.delete_cookie('session')

    return resp


@oauth_authorized.connect
def authorization_done(blueprint, token):
    blueprint.token = token
    return redirect(url_for('servers_list'))


if __name__ == "__main__":
    app.run(debug=True)
