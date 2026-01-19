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
    "{student_name}, привет! Мы не созванивались уже {days_passed} дн.\n"
    "Решил уточнить: всё ли в порядке с обучением? Если возникли сложности или какой-то материал кажется непонятным — не буксуй в одиночку. Напиши своему куратору, он поможет разобраться и мы снова войдем в ритм! 🙌»"

)

second_massage_student = (
    "{student_name}, добрый день! Заметил, что у нас пауза в созвонах уже {days_passed} д\n"
    "Обычно такие перерывы случаются, когда что-то идет не по плану или тема дается тяжело. Есть ли сейчас вопросы по программе? Пожалуйста, дай знать куратору, если нужна помощь или нужно скорректировать график. Мы на связи! 😊"
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
    "{student_name}, привет! На связи бот школы. Мы не общались в зуме уже {days_passed} д\n"
    "Чтобы обучение не превратилось в «долг», важно вовремя разобрать затыки. Расскажи, что сейчас мешает двигаться дальше? Напиши куратору прямо сейчас — обсудите, как лучше продолжить. Ждем твоего ответа! 🔥"
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
        # admin_text = f"<b>‼️ ОШИБКА ДОСТАВКИ</b> (ID: {chat_id})\n\n{text}"
        # try:
            # await bot.send_message(chat_id=MY_PERSONAL_ID, text=admin_text, reply_markup=kb, parse_mode="HTML")
        # except Exception as e2:
        #     print(f"❌ Даже админу не отправить: {e2}")
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

    # Запрос данных
    cur.execute("""
        SELECT s.id, s.fio, m.chat_id, s.telegram, s.last_call_date, s.training_type
        FROM students s
        JOIN mentors m ON s.mentor_id = m.id
        WHERE s.training_status = 'Учится'
        AND s.start_date >= '2025-10-01';
    """)
    rows = cur.fetchall()

    cur.execute("SELECT id, chat_id FROM mentors WHERE id IN (1, 3);")
    director_chat_ids = {int(row_id): row_chat_id for row_id, row_chat_id in cur.fetchall() if row_chat_id}

    state = load_state()
    today = date.today()

    # Словари для сбора "Дайджестов" (чтобы не спамить)
    curator_digests = {}  # {m_chat_id: [список строк уведомлений]}
    director_digests = {}  # {d_chat_id: [список строк уведомлений]}

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
            if s_id_str in state: del state[s_id_str]
            continue

        # Определение текущей максимальной стадии
        if days_passed >= 28:
            required_stage = 3
        elif days_passed >= 21:
            required_stage = 2
        else:
            required_stage = 1

        last_stage = int(state.get(s_id_str, {}).get("stage", 0))

        # Если стадия не выросла — ничего не шлем (кроме повторов для Stage 1, но это ниже)
        if required_stage <= last_stage:
            # Логика повторов для стадии 1 (раз в 3/7/14 дней) остается тут, если нужно
            continue

        context = {
            "student_name": s_name,
            "student_telegram": s_telegram,
            "days_passed": days_passed,
            "last_call_date": str(last_call),
            "training_type": training_type or "",
        }

        # --- ПОДГОТОВКА УВЕДОМЛЕНИЙ (БЕЗ ОТПРАВКИ КУРАТОРУ СРАЗУ) ---
        student_msg = None
        curator_alert = ""

        if required_stage == 1:
            student_msg = _render_template(first_masage, context)
            curator_alert = f"❗ <b>{s_name}</b> ({days_passed} дн.) — Напиши ученику: {s_telegram}"

        elif required_stage == 2:
            student_msg = _render_template(second_massage_student, context)
            curator_alert = f"⚠️ <b>{s_name}</b> ({days_passed} дн.) — 3 недели без связи! {s_telegram}"
            # Добавляем директорам
            for d_id in _director_ids_for_training_type(training_type):
                d_chat = director_chat_ids.get(d_id)
                if d_chat:
                    director_digests.setdefault(d_chat, []).append(f"⚠️ 3 нед: {s_name} ({training_type})")

        elif required_stage == 3:
            student_msg = _render_template(third_massage_student, context)
            curator_alert = f"🚨 <b>АЛАРМ: {s_name}</b> ({days_passed} дн.) — 4 недели тишины! {s_telegram}"
            # Добавляем директорам
            for d_id in _director_ids_for_training_type(training_type):
                d_chat = director_chat_ids.get(d_id)
                if d_chat:
                    director_digests.setdefault(d_chat, []).append(f"🚨 4 нед: {s_name} ({training_type})")

        # 1. Отправляем ученику (индивидуально, это не спам)
        if student_msg:
            await send_smart_message(s_telegram, student_msg)

        # 2. Копим сообщение для куратора
        curator_digests.setdefault(m_chat_id, []).append(curator_alert)

        # Обновляем состояние в JSON
        if s_id_str not in state: state[s_id_str] = {}
        state[s_id_str]["stage"] = required_stage
        state[s_id_str]["last_notified"] = str(today)

    # --- ФИНАЛЬНАЯ РАССЫЛКА ДАЙДЖЕСТОВ ---

    # Кураторам
    for chat_id, alerts in curator_digests.items():
        header = "<b>📋 Список студентов без созвонов:</b>\n\n"
        full_text = header + "\n".join(alerts)
        await send_smart_message(chat_id, full_text)

    # Директорам
    for chat_id, alerts in director_digests.items():
        header = "<b>📊 Сводка по проблемным студентам:</b>\n\n"
        full_text = header + "\n".join(alerts)
        await send_smart_message(chat_id, full_text)

    save_state(state)
    cur.close()
    conn.close()
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(run_check())
