from datetime import datetime

from sqlalchemy import func
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS
from commands.start_commands import exit_to_main_menu
from commands.states import EXPENSE_TYPE, EXPENSE_SUB_CATEGORY, EXPENSE_AMOUNT, EXPENSE_DATE
from data_base.db import session
# Импортируем твои новые модели
from data_base.models import MarketingSpend, FixedExpense
from utils.security import restrict_to

# Добавляем новое состояние для подкатегорий
# (EXPENSE_TYPE, EXPENSE_SUB_CATEGORY, EXPENSE_AMOUNT, EXPENSE_DATE) = range(4)

# Маппинг для базы данных (чтобы в БД сохранялись английские ключи, а в кнопках были русские)
MARKETING_CHANNELS = {
    "ОМ Ручной": "om_manual",
    "ОМ Авто": "om_auto",
    "Авито": "avito",
    "Ютуб": "media"
}

FIXED_CATEGORIES = {
    "Cineskop": "cineskop",
    "Chat Place": "chat_place",
    "Боты": "bots",
    "Оклады": "salaries_fixed",
    "Менторы": "mentors",
    "Другое": "other_fixed"
}

def get_additional_expenses_for_period(start_date, end_date, detailed=False):
    """
    Суммирует расходы из новых таблиц за указанный период.
    :param detailed: если True, вернет словарь с разбивкой по категориям
    """
    # Если даты пришли как datetime, берем только date
    if isinstance(start_date, datetime): start_date = start_date.date()
    if isinstance(end_date, datetime): end_date = end_date.date()

    # Считаем маркетинг
    marketing_query = session.query(func.sum(MarketingSpend.amount)).filter(
        MarketingSpend.report_month >= start_date,
        MarketingSpend.report_month <= end_date
    ).scalar() or 0

    # Считаем фиксы
    fixed_query = session.query(func.sum(FixedExpense.amount)).filter(
        FixedExpense.report_month >= start_date,
        FixedExpense.report_month <= end_date
    ).scalar() or 0

    total = float(marketing_query) + float(fixed_query)

    if not detailed:
        return total

    # Для юнит-экономики нам понадобится детальный отчет
    return {
        "total": total,
        "marketing_total": float(marketing_query),
        "fixed_total": float(fixed_query)
    }
@restrict_to(['admin', 'mentor']) # Разрешаем доступ обеим ролям
async def start_expense_process(update: Update, context: ContextTypes.DEFAULT_TYPE):


    await update.message.reply_text(
        "💸 Выберите тип расхода:",
        reply_markup=ReplyKeyboardMarkup(
            [["Маркетинг"], ["Фиксы"], ["Назад"]],
            one_time_keyboard=True, resize_keyboard=True
        )
    )
    return EXPENSE_TYPE


async def handle_expense_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()

    if choice == "Назад":
        return await exit_to_main_menu(update, context)

    context.user_data["main_type"] = choice  # 'Маркетинг' или 'Фиксы'

    if choice == "Маркетинг":
        keyboard = [["ОМ Ручной", "ОМ Авто"], ["Авито", "Ютуб"], ["Назад"]]
        text = "🎯 Выберите канал маркетинга:"
    elif choice == "Фиксы":
        keyboard = [["Cineskop", "Chat Place"], ["Боты", "Оклады"], ["Менторы", "Другое"], ["Назад"]]
        text = "⚙️ Выберите категорию фиксированных расходов:"
    else:
        return EXPENSE_TYPE

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return EXPENSE_SUB_CATEGORY


async def handle_sub_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sub_choice = update.message.text.strip()

    if sub_choice == "Назад":
        return await start_expense_process(update, context)

    # Сохраняем "человеческое" название для вывода и "техническое" для БД
    context.user_data["sub_category_name"] = sub_choice

    if context.user_data["main_type"] == "Маркетинг":
        context.user_data["db_category"] = MARKETING_CHANNELS.get(sub_choice, "other")
    else:
        context.user_data["db_category"] = FIXED_CATEGORIES.get(sub_choice, "other_fixed")

    await update.message.reply_text(
        f"💰 Введите сумму для '{sub_choice}':",
        reply_markup=ReplyKeyboardMarkup([["Назад"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return EXPENSE_AMOUNT


async def handle_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text.strip()
    if amount_text == "Назад":
        return await handle_expense_type(update, context)

    try:
        amount = float(amount_text.replace(",", "."))
        if amount <= 0: raise ValueError
        context.user_data["expense_amount"] = amount

        await update.message.reply_text(
            "📅 Введите дату расхода (ДД.ММ.ГГГГ) или нажмите 'Сегодня':",
            reply_markup=ReplyKeyboardMarkup([["Сегодня"], ["Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return EXPENSE_DATE
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число.")
        return EXPENSE_AMOUNT


async def handle_expense_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text.strip()
    if date_text == "Назад":
        return await handle_sub_category(update, context)

    try:
        if date_text.lower() == "сегодня":
            expense_date = datetime.now().date()
        else:
            expense_date = datetime.strptime(date_text, "%d.%m.%Y").date()

        # Для отчетности нам нужно 1-е число месяца
        report_month = expense_date.replace(day=1)

        main_type = context.user_data.get("main_type")
        db_category = context.user_data.get("db_category")
        amount = context.user_data.get("expense_amount")

        if main_type == "Маркетинг":
            new_record = MarketingSpend(
                report_month=report_month,
                channel=db_category,
                amount=amount
            )
        else:
            new_record = FixedExpense(
                report_month=report_month,
                category=db_category,
                amount=amount
            )

        session.add(new_record)
        session.commit()

        await update.message.reply_text(
            f"✅ Расход зафиксирован!\n"
            f"📁 Тип: {main_type} ({context.user_data['sub_category_name']})\n"
            f"💰 Сумма: {amount} руб.\n"
            f"📅 Отчетный период: {report_month.strftime('%m.%Y')}"
        )
        return await exit_to_main_menu(update, context)

    except Exception as e:
        session.rollback()
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return await exit_to_main_menu(update, context)