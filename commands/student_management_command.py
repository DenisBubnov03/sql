from datetime import datetime
import logging
from sqlalchemy import func
from sqlalchemy import select
from commands.authorized_users import AUTHORIZED_USERS
from commands.logger import custom_logger
from commands.start_commands import exit_to_main_menu
from commands.states import FIO, TELEGRAM, START_DATE, COURSE_TYPE, TOTAL_PAYMENT, PAID_AMOUNT, COMMISSION, \
    SELECT_MENTOR

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from data_base.db import session
from data_base.models import Payment, Mentor, Student
from data_base.operations import  get_student_by_fio_or_telegram
from student_management.student_management import add_student
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

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

        context.user_data["id"] = student_id  # ✅ Теперь сохраняем `id`
        print(f"✅ DEBUG: student_id сохранён в context: {context.user_data['id']}")

        # ✅ Теперь записываем платёж
        course_type = context.user_data.get("course_type")
        mentor_id = context.user_data.get("mentor_id")
        auto_mentor_id = context.user_data.get("auto_mentor_id")
        if course_type == "Фуллстек":
            payment_mentor_id = auto_mentor_id
        else:
            payment_mentor_id = mentor_id if mentor_id else auto_mentor_id
        if payment_mentor_id is not None:
            record_initial_payment(student_id, context.user_data.get("paid_amount", 0), payment_mentor_id)
        else:
            print(f"❌ DEBUG: Не выбран ни один ментор для платежа студента {student_id}")

        # ✅ Получаем имена менторов
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

        # ✅ Финальное сообщение
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

        detailed_payments = session.query(Payment).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.status == "подтвержден",
            ~Payment.comment.ilike("%преми%")  # исключаем премии из основного расчёта
        ).all()

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

        if fullstack_students:
            bonus = len(fullstack_students) * 5000
            mentor_salaries[1] += bonus
            for student in fullstack_students:
                log_line = f"Бонус за фуллстек: {student.fio} (ID {student.id}) | +5000 руб."
                if 1 not in detailed_logs:
                    detailed_logs[1] = []
                detailed_logs[1].append(log_line)

        # Fullstack доля для ментора 3
        # 🔁 Новый расчёт по Фуллстек: распределение 30%/10%/20%
        for payment in detailed_payments:
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if not student or student.training_type != "Фуллстек":
                continue

            amount = float(payment.amount)
            mentor_id = payment.mentor_id

            # 🔹 Ментор 3 получает:
            if mentor_id == 3:
                bonus = amount * 0.3
                mentor_salaries[3] += bonus
                detailed_logs.setdefault(3, []).append(
                    f"💼 30% ментору 3 за своего фуллстек ученика {student.fio} | "
                    f"{payment.payment_date}, {amount} руб. | +{round(bonus, 2)} руб."
                )
            else:
                bonus_3 = amount * 0.1
                mentor_salaries[3] += bonus_3
                detailed_logs.setdefault(3, []).append(
                    f"🔁 10% ментору 3 за чужого фуллстек ученика {student.fio} | "
                    f"{payment.payment_date}, {amount} руб. | +{round(bonus_3, 2)} руб."
                )

                bonus_other = amount * 0.2
                mentor_salaries[mentor_id] += bonus_other
                detailed_logs.setdefault(mentor_id, []).append(
                    f"💼 20% ментору {mentor_id} за фуллстек ученика {student.fio} | "
                    f"{payment.payment_date}, {amount} руб. | +{round(bonus_other, 2)} руб."
                )

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
            mentor_salaries[mentor_id] += bonus_amount

            detailed_logs.setdefault(mentor_id, []).append(
                f"🎁 Премия {payment.amount} руб. | {payment.payment_date} | +{bonus_amount} руб."
            )

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
