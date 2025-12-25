from check_postpayment_job import logger
from data_base.db import session
from data_base.models import Mentor, Payment, Salary, SalaryKK
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
        # Парсим сумму
        amount_str = update.message.text.strip().replace(',', '.')
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной.")

        # Достаем данные из контекста (кто именно получает премию)
        mentor_id = context.user_data.get("mentor_id")
        kk_id = context.user_data.get("kk_id")

        # Определяем имя для сообщения (кто бы это ни был)
        staff_name = context.user_data.get("mentor_name") or context.user_data.get("kk_name") or "Сотрудник"

        # 1. СОЗДАЕМ ОБЩИЙ ПЛАТЕЖ (для истории транзакций)
        new_payment = Payment(
            student_id=None,  # Премия не привязана к студенту
            mentor_id=mentor_id if mentor_id else None,
            amount=amount,
            payment_date=datetime.now().date(),
            comment=f"Премия: {staff_name}",
            status="подтвержден"
        )
        session.add(new_payment)

        # flush позволяет получить ID платежа, не закрывая транзакцию коммитом
        session.flush()

        # 2. ДУБЛИРУЕМ В ЗАРПЛАТНУЮ ТАБЛИЦУ
        if mentor_id:
            # Если это МЕНТОР — пишем в Salary
            new_salary_entry = Salary(
                mentor_id=mentor_id,
                calculated_amount=amount,
                date_calculated=datetime.utcnow(),
                is_paid=False,
                comment=f"🎁 Премия (ID платежа: {new_payment.id})"
            )
            session.add(new_salary_entry)

        elif kk_id:
            # Если это КК — пишем в SalaryKK
            new_kk_salary = SalaryKK(
                payment_id=new_payment.id,
                kk_id=kk_id,
                student_id=0,  # Технический ID (так как премия общая, а не за ученика)
                calculated_amount=amount,
                total_potential=0,
                remaining_limit=0,
                is_paid=False,
                date_calculated=datetime.utcnow(),
                comment=f"🎁 Премия КК (ID платежа: {new_payment.id})"
            )
            session.add(new_kk_salary)

        # Фиксируем обе записи в базе одной транзакцией
        session.commit()

        await update.message.reply_text(
            f"✅ Премия <b>{amount:,.2f} руб.</b> успешно начислена сотруднику <b>{staff_name}</b>.\n"
            f"Запись добавлена в реестр выплат.",
            parse_mode="HTML"
        )

        return await exit_to_main_menu(update, context)

    except ValueError:
        await update.message.reply_text("❌ Ошибка: Введите корректное число (сумму премии).")
        return "WAIT_FOR_BONUS_AMOUNT"
    except Exception as e:
        session.rollback()  # Отменяем всё, если произошла ошибка
        logger.error(f"Ошибка при начислении премии: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка при сохранении: {e}")
        return await exit_to_main_menu(update, context)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}. Введите сумму ещё раз.")
        return AWAIT_BONUS_AMOUNT
