from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


def get_career_consultant_main_keyboard():
    """Основная клавиатура для карьерных консультантов."""
    return ReplyKeyboardMarkup(
        [
            ["🔗 Закрепить КК"],
            ["📊 Моя статистика"]
        ],
        one_time_keyboard=True,
        resize_keyboard=True
    )


def get_student_selection_keyboard(students):
    """Клавиатура для выбора студента для закрепления."""
    keyboard = []
    for student in students:
        keyboard.append([
            InlineKeyboardButton(
                f"{student.fio} (@{student.telegram})",
                callback_data=f"assign_student_{student.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_assignment")])
    
    return InlineKeyboardMarkup(keyboard)


def get_confirmation_keyboard(student_id):
    """Клавиатура для подтверждения закрепления студента."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_assign_{student_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_assignment")
        ]
    ]) 