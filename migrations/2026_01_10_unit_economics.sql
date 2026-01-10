CREATE TABLE IF NOT EXISTS unit_economics (
    id BIGSERIAL PRIMARY KEY,

    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    product_code TEXT NOT NULL DEFAULT 'default',

    om_manual_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    om_auto_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    avito_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    media_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,

    leads_total_count INTEGER NOT NULL DEFAULT 0,
    leads_om_count INTEGER NOT NULL DEFAULT 0,

    infrastructure_costs NUMERIC(14, 2) NOT NULL DEFAULT 0,
    salary_admin_fixed NUMERIC(14, 2) NOT NULL DEFAULT 0,
    salary_mentors_manual NUMERIC(14, 2) NOT NULL DEFAULT 0,
    salary_mentors_auto NUMERIC(14, 2) NOT NULL DEFAULT 0,

    revenue_total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    product_price NUMERIC(14, 2) NOT NULL DEFAULT 0,

    om_total NUMERIC(14, 2) GENERATED ALWAYS AS (
        om_manual_cost + om_auto_cost
    ) STORED,
    marketing_total NUMERIC(14, 2) GENERATED ALWAYS AS (
        (om_manual_cost + om_auto_cost) + avito_cost + media_cost
    ) STORED,

    lead_cost_total NUMERIC(14, 4) GENERATED ALWAYS AS (
        ((om_manual_cost + om_auto_cost) + avito_cost + media_cost) / NULLIF(leads_total_count, 0)
    ) STORED,
    lead_cost_om NUMERIC(14, 4) GENERATED ALWAYS AS (
        (om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0)
    ) STORED,

    fixed_costs_total NUMERIC(14, 2) GENERATED ALWAYS AS (
        infrastructure_costs + salary_admin_fixed + salary_mentors_manual + salary_mentors_auto
    ) STORED,

    profit_manual_before_fixed NUMERIC(14, 4) GENERATED ALWAYS AS (
        product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))
    ) STORED,
    profit_auto_before_fixed NUMERIC(14, 4) GENERATED ALWAYS AS (
        product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))
    ) STORED,
    profit_full_before_fixed NUMERIC(14, 4) GENERATED ALWAYS AS (
        product_price - (((om_manual_cost + om_auto_cost) + avito_cost + media_cost) / NULLIF(leads_total_count, 0))
    ) STORED,

    dir_manual NUMERIC(14, 4) GENERATED ALWAYS AS (
        (product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))) * 0.10
    ) STORED,
    dir_auto NUMERIC(14, 4) GENERATED ALWAYS AS (
        (product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))) * 0.10
    ) STORED,

    margin_manual NUMERIC(14, 4) GENERATED ALWAYS AS (
        product_price
        - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))
        - ((product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))) * 0.10)
    ) STORED,
    margin_auto NUMERIC(14, 4) GENERATED ALWAYS AS (
        product_price
        - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))
        - ((product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))) * 0.10)
    ) STORED,

    gross_profit NUMERIC(14, 2) GENERATED ALWAYS AS (
        revenue_total - (((om_manual_cost + om_auto_cost) + avito_cost + media_cost))
    ) STORED,
    net_profit NUMERIC(14, 2) GENERATED ALWAYS AS (
        revenue_total
        - (((om_manual_cost + om_auto_cost) + avito_cost + media_cost))
        - (infrastructure_costs + salary_admin_fixed + salary_mentors_manual + salary_mentors_auto)
    ) STORED,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_unit_economics_period_product UNIQUE (period_start, period_end, product_code),
    CONSTRAINT ck_unit_economics_leads_total_nonneg CHECK (leads_total_count >= 0),
    CONSTRAINT ck_unit_economics_leads_om_nonneg CHECK (leads_om_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_unit_economics_period
    ON unit_economics (period_start, period_end);

