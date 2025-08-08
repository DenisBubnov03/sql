from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from data_base.db import session
from data_base.models import CareerConsultant
from commands.authorized_users import AUTHORIZED_USERS
from commands.start_commands import exit_to_main_menu
from datetime import datetime

# Состояния для добавления карьерного консультанта
AWAIT_CC_TELEGRAM = "AWAIT_CC_TELEGRAM"
AWAIT_CC_NAME = "AWAIT_CC_NAME"


async def add_career_consultant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления карьерного консультанта."""
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этой функции.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "💼 Добавление карьерного консультанта\n\n"
        "Введите Telegram карьерного консультанта (например: @consultant):",
        reply_markup=ReplyKeyboardMarkup([["🔙 Главное меню"]], one_time_keyboard=True)
    )
    return AWAIT_CC_TELEGRAM


async def handle_cc_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод Telegram карьерного консультанта."""
    telegram = update.message.text.strip()
    
    # Проверяем кнопку возврата
    if telegram == "🔙 Главное меню":
        return await exit_to_main_menu(update, context)
    
    # Проверяем формат
    if not telegram.startswith('@'):
        await update.message.reply_text("❌ Telegram должен начинаться с @. Попробуйте снова:")
        return AWAIT_CC_TELEGRAM
    
    # Проверяем, не существует ли уже такой консультант
    existing = session.query(CareerConsultant).filter(CareerConsultant.telegram == telegram).first()
    if existing:
        await update.message.reply_text(
            f"❌ Карьерный консультант с Telegram {telegram} уже существует."
        )
        return await exit_to_main_menu(update, context)
    
    context.user_data["cc_telegram"] = telegram
    await update.message.reply_text(
        "Введите полное имя карьерного консультанта:",
        reply_markup=ReplyKeyboardMarkup([["🔙 Главное меню"]], one_time_keyboard=True)
    )
    return AWAIT_CC_NAME


async def handle_cc_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод имени карьерного консультанта."""
    full_name = update.message.text.strip()
    
    # Проверяем кнопку возврата
    if full_name == "🔙 Главное меню":
        return await exit_to_main_menu(update, context)
    
    telegram = context.user_data.get("cc_telegram")
    
    try:
        # Создаем нового карьерного консультанта
        new_consultant = CareerConsultant(
            telegram=telegram,
            full_name=full_name,
            is_active=True,
            created_at=datetime.now().date()
        )
        
        session.add(new_consultant)
        session.commit()
        
        await update.message.reply_text(
            f"✅ Карьерный консультант {full_name} ({telegram}) успешно добавлен!"
        )
        return await exit_to_main_menu(update, context)
        
    except Exception as e:
        session.rollback()
        await update.message.reply_text(
            f"❌ Ошибка при добавлении карьерного консультанта: {str(e)}"
        )
        return await exit_to_main_menu(update, context)


# Создаем ConversationHandler для добавления карьерных консультантов
add_career_consultant_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^💼 Добавить КК$"), add_career_consultant_start)],
    states={
        AWAIT_CC_TELEGRAM: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cc_telegram),
            MessageHandler(filters.Regex("^🔙 Главное меню$"), exit_to_main_menu)
        ],
        AWAIT_CC_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cc_name),
            MessageHandler(filters.Regex("^🔙 Главное меню$"), exit_to_main_menu)
        ],
    },
    fallbacks=[MessageHandler(filters.Regex("^🔙 Главное меню$"), exit_to_main_menu)],
) 