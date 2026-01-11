import os
import json
import asyncio
import psycopg2
from datetime import datetime, date
from pathlib import Path
from typing import Optional
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

# --- ТЕКСТЫ УВЕДОМЛЕНИЙ (заполни при необходимости) ---
# В этих шаблонах можно использовать параметры:
# {student_name}, {student_telegram}, {days_passed}, {last_call_date}, {training_type}
first_masage = (
    "Привет! Мы не созванивались уже {days_passed} дней. "
    "Напиши, пожалуйста, когда удобно созвониться."
)

second_massage_student = (
    "Привет! Напоминаю: созвона не было уже {days_passed} дней. "
    "Давай запланируем звонок на этой неделе."
)
second_massage_curator = (
    "⚠️ 3 недели без созвона: <b>{student_name}</b> {student_telegram} "
    "(тип: {training_type}). Последний созвон: <b>{last_call_date}</b>."
)
second_massage_director = (
    "⚠️ 3 недели без созвона: <b>{student_name}</b> {student_telegram} "
    "(тип: {training_type}). Последний созвон: <b>{last_call_date}</b>."
)

third_massage_student = (
    "Привет! Это важное напоминание: созвона не было уже {days_passed} дней. "
    "Пожалуйста, ответь и согласуй время созвона."
)
third_massage_curator_alarm = (
    "🚨 <b>АЛАРМ</b>: 4 недели без созвона — <b>{student_name}</b> {student_telegram} "
    "(тип: {training_type}). Последний созвон: <b>{last_call_date}</b>."
)
third_massage_director_alarm = (
    "🚨 <b>АЛАРМ</b>: 4 недели без созвона — <b>{student_name}</b> {student_telegram} "
    "(тип: {training_type}). Последний созвон: <b>{last_call_date}</b>."
)


# --- ФУНКЦИИ ---
def load_state():
    if JSON_FILE.exists():
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=4)


def _render_template(template: str, context: dict) -> str:
    try:
        return template.format(**context)
    except Exception:
        return template


def _director_ids_for_training_type(training_type: Optional[str]) -> list[int]:
    if training_type == "Ручное тестирование":
        return [1]
    if training_type == "Автотестирование":
        return [3]
    if training_type == "Фуллстек":
        return [1, 3]
    return []


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
        SELECT s.id, s.fio, m.chat_id, s.telegram, s.last_call_date, s.training_type
        FROM students s
        JOIN mentors m ON s.mentor_id = m.id
        WHERE s.training_status = 'Учится'
        and s.start_date >= '2025-10-01';
    """)
    rows = cur.fetchall()

    cur.execute("SELECT id, chat_id FROM mentors WHERE id IN (1, 3);")
    director_chat_ids = {int(row_id): row_chat_id for row_id, row_chat_id in cur.fetchall() if row_chat_id}

    state = load_state()
    today = date.today()

    for s_id, s_name, m_chat_id, s_telegram, raw_date, training_type in rows:
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
                del state[s_id_str]  # Удаляем все флаги, т.к. ученик ожил
            continue

        # --- Логика триггеров (2/3/4 недели) ---
        if s_id_str not in state:
            state[s_id_str] = {}

        last_stage = int(state[s_id_str].get("stage", 0) or 0)
        if days_passed >= 28:
            required_stage = 3
        elif days_passed >= 21:
            required_stage = 2
        else:
            required_stage = 1  # 15-20 дней

        context = {
            "student_name": s_name,
            "student_telegram": s_telegram,
            "days_passed": days_passed,
            "last_call_date": str(last_call),
            "training_type": training_type or "",
        }

        async def _send_to_directors(text: str) -> None:
            for director_id in _director_ids_for_training_type(training_type):
                chat_id = director_chat_ids.get(director_id)
                if chat_id:
                    await send_smart_message(chat_id, text)

        # Отправляем недостающие стадии по порядку, чтобы не пропускать эскалации
        for stage in range(last_stage + 1, required_stage + 1):
            if stage == 1:
                curator_text = (
                    f"⚠️ Студент <b>{s_name}</b> не созванивался уже <b>{days_passed}</b> дн.! "
                    f"Необходимо написать ученику {s_telegram}."
                )
                student_text = _render_template(first_masage, context)
                await send_smart_message(m_chat_id, curator_text)
                await send_smart_message(s_telegram, student_text)

            elif stage == 2:
                student_text = _render_template(second_massage_student, context)
                curator_text = _render_template(second_massage_curator, context)
                director_text = _render_template(second_massage_director, context)
                await send_smart_message(s_telegram, student_text)
                await send_smart_message(m_chat_id, curator_text)
                await _send_to_directors(director_text)

            elif stage == 3:
                student_text = _render_template(third_massage_student, context)
                curator_text = _render_template(third_massage_curator_alarm, context)
                director_text = _render_template(third_massage_director_alarm, context)
                await send_smart_message(s_telegram, student_text)
                await send_smart_message(m_chat_id, curator_text)
                await _send_to_directors(director_text)

        if required_stage > last_stage:
            state[s_id_str]["stage"] = required_stage
            state[s_id_str]["last_notified"] = str(today)

        # Повторы для 1-го уровня (2 недели) — как раньше, с кнопками статуса
        if required_stage == 1 and state[s_id_str].get("last_notified"):
            last_notified = datetime.strptime(state[s_id_str]["last_notified"], "%Y-%m-%d").date()

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

    save_state(state)
    cur.close()
    conn.close()
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_check())
