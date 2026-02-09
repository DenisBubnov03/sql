import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from data_base.db import session
from data_base.models import Student, StudentMeta, MarketingSpend
from commands.states import REF_MENU, REF_WAIT_TG, REF_CONFIRM_PAYOUT
from commands.start_commands import exit_to_main_menu

# Клавиатуры
ref_main_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("🏠 Внутренняя"), KeyboardButton("🌍 Внешняя")],
    [KeyboardButton("⬅️ Назад")]
], resize_keyboard=True)

inner_ref_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("💰 Выплатить всем")],
    [KeyboardButton("👤 Выплатить одному")],
    [KeyboardButton("⬅️ Назад")]
], resize_keyboard=True)

confirm_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("✅ Подтвердить"), KeyboardButton("❌ Отмена")]
], resize_keyboard=True)


def get_referral_debtors_list():
    """Находит рефералов с полной оплатой, которым еще не выплатили бонус."""
    return (
        session.query(Student.fio, StudentMeta.referrer_telegram, Student.telegram, StudentMeta)
        .join(StudentMeta, StudentMeta.student_id == Student.id)
        .filter(
            StudentMeta.is_referral == True,
            StudentMeta.ref_paid == False,
            Student.fully_paid == "Да"  # СТРОГОЕ УСЛОВИЕ ТЗ
        ).all()
    )


async def start_ref_module(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите тип реферальной программы:", reply_markup=ref_main_keyboard)
    return REF_MENU


async def show_external_refs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вместо лямбды - нормальная функция"""
    await update.message.reply_text("Модуль внешних рефералок в разработке... 🏗")
    return REF_MENU


async def show_inner_refs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debtors = get_referral_debtors_list()
    if not debtors:
        await update.message.reply_text("Долгов по рефералкам (с полной оплатой) нет! 🎉")
        return REF_MENU

    grouped = {}
    for fio, ref_tg, s_tg, _ in debtors:
        ref_key = ref_tg if ref_tg else "Неизвестно"
        if ref_key not in grouped: grouped[ref_key] = []
        grouped[ref_key].append(f"{fio} ({s_tg})")

    msg = "<b>Список задолженностей (Полная оплата):</b>\n\n"
    grand_total = 0
    for ref_tg, students in grouped.items():
        sub_total = len(students) * 5000
        grand_total += sub_total
        msg += f"<b>Кому платим: {ref_tg}</b>\nКого привел:\n"
        for s in students: msg += f"  • {s}\n"
        msg += f"<b>Итого {sub_total}</b>\n---------------------------\n\n"

    msg += f"<b>ВСЕГО К ВЫПЛАТЕ: {grand_total} ₽</b>"
    await update.message.reply_text(msg, reply_markup=inner_ref_keyboard, parse_mode="HTML")
    return REF_MENU


async def ask_ref_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите Telegram того, кому платим:",
                                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Назад")]],
                                                                     resize_keyboard=True))
    return REF_WAIT_TG


async def process_single_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_tg = update.message.text.strip().replace("@", "")
    debtors = get_referral_debtors_list()
    found = [d for d in debtors if d[1] and d[1].replace("@", "") == target_tg]

    if not found:
        await update.message.reply_text(f"Долгов перед @{target_tg} не найдено.")
        return REF_MENU

    context.user_data['payout_mode'] = 'single'
    context.user_data['payout_target_tg'] = target_tg
    await update.message.reply_text(f"Выплатить {len(found) * 5000}₽ для @{target_tg}?", reply_markup=confirm_keyboard)
    return REF_CONFIRM_PAYOUT


async def handle_payout_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['payout_mode'] = 'all'
    await update.message.reply_text("Выплатить ВСЕ задолженности?", reply_markup=confirm_keyboard)
    return REF_CONFIRM_PAYOUT


async def confirm_single_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('payout_mode')
    target_tg = context.user_data.get('payout_target_tg')
    report_month = datetime.now().replace(day=1).date()

    try:
        debtors = get_referral_debtors_list()
        to_pay = [d for d in debtors if d[1] and d[1].replace("@", "") == target_tg] if mode == 'single' else debtors

        for fio, ref_tg, s_tg, meta_obj in to_pay:
            meta_obj.ref_paid = True
            session.add(MarketingSpend(
                report_month=report_month,
                channel=f"ref {ref_tg}",
                amount=5000
            ))
        session.commit()
        await update.message.reply_text("✅ Выплаты подтверждены!", reply_markup=ref_main_keyboard)
    except Exception as e:
        session.rollback()
        await update.message.reply_text(f"❌ Ошибка БД: {e}")

    return REF_MENU