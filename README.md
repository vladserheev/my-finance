# Фінанси Олі й Марка

Трекер на Beancount 3 для двох людей: виписки Олі й Марка, звіт за місяць і веб-сторінка для телефона з формою «Додати готівкову витрату». **Усі дані тут штучні** (папка `demo-data/`), справжніх виписок у репозиторії немає.

## Перевірка однією командою
```
uv sync
uv run python check.py
```
Команда збирає `transactions.beancount` з обох виписок, запускає `bean-check` (він має мовчати) і друкує контрольні цифри змінних витрат та порівнює їх з очікуваними:

| | серпень | вересень |
|---|---|---|
| Оля | 2 195,21 зл | 2 582,42 зл |
| Марко | 1 855,57 зл | 2 432,83 зл |

Код виходу 0 означає, що все збіглося.

## Що де лежить
- `demo-data/olya/`, `demo-data/marko/` — штучні виписки (різні формати двох банків).
- `import.py` — читає обидві виписки, застосовує `rules.csv`, пише `transactions.beancount` і звірки із залишком банку.
- `main.beancount` — рахунки, збережені запити, `include` двох файлів з операціями. `cash.beancount` — готівкові витрати з телефона.
- `tracker.py` — розрахунки (дохід, витрати, фіксовані й змінні, норма заощаджень) і запис готівки. `app.py` — веб-сторінка. `report.py` — статичний `report.html` для Олі.

## Хеш пароля
Паролі ніде не зберігаються відкритим текстом, лише хеші (PBKDF2-SHA256 з сіллю). Зробити хеш:
```
uv run python -c "import getpass; from werkzeug.security import generate_password_hash as g; print(g(getpass.getpass('Пароль: '), method='pbkdf2:sha256'))"
```
(на PythonAnywhere замість `uv run python` пишуть `~/venv/bin/python`).

## Веб-сторінка локально
Потрібні змінні `OLYA_LOGIN`, `OLYA_PASSWORD_HASH`, `MARKO_LOGIN`, `MARKO_PASSWORD_HASH`, `SECRET_KEY`:
```
export OLYA_LOGIN=olya OLYA_PASSWORD_HASH='<хеш>' MARKO_LOGIN=marko MARKO_PASSWORD_HASH='<хеш>'
export SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
ALLOW_HTTP=1 uv run flask --app app run
```
`ALLOW_HTTP=1` лише для перевірки на своєму комп'ютері; на сервері його не задають.

## Безпека
- Без входу сторінка не показує жодних даних: усі адреси, крім входу, перенаправляють на форму.
- Два користувачі, Оля й Марко. Кожен після входу бачить лише свої дані; готівкова витрата завжди записується на ту людину, яка увійшла, навіть якщо підробити форму.
- Паролі зберігаються лише як хеші (PBKDF2-SHA256 з сіллю). Логіни, хеші й ключ сесії лежать у змінних середовища, у коді й репозиторії їх немає. Якщо змінних немає, сторінка відповідає 503 і нічого не показує.
- Лише HTTPS: звичайний `http://` перенаправляється на `https://`, кукі позначені `Secure` і `HttpOnly`, надсилається HSTS.
- Захист форм від підробки (CSRF-токен) і від підбору пароля (8 невдалих спроб за 10 хвилин закривають вхід).
- У репозиторії й на сервері лише штучні дані з завдання.
- Двофакторний вхід і журнал доступу не додавали: для двох людей вони ускладнюють користування більше, ніж захищають. Диск не шифрується, власник хостингу технічно бачить файли.

## Публікація на PythonAnywhere (безкоштовно)
1. Зареєструвати безкоштовний акаунт на pythonanywhere.com. Адреса буде `імʼя.pythonanywhere.com` (HTTPS є одразу).
2. У Bash-консолі: `git clone <посилання на репозиторій> my-finance`, потім `cd my-finance`, `python3 -m venv ~/venv`, `~/venv/bin/pip install -r requirements.txt`, `~/venv/bin/python check.py`.
3. Вкладка Web → Add a new web app → Manual configuration (Python 3.12 чи новіша). Virtualenv: `/home/імʼя/venv`. Увімкнути **Force HTTPS**.
4. У WSGI-файлі вставити (хеші зробити командою вище; у git їх немає):
```python
import os, sys
sys.path.insert(0, "/home/імʼя/my-finance")
os.chdir("/home/імʼя/my-finance")
os.environ["OLYA_LOGIN"] = "логін-олі"
os.environ["OLYA_PASSWORD_HASH"] = 'хеш-пароля-олі'
os.environ["MARKO_LOGIN"] = "логін-марка"
os.environ["MARKO_PASSWORD_HASH"] = 'хеш-пароля-марка'
os.environ["SECRET_KEY"] = "довгий-випадковий-рядок"
from app import app as application
```
5. Натиснути Reload. Готівкові витрати зберігаються у файлі `cash.beancount` на сервері. Щоб `git pull` не конфліктував з ним, виконати один раз `git update-index --skip-worktree cash.beancount`.
6. Безкоштовний тариф «засинає» без відвідувачів і потребує заходити на вкладку Web хоча б раз на три місяці, щоб його не вимкнули.
