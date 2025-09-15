from datetime import datetime
import logging
from sqlalchemy import func
from sqlalchemy import select
from commands.authorized_users import AUTHORIZED_USERS
from commands.logger import custom_logger
from commands.start_commands import exit_to_main_menu
from commands.states import FIO, TELEGRAM, START_DATE, COURSE_TYPE, TOTAL_PAYMENT, PAID_AMOUNT, \
    SELECT_MENTOR, MAIN_MENU

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from data_base.db import session
from data_base.models import Payment, Mentor, Student, CareerConsultant, FullstackTopicAssign
from data_base.operations import  get_student_by_fio_or_telegram
from student_management.student_management import add_student
from commands.fullstack_salary_calculator import calculate_fullstack_salary
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

def debug_fullstack_data():
    """Отладочная функция для проверки данных фуллстеков"""
    try:
        # Проверяем фуллстек студентов
        fullstack_students = session.query(Student).filter(Student.training_type == "Фуллстек").all()
        logger.info(f"🔍 DEBUG: Всего фуллстек студентов: {len(fullstack_students)}")
        
        # Проверяем записи принятых тем
        all_topics = session.query(FullstackTopicAssign).all()
        logger.info(f"🔍 DEBUG: Всего записей принятых тем: {len(all_topics)}")
        
        # Проверяем ручные темы
        manual_topics = session.query(FullstackTopicAssign).filter(
            FullstackTopicAssign.topic_manual.isnot(None)
        ).all()
        logger.info(f"🔍 DEBUG: Всего ручных тем: {len(manual_topics)}")
        
        # Проверяем авто темы
        auto_topics = session.query(FullstackTopicAssign).filter(
            FullstackTopicAssign.topic_auto.isnot(None)
        ).all()
        logger.info(f"🔍 DEBUG: Всего авто тем: {len(auto_topics)}")
        
        # Показываем примеры данных
        if manual_topics:
            logger.info("🔍 DEBUG: Примеры ручных тем:")
            for topic in manual_topics[:5]:  # Первые 5
                logger.info(f"  • Студент {topic.student_id}, Ментор {topic.mentor_id}: {topic.topic_manual}")
        
        if auto_topics:
            logger.info("🔍 DEBUG: Примеры авто тем:")
            for topic in auto_topics[:5]:  # Первые 5
                logger.info(f"  • Студент {topic.student_id}, Ментор {topic.mentor_id}: {topic.topic_auto}")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при отладке данных фуллстеков: {e}")

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
            # Хардкодим комиссию "2, 50%"
            context.user_data["commission"] = "2, 50%"
            
            # Сразу создаем студента и записываем платеж
            mentor_id = context.user_data.get("mentor_id", 1)

            # Обработка даты
            from datetime import datetime
            start_date_str = context.user_data["start_date"]
            if isinstance(start_date_str, str):
                try:
                    start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
                except Exception:
                    start_date = None
            else:
                start_date = start_date_str
                
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
            from data_base.db import session
            from data_base.models import Mentor

            mentor_id = context.user_data.get("mentor_id")
            auto_mentor_id = context.user_data.get("auto_mentor_id")
            mentor_name = None
            auto_mentor_name = None
            if mentor_id:
                mentor = session.query(Mentor).filter(Mentor.id == mentor_id).first()
                mentor_name = mentor.full_name if mentor else f"ID {mentor_id}"
            if auto_mentor_id:
                auto_mentor = session.query(Mentor).filter(Mentor.id == auto_mentor_id).first()
                auto_mentor_name = auto_mentor.full_name if auto_mentor else f"ID {auto_mentor_id}"

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

            await update.message.reply_text(msg)
            await exit_to_main_menu(update, context)
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                f"Сумма оплаты должна быть в пределах от 0 до {total_payment}. Попробуйте ещё раз."
            )
            return PAID_AMOUNT
    except ValueError:
        await update.message.reply_text("Введите корректное число. Попробуйте ещё раз.")
        return PAID_AMOUNT

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
        ).all()

        logger.info(f"📊 Найдено детальных платежей: {len(detailed_payments)}")

        for payment in detailed_payments:
            mentor_id = payment.mentor_id
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if not student:
                continue

            if student.training_type == "Фуллстек":
                continue  # Fullstack оплачивается отдельно: фикс 5000 ментору 1, 30% ментору 3

            if mentor_id == 1 and student.training_type == "Ручное тестирование":
                percent = 0.3
            elif mentor_id == 3 and student.training_type == "Автотестирование":
                percent = 0.3
            else:
                percent = 0.2

            payout = float(payment.amount) * percent
            if mentor_id not in mentor_salaries:
                mentor_salaries[mentor_id] = 0
            mentor_salaries[mentor_id] += payout

            line = f"{student.fio} (ID {student.id}) {student.training_type}, {payment.payment_date}, {payment.amount} {payment.comment} руб., {int(percent*100)}%, {round(payout, 2)} руб."

            if mentor_id not in detailed_logs:
                detailed_logs[mentor_id] = []
            detailed_logs[mentor_id].append(line)

        # 🔁 Бонусы 10% за чужих студентов (кроме Fullstack)
        for payment in detailed_payments:
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if not student:
                continue

            if student.training_type == "Фуллстек":
                continue  # ❌ Бонус не начисляется за Fullstack

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

        # 💻 НОВАЯ СИСТЕМА РАСЧЕТА ЗП ДИРЕКТОРОВ НАПРАВЛЕНИЯ ЗА ФУЛЛСТЕК
        logger.info("💻 Запускаем новую систему расчета ЗП директоров направления за фуллстек")
        
        # Отладочная информация
        debug_fullstack_data()
        
        fullstack_salary_result = calculate_fullstack_salary(start_date, end_date)
        
        # Интегрируем ЗП директоров направления в общий расчет для каждого директора
        for director_id, salary in fullstack_salary_result['salaries'].items():
            if salary > 0:
                if director_id not in mentor_salaries:
                    mentor_salaries[director_id] = 0
                mentor_salaries[director_id] += salary
                
                # Добавляем логи фуллстеков в общие логи директора
                if director_id not in detailed_logs:
                    detailed_logs[director_id] = []
                detailed_logs[director_id].extend(fullstack_salary_result['logs'][director_id])
        
        logger.info(f"💻 Новая система фуллстеков: обработано {fullstack_salary_result['students_processed']} студентов")

        # 🎁 Учет премий (выплаты с комментарием "Премия")
        premium_payments = session.query(Payment).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.status == "подтвержден",
            Payment.comment.ilike("%преми%")  # ловим "Премия", "премия", "ПРЕМИЯ" и т.д.
        ).all()

        for payment in premium_payments:
            bonus_amount = float(payment.amount)
            mentor_id = payment.mentor_id
            if mentor_id not in mentor_salaries:
                mentor_salaries[mentor_id] = 0
            mentor_salaries[mentor_id] += bonus_amount

            detailed_logs.setdefault(mentor_id, []).append(
                f"🎁 Премия {payment.amount} руб. | {payment.payment_date} | +{bonus_amount} руб."
            )

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
            ).all()
            
            # Фильтруем по комиссии
            commission_payments = [p for p in all_student_payments if "комисси" in p.comment.lower()]
            
            # 10% от суммы комиссий
            total_commission = sum(float(p.amount) for p in commission_payments)
            salary = total_commission * 0.1
            career_consultant_salaries[consultant.id] = round(salary, 2)
            
            # Подробное логирование каждого платежа комиссии
            if commission_payments:
                detailed_logs.setdefault(f"cc_{consultant.id}", []).append(
                    f"💼 Карьерный консультант {consultant.full_name} | "
                    f"Комиссии: {total_commission} руб. | 10% = {salary} руб."
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
            elif salary > 0:
                detailed_logs.setdefault(f"cc_{consultant.id}", []).append(
                    f"💼 Карьерный консультант {consultant.full_name} | "
                    f"Комиссии: {total_commission} руб. | 10% = {salary} руб."
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
                [[name] for name in context.user_data["mentors_list"].keys()],
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
                [[name] for name in context.user_data["mentors_list"].keys()],
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
            [[name] for name in context.user_data["mentors_list"].keys()],
            one_time_keyboard=True
        )
    )
    return SELECT_MENTOR

async def handle_mentor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = update.message.text.strip()
    mentors_list = context.user_data.get("mentors_list", {})

    if selected not in mentors_list:
        await update.message.reply_text("❌ Пожалуйста, выберите одного из предложенных.")
        return SELECT_MENTOR

    course_type = context.user_data.get("course_type")
    # Для Fullstack: сначала ручной, потом авто
    if course_type == "Фуллстек":
        # Если еще не выбран ручной ментор — сейчас выбираем его
        if "mentor_id" not in context.user_data:
            context.user_data["mentor_id"] = mentors_list[selected]
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
                    [[name] for name in context.user_data["mentors_list"].keys()],
                    one_time_keyboard=True
                )
            )
            return SELECT_MENTOR
        else:
            # Сейчас выбираем авто-ментора
            context.user_data["auto_mentor_id"] = mentors_list[selected]
            await update.message.reply_text("Оба ментора выбраны. Введите общую стоимость обучения:")
            return TOTAL_PAYMENT
    elif course_type == "Автотестирование":
        context.user_data["auto_mentor_id"] = mentors_list[selected]
        context.user_data["mentor_id"] = None
        await update.message.reply_text("Введите общую стоимость обучения:")
        return TOTAL_PAYMENT
    else:  # Ручное тестирование
        context.user_data["mentor_id"] = mentors_list[selected]
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
                    import asyncio
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

        total_initial = 0.0
        total_additional = 0.0
        total_commission = 0.0

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
                if "первонач" in comment_lower:
                    total_initial += amount
                elif "доплат" in comment_lower:
                    total_additional += amount
                elif "комисси" in comment_lower:
                    total_commission += amount

        total_prepayment = round(total_initial + total_additional, 2)
        total_postpayment = round(total_commission, 2)
        tax_amount = round(salary * 0.06, 2)

        # Вычисляем составляющие зарплаты (20% от сумм)
        from_students = round(total_prepayment * 0.2, 2)  # с учеников (первоначальный + доплата)
        from_offers = round(total_postpayment * 0.2, 2)   # с оффера (комиссия)
        
        # Добавляем разбивку зарплаты после итоговой зарплаты
        report += f"📊 Составляющие зарплаты:\n"
        report += f"| с учеников {from_students} руб. |\n"
        report += f"| с оффера {from_offers} руб. |\n"
        report += f"| налог {tax_amount} руб. |\n\n"

        # Показываем 20% от сумм
        prepayment_20_percent = round(total_prepayment * 0.2, 2)
        postpayment_20_percent = round(total_postpayment * 0.2, 2)

        report += f"Предоплата (первоначальный + доплата): {prepayment_20_percent} руб. (20% от {total_prepayment} руб.)\n"
        report += f"Постоплата (комиссия): {postpayment_20_percent} руб. (20% от {total_postpayment} руб.)\n"
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
    ).all()
    
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

    if period_start and period_end:
        student_ids_subq = session.query(Student.id).filter(Student.career_consultant_id == consultant.id)
        payments_q = session.query(Payment).filter(
            Payment.student_id.in_(student_ids_subq),
            Payment.payment_date >= period_start,
            Payment.payment_date <= period_end,
            Payment.status == "подтвержден",
        ).all()

        for payment in payments_q:
            comment_lower = (payment.comment or "").lower()
            amount = float(payment.amount)
            if "первонач" in comment_lower:
                total_initial += amount
            elif "доплат" in comment_lower:
                total_additional += amount
            elif "комисси" in comment_lower:
                total_commission += amount

    total_prepayment = round(total_initial + total_additional, 2)
    total_postpayment = round(total_commission, 2)
    tax_amount = round(salary * 0.06, 2)

    # Показываем 20% от сумм
    prepayment_20_percent = round(total_prepayment * 0.2, 2)
    postpayment_20_percent = round(total_postpayment * 0.2, 2)

    report += f"Предоплата (первоначальный + доплата): {prepayment_20_percent} руб. (20% от {total_prepayment} руб.)\n"
    report += f"Постоплата (комиссия): {postpayment_20_percent} руб. (20% от {total_postpayment} руб.)\n"
    report += f"Налог 6% к уплате: {tax_amount} руб.\n\n"

    if commission_payments:
        report += "📋 Детализация комиссий (10% от каждого платежа):\n"
        for payment in commission_payments:
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if student:
                commission_amount = round(float(payment.amount) * 0.1, 2)
                report += f"• {student.fio} ({student.telegram}): {payment.amount} руб. → {commission_amount} руб.\n"
                report += f"  📅 {payment.payment_date} | 💬 {payment.comment}\n"
    else:
        report += "📋 Детализация комиссий не найдена.\n"
    
    return report
