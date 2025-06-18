import os

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from commands.mentor_bonus_commands import start_bonus_process, handle_mentor_tg, handle_bonus_amount
from commands.start_commands import start, exit_to_main_menu
from commands.states import NOTIFICATION_MENU, STATISTICS_MENU, START_PERIOD, END_PERIOD, COURSE_TYPE_MENU, \
    CONFIRM_DELETE, WAIT_FOR_PAYMENT_DATE, SELECT_MENTOR, AWAIT_MENTOR_TG, AWAIT_BONUS_AMOUNT
from commands.student_commands import *
from commands.student_employment_commands import *
from commands.student_info_commands import *
from commands.student_management_command import *
from commands.student_notifications import check_call_notifications, check_payment_notifications, \
    check_all_notifications, show_notifications_menu
from commands.student_selection import *
from commands.student_statistic_commands import show_statistics_menu, show_general_statistics, show_course_type_menu, \
    show_manual_testing_statistics, show_automation_testing_statistics, show_fullstack_statistics, request_period_start, \
    handle_period_start, handle_period_end

# Токен Telegram-бота
TELEGRAM_TOKEN = "6106505792:AAE7mlAus0SiuqKFVjHWaK8sOhe9i_6k0xQ"


# Состояния для ConversationHandler
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
            COMMISSION: [MessageHandler(filters.TEXT, add_student_commission)],
        },
        fallbacks=[],
    )

    # Обработчик редактирования студента
    edit_student_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Редактировать данные студента$"), edit_student)],
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_student_field),
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
            ],
            START_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_period_start)],
            END_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_period_end)],
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
            "WAIT_FOR_SALARY_DATES": [MessageHandler(filters.TEXT & ~filters.COMMAND, calculate_salary)]
        },
        fallbacks=[]
    )

    bonus_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Премия куратору$"), start_bonus_process)],
        states={
            AWAIT_MENTOR_TG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mentor_tg)],
            AWAIT_BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bonus_amount)],
        },
        fallbacks=[MessageHandler(filters.Regex("^Главное меню$"), exit_to_main_menu)],
    )
    application.add_handler(bonus_handler)

    # Регистрация обработчиков
    application.add_handler(salary_handler)
    application.add_handler(CommandHandler("start", start))
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
