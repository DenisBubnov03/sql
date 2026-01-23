from __future__ import annotations
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
from data_base.models import StudentMeta, Payment, MarketingSpend, FixedExpense, Student

from datetime import datetime
from sqlalchemy import func
from data_base.db import session
from data_base.models import StudentMeta, Payment, MarketingSpend, FixedExpense


def _fmt_money(v):
    return f"{float(v or 0):,.0f}".replace(",", " ") + " ₽"


# --- КОНСТАНТЫ ЗП (Меняй только здесь, и всё обновится само) ---
RESERVE_M = 9200
RESERVE_A = 17200
RESERVE_F = RESERVE_A + RESERVE_M


def calculate_ue_data(start_date, end_date):
    # 1. ОБЩАЯ ВЫРУЧКА
    revenue_total = session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date.between(start_date, end_date),
        Payment.status == "подтвержден",
        ~Payment.comment.ilike("%Системное восстановление%"),
        ~Payment.comment.ilike("%Доп расход%")
    ).scalar() or 0

    # 2. НОВЫЕ ОМ-ЩИКИ
    new_om_students = (
        session.query(Student.id, Student.training_type)
        .join(StudentMeta, StudentMeta.student_id == Student.id)
        .filter(
            StudentMeta.created_at.between(start_date, end_date),
            StudentMeta.source.ilike("%ОМ%")
        ).all()
    )

    m_om, a_om, f_om = set(), set(), set()
    for s_id, t_type in new_om_students:
        t_type_low = (t_type or "").lower()
        if "фулл" in t_type_low:
            f_om.add(s_id)
        elif "авто" in t_type_low:
            a_om.add(s_id)
        elif "ручн" in t_type_low:
            m_om.add(s_id)

    count_m_om, count_a_om, count_f_om = len(m_om), len(a_om), len(f_om)
    total_om = count_m_om + count_a_om + count_f_om

    # 3. ВСЕ НОВЫЕ (для общего резерва ЗП)
    all_new_raw = (
        session.query(Student.id, Student.training_type)
        .join(StudentMeta, StudentMeta.student_id == Student.id)
        .filter(StudentMeta.created_at.between(start_date, end_date))
        .all()
    )

    m_all, a_all, f_all = set(), set(), set()
    for s_id, t_type in all_new_raw:
        t_type_low = (t_type or "").lower()
        if "фулл" in t_type_low:
            f_all.add(s_id)
        elif "авто" in t_type_low:
            a_all.add(s_id)
        elif "ручн" in t_type_low:
            m_all.add(s_id)

    count_m_all, count_a_all, count_f_all = len(m_all), len(a_all), len(f_all)

    # 4. МАРКЕТИНГ И ФИКСЫ
    m_spend = session.query(MarketingSpend.channel, func.sum(MarketingSpend.amount)).filter(
        MarketingSpend.report_month.between(start_date, end_date)
    ).group_by(MarketingSpend.channel).all()

    m_map = {c: float(a) for c, a in m_spend}
    om_m_cost = m_map.get('om_manual', 0)
    om_a_cost = m_map.get('om_auto', 0)
    om_total = om_m_cost + om_a_cost
    marketing_total = om_total + m_map.get('avito', 0) + m_map.get('media', 0)

    fixed_other = session.query(func.sum(FixedExpense.amount)).filter(
        FixedExpense.report_month.between(start_date, end_date)
    ).scalar() or 0

    # 5. МЕТРИКИ И МАРЖА
    client_cost_om = om_total / total_om if total_om > 0 else 0
    cost_manual, cost_avto, cost_full = 46000, 86000, 96000

    margin_m = cost_manual - client_cost_om - RESERVE_M
    margin_a = cost_avto - client_cost_om - RESERVE_A
    margin_f = cost_full - client_cost_om - RESERVE_F

    # 6. РЕЗЕРВЫ (Синхронизировано с константами)
    res_om = (count_m_om * RESERVE_M) + (count_a_om * RESERVE_A) + (count_f_om * RESERVE_F)
    res_all = (count_m_all * RESERVE_M) + (count_a_all * RESERVE_A) + (count_f_all * RESERVE_F)

    # 7. ПРИБЫЛЬ
    gross_before_fixed = float(revenue_total) - marketing_total
    net_profit = gross_before_fixed - float(fixed_other) - res_all

    return {
        "revenue": revenue_total, "om_m_cost": om_m_cost, "om_a_cost": om_a_cost,
        "om_total": om_total, "cac": client_cost_om, "gross_bf": gross_before_fixed,
        "m_m": margin_m, "m_a": margin_a, "m_f": margin_f,
        "c_m_om": count_m_om, "c_a_om": count_a_om, "c_f_om": count_f_om,
        "c_m_all": count_m_all, "c_a_all": count_a_all, "c_f_all": count_f_all,
        "res_om": res_om, "res_all": res_all, "fixed": fixed_other, "net": net_profit
    }


def _format_report(d):
    return (
        f"💹 <b>Юнит-экономика</b>\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"— Выручка: {_fmt_money(d['revenue'])}\n"
        f"— Gross profit before fixed: <b>{_fmt_money(d['gross_bf'])}</b>\n\n"

        f"🎯 <b>Маркетинг ОМ:</b>\n"
        # f"  ├ OM manual: {_fmt_money(d['om_m_cost'])}\n"
        # f"  └ OM auto: {_fmt_money(d['om_a_cost'])}\n"
        # f"— <b>OM total: {_fmt_money(d['om_total'])}</b>\n"
        f"— Клиентов ОМ: <b>{d['c_m_om'] + d['c_a_om'] + d['c_f_om']}</b>\n"
        f"— Сlient cost OM: <b>{_fmt_money(d['cac'])}</b>\n\n"

        # f"👨‍🏫 <b>Резерв ЗП менторов (Только ОМ):</b>\n"
        # f"— Ручное ({d['c_m_om']} чел): {_fmt_money(d['c_m_om'] * RESERVE_M)}\n"
        # f"— Авто ({d['c_a_om']} чел): {_fmt_money(d['c_a_om'] * RESERVE_A)}\n"
        # f"— Fullstack ({d['c_f_om']} чел): {_fmt_money(d['c_f_om'] * RESERVE_F)}\n"
        # f"📌 Итого ЗП (ОМ): {_fmt_money(d['res_om'])}\n\n"
        # 
        # f"🏢 <b>ОБЩИЕ расходы (Все новые):</b>\n"
        # f"— Ручное ({d['c_m_all']} чел): {_fmt_money(d['c_m_all'] * RESERVE_M)}\n"
        # f"— Авто ({d['c_a_all']} чел): {_fmt_money(d['c_a_all'] * RESERVE_A)}\n"
        # f"— Fullstack ({d['c_f_all']} чел): {_fmt_money(d['c_f_all'] * RESERVE_F)}\n"
        # f"— Прочие фиксы: {_fmt_money(d['fixed'])}\n"
        # f"💰 <b>ИТОГО РАСХОДОВ: {_fmt_money(d['res_all'] + d['fixed'])}</b>\n\n"

        f"📈 <b>Маржа с ОМ продукта:</b>\n"
        f"— Manual: <b>{_fmt_money(d['m_m'])}</b>\n"
        f"— Auto: <b>{_fmt_money(d['m_a'])}</b>\n"
        f"— Fullstack: <b>{_fmt_money(d['m_f'])}</b>\n\n"

        # f"🏁 <b>Чистая прибыль (net_profit): {_fmt_money(d['net'])}</b>"
    )


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


import traceback

import traceback


async def unit_economics_handle_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        end_date = datetime.strptime(text, "%d.%m.%Y").date()
        start_date = context.user_data.get("ue_period_start")

        # 1. Считаем
        data = calculate_ue_data(start_date, end_date)

        # 2. Проверяем, не вернулась ли ошибка вместо словаря
        if isinstance(data, str):
            await update.message.reply_text(f"🚨 Ошибка в расчетах:\n<code>{data}</code>", parse_mode="HTML")
            return UE_MENU

        # 3. Форматируем (твой шаблон)
        msg = _format_report(data)
        await update.message.reply_text(msg, parse_mode="HTML")
        return UE_MENU

    except Exception:
        err = traceback.format_exc()
        await update.message.reply_text(f"🚨 Критическая ошибка:\n<code>{err}</code>", parse_mode="HTML")
        return UE_MENU


async def unit_economics_back_to_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_statistics_menu(update, context)


async def unit_economics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Для быстрой команды через слэш
    start_date = datetime.now().replace(day=1).date()
    end_date = datetime.now().date()
    data = calculate_ue_data(start_date, end_date)
    await update.message.reply_text(_format_report(data), parse_mode="HTML")