# Прогрес

## Зроблено
- Інтервʼю з Олею (5 питань), рішення зафіксовано в `PRD.md`.
- Створено `PRD.md`, `IMPLEMENTATION_PLAN.md` (кроки зі «Зробити» і «Перевірити»), `PROGRESS.md`.
- У `CLAUDE.md` дописано розділ «Проєкт».
- Крок 1: каркас `main.beancount` (рахунки, початковий залишок 4 500 зл, `include`). `bean-check` пройшов без повідомлень. Порожня заготовка `transactions.beancount` (поза git).
- Крок 2: у `rules.csv` додано Play (фіксована), Rossmann, Decathlon. Усі рахунки з правил відкриті в `main.beancount`, `bean-check` чистий.

## Далі
- Крок 3: `import.py`, який збирає `transactions.beancount` з `data/*.csv` і `rules.csv`.
