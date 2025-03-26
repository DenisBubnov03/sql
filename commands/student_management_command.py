from datetime import datetime
import logging
from sqlalchemy import func
from sqlalchemy import select
from commands.authorized_users import AUTHORIZED_USERS
from commands.logger import custom_logger
from commands.start_commands import exit_to_main_menu
from commands.states import FIO, TELEGRAM, START_DATE, COURSE_TYPE, TOTAL_PAYMENT, PAID_AMOUNT, COMMISSION

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from data_base.db import session
from data_base.models import Payment, Mentor, Student
from data_base.operations import  get_student_by_fio_or_telegram, assign_mentor
from student_management.student_management import add_student
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

# Добавление студента: шаг 1 - ввод ФИО
async def add_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Старт добавления студента: запрос ФИО.
    """
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
        await update.message.reply_text(
            "Возвращаемся в главное меню:",
            reply_markup=ReplyKeyboardMarkup(
                [['Добавить студента', 'Просмотреть студентов'],
                 ['Редактировать данные студента', 'Проверить уведомления'],
                 ['Поиск ученика', 'Статистика']],
                one_time_keyboard=True
            )
        )
        return ConversationHandler.END

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
        await update.message.reply_text(
            "Добавление студента прервано. Возвращаемся в главное меню:",
            reply_markup=ReplyKeyboardMarkup(
                [['Добавить студента', 'Просмотреть студентов'],
                 ['Редактировать данные студента', 'Проверить уведомления'],
                 ['Поиск ученика', 'Статистика']],
                one_time_keyboard=True
            )
        )
        return ConversationHandler.END

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
    Завершение добавления студента с введением комиссии и записью платежа.
    """
    try:
        commission_input = update.message.text
        payments, percentage = map(str.strip, commission_input.split(","))
        payments, percentage = int(payments), int(percentage.strip('%'))

        if payments <= 0 or percentage <= 0:
            raise ValueError("Комиссия должна быть положительным числом.")

        context.user_data["commission"] = f"{payments}, {percentage}%"
        mentor_id = assign_mentor(context.user_data["course_type"])

        # ✅ Добавляем студента
        student_id = add_student(
            fio=context.user_data["fio"],
            telegram=context.user_data["telegram"],
            start_date=context.user_data["start_date"],
            training_type=context.user_data["course_type"],
            total_cost=context.user_data["total_payment"],
            payment_amount=context.user_data.get("paid_amount", 0),
            fully_paid="Да" if context.user_data.get("paid_amount", 0) == context.user_data["total_payment"] else "Нет",
            commission=context.user_data["commission"],
            mentor_id=mentor_id
        )

        if not student_id:
            await update.message.reply_text("❌ Ошибка: студент не был создан.")
            return ConversationHandler.END

        context.user_data["id"] = student_id  # ✅ Теперь сохраняем `id`
        print(f"✅ DEBUG: student_id сохранён в context: {context.user_data['id']}")

        # ✅ Теперь записываем платёж
        record_initial_payment(student_id, context.user_data.get("paid_amount", 0), mentor_id)

        # ✅ Получаем имя ментора
        from data_base.db import session
        from data_base.models import Mentor

        mentor = session.query(Mentor).filter(Mentor.id == mentor_id).first()
        mentor_name = mentor.full_name if mentor else f"ID {mentor_id}"

        # ✅ Финальное сообщение
        await update.message.reply_text(f"✅ Студент {context.user_data['fio']} добавлен к ментору {mentor_name}!")

        await exit_to_main_menu(update, context)  # ✅ Сначала выполняем меню
        return ConversationHandler.END  # ✅ Завершаем процесс корректно

    except ValueError:
        await update.message.reply_text("❌ Введите корректные данные о комиссии.")
        return COMMISSION




async def add_student_paid_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос данных о внесённой оплате.
    """
    try:
        paid_amount = int(update.message.text)
        total_payment = context.user_data["total_payment"]

        if 0 <= paid_amount <= total_payment:
            context.user_data["paid_amount"] = paid_amount
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
        await update.message.reply_text("Введите корректное число. Попробуйте ещё раз.")
        return PAID_AMOUNT

def record_initial_payment(student_id, paid_amount, mentor_id):
    """
    Записывает первоначальный платёж в `payments`.
    """
    try:
        if paid_amount > 0:
            new_payment = Payment(
                student_id=student_id,
                mentor_id=mentor_id,
                amount=paid_amount,
                payment_date=datetime.now().date(),
                comment="Первоначальный платёж при регистрации"
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
        logger.info(f"📅 Полученный диапазон дат: {date_range}")

        if " - " not in date_range:
            raise ValueError("Формат должен быть ДД.ММ.ГГГГ - ДД.ММ.ГГГГ")

        start_date_str, end_date_str = map(str.strip, date_range.split("-"))
        start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
        end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()

        if start_date > end_date:
            raise ValueError("Дата начала не может быть позже даты окончания.")

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

        # Детальный расчёт зарплат
        detailed_payments = session.query(Payment).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date
        ).all()

        for payment in detailed_payments:
            mentor_id = payment.mentor_id
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if not student:
                continue

            percent = 0.2
            if mentor_id == 1 and student.training_type == "Ручное тестирование":
                percent = 0.3
            elif mentor_id == 3 and student.training_type == "Автотестирование":
                percent = 0.3
            else:
                percent = 0.2


            payout = float(payment.amount) * percent
            mentor_salaries[mentor_id] += payout

            line = f"{student.fio} (ID {student.id}) {student.training_type}, {payment.payment_date}, {payment.amount} {payment.comment} руб., {int(percent*100)}%, {round(payout, 2)} руб."

            if mentor_id not in detailed_logs:
                detailed_logs[mentor_id] = []
            detailed_logs[mentor_id].append(line)

        # Бонус 10% главным менторам
        for payment in detailed_payments:
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if not student:
                continue

            for head_mentor in session.query(Mentor).filter(Mentor.id.in_([1, 3])).all():
                if head_mentor.direction == student.training_type and payment.mentor_id != head_mentor.id:
                    bonus = float(payment.amount) * 0.1
                    mentor_salaries[head_mentor.id] += bonus

                    line = f"Бонус за {student.fio} (ID {student.id}) {student.training_type}, {payment.payment_date}, {payment.amount} {payment.comment} руб., 10%, {round(bonus, 2)} руб."
                    if head_mentor.id not in detailed_logs:
                        detailed_logs[head_mentor.id] = []
                    detailed_logs[head_mentor.id].append(line)

        # Фуллстек бонусы
        fullstack_students = session.query(Student).filter(
            Student.training_type == "Фуллстек",
            Student.total_cost >= 50000,
            Student.start_date >= start_date,
            Student.start_date <= end_date
        ).all()

        if fullstack_students:
            bonus = len(fullstack_students) * 5000
            mentor_salaries[1] += bonus
            for student in fullstack_students:
                log_line = f"Бонус за фуллстек: {student.fio} (ID {student.id}) | +5000 руб."
                if 1 not in detailed_logs:
                    detailed_logs[1] = []
                detailed_logs[1].append(log_line)

        # Fullstack доля для ментора 3
        fullstack_payment_total = session.query(
            func.sum(Payment.amount)
        ).filter(
            Payment.student_id.in_(
                select(Student.id).filter(Student.training_type == "Фуллстек")
            ),
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date
        ).scalar() or 0

        mentor_3_bonus = float(fullstack_payment_total) * 0.3
        if mentor_3_bonus > 0:
            mentor_salaries[3] += mentor_3_bonus
            log_line = f"30% от всех фуллстек платежей ({fullstack_payment_total} руб.) | +{round(mentor_3_bonus, 2)} руб."
            if 3 not in detailed_logs:
                detailed_logs[3] = []
            detailed_logs[3].append(log_line)

        # Вывод логов в файл
        for mentor_id, logs in detailed_logs.items():
            mentor = all_mentors.get(mentor_id)
            logger.info(f"\n📘 Ментор: {mentor.full_name} ({mentor.telegram})")
            for log in logs:
                logger.info(f"— {log}")
            logger.info(f"Итог: {round(mentor_salaries[mentor_id], 2)} руб.")

        # Формирование сообщения для Telegram
        salary_report = f"📊 Расчёт зарплат за {start_date_str} - {end_date_str}\n\n"
        for mentor in all_mentors.values():
            salary = round(mentor_salaries.get(mentor.id, 0), 2)
            if salary > 0:
                salary_report += f"💰 {mentor.full_name} ({mentor.telegram}): {salary} руб.\n"
            else:
                salary_report += f"❌ {mentor.full_name} ({mentor.telegram}): У ментора нет платежей за этот период\n"

        await update.message.reply_text(salary_report)
        return ConversationHandler.END

    except ValueError as e:
        logger.error(f"❌ Ошибка ввода даты: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}\nВведите период в формате 'ДД.ММ.ГГГГ - ДД.ММ.ГГГГ'.")
        return "WAIT_FOR_SALARY_DATES"


