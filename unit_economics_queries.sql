-- Upsert (создать/обновить) входные данные юнит-экономики за период.
INSERT INTO unit_economics (
    period_start,
    period_end,
    product_code,
    om_manual_cost,
    om_auto_cost,
    avito_cost,
    media_cost,
    leads_total_count,
    leads_om_count,
    infrastructure_costs,
    salary_admin_fixed,
    salary_mentors_manual,
    salary_mentors_auto,
    revenue_total,
    product_price
)
VALUES (
    DATE '2026-01-01',
    DATE '2026-01-31',
    'default',
    0, 0, 0, 0,
    0, 0,
    0, 0, 0, 0,
    0, 0
)
ON CONFLICT (period_start, period_end, product_code) DO UPDATE
SET
    om_manual_cost = EXCLUDED.om_manual_cost,
    om_auto_cost = EXCLUDED.om_auto_cost,
    avito_cost = EXCLUDED.avito_cost,
    media_cost = EXCLUDED.media_cost,
    leads_total_count = EXCLUDED.leads_total_count,
    leads_om_count = EXCLUDED.leads_om_count,
    infrastructure_costs = EXCLUDED.infrastructure_costs,
    salary_admin_fixed = EXCLUDED.salary_admin_fixed,
    salary_mentors_manual = EXCLUDED.salary_mentors_manual,
    salary_mentors_auto = EXCLUDED.salary_mentors_auto,
    revenue_total = EXCLUDED.revenue_total,
    product_price = EXCLUDED.product_price,
    updated_at = NOW()
RETURNING *;

-- Срез расчетных метрик (все calculated колонки считаются автоматически).
SELECT
    period_start,
    period_end,
    product_code,
    om_manual_cost,
    om_auto_cost,
    avito_cost,
    media_cost,
    leads_total_count,
    leads_om_count,
    infrastructure_costs,
    salary_admin_fixed,
    salary_mentors_manual,
    salary_mentors_auto,
    revenue_total,
    product_price,
    om_total,
    marketing_total,
    lead_cost_total,
    lead_cost_om,
    fixed_costs_total,
    profit_manual_before_fixed,
    profit_auto_before_fixed,
    profit_full_before_fixed,
    dir_manual,
    dir_auto,
    margin_manual,
    margin_auto,
    gross_profit,
    net_profit
FROM unit_economics
ORDER BY period_start DESC, period_end DESC, product_code;

