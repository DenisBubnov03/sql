
import psycopg2
import requests
import datetime
import time
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
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        print(f"📊 Получено из PostgreSQL ({table_name}): {len(rows)} записей")
        if rows:
            print(f"📋 Поля: {list(rows[0].keys())}")
            print(f"🔍 Пример записи: {rows[0]}")
        return rows

def get_existing_airtable_records(table_id):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    records = []
    offset = None

    print(f"🌐 Запрос к Airtable: {url}")

    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        response = requests.get(url, headers=headers, params=params)
        print(f"📡 Airtable ответ: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Ошибка Airtable ({response.status_code}):", response.text)
            break

        data = response.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    print(f"📦 Получено из Airtable: {len(records)} записей")
    if records:
        print(f"📋 Поля в Airtable: {list(records[0].get('fields', {}).keys())}")
        print(f"🔍 Пример записи Airtable: {records[0]}")
    
    return records

def build_airtable_id_map(records, key_field):
    id_map = {}
    print(f"🔍 Построение карты ID для поля: {key_field}")
    
    for rec in records:
        try:
            raw_id = rec.get("fields", {}).get(key_field)
            if raw_id is None:
                print(f"⚠️ Пропускаем запись без поля {key_field}: {rec}")
                continue
                
            normalized = str(int(float(raw_id)))
            id_map[normalized] = rec["id"]
            print(f"✅ ID маппинг: {raw_id} -> {normalized} -> {rec['id']}")
        except (TypeError, ValueError) as e:
            print(f"❌ Ошибка обработки ID {raw_id}: {e}")
            continue
    
    print(f"📊 Построена карта ID: {len(id_map)} записей")
    return id_map

def update_to_airtable(record_id, record, table_id, key):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"🔄 Обновление записи {record_id}:")
    print(f"   📤 Данные: {record}")
    
    response = requests.patch(url, headers=headers, json={"fields": record})
    time.sleep(0.25)
    
    if response.status_code == 200:
        print(f"✅ Обновлено: {record[key]} ({response.status_code})")
    else:
        print(f"❌ Ошибка обновления: {response.status_code} - {response.text}")

def create_to_airtable(record, table_id, key):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"➕ Создание новой записи:")
    print(f"   📤 Данные: {record}")
    
    response = requests.post(url, headers=headers, json={"fields": record})
    time.sleep(0.25)
    
    if response.status_code == 200:
        print(f"✅ Добавлено: {record[key]} ({response.status_code})")
    else:
        print(f"❌ Ошибка создания: {response.status_code} - {response.text}")

def sync_table(conn, table_name, airtable_table_id, key):
    print(f"\n🔁 Синхронизация таблицы: {table_name}")
    print(f"🔑 Ключевое поле: {key}")
    print(f"📋 Airtable таблица: {airtable_table_id}")
    print("=" * 60)
    
    # Получаем данные из PostgreSQL
    rows = fetch_rows(conn, table_name)
    if not rows:
        print("⚠️ Нет данных в PostgreSQL")
        return
    
    # Получаем данные из Airtable
    airtable_records = get_existing_airtable_records(airtable_table_id)
    airtable_id_map = build_airtable_id_map(airtable_records, key)

    print(f"\n🔄 Начинаем синхронизацию...")
    updated_count = 0
    created_count = 0

    for row in rows:
        try:
            cleaned = serialize_for_airtable({k: v for k, v in row.items() if v is not None}, key)
            row_id = str(int(float(cleaned.get(key))))
            
            print(f"\n🔍 Обработка записи {key}={row_id}")

            if row_id in airtable_id_map:
                print(f"   🔄 Найдена в Airtable, обновляем...")
                update_to_airtable(airtable_id_map[row_id], cleaned, airtable_table_id, key)
                updated_count += 1
            else:
                print(f"   ➕ Не найдена в Airtable, создаем...")
                create_to_airtable(cleaned, airtable_table_id, key)
                created_count += 1
                
        except Exception as e:
            print(f"❌ Ошибка обработки записи {row}: {e}")
            continue

    print(f"\n📊 Итоги синхронизации {table_name}:")
    print(f"   🔄 Обновлено: {updated_count}")
    print(f"   ➕ Создано: {created_count}")

def main():
    print("🚀 Запуск синхронизации с Airtable")
    print("=" * 60)
    
    try:
        conn = get_connection()
        print("✅ Подключение к PostgreSQL установлено")
        
        for table_conf in TABLES_TO_SYNC:
            sync_table(conn, table_conf["pg_table"], table_conf["airtable_table_id"], table_conf["key"])
            
        conn.close()
        print("\n✅ Синхронизация завершена")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
