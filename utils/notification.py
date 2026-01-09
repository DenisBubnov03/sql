import os
import json
import asyncio
import psycopg2
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

# --- ПУТИ ---
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=dotenv_path)

TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
MY_PERSONAL_ID = 1257163820

bot = Bot(token=TOKEN)
JSON_FILE = Path(__file__).resolve().parent / "notification_state.json"


# --- ФУНКЦИИ ---
def load_state():
    if JSON_FILE.exists():
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=4)


async def send_smart_message(chat_id, text, kb=None):
    """
    Отправляет сообщение. Используем HTML вместо Markdown,
    чтобы не падать на символах '_' в юзернеймах.
    """
    try:
        # 1. Валидация chat_id
        target = str(chat_id).strip()
        if not target or target.lower() == 'none':
            raise ValueError("ID пустой")

        # Если это не юзернейм (нет @), превращаем в int
        if not target.startswith('@'):
            target = int(target)

        # 2. Отправка (Parse mode HTML)
        await bot.send_message(chat_id=target, text=text, reply_markup=kb, parse_mode="HTML")
        return True

    except Exception as e:
        print(f"⚠️ Ошибка отправки на {chat_id}: {e}. Пересылаю админу.")
        # Экранируем текст для админа, чтобы не упало при пересылке
        admin_text = f"<b>‼️ ОШИБКА ДОСТАВКИ</b> (ID: {chat_id})\n\n{text}"
        try:
            await bot.send_message(chat_id=MY_PERSONAL_ID, text=admin_text, reply_markup=kb, parse_mode="HTML")
        except Exception as e2:
            print(f"❌ Даже админу не отправить: {e2}")
        return False


async def run_check():
    if not DATABASE_URL:
        print("❌ DATABASE_URL не найден")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        return

    cur.execute("""
        SELECT s.id, s.fio, m.chat_id, s.telegram, s.last_call_date 
        FROM students s
        JOIN mentors m ON s.mentor_id = m.id
        WHERE s.training_status = 'Учится'
        and s.start_date >= '2025-10-01';
    """)
    rows = cur.fetchall()

    state = load_state()
    today = date.today()

    for s_id, s_name, m_chat_id,s_telegram, raw_date in rows:
        s_id_str = str(s_id)
        try:
            if not raw_date: continue
            last_call = raw_date if isinstance(raw_date, date) else datetime.strptime(str(raw_date).strip(),
                                                                                      "%Y-%m-%d").date()
        except:
            continue

        days_passed = (today - last_call).days
        if days_passed <= 14:
            if s_id_str in state:
                del state[s_id_str]  # Удаляем все флаги (slow_progress, active_hold), т.к. ученик ожил
            continue

            # --- Логика уведомлений ---
        if days_passed > 14:
            if s_id_str not in state:
                # Первое уведомление
                msg = f"⚠️ Студент <b>{s_name}</b> не созванивался уже <b>{days_passed}</b> дн.! Необходимо написать ученику."
                if await send_smart_message(m_chat_id, msg):
                    state[s_id_str] = {"last_notified": str(today)}

            else:
                last_notified = datetime.strptime(state[s_id_str]["last_notified"], "%Y-%m-%d").date()

                # ВЫБОР ИНТЕРВАЛА
                if state[s_id_str].get("active_hold"):
                    interval = 14  # Пауза 2 недели после кнопки "Активен"
                    status_note = " (после подтверждения активности)"
                elif state[s_id_str].get("slow_progress"):
                    interval = 7  # Пауза неделя после кнопки "Долго учится"
                    status_note = " (режим: раз в неделю)"
                else:
                    interval = 3  # Стандартно
                    status_note = ""

                if (today - last_notified).days >= interval:
                    # Если срок холда (14 дней) прошел, мы можем сбросить флаг active_hold,
                    # чтобы после этого уведомления снова начать пинговать раз в 3 дня
                    if state[s_id_str].get("active_hold"):
                        state[s_id_str].pop("active_hold", None)

                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="❌ Не учится", callback_data=f"set_inactive:{s_id_str}")],
                        [InlineKeyboardButton(text="✅ Активен (на 2 нед.)", callback_data=f"keep_active:{s_id_str}")],
                        [InlineKeyboardButton(text="⏳ Долго учится (на 1 нед.)",
                                              callback_data=f"slow_progress:{s_id_str}")]
                    ])

                    msg = f"🔔 Повтор{status_note}! <b>{s_name}</b> молчит {days_passed} дн. Подтвердите статус:"

                    if await send_smart_message(m_chat_id, msg, kb):
                        state[s_id_str]["last_notified"] = str(today)

        if days_passed > 14:
            if s_id_str not in state:
                # Первое уведомление (без изменений)
                msg = f"⚠️ Студент <b>{s_name}</b> не созванивался уже <b>{days_passed}</b> дн.!"
                if await send_smart_message(m_chat_id, msg):
                    state[s_id_str] = {"last_notified": str(today)}

            else:
                last_notified = datetime.strptime(state[s_id_str]["last_notified"], "%Y-%m-%d").date()

                # НОВАЯ ЛОГИКА: Выбираем интервал (7 дней если "долго учится", иначе 3)
                interval = 7 if state[s_id_str].get("slow_progress") else 3

                if (today - last_notified).days >= interval:
                    # Добавляем третью кнопку
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="❌ Не учится", callback_data=f"set_inactive:{s_id_str}")],
                        [InlineKeyboardButton(text="✅ Активен", callback_data=f"keep_active:{s_id_str}")],
                        [InlineKeyboardButton(text="⏳ Долго учится", callback_data=f"slow_progress:{s_id_str}")]
                    ])

                    status_text = " (режим: раз в неделю)" if interval == 7 else ""
                    msg = f"🔔 Повтор{status_text}! <b>{s_name}</b> молчит {days_passed} дн. Что делаем?"

                    if await send_smart_message(m_chat_id, msg, kb):
                        state[s_id_str]["last_notified"] = str(today)

    save_state(state)
    cur.close()
    conn.close()
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_check())