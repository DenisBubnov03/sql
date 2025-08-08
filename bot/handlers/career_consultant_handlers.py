from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from data_base.operations import (
    get_career_consultant_by_telegram,
    get_students_by_career_consultant,
    assign_student_to_career_consultant
)
from bot.keyboards.career_consultant_keyboards import (
    get_career_consultant_main_keyboard
)
from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS
from commands.states import SELECT_STUDENT, CONFIRM_ASSIGNMENT
from datetime import datetime, timedelta


async def career_consultant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начальная точка для карьерных консультантов."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # Проверяем, является ли пользователь карьерным консультантом в БД
    consultant = get_career_consultant_by_telegram(f"@{username}")
    if not consultant or not consultant.is_active:
        await update.message.reply_text("❌ Вы не найдены в базе карьерных консультантов или ваш аккаунт неактивен.")
        return ConversationHandler.END
    
    context.user_data["consultant_id"] = consultant.id
    context.user_data["consultant_name"] = consultant.full_name
    
    await update.message.reply_text(
        f"👋 Добро пожаловать, {consultant.full_name}!\n\n"
        f"Выберите действие:",
        reply_markup=get_career_consultant_main_keyboard()
    )
    return ConversationHandler.END


async def exit_career_consultant_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из меню карьерного консультанта."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # Проверяем авторизацию в БД
    consultant = get_career_consultant_by_telegram(f"@{username}")
    if not consultant or not consultant.is_active:
        await update.message.reply_text("❌ Вы не найдены в базе карьерных консультантов или ваш аккаунт неактивен.")
        return ConversationHandler.END
    
    # Возвращаемся в главное меню
    from commands.start_commands import exit_to_main_menu
    return await exit_to_main_menu(update, context)


async def show_assign_student_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню для закрепления студента."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # Проверяем авторизацию в БД
    consultant = get_career_consultant_by_telegram(f"@{username}")
    if not consultant or not consultant.is_active:
        await update.message.reply_text("❌ Вы не найдены в базе карьерных консультантов или ваш аккаунт неактивен.")
        return ConversationHandler.END
    
    context.user_data["consultant_id"] = consultant.id
    
    await update.message.reply_text(
        "🔗 Введите Telegram ученика для закрепления:\n"
        "Пример: @username",
        reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], resize_keyboard=True)
    )
    return SELECT_STUDENT


async def handle_student_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод Telegram студента для закрепления."""
    user_input = update.message.text.strip()
    
    if user_input == "🔙 Назад":
        await update.message.reply_text(
            "❌ Закрепление отменено.",
            reply_markup=get_career_consultant_main_keyboard()
        )
        return ConversationHandler.END
    
    # Проверяем формат Telegram
    if not user_input.startswith("@"):
        await update.message.reply_text(
            "❌ Неверный формат Telegram. Введите в формате @username",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], resize_keyboard=True)
        )
        return SELECT_STUDENT
    
    # Ищем студента по Telegram
    from data_base.operations import get_student_by_fio_or_telegram
    student = get_student_by_fio_or_telegram(user_input)
    
    if not student:
        await update.message.reply_text(
            f"❌ Студент с Telegram {user_input} не найден.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], resize_keyboard=True)
        )
        return SELECT_STUDENT
    
    # Проверяем, не закреплен ли уже студент
    if student.career_consultant_id:
        await update.message.reply_text(
            f"❌ Студент {student.fio} уже закреплен за другим карьерным консультантом.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], resize_keyboard=True)
        )
        return SELECT_STUDENT
    
    context.user_data["selected_student"] = student
    
    await update.message.reply_text(
        f"📋 Подтвердите закрепление:\n\n"
        f"👤 Студент: {student.fio}\n"
        f"📱 Telegram: {user_input}\n"
        f"📚 Курс: {student.training_type}\n\n"
        f"Вы уверены, что хотите закрепить этого студента за собой?",
        reply_markup=ReplyKeyboardMarkup([
            ["✅ Да, закрепить"],
            ["❌ Нет, отменить"]
        ], resize_keyboard=True)
    )
    return CONFIRM_ASSIGNMENT


async def handle_assignment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает подтверждение закрепления студента."""
    user_input = update.message.text.strip()
    
    if user_input == "❌ Нет, отменить":
        await update.message.reply_text(
            "❌ Закрепление отменено.",
            reply_markup=get_career_consultant_main_keyboard()
        )
        return ConversationHandler.END
    
    if user_input == "✅ Да, закрепить":
        consultant_id = context.user_data.get("consultant_id")
        student = context.user_data.get("selected_student")
        
        try:
            assign_student_to_career_consultant(student.id, consultant_id)
            await update.message.reply_text(
                f"✅ Студент {student.fio} ({student.telegram}) успешно закреплен за вами!",
                reply_markup=get_career_consultant_main_keyboard()
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка при закреплении: {str(e)}",
                reply_markup=get_career_consultant_main_keyboard()
            )
        
        return ConversationHandler.END
    
    # Если введен неправильный ответ
    await update.message.reply_text(
        "❌ Пожалуйста, выберите '✅ Да, закрепить' или '❌ Нет, отменить'",
        reply_markup=ReplyKeyboardMarkup([
            ["✅ Да, закрепить"],
            ["❌ Нет, отменить"]
        ], resize_keyboard=True)
    )
    return CONFIRM_ASSIGNMENT


async def show_career_consultant_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику карьерного консультанта."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # Проверяем авторизацию в БД
    consultant = get_career_consultant_by_telegram(f"@{username}")
    if not consultant or not consultant.is_active:
        await update.message.reply_text("❌ Вы не найдены в базе карьерных консультантов или ваш аккаунт неактивен.")
        return ConversationHandler.END
    
    # Получаем студентов, закрепленных за консультантом
    students = get_students_by_career_consultant(consultant.id)
    
    response = (
        f"📊 Статистика карьерного консультанта {consultant.full_name}:\n\n"
        f"👥 Закрепленных студентов: {len(students)}\n\n"
    )
    
    if students:
        response += "📋 Список закрепленных студентов:\n"
        for student in students:
            response += f"• {student.fio} ({student.telegram}) - {student.training_type}\n"
    else:
        response += "📝 У вас пока нет закрепленных студентов."
    
    await update.message.reply_text(
        response,
        reply_markup=get_career_consultant_main_keyboard()
    )
    return ConversationHandler.END