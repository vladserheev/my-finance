"""Збирає transactions.beancount з виписок Олі й Марка і правил з rules.csv.

Виписки лежать у demo-data/ (штучні дані): olya/*.csv (формат банку Олі, англійською)
і marko/*.csv (формат банку Марка, польською, з крапкою з комою).
Запуск: uv run python import.py
"""
import csv
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "demo-data"
NO_CATEGORY = "Expenses:Без-Категорії"
OTHER_INCOME = "Income:Інше"


def load_rules():
    with open(ROOT / "rules.csv", encoding="utf-8", newline="") as f:
        return [
            (r["шаблон"].lower(), r["рахунок"], r["фіксована"].strip().lower() == "так")
            for r in csv.DictReader(f)
        ]


def find_rule(rules, description, amount):
    """Перше правило, що підійшло. Надходження ідуть лише в Income:*."""
    text = description.lower()
    for pattern, account, fixed in rules:
        if pattern in text:
            if amount > 0 and not account.startswith("Income:"):
                continue
            if amount < 0 and account.startswith("Income:"):
                continue
            return account, fixed
    return (OTHER_INCOME if amount > 0 else NO_CATEGORY), False


# Хто, рахунок, початковий залишок на 31 липня 2026 (він же в main.beancount).
PEOPLE = {
    "olya": ("Assets:Банк-Оля", Decimal("4500.00")),
    "marko": ("Assets:Банк-Марко", Decimal("2860.40")),
}


def number(text):
    """'-1 234,56' або '-1234.56' -> Decimal."""
    return Decimal(re.sub(r"\s", "", text).replace(",", "."))


def read_olya():
    """Банк Олі: рядки в порядку банку; однакові (дата, опис, сума, залишок) рахуємо раз."""
    seen = set()
    for path in sorted((DATA / "olya").glob("*.csv")):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["State"] != "COMPLETED":
                    continue
                key = (row["Completed Date"], row["Description"], row["Amount"], row["Balance"])
                if key in seen:
                    continue
                seen.add(key)
                yield {
                    "date": row["Completed Date"][:10],
                    "description": row["Description"],
                    "amount": number(row["Amount"]) - number(row["Fee"] or "0"),
                    "balance": number(row["Balance"]),
                }


def read_marko():
    """Банк Марка: найновіші рядки зверху, тому читаємо у зворотному порядку.
    Дата — дата księgowania (проведення), бо залишок рахується в порядку проведення."""
    seen = set()
    rows = []
    for path in sorted((DATA / "marko").glob("*.csv")):
        with open(path, encoding="utf-8", newline="") as f:
            for line in csv.reader(f, delimiter=";"):
                if len(line) != 6 or not re.match(r"\d\d\.\d\d\.\d{4}$", line[0]):
                    continue  # шапка, порожні рядки, «Saldo początkowe»
                key = (line[1], line[3], line[4], line[5])
                if key in seen:
                    continue
                seen.add(key)
                d, m, y = line[1].split(".")
                rows.append({
                    "date": f"{y}-{m}-{d}",
                    "description": line[3],
                    "amount": number(line[4]),
                    "balance": number(line[5]),
                })
    yield from reversed(rows)


def person_entries(person, rows, out):
    """Додає операції людини в out. Повертає (кількість, останній рядок кожного місяця)."""
    bank, opening = PEOPLE[person]
    rules = load_rules()
    month_end = {}
    running = opening
    count = 0
    for row in rows:
        running += row["amount"]
        if running != row["balance"]:
            raise SystemExit(f"{person}: залишок у виписці не сходиться на {row['date']} {row['description']}")
        month_end[row["date"][:7]] = row
        description = row["description"].replace('"', "'")
        account, fixed = find_rule(rules, row["description"], row["amount"])
        tags = f" #{person}" + (" #fixed" if fixed else "")
        out.append(f'{row["date"]} * "{description}"{tags}')
        out.append(f"  {bank}  {row['amount']:.2f} PLN")
        out.append(f"  {account}  {-row['amount']:.2f} PLN")
        out.append("")
        count += 1
    # Звірка з банком: залишок останнього рядка місяця на наступний день після нього.
    # Для останнього місяця це день після останньої операції.
    months = sorted(month_end)
    asserts = []
    for month in months:
        last = month_end[month]
        last_day = date.fromisoformat(last["date"])
        if month == months[-1]:
            check_day = last_day + timedelta(days=1)
        else:
            check_day = (last_day.replace(day=1) + timedelta(days=32)).replace(day=1)
        asserts.append(f"{check_day} balance {bank}  {last['balance']:.2f} PLN")
    return count, asserts


def main():
    out = ["; Згенеровано import.py. Руками не правимо: файл перезаписується при кожному імпорті.", ""]
    total = 0
    all_asserts = []
    for person, rows in (("olya", read_olya()), ("marko", read_marko())):
        count, asserts = person_entries(person, rows, out)
        total += count
        all_asserts += asserts
        print(f"{person}: операцій {count}, звірок із банком {len(asserts)}")
    out += all_asserts + [""]
    (ROOT / "transactions.beancount").write_text("\n".join(out), encoding="utf-8")
    print(f"Записано операцій: {total}")


if __name__ == "__main__":
    main()
