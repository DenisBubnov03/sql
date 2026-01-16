from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import func

from commands.states import UE_MENU, UE_START_PERIOD, UE_END_PERIOD, STATISTICS_MENU
from commands.student_statistic_commands import show_statistics_menu
from data_base.db import session
from data_base.models import StudentMeta, Payment, MarketingSpend, FixedExpense


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ФОРМАТИРОВАНИЯ ---

def _fmt_money(value: float | Decimal | None) -> str:
    if value is None or value == 0:
        return "0 ₽"
    return f"{float(value):,.0f}".replace(",", " ") + " ₽"


def _fmt_num(value: float | Decimal | None, decimals: int = 2) -> str:
    if value is None:
        return "0"
    return f"{float(value):,.{decimals}f}".replace(",", " ")


# --- ЯДРО: КАЛЬКУЛЯТОР ЮНИТ-ЭКОНОМИКИ ---

def calculate_ue_data(start_date, end_date):
    """Выполняет расчет всех метрик из ТЗ на лету"""

    # 1. Лиды (из StudentMeta)
    leads_total = session.query(StudentMeta).filter(
        StudentMeta.created_at.between(start_date, end_date)
    ).count() or 0

    leads_om = session.query(StudentMeta).filter(
        StudentMeta.created_at.between(start_date, end_date),
        StudentMeta.source.ilike('%ОМ%')  # Ищем источник, где есть "ОМ"
    ).count() or 0

    # 2. Маркетинговые расходы (из MarketingSpend)
    m_spend = session.query(MarketingSpend.channel, func.sum(MarketingSpend.amount)).filter(
        MarketingSpend.report_month.between(start_date, end_date)
    ).group_by(MarketingSpend.channel).all()

    m_map = {channel: float(amount) for channel, amount in m_spend}
    om_manual = m_map.get('om_manual', 0)
    om_auto = m_map.get('om_auto', 0)
    avito = m_map.get('avito', 0)
    media = m_map.get('media', 0)

    om_total = om_manual + om_auto
    marketing_total = om_total + avito + media

    # 3. Фиксы (из FixedExpense)
    f_spend = session.query(FixedExpense.category, func.sum(FixedExpense.amount)).filter(
        FixedExpense.report_month.between(start_date, end_date)
    ).group_by(FixedExpense.category).all()

    f_map = {cat: float(amt) for cat, amt in f_spend}
    infra = f_map.get('cineskop', 0) + f_map.get('chat_place', 0) + f_map.get('bots', 0)
    salary_fixed = f_map.get('salaries_fixed', 0)
    mentors_manual = f_map.get('mentors_manual', 0)
    mentors_auto = f_map.get('mentors_auto', 0)

    fixed_costs_total = infra + salary_fixed + mentors_manual + mentors_auto

    # 4. Выручка (из Payment)
    revenue_total = session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date.between(start_date, end_date),
        Payment.status == 'подтвержден'
    ).scalar() or 0

    # Кол-во продаж (учеников с оплатами в этот период)
    sales_count = session.query(func.count(func.distinct(Payment.student_id))).filter(
        Payment.payment_date.between(start_date, end_date),
        Payment.status == 'подтвержден'
    ).scalar() or 0

    # Средняя цена продукта (Revenue / Sales)
    product_price = float(revenue_total) / sales_count if sales_count > 0 else 0

    # --- РАСЧЕТ МЕТРИК ---

    # Стоимость лида
    lead_cost_total = marketing_total / leads_total if leads_total > 0 else 0
    lead_cost_om = om_total / leads_om if leads_om > 0 else 0

    # Прибыль с продукта до фиксов (Цена - Лид)
    profit_manual_bf = product_price - lead_cost_om
    profit_auto_bf = product_price - lead_cost_om
    profit_full_bf = product_price - lead_cost_total

    # Проценты директорам (10%)
    dir_manual = profit_manual_bf * 0.10 if profit_manual_bf > 0 else 0
    dir_auto = profit_auto_bf * 0.10 if profit_auto_bf > 0 else 0

    # Маржа (Чистая с продукта)
    margin_manual = profit_manual_bf - dir_manual
    margin_auto = profit_auto_bf - dir_auto

    # Итого по школе
    gross_profit = float(revenue_total) - marketing_total
    net_profit = gross_profit - fixed_costs_total

    return {
        "period": f"{start_date:%d.%m.%Y} — {end_date:%d.%m.%Y}",
        "om_manual": om_manual, "om_auto": om_auto, "avito": avito, "media": media,
        "leads_total": leads_total, "leads_om": leads_om,
        "infra": infra, "salary_fixed": salary_fixed,
        "mentors_manual": mentors_manual, "mentors_auto": mentors_auto,
        "revenue": float(revenue_total), "price": product_price,
        "om_total": om_total, "m_total": marketing_total,
        "cpa_total": lead_cost_total, "cpa_om": lead_cost_om,
        "f_total": fixed_costs_total,
        "p_manual_bf": profit_manual_bf, "p_auto_bf": profit_auto_bf, "p_full_bf": profit_full_bf,
        "dir_manual": dir_manual, "dir_auto": dir_auto,
        "margin_manual": margin_manual, "margin_auto": margin_auto,
        "gross": gross_profit, "net": net_profit
    }


def _format_report(d: dict) -> str:
    return (
        f"💹 <b>Юнит-экономика</b>\n"
        f"Период: <b>{d['period']}</b>\n\n"
        f"📥 <b>Входные данные</b>\n"
        f"ОМ manual: {_fmt_money(d['om_manual'])}\n"
        f"ОМ auto: {_fmt_money(d['om_auto'])}\n"
        f"Avito: {_fmt_money(d['avito'])}\n"
        f"Media: {_fmt_money(d['media'])}\n"
        f"Лиды всего: <b>{d['leads_total']}</b>\n"
        f"Лиды ОМ: <b>{d['leads_om']}</b>\n"
        f"Инфраструктура: {_fmt_money(d['infra'])}\n"
        f"Оклады админ: {_fmt_money(d['salary_fixed'])}\n"
        f"ЗП менторов M/A: {_fmt_money(d['mentors_manual'])} / {_fmt_money(d['mentors_auto'])}\n"
        f"Выручка: {_fmt_money(d['revenue'])}\n"
        f"Средний чек: {_fmt_money(d['price'])}\n\n"
        f"📊 <b>Расчетные метрики</b>\n"
        f"Marketing total: {_fmt_money(d['m_total'])}\n"
        f"Lead cost total: <b>{_fmt_num(d['cpa_total'])}</b>\n"
        f"Lead cost OM: <b>{_fmt_num(d['cpa_om'])}</b>\n"
        f"Fixed costs total: {_fmt_money(d['f_total'])}\n\n"
        f"Profit manual (до фиксов): <b>{_fmt_num(d['p_manual_bf'])}</b>\n"
        f"Profit auto (до фиксов): <b>{_fmt_num(d['p_auto_bf'])}</b>\n"
        f"Dir manual (10%): <b>{_fmt_num(d['dir_manual'])}</b>\n"
        f"Margin manual: <b>{_fmt_num(d['margin_manual'])}</b>\n\n"
        f"💰 <b>ИТОГО:</b>\n"
        f"Gross profit: <b>{_fmt_money(d['gross'])}</b>\n"
        f"Чистая прибыль (Net): <b>{_fmt_money(d['net'])}</b>"
    )


# --- ХЕНДЛЕРЫ БОТА ---

async def show_unit_economics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💹 Юнит-экономика:\nВыберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            [["📌 Текущий месяц", "📅 Выбрать период"], ["🔙 Назад"]],
            one_time_keyboard=True, resize_keyboard=True
        )
    )
    return UE_MENU


async def show_latest_unit_economics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Берем данные с начала текущего месяца по сегодняшний день
    start_date = datetime.now().replace(day=1).date()
    end_date = datetime.now().date()

    data = calculate_ue_data(start_date, end_date)
    await update.message.reply_text(_format_report(data), parse_mode="HTML")
    return UE_MENU


async def unit_economics_request_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите начальную дату периода (ДД.ММ.ГГГГ):")
    return UE_START_PERIOD


async def unit_economics_handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
        context.user_data["ue_period_start"] = start_date
        await update.message.reply_text("Введите конечную дату периода (ДД.ММ.ГГГГ):")
        return UE_END_PERIOD
    except ValueError:
        await update.message.reply_text("❌ Формат ДД.ММ.ГГГГ:")
        return UE_START_PERIOD


async def unit_economics_handle_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        end_date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
        start_date = context.user_data.get("ue_period_start")

        data = calculate_ue_data(start_date, end_date)
        await update.message.reply_text(_format_report(data), parse_mode="HTML")
        return UE_MENU
    except ValueError:
        await update.message.reply_text("❌ Формат ДД.ММ.ГГГГ:")
        return UE_END_PERIOD


async def unit_economics_back_to_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_statistics_menu(update, context)


async def unit_economics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Для быстрой команды через слэш
    start_date = datetime.now().replace(day=1).date()
    end_date = datetime.now().date()
    data = calculate_ue_data(start_date, end_date)
    await update.message.reply_text(_format_report(data), parse_mode="HTML")