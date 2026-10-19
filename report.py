"""Створює report.html з main.beancount: три відповіді для Олі."""
from collections import defaultdict
from decimal import Decimal
from html import escape

from beancount import loader
from beancount.core.data import Transaction

MONTHS = {8: "Серпень", 9: "Вересень", 10: "Жовтень"}
INCOMPLETE = {10}  # місяці, яких у виписці ще не повністю

entries, errors, _ = loader.load_file("main.beancount")
if errors:
    raise SystemExit(f"Облік має помилки, звіт не створено: {errors[0].message}")

salary = defaultdict(Decimal)
other_income = defaultdict(Decimal)
fixed = defaultdict(Decimal)
managed = defaultdict(Decimal)
by_category = defaultdict(lambda: defaultdict(Decimal))

for e in entries:
    if not isinstance(e, Transaction) or e.narration == "Початковий залишок":
        continue
    m = e.date.month
    for p in e.postings:
        name = p.account
        amount = p.units.number
        if name == "Income:Зарплата":
            salary[m] -= amount
        elif name.startswith("Income:"):
            other_income[m] -= amount
        elif name.startswith("Expenses:"):
            (fixed if "fixed" in e.tags else managed)[m] += amount
            by_category[name.split(":", 1)[1]][m] += amount

months = sorted(set(salary) | set(fixed) | set(managed))
categories = sorted(by_category, key=lambda c: -sum(by_category[c].values()))


def zl(x):
    return f"{x:,.2f}".replace(",", " ").replace(".", ",") + " зл"


def label(m):
    return MONTHS[m] + (" <small>(неповний місяць, до 15 жовтня)</small>" if m in INCOMPLETE else "")


def table(head, rows):
    h = "".join(f"<th>{c}</th>" for c in head)
    r = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{h}</tr>{r}</table>"


q1 = table(
    ["Категорія"] + [label(m) for m in months],
    [[escape(c)] + [zl(by_category[c][m]) for m in months] for c in categories]
    + [["<b>Разом</b>"] + [f"<b>{zl(fixed[m] + managed[m])}</b>" for m in months]],
)

rows2 = []
for m in months:
    spent = fixed[m] + managed[m]
    saved = salary[m] - spent
    rate = f"{saved / salary[m] * 100:.1f}%".replace(".", ",") if salary[m] else "—"
    rows2.append([label(m), zl(salary[m]), zl(spent), zl(saved), rate, zl(other_income[m])])
q2 = table(["Місяць", "Дохід (зарплата)", "Витрати", "Відкладено", "Норма заощаджень", "Інші надходження"], rows2)

rows3 = []
for m in months:
    spent = fixed[m] + managed[m]
    share = f"{fixed[m] / spent * 100:.0f}%" if spent else "—"
    rows3.append([label(m), zl(fixed[m]), zl(managed[m]), share])
q3 = table(["Місяць", "Фіксовані", "Керовані", "Частка фіксованих"], rows3)

html = f"""<!doctype html>
<html lang="uk"><head><meta charset="utf-8"><title>Фінанси Олі</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#222}}
table{{border-collapse:collapse;width:100%;margin-bottom:2rem}}
th,td{{border-bottom:1px solid #ddd;padding:.5rem;text-align:right}}
th:first-child,td:first-child{{text-align:left}}
small{{color:#a35;font-weight:normal}}
</style></head><body>
<h1>Фінанси Олі</h1>
<p>Виписка: 1 серпня – 15 жовтня 2026. Усі суми в злотих.</p>
<h2>1. Скільки йде на кожну категорію</h2>{q1}
<h2>2. Яку частку доходу Оля відкладає</h2>
<p>Відкладено = дохід мінус витрати. Інші надходження в норму не входять.</p>{q2}
<h2>3. Фіксовані й керовані витрати</h2>{q3}
</body></html>"""

open("report.html", "w", encoding="utf-8").write(html)
print("Створено report.html")
