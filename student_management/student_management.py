# student_management/student_management.py
import gspread


def connect_to_sheets():
    """Устанавливает подключение к таблице Google Sheets."""
    gc = gspread.service_account(filename="client_secret.json")
    spreadsheet = gc.open("Ученики")  # Название таблицы
    worksheet = spreadsheet.sheet1
    return worksheet

worksheet = connect_to_sheets()

# Подключение к Google Sheets
worksheet = connect_to_sheets()


def add_student(fio, telegram, start_date, course_type, total_payment, paid_amount, fully_paid, commission):
    """
    Добавляет нового студента в Google Sheets.

    Args:
        fio (str): ФИО студента.
        telegram (str): Telegram студента.
        start_date (str): Дата начала обучения.
        course_type (str): Тип обучения.
        total_payment (float): Стоимость курса.
        paid_amount (float): Оплаченная сумма.
        fully_paid (str): Полностью оплачено ("Да"/"Нет").
        commission (str): Информация о комиссии.

    Returns:
        None
    """
    try:
        worksheet.append_row([
            fio, telegram, start_date, course_type, total_payment, paid_amount, "",
            "-", "-", "0", fully_paid, "Учится", commission, "0"
        ])
    except Exception as e:
        raise RuntimeError(f"Ошибка добавления студента: {e}")


def delete_student(identifier):
    """
    Удаляет студента по ФИО или Telegram из Google Sheets.

    Args:
        identifier (str): ФИО или Telegram студента.

    Returns:
        bool: True, если студент удалён, иначе False.
    """
    try:
        students = worksheet.get_all_records()
        for i, student in enumerate(students):
            if student["ФИО"] == identifier or student["Telegram"] == identifier:
                worksheet.delete_rows(i + 2)
                return True
        return False
    except Exception as e:
        raise RuntimeError(f"Ошибка удаления студента: {e}")


def update_student_data(identifier, field, new_value):
    """
    Обновляет данные студента в Google Sheets.

    Args:
        identifier (str): ФИО студента.
        field (str): Поле, которое нужно обновить.
        new_value (str): Новое значение.

    Returns:
        bool: True, если обновление успешно, иначе False.
    """
    try:
        students = worksheet.get_all_records()
        for i, student in enumerate(students):
            if student["ФИО"] == identifier:
                headers = list(student.keys())
                if field in headers:
                    col_index = headers.index(field) + 1
                    worksheet.update_cell(i + 2, col_index, new_value)
                    return True
        return False
    except Exception as e:
        raise RuntimeError(f"Ошибка обновления данных студента: {e}")


def get_all_students():
    """
    Возвращает список всех студентов.

    Returns:
        list: Список студентов в виде словарей.
    """
    try:
        return worksheet.get_all_records()
    except Exception as e:
        raise RuntimeError(f"Ошибка получения списка студентов: {e}")
