
import psycopg2
import requests
import datetime
from decimal import Decimal
from config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, POSTGRESQL_CONFIG

# Таблицы для синхронизации
TABLES_TO_SYNC = [
    {
        "pg_table": "students",
        "airtable_table_id": "tblmrEN4NFj7kdBlw",
        "key": "student_id"
    },
    {
        "pg_table": "payments",
        "airtable_table_id": "tblWRubDgF7C7A0gZ",
        "key": "id"
    },
    {
        "pg_table": "mentors",
        "airtable_table_id": "tbl32BJoSL5TxRWEa",
        "key": "id"
    }
]

def serialize_for_airtable(record: dict, key_field: str):
    result = {}
    for k, v in record.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            result[k] = v.isoformat()
        elif isinstance(v, Decimal):
            result[k] = float(v)
        else:
            result[k] = v
    if 'id' in result and key_field != 'id':
        result[key_field] = result.pop('id')
    return result

def get_connection():
    return psycopg2.connect(**POSTGRESQL_CONFIG)

def fetch_rows(conn, table_name):
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {table_name}")
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

def get_existing_airtable_records(table_id):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    records = []
    offset = None

    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"❌ Ошибка Airtable ({response.status_code}):", response.text)
            break

        data = response.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    return records

def build_airtable_id_map(records, key_field):
    id_map = {}
    for rec in records:
        try:
            raw_id = rec.get("fields", {}).get(key_field)
            normalized = str(int(float(raw_id)))
            id_map[normalized] = rec["id"]
        except (TypeError, ValueError):
            continue
    return id_map

def update_to_airtable(record_id, record, table_id, key):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.patch(url, headers=headers, json={"fields": record})
    print(f"🔄 Обновлено: {record[key]} ({response.status_code})")

def create_to_airtable(record, table_id, key):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json={"fields": record})
    print(f"➕ Добавлено: {record[key]} ({response.status_code})")

def sync_table(conn, table_name, airtable_table_id, key):
    print(f"🔁 Синхронизация таблицы: {table_name}")
    rows = fetch_rows(conn, table_name)
    airtable_records = get_existing_airtable_records(airtable_table_id)
    airtable_id_map = build_airtable_id_map(airtable_records, key)

    print(f"📦 Получено из Airtable: {len(airtable_id_map)} записей")

    for row in rows:
        cleaned = serialize_for_airtable({k: v for k, v in row.items() if v is not None}, key)
        row_id = str(int(float(cleaned.get(key))))

        if row_id in airtable_id_map:
            update_to_airtable(airtable_id_map[row_id], cleaned, airtable_table_id, key)
        else:
            print(f"⚠️ Не нашли {key}={row_id} — добавляем")
            create_to_airtable(cleaned, airtable_table_id, key)

def main():
    conn = get_connection()
    for table_conf in TABLES_TO_SYNC:
        sync_table(conn, table_conf["pg_table"], table_conf["airtable_table_id"], table_conf["key"])
    conn.close()

if __name__ == "__main__":
    main()
