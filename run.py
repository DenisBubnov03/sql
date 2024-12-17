import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler

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

TELEGRAM_TOKEN = "7581276969:AAFcFbSt5F2XpVq3yCKDjhLP7tv1cs8TK8Q"
WEBHOOK_URL = f"https://save-kltt.onrender.com/webhook/{TELEGRAM_TOKEN}"

app = Flask(__name__)

# Создаём приложение бота
application = Application.builder().token(TELEGRAM_TOKEN).build()

@app.route("/")
def home():
    return "Telegram Bot is Running!"

@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    application.update_queue.put(update)
    return "OK", 200


def setup_handlers():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^Просмотреть студентов$"), view_students))

if __name__ == "__main__":
    setup_handlers()

    async def set_webhook():
        await application.bot.set_webhook(url=WEBHOOK_URL)

    # Запуск webhook и Flask сервера
    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

