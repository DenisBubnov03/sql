import logging
import asyncio
import logging
# Импорты
from datetime import datetime, date

from sqlalchemy import func
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from classes.salary import SalaryManager
from commands.start_commands import exit_to_main_menu
from commands.states import FIO, TELEGRAM, START_DATE, COURSE_TYPE, TOTAL_PAYMENT, PAID_AMOUNT, \
    SELECT_MENTOR, IS_REFERRAL, REFERRER_TELEGRAM, STUDENT_SOURCE, PAYMENT_CHANNEL
from data_base.db import session
from data_base.models import Payment, Student, CareerConsultant, SalaryKK
from data_base.models import Payout, Salary, Mentor
from data_base.models import StudentMeta
from data_base.operations import get_student_by_fio_or_telegram
from student_management.student_management import add_student

logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

import re

import re


def create_mentor_report(name, logs):
    """
    Универсальная функция: формирует детальный отчет с группировкой по категориям.
    """
    # 1. Инициализация категорий
    sums = {
        "accepted": 0.0,  # Темы
        "commission": 0.0,  # Комиссии, Доплаты, Legacy
        "bonus": 0.0,  # Бонусы
        "prize": 0.0,  # Премии
        "other": 0.0  # Неопознанное
    }
    total_base = 0.0

    # 2. Парсинг и распределение сумм
    for log in logs:
        # Ищем число после символа '|'
        match = re.search(r'\|\s*([\d\s,.]+)', log)
        amount = 0.0
        if match:
            clean_str = match.group(1).replace(' ', '').replace(',', '')
            try:
                amount = float(clean_str)
            except ValueError:
                amount = 0.0

        # Суммируем в общий котел (чтобы итого был точным)
        total_base += amount

        # Распределяем по категориям для сводки
        txt = log.lower()
        if "принял" in txt:
            sums["accepted"] += amount
        elif any(word in txt for word in ["комиссия", "доплата", "legacy"]):
            sums["commission"] += amount
        elif "бонус" in txt:
            sums["bonus"] += amount
        elif "премия" in txt:
            sums["prize"] += amount
        else:
            sums["other"] += amount

    # 3. Формирование текста отчета
    text = f"👤 <b>{name}</b>\n\n"

    # Внутренняя функция для красивых строк сводки
    def format_summary_line(title, val):
        if val > 0:
            return f"   ▫️ {title}: <b>{val:,.2f}р.</b> (с нал. {val * 1.06:,.2f}р.)\n"
        return ""

    # Сводка (кратко)
    text += "📊 <b>Сводка по категориям:</b>\n"
    text += format_summary_line("Принятые темы", sums["accepted"])
    text += format_summary_line("Доплаты и Legacy", sums["commission"])
    text += format_summary_line("Бонусы", sums["bonus"])
    text += format_summary_line("Премии", sums["prize"])
    text += format_summary_line("Прочее", sums["other"])

    # Итоги
    tax = total_base * 0.06
    text += "─" * 20 + "\n"
    text += f"💰 <b>ИТОГО К ВЫПЛАТЕ: {total_base:,.2f}р.</b>\n"
    text += f"🏦 <b>С НДФЛ (6%): {total_base + tax:,.2f}р.</b>\n\n"

    # Детализация (сами логи)
    text += "📜 <b>Детализация операций:</b>\n"
    if logs:
        for log in logs:
            text += f" {log}\n"
    else:
        text += "   (Нет записей)\n"

    return text


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
                [['Ручное тестирование'], ['Автотестирование'], ['Фуллстек']],
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
                    [["Да"], ["Нет"]],
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
                [["ОМ"], ["Ютуб"], ["Инстаграм"], ["Авито"], ["Сайт"], ["Через знакомых"], ["Пусто"]],
                one_time_keyboard=True
            )
        )
        return STUDENT_SOURCE
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите 'Да' или 'Нет'.",
            reply_markup=ReplyKeyboardMarkup(
                [["Да"], ["Нет"]],
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
            [["ОМ"], ["Ютуб"], ["Инстаграм"], ["Авито"], ["Сайт"], ["Через знакомых"], ["Пусто"]],
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
                [["ОМ"], ["Ютуб"], ["Инстаграм"], ["Авито"], ["Сайт"], ["Через знакомых"], ["Пусто"]],
                one_time_keyboard=True
            )
        )
        return STUDENT_SOURCE
    
    context.user_data["source"] = source

    # Спрашиваем канал внесения платежа (для вычета комиссии из ЗП директоров)
    await update.message.reply_text(
        "Через что вносит платеж? (влияет на расчёт ЗП директоров)",
        reply_markup=ReplyKeyboardMarkup(
            [["Лава"], ["ИП"], ["Карточка"], ["Крипта"]],
            one_time_keyboard=True
        )
    )
    return PAYMENT_CHANNEL


async def add_student_payment_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка выбора канала оплаты: Лава (12%), ИП (8%), Карточка/Крипта (0%).
    """
    raw = update.message.text.strip()
    channel_map = {"Лава": "lava", "ИП": "ip", "Карточка": "card", "Крипта": "crypto"}
    if raw not in channel_map:
        await update.message.reply_text(
            "Выберите один из вариантов: Лава, ИП, Карточка или Крипта.",
            reply_markup=ReplyKeyboardMarkup(
                [["Лава"], ["ИП"], ["Карточка"], ["Крипта"]],
                one_time_keyboard=True
            )
        )
        return PAYMENT_CHANNEL
    context.user_data["payment_channel"] = channel_map[raw]
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
            payment_channel=context.user_data.get("payment_channel"),  # lava, ip, card, crypto
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
        paid_amount = context.user_data.get("paid_amount", 0)
        if paid_amount > 0:
            record_initial_payment(student_id, paid_amount, payment_mentor_id)
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

def record_initial_payment(student_id, paid_amount, mentor_id=None):
        """
        Записывает платёж ВСЕГДА (если сумма > 0).
        Бонус директору начисляется только при наличии условий.
        """
        try:
            if paid_amount <= 0:
                print(f"⚠️ Пропуск: Платёж для студента {student_id} имеет нулевую сумму.")
                return

            # 1. Создаем платеж. mentor_id теперь может быть None!
            # В таблице payments поле mentor_id должно допускать NULL.
            new_payment = Payment(
                student_id=student_id,
                mentor_id=mentor_id,
                amount=paid_amount,
                payment_date=datetime.now().date(),
                comment="Первоначальный платёж при регистрации",
                status="подтвержден"
            )

            session.add(new_payment)

            # Используем flush, чтобы получить ID платежа, но НЕ закрывать транзакцию
            session.flush()
            print(f"✅ Платёж зафиксирован (ID: {new_payment.id}, Сумма: {paid_amount})")

            # 2. Пробуем начислить бонус (Логика не мешает платежу)
            try:
                student = session.query(Student).get(student_id)
                if student:
                    # ВАЖНО: Мы передаем payment_id, чтобы связать начисление с чеком
                    salary_manager = SalaryManager()
                    salary_manager.init_director_bonus_commission(
                        session=session,
                        student=student,
                        payment_id=new_payment.id
                    )
                    print(f"✅ Бонусная часть обработана для {student.telegram}")
                else:
                    print(f"⚠️ ПРЕДУПРЕЖДЕНИЕ: Студент {student_id} не найден в базе для начисления бонуса.")

            except Exception as bonus_error:
                # Ошибка в бонусах НЕ должна отменять сам платеж
                print(f"❌ Ошибка при расчете бонуса (платеж сохранен): {bonus_error}")

            # Финальный и единственный коммит
            session.commit()

        except Exception as e:
            session.rollback()
            print(f"❌ Критическая ошибка в record_initial_payment: {e}")


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

async def calculate_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Рассчитывает зарплату и сразу выводит список сотрудников с суммами.
    """
    try:
        from datetime import datetime, time
        # 1. Парсинг дат
        date_range = update.message.text.strip()
        if " - " not in date_range:
            await update.message.reply_text("❌ Неверный формат! Используйте: ДД.ММ.ГГГГ - ДД.ММ.ГГГГ")
            return "WAIT_FOR_SALARY_DATES"

        start_date_str, end_date_str = map(str.strip, date_range.split("-"))
        try:
            start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
            end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
        except ValueError:
            await update.message.reply_text("❌ Ошибка в дате.")
            return "WAIT_FOR_SALARY_DATES"

        # Фильтр по времени (весь день до 23:59:59)
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        kk_report_data = {}  # {kk_id: amount_to_pay}
        context.user_data['salary_period'] = {'start': start_date, 'end': end_date}
        context.user_data['salary_period_str'] = f"{start_date_str} - {end_date_str}"

        # 2. Сбор данных из Salary
        salary_records = session.query(Salary).filter(
            Salary.date_calculated >= start_dt,
            Salary.date_calculated <= end_dt
        ).all()

        report_data = {}
        # Загружаем карту менторов {ID: Имя}
        mentors_query = session.query(Mentor).all()
        mentors_map = {m.id: m.full_name for m in mentors_query}
        context.user_data['mentors_map'] = mentors_map

        # Агрегация данных
        for record in salary_records:
            m_id = record.mentor_id
            if not m_id: continue

            amount = float(record.calculated_amount)

            if m_id not in report_data:
                report_data[m_id] = {'total': 0.0, 'paid': 0.0, 'to_pay': 0.0, 'logs': []}

            report_data[m_id]['total'] += amount

            if record.is_paid:
                report_data[m_id]['paid'] += amount
            else:
                report_data[m_id]['to_pay'] += amount

            # Логи
            status_icon = "✅" if record.is_paid else "⏳"
            date_log = record.date_calculated.strftime("%d.%m") if record.date_calculated else "??"
            report_data[m_id]['logs'].append(f"{status_icon} {date_log}: {record.comment} | {amount:,.2f}р.")

        context.user_data['salary_report_data'] = report_data

        # 3. Формирование текста отчета
        text = f"📊 <b>ОТЧЕТ ПО ЗАРПЛАТЕ ({start_date_str} - {end_date_str})</b>\n"
        text += "Использована таблица транзакций (Salary)\n\n"
        text += "👨‍🏫 <b>Менторы:</b>\n"

        total_to_pay_global = 0.0
        found_any = False

        for m_id, data in report_data.items():
            to_pay = data['to_pay']
            paid = data['paid']

            if to_pay == 0 and paid == 0: continue

            found_any = True
            name = mentors_map.get(m_id, f"ID {m_id}")

            with_tax = to_pay * 1.06
            total_to_pay_global += to_pay

            line = f"• {name}: <b>{to_pay:,.2f} руб.</b> (с налогом: {with_tax:,.2f})"
            if paid > 0:
                line += f" | <i>выплачено: {paid:,.2f} руб.</i>"
            text += line + "\n"

        if not found_any:
            text += "Нет начислений за этот период.\n"

        # --- БЛОК КАРЬЕРНЫХ КОНСУЛЬТАНТОВ ---
        text += "\n💼 <b>Карьерные Консультанты:</b>\n"
        kk_total_to_pay = 0.0

        # 1. Используем start_dt и end_dt для TIMESTAMP
        active_kks = session.query(CareerConsultant).join(SalaryKK).filter(
            SalaryKK.date_calculated >= start_dt,  # Было start_date
            SalaryKK.date_calculated <= end_dt,  # Было end_date
            SalaryKK.is_paid == False  # Добавляем, если ищем только долги
        ).distinct().all()

        if not active_kks:
            text += "<i>Начислений по КК не найдено</i>\n"
        else:
            for kk in active_kks:
                # 2. Здесь тоже используем dt с временем
                kk_items = session.query(SalaryKK).filter(
                    SalaryKK.kk_id == kk.id,
                    SalaryKK.date_calculated >= start_dt,
                    SalaryKK.date_calculated <= end_dt,
                    SalaryKK.is_paid == False
                ).all()

                kk_sum = sum(float(item.calculated_amount) for item in kk_items)
                kk_report_data[kk.id] = kk_sum

                kk_total_to_pay += kk_sum
                text += f"👤 <b>{kk.full_name}</b>\n"

                for item in kk_items:
                    student = session.query(Student).filter(Student.id == item.student_id).first()
                    student_name = student.fio if student else f"ID:{item.student_id}"

                    text += (f"  ▫️ {student_name}: <b>{float(item.calculated_amount):,.2f} руб. (с налогом: {float(item.calculated_amount)*1.06:,.2f})</b> "
                             f"(Ост. лимит: {float(item.remaining_limit):,.2f})\n")

                # text += f"  💰 <b>Итого по консультанту: {kk_sum:,.2f} руб.</b>\n\n"

        # 5. Итоговая сумма по всему отчету
        total_to_pay_global += kk_total_to_pay  # Добавляем КК в общий итог

        text += "---"
        text += f"\n💵 <b>ОБЩИЙ ИТОГ К ВЫПЛАТЕ: {total_to_pay_global:.2f} руб.</b>"
        text += "Выберите действие:"

        keyboard = [
            ["💸 Выплатить ЗП"],
            ["📜 Показать историю операций"],
            ["🔙 Возврат в меню"]
        ]

        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True),
            parse_mode="HTML"
        )
        context.user_data['kk_report_data'] = kk_report_data
        return "SALARY_MAIN_MENU"

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Ошибка: {e}")
        return ConversationHandler.END


# === ШАГ 2: ОБРАБОТЧИК ГЛАВНОГО МЕНЮ ===

async def handle_salary_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text

    if choice == "🔙 Возврат в меню":
        return await exit_to_main_menu(update, context)

    elif choice == "📜 Показать историю операций":
        await update.message.reply_text(
            "По кому показать историю?",
            reply_markup=ReplyKeyboardMarkup([["👥 По всем сразу"], ["👤 Выбрать сотрудника"], ["🔙 Возврат в меню"]],
                                             one_time_keyboard=True)
        )
        return "SALARY_DETAIL_SELECT"

    elif choice == "💸 Выплатить ЗП":
        report_data = context.user_data.get('salary_report_data', {})
        total_to_pay = sum(d['to_pay'] for d in report_data.values())

        if total_to_pay <= 0:
            await update.message.reply_text("✅ Все начисления уже выплачены! Платить нечего.",
                                            reply_markup=ReplyKeyboardMarkup([["🔙 Возврат в меню"]],
                                                                             one_time_keyboard=True))
            return "SALARY_MAIN_MENU"

        await update.message.reply_text(
            f"К выплате доступно: {total_to_pay:,.2f} руб.\nКому производим выплату?",
            reply_markup=ReplyKeyboardMarkup([["👥 Выплатить ВСЕМ"], ["👤 Выбрать сотрудника"], ["🔙 Возврат в меню"]],
                                             one_time_keyboard=True)
        )
        return "SALARY_PAY_SELECT"


# === ШАГ 3: ЛОГИКА ИСТОРИИ ОПЕРАЦИЙ (ДЕТАЛИЗАЦИЯ) ===

async def handle_detail_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    report_data = context.user_data.get('salary_report_data', {})
    mentors_map = context.user_data.get('mentors_map', {})

    # --- 1. КНОПКА НАЗАД ---
    if choice == "🔙 Возврат в меню":
        period_str = context.user_data.get('salary_period_str', '')
        await update.message.reply_text(
            f"Меню отчета ({period_str}).",
            reply_markup=ReplyKeyboardMarkup(
                [["💸 Выплатить ЗП"], ["📜 Показать историю операций"], ["🔙 Возврат в меню"]], one_time_keyboard=True)
        )
        return "SALARY_MAIN_MENU"

    # --- 2. ПО ВСЕМ СРАЗУ ---
    elif choice == "👥 По всем сразу":
        await update.message.reply_text("📋 <b>История операций по всем:</b>", parse_mode="HTML")

        for m_id, data in report_data.items():
            name = mentors_map.get(m_id, f"ID {m_id}")
            # Вызываем нашу функцию
            text = create_mentor_report(name, data['logs'])

            for part in split_long_message(text):
                await update.message.reply_text(part, parse_mode="HTML")

        await update.message.reply_text("Действия:", reply_markup=ReplyKeyboardMarkup([["🔙 Возврат в меню"]],
                                                                                      one_time_keyboard=True))
        return "SALARY_MAIN_MENU"

    # --- 3. ПОКАЗАТЬ СПИСОК (Кнопки) ---
    elif choice == "👤 Выбрать сотрудника":
        buttons = []
        button_map = {}

        # 1. Сначала добавляем Менторов из report_data
        for m_id, data in report_data.items():
            name = mentors_map.get(m_id, f"ID {m_id}")
            btn_text = f"👨‍🏫 {name}"
            buttons.append([btn_text])
            button_map[btn_text] = ("mentor", m_id)  # Запоминаем, что это ментор

        # 2. 🔥 ДОБАВЛЯЕМ КК ИЗ kk_report_data
        kk_report = context.user_data.get('kk_report_data', {})
        for kk_id in kk_report.keys():
            kk_obj = session.query(CareerConsultant).filter_by(id=kk_id).first()
            if kk_obj:
                btn_text = f"💼 {kk_obj.full_name}"
                buttons.append([btn_text])
                button_map[btn_text] = ("kk", kk_id)  # Запоминаем, что это КК

        context.user_data['salary_detail_button_map'] = button_map
        buttons.append(["🔙 Возврат в меню"])

        await update.message.reply_text(
            "Выберите сотрудника для просмотра истории:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )
        return "SALARY_DETAIL_SELECT"

        # --- 4. КОНКРЕТНЫЙ СОТРУДНИК (Нажатие на имя) ---
    else:
        button_map = context.user_data.get('salary_detail_button_map', {})
        res = button_map.get(choice)

        if res:
            res_type, res_id = res  # Распаковываем тип (mentor/kk) и ID

            if res_type == "mentor":
                # Старая логика для менторов
                data = report_data.get(res_id)
                if data:
                    name = mentors_map.get(res_id, f"ID {res_id}")
                    text = create_mentor_report(name, data['logs'])
                    for part in split_long_message(text):
                        await update.message.reply_text(part, parse_mode="HTML")

            elif res_type == "kk":

             # Логика для Карьерного Консультанта

                kk_obj = session.query(CareerConsultant).filter_by(id=res_id).first()

                name = kk_obj.full_name if kk_obj else "КК"

                # Собираем историю начислений КК (используем func.date для точности)

                kk_items = session.query(SalaryKK).filter(

                    SalaryKK.kk_id == res_id,

                    func.date(SalaryKK.date_calculated) >= context.user_data['salary_period']['start'],

                    func.date(SalaryKK.date_calculated) <= context.user_data['salary_period']['end']

                ).order_by(SalaryKK.date_calculated.desc()).all()

                text = f"💼 <b>История операций КК: {name}</b>\n\n"

                if not kk_items:

                    text += "<i>Записей за этот период не найдено.</i>"

                else:

                    for item in kk_items:
                        # Получаем данные студента

                        student = session.query(Student).filter(Student.id == item.student_id).first()

                        st_name = student.fio if student else "Студент"

                        # 🔥 ПОЛУЧАЕМ ДАННЫЕ ОРИГИНАЛЬНОГО ПЛАТЕЖА

                        payment = session.query(Payment).filter(Payment.id == item.payment_id).first()

                        p_amount = float(payment.amount) if payment else 0.0

                        status = "✅" if item.is_paid else "⏳"

                        date_str = item.date_calculated.strftime('%d.%m')

                        # Формируем красивую строку

                        text += (f"{status} <b>{date_str}</b> | {st_name}\n"
                
                                 f"   └ Платёж: {p_amount:,.2f}р. | Бонус: <b>+{float(item.calculated_amount):,.2f}р.</b>\n")

                for part in split_long_message(text):
                    await update.message.reply_text(part, parse_mode="HTML")

            await update.message.reply_text("Выберите другого или вернитесь:",
                                            reply_markup=ReplyKeyboardMarkup([["🔙 Возврат в меню"]],
                                                                             one_time_keyboard=True))
            return "SALARY_DETAIL_SELECT"
# === ШАГ 4: ЛОГИКА ВЫБОРА ОПЛАТЫ ===

async def handle_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    report_data = context.user_data.get('salary_report_data', {})
    mentors_map = context.user_data.get('mentors_map', {})

    if choice == "🔙 Возврат в меню":
        period_str = context.user_data.get('salary_period_str', '')
        await update.message.reply_text(f"Меню отчета ({period_str}).", reply_markup=ReplyKeyboardMarkup(
            [["💸 Выплатить ЗП"], ["📜 Показать историю операций"], ["🔙 Возврат в меню"]], one_time_keyboard=True))
        return "SALARY_MAIN_MENU"

    target_ids = []
    target_kk_ids = []  # Добавляем список для КК
    total_amount = 0.0
    confirm_msg = ""

    # СЦЕНАРИЙ: ПЛАТИМ ВСЕМ
    if choice == "👥 Выплатить ВСЕМ":
        for m_id, data in report_data.items():
            if data['to_pay'] > 0:
                target_ids.append(m_id)
                total_amount += data['to_pay']
        kk_report = context.user_data.get('kk_report_data', {})
        for k_id, amount in kk_report.items():
            target_kk_ids.append(k_id)
            total_amount += amount
        confirm_msg = f"❗ <b>ВНИМАНИЕ</b> ❗\nВыплата для <b>{len(target_ids)} сотрудников</b>.\nОбщая сумма: <b>{total_amount:,.2f} руб.</b>\n\nПодтверждаете?"

    # СЦЕНАРИЙ: ОПЛАТА КОНКРЕТНОМУ (из детализации)
    elif choice == "💸 Выплатить этому сотруднику":
        m_id = context.user_data.get('selected_mentor_for_pay')
        if m_id:
            amount = report_data[m_id]['to_pay']
            target_ids.append(m_id)
            total_amount = amount
            name = mentors_map.get(m_id)
            confirm_msg = f"Выплата сотруднику: <b>{name}</b>.\nСумма: <b>{total_amount:,.2f} руб.</b>\n\nПодтверждаете?"
        else:
            await update.message.reply_text("Ошибка выбора.")
            return "SALARY_MAIN_MENU"

    # СЦЕНАРИЙ: ВЫБРАТЬ ИЗ СПИСКА
    elif choice == "👤 Выбрать сотрудника":
        buttons = []
        button_map = {}

        # 1. Менторы
        for m_id, data in report_data.items():
            if data['to_pay'] > 0:
                name = mentors_map.get(m_id)
                btn_text = f"👨‍🏫 {name} ({data['to_pay']:,.0f}р)"
                buttons.append([btn_text])
                button_map[btn_text] = ("mentor", m_id)

        # 2. 🔥 КК
        kk_report = context.user_data.get('kk_report_data', {})
        for kk_id, amount in kk_report.items():
            if amount > 0:
                kk_obj = session.query(CareerConsultant).filter_by(id=kk_id).first()
                if kk_obj:
                    btn_text = f"💼 {kk_obj.full_name} ({amount:,.0f}р)"
                    buttons.append([btn_text])
                    button_map[btn_text] = ("kk", kk_id)

        context.user_data['salary_payment_button_map'] = button_map
        buttons.append(["🔙 Возврат в меню"])

        await update.message.reply_text(
            "Кому выплачиваем?",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )
        return "SALARY_PAY_SELECT"

    # СЦЕНАРИЙ: НАЖАЛИ НА КНОПКУ СОТРУДНИКА
        # СЦЕНАРИЙ: НАЖАЛИ НА КНОПКУ СОТРУДНИКА
    else:
        button_map = context.user_data.get('salary_payment_button_map', {})
        res = button_map.get(choice)

        if res:
            res_type, res_id = res
            if res_type == "mentor":
                # Логика для ментора
                target_ids = [res_id]
                total_amount = report_data[res_id]['to_pay']
                name = mentors_map.get(res_id)
            else:
                # 🔥 Логика для КК
                target_kk_ids = [res_id]
                kk_report = context.user_data.get('kk_report_data', {})
                total_amount = kk_report.get(res_id, 0.0)
                kk_obj = session.query(CareerConsultant).filter_by(id=res_id).first()
                name = kk_obj.full_name if kk_obj else "КК"

            confirm_msg = f"Выплачиваем: <b>{name}</b>\nСумма: <b>{total_amount:,.2f} руб.</b>\n\nПодтверждаете?"
        else:
            await update.message.reply_text("Не нашел сотрудника или ему нечего платить.")
            return "SALARY_PAY_SELECT"

    # Сохраняем контекст оплаты
    context.user_data['payment_context'] = {
        'target_ids': target_ids,
        'target_kk_ids': target_kk_ids,  # Передаем ID консультантов
        'total_amount': total_amount
    }
    await update.message.reply_text(
        confirm_msg,
        reply_markup=ReplyKeyboardMarkup([["✅ ДА, ВЫПЛАТИТЬ"], ["❌ ОТМЕНА"]], one_time_keyboard=True),
        parse_mode="HTML"
    )
    return "SALARY_CONFIRM_PAY"


# === ШАГ 5: ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ И ЗАПИСЬ В БД ===

async def confirm_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice != "✅ ДА, ВЫПЛАТИТЬ":
        await update.message.reply_text("❌ Выплата отменена.")
        return await exit_to_main_menu(update, context)

    pay_ctx = context.user_data.get('payment_context')
    target_ids = pay_ctx.get('target_ids', [])
    target_kk_ids = pay_ctx.get('target_kk_ids', [])  # Получаем КК

    period_start = context.user_data['salary_period']['start']
    period_end = context.user_data['salary_period']['end']

    try:
        processed_count = 0
        total_recorded = 0.0

        # ВЫПЛАТА МЕНТОРАМ
        for m_id in target_ids:
            unpaid = session.query(Salary).filter(
                Salary.mentor_id == m_id,
                func.date(Salary.date_calculated) >= period_start,
                func.date(Salary.date_calculated) <= period_end,
                Salary.is_paid == False
            ).all()
            if unpaid:
                amount = sum(float(s.calculated_amount) for s in unpaid)
                new_payout = Payout(mentor_id=m_id, total_amount=amount, period_start=period_start,kk_id=None,
                                    period_end=period_end, payout_status='completed', date_processed=datetime.utcnow())
                session.add(new_payout)
                for s in unpaid: s.is_paid = True
                total_recorded += amount
                processed_count += 1

        # ВЫПЛАТА КАРЬЕРНЫМ КОНСУЛЬТАНТАМ
        for k_id in target_kk_ids:
            unpaid_kk = session.query(SalaryKK).filter(
                SalaryKK.kk_id == k_id,
                func.date(SalaryKK.date_calculated) >= period_start,
                func.date(SalaryKK.date_calculated) <= period_end,
                SalaryKK.is_paid == False
            ).all()

            if unpaid_kk:
                amount = sum(float(s.calculated_amount) for s in unpaid_kk)
                # 🔥 Добавляем kk_id=k_id в конструктор
                new_payout = Payout(
                    mentor_id=None,
                    kk_id=k_id,  # Обязательно добавь это поле!
                    total_amount=amount,
                    period_start=period_start,
                    period_end=period_end,
                    payout_status='completed',
                    date_processed=datetime.utcnow()
                )
                session.add(new_payout)
                for s in unpaid_kk:
                    s.is_paid = True
                total_recorded += amount
                processed_count += 1

        session.commit()
        await update.message.reply_text(f"✅ Успешно! Выплачено: {total_recorded:,.2f} руб.")
    except Exception as e:
        session.rollback()
        await update.message.reply_text(f"❌ Ошибка: {e}")

    return await exit_to_main_menu(update, context)


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

                # Комиссия канала (Лава/ИП) уже учтена при создании записей в Salary — здесь только пересчёт для сводки
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
