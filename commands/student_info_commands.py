from commands.authorized_users import AUTHORIZED_USERS
from commands.states import FIO_OR_TELEGRAM

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from data_base.db import session
from data_base.models import Mentor
from data_base.operations import get_all_students, get_student_by_fio_or_telegram


async def search_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрашивает ввод для поиска студента по ФИО или Telegram с возможностью возврата в главное меню.
    """
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return ConversationHandler.END

    # Проверяем, ввел ли пользователь "Главное меню"
    search_query = update.message.text.strip() if update.message else None
    if search_query == "Главное меню":
        await update.message.reply_text(
            "Возвращаемся в главное меню:",
            reply_markup=ReplyKeyboardMarkup(
                [
        ['Добавить студента', 'Просмотреть студентов'],
        ['Редактировать данные студента', 'Проверить уведомления'],
        ['Поиск ученика', 'Статистика', "📊 Рассчитать зарплату"]
    ],
                one_time_keyboard=True
            )
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Введите ФИО или Telegram ученика, информацию о котором хотите посмотреть:",
        reply_markup=ReplyKeyboardMarkup(
            [["Главное меню"]],
            one_time_keyboard=True
        )
    )
    return FIO_OR_TELEGRAM



def calculate_commission(student):
    """
    Вычисляет общую комиссию и уже выплаченную сумму для студента.
    """
    try:
        # Разделяем данные комиссии (количество выплат, процент)
        commission_info = student.commission.split(", ")
        payments = int(commission_info[0]) if len(commission_info) > 0 and commission_info[0].isdigit() else 0
        percentage = int(commission_info[1].replace("%", "")) if len(commission_info) > 1 else 0

        # Зарплата
        salary = student.salary or 0

        # Расчёт общей комиссии
        total_commission = (salary * percentage / 100) * payments

        # Выплаченная комиссия
        paid_commission = student.commission_paid or 0

        return total_commission, paid_commission
    except Exception as e:
        print(f"Ошибка при расчёте комиссии: {e}")
        return 0, 0


async def display_student_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ищет информацию о студенте и выводит её.
    """

    # Проверяем, ввел ли пользователь "Главное меню"
    search_query = update.message.text.strip() if update.message else None
    if search_query == "Главное меню":
        await update.message.reply_text(
            "Возвращаемся в главное меню:",
            reply_markup=ReplyKeyboardMarkup(
                [
                    ['Добавить студента', 'Просмотреть студентов'],
                    ['Редактировать данные студента', 'Проверить уведомления'],
                    ['Поиск ученика', 'Статистика', "📊 Рассчитать зарплату"]
                ],
                one_time_keyboard=True
            )
        )
        return ConversationHandler.END

    # Получаем студента
    student = get_student_by_fio_or_telegram(search_query)
    mentor = session.query(Mentor).filter(Mentor.id == student.mentor_id).first()
    mentor_name = mentor.full_name if mentor else f"ID {student.mentor_id}"

    if not student:
        await update.message.reply_text("Ученик не найден. Попробуйте ещё раз.")
        return FIO_OR_TELEGRAM


    # Проверяем наличие данных для комиссии
    if not student.commission or "," not in student.commission:
        total_commission, paid_commission = 0, 0
    else:
        total_commission, paid_commission = calculate_commission(student)

    commission_info = f"{paid_commission} из {total_commission}"

    # Формируем информацию о студенте
    info = "\n".join([
        f"ФИО: {student.fio}",
        f"Telegram: {student.telegram}",
        f"Ментор: {mentor_name}",
        f"Дата начала обучения: {student.start_date}",
        f"Тип обучения: {student.training_type}",
        f"Общая стоимость: {student.total_cost}",
        f"Оплачено: {student.payment_amount}",
        f"Полностью оплачено: {student.fully_paid}",
        f"Компания: {student.company}",
        f"Зарплата: {student.salary}",
        f"Комиссия: {student.commission}",
        f"Комиссия выплачено: {commission_info}",
        f"Статус обучения: {student.training_status}"
    ])

    # Отправляем информацию пользователю
    await update.message.reply_text(
        f"Информация об ученике:\n\n{info}",
        reply_markup=ReplyKeyboardMarkup(
            [
                ['Добавить студента', 'Просмотреть студентов'],
                ['Редактировать данные студента', 'Проверить уведомления'],
                ['Поиск ученика', 'Статистика']
            ],
            one_time_keyboard=True
        )
    )
    return ConversationHandler.END

