import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler

# Импорт ваших остальных команд и настроек
from commands.start_commands import start, exit_to_main_menu
from commands.states import NOTIFICATION_MENU
from commands.student_commands import *
from commands.student_employment_commands import *
from commands.student_info_commands import *
from commands.student_management_command import *
from commands.student_notifications import (
    check_call_notifications, 
    check_payment_notifications, 
    check_all_notifications, 
    show_notifications_menu
)
from commands.student_selection import *
from commands.student_statistic_commands import (
    show_statistics_menu, 
    show_general_statistics, 
    show_course_type_menu, 
    show_manual_testing_statistics, 
    show_automation_testing_statistics, 
    show_fullstack_statistics
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
print("TELEGRAM_TOKEN:", TELEGRAM_TOKEN)

WEBHOOK_URL = f"https://my-telegram-bot.onrender.com/webhook"  # Ваш реальный домен от Render

app = Flask(__name__)

@app.route("/")
def home():
    return "Telegram Bot is Running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    application.update_queue.put(update)
    return "OK", 200

def create_application():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    add_student_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Добавить студента$"), add_student_start)],
        states={
            FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_fio)],
            TELEGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_telegram)],
            START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_date)],
            COURSE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_course_type)],
            TOTAL_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_total_payment)],
            PAID_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_paid_amount)],
            COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_commission)],
        },
        fallbacks=[],
    )

    edit_student_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Редактировать данные студента$"), edit_student)],
        states={
            FIO_OR_TELEGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, find_student)],
            SELECT_STUDENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_multiple_students)],
            FIELD_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_student_field)],
            WAIT_FOR_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_value)],
            "COMPANY_NAME": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_company_name)],
            "SALARY": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_salary)],
            "COMMISSION": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_commission)],
            "CONFIRMATION": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_employment_confirmation)],
        },
        fallbacks=[],
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
            "STATISTICS_MENU": [
                MessageHandler(filters.Regex("^📈 Общая статистика$"), show_general_statistics),
                MessageHandler(filters.Regex("^📚 По типу обучения$"), show_course_type_menu),
            ],
            "COURSE_TYPE_MENU": [
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

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^Просмотреть студентов$"), view_students))
    application.add_handler(add_student_handler)
    application.add_handler(edit_student_handler)
    application.add_handler(search_student_handler)
    application.add_handler(statistics_handler)
    application.add_handler(notifications_handler)

    return application

async def start(update, context):
    await update.message.reply_text("Бот запущен!")

if __name__ == "__main__":
    application = create_application()

    async def main():
        # Устанавливаем вебхук
        await application.bot.set_webhook(url=WEBHOOK_URL)
        # Инициализируем и запускаем приложение
        await application.initialize()
        await application.start()

    # Запускаем асинхронно инициализацию и запуск приложения
    asyncio.run(main())

    # Запускаем Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
