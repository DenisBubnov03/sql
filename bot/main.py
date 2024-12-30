from telegram.ext import Application, CommandHandler, MessageHandler, filters
from bot.handlers.start_handlers import start
from bot.handlers.student_handlers import add_student_handler, edit_student_handler, search_student_handler
from bot.handlers.statistics_handlers import statistics_handler
from bot.handlers.notification_handlers import notifications_handler
from migrations.env import TELEGRAM_TOKEN

# Создание приложения
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Регистрация хэндлеров
application.add_handler(CommandHandler("start", start))
application.add_handler(add_student_handler)
application.add_handler(edit_student_handler)
application.add_handler(search_student_handler)
application.add_handler(statistics_handler)
application.add_handler(notifications_handler)

# Запуск приложения
if __name__ == "__main__":
    application.run_polling()
