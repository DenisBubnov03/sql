from datetime import datetime

from sqlalchemy import func
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from classes.comission import AdminCommissionManager
from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS
from commands.logger import log_student_change
from commands.start_commands import exit_to_main_menu
from commands.states import FIELD_TO_EDIT, WAIT_FOR_NEW_VALUE, FIO_OR_TELEGRAM, WAIT_FOR_PAYMENT_DATE, SIGN_CONTRACT, SELECT_CURATOR_TYPE, SELECT_CURATOR_MENTOR
from commands.student_info_commands import calculate_commission
from data_base.db import session
from data_base.models import Student, Payment, CuratorInsuranceBalance, Mentor, ManualProgress, CuratorCommission
from data_base.operations import get_all_students, update_student, get_student_by_fio_or_telegram, delete_student
from telegram import ReplyKeyboardMarkup, KeyboardButton


# Функция редактирования студента
async def edit_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало процесса редактирования студента.
    """
    await update.message.reply_text(
        "Введите ФИО или Telegram студента, данные которого вы хотите отредактировать:",
        reply_markup=ReplyKeyboardMarkup([["Главное меню"]], one_time_keyboard=True)
    )
    return FIO_OR_TELEGRAM


# Ограниченная функция редактирования для NOT_ADMINS
async def edit_student_limited(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ограниченная версия редактирования студента для NOT_ADMINS.
    """
    user_id = update.message.from_user.id
    if user_id not in NOT_ADMINS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Введите ФИО или Telegram студента, данные которого вы хотите отредактировать:",
        reply_markup=ReplyKeyboardMarkup([["Главное меню"]], one_time_keyboard=True)
    )
    return FIO_OR_TELEGRAM


# Редактирование поля студента
async def edit_student_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выбор поля для редактирования или удаления.
    """
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return

    FIELD_MAPPING = {
        "ФИО": "fio",
        "Telegram": "telegram",
        "Сумма оплаты": "payment_amount",
        "Статус обучения": "training_status",
        "Получил работу": "company",
        "Комиссия выплачено": "commission_paid",
        "Удалить ученика": "delete_student"
    }

    field_to_edit = update.message.text.strip()
    student = context.user_data.get("student")

    # Универсальная обработка кнопки "Назад"
    if field_to_edit == "Назад":
        return await exit_to_main_menu(update, context)

    if field_to_edit == "Удалить ученика":
        await update.message.reply_text(
            f"Вы уверены, что хотите удалить студента {student.fio}? Это действие нельзя отменить.",
                reply_markup=ReplyKeyboardMarkup(
                    [["Да, удалить"], ["Нет, отменить"]],
                    one_time_keyboard=True
                )
        )
        return "CONFIRM_DELETE"

    if field_to_edit == "Получил работу":
        # Уникальная обработка для "Получил работу"
        context.user_data["field_to_edit"] = field_to_edit
        context.user_data["employment_step"] = "company"
        await update.message.reply_text("Введите название компании:")
        return WAIT_FOR_NEW_VALUE

    if field_to_edit == "Куратор":
        # Обработка редактирования куратора
        return await edit_curator(update, context)

    if field_to_edit in FIELD_MAPPING:
        context.user_data["field_to_edit"] = field_to_edit

        if field_to_edit == "Дата последнего звонка":
            await update.message.reply_text(
                "Введите дату последнего звонка в формате ДД.ММ.ГГГГ или нажмите 'Сегодня':",
                reply_markup=ReplyKeyboardMarkup(
                    [["Сегодня"], ["Назад"]],
                    one_time_keyboard=True
                )
            )
            return WAIT_FOR_NEW_VALUE

        if field_to_edit == "Статус обучения":
            await update.message.reply_text(
                "Выберите новый статус обучения:",
                reply_markup=ReplyKeyboardMarkup(
                    [["Не учится"], ["Учится"], ["Получил 5 модуль"], ["Устроился"], ["Назад"]],
                    one_time_keyboard=True
                )
            )
            return WAIT_FOR_NEW_VALUE

        await update.message.reply_text(
            f"Введите новое значение для '{field_to_edit}':",
            reply_markup=ReplyKeyboardMarkup([["Назад"]], one_time_keyboard=True)
        )
        return WAIT_FOR_NEW_VALUE

    await update.message.reply_text(
        "Некорректное поле. Выберите одно из предложенных:",
        reply_markup=ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton("ФИО"),
                    KeyboardButton("Telegram"),
                    KeyboardButton("Сумма оплаты"),
                    KeyboardButton("Статус обучения"),
                    KeyboardButton("Получил работу"),
                    KeyboardButton("Комиссия выплачено"),
                    KeyboardButton("Удалить ученика"),
                ],
                [
                    KeyboardButton("Назад")
                ]
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return FIELD_TO_EDIT


# Ограниченное редактирование поля студента для NOT_ADMINS
async def edit_student_field_limited(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ограниченный выбор поля для редактирования для NOT_ADMINS.
    """
    user_id = update.message.from_user.id
    if user_id not in NOT_ADMINS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return ConversationHandler.END

    LIMITED_FIELD_MAPPING = {
        "ФИО": "fio",
        "Telegram": "telegram",
        "Статус обучения": "training_status",
        "Получил работу": "company"
    }

    field_to_edit = update.message.text.strip()
    student = context.user_data.get("student")

    # Универсальная обработка кнопки "Назад"
    if field_to_edit == "Назад":
        return await exit_to_main_menu(update, context)

    if field_to_edit == "Куратор":
        # Обработка редактирования куратора
        return await edit_curator(update, context)

    if field_to_edit == "Получил работу":
        # Уникальная обработка для "Получил работу"
        context.user_data["field_to_edit"] = field_to_edit
        context.user_data["employment_step"] = "company"
        await update.message.reply_text("Введите название компании:")
        return WAIT_FOR_NEW_VALUE

    if field_to_edit in LIMITED_FIELD_MAPPING:
        context.user_data["field_to_edit"] = field_to_edit

        if field_to_edit == "Статус обучения":
            await update.message.reply_text(
                "Выберите новый статус обучения:",
                reply_markup=ReplyKeyboardMarkup(
                    [["Не учится"], ["Учится"], ["Получил 5 модуль"], ["Устроился"], ["Назад"]],
                    one_time_keyboard=True
                )
            )
            return WAIT_FOR_NEW_VALUE

        await update.message.reply_text(
            f"Введите новое значение для '{field_to_edit}':",
            reply_markup=ReplyKeyboardMarkup([["Назад"]], one_time_keyboard=True)
        )
        return WAIT_FOR_NEW_VALUE

    await update.message.reply_text(
        "Некорректное поле. Выберите одно из предложенных:",
        reply_markup=ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton("ФИО"),
                    KeyboardButton("Telegram"),
                    KeyboardButton("Статус обучения"),
                    KeyboardButton("Получил работу"),
                    KeyboardButton("Куратор"),
                ],
                [KeyboardButton("Назад")]
            ],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return FIELD_TO_EDIT

async def handle_student_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Подтверждение удаления студента.
    """
    student = context.user_data.get("student")
    if not student:
        await update.message.reply_text("Ошибка: объект студента не найден.")
        return FIELD_TO_EDIT

    if update.message.text == "Да, удалить":
        try:
            # Удаление студента
            delete_student(student.id)
            await update.message.reply_text(f"Студент {student.fio} успешно удалён.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка при удалении студента: {e}")
    else:
        await update.message.reply_text("Удаление отменено.")

    return await exit_to_main_menu(update, context)

async def handle_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    from config import Config

    student = context.user_data.get("student")
    field_to_edit = context.user_data.get("field_to_edit")
    new_value = update.message.text.strip()
    editor_tg = update.message.from_user.username

    FIELD_MAPPING = {
        "ФИО": "fio",
        "Telegram": "telegram",
        "Дата последнего звонка": "last_call_date",
        "Сумма оплаты": "payment_amount",
        "Статус обучения": "training_status",
        "Получил работу": "company",
        "Комиссия выплачено": "commission_paid"
    }

    # Проверяем, что студент и поле для редактирования существуют
    if not student or not field_to_edit:
        await update.message.reply_text("Ошибка: данные для редактирования отсутствуют. Начните сначала.")
        return ConversationHandler.END

    if field_to_edit == "Комиссия выплачено":
        try:
            # Новая выплата по комиссии
            additional_payment = float(new_value)
            if additional_payment < 0:
                raise ValueError("Сумма не может быть отрицательной.")

            # Расчет общей комиссии и выплаченной суммы
            total_commission = calculate_commission(student)[0]  # Общая комиссия
            current_commission_paid = student.commission_paid or 0  # Выплачено на текущий момент

            # Новая сумма выплаченной комиссии
            new_commission_paid = current_commission_paid + additional_payment

            # Проверка, чтобы выплата не превышала общую сумму комиссии
            if new_commission_paid > total_commission:
                await update.message.reply_text(
                    f"Ошибка: общая выплаченная комиссия ({new_commission_paid:.2f}) "
                    f"превышает рассчитанную ({total_commission:.2f})."
                )
                return WAIT_FOR_NEW_VALUE

            # Обновляем поле "commission_paid" в базе
            update_student(student.id, {"commission_paid": new_commission_paid})

            # Остаток комиссии для оплаты
            remaining_commission = total_commission - new_commission_paid

            # Отправляем уведомление о результате
            await update.message.reply_text(
                f"Сумма комиссии успешно обновлена: {current_commission_paid:.2f} ➡ {new_commission_paid:.2f}\n"
                f"Остаток для оплаты: {remaining_commission:.2f}"
            )

            # Перезагружаем данные студента
            updated_student = session.query(Student).get(student.id)
            context.user_data["student"] = updated_student

        except ValueError:
            await update.message.reply_text("Некорректная сумма. Введите положительное число.")
            return WAIT_FOR_NEW_VALUE
        except Exception as e:
            await update.message.reply_text(f"Произошла ошибка при обновлении: {e}")
            return WAIT_FOR_NEW_VALUE

        # Возвращаемся в главное меню после успешного обновления
        return await exit_to_main_menu(update, context)

    if field_to_edit == "Получил работу":
        employment_step = context.user_data.get("employment_step")

        # Этап: Название компании
        if employment_step is None:
            context.user_data["employment_step"] = "company"
            await update.message.reply_text("Введите название компании:")
            return WAIT_FOR_NEW_VALUE

        # Этап: Дата устройства
        if employment_step == "company":
            context.user_data["company_name"] = new_value
            context.user_data["employment_step"] = "date"
            await update.message.reply_text(
                "Введите дату устройства (формат ДД.ММ.ГГГГ) или нажмите 'Сегодня':",
                reply_markup=ReplyKeyboardMarkup([["Сегодня"]], one_time_keyboard=True)
            )
            return WAIT_FOR_NEW_VALUE

        # Этап: Зарплата
        if employment_step == "date":
            if new_value.lower() == "сегодня":
                new_value = datetime.now().strftime("%d.%m.%Y")
            try:
                datetime.strptime(new_value, "%d.%m.%Y")  # Проверка формата даты
                context.user_data["employment_date"] = new_value
                context.user_data["employment_step"] = "salary"
                await update.message.reply_text("Введите зарплату:")
                return WAIT_FOR_NEW_VALUE
            except ValueError:
                await update.message.reply_text("Некорректная дата. Попробуйте снова.")
                return WAIT_FOR_NEW_VALUE

        if employment_step == "salary":
            try:
                salary = int(new_value)
                if salary <= 0:
                    raise ValueError("Зарплата должна быть положительным числом.")

                context.user_data["salary"] = salary

                # Обновляем данные студента в базе
                update_student(
                    student.id,
                    {
                        "company": context.user_data["company_name"],
                        "employment_date": context.user_data["employment_date"],
                        "salary": context.user_data["salary"],
                        "training_status": "Устроился",  # Обновляем статус обучения
                    }
                )

                # Перечитываем студента из БД, чтобы рассчитать комиссию по актуальным данным
                updated_student = session.query(Student).get(student.id)
                context.user_data["student"] = updated_student
                # 💰 Создаём запись комиссии куратора в curator_commissions
                try:
                    commission_manager = AdminCommissionManager()
                    result_message = commission_manager.calculate_and_save_debts(session, updated_student.id)
                    # Логируем результат
                    print(f"Log Commission: {result_message}")
                except Exception as e:
                    # Не роняем бота, если что-то пошло не так с записью комиссии
                    print(f"Ошибка при создании записи комиссии куратора: {e}")
                session.commit()

                # 🛡️ ОБРАБОТКА СТРАХОВКИ ПРИ УСТРОЙСТВЕ СТУДЕНТА
                await process_insurance_on_employment(student.id)
                await update.message.reply_text(
                    f"Данные о трудоустройстве успешно обновлены:\n"
                    f"Компания: {context.user_data['company_name']}\n"
                    f"Дата устройства: {context.user_data['employment_date']}\n"
                    f"Зарплата: {context.user_data['salary']}\n"
                    f"Статус обучения: Устроился"
                )
                context.user_data.pop("employment_step", None)
                return await exit_to_main_menu(update, context)
            except ValueError:
                await update.message.reply_text(
                    "Некорректные данные о комиссии. Убедитесь, что формат: количество выплат, процент (например: 2, 55%)."
                )
                return WAIT_FOR_NEW_VALUE

    # Преобразуем название поля в имя столбца
    db_field = FIELD_MAPPING.get(field_to_edit)
    if not db_field:
        await update.message.reply_text("Некорректное поле для редактирования.")
        return WAIT_FOR_NEW_VALUE

    try:
        # Обработка специального случая для даты
        if field_to_edit == "Дата последнего звонка" and new_value.lower() == "сегодня":
            new_value = datetime.now().strftime("%d.%m.%Y")

        # Проверяем формат даты, если это поле с датой
        if db_field.endswith("_date"):
            datetime.strptime(new_value, "%d.%m.%Y")

        # Обработка поля "Сумма оплаты"
        if field_to_edit == "Сумма оплаты":
            try:
                additional_payment = int(new_value)
                if additional_payment < 0:
                    raise ValueError("Сумма не может быть отрицательной.")

                # Текущая сумма оплаты
                existing_payment = int(getattr(student, "payment_amount", 0))
                total_cost = int(getattr(student, "total_cost", 0))

                updated_payment = existing_payment + additional_payment

                # Проверяем, не превышает ли сумма оплат полную стоимость курса
                if updated_payment > total_cost:
                    await update.message.reply_text(
                        f"❌ Ошибка: общая сумма оплаты ({updated_payment}) превышает стоимость обучения ({total_cost})."
                    )
                    return WAIT_FOR_NEW_VALUE

                # Запрашиваем у пользователя дату платежа с кнопкой "Сегодня"
                reply_markup = ReplyKeyboardMarkup(
                    [["Сегодня"], ["Отмена"]],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )

                await update.message.reply_text(
                    "Введите дату платежа в формате ДД.ММ.ГГГГ или выберите 'Сегодня':",
                    reply_markup=reply_markup
                )

                # Сохраняем сумму платежа для обработки после выбора даты
                context.user_data["pending_payment"] = additional_payment
                return WAIT_FOR_PAYMENT_DATE  # Переход к следующему шагу

            except ValueError:
                await update.message.reply_text("Некорректная сумма. Введите числовое значение.")
                return WAIT_FOR_NEW_VALUE

        # Получаем старое значение
        old_value = getattr(student, db_field, None)

        # Обновляем данные
        update_student(student.id, {db_field: new_value})

        # 🛡️ ОБРАБОТКА СТРАХОВКИ ПРИ ИЗМЕНЕНИИ СТАТУСА ОБУЧЕНИЯ
        if field_to_edit == "Статус обучения" and new_value == "Получил 5 модуль":
            # Начисляем страховку куратору за получение 5 модуля
            if student.training_type == "Ручное тестирование" and student.mentor_id:
                from config import Config
                if Config.CURATOR_INSURANCE_ENABLED:
                    await award_insurance_for_module_5(student.id, student.mentor_id)
                else:
                    print("🛡️ Страховочные выплаты для кураторов отключены")
        
        # 💰 ОСВОБОЖДЕНИЕ ХОЛДИРОВАНИЯ ПРИ ОТЧИСЛЕНИИ СТУДЕНТА
        if field_to_edit == "Статус обучения" and new_value == "Отчислен":
            from config import Config
            if Config.HELD_AMOUNTS_ENABLED:
                from data_base.models import HeldAmount
                from datetime import date
                import logging
                
                # Настраиваем логгер для холдирования
                held_logger = logging.getLogger('held_amounts')
                held_logger.setLevel(logging.INFO)
                # Проверяем, есть ли уже обработчик
                if not held_logger.handlers:
                    held_file_handler = logging.FileHandler('held_amounts.log', encoding='utf-8')
                    held_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                    held_logger.addHandler(held_file_handler)
                
                try:
                    # Освобождаем все активные холдирования для этого студента
                    held_amounts = session.query(HeldAmount).filter(
                        HeldAmount.student_id == student.id,
                        HeldAmount.status == "active"
                    ).all()
                    
                    if held_amounts:
                        total_released = 0.0
                        for held in held_amounts:
                            released_amount = float(held.held_amount)  # Текущее холдирование
                            held.status = "released"
                            held.held_amount = 0.0
                            held.updated_at = date.today()
                            total_released += released_amount
                            
                            held_logger.info(f"🔓 Освобождено холдирование: Студент {student.fio} (ID {student.id}) | "
                                            f"Направление: {held.direction} | "
                                            f"Освобождено: {released_amount} руб.")
                        
                        session.commit()
                        print(f"💰 Освобождено холдирование для студента {student.fio}: {round(total_released, 2)} руб.")
                except Exception as e:
                    print(f"❌ Ошибка при освобождении холдирования: {e}")
                    session.rollback()

        # Отправляем сообщение об успехе
        await update.message.reply_text(
            f"Поле '{field_to_edit}' успешно обновлено:\n"
            f"Старое значение: {old_value}\n"
            f"Новое значение: {new_value}"
        )
    except ValueError:
        await update.message.reply_text(
            "Неверный формат. Убедитесь, что данные введены корректно. Если это дата, используйте формат ДД.ММ.ГГГГ."
        )
        return WAIT_FOR_NEW_VALUE
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка при обновлении: {e}")

    return await exit_to_main_menu(update, context)

async def handle_payment_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод даты платежа, записывает платеж в `payments` и обновляет сумму оплат в `students`.
    """
    try:
        student = context.user_data.get("student")
        payment_date_str = update.message.text.strip()

        # Если пользователь выбрал "Сегодня", ставим текущую дату
        if payment_date_str.lower() == "сегодня":
            payment_date = datetime.now().date()
        else:
            payment_date = datetime.strptime(payment_date_str, "%d.%m.%Y").date()

        new_payment = context.user_data.pop("pending_payment", 0)

        # Текущие значения
        existing_payment = int(getattr(student, "payment_amount", 0))  # Уже оплаченная сумма
        total_cost = int(getattr(student, "total_cost", 0))  # Полная стоимость курса
        updated_payment = existing_payment + new_payment

        # Проверяем, не превышает ли сумма оплат полную стоимость курса
        if updated_payment > total_cost:
            await update.message.reply_text(
                f"❌ Ошибка: общая сумма оплаты ({updated_payment}) превышает стоимость обучения ({total_cost})."
            )
            await exit_to_main_menu(update, context)  # ✅ Отправляем в меню
            return ConversationHandler.END  # ✅ Завершаем процесс

        # ✅ Записываем новый платёж в `payments`
        mentor_id = student.mentor_id
        auto_mentor_id = getattr(student, 'auto_mentor_id', None)
        if student.training_type in ["Автотестирование", "Фуллстек"] and auto_mentor_id:
            mentor_id = auto_mentor_id
        new_payment_entry = Payment(
            student_id=student.id,
            mentor_id=mentor_id,
            amount=new_payment,
            payment_date=payment_date,
            comment="Дополнительный платёж через редактирование",
            status="подтвержден"
        )

        session.add(new_payment_entry)
        session.commit()

        # ✅ Обновляем сумму оплат в `students`
        student.payment_amount = existing_payment + new_payment
        student.fully_paid = "Да" if student.payment_amount >= total_cost else "Нет"
        session.commit()

        await update.message.reply_text(
            f"✅ Платёж {new_payment} руб. успешно добавлен за {payment_date.strftime('%d.%m.%Y')}.\n"
            f"💳 Общая сумма оплаты: {student.payment_amount} руб. из {total_cost} руб.\n"
            f"💰 Остаток к оплате: {max(0, total_cost - student.payment_amount)} руб."
        )

        await exit_to_main_menu(update, context)  # ✅ Гарантированно отправляем в меню
        return ConversationHandler.END  # ✅ Завершаем процесс корректно

    except ValueError:
        await update.message.reply_text("Некорректный формат даты. Введите в формате ДД.ММ.ГГГГ или выберите 'Сегодня'.")
        return WAIT_FOR_PAYMENT_DATE
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при записи платежа: {e}")
        return WAIT_FOR_PAYMENT_DATE

async def start_contract_signing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите Telegram ученика, чтобы отметить договор как подписанный:")
    return SIGN_CONTRACT


async def handle_contract_signing(update, context):
    telegram_input = update.message.text.strip()
    if telegram_input.startswith("@"):
        telegram_input = telegram_input[1:]
    # Проверка наличия студентов
    student = session.query(Student).filter(Student.telegram.ilike(f"%{telegram_input}%")).first()

    if not student:
        print("❌ Студент не найден.")
        await update.message.reply_text("Студент не найден.")
        return SIGN_CONTRACT
    student.contract_signed = True
    session.commit()

    await update.message.reply_text(f"✅ Договор для {student.fio} отмечен как подписанный.")
    return await exit_to_main_menu(update, context)

# Умная функция для определения прав редактирования
async def smart_edit_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Умная функция, которая определяет права пользователя и выбирает соответствующий обработчик.
    """
    user_id = update.message.from_user.id
    
    if user_id in AUTHORIZED_USERS:
        # Полные права - используем обычное редактирование
        return await edit_student(update, context)
    elif user_id in NOT_ADMINS:
        # Ограниченные права - используем ограниченное редактирование
        return await edit_student_limited(update, context)
    else:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return ConversationHandler.END

# Умная функция для определения прав редактирования полей
async def smart_edit_student_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Умная функция для редактирования полей в зависимости от прав пользователя.
    """
    user_id = update.message.from_user.id
    
    if user_id in AUTHORIZED_USERS:
        # Полные права - используем обычное редактирование полей
        return await edit_student_field(update, context)
    elif user_id in NOT_ADMINS:
        # Ограниченные права - используем ограниченное редактирование полей
        return await edit_student_field_limited(update, context)
    else:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return ConversationHandler.END


async def process_insurance_on_employment(student_id: int):
    """
    Обрабатывает страховку при устройстве студента на работу.
    Списывает активные страховки кураторов за этого студента.
    """
    try:
        from datetime import date

        # Получаем активные страховки за этого студента
        active_insurance = session.query(CuratorInsuranceBalance).filter(
            CuratorInsuranceBalance.student_id == student_id,
            CuratorInsuranceBalance.is_active == True
        ).all()

        if not active_insurance:
            return  # Нет активных страховок

        # Деактивируем все страховки за этого студента
        for insurance in active_insurance:
            insurance.is_active = False

        session.commit()

        # Логируем списание страховки
        total_amount = sum(float(ins.insurance_amount) for ins in active_insurance)
        print(f"🛡️ Страховка списана при устройстве студента {student_id}: {total_amount} руб.")

    except Exception as e:
        print(f"❌ Ошибка при обработке страховки при устройстве: {e}")
        session.rollback()


async def award_insurance_for_module_5(student_id: int, curator_id: int):
    """
    Начисляет страховку куратору за студента, получившего 5 модуль.
    Теперь проверяет дату получения 5 модуля из таблицы успеваемости.
    """
    try:
        from datetime import date
        from config import Config
        
        # Проверяем, включены ли страховочные выплаты для кураторов
        if not Config.CURATOR_INSURANCE_ENABLED:
            print("🛡️ Страховочные выплаты для кураторов отключены")
            return

        # Проверяем, что студент учится на ручном тестировании
        student = session.query(Student).filter(Student.id == student_id).first()
        if not student or student.training_type != "Ручное тестирование":
            return  # Не подходящий тип обучения

        # Проверяем, что куратор существует
        curator = session.query(Mentor).filter(
            Mentor.id == curator_id,
            Mentor.direction == "Ручное тестирование"
        ).first()
        if not curator:
            return  # Куратор не найден или неактивен

        # Проверяем, нет ли уже активной страховки за этого студента
        existing_insurance = session.query(CuratorInsuranceBalance).filter(
            CuratorInsuranceBalance.student_id == student_id,
            CuratorInsuranceBalance.is_active == True
        ).first()

        if existing_insurance:
            return  # Страховка уже начислена

        # 🔍 ПРОВЕРЯЕМ ДАТУ ПОЛУЧЕНИЯ 5 МОДУЛЯ ИЗ ТАБЛИЦЫ MANUAL_PROGRESS
        module_5_date = None

        # Получаем прогресс студента из таблицы manual_progress
        progress = session.query(ManualProgress).filter(
            ManualProgress.student_id == student_id
        ).first()

        if progress and progress.m5_start_date:
            module_5_date = progress.m5_start_date
        else:
            # Если дата не найдена в manual_progress, используем текущую дату
            module_5_date = date.today()

        # Создаем новую страховку
        insurance = CuratorInsuranceBalance(
            curator_id=curator_id,
            student_id=student_id,
            insurance_amount=5000.00,
            created_at=module_5_date,
            is_active=True
        )

        session.add(insurance)
        session.commit()

        print(f"🛡️ Начислена страховка куратору {curator_id} за студента {student_id}: 5000 руб. (дата 5 модуля: {module_5_date})")

    except Exception as e:
        print(f"❌ Ошибка при начислении страховки: {e}")
        session.rollback()


async def edit_curator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Редактирование куратора студента.
    """
    student = context.user_data.get("student")

    if not student:
        await update.message.reply_text("❌ Студент не найден.")
        return ConversationHandler.END

    # Определяем тип обучения и показываем соответствующие опции
    if student.training_type == "Ручное тестирование":
        await update.message.reply_text(
            f"Редактирование ручного куратора для студента {student.fio}",
            reply_markup=ReplyKeyboardMarkup(
                [["Изменить ручного куратора"], ["Главное меню"]],
                one_time_keyboard=True
            )
        )
        context.user_data["curator_type"] = "manual"
        return SELECT_CURATOR_TYPE

    elif student.training_type == "Автотестирование":
        await update.message.reply_text(
            f"Редактирование авто куратора для студента {student.fio}",
            reply_markup=ReplyKeyboardMarkup(
                [["Изменить авто куратора"], ["Главное меню"]],
                one_time_keyboard=True
            )
        )
        context.user_data["curator_type"] = "auto"
        return SELECT_CURATOR_TYPE

    elif student.training_type == "Фуллстек":
        await update.message.reply_text(
            f"Редактирование кураторов для фуллстек студента {student.fio}",
            reply_markup=ReplyKeyboardMarkup(
                [["Изменить ручного куратора"], ["Изменить авто куратора"], ["Главное меню"]],
                one_time_keyboard=True
            )
        )
        return SELECT_CURATOR_TYPE

    else:
        await update.message.reply_text("❌ Неизвестный тип обучения.")
        return ConversationHandler.END


async def handle_curator_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка выбора типа куратора для редактирования.
    """
    selected = update.message.text.strip()

    # Обработка кнопки "Главное меню"
    if selected == "Главное меню":
        return await exit_to_main_menu(update, context)

    student = context.user_data.get("student")

    if selected == "Изменить ручного куратора":
        context.user_data["curator_type"] = "manual"
        return await show_curator_mentors(update, context, "Ручное тестирование")
    elif selected == "Изменить авто куратора":
        context.user_data["curator_type"] = "auto"
        return await show_curator_mentors(update, context, "Автотестирование")
    else:
        await update.message.reply_text("❌ Пожалуйста, выберите один из предложенных вариантов.")
        return SELECT_CURATOR_TYPE


async def show_curator_mentors(update: Update, context: ContextTypes.DEFAULT_TYPE, direction: str):
    """
    Показывает список менторов для выбора куратора.
    """
    from data_base.models import Mentor

    mentors = session.query(Mentor).filter(Mentor.direction == direction).all()
    if not mentors:
        await update.message.reply_text(f"❌ Нет менторов для направления {direction}.")
        return ConversationHandler.END

    mentors_list = {m.full_name: m.id for m in mentors}
    # Добавляем опцию "Не назначен"
    mentors_list["Не назначен"] = None

    context.user_data["mentors_list"] = mentors_list

    await update.message.reply_text(
        f"Выберите нового куратора для направления {direction}:",
        reply_markup=ReplyKeyboardMarkup(
            [[name] for name in mentors_list.keys()] + [["Главное меню"]],
            one_time_keyboard=True
        )
    )
    return SELECT_CURATOR_MENTOR


async def handle_curator_mentor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка выбора нового куратора.
    """
    selected = update.message.text.strip()
    mentors_list = context.user_data.get("mentors_list", {})

    # Обработка кнопки "Главное меню"
    if selected == "Главное меню":
        return await exit_to_main_menu(update, context)

    if selected not in mentors_list:
        await update.message.reply_text("❌ Пожалуйста, выберите одного из предложенных.")
        return SELECT_CURATOR_MENTOR

    student = context.user_data.get("student")
    curator_type = context.user_data.get("curator_type")
    new_mentor_id = mentors_list[selected]

    # Обновляем куратора в базе данных
    try:
        if curator_type == "manual":
            student.mentor_id = new_mentor_id
        elif curator_type == "auto":
            student.auto_mentor_id = new_mentor_id

        session.commit()

        mentor_name = selected if selected != "Не назначен" else "Не назначен"
        await update.message.reply_text(
            f"✅ Куратор успешно изменен!\n"
            f"Студент: {student.fio}\n"
            f"Новый куратор: {mentor_name}"
        )

        # Возвращаемся в главное меню после успешного обновления
        return await exit_to_main_menu(update, context)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при обновлении куратора: {str(e)}")
        return await exit_to_main_menu(update, context)
