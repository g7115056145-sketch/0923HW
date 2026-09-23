"""
fetch_data.py - 中央氣象署 (CWA) 氣象資料擷取與 SQLite 資料庫儲存模組
對應課程步驟：
- 步驟 3: CWA API Key 認證
- 步驟 4: Requests 取得 JSON 資料
- 步驟 5: 解析 JSON 資料結構
- 步驟 6: 提取最高溫 (maxt) 與最低溫 (mint)
- 步驟 7: 使用 Pandas 整理與預覽資料
- 步驟 8: 建立 SQLite 資料庫 (data.db)
- 步驟 9: 設計 TemperatureForecasts 資料表
- 步驟 10: 查詢資料驗證
- 步驟 20: 程式碼品質優化 (重複執行不重複插入、錯誤處理)
"""

import os
import sqlite3
import urllib3
import requests
import pandas as pd

# 關閉 SSL 不安全連線警告（因應部分 Windows 環境之根憑證檢查）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 預設 API Key 與 資料集網址 (F-C0032-003: 臺灣各分區未來1週天氣預報)
DEFAULT_API_KEY = "CWA-BB3C895D-E305-4A01-9E62-89FDFEB42B3C"
API_URL = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-C0032-003"
DB_PATH = "data.db"

# 課程主要展示的六大重點分區（同時也相容全部離島等地區）
TARGET_REGIONS = [
    "北部地區",
    "中部地區",
    "南部地區",
    "東北部地區",
    "東部地區",
    "東南部地區",
    "澎湖地區",
    "金門地區",
    "馬祖地區"
]


def fetch_cwa_weather_json(api_key: str = DEFAULT_API_KEY) -> dict:
    """步驟 4: 使用 requests 從中央氣象署 API 取得預報 JSON"""
    params = {
        "Authorization": api_key,
        "downloadType": "WEB",
        "format": "JSON"
    }
    print(f"[步驟 4] 正在連線中央氣象署 API 取得氣象資料...")
    response = requests.get(API_URL, params=params, verify=False, timeout=15)
    response.raise_for_status()
    print("[步驟 4] 資料取得成功！")
    return response.json()


def parse_temperature_forecasts(raw_data: dict) -> pd.DataFrame:
    """步驟 5、6、7: 解析 JSON 結構，提取最高溫與最低溫，轉化為結構化 DataFrame"""
    print("[步驟 5 & 6] 正在解析 JSON 結構並提取各分區氣溫資料...")
    
    dataset = raw_data.get("cwaopendata", {}).get("Dataset", {})
    locations_wrapper = dataset.get("Locations", {})
    location_list = locations_wrapper.get("Location", [])

    records = []

    for loc in location_list:
        region_name = loc.get("LocationName")
        if not region_name or region_name not in TARGET_REGIONS:
            continue

        weather_elements = loc.get("WeatherElement", [])
        
        # 分別取出最高溫 (MaxTemperature) 與最低溫 (MinTemperature) 的時間序列
        maxt_series = {}
        mint_series = {}

        for element in weather_elements:
            el_name = element.get("ElementName")
            times = element.get("Time", [])

            if el_name in ["最高溫度", "MaxT"]:
                for t in times:
                    date_str = t.get("StartTime", "")[:10]
                    val = (
                        t.get("ElementValue", {}).get("MaxTemperature")
                        or t.get("ElementValue", {}).get("parameterName")
                    )
                    if date_str and val is not None:
                        maxt_series[date_str] = float(val)

            elif el_name in ["最低溫度", "MinT"]:
                for t in times:
                    date_str = t.get("StartTime", "")[:10]
                    val = (
                        t.get("ElementValue", {}).get("MinTemperature")
                        or t.get("ElementValue", {}).get("parameterName")
                    )
                    if date_str and val is not None:
                        mint_series[date_str] = float(val)

        # 整合同一天的最高溫與最低溫
        common_dates = sorted(set(maxt_series.keys()) & set(mint_series.keys()))
        for data_date in common_dates:
            records.append({
                "regionName": region_name,
                "dataDate": data_date,
                "mint": mint_series[data_date],
                "maxt": maxt_series[data_date]
            })

    # 步驟 7: 建立 Pandas DataFrame
    df = pd.DataFrame(records)
    print(f"[步驟 7] 資料整理完成，共取得 {len(df)} 筆氣溫預報紀錄。")
    return df


def init_database(db_path: str = DB_PATH) -> None:
    """步驟 8 & 9: 建立 SQLite 資料庫與 TemperatureForecasts 資料表"""
    print(f"[步驟 8 & 9] 正在初始化 SQLite 資料庫 ({db_path})...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 建立表格，加入 UNIQUE(regionName, dataDate) 確保步驟 20「重複執行不重複插入」
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS TemperatureForecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regionName TEXT NOT NULL,
            dataDate TEXT NOT NULL,
            mint REAL NOT NULL,
            maxt REAL NOT NULL,
            UNIQUE(regionName, dataDate)
        )
    """)
    conn.commit()
    conn.close()
    print("[步驟 8 & 9] 資料表 TemperatureForecasts 準備就緒！")


def save_forecasts_to_db(df: pd.DataFrame, db_path: str = DB_PATH) -> int:
    """步驟 8 & 20: 儲存至 SQLite，使用 INSERT OR REPLACE 避免重複插入"""
    print(f"[步驟 20] 正在將資料寫入 SQLite 資料庫 (使用 INSERT OR REPLACE)...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    insert_sql = """
        INSERT OR REPLACE INTO TemperatureForecasts (regionName, dataDate, mint, maxt)
        VALUES (?, ?, ?, ?)
    """
    
    rows_to_insert = [
        (row["regionName"], row["dataDate"], row["mint"], row["maxt"])
        for _, row in df.iterrows()
    ]
    cursor.executemany(insert_sql, rows_to_insert)
    conn.commit()
    inserted_count = cursor.rowcount
    conn.close()

    print(f"[步驟 8 & 20] 成功寫入/更新 {len(rows_to_insert)} 筆資料！")
    return inserted_count


def verify_database(db_path: str = DB_PATH) -> None:
    """步驟 10: 查詢資料驗證 (使用 SQL 檢查資料)"""
    print("\n" + "=" * 50)
    print("[步驟 10] 開始進行 SQL 資料庫查詢驗證：")
    print("=" * 50)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 驗證查詢 1: 查詢所有不重複的分區名稱
    cursor.execute("SELECT DISTINCT regionName FROM TemperatureForecasts ORDER BY regionName;")
    regions = [row[0] for row in cursor.fetchall()]
    print(f"1. 資料庫內現有分區 (DISTINCT regionName): {', '.join(regions)}")

    # 驗證查詢 2: 查詢特定分區 (例如「中部地區」) 的預報資料
    test_region = "中部地區"
    cursor.execute(
        "SELECT id, regionName, dataDate, mint, maxt FROM TemperatureForecasts WHERE regionName = ? ORDER BY dataDate;",
        (test_region,)
    )
    mid_records = cursor.fetchall()
    print(f"\n2. 查詢 '{test_region}' 預報資料驗證 (共 {len(mid_records)} 天)：")
    for r in mid_records:
        print(f"   [ID: {r[0]}] 日期: {r[2]} | 最低溫: {r[3]:4.1f}°C | 最高溫: {r[4]:4.1f}°C")

    conn.close()
    print("=" * 50 + "\n")


def update_weather_pipeline(api_key: str = DEFAULT_API_KEY, db_path: str = DB_PATH) -> pd.DataFrame:
    """完整資料擷取與儲存流水線（可供 CLI 或 Streamlit 呼叫）"""
    init_database(db_path)
    raw_json = fetch_cwa_weather_json(api_key)
    df = parse_temperature_forecasts(raw_json)
    save_forecasts_to_db(df, db_path)
    verify_database(db_path)
    return df


if __name__ == "__main__":
    update_weather_pipeline()
