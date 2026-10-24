"""Одна команда перевірки: імпорт виписок, bean-check і контрольні цифри Олі й Марка.

Запуск: uv run python check.py
Код виходу 0 лише якщо облік без помилок і всі контрольні цифри збігаються.
"""
import subprocess
import sys
from decimal import Decimal

import tracker

# Змінні (керовані) витрати з умови завдання: (людина, місяць) -> сума.
EXPECTED = {
    ("olya", 8): Decimal("2195.21"), ("olya", 9): Decimal("2582.42"),
    ("marko", 8): Decimal("1855.57"), ("marko", 9): Decimal("2432.83"),
}


def main():
    if subprocess.run([sys.executable, "import.py"]).returncode:
        return 1
    # bean-check: має мовчати
    if subprocess.run([sys.executable, "-m", "beancount.scripts.check", "main.beancount"]).returncode:
        print("bean-check знайшов помилки")
        return 1
    entries, errors = tracker.load()
    if errors:
        print("Помилки обліку:", errors[0].message)
        return 1
    print("\nbean-check: помилок немає\n")
    ok = True
    for person, name in tracker.PEOPLE.items():
        stats = tracker.month_stats(entries, person)
        for month in (8, 9):
            got = stats[(2026, month)]["managed"]
            want = EXPECTED[(person, month)]
            good = got == want
            ok &= good
            print(f"{name}, {tracker.MONTH_NAMES[month].lower()}: змінні витрати {got:.2f} зл"
                  f" (очікується {want}) {'OK' if good else 'НЕ ЗБІГАЄТЬСЯ'}")
    no_cat = [e for e in entries if getattr(e, "postings", None)
              and any(p.account.endswith("Без-Категорії") for p in e.postings)]
    if no_cat:
        ok = False
        print(f"Операцій без категорії: {len(no_cat)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
