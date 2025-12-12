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
    SELECT_MENTOR, IS_REFERRAL, REFERRER_TELEGRAM, STUDENT_SOURCE
from data_base.db import session
from data_base.models import Payment, Student
from data_base.models import Payout, Salary, Mentor
from data_base.models import StudentMeta
from data_base.operations import get_student_by_fio_or_telegram
from student_management.student_management import add_student

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
    Записывает первоначальный платёж в `payments` и начисляет бонус директору.
    """
    try:
        if mentor_id is None:
            print(f"❌ DEBUG: Платёж не записан — не передан mentor_id для студента {student_id}")
            return

        if paid_amount > 0:
            # 1. Создаем и сохраняем платеж
            new_payment = Payment(
                student_id=student_id,
                mentor_id=mentor_id,
                amount=paid_amount,
                payment_date=datetime.now().date(),
                comment="Первоначальный платёж при регистрации",
                status="подтвержден"
            )

            session.add(new_payment)
            session.commit()  # В этот момент у new_payment появляется ID
            print(f"✅ DEBUG: Платёж записан в payments! {paid_amount} руб. (ID: {new_payment.id})")

            # 2. Начисляем бонус директору (ДОБАВЛЕННАЯ ЧАСТЬ)
            try:
                # Нам нужен объект студента для проверки типа обучения
                student = session.query(Student).filter(Student.id == student_id).first()

                if student:
                    salary_manager = SalaryManager()
                    # Передаем сессию, студента и ID только что созданного платежа
                    salary_manager.init_director_bonus_commission(
                        session=session,
                        student=student,
                        payment_id=new_payment.id
                    )
                    session.commit()  # Фиксируем записи в salary и curator_commissions
                    print(f"✅ DEBUG: Бонус директора обработан для платежа {new_payment.id}")
                else:
                    print(f"⚠️ Warn: Студент {student_id} не найден, бонус директора пропущен.")

            except Exception as e:
                print(f"❌ Ошибка при начислении бонуса директора: {e}")
                # Не прерываем выполнение, так как сам платеж уже записан

    except Exception as e:
        print(f"❌ Ошибка в record_initial_payment: {e}")
        session.rollback()

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


# async def calculate_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     Рассчитывает зарплату, агрегируя готовые данные из таблицы Salary,
#     и добавляет периодические начисления (KPI, КК).
#     """
#     try:
#         from datetime import datetime, date
#         from sqlalchemy import func
#         # Импортируем модель Salary, так как теперь это главный источник
#         from data_base.models import Salary, Mentor, CareerConsultant, Payment
#
#         # 1. Парсинг дат
#         date_range = update.message.text.strip()
#         if " - " not in date_range:
#             await update.message.reply_text("❌ Неверный формат! Используйте: ДД.ММ.ГГГГ - ДД.ММ.ГГГГ")
#             return "WAIT_FOR_SALARY_DATES"
#
#         start_date_str, end_date_str = map(str.strip, date_range.split("-"))
#         try:
#             start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
#             end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
#         except ValueError:
#             await update.message.reply_text("❌ Ошибка в дате.")
#             return "WAIT_FOR_SALARY_DATES"
#
#         await update.message.reply_text(f"📊 Сбор данных из таблицы Salary за {start_date_str} - {end_date_str}...")
#
#         # Структуры для отчета
#         mentor_salaries = {}  # {mentor_id: float}
#         detailed_logs = {}  # {mentor_id: [str]}
#         all_mentors = {m.id: m for m in session.query(Mentor).all()}
#
#         # =================================================================================
#         # 🟢 1. ГЛАВНЫЙ СБОР: ТРАНЗАКЦИИ ИЗ SALARY
#         # =================================================================================
#         # Используем поле date_calculated, которое вы показали на скриншоте
#         salary_records = session.query(Salary).filter(
#             func.date(Salary.date_calculated) >= start_date,
#             func.date(Salary.date_calculated) <= end_date
#         ).all()
#
#         logger.info(f"Найдено {len(salary_records)} записей в таблице Salary.")
#
#         for record in salary_records:
#             m_id = record.mentor_id
#             if not m_id: continue
#
#             amount = float(record.calculated_amount)
#
#             # Инициализация
#             if m_id not in mentor_salaries:
#                 mentor_salaries[m_id] = 0.0
#                 detailed_logs[m_id] = []
#
#             mentor_salaries[m_id] += amount
#
#             # Формируем красивую строку лога
#             # Берем дату из date_calculated
#             date_log = record.date_calculated.strftime("%d.%m") if record.date_calculated else "??"
#             status_icon = "✅" if record.is_paid else "⏳"
#
#             log_line = f"{status_icon} {date_log}: {record.comment} | +{amount:,.2f} руб."
#             detailed_logs[m_id].append(log_line)
#
#         # =================================================================================
#         # 🟠 2. ДОПОЛНИТЕЛЬНЫЕ РАСЧЕТЫ (KPI, Страховка, Премии)
#         # =================================================================================
#         # Эти данные часто считаются "поверх" базы, в конце месяца.
#
#         from config import Config
#
#         # --- А. Учет ПРЕМИЙ (Ручные платежи с комментом "Премия") ---
#         # Если вы не проводите премии через SalaryManager, оставляем этот блок
#         premium_payments = session.query(Payment).filter(
#             Payment.payment_date >= start_date,
#             Payment.payment_date <= end_date,
#             Payment.status == "подтвержден",
#             Payment.mentor_id.isnot(None),
#             func.lower(Payment.comment).like("%премия%")
#         ).all()
#
#         for p in premium_payments:
#             amt = float(p.amount)
#             if p.mentor_id not in mentor_salaries:
#                 mentor_salaries[p.mentor_id] = 0.0
#                 detailed_logs[p.mentor_id] = []
#
#             mentor_salaries[p.mentor_id] += amt
#             detailed_logs[p.mentor_id].append(f"🎁 Премия (из Payments): {p.comment} | +{amt} руб.")
#
#         # --- Б. Страховка Кураторов (Ваш старый код) ---
#         if Config.CURATOR_INSURANCE_ENABLED:
#             # ... (Вставьте сюда ваш код расчета страховки из предыдущей версии) ...
#             # Главное - добавляйте результат в mentor_salaries[id] += bonus
#             pass
#
#             # --- В. KPI (Ваш старый код) ---
#         if Config.KPI_ENABLED:
#             # ... (Вставьте сюда ваш код расчета KPI) ...
#             pass
#
#         # =================================================================================
#         # 🟣 3. КАРЬЕРНЫЕ КОНСУЛЬТАНТЫ (Отдельная логика)
#         # =================================================================================
#         # Если КК еще не переведены на SalaryManager, оставляем старый расчет
#         career_consultant_salaries = {}
#         all_consultants = {c.id: c for c in session.query(CareerConsultant).filter_by(is_active=True).all()}
#
#         # ... (Вставьте сюда ваш цикл расчета КК, он у вас был сложный с датой 18.11) ...
#         # Или, если вы начнете писать КК тоже в таблицу Salary, этот блок можно будет убрать.
#
#         # =================================================================================
#         # 🏁 4. ФИНАЛЬНЫЙ ОТЧЕТ
#         # =================================================================================
#         total_mentors = sum(mentor_salaries.values())
#         total_cc = sum(career_consultant_salaries.values())
#         grand_total = total_mentors + total_cc
#
#         report = f"📊 ОТЧЕТ ПО ЗАРПЛАТЕ ({start_date_str} - {end_date_str})\n"
#         report += f"Использована таблица транзакций (Salary)\n\n"
#
#         report += "👨‍🏫 Менторы:\n"
#         for m_id, amount in mentor_salaries.items():
#             if amount == 0: continue
#             mentor = all_mentors.get(m_id)
#             name = mentor.full_name if mentor else f"ID {m_id}"
#
#             # Считаем налог для отображения
#             with_tax = amount * 1.06
#             report += f"• {name}: {amount:,.2f} руб. (с налогом: {with_tax:,.2f})\n"
#
#         if total_cc > 0:
#             report += f"\n💼 Карьерные консультанты: {total_cc:,.2f} руб.\n"
#
#         report += f"\n💰 ИТОГО К ВЫПЛАТЕ: {grand_total:,.2f} руб."
#
#         # Сохраняем контекст для детального отчета (кнопка "Показать подробности")
#         context.user_data['detailed_salary_data'] = {
#             'mentor_salaries': mentor_salaries,
#             'career_consultant_salaries': career_consultant_salaries,
#             'detailed_logs': detailed_logs,
#             'start_date': start_date_str,
#             'end_date': end_date_str,
#             'all_mentors': all_mentors,
#             'all_consultants': all_consultants
#         }
#
#         await update.message.reply_text(
#             report,
#             reply_markup=ReplyKeyboardMarkup(
#                 [["Да, показать подробности"], ["Нет, достаточно"]],
#                 one_time_keyboard=True
#             )
#         )
#         return "WAIT_FOR_DETAILED_SALARY"
#
#     except Exception as e:
#         logger.error(f"Error calculating salary: {e}", exc_info=True)
#         await update.message.reply_text(f"❌ Ошибка расчета: {e}")
#         return "WAIT_FOR_SALARY_DATES"

# student_management_command.py

# ... (импорты остаются) ...

# === ШАГ 1: РАСЧЕТ И ОТОБРАЖЕНИЕ ОБЩЕГО МЕНЮ ===

# === ОБРАБОТЧИКИ МЕНЮ (С исправленными кнопками и поиском имен) ===
# === ШАГ 1: РАСЧЕТ И ОТОБРАЖЕНИЕ ОТЧЕТА ===

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

        text += f"\n💰 <b>ИТОГО К ВЫПЛАТЕ: {total_to_pay_global:,.2f} руб.</b>\n\n"
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

    # 1. Навигация
    if choice == "🔙 Возврат в меню":
        period_str = context.user_data.get('salary_period_str', '')
        await update.message.reply_text(
            f"Меню отчета ({period_str}).",
            reply_markup=ReplyKeyboardMarkup(
                [["💸 Выплатить ЗП"], ["📜 Показать историю операций"], ["🔙 Возврат в меню"]], one_time_keyboard=True)
        )
        return "SALARY_MAIN_MENU"

    # 2. Вывод всех сразу
    if choice == "👥 По всем сразу":
        full_text = "📋 <b>История операций по всем:</b>\n\n"
        for m_id, data in report_data.items():
            name = mentors_map.get(m_id, f"ID {m_id}")
            full_text += f"👤 <b>{name}</b>\n"
            if data['logs']:
                for log in data['logs']:
                    full_text += f"   - {log}\n"
            else:
                full_text += "   (Нет операций)\n"
            full_text += "\n"

        for part in split_long_message(full_text):
            await update.message.reply_text(part, parse_mode="HTML")

        await update.message.reply_text("Действия:", reply_markup=ReplyKeyboardMarkup([["🔙 Возврат в меню"]],
                                                                                      one_time_keyboard=True))
        return "SALARY_MAIN_MENU"

    # 3. Выбор конкретного сотрудника (Генерация кнопок)
    elif choice == "👤 Выбрать сотрудника":
        buttons = []
        button_map = {}  # Карта для поиска ID по тексту кнопки

        for m_id, data in report_data.items():
            name = mentors_map.get(m_id, f"ID {m_id}")
            # Формируем кнопку с долгом
            btn_text = f"{name} (Долг: {data['to_pay']}р)"
            buttons.append([btn_text])
            button_map[btn_text] = m_id  # Запоминаем ID

        context.user_data['salary_detail_button_map'] = button_map  # Сохраняем карту

        buttons.append(["🔙 Возврат в меню"])
        await update.message.reply_text("Выберите сотрудника:",
                                        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True))
        return "SALARY_DETAIL_SELECT"

    # 4. Обработка нажатия на кнопку сотрудника
    else:
        # Ищем ID ментора по тексту кнопки через нашу карту
        button_map = context.user_data.get('salary_detail_button_map', {})
        selected_id = button_map.get(choice)

        if not selected_id:
            await update.message.reply_text("Не нашел такого сотрудника. Используйте кнопки.")
            return "SALARY_DETAIL_SELECT"

        data = report_data[selected_id]
        name = mentors_map.get(selected_id)

        text = f"👤 <b>{name}</b>\n"
        text += f"🔹 Начислено: {data['total']} | 🔻 К выплате: {data['to_pay']}\n\n"
        text += "📜 История:\n" + "\n".join(data['logs'])

        context.user_data['selected_mentor_for_pay'] = selected_id

        keyboard = [["🔙 Возврат в меню"]]
        if data['to_pay'] > 0:
            keyboard.insert(0, ["💸 Выплатить этому сотруднику"])

        await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True),
                                        parse_mode="HTML")
        return "SALARY_PAY_SELECT"


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
    total_amount = 0.0
    confirm_msg = ""

    # СЦЕНАРИЙ: ПЛАТИМ ВСЕМ
    if choice == "👥 Выплатить ВСЕМ":
        for m_id, data in report_data.items():
            if data['to_pay'] > 0:
                target_ids.append(m_id)
                total_amount += data['to_pay']
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
        for m_id, data in report_data.items():
            if data['to_pay'] > 0:
                name = mentors_map.get(m_id)
                btn_text = f"{name} ({data['to_pay']:,.0f}р)"
                buttons.append([btn_text])
                button_map[btn_text] = m_id

        context.user_data['salary_payment_button_map'] = button_map  # Сохраняем карту для оплаты

        buttons.append(["🔙 Возврат в меню"])
        await update.message.reply_text("Кому выплачиваем?",
                                        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True))
        return "SALARY_PAY_SELECT"

    # СЦЕНАРИЙ: НАЖАЛИ НА КНОПКУ СОТРУДНИКА
    else:
        # Ищем ID по карте
        button_map = context.user_data.get('salary_payment_button_map', {})
        selected_id = button_map.get(choice)

        if selected_id and report_data[selected_id]['to_pay'] > 0:
            target_ids.append(selected_id)
            total_amount = report_data[selected_id]['to_pay']
            name = mentors_map.get(selected_id)
            confirm_msg = f"Выплачиваем: <b>{name}</b>\nСумма: <b>{total_amount:,.2f} руб.</b>\n\nПодтверждаете?"
        else:
            await update.message.reply_text("Не нашел сотрудника или ему нечего платить.")
            return "SALARY_PAY_SELECT"

    # Сохраняем контекст оплаты
    context.user_data['payment_context'] = {
        'target_ids': target_ids,
        'total_amount': total_amount
    }

    await update.message.reply_text(
        confirm_msg,
        reply_markup=ReplyKeyboardMarkup([["✅ ДА, ВЫПЛАТИТЬ"], ["❌ ОТМЕНА"]], one_time_keyboard=True),
        parse_mode="HTML"
    )
    return "SALARY_CONFIRM_PAY"


# confirm_payout остается прежним, только убедитесь, что кнопка возврата там "🔙 Возврат в меню"


# === ШАГ 5: ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ И ЗАПИСЬ В БД ===

async def confirm_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice != "✅ ДА, ВЫПЛАТИТЬ":
        await update.message.reply_text("Выплата отменена.", reply_markup=ReplyKeyboardMarkup([["🔙 В главное меню"]],
                                                                                              one_time_keyboard=True))
        return "SALARY_MAIN_MENU"

    # НАЧИНАЕМ ТРАНЗАКЦИЮ
    pay_ctx = context.user_data.get('payment_context')
    if not pay_ctx:
        await update.message.reply_text("Ошибка контекста.")
        return "SALARY_MAIN_MENU"

    target_ids = pay_ctx['target_ids']
    period_start = context.user_data['salary_period']['start']
    period_end = context.user_data['salary_period']['end']

    try:
        processed_count = 0
        total_recorded = 0.0

        for m_id in target_ids:
            # 1. Находим все неоплаченные записи Salary этого ментора за этот период
            unpaid_salaries = session.query(Salary).filter(
                Salary.mentor_id == m_id,
                func.date(Salary.date_calculated) >= period_start,
                func.date(Salary.date_calculated) <= period_end,
                Salary.is_paid == False  # Только те, что еще не оплачены
            ).all()

            if not unpaid_salaries:
                continue

            # Сумма к выплате по факту
            amount_to_pay = sum(float(s.calculated_amount) for s in unpaid_salaries)

            if amount_to_pay <= 0: continue

            # 2. Создаем запись в Payouts
            new_payout = Payout(
                mentor_id=m_id,
                period_start=period_start,
                period_end=period_end,
                total_amount=amount_to_pay,
                payout_status='completed',
                date_processed=datetime.utcnow()
            )
            session.add(new_payout)
            session.flush()  # Чтобы получить ID

            # 3. Обновляем Salary (ставим галочку "Выплачено")
            for sal in unpaid_salaries:
                sal.is_paid = True
                # Если вы добавите payout_id в Salary, то: sal.payout_id = new_payout.payout_id
                session.add(sal)

            total_recorded += amount_to_pay
            processed_count += 1

        session.commit()

        await update.message.reply_text(
            f"✅ <b>Успешно!</b>\n\nСоздано выплат: {processed_count}\nОбщая сумма: {total_recorded:,.2f} руб.\n\nДанные внесены в реестр выплат.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup([["🔙 В главное меню"]], one_time_keyboard=True)
        )
        return "SALARY_MAIN_MENU"

    except Exception as e:
        session.rollback()
        logger.error(f"Payout Error: {e}")
        await update.message.reply_text(f"❌ Ошибка при сохранении выплаты: {e}")
        return ConversationHandler.END

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
