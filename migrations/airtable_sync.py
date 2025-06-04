import psycopg2
import requests
from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, POSTGRESQL_CONFIG
import datetime
from decimal import Decimal

def serialize_for_airtable(record: dict):
    result = {}
    for k, v in record.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            result[k] = v.isoformat()
        elif isinstance(v, Decimal):
            result[k] = float(v)  # Или str(v), если Airtable требует текст
        else:
            result[k] = v
    if 'id' in result:
        result['student_id'] = result.pop('id')
    return result



def get_connection():
    return psycopg2.connect(**POSTGRESQL_CONFIG)


def fetch_students(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM students")
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def find_airtable_record_id(existing_records, student_id):
    for rec in existing_records:
        if str(rec.get("fields", {}).get("student_id")) == str(student_id):
            return rec["id"]
    return None


def get_existing_airtable_records():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}?pageSize=100"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    response = requests.get(url, headers=headers)
    return response.json().get("records", [])


def upsert_to_airtable(record, existing_airtable):
    airtable_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    record_id = find_airtable_record_id(existing_airtable, record['student_id'])

    data = {
        "fields": record
    }

    if record_id:
        # Обновление
        response = requests.patch(f"{airtable_url}/{record_id}", headers=headers, json=data)
        print(f"🔄 Обновлено: {record['student_id']} ({response.status_code})")
    else:
        # Добавление
        response = requests.post(airtable_url, headers=headers, json=data)
        print(f"➕ Добавлено: {record['student_id']} ({response.status_code})")
        print(response.text)  # <<< добавь эту строку


def main():
    conn = get_connection()
    students = fetch_students(conn)
    existing_airtable = get_existing_airtable_records()

    for student in students:
        # Airtable требует, чтобы None был пропущен
        student_cleaned = serialize_for_airtable({k: v for k, v in student.items() if v is not None})
        upsert_to_airtable(student_cleaned, existing_airtable)

    conn.close()


if __name__ == "__main__":
    main()
