import os
import sqlite3
import re

from flask import Flask, render_template, request, redirect, url_for, make_response, flash
from flask_dance.contrib.discord import make_discord_blueprint, discord
from flask_dance.consumer import oauth_authorized
from oauthlib import oauth2
from dotenv import load_dotenv

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

load_dotenv('.env')
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_DANCE_SECRET")

blueprint = make_discord_blueprint(
    client_id=os.getenv('CLIENT_ID'), client_secret=os.getenv('CLIENT_SECRET'), scope=["identify", "guilds"],
        redirect_url=f"{os.getenv('ROOT_URI')}/login/authorized", authorized_url="/authorized",
)

app.register_blueprint(blueprint, url_prefix="/login")


@app.errorhandler(oauth2.MismatchingStateError)
def handle_user_cancel(e):
    return redirect(url_for("home"))


@app.errorhandler(404)
def handle_404(e):
    # return render_template('errors/404.html', allowed=discord.authorized)
    flash("That page doesn't exist.", "warning")
    return render_template('home.html', allowed=discord.authorized)


@app.errorhandler(TypeError)
def handle_weird_indices_error(e):
    if e == "list indices must be integers or slices, not str":
        flash("An error occurred rendering your servers, please try again.")
        return render_template("home.html")


@app.route("/")
def home():
    return render_template('home.html', allowed=discord.authorized)


@app.route("/dashboard/")
def hello():
    if not discord.authorized:
        return redirect(url_for("discord.login"))

    return redirect(url_for("servers_list"))


@app.route("/dashboard/servers/")
def servers_list():
    if not discord.authorized:
        return redirect(url_for("discord.login"))

    con = sqlite3.connect(f'{os.getenv("BOT_DIR")}db/database.sqlite3')
    cur = con.cursor()

    user = discord.get('https://discord.com/api/v7/users/@me')
    guilds = discord.get('https://discord.com/api/v7/users/@me/guilds')

    userd = user.json()
    userd['gif'] = True if userd['avatar'].endswith("_a") else False

    with con:
        cur.execute('SELECT id FROM config')
        current_aeon_guilds = cur.fetchall()

    ids = [row[0] for row in current_aeon_guilds]
    invite = []
    servers = []

    for guild in guilds.json():
        def append(list):
            gdict = {
                'name': guild['name'],
                'id': guild['id'],
            }

            if guild['icon']:
                gdict['url'] = f'https://cdn.discordapp.com/icons/{guild["id"]}/{guild["icon"]}.{"gif" if guild["icon"].endswith("_a") else "webp"}?size=256'
            else:
                initials = []

                for word in guild['name'].split(' '):
                    initials.append(word[0])

                gdict['initials'] = ''.join(initials)

            list.append(gdict)

        if (int(guild['permissions']) & 0x8) == 0x8 or guild['owner'] is True:
            if int(guild['id']) in ids:
                append(servers)
            else:
                append(invite)

    servers.sort(key=lambda x: x['name'].lower())
    invite.sort(key=lambda x: x['name'].lower())
    return render_template(
        "dashboard/servers.html",
        user=userd, servers=servers, invite=invite, count=[len(invite) + len(servers), len(servers)])


@app.route('/dashboard/edit/', methods=["GET", "POST"])
def edit_guild():  # sourcery no-metrics skip
    global display_guild
    if not discord.authorized:
        return redirect(url_for("discord.login"))

    guild = request.args.get('server')
    if not guild:
        flash("You need to provide a server ID.", "danger")
        return redirect(url_for("servers_list"))
    re.sub("[^0-9]", "", guild)

    if len(guild) != 18:
        if not guild:
            flash("You need to provide a server ID.", "danger")
            return redirect(url_for("servers_list"))

    con = sqlite3.connect(f'{os.getenv("BOT_DIR")}db/database.sqlite3')
    cur = con.cursor()

    with con:
        cur.execute('SELECT * FROM config WHERE id = :id', {'id': guild})
        tuple = cur.fetchone()

        if not tuple:
            flash("That server doesn't exist.", "danger")
            return redirect(url_for("servers_list"))

        config = [item for item in tuple]
        config.pop(0)

        pwc = True if config[6] == "ON" else False
        atc = True if config[0] == "ON" else False
        awc = True if config[3] == "ON" else False

    guilds = discord.get('https://discord.com/api/v7/users/@me/guilds')

    with con:
        cur.execute('SELECT id FROM config')
        current_aeon_guilds = cur.fetchall()

    ids = [row[0] for row in current_aeon_guilds]
    invite = []
    servers = []

    invite_ids = []
    server_ids = []

    for _guild in guilds.json():
        def append(list):
            list.append(
                {
                    'name': _guild['name'],
                    'id': _guild['id'],
                    'url': f'https://cdn.discordapp.com/icons/{_guild["id"]}/{_guild["icon"]}.webp?size=256' if _guild["icon"] else None
                }
            )

        if (int(_guild['permissions']) & 0x8) == 0x8 or _guild['owner'] is True:
            if int(_guild['id']) in ids:
                append(servers)
                server_ids.append(_guild['id'])
            else:
                append(invite)
                invite.append(_guild['id'])

    if str(guild) not in server_ids:
        if str(guild) in invite_ids:
            flash("Aeon is not in that server.")
            return redirect(url_for("servers_list"))

        flash("You don't have permission to manage that server.")
        return redirect(url_for("servers_list"))

    currguild = []

    for server in servers:
        if server["id"] == str(guild):
            currguild.append(server)

    if request.method == "POST":
        prefix = request.form["pfx"]
        pfx_warn = 'on' if 'pfx-warn' in request.form else 'off'

        as_toggle = 'on' if 'as-toggle' in request.form else 'off'
        as_words = request.form['as-words'] if 'as-words' in request.form else config[1]
        as_wc = 'on' if "as-wc" in request.form else 'off'

        if prefix:
            prefix = prefix.replace('"', "").replace("{s}", " ").replace(
                "`", "").replace("﷽", "").replace("'", "")

            if prefix in ["", " "]:
                flash("That prefix contains an invalid character.", "danger")
                return render_template('dashboard/form.html', config=config, currguild=currguild[0], pwc=pwc, atc=atc, awc=awc)

            with con:
                cur.execute('UPDATE config SET prefix = :prefix WHERE id = :id', {
                    'id': guild,
                    'prefix': prefix
                })

        if pfx_warn:
            with con:
                cur.execute('UPDATE config SET prefix_warn = :pw WHERE id = :id', {
                    'id': guild,
                    'pw': pfx_warn.upper()
                })

        if as_toggle:
            with con:
                cur.execute('UPDATE config SET delete_swear = :pw WHERE id = :id', {
                    'id': guild,
                    'pw': as_toggle.upper()
                })

        if as_words:
            with con:
                if as_words == "reset":
                    cur.execute('UPDATE config SET swears = :swears WHERE :id = id', {
                        'id': guild,
                        'swears': None
                    })
                else:
                    cur.execute('UPDATE config SET swears = :swears WHERE :id = id', {
                        'id': guild,
                        'swears': as_words.replace(" ", ", ")
                    })

        if as_wc:
            with con:
                cur.execute('UPDATE config SET wildcard = :as_wc WHERE :id = id', {
                    'id': guild,
                    'as_wc': as_wc.upper()
                })

        with con:
            cur.execute('SELECT * FROM config WHERE id = :id', {'id': guild})
            tuple = cur.fetchone()

            config = [item for item in tuple]
            config.pop(0)

            pwc = True if config[6] == "ON" else False
            atc = True if config[0] == "ON" else False
            awc = True if config[3] == "ON" else False

        flash("All Changes Saved.", "success")

    return render_template('dashboard/form.html', config=config, currguild=currguild[0], pwc=pwc, atc=atc, awc=awc)


@app.route("/dashboard/logout/")
def logout():
    if not discord.authorized:
        flash("You need to be logged in to log out.", "warning")
        return redirect(url_for('home'))

    resp = make_response(redirect(url_for('home')))
    resp.delete_cookie('session')

    return resp


@oauth_authorized.connect
def authorization_done(blueprint, token):
    blueprint.token = token
    return redirect(url_for('servers_list'))


if __name__ == "__main__":
    app.run(debug=True)
