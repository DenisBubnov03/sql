import gspread
from google.oauth2.service_account import Credentials

# Подключение к Google Sheets через OAuth
def connect_to_sheets():
    gc = gspread.service_account(filename="/etc/secrets/client_secret.json")
  # Путь к скачанному OAuth-файлу
    spreadsheet = gc.open("Ученики")  # Замените "Ученики" на название таблицы
    return spreadsheet.sheet1
