from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from commands.states import UE_MENU, UE_START_PERIOD, UE_END_PERIOD, UE_PRODUCT_CODE, STATISTICS_MENU
from commands.student_statistic_commands import show_statistics_menu
from data_base.operations import get_latest_unit_economics, get_unit_economics


def _fmt_money(value: Optional[Decimal], decimals: int = 2) -> str:
    if value is None:
        return "—"
    formatted = f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{formatted} ₽"


def _fmt_num(value: Optional[Decimal], decimals: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",")


def _format_unit_economics_row(row) -> str:
    return (
        f"💹 <b>Юнит-экономика</b>\n"
        f"Период: <b>{row.period_start:%d.%m.%Y} — {row.period_end:%d.%m.%Y}</b>\n"
        f"Продукт: <b>{row.product_code}</b>\n\n"
        f"— <b>Входные данные</b>\n"
        f"ОМ manual: {_fmt_money(row.om_manual_cost)}\n"
        f"ОМ auto: {_fmt_money(row.om_auto_cost)}\n"
        f"Avito: {_fmt_money(row.avito_cost)}\n"
        f"Media: {_fmt_money(row.media_cost)}\n"
        f"Лиды всего: <b>{row.leads_total_count}</b>\n"
        f"Лиды ОМ: <b>{row.leads_om_count}</b>\n"
        f"Инфраструктура: {_fmt_money(row.infrastructure_costs)}\n"
        f"Оклады админ: {_fmt_money(row.salary_admin_fixed)}\n"
        f"ЗП менторов manual: {_fmt_money(row.salary_mentors_manual)}\n"
        f"ЗП менторов auto: {_fmt_money(row.salary_mentors_auto)}\n"
        f"Выручка total: {_fmt_money(row.revenue_total)}\n"
        f"Цена продукта: {_fmt_money(row.product_price)}\n\n"
        f"— <b>Расчетные метрики</b>\n"
        f"ОМ total: {_fmt_money(row.om_total)}\n"
        f"Marketing total: {_fmt_money(row.marketing_total)}\n"
        f"Lead cost total: <b>{_fmt_num(row.lead_cost_total, 4)}</b>\n"
        f"Lead cost OM: <b>{_fmt_num(row.lead_cost_om, 4)}</b>\n"
        f"Fixed costs total: {_fmt_money(row.fixed_costs_total)}\n\n"
        f"Profit manual (до фиксов): <b>{_fmt_num(row.profit_manual_before_fixed, 4)}</b>\n"
        f"Profit auto (до фиксов): <b>{_fmt_num(row.profit_auto_before_fixed, 4)}</b>\n"
        f"Profit full (до фиксов): <b>{_fmt_num(row.profit_full_before_fixed, 4)}</b>\n"
        f"Dir manual (10%): <b>{_fmt_num(row.dir_manual, 4)}</b>\n"
        f"Dir auto (10%): <b>{_fmt_num(row.dir_auto, 4)}</b>\n"
        f"Margin manual: <b>{_fmt_num(row.margin_manual, 4)}</b>\n"
        f"Margin auto: <b>{_fmt_num(row.margin_auto, 4)}</b>\n\n"
        f"Gross profit: {_fmt_money(row.gross_profit)}\n"
        f"Net profit: {_fmt_money(row.net_profit)}\n"
    )


async def show_unit_economics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💹 Юнит-экономика:\nВыберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["📌 Последний период", "📅 Выбрать период"],
                ["🔙 Назад"],
            ],
            one_time_keyboard=True,
            resize_keyboard=True,
        ),
    )
    return UE_MENU


async def show_latest_unit_economics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_latest_unit_economics(product_code="default")
    if not row:
        await update.message.reply_text(
            "Нет данных в `unit_economics`.\n"
            "Сначала добавьте запись за период (см. `unit_economics_queries.sql`).",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True),
        )
        return UE_MENU

    await update.message.reply_text(_format_unit_economics_row(row), parse_mode="HTML")
    return UE_MENU


async def unit_economics_request_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите начальную дату периода (ДД.ММ.ГГГГ):")
    return UE_START_PERIOD


async def unit_economics_handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return UE_START_PERIOD

    context.user_data["ue_period_start"] = start_date
    await update.message.reply_text("Введите конечную дату периода (ДД.ММ.ГГГГ):")
    return UE_END_PERIOD


async def unit_economics_handle_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        end_date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return UE_END_PERIOD

    start_date = context.user_data.get("ue_period_start")
    if not start_date:
        await update.message.reply_text("❌ Начальная дата не найдена. Начните заново.")
        return UE_START_PERIOD

    if end_date < start_date:
        await update.message.reply_text("❌ Конечная дата не может быть раньше начальной. Введите снова:")
        return UE_END_PERIOD

    context.user_data["ue_period_end"] = end_date
    await update.message.reply_text(
        "Введите product_code (или нажмите кнопку `default`):",
        reply_markup=ReplyKeyboardMarkup([["default"]], one_time_keyboard=True, resize_keyboard=True),
    )
    return UE_PRODUCT_CODE


async def unit_economics_handle_product_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_code = (update.message.text or "").strip() or "default"
    start_date = context.user_data.get("ue_period_start")
    end_date = context.user_data.get("ue_period_end")

    row = get_unit_economics(start_date, end_date, product_code=product_code)
    if not row:
        await update.message.reply_text(
            f"Нет записи за период {start_date:%d.%m.%Y} — {end_date:%d.%m.%Y} (product_code={product_code}).",
            reply_markup=ReplyKeyboardMarkup([["📌 Последний период", "📅 Выбрать период"], ["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True),
        )
        return UE_MENU

    await update.message.reply_text(_format_unit_economics_row(row), parse_mode="HTML")
    return UE_MENU


async def unit_economics_back_to_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_statistics_menu(update, context)


async def unit_economics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /unit_economics [ДД.ММ.ГГГГ] [ДД.ММ.ГГГГ] [product_code]
    Без аргументов — показывает последний период для product_code=default.
    """
    args = context.args or []
    if not args:
        row = get_latest_unit_economics(product_code="default")
        if not row:
            await update.message.reply_text("Нет данных в `unit_economics`.")
            return
        await update.message.reply_text(_format_unit_economics_row(row), parse_mode="HTML")
        return

    if len(args) < 2:
        await update.message.reply_text("Формат: /unit_economics ДД.ММ.ГГГГ ДД.ММ.ГГГГ [product_code]")
        return

    try:
        start_date = datetime.strptime(args[0].strip(), "%d.%m.%Y").date()
        end_date = datetime.strptime(args[1].strip(), "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("❌ Неверный формат дат. Используйте: ДД.ММ.ГГГГ")
        return

    product_code = args[2].strip() if len(args) >= 3 else "default"
    row = get_unit_economics(start_date, end_date, product_code=product_code)
    if not row:
        await update.message.reply_text(
            f"Нет записи за период {start_date:%d.%m.%Y} — {end_date:%d.%m.%Y} (product_code={product_code})."
        )
        return

    await update.message.reply_text(_format_unit_economics_row(row), parse_mode="HTML")

