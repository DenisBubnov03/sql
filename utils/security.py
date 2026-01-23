# utils/security.py
from commands.authorized_users import AUTHORIZED_USERS
from data_base.db import get_session
from data_base.models import Mentor, CareerConsultant
from functools import wraps

from data_base.operations import get_mentor_by_telegram, get_career_consultant_by_telegram


async def get_user_role(user_id: int, username: str = None):
    if not username:
        return "admin" if user_id in AUTHORIZED_USERS else None

    formatted_username = f"@{username.replace('@', '')}"
    session = get_session()
    try:
        # 1. Проверяем КК (возвращаем именно "cc")
        cc = get_career_consultant_by_telegram(formatted_username)
        if cc and cc.is_active:
            return "cc"

        # 2. Проверяем Ментора
        mentor = get_mentor_by_telegram(formatted_username)
        if mentor:
            # Если в базе есть флаг is_admin, проверяем его здесь
            # return "admin" if getattr(mentor, 'is_admin', False) else "mentor"
            return "mentor"

        # 3. Резервная проверка админов по ID
        if user_id in AUTHORIZED_USERS:
            return "admin"

        return None
    finally:
        session.close()


def restrict_to(allowed_roles: list):
    """Декоратор для ограничения доступа к функциям."""

    def decorator(func):
        @wraps(func)
        async def wrapped(update, context, *args, **kwargs):
            if not update.effective_user:
                return

            user_id = update.effective_user.id
            username = update.effective_user.username

            role = await get_user_role(user_id, username)

            if role in allowed_roles:
                return await func(update, context, *args, **kwargs)
            else:
                await update.effective_message.reply_text("У вас нет прав для выполнения этой команды.")

        return wrapped

    return decorator


async def role_based_router(update, context, admin_handler, mentor_handler):
    """Вспомогательная функция для выбора обработчика на лету."""
    user = update.effective_user
    role = await get_user_role(user.id, user.username)

    if role == 'admin':
        return await admin_handler(update, context)
    return await mentor_handler(update, context)