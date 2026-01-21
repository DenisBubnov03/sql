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
from data_base.db import DATABASE_URL
# --- ПУТИ ---
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=dotenv_path)

TOKEN = os.getenv("TELEGRAM_TOKEN_STUDENT")
DATABASE_URL = DATABASE_URL
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
    "{student_name}, привет! На связи бот школы. Мы не общались уже {days_passed} д\n"
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


def get_director_chat_id_from_db(director_id: int) -> Optional[int]:
    """
    Получает chat_id ментора/директора из базы данных по его первичному ключу (ID).
    """
    try:
        # Используем DATABASE_URL из .env
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("SELECT chat_id FROM mentors WHERE id = %s", (director_id,))
        row = cur.fetchone()

        cur.close()
        conn.close()

        if row and row[0]:
            return int(row[0])
        return None
    except Exception as e:
        print(f"❌ Ошибка при получении chat_id директора {director_id}: {e}")
        return None

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

    # 1. Запрос активных студентов
    cur.execute("""
        SELECT s.id, s.fio, m.chat_id, s.telegram, s.last_call_date, s.training_type
        FROM students s
        JOIN mentors m ON s.mentor_id = m.id
        WHERE s.training_status = 'Учится'
        AND s.start_date >= '2025-10-01';
    """)
    rows = cur.fetchall()

    # 2. Получение chat_id директоров (ID 1 и 3)
    cur.execute("SELECT id, chat_id FROM mentors WHERE id IN (1, 3);")
    director_chat_ids = {int(row_id): row_chat_id for row_id, row_chat_id in cur.fetchall() if row_chat_id}

    state = load_state()
    today = date.today()

    # Словари для дайджестов (Stage 2 и 3)
    curator_digests = {}  # {m_chat_id: [сообщения]}
    director_digests = {}  # {d_chat_id: [сообщения]}

    for s_id, s_name, m_chat_id, s_telegram, raw_date, training_type in rows:
        s_id_str = str(s_id)

        # Парсинг даты последнего созвона
        try:
            if not raw_date: continue
            last_call = raw_date if isinstance(raw_date, date) else datetime.strptime(str(raw_date).strip(),
                                                                                      "%Y-%m-%d").date()
        except:
            continue

        days_passed = (today - last_call).days

        # Если студент созвонился — удаляем его из мониторинга
        if days_passed <= 14:
            if s_id_str in state:
                del state[s_id_str]
            continue

        # 3. Проверка "Холда" (паузы 14 дней)
        if state.get(s_id_str, {}).get("active_hold"):
            last_notified_str = state[s_id_str].get("last_notified")
            if last_notified_str:
                last_notified = datetime.strptime(last_notified_str, "%Y-%m-%d").date()
                if (today - last_notified).days < 14:
                    continue  # Пропускаем студента, он на паузе

        # 4. Определение требуемой стадии
        if days_passed >= 35:
            required_stage = 4
        elif days_passed >= 28:
            required_stage = 3
        elif days_passed >= 21:
            required_stage = 2
        else:
            required_stage = 1

        last_stage = int(state.get(s_id_str, {}).get("stage", 0))

        # Если стадия не изменилась — ничего не делаем
        if required_stage <= last_stage:
            continue

        context = {
            "student_name": s_name,
            "student_telegram": s_telegram,
            "days_passed": days_passed,
            "last_call_date": str(last_call),
            "training_type": training_type or "",
        }

        # --- ОБРАБОТКА СТАДИЙ ---

        # STAGE 1: Мягкое напоминание (Индивидуально с кнопками)
        if required_stage == 1:
            student_text = _render_template(first_masage, context)
            curator_text = f"🔔 <b>{s_name}</b> молчит {days_passed} дн. Подтвердите статус:"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Активен (пауза 2 нед.)", callback_data=f"keep_active:{s_id_str}")],
                [InlineKeyboardButton(text="❌ Не учится", callback_data=f"set_inactive:{s_id_str}")]
            ])
            await send_smart_message(s_telegram, student_text)
            await send_smart_message(m_chat_id, curator_text, kb)

        # STAGE 2: 3 недели (Дайджест)
        elif required_stage == 2:
            student_text = _render_template(second_massage_student, context)
            alert = f"⚠️ 3 нед: <b>{s_name}</b> {s_telegram} ({training_type})"

            await send_smart_message(s_telegram, student_text)
            curator_digests.setdefault(m_chat_id, []).append(alert)
            for d_id in _director_ids_for_training_type(training_type):
                d_chat = director_chat_ids.get(d_id)
                if d_chat:
                    director_digests.setdefault(d_chat, []).append(alert)

        # STAGE 3: 4 недели / АЛАРМ (Дайджест)
        elif required_stage == 3:
            student_text = _render_template(third_massage_student, context)
            alert = f"🚨 <b>АЛАРМ 4 нед</b>: {s_name} {s_telegram} ({training_type})"

            await send_smart_message(s_telegram, student_text)
            curator_digests.setdefault(m_chat_id, []).append(alert)
            for d_id in _director_ids_for_training_type(training_type):
                d_chat = director_chat_ids.get(d_id)
                if d_chat:
                    director_digests.setdefault(d_chat, []).append(alert)

        # STAGE 4: 5 недель (Предложение отчислить)
        elif required_stage == 4:
            curator_text = (
                f"💀 <b>ФИНАЛЬНЫЙ ЭТАП: {s_name} {s_telegram}</b>\n"
                f"Молчание <b>{days_passed}</b> дн. Пора принимать решение.\n"
                f"Перевести в статус <b>'Не учится'</b>?"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, отчислить", callback_data=f"drop_student:{s_id_str}")],
                [InlineKeyboardButton(text="❌ Нет, оставить (пауза 2 нед.)", callback_data=f"keep_active:{s_id_str}")]
            ])
            await send_smart_message(m_chat_id, curator_text, kb)

        # Сохраняем состояние
        state[s_id_str] = {
            "stage": required_stage,
            "last_notified": str(today),
            "active_hold": False  # Сбрасываем холд при переходе на новую стадию
        }

    # 5. Рассылка собранных дайджестов
    for chat_id, alerts in curator_digests.items():
        text = "<b>📋 Сводка по пропускам (2-3 недели):</b>\n\n" + "\n".join(alerts)
        await send_smart_message(chat_id, text)

    for chat_id, alerts in director_digests.items():
        text = "<b>📊 Отчет для руководства (Проблемные студенты):</b>\n\n" + "\n".join(alerts)
        await send_smart_message(chat_id, text)

    save_state(state)
    cur.close()
    conn.close()
    await bot.session.close()
if __name__ == "__main__":
    asyncio.run(run_check())
