from data_base.db import session
from data_base.models import Mentor, Payment
from commands.start_commands import exit_to_main_menu
from commands.states import AWAIT_MENTOR_TG, AWAIT_BONUS_AMOUNT
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime


async def start_bonus_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите Telegram куратора (например: @mentor):")
    return AWAIT_MENTOR_TG


async def handle_mentor_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.message.text.strip()
    mentor = session.query(Mentor).filter(Mentor.telegram == tg).first()

    if not mentor:
        await update.message.reply_text("❌ Куратор не найден. Попробуйте снова или нажмите 'Главное меню'.",
                                        reply_markup=ReplyKeyboardMarkup([["Главное меню"]], one_time_keyboard=True))
        return AWAIT_MENTOR_TG

    context.user_data["mentor_id"] = mentor.id
    context.user_data["mentor_name"] = mentor.full_name
    await update.message.reply_text(f"Куратор найден: {mentor.full_name}\nВведите сумму премии:")
    return AWAIT_BONUS_AMOUNT


async def handle_bonus_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной.")

        mentor_id = context.user_data["mentor_id"]
        new_payment = Payment(
            student_id=0,
            mentor_id=mentor_id,
            amount=amount,
            payment_date=datetime.now().date(),
            comment="Премия",
            status="подтвержден"
        )
        session.add(new_payment)
        session.commit()

        await update.message.reply_text(
            f"✅ Премия {amount} руб. успешно добавлена для куратора {context.user_data['mentor_name']}."
        )
        return await exit_to_main_menu(update, context)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}. Введите сумму ещё раз.")
        return AWAIT_BONUS_AMOUNT
