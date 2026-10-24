"""Розрахунки по обліку й запис готівкових витрат. Без веб-коду: це використовують і app.py, і check.py."""
import calendar
import re
import threading
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from beancount import loader
from beancount.core.data import Open, Transaction

ROOT = Path(__file__).parent
LEDGER = ROOT / "main.beancount"
CASH_FILE = ROOT / "cash.beancount"

PEOPLE = {"olya": "Оля", "marko": "Марко"}
MONTH_NAMES = ["", "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
               "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]
MAX_AMOUNT = Decimal("100000")

_write_lock = threading.Lock()


def load():
    """Повертає (записи, помилки) з main.beancount."""
    entries, errors, _ = loader.load_file(str(LEDGER))
    return entries, errors


def expense_accounts(entries):
    """Відкриті рахунки витрат без службового «Без-Категорії»."""
    return sorted(
        e.account for e in entries
        if isinstance(e, Open) and e.account.startswith("Expenses:") and not e.account.endswith("Без-Категорії")
    )


def short(account):
    return account.split(":", 1)[1]


def _transactions(entries, person):
    for e in entries:
        if not isinstance(e, Transaction) or e.narration == "Початковий залишок":
            continue
        if person and person not in e.tags:
            continue
        yield e


def month_stats(entries, person=None):
    """{(рік, місяць): дані}. Дохід — лише Income:Зарплата; решта надходжень окремо."""
    months = defaultdict(lambda: {
        "salary": Decimal(0), "other": Decimal(0), "fixed": Decimal(0), "managed": Decimal(0),
        "categories": defaultdict(Decimal),
    })
    for e in _transactions(entries, person):
        m = months[(e.date.year, e.date.month)]
        for p in e.postings:
            amount = p.units.number
            if p.account == "Income:Зарплата":
                m["salary"] -= amount
            elif p.account.startswith("Income:"):
                m["other"] -= amount
            elif p.account.startswith("Expenses:"):
                m["fixed" if "fixed" in e.tags else "managed"] += amount
                m["categories"][short(p.account)] += amount
    for m in months.values():
        m["spent"] = m["fixed"] + m["managed"]
        m["saved"] = m["salary"] - m["spent"]
        m["rate"] = m["saved"] / m["salary"] * 100 if m["salary"] else None
    return dict(sorted(months.items()))


def last_bank_date(entries, person=None):
    """Остання дата у виписках (готівку не рахуємо): за нею визначаємо неповний місяць."""
    dates = [e.date for e in _transactions(entries, person) if "cash" not in e.tags]
    return max(dates) if dates else None


def is_incomplete(year_month, last_date):
    if last_date is None:
        return False
    y, m = year_month
    return (y, m) == (last_date.year, last_date.month) and last_date.day < calendar.monthrange(y, m)[1]


def parse_cash(form, accounts, today=None):
    """Перевіряє поля форми. Повертає (дані, помилка)."""
    today = today or date.today()
    person = form.get("person", "")
    if person not in PEOPLE:
        return None, "Оберіть, хто витратив."
    try:
        amount = Decimal(form.get("amount", "").strip().replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return None, "Сума має бути числом, наприклад 25,50."
    if not amount.is_finite() or amount <= 0 or amount > MAX_AMOUNT:
        return None, "Сума має бути більшою за 0 і не більшою за 100 000."
    if amount != amount.quantize(Decimal("0.01")):
        return None, "Не більше двох знаків після коми."
    category = form.get("category", "")
    if category not in accounts:
        return None, "Оберіть категорію зі списку."
    try:
        day = date.fromisoformat(form.get("date", "")) if form.get("date") else today
    except ValueError:
        return None, "Дата має бути у форматі РРРР-ММ-ДД."
    if day < date(2026, 7, 31) or day > today:
        return None, "Дата має бути між 31 липня 2026 і сьогодні."
    note = re.sub(r"[^\w .,:;()+\-/&!?%@№']", "", form.get("note", ""), flags=re.UNICODE)
    note = " ".join(note.replace("'", "").split())[:80] or "Готівка"
    return {"person": person, "amount": amount, "category": category, "date": day, "note": note}, None


def add_cash(data):
    """Дописує готівкову витрату в cash.beancount і перевіряє облік. Якщо є помилки, скасовує запис."""
    entry = (
        f'\n{data["date"]} * "{data["note"]}" #{data["person"]} #cash\n'
        f'  Assets:Готівка-{PEOPLE[data["person"]]}  {-data["amount"]:.2f} PLN\n'
        f'  {data["category"]}  {data["amount"]:.2f} PLN\n'
    )
    with _write_lock:
        before = CASH_FILE.read_text(encoding="utf-8")
        CASH_FILE.write_text(before + entry, encoding="utf-8")
        _, errors = load()
        if errors:
            CASH_FILE.write_text(before, encoding="utf-8")
            return False
    return True
