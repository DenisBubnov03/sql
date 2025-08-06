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
        "Введите Telegram карьерного консультанта (например: @consultant):"
    )
    return AWAIT_CC_TELEGRAM


async def handle_cc_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод Telegram карьерного консультанта."""
    telegram = update.message.text.strip()
    
    # Проверяем формат
    if not telegram.startswith('@'):
        await update.message.reply_text("❌ Telegram должен начинаться с @. Попробуйте снова:")
        return AWAIT_CC_TELEGRAM
    
    # Проверяем, не существует ли уже такой консультант
    existing = session.query(CareerConsultant).filter(CareerConsultant.telegram == telegram).first()
    if existing:
        await update.message.reply_text(
            f"❌ Карьерный консультант с Telegram {telegram} уже существует.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Главное меню"]], one_time_keyboard=True)
        )
        return ConversationHandler.END
    
    context.user_data["cc_telegram"] = telegram
    await update.message.reply_text("Введите полное имя карьерного консультанта:")
    return AWAIT_CC_NAME


async def handle_cc_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод имени карьерного консультанта."""
    full_name = update.message.text.strip()
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
            f"✅ Карьерный консультант {full_name} ({telegram}) успешно добавлен!",
            reply_markup=ReplyKeyboardMarkup([["🔙 Главное меню"]], one_time_keyboard=True)
        )
        return ConversationHandler.END
        
    except Exception as e:
        session.rollback()
        await update.message.reply_text(
            f"❌ Ошибка при добавлении карьерного консультанта: {str(e)}",
            reply_markup=ReplyKeyboardMarkup([["🔙 Главное меню"]], one_time_keyboard=True)
        )
        return ConversationHandler.END


async def list_career_consultants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех карьерных консультантов."""
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этой функции.")
        return ConversationHandler.END
    
    consultants = session.query(CareerConsultant).filter(CareerConsultant.is_active == True).all()
    
    if not consultants:
        await update.message.reply_text("📝 Карьерных консультантов пока нет.")
        return await exit_to_main_menu(update, context)
    
    response = "💼 Список карьерных консультантов:\n\n"
    for consultant in consultants:
        # Подсчитываем количество закрепленных студентов
        students_count = len(consultant.students)
        response += f"👤 {consultant.full_name}\n"
        response += f"📱 {consultant.telegram}\n"
        response += f"👥 Закрепленных студентов: {students_count}\n"
        response += f"📅 Дата добавления: {consultant.created_at}\n"
        response += "─" * 30 + "\n"
    
    await update.message.reply_text(response)
    return await exit_to_main_menu(update, context)


# Создаем ConversationHandler для добавления карьерных консультантов
add_career_consultant_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^💼 Добавить КК$"), add_career_consultant_start)],
    states={
        AWAIT_CC_TELEGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cc_telegram)],
        AWAIT_CC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cc_name)],
    },
    fallbacks=[MessageHandler(filters.Regex("^🔙 Главное меню$"), exit_to_main_menu)],
) 