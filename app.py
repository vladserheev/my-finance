"""Мала веб-сторінка для телефона: вхід за паролем, звіт за місяць і форма «Додати готівкову витрату».

Налаштування лише зі змінних середовища (у коді й репозиторії паролів немає):
  OLYA_LOGIN, OLYA_PASSWORD_HASH   — логін Олі і хеш її пароля;
  MARKO_LOGIN, MARKO_PASSWORD_HASH — логін Марка і хеш його пароля;
  SECRET_KEY                       — довгий випадковий рядок для підпису сесії.
Паролі зберігаються лише як хеші (як зробити хеш, див. README). Кожен бачить тільки свої дані.
Без цих змінних сторінка нічого не показує (відповідь 503).
Локальний запуск без HTTPS: ALLOW_HTTP=1 uv run flask --app app run
"""
import hmac
import os
import re
import secrets
import time
from datetime import date
from decimal import Decimal

from flask import Flask, abort, redirect, render_template_string, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

import tracker

ALLOW_HTTP = os.environ.get("ALLOW_HTTP") == "1"

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # хостинг передає, що зовні це HTTPS
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", ""),
    SESSION_COOKIE_SECURE=not ALLOW_HTTP,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14,
)

FAILED_LOGINS = []  # час невдалих спроб входу; після 8 за 10 хвилин вхід тимчасово закритий
MAX_FAILS, WINDOW = 8, 600


USER_VARS = {"olya": ("OLYA_LOGIN", "OLYA_PASSWORD_HASH"), "marko": ("MARKO_LOGIN", "MARKO_PASSWORD_HASH")}


def configured():
    names = ["SECRET_KEY"] + [v for pair in USER_VARS.values() for v in pair]
    if not all(os.environ.get(k) for k in names):
        return False
    for _, hash_var in USER_VARS.values():
        if not re.match(r"^(pbkdf2:\w+:\d+|scrypt:\d+:\d+:\d+)\$[^$]+\$[0-9a-f]+$", os.environ[hash_var]):
            app.logger.error("%s має неправильний формат: хеш має починатися з pbkdf2:sha256:... і містити два символи $", hash_var)
            return False
    return True


def zl(x):
    return f"{Decimal(x):,.2f}".replace(",", " ").replace(".", ",") + " зл"


app.jinja_env.filters["zl"] = zl


@app.before_request
def guard():
    if not configured():
        abort(503)
    if not ALLOW_HTTP and not request.is_secure:
        return redirect(request.url.replace("http://", "https://", 1), code=301)
    if request.endpoint not in ("login",) and not session.get("user"):
        return redirect(url_for("login"))


@app.after_request
def headers(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'unsafe-inline'; form-action 'self'"
    if not ALLOW_HTTP:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    return resp


@app.errorhandler(503)
def unavailable(_):
    return "Сервіс не налаштований.", 503


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def check_csrf():
    sent = request.form.get("csrf", "")
    if not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(400)


app.jinja_env.globals["csrf_token"] = csrf_token

PAGE = """<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Фінанси Олі й Марка</title>
<style>
:root{--bg:#fff;--fg:#1d1f23;--muted:#666;--line:#e1e3e6;--card:#f5f6f8;--accent:#2a6fdb;--bad:#b3261e;--ok:#1b7a3d}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--fg:#e8e8e8;--muted:#a0a4ab;--line:#33373d;--card:#1f2227;--accent:#6aa3ff;--bad:#ff8a80;--ok:#6fd08c}}
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:16px;max-width:640px;margin-inline:auto;line-height:1.45}
h1{font-size:1.3rem;margin:.2rem 0 .8rem}h2{font-size:1.05rem;margin:1.6rem 0 .5rem}
.top{display:flex;justify-content:space-between;align-items:center}
.top form{margin:0}
.tabs{display:flex;gap:8px;margin:.4rem 0}
.tabs a{flex:1;text-align:center;padding:10px;border:1px solid var(--line);border-radius:8px;color:var(--fg);text-decoration:none}
.tabs a.on{background:var(--accent);border-color:var(--accent);color:#fff}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:.8rem 0}
.card{background:var(--card);border-radius:10px;padding:12px}
.card small{color:var(--muted);display:block}.card b{font-size:1.15rem}
table{width:100%;border-collapse:collapse}td,th{padding:8px 4px;border-bottom:1px solid var(--line);text-align:right}
td:first-child,th:first-child{text-align:left}
.note{color:var(--muted);font-size:.9rem}.warn{color:var(--bad)}.ok{color:var(--ok)}
label{display:block;margin:.7rem 0 .2rem;font-size:.9rem;color:var(--muted)}
input,select,button{width:100%;font:inherit;padding:12px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg)}
button{background:var(--accent);border-color:var(--accent);color:#fff;margin-top:1rem;font-weight:600}
button.link{width:auto;background:none;color:var(--accent);border:none;margin:0;padding:6px;font-weight:400}
.msg{padding:10px 12px;border-radius:8px;margin:.8rem 0;background:var(--card)}
</style></head><body>
{{ body|safe }}
</body></html>"""

LOGIN = """
<h1>Фінанси Олі й Марка</h1>
{% if error %}<div class="msg warn">{{ error }}</div>{% endif %}
<form method="post">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<label for="u">Логін</label><input id="u" name="user" autocomplete="username" required>
<label for="p">Пароль</label><input id="p" name="password" type="password" autocomplete="current-password" required>
<button type="submit">Увійти</button>
</form>"""

REPORT = """
<div class="top"><h1>{{ name }}: фінанси</h1>
<form method="post" action="{{ url_for('logout') }}"><input type="hidden" name="csrf" value="{{ csrf_token() }}"><button class="link">Вийти</button></form></div>
{% if message %}<div class="msg {{ 'ok' if ok else 'warn' }}">{{ message }}</div>{% endif %}
<div class="tabs">
{% for key, name in month_options %}<a href="{{ url_for('report', m=key) }}" class="{{ 'on' if key == month_key else '' }}">{{ name }}</a>{% endfor %}
</div>
{% if incomplete %}<p class="note warn">Неповний місяць: виписка закінчується {{ last_date.day }} {{ last_month_gen }}.</p>{% endif %}
<div class="cards">
<div class="card"><small>Дохід (зарплата)</small><b>{{ s.salary|zl }}</b></div>
<div class="card"><small>Витрати</small><b>{{ s.spent|zl }}</b></div>
<div class="card"><small>Відкладено</small><b>{{ s.saved|zl }}</b></div>
<div class="card"><small>Норма заощаджень</small><b>{{ rate }}</b></div>
<div class="card"><small>Фіксовані</small><b>{{ s.fixed|zl }}</b></div>
<div class="card"><small>Змінні (керовані)</small><b>{{ s.managed|zl }}</b></div>
</div>
<p class="note">Інші надходження (не зарплата), в норму не входять: {{ s.other|zl }}</p>
<h2>Витрати за категоріями</h2>
<table>
{% for name, amount in categories %}<tr><td>{{ name }}</td><td>{{ amount|zl }}</td></tr>{% else %}<tr><td colspan="2" class="note">Немає витрат.</td></tr>{% endfor %}
<tr><th>Разом</th><th>{{ s.spent|zl }}</th></tr>
</table>
<h2>Додати готівкову витрату</h2>
<form method="post" action="{{ url_for('add') }}">
<input type="hidden" name="csrf" value="{{ csrf_token() }}">
<input type="hidden" name="back_m" value="{{ month_key }}">
<label for="amount">Сума, зл</label><input id="amount" name="amount" inputmode="decimal" placeholder="25,50" required>
<label for="cat">Категорія</label>
<select id="cat" name="category">{% for acc, name in accounts %}<option value="{{ acc }}">{{ name }}</option>{% endfor %}</select>
<label for="date">Дата</label><input id="date" name="date" type="date" value="{{ today }}" min="2026-07-31" max="{{ today }}">
<label for="note">Опис (необовʼязково)</label><input id="note" name="note" maxlength="80">
<button type="submit">Зберегти</button>
</form>"""

GENITIVE = ["", "січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня",
            "вересня", "жовтня", "листопада", "грудня"]


def page(template, **ctx):
    return render_template_string(PAGE, body=render_template_string(template, **ctx))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        check_csrf()
        now = time.time()
        FAILED_LOGINS[:] = [t for t in FAILED_LOGINS if now - t < WINDOW]
        if len(FAILED_LOGINS) >= MAX_FAILS:
            error = "Забагато невдалих спроб. Спробуйте за кілька хвилин."
        else:
            who = None
            for key, (login_var, hash_var) in USER_VARS.items():  # перевіряємо обох, щоб час відповіді не видавав логін
                login_ok = hmac.compare_digest(request.form.get("user", "").encode(), os.environ[login_var].encode())
                pass_ok = check_password_hash(os.environ[hash_var], request.form.get("password", ""))
                if login_ok and pass_ok:
                    who = key
            if who:
                session.clear()
                session["user"] = who
                session.permanent = True
                return redirect(url_for("report"))
            FAILED_LOGINS.append(now)
            error = "Невірний логін або пароль."
    return page(LOGIN, error=error)


@app.post("/logout")
def logout():
    check_csrf()
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
def report():
    message, ok = session.pop("flash", (None, True))
    entries, errors = tracker.load()
    if errors:
        abort(500)
    person = session["user"]  # лише власні дані людини, яка увійшла
    stats = tracker.month_stats(entries, person)
    all_months = sorted(stats)
    last_date = tracker.last_bank_date(entries, person)
    month = request.args.get("m", "")
    try:
        y, m = (int(x) for x in month.split("-"))
        key = (y, m) if (y, m) in all_months else all_months[-1]
    except ValueError:
        key = all_months[-1]
    empty = {"salary": 0, "other": 0, "fixed": 0, "managed": 0, "spent": 0, "saved": 0, "rate": None, "categories": {}}
    s = stats.get(key, empty)
    cats = sorted(s["categories"].items(), key=lambda kv: -kv[1])
    rate = f"{s['rate']:.1f}%".replace(".", ",") if s["rate"] is not None else "—"
    incomplete = tracker.is_incomplete(key, last_date)
    accounts = [(a, tracker.short(a).replace("-", " ")) for a in tracker.expense_accounts(entries)]
    return page(
        REPORT, message=message, ok=ok, name=tracker.PEOPLE[person], month_key=f"{key[0]}-{key[1]:02d}",
        month_options=[(f"{y}-{m:02d}", tracker.MONTH_NAMES[m]) for y, m in all_months],
        s=s, rate=rate, categories=[(a.replace("-", " "), v) for a, v in cats],
        incomplete=incomplete, last_date=last_date,
        last_month_gen=GENITIVE[last_date.month] if last_date else "",
        accounts=accounts, today=date.today().isoformat(),
    )


@app.post("/add")
def add():
    check_csrf()
    entries, errors = tracker.load()
    if errors:
        abort(500)
    form = {**request.form.to_dict(), "person": session["user"]}  # людина визначається входом, а не формою
    data, error = tracker.parse_cash(form, tracker.expense_accounts(entries))
    if error is None and not tracker.add_cash(data):
        error = "Облік відхилив запис, нічого не збережено."
    if error:
        session["flash"] = (error, False)
        return redirect(url_for("report", m=request.form.get("back_m", "")))
    session["flash"] = (f"Збережено: {tracker.PEOPLE[data['person']]}, {zl(data['amount'])}.", True)
    # після збереження показуємо місяць витрати, а сторінку можна безпечно перезавантажити
    return redirect(url_for("report", m=f"{data['date'].year}-{data['date'].month:02d}"))
