import gspread
from google.oauth2.service_account import Credentials

# Подключение к Google Sheets через OAuth
def connect_to_sheets():
    gc = gspread.oauth(credentials_filename="client_secret.json")  # Путь к скачанному OAuth-файлу
    spreadsheet = gc.open("Ученики")  # Замените "Ученики" на название таблицы
    return spreadsheet.sheet1
