"""Збирає transactions.beancount з усіх CSV у data/ і правил з rules.csv.

Запуск: uv run python import.py
"""
import csv
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
BANK = "Assets:Банк"
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


def read_rows():
    """Рядки в порядку банку; однакові (дата, опис, сума, залишок) рахуємо раз."""
    seen = set()
    for path in sorted((ROOT / "data").glob("*.csv")):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["State"] != "COMPLETED":
                    continue
                key = (row["Completed Date"], row["Description"], row["Amount"], row["Balance"])
                if key in seen:
                    continue
                seen.add(key)
                yield row


def main():
    rules = load_rules()
    out = ["; Згенеровано import.py. Руками не правимо: файл перезаписується при кожному імпорті.", ""]
    for row in read_rows():
        amount = Decimal(row["Amount"]) - Decimal(row["Fee"] or "0")
        description = row["Description"].replace('"', "'")
        account, fixed = find_rule(rules, row["Description"], amount)
        tag = " #fixed" if fixed else ""
        out.append(f'{row["Completed Date"][:10]} * "{description}"{tag}')
        out.append(f"  {BANK}  {amount:.2f} PLN")
        out.append(f"  {account}  {-amount:.2f} PLN")
        out.append("")
    (ROOT / "transactions.beancount").write_text("\n".join(out), encoding="utf-8")
    print(f"Записано операцій: {(len(out) - 2) // 4}")


if __name__ == "__main__":
    main()
