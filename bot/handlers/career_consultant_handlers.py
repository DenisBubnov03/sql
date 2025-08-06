from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler
from data_base.operations import (
    get_all_career_consultants, 
    get_career_consultant_by_telegram,
    get_students_by_career_consultant,
    assign_student_to_career_consultant,
    calculate_career_consultant_salary,
    get_all_students
)
from bot.keyboards.career_consultant_keyboards import (
    get_career_consultant_main_keyboard,
    get_student_selection_keyboard,
    get_confirmation_keyboard
)
from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS, CAREER_CONSULTANTS
from datetime import datetime, timedelta

# Состояния для карьерных консультантов
SELECT_STUDENT = "SELECT_STUDENT"
CONFIRM_ASSIGNMENT = "CONFIRM_ASSIGNMENT"


async def career_consultant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начальная точка для карьерных консультантов."""
    user_id = update.message.from_user.id
    
    # Проверяем, является ли пользователь карьерным консультантом
    if user_id not in CAREER_CONSULTANTS:
        await update.message.reply_text("❌ У вас нет доступа к функциям карьерного консультанта.")
        return ConversationHandler.END
    
    consultant = get_career_consultant_by_telegram(f"@{update.message.from_user.username}")
    if not consultant:
        await update.message.reply_text("❌ Вы не найдены в базе карьерных консультантов.")
        return ConversationHandler.END
    
    context.user_data["consultant_id"] = consultant.id
    context.user_data["consultant_name"] = consultant.full_name
    
    await update.message.reply_text(
        f"👋 Добро пожаловать, {consultant.full_name}!\n\n"
        f"Выберите действие:",
        reply_markup=get_career_consultant_main_keyboard()
    )
    return ConversationHandler.END


async def show_assign_student_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню для закрепления студента."""
    user_id = update.message.from_user.id
    
    # Проверяем авторизацию
    if user_id not in CAREER_CONSULTANTS:
        await update.message.reply_text("❌ У вас нет доступа к функциям карьерного консультанта.")
        return ConversationHandler.END
    
    consultant = get_career_consultant_by_telegram(f"@{update.message.from_user.username}")
    if not consultant:
        await update.message.reply_text("❌ Вы не найдены в базе карьерных консультантов.")
        return ConversationHandler.END
    
    context.user_data["consultant_id"] = consultant.id
    
    # Получаем всех студентов, которые еще не закреплены за карьерными консультантами
    all_students = get_all_students()
    available_students = [s for s in all_students if not s.career_consultant_id]
    
    if not available_students:
        await update.message.reply_text(
            "📝 Все студенты уже закреплены за карьерными консультантами.",
            reply_markup=get_career_consultant_main_keyboard()
        )
        return ConversationHandler.END
    
    context.user_data["available_students"] = available_students
    
    await update.message.reply_text(
        "🔗 Выберите студента для закрепления:",
        reply_markup=get_student_selection_keyboard(available_students)
    )
    return SELECT_STUDENT


async def handle_student_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор студента для закрепления."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_assignment":
        await query.edit_message_text(
            "❌ Закрепление отменено.",
            reply_markup=get_career_consultant_main_keyboard()
        )
        return ConversationHandler.END
    
    if query.data.startswith("assign_student_"):
        student_id = int(query.data.split("_")[2])
        available_students = context.user_data.get("available_students", [])
        student = next((s for s in available_students if s.id == student_id), None)
        
        if not student:
            await query.edit_message_text(
                "❌ Студент не найден.",
                reply_markup=get_career_consultant_main_keyboard()
            )
            return ConversationHandler.END
        
        context.user_data["selected_student"] = student
        
        await query.edit_message_text(
            f"📋 Подтвердите закрепление:\n\n"
            f"👤 Студент: {student.fio}\n"
            f"📱 Telegram: @{student.telegram}\n"
            f"📚 Курс: {student.training_type}\n\n"
            f"Вы уверены, что хотите закрепить этого студента за собой?",
            reply_markup=get_confirmation_keyboard(student_id)
        )
        return CONFIRM_ASSIGNMENT


async def handle_assignment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает подтверждение закрепления студента."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_assignment":
        await query.edit_message_text(
            "❌ Закрепление отменено.",
            reply_markup=get_career_consultant_main_keyboard()
        )
        return ConversationHandler.END
    
    if query.data.startswith("confirm_assign_"):
        student_id = int(query.data.split("_")[2])
        consultant_id = context.user_data.get("consultant_id")
        student = context.user_data.get("selected_student")
        
        try:
            assign_student_to_career_consultant(student_id, consultant_id)
            await query.edit_message_text(
                f"✅ Студент {student.fio} (@{student.telegram}) успешно закреплен за вами!",
                reply_markup=get_career_consultant_main_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Ошибка при закреплении: {str(e)}",
                reply_markup=get_career_consultant_main_keyboard()
            )
        
        return ConversationHandler.END


async def show_career_consultant_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику карьерного консультанта."""
    user_id = update.message.from_user.id
    
    # Проверяем авторизацию
    if user_id not in CAREER_CONSULTANTS:
        await update.message.reply_text("❌ У вас нет доступа к функциям карьерного консультанта.")
        return ConversationHandler.END
    
    consultant = get_career_consultant_by_telegram(f"@{update.message.from_user.username}")
    if not consultant:
        await update.message.reply_text("❌ Вы не найдены в базе карьерных консультантов.")
        return ConversationHandler.END
    
    # Получаем студентов, закрепленных за консультантом
    students = get_students_by_career_consultant(consultant.id)
    
    # Рассчитываем зарплату за текущий месяц
    today = datetime.now()
    start_of_month = today.replace(day=1)
    salary = calculate_career_consultant_salary(consultant.id, start_of_month, today)
    
    response = (
        f"📊 Статистика карьерного консультанта {consultant.full_name}:\n\n"
        f"👥 Закрепленных студентов: {len(students)}\n"
        f"💰 Зарплата за текущий месяц: {salary} руб.\n\n"
    )
    
    if students:
        response += "📋 Список закрепленных студентов:\n"
        for student in students:
            response += f"• {student.fio} (@{student.telegram}) - {student.training_type}\n"
    else:
        response += "📝 У вас пока нет закрепленных студентов."
    
    await update.message.reply_text(
        response,
        reply_markup=get_career_consultant_main_keyboard()
    )
    return ConversationHandler.END