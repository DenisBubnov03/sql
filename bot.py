import tracemalloc
import os
import tracemalloc
import json
from pathlib import Path
import psycopg2
from dotenv import load_dotenv
from telegram import CallbackQuery
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from bot.handlers.career_consultant_handlers import show_career_consultant_statistics, \
    show_assign_student_menu, handle_student_selection, handle_assignment_confirmation, career_consultant_start
from commands.additional_expenses_commands import start_expense_process, handle_expense_type, handle_expense_amount, \
    handle_expense_date, handle_sub_category
from commands.career_consultant_commands import add_career_consultant_handler
from commands.contract_commands import (
    start_contract_formation, handle_contract_menu, handle_student_telegram,
    handle_contract_type, handle_advance_amount, handle_payment_type, handle_months,
    handle_commission_type, handle_commission_custom, handle_fio, handle_address,
    handle_inn, handle_rs, handle_ks, handle_bank, handle_bik, handle_email
)
from commands.create_meeting import create_meeting_entry, select_meeting_type
from commands.mentor_bonus_commands import start_bonus_process, handle_mentor_tg, handle_bonus_amount
from commands.start_commands import start
from commands.states import NOTIFICATION_MENU, PAYMENT_NOTIFICATION_MENU, STATISTICS_MENU, START_PERIOD, END_PERIOD, \
    COURSE_TYPE_MENU, \
    CONFIRM_DELETE, WAIT_FOR_PAYMENT_DATE, AWAIT_MENTOR_TG, AWAIT_BONUS_AMOUNT, \
    EXPENSE_TYPE, EXPENSE_AMOUNT, EXPENSE_DATE, SIGN_CONTRACT, FIELD_TO_EDIT, SELECT_STUDENT, \
    WAIT_FOR_NEW_VALUE, \
    CONFIRM_ASSIGNMENT, WAIT_FOR_DETAILED_SALARY, SELECT_CURATOR_TYPE, SELECT_CURATOR_MENTOR, \
    CONTRACT_MENU, CONTRACT_STUDENT_TG, CONTRACT_TYPE, \
    CONTRACT_ADVANCE_AMOUNT, CONTRACT_PAYMENT_TYPE, CONTRACT_MONTHS, CONTRACT_COMMISSION_TYPE, \
    CONTRACT_COMMISSION_CUSTOM, CONTRACT_FIO, CONTRACT_ADDRESS, CONTRACT_INN, CONTRACT_RS, CONTRACT_KS, \
    CONTRACT_BANK, CONTRACT_BIK, CONTRACT_EMAIL, MEETING_TYPE_SELECTION, UE_MENU, UE_START_PERIOD, UE_END_PERIOD, \
    EXPENSE_SUB_CATEGORY
from commands.student_commands import (
    handle_student_deletion, handle_new_value,
    handle_payment_date, start_contract_signing, handle_contract_signing,
    smart_edit_student, smart_edit_student_field, handle_curator_type_selection, handle_curator_mentor_selection,
    confirm_refund_callback
)
from commands.student_info_commands import *
from commands.student_management_command import *
from commands.student_management_command import handle_detailed_salary_request
from commands.student_notifications import check_call_notifications, check_payment_notifications, \
    check_prepayment_notifications, check_postpayment_notifications, check_all_notifications, show_notifications_menu
from commands.student_selection import find_student, handle_multiple_students
from commands.student_statistic_commands import show_statistics_menu, show_general_statistics, show_course_type_menu, \
    show_manual_testing_statistics, show_automation_testing_statistics, show_fullstack_statistics, request_period_start, \
    handle_period_start, handle_period_end, show_held_amounts
from commands.unit_economics_commands import (
    show_unit_economics_menu,
    show_latest_unit_economics,
    unit_economics_request_start,
    unit_economics_handle_start,
    unit_economics_handle_end,
    # unit_economics_handle_product_code,
    unit_economics_back_to_statistics,
    unit_economics_command,
)
from data_base.db import DATABASE_URL
from utils.notification import _director_ids_for_training_type, load_state, save_state, bot, \
    get_director_chat_id_from_db

load_dotenv()
tracemalloc.start()
# Токен Telegram-бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


async def handle_student_inactivity_buttons(update, context):
    query = update.callback_query
    action, student_id_raw = query.data.split(":")
    student_id_str = str(student_id_raw)
    await query.answer()

    # Получаем данные куратора, который нажал кнопку
    curator = update.effective_user
    curator_tg = f"@{curator.username}" if curator.username else f"ID: {curator.id}"

    base_dir = Path(__file__).resolve().parent
    json_path = base_dir / "utils" / "notification_state.json"

    if action in ["set_inactive", "drop_student"]:
        try:
            db_url = os.getenv("DATABASE_URL")
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    # 1. Добавляем s.telegram в запрос
                    cur.execute("SELECT fio, training_type, telegram FROM students WHERE id = %s",
                                (int(student_id_raw),))
                    student_data = cur.fetchone()

                    if student_data:
                        s_name, t_type, s_tg = student_data  # s_tg — это ТГ ученика

                        cur.execute(
                            "UPDATE students SET training_status = 'Не учится' WHERE id = %s",
                            (int(student_id_raw),)
                        )
                        conn.commit()

                        # 2. Формируем расширенное сообщение для директора
                        for d_id in _director_ids_for_training_type(t_type):
                            d_chat = get_director_chat_id_from_db(d_id)
                            if d_chat:
                                msg = (
                                    f"📉 <b>СТАТУС ИЗМЕНЕН</b>\n\n"
                                    f"👤 Студент: <b>{s_name}</b> ({s_tg})\n"
                                    f"👨‍🏫 Куратор: <b>{curator_tg}</b>\n"
                                    f"📚 Направление: {t_type}\n"
                                    f"📝 Действие: Отчисление за неактивность"
                                )
                                await context.bot.send_message(chat_id=d_chat, text=msg, parse_mode="HTML")

            # Удаление из JSON (стейта)
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                if student_id_str in state:
                    del state[student_id_str]
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(state, f, ensure_ascii=False, indent=4)

            await query.edit_message_text(text=f"✅ Статус ученика {s_name} изменен. Руководство уведомлено.")

        except Exception as e:
            print(f"❌ ОШИБКА при отчислении: {e}")
            await query.edit_message_text(text="⚠️ Ошибка при обновлении данных.")

    # --- 2. ПАУЗА (keep_active) ---
    elif action == "keep_active":
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                state = json.load(f)

            if student_id_str in state:
                state[student_id_str]["active_hold"] = True
                state[student_id_str]["last_notified"] = str(date.today())
                state[student_id_str].pop("slow_progress", None)

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=4)

                await query.edit_message_text(
                    text="✅ Принято! Пауза 2 недели. Если созвона не будет, я вернусь с проверкой позже."
                )

    # --- 3. МЕДЛЕННЫЙ ПРОГРЕСС (slow_progress) ---
    elif action == "slow_progress":
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                state = json.load(f)

            if student_id_str in state:
                state[student_id_str]["slow_progress"] = True
                state[student_id_str]["last_notified"] = str(date.today())

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=4)

                await query.edit_message_text(
                    text="⏳ Статус 'Долго учится' установлен. Уведомления будут приходить раз в неделю."
                )
def main():
    # Создание приложения Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработчик добавления студента
    add_student_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Добавить студента$"), add_student_start)],
        states={
            FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_fio)],
            TELEGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_telegram)],
            START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_date)],
            COURSE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_course_type)],
            SELECT_MENTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mentor_selection)],
            TOTAL_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_total_payment)],
            PAID_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_paid_amount)],
            IS_REFERRAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_is_referral)],
            REFERRER_TELEGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_referrer_telegram)],
            STUDENT_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_source)],

        },
        fallbacks=[],
    )

    # Обработчик редактирования студента (умный - для всех пользователей)
    edit_student_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Редактировать данные студента$"), smart_edit_student)],
        states={
            FIO_OR_TELEGRAM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, find_student),
                MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)
            ],
            SELECT_STUDENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_multiple_students),
                MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)
            ],
            FIELD_TO_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, smart_edit_student_field),
                MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)
            ],
            WAIT_FOR_NEW_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_value),
                MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)
            ],
            CONFIRM_DELETE: [  # Добавляем состояние для подтверждения удаления
                MessageHandler(filters.Regex("^(Да, удалить|Нет, отмена)$"), handle_student_deletion),
            ],
            WAIT_FOR_PAYMENT_DATE: [  # Добавляем этот шаг
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_date),
                MessageHandler(filters.Regex("^Сегодня$"), handle_payment_date),  # Кнопка "Сегодня"
            ],
            SELECT_CURATOR_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_curator_type_selection),
                MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)
            ],
            SELECT_CURATOR_MENTOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_curator_mentor_selection),
                MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)
            ]
        },
        fallbacks=[MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)]
    )

    search_student_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Поиск ученика$"), search_student)],
        states={
            FIO_OR_TELEGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, display_student_info)],
        },
        fallbacks=[],
    )

    statistics_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Статистика$"), show_statistics_menu)],
        states={
            STATISTICS_MENU: [
                MessageHandler(filters.Regex("^📈 Общая статистика$"), show_general_statistics),
                MessageHandler(filters.Regex("^📚 По типу обучения$"), show_course_type_menu),
                MessageHandler(filters.Regex("^📅 По периоду$"), request_period_start),
                MessageHandler(filters.Regex("^💰 Холдирование$"), show_held_amounts),
                MessageHandler(filters.Regex("^💹 Юнит экономика$"), show_unit_economics_menu),
            ],
            START_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_period_start)],
            END_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_period_end)],
            UE_MENU: [
                MessageHandler(filters.Regex("^📌 Последний период$"), show_latest_unit_economics),
                MessageHandler(filters.Regex("^📅 Выбрать период$"), unit_economics_request_start),
                MessageHandler(filters.Regex("^🔙 Назад$"), unit_economics_back_to_statistics),
            ],
            UE_START_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, unit_economics_handle_start)],
            UE_END_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, unit_economics_handle_end)],
            # UE_PRODUCT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, unit_economics_handle_product_code)],
            COURSE_TYPE_MENU: [
                MessageHandler(filters.Regex("^👨‍💻 Ручное тестирование$"), show_manual_testing_statistics),
                MessageHandler(filters.Regex("^🤖 Автотестирование$"), show_automation_testing_statistics),
                MessageHandler(filters.Regex("^💻 Фуллстек$"), show_fullstack_statistics),
                MessageHandler(filters.Regex("^🔙 Назад$"), show_statistics_menu),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🔙 Вернуться в меню$"), exit_to_main_menu),
        ],
    )

    notifications_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Проверить уведомления$"), show_notifications_menu)],
        states={
            NOTIFICATION_MENU: [
                MessageHandler(filters.Regex("^По звонкам$"), check_call_notifications),
                MessageHandler(filters.Regex("^По оплате$"), check_payment_notifications),
                MessageHandler(filters.Regex("^Все$"), check_all_notifications),
            ],
            PAYMENT_NOTIFICATION_MENU: [
                MessageHandler(filters.Regex("^По предоплате$"), check_prepayment_notifications),
                MessageHandler(filters.Regex("^По постоплате$"), check_postpayment_notifications),
                MessageHandler(filters.Regex("^🔙 Назад$"), show_notifications_menu),
            ],
            "NOTIFICATION_PROCESS": [
                MessageHandler(filters.Regex("^🔙 Назад$"), show_notifications_menu),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🔙 Главное меню$"), exit_to_main_menu),
        ],
    )
    salary_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 Рассчитать зарплату$"), request_salary_period)],
        states={
            "WAIT_FOR_SALARY_DATES": [MessageHandler(filters.TEXT & ~filters.COMMAND, calculate_salary)],
            WAIT_FOR_DETAILED_SALARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_detailed_salary_request)],
            "SALARY_MAIN_MENU": [MessageHandler(filters.TEXT, handle_salary_main_menu)],
            "SALARY_DETAIL_SELECT": [MessageHandler(filters.TEXT, handle_detail_selection)],
            "SALARY_PAY_SELECT": [MessageHandler(filters.TEXT, handle_payment_selection)],
            "SALARY_CONFIRM_PAY": [MessageHandler(filters.TEXT, confirm_payout)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙 Главное меню$"), exit_to_main_menu)]
    )



    bonus_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Премия куратору$"), start_bonus_process)],
        states={
            AWAIT_MENTOR_TG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mentor_tg)],
            AWAIT_BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bonus_amount)],
        },
        fallbacks=[MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)],
    )
    contract_signing_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Подписание договора$"), start_contract_signing)],
        states={
            SIGN_CONTRACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contract_signing)],
        },
        fallbacks=[],
    )
    
    # Обработчик формирования договоров
    contract_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Договор$"), start_contract_formation)],
        states={
            CONTRACT_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contract_menu)],
            CONTRACT_STUDENT_TG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_student_telegram)],
            CONTRACT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contract_type)],
            CONTRACT_ADVANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_advance_amount)],
            CONTRACT_PAYMENT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_type)],
            CONTRACT_MONTHS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_months)],
            CONTRACT_COMMISSION_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_commission_type)],
            CONTRACT_COMMISSION_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_commission_custom)],
            CONTRACT_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_fio)],
            CONTRACT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address)],
            CONTRACT_INN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inn)],
            CONTRACT_RS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rs)],
            CONTRACT_KS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ks)],
            CONTRACT_BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank)],
            CONTRACT_BIK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bik)],
            CONTRACT_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🔙 Отмена$"), exit_to_main_menu),
            MessageHandler(filters.Regex("^🔙 Главное меню$"), exit_to_main_menu),
        ],
    )
    
    # Обработчик доп расходов
    expense_conv = ConversationHandler(
        # Добавил ^ и 💸 для соответствия кнопке
        entry_points=[MessageHandler(filters.Regex("^Доп расходы$"), start_expense_process)],
        states={
            EXPENSE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense_type)],
            EXPENSE_SUB_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sub_category)],
            EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense_amount)],
            EXPENSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense_date)],
        },
        fallbacks=[CommandHandler("cancel", exit_to_main_menu),
                   MessageHandler(filters.Regex("^🔙 Отмена$"), exit_to_main_menu)]
    )
    
    # Обработчик карьерных консультантов
    career_consultant_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔗 Закрепить КК$"), show_assign_student_menu)],
        states={
            SELECT_STUDENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_student_selection)],
            CONFIRM_ASSIGNMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_assignment_confirmation)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙 Назад$"), exit_to_main_menu)],
    )
    create_meeting_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📹 Создание встречи$"), create_meeting_entry)],
        states={
            MEETING_TYPE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_meeting_type)]
        },
        fallbacks=[]
    )
    application.add_handler(create_meeting_handler)
    # application.add_handler(
    #     CallbackQueryHandler(handle_student_inactivity_buttons, pattern="^(set_inactive|keep_active|slow_progress):")
    # )
    application.add_handler(
        CallbackQueryHandler(handle_student_inactivity_buttons, pattern="^(set_inactive|keep_active|drop_student):"))
    application.add_handler(contract_signing_handler)
    application.add_handler(contract_handler)
    application.add_handler(bonus_handler)
    application.add_handler(expense_conv)
    application.add_handler(CallbackQueryHandler(confirm_refund_callback, pattern="^conf_ref_"))
    # Обработчики карьерных консультантов
    application.add_handler(MessageHandler(filters.Regex("^📊 Моя статистика$"), show_career_consultant_statistics))
    application.add_handler(MessageHandler(filters.Regex("^💼 Карьерный консультант$"), career_consultant_start))
    application.add_handler(MessageHandler(filters.Regex("^🔙 Назад$"), exit_to_main_menu))
    application.add_handler(career_consultant_handler)
    # Обработчики управления карьерными консультантами
    application.add_handler(add_career_consultant_handler)
    application.add_handler(MessageHandler(filters.Regex("^🔙 Главное меню$"), exit_to_main_menu))
    # Регистрация обработчиков
    application.add_handler(salary_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("unit_economics", unit_economics_command))
    application.add_handler(add_student_handler)
    application.add_handler(edit_student_handler)
    application.add_handler(search_student_handler)
    application.add_handler(statistics_handler)
    application.add_handler(notifications_handler)

    # application.add_handler(MessageHandler(filters.Regex("Отмена"), cancel))  # Доп. проверка
    # application.add_handler(MessageHandler(filters.ALL, debug))

    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    main()
