# Unit Economics (Юнит-экономика)

Этот модуль добавляет детальную юнит-экономику онлайн‑школы в PostgreSQL и вывод ее в Telegram‑боте.

## 1) Откуда берутся данные

Юнит‑экономика состоит из:

- **Входных данных** (вносятся вручную или подтягиваются из CRM/учета и записываются в БД).
- **Расчетных показателей**, которые считаются в PostgreSQL автоматически на стороне БД.

Сейчас бот **только читает и показывает** юнит‑экономику из таблицы `unit_economics`. Заполнение/обновление делается SQL‑запросом (см. ниже).

## 2) Хранилище данных: таблица `unit_economics`

DDL: `migrations/2026_01_10_unit_economics.sql`

Ключевые поля:

- `period_start` / `period_end` — период, за который считаем.
- `product_code` — код продукта (если нужно вести несколько продуктов параллельно). По умолчанию `default`.

Уникальность:

- `(period_start, period_end, product_code)` — уникальная запись на период и продукт.

### 2.1 Входные поля (Input Variables)

**Маркетинг (Marketing Spend)**

- `om_manual_cost`
- `om_auto_cost`
- `avito_cost`
- `media_cost`

**Трафик (Traffic)**

- `leads_total_count`
- `leads_om_count`

**Фиксы (Fixed Costs)**

- `infrastructure_costs`
- `salary_admin_fixed`
- `salary_mentors_manual`
- `salary_mentors_auto`

**Продажи (Sales)**

- `revenue_total`
- `product_price`

### 2.2 Расчетные поля (Calculated Metrics)

Все расчетные поля реализованы как **PostgreSQL generated columns** (хранятся как STORED).
То есть при `INSERT/UPDATE` входных данных БД автоматически пересчитает все метрики.

Важно про деление:

- Деление идет через `NULLIF(..., 0)`.
- Если `leads_total_count = 0` или `leads_om_count = 0`, то соответствующие CPA/Profit/Margin будут `NULL` (в боте отображаются как `—`).

#### Маркетинг (Marketing Aggregates)

- `om_total = om_manual_cost + om_auto_cost`
- `marketing_total = om_total + avito_cost + media_cost`

#### CPA/CAC

- `lead_cost_total = marketing_total / leads_total_count`
- `lead_cost_om = om_total / leads_om_count`

#### Fixed Total

- `fixed_costs_total = infrastructure_costs + salary_admin_fixed + salary_mentors_manual + salary_mentors_auto`

#### Unit Economics per sale (до общих фиксов школы)

- `profit_manual_before_fixed = product_price - lead_cost_om`
- `profit_auto_before_fixed = product_price - lead_cost_om`
- `profit_full_before_fixed = product_price - lead_cost_total`

#### Комиссии директора (10% от маржи продукта)

- `dir_manual = profit_manual_before_fixed * 0.10`
- `dir_auto = profit_auto_before_fixed * 0.10`

#### Net Margin per unit

- `margin_manual = product_price - lead_cost_om - dir_manual`
- `margin_auto = product_price - lead_cost_om - dir_auto`

#### P&L level

- `gross_profit = revenue_total - marketing_total`
- `net_profit = revenue_total - marketing_total - fixed_costs_total`

## 3) Как создать/обновить таблицу в БД

Запустить DDL на Postgres:

```bash
psql "$DATABASE_URL" -f migrations/2026_01_10_unit_economics.sql
```

`DATABASE_URL` должен указывать на вашу Postgres БД (тот же URL используется ботом).

## 4) Как добавлять/редактировать данные (upsert)

Готовый пример upsert и выборки: `unit_economics_queries.sql`

- `INSERT ... ON CONFLICT ... DO UPDATE` обновляет входные поля.
- Все расчетные поля обновятся автоматически (generated columns).

## 5) Как смотреть в боте

### 5.1 Через меню

- `Статистика` → `💹 Юнит экономика`
  - `📌 Последний период` — показывает последнюю запись для `product_code=default`
  - `📅 Выбрать период` — вводите даты, затем `product_code` (или `default`)

### 5.2 Через команду

- `/unit_economics` — последний период (`product_code=default`)
- `/unit_economics 01.01.2026 31.01.2026 default` — конкретный период и продукт

## 6) Технические детали

- SQLAlchemy модель: `data_base/models.py` (`UnitEconomics`)
- Доступ к БД в коде: `DATABASE_URL` из окружения (см. `data_base/__init__.py`).
- Сессия SQLAlchemy: `data_base/db.py` (`session`, `get_session()`).

