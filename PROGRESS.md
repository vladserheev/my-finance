# Прогрес

## Зроблено
- Інтервʼю з Олею (5 питань), рішення зафіксовано в `PRD.md`.
- Створено `PRD.md`, `IMPLEMENTATION_PLAN.md` (кроки зі «Зробити» і «Перевірити»), `PROGRESS.md`.
- У `CLAUDE.md` дописано розділ «Проєкт».
- Крок 1: каркас `main.beancount` (рахунки, початковий залишок 4 500 зл, `include`). `bean-check` пройшов без повідомлень. Порожня заготовка `transactions.beancount` (поза git).
- Крок 2: у `rules.csv` додано Play (фіксована), Rossmann, Decathlon. Усі рахунки з правил відкриті в `main.beancount`, `bean-check` чистий.
- Крок 3: `import.py` (`uv run python import.py`) створює `transactions.beancount`: 142 операції, жодної в «Без-Категорії», 17 з тегом `#fixed`. `bean-check` чистий.

## Далі
- Крок 4: звірити залишок у Beancount з останнім Balance у виписці.
