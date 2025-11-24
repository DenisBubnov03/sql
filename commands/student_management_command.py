from datetime import datetime
import logging
import asyncio
from sqlalchemy import func
from sqlalchemy import select
from commands.authorized_users import AUTHORIZED_USERS
from commands.logger import custom_logger
from commands.start_commands import exit_to_main_menu
from commands.states import FIO, TELEGRAM, START_DATE, COURSE_TYPE, TOTAL_PAYMENT, PAID_AMOUNT, \
    SELECT_MENTOR, MAIN_MENU, IS_REFERRAL, REFERRER_TELEGRAM, STUDENT_SOURCE

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from data_base.db import session
from data_base.models import Payment, Mentor, Student, CareerConsultant
from data_base.operations import get_student_by_fio_or_telegram
from student_management.student_management import add_student

# Импорты
from datetime import datetime, date
from data_base.db import session
from data_base.models import StudentMeta, Mentor

logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


def split_long_message(text, max_length=4000):
    """
    Разбивает длинное сообщение на части, не превышающие max_length символов.
    """
    if len(text) <= max_length:
        return [text]
    
    logger.info(f"Сообщение слишком длинное ({len(text)} символов), разбиваю на части...")
    
    parts = []
    current_part = ""
    
    # Разбиваем по строкам
    lines = text.split('\n')
    
    for line in lines:
        # Если добавление строки превысит лимит
        if len(current_part) + len(line) + 1 > max_length:
            if current_part:
                parts.append(current_part.strip())
                current_part = line + '\n'
            else:
                # Если одна строка слишком длинная, разбиваем её
                if len(line) > max_length:
                    # Разбиваем по словам
                    words = line.split(' ')
                    temp_line = ""
                    for word in words:
                        if len(temp_line) + len(word) + 1 > max_length:
                            if temp_line:
                                parts.append(temp_line.strip())
                                temp_line = word + ' '
                            else:
                                # Если одно слово слишком длинное, разбиваем по символам
                                parts.append(word[:max_length])
                                temp_line = word[max_length:] + ' '
                        else:
                            temp_line += word + ' '
                    if temp_line.strip():
                        current_part = temp_line
                else:
                    current_part = line + '\n'
        else:
            current_part += line + '\n'
    
    if current_part.strip():
        parts.append(current_part.strip())
    
    logger.info(f"Сообщение разбито на {len(parts)} частей")
    return parts


# Добавление студента: шаг 1 - ввод ФИО
async def add_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Старт добавления студента: запрос ФИО.
    """
    # Очищаем id менторов для нового сценария
    context.user_data.pop('mentor_id', None)
    context.user_data.pop('auto_mentor_id', None)
    await update.message.reply_text(
        "Введите ФИО студента:",
        reply_markup=ReplyKeyboardMarkup(
            [["Главное меню"]],
            one_time_keyboard=True
        )
    )
    return FIO


# Добавление студента: шаг 2 - ввод Telegram
async def add_student_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос Telegram студента.
    """
    # Если пользователь нажал "Главное меню"
    if update.message.text.strip() == "Главное меню":
            return await exit_to_main_menu(update, context)

    # Сохранение ФИО
    context.user_data["fio"] = update.message.text.strip()
    await update.message.reply_text(
        "Введите Telegram студента:",
        reply_markup=ReplyKeyboardMarkup(
            [["Главное меню"]],
            one_time_keyboard=True
        )
    )
    return TELEGRAM


# Проверка уникальности Telegram
def is_telegram_unique(telegram):
    """
    Проверяет уникальность Telegram в базе данных.
    """
    student = get_student_by_fio_or_telegram(telegram)
    return student is None


# Добавление студента: шаг 3 - ввод даты начала обучения
async def add_student_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос даты начала обучения.
    """
    telegram_account = update.message.text.strip()

    # Обработка кнопки "Главное меню"
    if telegram_account == "Главное меню":
        return await exit_to_main_menu(update, context)

    # Проверка корректности введенного Telegram
    if not telegram_account.startswith("@") or len(telegram_account) <= 1:
        await update.message.reply_text(
            "Некорректный Telegram. Убедитесь, что он начинается с @. Попробуйте ещё раз.",
            reply_markup=ReplyKeyboardMarkup(
                [["Главное меню"]],
                one_time_keyboard=True
            )
        )
        return TELEGRAM

    # Проверка на уникальность Telegram
    if not is_telegram_unique(telegram_account):
        await update.message.reply_text(
            f"Студент с таким Telegram ({telegram_account}) уже существует. Введите другой Telegram.",
            reply_markup=ReplyKeyboardMarkup(
                [["Главное меню"]],
                one_time_keyboard=True
            )
        )
        return TELEGRAM

    # Сохраняем Telegram в context
    context.user_data["telegram"] = telegram_account

    # Запрос даты начала обучения
    await update.message.reply_text(
        "Введите дату начала обучения (в формате ДД.ММ.ГГГГ) или нажмите 'Сегодня':",
        reply_markup=ReplyKeyboardMarkup(
            [["Сегодня"], ["Главное меню"]],
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

        if date_text == "Сегодня":
            date_text = datetime.now().strftime("%d.%m.%Y")

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
        await update.message.reply_text(
            "Дата должна быть в формате ДД.ММ.ГГГГ или нажмите 'Сегодня'. Попробуйте ещё раз:"
        )
        return START_DATE


async def handle_mentor_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = update.message.text.strip()
    mentors_dict = context.user_data.get("mentors_list", {})
    mentor_id = mentors_dict.get(selected)

    if not mentor_id:
        await update.message.reply_text("Выберите одного из предложенных менторов.")
        return "WAIT_FOR_MENTOR_CHOICE"

    context.user_data["mentor_id"] = mentor_id
    await update.message.reply_text("Введите общую стоимость обучения:")
    return TOTAL_PAYMENT


# Добавление студента: шаг 5 - выбор стоимости обучения
async def add_student_course_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка выбора направления обучения. После выбора всегда идёт шаг выбора ментора.
    """
    valid_course_types = ["Ручное тестирование", "Автотестирование", "Фуллстек"]
    course_type = update.message.text.strip()

    if course_type not in valid_course_types:
        await update.message.reply_text(f"❌ Неверный выбор. Выберите: {', '.join(valid_course_types)}.")
        return COURSE_TYPE

    context.user_data["course_type"] = course_type
    return await select_mentor_by_direction(update, context)


# Добавление студента: шаг 6 - ввод общей стоимости
async def add_student_total_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def add_student_paid_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос данных о внесённой оплате.
    """
    try:
        paid_amount = int(update.message.text)
        total_payment = context.user_data["total_payment"]

        if 0 <= paid_amount <= total_payment:
            context.user_data["paid_amount"] = paid_amount
            # Устанавливаем комиссию в зависимости от типа обучения
            course_type = context.user_data.get("course_type", "")
            if course_type == "Фуллстек":
                context.user_data["commission"] = "2, 65%"
            else:
                context.user_data["commission"] = "2, 55%"
            
            # Переходим к вопросу о рефералке
            await update.message.reply_text(
                "По реферальной ли системе пришел студент?",
                reply_markup=ReplyKeyboardMarkup(
                    [["Да", "Нет"]],
                    one_time_keyboard=True
                )
            )
            return IS_REFERRAL
        else:
            await update.message.reply_text(
                f"Сумма оплаты должна быть в пределах от 0 до {total_payment}. Попробуйте ещё раз."
            )
            return PAID_AMOUNT
    except ValueError:
        await update.message.reply_text("Введите корректное число. Попробуйте ещё раз.")
        return PAID_AMOUNT


# Обработчик вопроса о рефералке
async def add_student_is_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка вопроса о том, является ли студент реферальным.
    """
    response = update.message.text.strip()
    
    if response == "Да":
        context.user_data["is_referral"] = True
        await update.message.reply_text(
            "Введите Telegram того, кто зарефералил студента:",
            reply_markup=ReplyKeyboardMarkup(
                [["Главное меню"]],
                one_time_keyboard=True
            )
        )
        return REFERRER_TELEGRAM
    elif response == "Нет":
        context.user_data["is_referral"] = False
        context.user_data["referrer_telegram"] = None
        # Переходим к вопросу об источнике
        await update.message.reply_text(
            "Откуда пришел студент?",
            reply_markup=ReplyKeyboardMarkup(
                [["ОМ", "Ютуб", "Инстаграм"], ["Авито", "Сайт", "Через знакомых"], ["Пусто"]],
                one_time_keyboard=True
            )
        )
        return STUDENT_SOURCE
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите 'Да' или 'Нет'.",
            reply_markup=ReplyKeyboardMarkup(
                [["Да", "Нет"]],
                one_time_keyboard=True
            )
        )
        return IS_REFERRAL


# Обработчик ввода Telegram реферера
async def add_student_referrer_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ввода Telegram реферера.
    """
    referrer_telegram = update.message.text.strip()
    
    # Обработка кнопки "Главное меню"
    if referrer_telegram == "Главное меню":
        return await exit_to_main_menu(update, context)
    
    # Проверка корректности введенного Telegram
    if not referrer_telegram.startswith("@") or len(referrer_telegram) <= 1:
        await update.message.reply_text(
            "Некорректный Telegram. Убедитесь, что он начинается с @. Попробуйте ещё раз.",
            reply_markup=ReplyKeyboardMarkup(
                [["Главное меню"]],
                one_time_keyboard=True
            )
        )
        return REFERRER_TELEGRAM
    
    context.user_data["referrer_telegram"] = referrer_telegram
    
    # Переходим к вопросу об источнике
    await update.message.reply_text(
        "Откуда пришел студент?",
        reply_markup=ReplyKeyboardMarkup(
            [["ОМ", "Ютуб", "Инстаграм"], ["Авито", "Сайт", "Через знакомых"], ["Пусто"]],
            one_time_keyboard=True
        )
    )
    return STUDENT_SOURCE


# Обработчик выбора источника
async def add_student_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка выбора источника привлечения студента.
    """
    source = update.message.text.strip()
    valid_sources = ["ОМ", "Ютуб", "Инстаграм", "Авито", "Сайт", "Через знакомых", "Пусто"]
    
    if source not in valid_sources:
        await update.message.reply_text(
            f"Пожалуйста, выберите один из предложенных вариантов: {', '.join(valid_sources)}",
            reply_markup=ReplyKeyboardMarkup(
                [["ОМ", "Ютуб", "Инстаграм"], ["Авито", "Сайт", "Через знакомых"], ["Пусто"]],
                one_time_keyboard=True
            )
        )
        return STUDENT_SOURCE
    
    context.user_data["source"] = source
    
    # Теперь создаем студента с мета-данными
    return await create_student_with_meta(update, context)


# Функция создания студента с мета-данными
async def create_student_with_meta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Создает студента и его мета-данные в базе данных.
    """
    try:
        # Обработка даты
        start_date_str = context.user_data["start_date"]
        if isinstance(start_date_str, str):
            try:
                start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
            except Exception:
                start_date = None
        else:
            start_date = start_date_str
                
        # Создаем студента
        student_id = add_student(
            fio=context.user_data["fio"],
            telegram=context.user_data["telegram"],
            start_date=start_date,
            training_type=context.user_data["course_type"],
            total_cost=context.user_data["total_payment"],
            payment_amount=context.user_data.get("paid_amount", 0),
            fully_paid="Да" if context.user_data.get("paid_amount", 0) == context.user_data["total_payment"] else "Нет",
            commission=context.user_data["commission"],
            mentor_id=context.user_data.get("mentor_id"),
            auto_mentor_id=context.user_data.get("auto_mentor_id")
        )

        if not student_id:
            await update.message.reply_text("❌ Ошибка: студент не был создан.")
            return ConversationHandler.END

        context.user_data["id"] = student_id

        # Создаем мета-данные студента
        student_meta = StudentMeta(
            student_id=student_id,
            is_referral=context.user_data.get("is_referral", False),
            referrer_telegram=context.user_data.get("referrer_telegram"),
            source=context.user_data.get("source"),
            created_at=date.today()
        )
        
        session.add(student_meta)
        session.commit()

        # Записываем платёж
        course_type = context.user_data.get("course_type")
        mentor_id = context.user_data.get("mentor_id")
        auto_mentor_id = context.user_data.get("auto_mentor_id")
        if course_type == "Фуллстек":
            payment_mentor_id = auto_mentor_id
        else:
            payment_mentor_id = mentor_id if mentor_id else auto_mentor_id
        if payment_mentor_id is not None:
            record_initial_payment(student_id, context.user_data.get("paid_amount", 0), payment_mentor_id)

        # Получаем имена менторов
        mentor_id = context.user_data.get("mentor_id")
        auto_mentor_id = context.user_data.get("auto_mentor_id")
        mentor_name = None
        auto_mentor_name = None
        if mentor_id:
            mentor = session.query(Mentor).filter(Mentor.id == mentor_id).first()
            mentor_name = mentor.full_name if mentor else f"ID {mentor_id}"
        else:
            mentor_name = "Не назначен"
        if auto_mentor_id:
            auto_mentor = session.query(Mentor).filter(Mentor.id == auto_mentor_id).first()
            auto_mentor_name = auto_mentor.full_name if auto_mentor else f"ID {auto_mentor_id}"
        else:
            auto_mentor_name = "Не назначен"

        # Финальное сообщение
        msg = f"✅ Студент {context.user_data['fio']} добавлен!\n"
        if mentor_name and auto_mentor_name:
            msg += f"Ручной ментор: {mentor_name}\nАвто-ментор: {auto_mentor_name}"
        elif mentor_name:
            msg += f"Ручной ментор: {mentor_name}"
        elif auto_mentor_name:
            msg += f"Авто-ментор: {auto_mentor_name}"
        else:
            msg += "Ментор не выбран."
        
        # Добавляем информацию о рефералке и источнике
        if context.user_data.get("is_referral"):
            msg += f"\n\n📋 Реферальная система: Да\n👤 Реферер: {context.user_data.get('referrer_telegram')}"
        else:
            msg += f"\n\n📋 Реферальная система: Нет"
        
        if context.user_data.get("source"):
            msg += f"\n📊 Источник: {context.user_data.get('source')}"

        await update.message.reply_text(msg)
        await exit_to_main_menu(update, context)
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при создании студента с мета-данными: {e}")
        await update.message.reply_text("❌ Произошла ошибка при создании студента.")
        return ConversationHandler.END


def record_initial_payment(student_id, paid_amount, mentor_id):
    """
    Записывает первоначальный платёж в `payments`.
    """
    try:
        if mentor_id is None:
            print(f"❌ DEBUG: Платёж не записан — не передан mentor_id для студента {student_id}")
            return
        if paid_amount > 0:
            new_payment = Payment(
                student_id=student_id,
                mentor_id=mentor_id,
                amount=paid_amount,
                payment_date=datetime.now().date(),
                comment="Первоначальный платёж при регистрации",
                status="подтвержден"
            )

            session.add(new_payment)
            session.commit()
            print(f"✅ DEBUG: Платёж записан в payments! {paid_amount} руб.")

    except Exception as e:
        session.rollback()
        print(f"❌ DEBUG: Ошибка при записи платежа: {e}")


async def request_salary_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрашивает у пользователя период расчёта зарплаты (от и до).
    """
    await update.message.reply_text(
        "📅 Введите период расчёта зарплаты в формате:\n"
        "ДД.ММ.ГГГГ - ДД.ММ.ГГГГ\n"
        "Пример: `01.03.2025 - 31.03.2025`"
    )
    return "WAIT_FOR_SALARY_DATES"


async def calculate_salary(update: Update, context):
    """
    Рассчитывает зарплату менторов за указанный период.
    """
    try:
        # Импортируем date в начале функции, чтобы избежать конфликтов
        from datetime import date
        from datetime import date as date_class  # Дополнительный импорт для избежания конфликтов
        # Импортируем новый калькулятор фуллстеков
        from commands.fullstack_salary_calculator import calculate_fullstack_salary
        date_range = update.message.text.strip()

        if " - " not in date_range:
            await update.message.reply_text(
                "❌ Неверный формат! Используйте формат: ДД.ММ.ГГГГ - ДД.ММ.ГГГГ\n"
                "Пример: 01.03.2025 - 31.03.2025"
            )
            return "WAIT_FOR_SALARY_DATES"

        start_date_str, end_date_str = map(str.strip, date_range.split("-"))
        
        try:
            start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
            end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Ошибка в формате даты: {e}\n"
                "Используйте формат ДД.ММ.ГГГГ\n"
                "Пример: 01.03.2025 - 31.03.2025"
            )
            return "WAIT_FOR_SALARY_DATES"

        if start_date > end_date:
            await update.message.reply_text(
                "❌ Дата начала не может быть позже даты окончания.\n"
                "Попробуйте снова:"
            )
            return "WAIT_FOR_SALARY_DATES"

        logger.info(f"📊 Запрашиваем всех менторов...")
        all_mentors = {mentor.id: mentor for mentor in session.query(Mentor).all()}

        if not all_mentors:
            logger.warning("⚠️ ВНИМАНИЕ: mentors не загружены! Проверь БД или session.commit()")
            await update.message.reply_text("❌ Ошибка: не удалось загрузить список менторов.")
            return ConversationHandler.END

        mentor_salaries = {mentor.id: 0 for mentor in all_mentors.values()}

        # Выбираем платежи за период
        logger.info(f"📊 Выполняем запрос к payments...")
        payments = session.query(
            Payment.mentor_id, func.sum(Payment.amount)
        ).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date
        ).group_by(Payment.mentor_id).all()

        logger.info(f"📊 Найдено платежей: {len(payments)}")

        if not payments:
            logger.warning("⚠️ Нет платежей за этот период!")
            payments = []
        # Подробный лог для каждого ментора
        detailed_logs = {}

        detailed_payments = session.query(Payment).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.status == "подтвержден",
            ~Payment.comment.ilike("%преми%")  # исключаем премии из основного расчёта
        ).order_by(Payment.payment_date.asc(), Payment.mentor_id.asc()).all()

        logger.info(f"📊 Найдено детальных платежей: {len(detailed_payments)}")

        # Дата начала новой системы расчета для ручных и авто кураторов
        from config import Config
        new_system_start_date = Config.NEW_PAYMENT_SYSTEM_START_DATE

        for payment in detailed_payments:
            mentor_id = payment.mentor_id
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if not student:
                continue

            if student.training_type == "Фуллстек":
                continue  # Fullstack оплачивается отдельно: фикс 5000 ментору 1, 30% ментору 3

            # ВАЖНО: Старая форма расчета (20% от платежей) применяется только для студентов,
            # пришедших ДО new_system_start_date. Даже если их платеж был после этой даты,
            # он все равно считается по старой системе (20% от суммы платежа).
            # Студенты, пришедшие ПОСЛЕ new_system_start_date, рассчитываются только по новой системе
            # (по темам/модулям) и НЕ получают 20% от платежей.
            if student.training_type in ["Ручное тестирование", "Автотестирование"]:
                if student.start_date and student.start_date >= new_system_start_date:
                    logger.debug(f"⏭️ Пропускаем студента {student.fio} (ID {student.id}): пришел {student.start_date} >= {new_system_start_date}, будет рассчитан по новой системе")
                    continue  # Пропускаем - эти студенты рассчитываются по новой системе (только по темам/модулям)
                else:
                    logger.debug(f"✅ Старая система: студент {student.fio} (ID {student.id}), пришел {student.start_date}, платеж {payment.payment_date}, сумма {payment.amount} руб.")

            if mentor_id == 1 and student.training_type == "Ручное тестирование":
                percent = 0.3
            elif mentor_id == 3 and student.training_type == "Автотестирование":
                percent = 0.3
            else:
                percent = 0.2

            # Для комиссионных платежей используем новую формулу расчета от базового дохода
            comment_lower = (payment.comment or "").lower()
            if "комисси" in comment_lower and student.commission:
                from data_base.operations import calculate_base_income_and_salary
                base_income, curator_salary = calculate_base_income_and_salary(
                    float(payment.amount),
                    student.commission,
                    percent
                )
                
                if curator_salary is not None:
                    payout = curator_salary
                    line = f"{student.fio} (ID {student.id}) {student.training_type}, {payment.payment_date}, {payment.amount} {payment.comment} руб. (базовый доход: {base_income} руб.), {int(percent * 100)}%, {round(payout, 2)} руб."
                else:
                    # Fallback на старую формулу, если не удалось рассчитать по новой
                    payout = float(payment.amount) * percent
                    line = f"{student.fio} (ID {student.id}) {student.training_type}, {payment.payment_date}, {payment.amount} {payment.comment} руб., {int(percent * 100)}%, {round(payout, 2)} руб."
            else:
                # Для остальных платежей используем старую формулу
                payout = float(payment.amount) * percent
                line = f"{student.fio} (ID {student.id}) {student.training_type}, {payment.payment_date}, {payment.amount} {payment.comment} руб., {int(percent * 100)}%, {round(payout, 2)} руб."

            if mentor_id not in mentor_salaries:
                mentor_salaries[mentor_id] = 0
            mentor_salaries[mentor_id] += payout

            if mentor_id not in detailed_logs:
                detailed_logs[mentor_id] = []
            detailed_logs[mentor_id].append(line)

        # 🔁 Бонусы 10% за чужих студентов (кроме Fullstack)
        # ВАЖНО: Бонусы директорам (ментор 1 и ментор 3) начисляются независимо от даты перехода
        # на новую систему. Они работают для всех студентов, независимо от того, когда студент пришел.
        for payment in detailed_payments:
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if not student:
                continue

            if student.training_type == "Фуллстек":
                continue  # ❌ Бонус не начисляется за Fullstack

            # НЕ проверяем дату для бонусов директорам - они начисляются всегда

            if 1 not in detailed_logs:
                detailed_logs[1] = []
            if 3 not in detailed_logs:
                detailed_logs[3] = []

            # 🔹 Ментор 1 получает 10% за всех чужих студентов (только ручное тестирование)
            if payment.mentor_id != 1 and student.training_type.lower().strip() == "ручное тестирование":
                bonus = float(payment.amount) * 0.1
                if 1 not in mentor_salaries:
                    mentor_salaries[1] = 0
                mentor_salaries[1] += bonus
                detailed_logs[1].append(
                    f"🔁 10% бонус ментору 1 за чужого ученика {student.fio} ({student.training_type}) | "
                    f"{payment.payment_date}, {payment.amount} руб. | +{round(bonus, 2)} руб."
                )

            # 🔹 Ментор 3 получает 10% только за чужих автотест-студентов
            if (
                    student.training_type == "Автотестирование"
                    and payment.mentor_id != 3
            ):
                bonus = float(payment.amount) * 0.1
                if 3 not in mentor_salaries:
                    mentor_salaries[3] = 0
                mentor_salaries[3] += bonus
                detailed_logs[3].append(
                    f"🔁 10% бонус ментору 3 за чужого автотест ученика {student.fio} | "
                    f"{payment.payment_date}, {payment.amount} руб. | +{round(bonus, 2)} руб."
                )

        # Фуллстек бонусы
        fullstack_students = session.query(Student).filter(
            Student.training_type == "Фуллстек",
            Student.total_cost >= 50000,
            Student.start_date >= start_date,
            Student.start_date <= end_date
        ).all()

        # if fullstack_students:
        #     bonus = len(fullstack_students) * 5000
        #     if 1 not in mentor_salaries:
        #         mentor_salaries[1] = 0
        #     mentor_salaries[1] += bonus
        #     for student in fullstack_students:
        #         log_line = f"Бонус за фуллстек: {student.fio} (ID {student.id}) | +5000 руб."
        #         if 1 not in detailed_logs:
        #             detailed_logs[1] = []
        #         detailed_logs[1].append(log_line)

        # 🎯 НОВЫЙ РАСЧЕТ ФУЛЛСТЕКОВ ПО ПРИНЯТЫМ ТЕМАМ
        logger.info("🎯 Запускаем новый расчет фуллстеков по принятым темам")
        try:
            fullstack_result = calculate_fullstack_salary(start_date, end_date)
            
            # Добавляем результаты директоров к основному расчету
            for director_id, salary in fullstack_result['director_salaries'].items():
                if director_id not in mentor_salaries:
                    mentor_salaries[director_id] = 0
                mentor_salaries[director_id] += salary
            
            # Добавляем результаты кураторов к основному расчету
            for curator_id, salary in fullstack_result['curator_salaries'].items():
                if curator_id not in mentor_salaries:
                    mentor_salaries[curator_id] = 0
                mentor_salaries[curator_id] += salary
            
            # Добавляем логи директоров
            for director_id, logs in fullstack_result['logs'].items():
                if director_id not in detailed_logs:
                    detailed_logs[director_id] = []
                detailed_logs[director_id].extend(logs)
            
            # Добавляем логи кураторов
            for curator_id, logs in fullstack_result['curator_logs'].items():
                if curator_id not in detailed_logs:
                    detailed_logs[curator_id] = []
                detailed_logs[curator_id].extend(logs)
            
            # Добавляем статистику
            logger.info(f"🎯 Фуллстек расчет завершен: обработано {fullstack_result['students_processed']} студентов, {fullstack_result['topics_processed']} тем")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при расчете фуллстеков: {e}")
            # Продолжаем расчет без фуллстеков

        # 🎯 РАСЧЕТ ЗП РУЧНЫХ И АВТО КУРАТОРОВ ПО ПРИНЯТЫМ ТЕМАМ/МОДУЛЯМ
        logger.info("🎯 Запускаем расчет ЗП ручных и авто кураторов по принятым темам/модулям")
        try:
            from commands.manual_auto_curator_salary_calculator import calculate_manual_auto_curator_salary
            manual_auto_result = calculate_manual_auto_curator_salary(start_date, end_date)
            
            # Добавляем результаты кураторов к основному расчету
            for curator_id, salary in manual_auto_result['curator_salaries'].items():
                if curator_id not in mentor_salaries:
                    mentor_salaries[curator_id] = 0
                mentor_salaries[curator_id] += salary
            
            # Добавляем логи кураторов
            for curator_id, logs in manual_auto_result['logs'].items():
                if curator_id not in detailed_logs:
                    detailed_logs[curator_id] = []
                detailed_logs[curator_id].extend(logs)
            
            # Добавляем статистику
            stats = manual_auto_result['students_processed']
            logger.info(f"🎯 Расчет ручных/авто кураторов завершен: обработано {stats['total']} студентов (ручных: {stats['manual']}, авто: {stats['auto']}), кураторов: {manual_auto_result['curators_count']}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при расчете ручных/авто кураторов: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Продолжаем расчет без ручных/авто кураторов

        # 🛡️ СТРАХОВКА ДЛЯ КУРАТОРОВ РУЧНОГО НАПРАВЛЕНИЯ
        from config import Config

        if Config.CURATOR_INSURANCE_ENABLED:
            logger.info("🛡️ Запускаем расчет страховки для кураторов ручного направления")

            # Импортируем модели
            from data_base.models import CuratorInsuranceBalance, ManualProgress

            # Получаем всех кураторов ручного направления (кроме директора ID=1)
            manual_curators = session.query(Mentor).filter(
                Mentor.direction == "Ручное тестирование",
                Mentor.id != 1  # Исключаем директора
            ).all()

            for curator in manual_curators:
                # Получаем активные страховки куратора за период
                active_insurance = session.query(CuratorInsuranceBalance).filter(
                    CuratorInsuranceBalance.curator_id == curator.id,
                    CuratorInsuranceBalance.is_active == True,
                    CuratorInsuranceBalance.created_at >= start_date,
                    CuratorInsuranceBalance.created_at <= end_date
                ).all()

                if active_insurance:
                    total_insurance = sum(float(ins.insurance_amount) for ins in active_insurance)

                    # Добавляем страховку к ЗП куратора
                    if curator.id not in mentor_salaries:
                        mentor_salaries[curator.id] = 0
                    mentor_salaries[curator.id] += total_insurance

                    # Добавляем логи страховки
                    if curator.id not in detailed_logs:
                        detailed_logs[curator.id] = []

                    detailed_logs[curator.id].append(f"🛡️ Страховка за {len(active_insurance)} студентов: +{round(total_insurance, 2)} руб.")

                    # Детальные логи по каждому студенту
                    for insurance in active_insurance:
                        student = session.query(Student).filter(Student.id == insurance.student_id).first()
                        if student:
                            detailed_logs[curator.id].append(
                                f"  📋 {student.fio} (ID {student.id}) - 5 модуль | +{float(insurance.insurance_amount)} руб."
                            )

                    logger.info(f"🛡️ Куратор {curator.full_name}: страховка {total_insurance} руб. за {len(active_insurance)} студентов")

                # 🔍 АВТОМАТИЧЕСКОЕ НАЧИСЛЕНИЕ СТРАХОВКИ НА ОСНОВЕ ДАТЫ 5 МОДУЛЯ ИЗ MANUAL_PROGRESS
                # Получаем студентов куратора с прогрессом по 5 модулю
                students_with_module_5 = session.query(Student, ManualProgress).join(
                    ManualProgress, Student.id == ManualProgress.student_id
                ).filter(
                    Student.mentor_id == curator.id,
                    Student.training_type == "Ручное тестирование",
                    ManualProgress.m5_start_date.isnot(None),
                    ManualProgress.m5_start_date >= start_date,
                    ManualProgress.m5_start_date <= end_date
                ).all()

                for student, progress in students_with_module_5:
                    module_5_date = progress.m5_start_date

                    # Проверяем, нет ли уже страховки за этого студента
                    existing_insurance = session.query(CuratorInsuranceBalance).filter(
                        CuratorInsuranceBalance.student_id == student.id,
                        CuratorInsuranceBalance.is_active == True
                    ).first()

                    if not existing_insurance:
                        # Создаем новую страховку
                        new_insurance = CuratorInsuranceBalance(
                            curator_id=curator.id,
                            student_id=student.id,
                            insurance_amount=5000.00,
                            created_at=module_5_date,
                            is_active=True
                        )
                        session.add(new_insurance)
                        session.commit()

                        # Добавляем к ЗП куратора
                        if curator.id not in mentor_salaries:
                            mentor_salaries[curator.id] = 0
                        mentor_salaries[curator.id] += 5000.00

                        # Добавляем логи
                        if curator.id not in detailed_logs:
                            detailed_logs[curator.id] = []
                        detailed_logs[curator.id].append(
                            f"🛡️ Авто-страховка за {student.fio} (ID {student.id}) - 5 модуль {module_5_date} | +5000 руб."
                        )

                        logger.info(f"🛡️ Авто-начислена страховка куратору {curator.full_name} за студента {student.fio}: 5000 руб.")
        else:
            logger.info("🛡️ Страховочные выплаты для кураторов отключены (CURATOR_INSURANCE_ENABLED = False)")

        # 🎁 Учет премий (выплаты с комментарием "Премия")
        premium_payments = session.query(Payment).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.status == "подтвержден",
            Payment.comment.ilike("%преми%")  # ловим "Премия", "премия", "ПРЕМИЯ" и т.д.
        ).order_by(Payment.payment_date.asc()).all()

        for payment in premium_payments:
            bonus_amount = float(payment.amount)
            mentor_id = payment.mentor_id
            if mentor_id not in mentor_salaries:
                mentor_salaries[mentor_id] = 0
            mentor_salaries[mentor_id] += bonus_amount

            detailed_logs.setdefault(mentor_id, []).append(
                f"🎁 Премия {payment.amount} руб. | {payment.payment_date} | +{bonus_amount} руб."
            )

        # 🛡️ ВЫЧЕТ СТРАХОВКИ ПРИ ПОЛУЧЕНИИ КОМИССИИ
        logger.info("🛡️ Проверяем вычет страховки при получении комиссии")

        # Импортируем модели для работы со страховкой
        from data_base.models import CuratorInsuranceBalance

        # Получаем все платежи с комментарием "Комиссия" за период
        commission_payments = session.query(Payment).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.status == "подтвержден",
            Payment.comment == "Комиссия"
        ).order_by(Payment.payment_date.asc()).all()
        
        for payment in commission_payments:
            student_id = payment.student_id
            if not student_id:
                continue
                
            # Получаем студента
            student = session.query(Student).filter(Student.id == student_id).first()
            if not student or student.training_type != "Ручное тестирование":
                continue
                
            # Получаем куратора студента
            curator_id = student.mentor_id
            if not curator_id:
                continue
                
            # Проверяем, есть ли активная страховка за этого студента
            active_insurance = session.query(CuratorInsuranceBalance).filter(
                CuratorInsuranceBalance.student_id == student_id,
                CuratorInsuranceBalance.curator_id == curator_id,
                CuratorInsuranceBalance.is_active == True
            ).first()
            
            if active_insurance:
                # Вычитаем страховку из ЗП куратора
                insurance_amount = float(active_insurance.insurance_amount)
                if curator_id not in mentor_salaries:
                    mentor_salaries[curator_id] = 0
                mentor_salaries[curator_id] -= insurance_amount
                
                # Деактивируем страховку
                active_insurance.is_active = False
                session.commit()
                
                # Добавляем логи
                if curator_id not in detailed_logs:
                    detailed_logs[curator_id] = []
                detailed_logs[curator_id].append(
                    f"🛡️ Вычет страховки за {student.fio} (ID {student_id}) - комиссия {payment.amount} руб. | -{insurance_amount} руб."
                )
                
                logger.info(f"🛡️ Вычтена страховка {insurance_amount} руб. у куратора {curator_id} за студента {student.fio} при получении комиссии")

        # 🎯 KPI ДЛЯ ВСЕХ КУРАТОРОВ (кроме директоров)
        from config import Config

        if Config.KPI_ENABLED:
            logger.info("🎯 Рассчитываем KPI для всех кураторов")

            # Импортируем модель для отслеживания KPI студентов
            from data_base.models import CuratorKpiStudents

            # Получаем всех кураторов (кроме директоров ID=1,3)
            all_curators_for_kpi = session.query(Mentor).filter(
                ~Mentor.id.in_([1, 3])  # Исключаем директоров
            ).all()

            for curator in all_curators_for_kpi:
                # Определяем типы обучения для куратора (свое направление + фуллстек)
                curator_training_types = []
                if curator.direction == "Ручное тестирование":
                    curator_training_types = ["Ручное тестирование", "Фуллстек"]
                elif curator.direction == "Автоматизация" or curator.direction == "Автотестирование":
                    curator_training_types = ["Автоматизация", "Автотестирование", "Фуллстек"]
                else:
                    # Для других направлений добавляем фуллстек
                    curator_training_types = [curator.direction, "Фуллстек"]

                # Получаем студентов куратора подходящих типов
                # Для автоматизации проверяем auto_mentor_id, для остальных - mentor_id
                if curator.direction in ["Автоматизация", "Автотестирование"]:
                    students = session.query(Student).filter(
                        Student.auto_mentor_id == curator.id,
                        Student.training_type.in_(curator_training_types)
                    ).all()
                else:
                    students = session.query(Student).filter(
                        Student.mentor_id == curator.id,
                        Student.training_type.in_(curator_training_types)
                    ).all()
                student_ids = [s.id for s in students]

                if not student_ids:
                    continue

                # Получаем первоначальные платежи студентов в периоде
                initial_payments = session.query(Payment).filter(
                    Payment.student_id.in_(student_ids),
                    Payment.payment_date >= start_date,
                    Payment.payment_date <= end_date,
                    Payment.status == "подтвержден",
                    Payment.comment == "Первоначальный платёж при регистрации"
                ).order_by(Payment.payment_date.asc()).all()

                # Считаем уникальных студентов, купивших в периоде
                unique_students = set(p.student_id for p in initial_payments)
                student_count = len(unique_students)

                # Определяем процент KPI через конфигурацию
                kpi_percent = Config.get_kpi_percent(student_count)

                if kpi_percent > 0:
                    # 📝 СОХРАНЯЕМ СТУДЕНТОВ, ПОПАВШИХ ПОД KPI
                    for student_id in unique_students:
                        # Проверяем, нет ли уже записи для этого студента в этом периоде
                        existing_kpi = session.query(CuratorKpiStudents).filter(
                            CuratorKpiStudents.curator_id == curator.id,
                            CuratorKpiStudents.student_id == student_id,
                            CuratorKpiStudents.period_start == start_date,
                            CuratorKpiStudents.period_end == end_date
                        ).first()

                        if not existing_kpi:
                            # Создаем новую запись
                            kpi_student = CuratorKpiStudents(
                                curator_id=curator.id,
                                student_id=student_id,
                                kpi_percent=kpi_percent,
                                period_start=start_date,
                                period_end=end_date,
                                created_at=datetime.now().date()
                            )
                            session.add(kpi_student)

                    # Суммируем первоначальные платежи
                    total_initial_payments = sum(float(p.amount) for p in initial_payments)

                    # Вычисляем разницу между KPI процентом и стандартным процентом
                    standard_percent = Config.STANDARD_PERCENT
                    kpi_bonus = total_initial_payments * (kpi_percent - standard_percent)

                    # Добавляем разницу к зарплате (так как 20% уже учтены в основном расчете)
                    if curator.id not in mentor_salaries:
                        mentor_salaries[curator.id] = 0
                    mentor_salaries[curator.id] += kpi_bonus

                    # Добавляем логи
                    if curator.id not in detailed_logs:
                        detailed_logs[curator.id] = []
                    detailed_logs[curator.id].append(
                        f"🎯 KPI ({curator.direction}): {student_count} студентов → {int(kpi_percent * 100)}% вместо {int(standard_percent * 100)}% (доплата +{int((kpi_percent - standard_percent) * 100)}%) | +{kpi_bonus:.2f} руб."
                    )

                    logger.info(f"🎯 KPI начислен куратору {curator.full_name} ({curator.direction}): {student_count} студентов, {kpi_percent * 100}% вместо {standard_percent * 100}%, доплата {kpi_bonus:.2f} руб.")

            # 🎯 ДОПОЛНИТЕЛЬНЫЙ KPI ДЛЯ ДОПЛАТ ОТ KPI-СТУДЕНТОВ
            logger.info("🎯 Рассчитываем дополнительный KPI для доплат от KPI-студентов")

            # Получаем всех студентов, которые попали под KPI в любом периоде
            kpi_students = session.query(CuratorKpiStudents).all()

            for kpi_record in kpi_students:
                curator_id = kpi_record.curator_id
                student_id = kpi_record.student_id
                kpi_percent = float(kpi_record.kpi_percent)

                # Получаем доплаты этого студента в текущем периоде расчета
                additional_payments = session.query(Payment).filter(
                    Payment.student_id == student_id,
                    Payment.payment_date >= start_date,
                    Payment.payment_date <= end_date,
                    Payment.status == "подтвержден",
                    Payment.comment == "Доплата за обучение"
                ).order_by(Payment.payment_date.asc()).all()

                if additional_payments:
                    # Суммируем доплаты
                    total_additional_payments = sum(float(p.amount) for p in additional_payments)

                    # Вычисляем разницу между KPI процентом и стандартным процентом
                    standard_percent = Config.STANDARD_PERCENT
                    additional_kpi_bonus = total_additional_payments * (kpi_percent - standard_percent)

                    # Добавляем к зарплате куратора
                    if curator_id not in mentor_salaries:
                        mentor_salaries[curator_id] = 0
                    mentor_salaries[curator_id] += additional_kpi_bonus

                    # Получаем информацию о студенте для логов
                    student = session.query(Student).filter(Student.id == student_id).first()
                    student_name = student.fio if student else f"ID {student_id}"

                    # Добавляем логи
                    if curator_id not in detailed_logs:
                        detailed_logs[curator_id] = []
                    detailed_logs[curator_id].append(
                        f"🎯 KPI доплаты от {student_name}: {int(kpi_percent * 100)}% вместо {int(standard_percent * 100)}% с {total_additional_payments:.2f} руб. | +{additional_kpi_bonus:.2f} руб."
                    )

                    logger.info(f"🎯 Дополнительный KPI начислен куратору {curator_id} за доплаты студента {student_name}: {additional_kpi_bonus:.2f} руб.")

            # Коммитим изменения в базу данных
            session.commit()
        else:
            logger.info("🎯 KPI система отключена (KPI_ENABLED = False)")

        # 💼 Расчет зарплат карьерных консультантов
        career_consultant_salaries = {}
        all_consultants = session.query(CareerConsultant).filter(CareerConsultant.is_active == True).all()
        
        for consultant in all_consultants:
            salary = 0
            total_commission = 0
            
            # Получаем всех студентов, закрепленных за консультантом
            students = session.query(Student).filter(Student.career_consultant_id == consultant.id).all()
            student_ids = [student.id for student in students]
            
            if not student_ids:
                continue
            
            # Получаем все подтвержденные платежи с комментарием "Комиссия" за период
            all_student_payments = session.query(Payment).filter(
                Payment.student_id.in_(student_ids),
                Payment.payment_date >= start_date,
                Payment.payment_date <= end_date,
                Payment.status == "подтвержден"
            ).order_by(Payment.payment_date.asc()).all()
            
            # Фильтруем по комиссии
            commission_payments = [p for p in all_student_payments if "комисси" in p.comment.lower()]
            
            # Рассчитываем комиссию: 20% если КК с ID=1 взял студента после 18.11.2025, иначе 10%
            COMMISSION_CHANGE_DATE = date_class(2025, 11, 18)
            
            total_commission = 0
            salary = 0
            for payment in commission_payments:
                student = session.query(Student).filter(Student.id == payment.student_id).first()
                if not student:
                    continue
                
                # Определяем процент КК
                if student and student.consultant_start_date:
                    # Если КК взял студента после 18.11.2025 и КК с ID=1, то 20%, иначе 10%
                    if student.consultant_start_date >= COMMISSION_CHANGE_DATE and student.career_consultant_id == 1:
                        consultant_percent = 0.2
                    else:
                        consultant_percent = 0.1
                else:
                    # Если дата не установлена, используем старую ставку 10%
                    consultant_percent = 0.1
                
                # Используем новую формулу расчета от базового дохода
                from data_base.operations import calculate_base_income_and_salary
                base_income, consultant_salary = calculate_base_income_and_salary(
                    float(payment.amount),
                    student.commission,
                    consultant_percent
                )
                
                if consultant_salary is not None:
                    salary += consultant_salary
                else:
                    # Fallback на старую формулу, если не удалось рассчитать по новой
                    salary += float(payment.amount) * consultant_percent
                
                total_commission += float(payment.amount)
            
            # 🛡️ СТРАХОВКА ДЛЯ КАРЬЕРНЫХ КОНСУЛЬТАНТОВ
            from data_base.models import ConsultantInsuranceBalance
            from config import Config
            
            if Config.CONSULTANT_INSURANCE_ENABLED:
                logger.info(f"🛡️ Запускаем расчет страховки для КК {consultant.full_name}")
                
                total_insurance = 0.0
                insurance_students_count = 0
                
                # СНАЧАЛА: Учитываем ВСЕ активные страховки КК (для студентов, взяттых ранее)
                all_active_insurance = session.query(ConsultantInsuranceBalance).filter(
                    ConsultantInsuranceBalance.consultant_id == consultant.id,
                    ConsultantInsuranceBalance.is_active == True
                ).all()
                
                logger.info(f"🛡️ Найдено активных страховок КК {consultant.full_name}: {len(all_active_insurance)}")
                
                processed_student_ids = set()
                
                # Учитываем все активные страховки
                for ins in all_active_insurance:
                    total_insurance += float(ins.insurance_amount)
                    insurance_students_count += 1
                    processed_student_ids.add(ins.student_id)
                    student = session.query(Student).filter(Student.id == ins.student_id).first()
                    if student:
                        created_date = ins.created_at.strftime("%d.%m.%Y") if ins.created_at else "неизвестно"
                        detailed_logs.setdefault(f"cc_{consultant.id}", []).append(
                            f"🛡️ Страховка за {student.fio} (ID {ins.student_id}) - активная (создана {created_date}) | +{float(ins.insurance_amount)} руб."
                        )
                        logger.info(f"🛡️ Учитывается активная страховка КК {consultant.full_name} за студента {student.fio}: {float(ins.insurance_amount)} руб.")
                
                # ЗАТЕМ: Проверяем студентов, взятых КК В ЭТОМ ПЕРИОДЕ (consultant_start_date в периоде)
                # Сначала получаем всех студентов КК для отладки
                all_students_consultant = session.query(Student).filter(
                    Student.career_consultant_id == consultant.id
                ).all()
                
                logger.info(f"🛡️ Всего студентов у КК {consultant.full_name} (ID {consultant.id}): {len(all_students_consultant)}")
                for stud in all_students_consultant:
                    logger.info(f"   📋 Студент {stud.fio} (ID {stud.id}): consultant_start_date = {stud.consultant_start_date}, career_consultant_id = {stud.career_consultant_id}")
                
                students_taken_in_period = session.query(Student).filter(
                    Student.career_consultant_id == consultant.id,
                    Student.consultant_start_date.isnot(None),
                    Student.consultant_start_date >= start_date,
                    Student.consultant_start_date <= end_date
                ).all()
                
                logger.info(f"🛡️ Период расчета: {start_date} - {end_date}")
                logger.info(f"🛡️ Найдено студентов, взятых КК в периоде: {len(students_taken_in_period)}")
                for stud in students_taken_in_period:
                    logger.info(f"   ✅ Студент {stud.fio} (ID {stud.id}): consultant_start_date = {stud.consultant_start_date}")
                
                # Создаем страховку для студентов, взятых в периоде (если её еще нет)
                for student in students_taken_in_period:
                    if student.id not in processed_student_ids:
                        # Проверяем, нет ли уже страховки (на всякий случай)
                        existing_insurance = session.query(ConsultantInsuranceBalance).filter(
                            ConsultantInsuranceBalance.student_id == student.id,
                            ConsultantInsuranceBalance.consultant_id == consultant.id,
                            ConsultantInsuranceBalance.is_active == True
                        ).first()
                        
                        if not existing_insurance:
                            # Создаем новую страховку
                            new_insurance = ConsultantInsuranceBalance(
                                consultant_id=consultant.id,
                                student_id=student.id,
                                insurance_amount=1000.00,
                                created_at=student.consultant_start_date,
                                is_active=True
                            )
                            session.add(new_insurance)
                            total_insurance += 1000.00
                            insurance_students_count += 1
                            
                            date_str = student.consultant_start_date.strftime("%d.%m.%Y") if student.consultant_start_date else "неизвестно"
                            detailed_logs.setdefault(f"cc_{consultant.id}", []).append(
                                f"🛡️ Страховка за {student.fio} (ID {student.id}) - взял в работу {date_str} | +1000 руб."
                            )
                            logger.info(f"🛡️ Начислена страховка КК {consultant.full_name} за студента {student.fio}: 1000 руб. (дата: {date_str})")
                        else:
                            # Страховка уже есть (не должно быть, но на всякий случай)
                            total_insurance += float(existing_insurance.insurance_amount)
                            insurance_students_count += 1
                            logger.info(f"🛡️ Страховка уже существует для студента {student.fio}, учитываем её")
                        
                        processed_student_ids.add(student.id)
                
                if total_insurance > 0:
                    salary += total_insurance
                    detailed_logs.setdefault(f"cc_{consultant.id}", []).append(
                        f"🛡️ Итого страховка за {insurance_students_count} студентов: +{round(total_insurance, 2)} руб."
                    )
                    logger.info(f"🛡️ КК {consultant.full_name}: страховка {total_insurance} руб. за {insurance_students_count} студентов")
                else:
                    logger.info(f"🛡️ КК {consultant.full_name}: страховка не начислена (нет активных страховок или студентов, взятых в периоде)")
                
                session.commit()
            
            # 🛡️ ВЫЧЕТ СТРАХОВКИ КК ПРИ ПОЛУЧЕНИИ КОМИССИИ (без детализации)
            # Вычитаем страховку за студентов, по которым поступила комиссия в этом периоде
            if Config.CONSULTANT_INSURANCE_ENABLED and commission_payments:
                logger.info(f"🛡️ Проверяем вычет страховки КК {consultant.full_name} при получении комиссии")
                
                for payment in commission_payments:
                    student_id = payment.student_id
                    if not student_id:
                        continue
                    
                    # Проверяем, есть ли активная страховка за этого студента
                    active_insurance = session.query(ConsultantInsuranceBalance).filter(
                        ConsultantInsuranceBalance.student_id == student_id,
                        ConsultantInsuranceBalance.consultant_id == consultant.id,
                        ConsultantInsuranceBalance.is_active == True
                    ).first()
                    
                    if active_insurance:
                        # Вычитаем страховку из ЗП КК
                        insurance_amount = float(active_insurance.insurance_amount)
                        salary -= insurance_amount
                        
                        # Деактивируем страховку
                        active_insurance.is_active = False
                        session.commit()
                        
                        # Логируем (но НЕ добавляем в детализацию, как требовал пользователь)
                        student = session.query(Student).filter(Student.id == student_id).first()
                        student_name = student.fio if student else f"ID {student_id}"
                        logger.info(f"🛡️ Вычтена страховка {insurance_amount} руб. у КК {consultant.full_name} за студента {student_name} при получении комиссии {payment.amount} руб. (НЕ показано в детализации)")
            
            career_consultant_salaries[consultant.id] = round(salary, 2)
            
            # Подробное логирование каждого платежа комиссии
            if commission_payments:
                detailed_logs.setdefault(f"cc_{consultant.id}", []).append(
                    f"💼 Карьерный консультант {consultant.full_name} | "
                    f"Комиссии: {total_commission} руб. | Итого: {salary} руб."
                )
                
                # Логируем каждый платеж комиссии отдельно
                for payment in commission_payments:
                    student = session.query(Student).filter(Student.id == payment.student_id).first()
                    if student:
                        detailed_logs[f"cc_{consultant.id}"].append(
                            f"  📄 Студент {student.fio} ({student.telegram}) | "
                            f"Платеж: {payment.amount} руб. | "
                            f"Дата: {payment.payment_date} | "
                            f"Комментарий: {payment.comment}"
                        )
            elif total_commission > 0:
                detailed_logs.setdefault(f"cc_{consultant.id}", []).append(
                    f"💼 Карьерный консультант {consultant.full_name} | "
                    f"Комиссии: {total_commission} руб. | Итого: {salary} руб."
                )

        # Вывод логов в файл
        for mentor_id, logs in detailed_logs.items():
            if isinstance(mentor_id, str) and mentor_id.startswith("cc_"):
                # Логи для карьерных консультантов
                consultant_id = int(mentor_id.split("_")[1])
                consultant = next((c for c in all_consultants if c.id == consultant_id), None)
                if consultant:
                    logger.info(f"\n📘 Карьерный консультант: {consultant.full_name} ({consultant.telegram})")
                    for log in logs:
                        logger.info(f"— {log}")
                    salary = career_consultant_salaries.get(consultant_id, 0)
                    salary_with_tax = round(salary * 1.06, 2)
                    logger.info(f"Итог: {salary} руб. (с НДФЛ {salary_with_tax})")
            else:
                # Логи для менторов
                mentor = all_mentors.get(mentor_id)
                if mentor:
                    logger.info(f"\n📘 Ментор: {mentor.full_name} ({mentor.telegram})")
                    for log in logs:
                        logger.info(f"— {log}")
                    salary = round(mentor_salaries[mentor_id], 2)
                    salary_with_tax = round(salary * 1.06, 2)
                    logger.info(f"Итог: {salary} руб. (с НДФЛ {salary_with_tax})")
                else:
                    logger.info(f"\n📘 Ментор ID {mentor_id}:")
                    for log in logs:
                        logger.info(f"— {log}")
                    salary = round(mentor_salaries.get(mentor_id, 0), 2)
                    salary_with_tax = round(salary * 1.06, 2)
                    logger.info(f"Итог: {salary} руб. (с НДФЛ {salary_with_tax})")

        # 💰 РАСЧЕТ ХОЛДИРОВАНИЯ ДЛЯ ФУЛЛСТЕК КУРАТОРОВ
        from config import Config
        from data_base.models import HeldAmount
        from data_base.operations import calculate_held_amount
        from datetime import date
        
        # Настраиваем отдельный логгер для холдирования
        held_logger = logging.getLogger('held_amounts')
        held_logger.setLevel(logging.INFO)
        # Проверяем, есть ли уже обработчик (избегаем дублирования)
        if not held_logger.handlers:
            held_file_handler = logging.FileHandler('held_amounts.log', encoding='utf-8')
            held_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            held_logger.addHandler(held_file_handler)
        
        total_held_amount = 0.0
        
        if Config.HELD_AMOUNTS_ENABLED:
            logger.info("💰 Запускаем расчет холдирования для фуллстек кураторов")
            held_logger.info(f"=" * 80)
            held_logger.info(f"💰 Расчет холдирования за период {start_date_str} - {end_date_str}")
            held_logger.info(f"=" * 80)
            
            # Дата начала действия системы холдирования
            from datetime import date as date_class
            held_amounts_start_date = date_class(2025, 9, 1)
            
            # 🔄 ПРОВЕРЯЕМ И ОБНОВЛЯЕМ СТАТУСЫ ЗАПИСЕЙ В held_amounts
            # Если у студента training_status = "Не учится" или "Отчислен", 
            # помечаем все его записи как released
            held_logger.info("🔄 Проверяем статусы студентов в held_amounts...")
            all_held_records = session.query(HeldAmount).all()
            students_to_deactivate = set()
            
            for held_record in all_held_records:
                student = session.query(Student).filter(Student.id == held_record.student_id).first()
                if student and student.training_status in ["Не учится", "Отчислен"]:
                    students_to_deactivate.add(student.id)
                    if held_record.status == "active":
                        held_record.status = "released"
                        held_logger.info(f"🔴 Помечено как released: студент ID {student.id} ({student.fio}), training_status={student.training_status}")
            
            if students_to_deactivate:
                session.commit()
                held_logger.info(f"✅ Обновлено записей для {len(students_to_deactivate)} студентов со статусом 'Не учится' или 'Отчислен'")
            
            # Получаем активных студентов фуллстек, которые:
            # 1. Начали обучение с 1 сентября 2025
            # 2. Не отчислены (training_status != "Отчислен")
            # 3. Статус обучения не равен "Не учится" (training_status != "Не учится")
            # ВАЖНО: Создаем/обновляем холдирование для ВСЕХ студентов >= 01.09.2025,
            # независимо от периода расчета зарплаты, чтобы записи всегда были актуальными
            fullstack_students = session.query(Student).filter(
                Student.training_type == "Фуллстек",
                Student.start_date >= held_amounts_start_date,
                Student.training_status != "Отчислен",
                Student.training_status != "Не учится"
            ).all()
            
            # Дополнительная фильтрация в Python для надежности
            fullstack_students = [
                s for s in fullstack_students 
                if s.training_status not in ["Отчислен", "Не учится"]
            ]
            
            logger.info(f"💰 Найдено активных студентов фуллстек (>= 01.09.2025): {len(fullstack_students)}")
            held_logger.info(f"💰 Найдено активных студентов фуллстек для обработки: {len(fullstack_students)}")
            
            if len(fullstack_students) == 0:
                held_logger.info("⚠️ Студенты не найдены. Проверьте фильтры:")
                held_logger.info(f"   - training_type == 'Фуллстек'")
                held_logger.info(f"   - training_status != 'Отчислен'")
                held_logger.info(f"   - start_date >= {held_amounts_start_date}")
            
            for student in fullstack_students:
                try:
                    # 🔍 РУЧНОЕ НАПРАВЛЕНИЕ: проверяем, кто назначен куратором
                    if student.mentor_id == Config.DIRECTOR_MANUAL_ID:
                        # Директор ручного направления - холдим 30% от total_cost
                        manual_result = calculate_held_amount(student.id, "manual", Config.DIRECTOR_MANUAL_ID, is_director=True)
                        direction_for_db = "manual"  # Используем обычный direction для хранения
                        is_director_manual = True
                    elif student.mentor_id:
                        # Обычный куратор ручного направления - холдим 20% от стоимости курса
                        manual_result = calculate_held_amount(student.id, "manual", student.mentor_id, is_director=False)
                        direction_for_db = "manual"
                        is_director_manual = False
                    else:
                        # Куратор не назначен - создаем холдирование для куратора (20% от стоимости)
                        manual_result = calculate_held_amount(student.id, "manual", None, is_director=False)
                        direction_for_db = "manual"
                        is_director_manual = False
                    
                    if manual_result:
                        held_amount = manual_result['held_amount']
                        potential_amount = manual_result['potential_amount']
                        paid_amount = manual_result['paid_amount']
                        modules_completed = manual_result['modules_completed']
                        total_modules = manual_result['total_modules']
                        mentor_id_for_db = student.mentor_id if student.mentor_id else Config.DIRECTOR_MANUAL_ID if is_director_manual else None
                        
                        # Создаем или обновляем запись холдирования для ручного направления
                        held_record = session.query(HeldAmount).filter(
                            HeldAmount.student_id == student.id,
                            HeldAmount.direction == "manual"
                        ).first()
                        
                        if held_record:
                            # Обновляем существующую запись
                            held_record.mentor_id = mentor_id_for_db
                            held_record.held_amount = held_amount
                            held_record.potential_amount = potential_amount
                            held_record.paid_amount = paid_amount
                            held_record.modules_completed = modules_completed
                            held_record.total_modules = total_modules
                            held_record.updated_at = date.today()
                            if held_record.status == "released":
                                held_record.status = "active"
                            
                            role_text = "ДИРЕКТОР" if is_director_manual else "КУРАТОР"
                            held_logger.info(f"📝 Обновлено холдирование РУЧНОЕ ({role_text}): Студент {student.fio} (ID {student.id}) | "
                                            f"ID: {mentor_id_for_db or 'не назначен'} | "
                                            f"Модулей: {modules_completed}/{total_modules} | "
                                            f"Потенциально: {potential_amount} руб. | "
                                            f"Выплачено: {paid_amount} руб. | "
                                            f"Холдировано: {held_amount} руб.")
                        else:
                            # Создаем новую запись
                            held_record = HeldAmount(
                                student_id=student.id,
                                mentor_id=mentor_id_for_db,
                                direction="manual",
                                held_amount=held_amount,
                                potential_amount=potential_amount,
                                paid_amount=paid_amount,
                                modules_completed=modules_completed,
                                total_modules=total_modules,
                                status="active",
                                created_at=date.today(),
                                updated_at=date.today()
                            )
                            session.add(held_record)
                            
                            role_text = "ДИРЕКТОР" if is_director_manual else "КУРАТОР"
                            held_logger.info(f"➕ Создано холдирование РУЧНОЕ ({role_text}): Студент {student.fio} (ID {student.id}) | "
                                            f"ID: {mentor_id_for_db or 'не назначен'} | "
                                            f"Модулей: {modules_completed}/{total_modules} | "
                                            f"Потенциально: {potential_amount} руб. | "
                                            f"Выплачено: {paid_amount} руб. | "
                                            f"Холдировано: {held_amount} руб.")
                        
                        total_held_amount += held_amount
                    
                    # 🔍 АВТО НАПРАВЛЕНИЕ: проверяем, кто назначен куратором
                    if student.auto_mentor_id == Config.DIRECTOR_AUTO_ID:
                        # Директор авто направления - холдим 30% от total_cost
                        auto_result = calculate_held_amount(student.id, "auto", Config.DIRECTOR_AUTO_ID, is_director=True)
                        direction_for_db = "auto"
                        is_director_auto = True
                    elif student.auto_mentor_id:
                        # Обычный куратор авто направления - холдим 20% от стоимости курса
                        auto_result = calculate_held_amount(student.id, "auto", student.auto_mentor_id, is_director=False)
                        direction_for_db = "auto"
                        is_director_auto = False
                    else:
                        # Куратор не назначен - создаем холдирование для куратора (20% от стоимости)
                        auto_result = calculate_held_amount(student.id, "auto", None, is_director=False)
                        direction_for_db = "auto"
                        is_director_auto = False
                    
                    if auto_result:
                        held_amount = auto_result['held_amount']
                        potential_amount = auto_result['potential_amount']
                        paid_amount = auto_result['paid_amount']
                        modules_completed = auto_result['modules_completed']
                        total_modules = auto_result['total_modules']
                        mentor_id_for_db = student.auto_mentor_id if student.auto_mentor_id else Config.DIRECTOR_AUTO_ID if is_director_auto else None
                        
                        # Создаем или обновляем запись холдирования для авто направления
                        held_record = session.query(HeldAmount).filter(
                            HeldAmount.student_id == student.id,
                            HeldAmount.direction == "auto"
                        ).first()
                        
                        if held_record:
                            # Обновляем существующую запись
                            held_record.mentor_id = mentor_id_for_db
                            held_record.held_amount = held_amount
                            held_record.potential_amount = potential_amount
                            held_record.paid_amount = paid_amount
                            held_record.modules_completed = modules_completed
                            held_record.total_modules = total_modules
                            held_record.updated_at = date.today()
                            if held_record.status == "released":
                                held_record.status = "active"
                            
                            role_text = "ДИРЕКТОР" if is_director_auto else "КУРАТОР"
                            held_logger.info(f"📝 Обновлено холдирование АВТО ({role_text}): Студент {student.fio} (ID {student.id}) | "
                                            f"ID: {mentor_id_for_db or 'не назначен'} | "
                                            f"Модулей: {modules_completed}/{total_modules} | "
                                            f"Потенциально: {potential_amount} руб. | "
                                            f"Выплачено: {paid_amount} руб. | "
                                            f"Холдировано: {held_amount} руб.")
                        else:
                            # Создаем новую запись
                            held_record = HeldAmount(
                                student_id=student.id,
                                mentor_id=mentor_id_for_db,
                                direction="auto",
                                held_amount=held_amount,
                                potential_amount=potential_amount,
                                paid_amount=paid_amount,
                                modules_completed=modules_completed,
                                total_modules=total_modules,
                                status="active",
                                created_at=date.today(),
                                updated_at=date.today()
                            )
                            session.add(held_record)
                            
                            role_text = "ДИРЕКТОР" if is_director_auto else "КУРАТОР"
                            held_logger.info(f"➕ Создано холдирование АВТО ({role_text}): Студент {student.fio} (ID {student.id}) | "
                                            f"ID: {mentor_id_for_db or 'не назначен'} | "
                                            f"Модулей: {modules_completed}/{total_modules} | "
                                            f"Потенциально: {potential_amount} руб. | "
                                            f"Выплачено: {paid_amount} руб. | "
                                            f"Холдировано: {held_amount} руб.")
                        
                        total_held_amount += held_amount
                    
                    session.commit()
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при расчете холдирования для студента {student.id}: {e}")
                    held_logger.error(f"❌ Ошибка при расчете холдирования для студента {student.fio} (ID {student.id}): {e}")
                    session.rollback()
            
            held_logger.info(f"💰 ИТОГО холдирование за период: {round(total_held_amount, 2)} руб.")
            held_logger.info(f"=" * 80)
            logger.info(f"💰 Расчет холдирования завершен. Итого холдировано: {round(total_held_amount, 2)} руб.")
        else:
            logger.info("💰 Система холдирования отключена (HELD_AMOUNTS_ENABLED = False)")

        # Вычисляем общий бюджет на зарплаты (включая карьерных консультантов)
        total_mentor_salaries = sum(mentor_salaries.values())
        total_career_consultant_salaries = sum(career_consultant_salaries.values())
        total_salaries = total_mentor_salaries + total_career_consultant_salaries
        
        # Сохраняем для последующего использования
        context.user_data['total_salaries'] = total_salaries
        context.user_data['total_mentor_salaries'] = total_mentor_salaries
        context.user_data['total_career_consultant_salaries'] = total_career_consultant_salaries
        
        # Формируем отчет
        salary_report = f"📊 Расчёт зарплат за {start_date_str} - {end_date_str}\n\n"
        
        # Отчет по менторам
        salary_report += "👨‍🏫 Зарплата менторов:\n"
        for mentor in all_mentors.values():
            salary = round(mentor_salaries.get(mentor.id, 0), 2)
            if salary > 0:
                # Расчет с учетом НДФЛ 6%
                salary_with_tax = round(salary * 1.06, 2)
                salary_report += f"💰 {mentor.full_name} ({mentor.telegram}): {salary} руб. (с НДФЛ {salary_with_tax})\n"
            else:
                salary_report += f"❌ {mentor.full_name} ({mentor.telegram}): У ментора нет платежей за этот период\n"
        
        # Итого менторов с НДФЛ
        total_mentor_salaries_with_tax = round(total_mentor_salaries * 1.06, 2)
        salary_report += f"📈 Итого менторов: {int(total_mentor_salaries):,} руб. (с НДФЛ {int(total_mentor_salaries_with_tax):,})\n\n"
        
        # Отчет по карьерным консультантам
        if career_consultant_salaries:
            salary_report += "💼 Зарплата карьерных консультантов:\n"
            for consultant in all_consultants:
                salary = career_consultant_salaries.get(consultant.id, 0)
                if salary > 0:
                    # Расчет с учетом НДФЛ 6%
                    salary_with_tax = round(salary * 1.06, 2)
                    salary_report += f"💰 {consultant.full_name} ({consultant.telegram}): {salary} руб. (с НДФЛ {salary_with_tax})\n"
                else:
                    salary_report += f"❌ {consultant.full_name} ({consultant.telegram}): У консультанта нет комиссий за этот период\n"
            
            # Итого КК с НДФЛ
            total_career_consultant_salaries_with_tax = round(total_career_consultant_salaries * 1.06, 2)
            salary_report += f"📈 Итого КК: {int(total_career_consultant_salaries):,} руб. (с НДФЛ {int(total_career_consultant_salaries_with_tax):,})\n\n"
        
        # Общий итог с НДФЛ
        total_salaries_with_tax = round(total_salaries * 1.06, 2)
        salary_report += f"💸 Общий итог: {int(total_salaries):,} руб. (с НДФЛ {int(total_salaries_with_tax):,})\n"

        # Добавляем кнопку для подробной информации
        salary_report += "\n🔍 Хотите увидеть подробное формирование зарплаты по каждому сотруднику?"
        
        # Сохраняем данные для подробного отчета
        context.user_data['detailed_salary_data'] = {
            'mentor_salaries': mentor_salaries,
            'career_consultant_salaries': career_consultant_salaries,
            'detailed_logs': detailed_logs,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'all_mentors': {m.id: m for m in all_mentors.values()},
            'all_consultants': {c.id: c for c in all_consultants}
        }

        await update.message.reply_text(
            salary_report,
            reply_markup=ReplyKeyboardMarkup(
                [["Да, показать подробности"], ["Нет, достаточно"]],
                one_time_keyboard=True
            )
        )
        return "WAIT_FOR_DETAILED_SALARY"
    except ValueError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return "WAIT_FOR_SALARY_DATES"
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при расчете зарплаты: {e}")
        logger.error(f"❌ Тип ошибки: {type(e).__name__}")
        logger.error(f"❌ Детали ошибки: {str(e)}")
        await update.message.reply_text(f"❌ Произошла ошибка при расчете зарплаты: {str(e)}")
        return "WAIT_FOR_SALARY_DATES"


async def select_mentor_by_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает список менторов в зависимости от направления.
    """
    from data_base.models import Mentor

    course_type = context.user_data["course_type"]

    # Для Fullstack: сначала ручное направление
    if course_type == "Фуллстек" and "mentor_id" not in context.user_data:
        mentor_direction = "Ручное тестирование"
        mentors = session.query(Mentor).filter(Mentor.direction == mentor_direction).all()
        if not mentors:
            await update.message.reply_text("❌ Нет менторов для выбранного направления.")
            return COURSE_TYPE
        context.user_data["mentors_list"] = {m.full_name: m.id for m in mentors}
        await update.message.reply_text(
            "Сначала выберите ментора для ручного направления (Ручное тестирование):",
            reply_markup=ReplyKeyboardMarkup(
                [[name] for name in context.user_data["mentors_list"].keys()] + [["Пропустить"]],
                one_time_keyboard=True
            )
        )
        return SELECT_MENTOR
    # Для Fullstack: после выбора ручного — авто
    elif course_type == "Фуллстек" and "mentor_id" in context.user_data:
        mentor_direction = "Автотестирование"
        mentors = session.query(Mentor).filter(Mentor.direction == mentor_direction).all()
        if not mentors:
            await update.message.reply_text("❌ Нет менторов для автотестирования.")
            return COURSE_TYPE
        context.user_data["mentors_list"] = {m.full_name: m.id for m in mentors}
        await update.message.reply_text(
            "Теперь выберите ментора для авто-направления (Автотестирование):",
            reply_markup=ReplyKeyboardMarkup(
                [[name] for name in context.user_data["mentors_list"].keys()] + [["Пропустить"]],
                one_time_keyboard=True
            )
        )
        return SELECT_MENTOR
    # Обычная логика для остальных направлений
    if course_type == "Ручное тестирование":
        mentor_direction = "Ручное тестирование"
    else:
        mentor_direction = "Автотестирование"

    mentors = session.query(Mentor).filter(Mentor.direction == mentor_direction).all()

    if not mentors:
        await update.message.reply_text("❌ Нет менторов для выбранного направления.")
        return COURSE_TYPE

    context.user_data["mentors_list"] = {m.full_name: m.id for m in mentors}

    # Для авто и ручного — стандартное сообщение
    if course_type == "Автотестирование":
        msg = "Выберите ментора по направлению: Автотестирование"
    else:
        msg = "Выберите ментора по направлению: Ручное тестирование"
    await update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup(
            [[name] for name in context.user_data["mentors_list"].keys()] + [["Пропустить"]],
            one_time_keyboard=True
        )
    )
    return SELECT_MENTOR


async def handle_mentor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = update.message.text.strip()
    mentors_list = context.user_data.get("mentors_list", {})

    if selected not in mentors_list and selected != "Пропустить":
        await update.message.reply_text("❌ Пожалуйста, выберите одного из предложенных или нажмите 'Пропустить'.")
        return SELECT_MENTOR

    course_type = context.user_data.get("course_type")
    # Для Fullstack: сначала ручной, потом авто
    if course_type == "Фуллстек":
        # Если еще не выбран ручной ментор — сейчас выбираем его
        if "mentor_id" not in context.user_data:
            context.user_data["mentor_id"] = None if selected == "Пропустить" else mentors_list[selected]
            # Теперь показать выбор авто-ментора
            from data_base.models import Mentor
            mentors = session.query(Mentor).filter(Mentor.direction == "Автотестирование").all()
            if not mentors:
                await update.message.reply_text("❌ Нет менторов для автотестирования.")
                return COURSE_TYPE
            context.user_data["mentors_list"] = {m.full_name: m.id for m in mentors}
            await update.message.reply_text(
                "Теперь выберите ментора для авто-направления (Автотестирование):",
                reply_markup=ReplyKeyboardMarkup(
                    [[name] for name in context.user_data["mentors_list"].keys()] + [["Пропустить"]],
                    one_time_keyboard=True
                )
            )
            return SELECT_MENTOR
        else:
            # Сейчас выбираем авто-ментора
            context.user_data["auto_mentor_id"] = None if selected == "Пропустить" else mentors_list[selected]
            await update.message.reply_text("Оба ментора выбраны. Введите общую стоимость обучения:")
            return TOTAL_PAYMENT
    elif course_type == "Автотестирование":
        context.user_data["auto_mentor_id"] = None if selected == "Пропустить" else mentors_list[selected]
        context.user_data["mentor_id"] = None
        await update.message.reply_text("Введите общую стоимость обучения:")
        return TOTAL_PAYMENT
    else:  # Ручное тестирование
        context.user_data["mentor_id"] = None if selected == "Пропустить" else mentors_list[selected]
        context.user_data["auto_mentor_id"] = None
        await update.message.reply_text("Введите общую стоимость обучения:")
        return TOTAL_PAYMENT


async def handle_detailed_salary_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает запрос на подробную информацию о зарплатах.
    """
    user_choice = update.message.text.strip()
    
    if user_choice == "Нет, достаточно":
        await update.message.reply_text(
            "Хорошо! Возвращаемся в главное меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Главное меню"]], one_time_keyboard=True)
        )
        return await exit_to_main_menu(update, context)
    
    elif user_choice == "Да, показать подробности":
        detailed_data = context.user_data.get('detailed_salary_data')
        if not detailed_data:
            await update.message.reply_text("❌ Ошибка: данные о зарплатах не найдены.")
            return await exit_to_main_menu(update, context)
        
        await update.message.reply_text("📋 Формирую подробные отчеты по каждому сотруднику...")
        
        # Отправляем подробные отчеты по менторам
        mentor_salaries = detailed_data['mentor_salaries']
        detailed_logs = detailed_data['detailed_logs']
        all_mentors = detailed_data['all_mentors']
        
        logger.info(f"Начинаю отправку отчетов по {len(mentor_salaries)} менторам")
        
        for mentor_id, salary in mentor_salaries.items():
            if salary > 0 and mentor_id in all_mentors:
                try:
                    mentor = all_mentors[mentor_id]
                    logger.info(f"Формирую отчет для ментора {mentor.full_name}")
                    
                    detailed_report = await generate_mentor_detailed_report(
                        mentor, salary, detailed_logs.get(mentor_id, []), 
                        detailed_data['start_date'], detailed_data['end_date']
                    )
                    
                    logger.info(f"Отчет для {mentor.full_name} сформирован, отправляю...")
                    
                    # Разбиваем длинное сообщение на части
                    report_parts = split_long_message(detailed_report)
                    if len(report_parts) > 1:
                        logger.info(f"Отчет для {mentor.full_name} разбит на {len(report_parts)} частей")
                        for i, part in enumerate(report_parts, 1):
                            part_header = f"📄 Часть {i} из {len(report_parts)}:\n\n"
                            await update.message.reply_text(part_header + part)
                            await asyncio.sleep(0.3)  # Небольшая задержка между частями
                    else:
                        await update.message.reply_text(detailed_report)
                    
                    logger.info(f"Отчет для {mentor.full_name} отправлен")
                    
                    # Небольшая задержка между отправкой отчетов
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Ошибка при формировании отчета для ментора {mentor_id}: {e}")
                    await update.message.reply_text(f"❌ Ошибка при формировании отчета для ментора {mentor_id}: {e}")
        
        # Отправляем подробные отчеты по карьерным консультантам
        career_consultant_salaries = detailed_data['career_consultant_salaries']
        all_consultants = detailed_data['all_consultants']
        
        logger.info(f"Начинаю отправку отчетов по {len(career_consultant_salaries)} карьерным консультантам")
        
        for consultant_id, salary in career_consultant_salaries.items():
            if salary > 0 and consultant_id in all_consultants:
                try:
                    consultant = all_consultants[consultant_id]
                    logger.info(f"Формирую отчет для КК {consultant.full_name}")
                    
                    detailed_report = await generate_consultant_detailed_report(
                        consultant, salary, detailed_data['start_date'], detailed_data['end_date']
                    )
                    
                    logger.info(f"Отчет для КК {consultant.full_name} сформирован, отправляю...")
                    
                    # Разбиваем длинное сообщение на части
                    report_parts = split_long_message(detailed_report)
                    if len(report_parts) > 1:
                        logger.info(f"Отчет для КК {consultant.full_name} разбит на {len(report_parts)} частей")
                        for i, part in enumerate(report_parts, 1):
                            part_header = f"📄 Часть {i} из {len(report_parts)}:\n\n"
                            await update.message.reply_text(part_header + part)
                            await asyncio.sleep(0.3)  # Небольшая задержка между частями
                    else:
                        await update.message.reply_text(detailed_report)
                    
                    logger.info(f"Отчет для КК {consultant.full_name} отправлен")
                    
                    # Небольшая задержка между отправкой отчетов
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Ошибка при формировании отчета для КК {consultant_id}: {e}")
                    await update.message.reply_text(f"❌ Ошибка при формировании отчета для КК {consultant_id}: {e}")
        
        await update.message.reply_text(
            "✅ Подробные отчеты по всем сотрудникам отправлены!",
            reply_markup=ReplyKeyboardMarkup([["🔙 Главное меню"]], one_time_keyboard=True)
        )
        return await exit_to_main_menu(update, context)
    
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите один из вариантов: 'Да, показать подробности' или 'Нет, достаточно'",
            reply_markup=ReplyKeyboardMarkup(
                [["Да, показать подробности"], ["Нет, достаточно"]],
                one_time_keyboard=True
            )
        )
        return "WAIT_FOR_DETAILED_SALARY"


async def generate_mentor_detailed_report(mentor, salary, logs, start_date, end_date):
    """
    Генерирует подробный отчет по зарплате ментора.
    """
    # Импортируем date в начале функции, чтобы избежать конфликтов
    from datetime import date
    
    logger.info(f"Начинаю формирование отчета для ментора {mentor.full_name}")
    
    try:
        salary_with_tax = round(salary * 1.06, 2)
        
        report = f"👨‍🏫 Подробный отчет по зарплате ментора\n"
        report += f"👤 {mentor.full_name} ({mentor.telegram})\n"
        report += f"📅 Период: {start_date} - {end_date}\n"
        report += f"💰 Итоговая зарплата: {salary} руб. (с НДФЛ {salary_with_tax})\n\n"
        
        logger.info(f"Базовая информация для {mentor.full_name} добавлена")
        
        # Подсчёт предоплаты и постоплаты за период
        try:
            period_start = datetime.strptime(start_date, "%d.%m.%Y").date()
            period_end = datetime.strptime(end_date, "%d.%m.%Y").date()
        except Exception:
            period_start = None
            period_end = None

        # Брутто суммы по видам платежей (для справки)
        total_initial = 0.0
        total_additional = 0.0
        total_commission = 0.0

        # Брутто базы, которые реально попали в расчёт (исключая Fullstack)
        counted_initial = 0.0
        counted_additional = 0.0
        counted_commission = 0.0

        # Начисленные суммы (нетто) с учётом правил процентов, как в основном расчёте
        from_students_payout = 0.0  # первоначальный + доплата
        from_offers_payout = 0.0    # комиссия

        # Дата начала новой системы расчета для ручных и авто кураторов
        from config import Config
        new_system_start_date = Config.NEW_PAYMENT_SYSTEM_START_DATE

        if period_start and period_end:
            payments_q = session.query(Payment, Student).join(Student, Student.id == Payment.student_id).filter(
                Payment.payment_date >= period_start,
                Payment.payment_date <= period_end,
                Payment.status == "подтвержден",
                Payment.mentor_id == mentor.id
            ).all()

            for payment, student in payments_q:
                comment_lower = (payment.comment or "").lower()
                amount = float(payment.amount)

                # Брутто агрегаты (все платежи)
                if "первонач" in comment_lower:
                    total_initial += amount
                elif "доплат" in comment_lower:
                    total_additional += amount
                elif "комисси" in comment_lower:
                    total_commission += amount

                # Исключаем Fullstack из расчётной базы
                if student.training_type == "Фуллстек":
                    continue

                # Старая форма расчета: только для студентов, пришедших ДО 01.10.2025
                if student.training_type in ["Ручное тестирование", "Автотестирование"]:
                    if student.start_date and student.start_date >= new_system_start_date:
                        continue  # Пропускаем - эти студенты рассчитываются по новой системе

                # Платёж попадает в расчёт — накапливаем расчётную базу
                if "первонач" in comment_lower:
                    counted_initial += amount
                elif "доплат" in comment_lower:
                    counted_additional += amount
                elif "комисси" in comment_lower:
                    counted_commission += amount

                # Применяем те же правила процентов, что и в calculate_salary
                if mentor.id == 1 and student.training_type == "Ручное тестирование":
                    percent = 0.3
                elif mentor.id == 3 and student.training_type == "Автотестирование":
                    percent = 0.3
                else:
                    percent = 0.2

                # Для комиссионных платежей используем новую формулу расчета от базового дохода
                if "комисси" in comment_lower and student.commission:
                    from data_base.operations import calculate_base_income_and_salary
                    base_income, curator_salary = calculate_base_income_and_salary(
                        amount,
                        student.commission,
                        percent
                    )
                    
                    if curator_salary is not None:
                        payout = curator_salary
                    else:
                        # Fallback на старую формулу, если не удалось рассчитать по новой
                        payout = amount * percent
                else:
                    # Для остальных платежей используем старую формулу
                    payout = amount * percent
                
                if "первонач" in comment_lower or "доплат" in comment_lower:
                    from_students_payout += payout
                elif "комисси" in comment_lower:
                    from_offers_payout += payout

        total_prepayment = round(total_initial + total_additional, 2)
        total_postpayment = round(total_commission, 2)

        # Отображаемые базы — только то, что реально попало в расчёт (без Fullstack)
        counted_prepayment = round(counted_initial + counted_additional, 2)
        counted_postpayment = round(counted_commission, 2)
        tax_amount = round(salary * 0.06, 2)

        # Составляющие зарплаты по правилам процентов (20/30%)
        from_students = round(from_students_payout, 2)  # начислено с учеников
        from_offers = round(from_offers_payout, 2)      # начислено с оффера

        # Добавляем сумму за созвоны по фуллстекам (из логов расчета фуллстека)
        # Эти выплаты должны попадать в компонент "с учеников"
        fullstack_calls_amount = 0.0
        if logs:
            import re
            for log in logs:
                # Кураторские логи фуллстека
                if "фуллстек" in log.lower() and "+" in log:
                    m = re.search(r"\+(\d+\.?\d*) руб\.", log)
                    if m:
                        fullstack_calls_amount += float(m.group(1))
                # Логи директоров направления (тоже считаем как созвоны)
                elif ("директор" in log.lower() or "принял" in log.lower()) and "+" in log:
                    m = re.search(r"\+(\d+\.?\d*) руб\.", log)
                    if m:
                        fullstack_calls_amount += float(m.group(1))

        if fullstack_calls_amount > 0:
            from_students = round(from_students + fullstack_calls_amount, 2)
        
        # Вычисляем KPI и другие бонусы из логов
        import re
        kpi_amount = 0.0
        insurance_amount = 0.0
        premium_amount = 0.0
        
        if logs:
            for log in logs:
                if "🎯 KPI" in log:
                    # Извлекаем сумму KPI из лога
                    kpi_match = re.search(r'\+(\d+\.?\d*) руб\.$', log)
                    if kpi_match:
                        kpi_amount += float(kpi_match.group(1))
                elif "🛡️" in log and "+" in log:
                    # Страховка (начисления)
                    insurance_match = re.search(r'\+(\d+\.?\d*) руб\.$', log)
                    if insurance_match:
                        insurance_amount += float(insurance_match.group(1))
                elif "🎁 Премия" in log:
                    # Премии
                    premium_match = re.search(r'\+(\d+\.?\d*) руб\.$', log)
                    if premium_match:
                        premium_amount += float(premium_match.group(1))
        
        # Добавляем разбивку зарплаты после итоговой зарплаты
        report += f"📊 Составляющие зарплаты:\n"
        report += f"| с учеников {from_students} руб. |\n"
        report += f"| с оффера {from_offers} руб. |\n"
        if kpi_amount > 0:
            report += f"| KPI бонус {kpi_amount} руб. |\n"
        if insurance_amount > 0:
            report += f"| страховка {insurance_amount} руб. |\n"
        if premium_amount > 0:
            report += f"| премии {premium_amount} руб. |\n"
        report += f"| налог {tax_amount} руб. |\n\n"

        # Поясняем начисления без фиксации процента в тексте (так как 20/30% зависят от роли/курса)
        report += f"Предоплата (первоначальный + доплата): {from_students} руб. (от {counted_prepayment} руб.)\n"
        report += f"Постоплата (комиссия): {from_offers} руб. (от {counted_postpayment} руб.)\n"
        report += f"Налог 6% к уплате: {tax_amount} руб.\n\n"

        if logs:
            report += "📋 Детализация выплат:\n"
            for log in logs:
                # Очищаем лог от лишних символов для лучшей читаемости
                clean_log = log.replace("— ", "").replace("💼 ", "").replace("🔁 ", "")
                report += f"• {clean_log}\n"
        else:
            report += "📋 Детализация выплат не найдена.\n"
        
        logger.info(f"Отчет для {mentor.full_name} полностью сформирован")
        return report
        
    except Exception as e:
        logger.error(f"Ошибка при формировании отчета для ментора {mentor.full_name}: {e}")
        return f"❌ Ошибка при формировании отчета: {e}"


async def generate_consultant_detailed_report(consultant, salary, start_date, end_date):
    """
    Генерирует подробный отчет по зарплате карьерного консультанта.
    """
    # Импортируем date в начале функции, чтобы избежать конфликтов
    from datetime import date
    
    logger.info(f"Начинаю формирование отчета для КК {consultant.full_name}")
    
    salary_with_tax = round(salary * 1.06, 2)
    
    report = f"💼 Подробный отчет по зарплате карьерного консультанта\n"
    report += f"👤 {consultant.full_name} ({consultant.telegram})\n"
    report += f"📅 Период: {start_date} - {end_date}\n"
    report += f"💰 Итоговая зарплата: {salary} руб. (с НДФЛ {salary_with_tax})\n\n"
    
    logger.info(f"Базовая информация для КК {consultant.full_name} добавлена")
    
    # Получаем детали по комиссиям
    from data_base.models import Payment, Student
    
    commission_payments = session.query(Payment).filter(
        Payment.student_id.in_(
            session.query(Student.id).filter(Student.career_consultant_id == consultant.id)
        ),
        Payment.payment_date >= datetime.strptime(start_date, "%d.%m.%Y").date(),
        Payment.payment_date <= datetime.strptime(end_date, "%d.%m.%Y").date(),
        Payment.status == "подтвержден",
        Payment.comment.ilike("%комисси%")
    ).order_by(Payment.payment_date.asc()).all()
    
    # Подсчёт предоплаты и постоплаты за период (для справки)
    try:
        period_start = datetime.strptime(start_date, "%d.%m.%Y").date()
        period_end = datetime.strptime(end_date, "%d.%m.%Y").date()
    except Exception:
        period_start = None
        period_end = None

    total_initial = 0.0
    total_additional = 0.0
    total_commission = 0.0

    commission_details_fallback = []

    if period_start and period_end:
        student_ids_subq = session.query(Student.id).filter(Student.career_consultant_id == consultant.id)
        payments_q = session.query(Payment).filter(
            Payment.student_id.in_(student_ids_subq),
            Payment.payment_date >= period_start,
            Payment.payment_date <= period_end,
            Payment.status == "подтвержден",
        ).order_by(Payment.payment_date.asc()).all()

        for payment in payments_q:
            comment_lower = (payment.comment or "").lower()
            amount = float(payment.amount)
            if "первонач" in comment_lower:
                total_initial += amount
            elif "доплат" in comment_lower:
                total_additional += amount
            elif "комисси" in comment_lower:
                total_commission += amount
                commission_details_fallback.append(payment)

    total_prepayment = round(total_initial + total_additional, 2)
    total_postpayment = round(total_commission, 2)
    tax_amount = round(salary * 0.06, 2)

    # Для КК учитываем только комиссию: 20% если КК взял студента после 18.11.2025, иначе 10%
    # Предоплата не выплачивается
    COMMISSION_CHANGE_DATE = date(2025, 11, 18)
    
    prepayment_percent = 0.0
    prepayment_amount = round(total_prepayment * prepayment_percent, 2)
    
    # Пересчитываем postpayment_amount с учетом даты закрепления для каждого платежа
    postpayment_amount = 0
    for payment in commission_details_fallback:
        student = session.query(Student).filter(Student.id == payment.student_id).first()
        if not student:
            continue
        
        # Определяем процент КК
        if student and student.consultant_start_date:
            # Если КК взял студента после 18.11.2025 и КК с ID=1, то 20%, иначе 10%
            if student.consultant_start_date >= COMMISSION_CHANGE_DATE and student.career_consultant_id == 1:
                consultant_percent = 0.2
            else:
                consultant_percent = 0.1
        else:
            consultant_percent = 0.1
        
        # Используем новую формулу расчета от базового дохода
        from data_base.operations import calculate_base_income_and_salary
        base_income, consultant_salary = calculate_base_income_and_salary(
            float(payment.amount),
            student.commission,
            consultant_percent
        )
        
        if consultant_salary is not None:
            postpayment_amount += consultant_salary
        else:
            # Fallback на старую формулу, если не удалось рассчитать по новой
            postpayment_amount += float(payment.amount) * consultant_percent
    postpayment_amount = round(postpayment_amount, 2)

    # 🛡️ Получаем информацию о страховке
    total_insurance = 0.0
    insurance_items = []
    from data_base.models import ConsultantInsuranceBalance
    from config import Config
    
    if Config.CONSULTANT_INSURANCE_ENABLED and period_start and period_end:
        # Получаем активные страховки, созданные в периоде (включая те, которые могли быть деактивированы позже)
        all_insurance_in_period = session.query(ConsultantInsuranceBalance).filter(
            ConsultantInsuranceBalance.consultant_id == consultant.id,
            ConsultantInsuranceBalance.created_at >= period_start,
            ConsultantInsuranceBalance.created_at <= period_end
        ).all()
        
        for ins in all_insurance_in_period:
            student = session.query(Student).filter(Student.id == ins.student_id).first()
            if student:
                insurance_amount = float(ins.insurance_amount)
                total_insurance += insurance_amount
                insurance_status = "активна" if ins.is_active else "погашена при получении комиссии"
                insurance_items.append({
                    'student': student,
                    'amount': insurance_amount,
                    'created_at': ins.created_at,
                    'status': insurance_status
                })

    report += f"Предоплата (первоначальный + доплата): {prepayment_amount} руб. ({int(prepayment_percent*100)}% от {total_prepayment} руб.)\n"
    # Вычисляем средний процент для отображения
    avg_percent = (postpayment_amount / total_postpayment * 100) if total_postpayment > 0 else 0
    report += f"Постоплата (комиссия): {postpayment_amount} руб. (средний {avg_percent:.1f}% от {total_postpayment} руб.)\n"
    if total_insurance > 0:
        report += f"🛡️ Страховка за студентов: {round(total_insurance, 2)} руб.\n"
    report += f"Налог 6% к уплате: {tax_amount} руб.\n\n"

    # Если прямой запрос по комиссиям ничего не вернул, используем собранные комиссии из общего списка
    commission_items = commission_payments if commission_payments else commission_details_fallback

    if commission_items:
        report += "📋 Детализация комиссий:\n"
        for payment in commission_items:
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if student:
                # Определяем процент комиссии в зависимости от даты закрепления и ID КК
                if student.consultant_start_date and student.consultant_start_date >= COMMISSION_CHANGE_DATE and student.career_consultant_id == 1:
                    commission_percent = 0.2
                    percent_text = "20%"
                else:
                    commission_percent = 0.1
                    percent_text = "10%"
                
                commission_amount = round(float(payment.amount) * commission_percent, 2)
                report += f"• {student.fio} ({student.telegram}): {payment.amount} руб. → {commission_amount} руб. ({percent_text})\n"
                report += f"  📅 {payment.payment_date} | 💬 {payment.comment}\n"
    else:
        report += "📋 Детализация комиссий не найдена.\n"
    
    # 🛡️ Детализация страховки
    if insurance_items:
        report += "\n🛡️ Детализация страховки (1000 руб. за каждого студента, взятого в периоде):\n"
        for item in insurance_items:
            student = item['student']
            report += f"• {student.fio} ({student.telegram}): +{item['amount']} руб.\n"
            report += f"  📅 Дата взятия в работу: {item['created_at']} | Статус: {item['status']}\n"
    
    return report
