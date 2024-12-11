from datetime import datetime

from commands.authorized_users import AUTHORIZED_USERS
from commands.logger import custom_logger
from commands.states import FIO, TELEGRAM, START_DATE, COURSE_TYPE, TOTAL_PAYMENT, PAID_AMOUNT, COMMISSION

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from student_management.student_management import get_all_students, add_student


# Добавление студента: шаг 1 - ввод ФИО
async def add_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Старт добавления студента: запрос ФИО.
    """
    await update.message.reply_text("Введите ФИО студента:")
    return FIO


# Добавление студента: шаг 2 - ввод Telegram
async def add_student_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос Telegram студента.
    """
    context.user_data["fio"] = update.message.text
    await update.message.reply_text("Введите Telegram студента:")
    return TELEGRAM


# Проверка уникальности Telegram
def is_telegram_unique(telegram, students):
    """
    Проверяет уникальность Telegram.
    """
    return all(student["Telegram"].lower() != telegram.lower() for student in students)


# Добавление студента: шаг 3 - ввод даты начала обучения
async def add_student_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос даты начала обучения.
    """
    telegram_account = update.message.text.strip()

    if not telegram_account.startswith("@") or len(telegram_account) <= 1:
        await update.message.reply_text(
            "Некорректный Telegram. Убедитесь, что он начинается с @. Попробуйте ещё раз."
        )
        return TELEGRAM

    students = get_all_students()
    if not is_telegram_unique(telegram_account, students):
        await update.message.reply_text(
            f"Студент с таким Telegram ({telegram_account}) уже существует. Введите другой Telegram."
        )
        return TELEGRAM

    # Сохраняем Telegram в context
    context.user_data["telegram"] = telegram_account

    # Добавляем клавиатуру с кнопкой "Сегодня"
    await update.message.reply_text(
        "Введите дату начала обучения (в формате ДД.ММ.ГГГГ) или нажмите 'Сегодня':",
        reply_markup=ReplyKeyboardMarkup(
            [["Сегодня"], ["Назад"]],
            one_time_keyboard=True
        )
    )
    return START_DATE


# Добавление студента: шаг 4 - выбор типа обучения
async def add_student_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка даты начала обучения.
    """
    try:
        date_text = update.message.text.strip()

        # Логика для кнопки "Сегодня"
        if date_text == "Сегодня":
            date_text = datetime.now().strftime("%d.%m.%Y")

        # Проверка формата даты
        datetime.strptime(date_text, "%d.%m.%Y")
        context.user_data["start_date"] = date_text

        await update.message.reply_text(
            f"Дата начала обучения установлена: {date_text}.\nВыберите тип обучения:",
            reply_markup=ReplyKeyboardMarkup(
                [['Ручное тестирование', 'Автотестирование', 'Фуллстек']],
                one_time_keyboard=True
            )
        )
        return COURSE_TYPE
    except ValueError:
        # Сообщение об ошибке и предложение повторного ввода
        await update.message.reply_text(
            "Дата должна быть в формате ДД.ММ.ГГГГ или нажмите 'Сегодня'. Попробуйте ещё раз:",
            reply_markup=ReplyKeyboardMarkup(
                [["Сегодня"], ["Назад"]],
                one_time_keyboard=True
            )
        )
        return START_DATE


# Добавление студента: шаг 5 - выбор стоимости обучения
async def add_student_course_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос стоимости обучения.
    """
    valid_course_types = ["Ручное тестирование", "Автотестирование", "Фуллстек"]
    course_type = update.message.text

    if course_type in valid_course_types:
        context.user_data["course_type"] = course_type
        await update.message.reply_text("Введите общую стоимость обучения:")
        return TOTAL_PAYMENT

    await update.message.reply_text(f"Некорректный тип обучения. Выберите: {', '.join(valid_course_types)}.")
    return COURSE_TYPE


# Добавление студента: шаг 6 - ввод общей стоимости
async def add_student_total_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return
    """
    Запрос внесённой оплаты.
    """
    try:
        total_payment = int(update.message.text)
        if total_payment > 0:
            context.user_data["total_payment"] = total_payment
            await update.message.reply_text("Введите сумму уже внесённой оплаты:")
            return PAID_AMOUNT

        await update.message.reply_text("Сумма должна быть больше 0. Попробуйте ещё раз.")
        return TOTAL_PAYMENT
    except ValueError:
        await update.message.reply_text("Введите корректное число. Попробуйте ещё раз.")
        return TOTAL_PAYMENT


# Шаг добавления комиссии
async def add_student_commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Завершение добавления студента с введением комиссии.
    """
    commission_input = update.message.text
    try:
        payments, percentage = map(str.strip, commission_input.split(","))
        payments, percentage = int(payments), int(percentage.strip('%'))

        if payments <= 0 or percentage <= 0:
            raise ValueError("Комиссия должна быть положительным числом.")

        context.user_data["commission"] = f"{payments}, {percentage}%"

        # Сохранение данных
        add_student(
            context.user_data["fio"], context.user_data["telegram"],
            context.user_data["start_date"], context.user_data["course_type"],
            context.user_data["total_payment"], context.user_data["paid_amount"],
            "Да" if context.user_data["paid_amount"] == context.user_data["total_payment"] else "Нет",
            context.user_data["commission"]
        )

        editor_tg = update.message.from_user.username
        custom_logger.info(f"@{editor_tg} добавил студента: {context.user_data}")
        await update.message.reply_text("Студент успешно добавлен!")
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("Введите корректные данные о комиссии (например: '2, 50'). Попробуйте ещё раз.")
        return COMMISSION

async def add_student_paid_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        paid_amount = int(update.message.text)
        total_payment = context.user_data["total_payment"]

        if 0 <= paid_amount <= total_payment:
            fully_paid = "Да" if paid_amount == total_payment else "Нет"
            context.user_data["paid_amount"] = paid_amount

            # Переходим к вводу комиссии
            await update.message.reply_text(
                "Введите данные о комиссии (в формате: Количество выплат, Процент). Например: '2, 50%'",
            )
            return COMMISSION
        else:
            await update.message.reply_text(
                f"Сумма оплаты должна быть в пределах от 0 до {total_payment}. Попробуйте ещё раз."
            )
            return PAID_AMOUNT
    except ValueError:
        await update.message.reply_text(
            "Введите корректное число. Попробуйте ещё раз."
        )