from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS
from commands.start_commands import exit_to_main_menu
from data_base.db import session
from data_base.models import Payment

# Состояния для ConversationHandler
EXPENSE_TYPE = "EXPENSE_TYPE"
EXPENSE_AMOUNT = "EXPENSE_AMOUNT"
EXPENSE_DATE = "EXPENSE_DATE"



async def start_expense_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало процесса добавления доп расходов.
    """
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS and user_id not in NOT_ADMINS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return ConversationHandler.END

    await update.message.reply_text(
        "💸 Выберите тип доп расходов:",
        reply_markup=ReplyKeyboardMarkup(
            [["Реклама", "Зарплата"], ["Назад"]],
            one_time_keyboard=True
        )
    )
    return EXPENSE_TYPE

async def handle_expense_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор типа расхода.
    """
    expense_type = update.message.text.strip()
    
    if expense_type == "Назад":
        return await exit_to_main_menu(update, context)
    
    if expense_type not in ["Реклама", "Зарплата"]:
        await update.message.reply_text(
            "❌ Некорректный тип расхода. Выберите 'Реклама' или 'Зарплата':",
            reply_markup=ReplyKeyboardMarkup(
                [["Реклама", "Зарплата"], ["Назад"]],
                one_time_keyboard=True
            )
        )
        return EXPENSE_TYPE
    
    context.user_data["expense_type"] = expense_type
    await update.message.reply_text(
        f"💰 Введите сумму для расхода '{expense_type}':",
        reply_markup=ReplyKeyboardMarkup([["Назад"]], one_time_keyboard=True)
    )
    return EXPENSE_AMOUNT

async def handle_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод суммы расхода.
    """
    amount_text = update.message.text.strip()
    
    if amount_text == "Назад":
        return await exit_to_main_menu(update, context)
    
    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
        
        context.user_data["expense_amount"] = amount
        await update.message.reply_text(
            f"📅 Введите дату расхода в формате ДД.ММ.ГГГГ или выберите 'Сегодня':",
            reply_markup=ReplyKeyboardMarkup(
                [["Сегодня"], ["Назад"]],
                one_time_keyboard=True
            )
        )
        return EXPENSE_DATE
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректная сумма. Введите положительное число:",
            reply_markup=ReplyKeyboardMarkup([["Назад"]], one_time_keyboard=True)
        )
        return EXPENSE_AMOUNT

async def handle_expense_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод даты расхода и сохраняет расход в базу.
    """
    date_text = update.message.text.strip()
    
    if date_text == "Назад":
        return await exit_to_main_menu(update, context)
    
    try:
        if date_text.lower() == "сегодня":
            expense_date = datetime.now().date()
        else:
            expense_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        
        expense_type = context.user_data.get("expense_type")
        expense_amount = context.user_data.get("expense_amount")
        
        # Создаем запись о расходе в таблице Payment
        # student_id = None для расходов без привязки к студенту
        expense_payment = Payment(
            student_id=None,  # Нет привязки к студенту для доп расходов
            mentor_id=None,  # Нет привязки к ментору
            amount=expense_amount,
            payment_date=expense_date,
            comment=f"Доп расход: {expense_type}",
            status="подтвержден"
        )
        
        try:
            session.add(expense_payment)
            session.commit()
            
            await update.message.reply_text(
                f"✅ Расход успешно добавлен:\n"
                f"💰 Тип: {expense_type}\n"
                f"💸 Сумма: {expense_amount} руб.\n"
                f"📅 Дата: {expense_date.strftime('%d.%m.%Y')}"
            )
        except Exception as commit_error:
            session.rollback()
            await update.message.reply_text(f"❌ Ошибка при сохранении расхода: {commit_error}")
            return await exit_to_main_menu(update, context)
        
        # Очищаем данные
        context.user_data.pop("expense_type", None)
        context.user_data.pop("expense_amount", None)
        
        return await exit_to_main_menu(update, context)
        
    except ValueError:
        await update.message.reply_text(
            "❌ Некорректная дата. Введите дату в формате ДД.ММ.ГГГГ или выберите 'Сегодня':",
            reply_markup=ReplyKeyboardMarkup(
                [["Сегодня"], ["Назад"]],
                one_time_keyboard=True
            )
        )
        return EXPENSE_DATE
    except Exception as e:
        # Делаем rollback в случае ошибки
        session.rollback()
        await update.message.reply_text(f"❌ Ошибка при сохранении расхода: {e}")
        return await exit_to_main_menu(update, context)

def get_additional_expenses_for_period(start_date, end_date, session):
    """
    Получает сумму доп расходов за период.
    """
    expenses = session.query(Payment).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date,
        Payment.status == "подтвержден",
        Payment.comment.ilike("%Доп расход%"),
        Payment.student_id.is_(None),  # Только расходы без студента
        Payment.mentor_id.is_(None)  # Только расходы без ментора
    ).all()
    
    return sum(float(expense.amount) for expense in expenses) 