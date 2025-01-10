from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from commands.authorized_users import AUTHORIZED_USERS
from commands.logger import log_student_change
from commands.start_commands import exit_to_main_menu
from commands.states import FIELD_TO_EDIT, WAIT_FOR_NEW_VALUE, FIO_OR_TELEGRAM
from commands.student_info_commands import calculate_commission
from data_base.db import session
from data_base.models import Student
from data_base.operations import get_all_students, update_student, get_student_by_fio_or_telegram


async def view_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает список студентов.
    """
    students = get_all_students()
    if not students:
        await update.message.reply_text("Список студентов пуст. Добавьте студентов через меню.")
        return

    response = "Список студентов:\n"
    for i, student in enumerate(students, start=1):
        response += f"{i}. {student.fio} - {student.telegram} ({student.training_type})\n"
    await update.message.reply_text(response)


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


# Редактирование поля студента
async def edit_student_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return

    FIELD_MAPPING = {
        "ФИО": "fio",
        "Telegram": "telegram",
        "Дата последнего звонка": "last_call_date",
        "Сумма оплаты": "payment_amount",
        "Статус обучения": "training_status",
        "Получил работу": "company",
        "Комиссия выплачено": "commission_paid"
    }

    field_to_edit = update.message.text.strip()
    student = context.user_data.get("student")

    # Универсальная обработка кнопки "Назад"
    if field_to_edit == "Назад":
        await update.message.reply_text(
            "Возврат в главное меню:",
            reply_markup=ReplyKeyboardMarkup(
                [["Добавить студента", "Просмотреть студентов"],
                 ["Редактировать данные студента", "Проверить уведомления"]],
                one_time_keyboard=True
            )
        )
        return ConversationHandler.END

    if field_to_edit == "Получил работу":
        # Уникальная обработка для "Получил работу"
        context.user_data["field_to_edit"] = field_to_edit
        context.user_data["employment_step"] = "company"
        await update.message.reply_text("Введите название компании:")
        return WAIT_FOR_NEW_VALUE

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
                    [["Не учится", "Учится", "Устроился"], ["Назад"]],
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
            [["ФИО", "Telegram", "Дата последнего звонка", "Сумма оплаты",
              "Статус обучения", "Получил работу", "Комиссия выплачено"],
             ["Назад"]],
            one_time_keyboard=True
        )
    )
    return FIELD_TO_EDIT


async def handle_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime

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
                context.user_data["employment_step"] = "commission"
                await update.message.reply_text(
                    "Введите данные о комиссии в формате: количество выплат, процент (например: 2, 50%):"
                )
                return WAIT_FOR_NEW_VALUE
            except ValueError:
                await update.message.reply_text("Некорректная зарплата. Введите положительное число.")
                return WAIT_FOR_NEW_VALUE

        if employment_step == "commission":
            try:
                payments, percentage = map(str.strip, new_value.split(","))
                payments = int(payments)
                percentage = int(percentage.strip('%'))
                if payments <= 0 or percentage <= 0:
                    raise ValueError("Количество выплат и процент должны быть положительными числами.")
                commission = f"{payments}, {percentage}%"
                update_student(
                    student.id,
                    {
                        "company": context.user_data["company_name"],
                        "employment_date": context.user_data["employment_date"],
                        "salary": context.user_data["salary"],
                        "commission": commission,
                        "training_status": "Устроился"  # Обновляем статус обучения
                    }
                )
                await update.message.reply_text(
                    f"Данные о трудоустройстве успешно обновлены:\n"
                    f"Компания: {context.user_data['company_name']}\n"
                    f"Дата устройства: {context.user_data['employment_date']}\n"
                    f"Зарплата: {context.user_data['salary']}\n"
                    f"Комиссия: {commission}\n"
                    f"Статус обучения: Устроился"
                )
                context.user_data.pop("employment_step", None)
                return await exit_to_main_menu(update, context)
            except ValueError:
                await update.message.reply_text(
                    "Некорректные данные о комиссии. Убедитесь, что формат: количество выплат, процент (например: 2, 50%)."
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
                fully_paid = "Да" if updated_payment == total_cost else "Нет"


                # Суммируем и проверяем
                updated_payment = existing_payment + additional_payment
                if updated_payment > total_cost:
                    await update.message.reply_text(
                        f"Ошибка: общая сумма оплаты ({updated_payment}) превышает стоимость обучения ({total_cost})."
                    )
                    return WAIT_FOR_NEW_VALUE

                # Обновляем данные
                update_student(student.id, {
                    "payment_amount": updated_payment,
                    "fully_paid": fully_paid
                })

                await update.message.reply_text(
                    f"Сумма оплаты успешно обновлена: {existing_payment} ➡ {updated_payment}."
                )
                return await exit_to_main_menu(update, context)
            except ValueError:
                await update.message.reply_text("Некорректная сумма. Введите числовое значение.")
                return WAIT_FOR_NEW_VALUE

        # Получаем старое значение
        old_value = getattr(student, db_field, None)

        # Обновляем данные
        update_student(student.id, {db_field: new_value})

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
