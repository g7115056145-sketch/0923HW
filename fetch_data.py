"""
fetch_data.py - 中央氣象署 (CWA) 氣象資料擷取與 SQLite 資料庫儲存模組
支援雙層級架構：
1. 分區預報 (TemperatureForecasts: 北部、中部、南部等大分區 - 課程指定規格)
2. 縣市預報 (CountyForecasts: 全台 22 縣市細緻資料 - 支援放大下鑽各縣市詳細資訊)
"""

import collections
import os
import sys
import sqlite3
import urllib3
import requests
import pandas as pd

# 解決 Windows cp950 終端機輸出編碼問題
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 關閉 SSL 不安全連線警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API 設定
DEFAULT_API_KEY = "CWA-BB3C895D-E305-4A01-9E62-89FDFEB42B3C"
API_URL_REGIONS = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-C0032-003"
API_URL_COUNTIES = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-C0032-005"
DB_PATH = "data.db"

# 六大主要分區
TARGET_REGIONS = [
    "北部地區", "中部地區", "南部地區", "東北部地區",
    "東部地區", "東南部地區", "澎湖地區", "金門地區", "馬祖地區"
]

# 縣市與分區對照表
COUNTY_REGION_MAP = {
    # 北部地區
    "基隆市": "北部地區", "臺北市": "北部地區", "新北市": "北部地區",
    "桃園市": "北部地區", "新竹市": "北部地區", "新竹縣": "北部地區", "苗栗縣": "北部地區",
    # 中部地區
    "臺中市": "中部地區", "彰化縣": "中部地區", "南投縣": "中部地區",
    "雲林縣": "中部地區", "嘉義市": "中部地區", "嘉義縣": "中部地區",
    # 南部地區
    "臺南市": "南部地區", "高雄市": "南部地區", "屏東縣": "南部地區",
    # 東北部地區
    "宜蘭縣": "東北部地區",
    # 東部地區
    "花蓮縣": "東部地區",
    # 東南部地區
    "臺東縣": "東南部地區",
    # 離島地區
    "澎湖縣": "澎湖地區", "金門縣": "金門地區", "連江縣": "馬祖地區"
}


def fetch_json(url: str, api_key: str = DEFAULT_API_KEY) -> dict:
    """從 CWA FileAPI 取得 JSON 資料"""
    params = {
        "Authorization": api_key,
        "downloadType": "WEB",
        "format": "JSON"
    }
    resp = requests.get(url, params=params, verify=False, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_region_forecasts(raw_data: dict) -> pd.DataFrame:
    """步驟 5、6、7: 解析分區預報 (F-C0032-003)"""
    dataset = raw_data.get("cwaopendata", {}).get("Dataset", {})
    location_list = dataset.get("Locations", {}).get("Location", [])

    records = []
    for loc in location_list:
        region_name = loc.get("LocationName")
        if not region_name or region_name not in TARGET_REGIONS:
            continue

        maxt_series = {}
        mint_series = {}

        for element in loc.get("WeatherElement", []):
            el_name = element.get("ElementName")
            times = element.get("Time", [])

            if el_name in ["最高溫度", "MaxT"]:
                for t in times:
                    d = t.get("StartTime", "")[:10]
                    val = t.get("ElementValue", {}).get("MaxTemperature") or t.get("ElementValue", {}).get("parameterName")
                    if d and val is not None:
                        maxt_series[d] = float(val)

            elif el_name in ["最低溫度", "MinT"]:
                for t in times:
                    d = t.get("StartTime", "")[:10]
                    val = t.get("ElementValue", {}).get("MinTemperature") or t.get("ElementValue", {}).get("parameterName")
                    if d and val is not None:
                        mint_series[d] = float(val)

        common_dates = sorted(set(maxt_series.keys()) & set(mint_series.keys()))
        for d in common_dates:
            records.append({
                "regionName": region_name,
                "dataDate": d,
                "mint": mint_series[d],
                "maxt": maxt_series[d]
            })

    return pd.DataFrame(records)


def parse_county_forecasts(raw_data: dict) -> pd.DataFrame:
    """解析全台 22 縣市逐日預報 (F-C0032-005)"""
    location_list = raw_data.get("cwaopendata", {}).get("dataset", {}).get("location", [])

    county_records = []
    for loc in location_list:
        county_name = loc.get("locationName")
        region_name = COUNTY_REGION_MAP.get(county_name, "其他地區")

        daily_min = collections.defaultdict(list)
        daily_max = collections.defaultdict(list)
        daily_wx = collections.defaultdict(list)

        for el in loc.get("weatherElement", []):
            el_name = el.get("elementName")
            for t in el.get("time", []):
                d = t.get("startTime", "")[:10]
                val = t.get("parameter", {}).get("parameterName")
                if el_name == "MinT" and val is not None:
                    daily_min[d].append(float(val))
                elif el_name == "MaxT" and val is not None:
                    daily_max[d].append(float(val))
                elif el_name == "Wx" and val is not None:
                    daily_wx[d].append(val)

        common_dates = sorted(set(daily_min.keys()) & set(daily_max.keys()))
        for d in common_dates:
            county_records.append({
                "countyName": county_name,
                "regionName": region_name,
                "dataDate": d,
                "mint": min(daily_min[d]),
                "maxt": max(daily_max[d]),
                "weatherDesc": daily_wx[d][0] if daily_wx[d] else ""
            })

    return pd.DataFrame(county_records)


def init_database(db_path: str = DB_PATH) -> None:
    """初始化 SQLite 資料庫結構"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. 課程指定分區表
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

    # 2. 縣市細部預報表 (支援點進分區後放大下鑽各縣市)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CountyForecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            countyName TEXT NOT NULL,
            regionName TEXT NOT NULL,
            dataDate TEXT NOT NULL,
            mint REAL NOT NULL,
            maxt REAL NOT NULL,
            weatherDesc TEXT,
            UNIQUE(countyName, dataDate)
        )
    """)

    conn.commit()
    conn.close()


def save_data(df_regions: pd.DataFrame, df_counties: pd.DataFrame, db_path: str = DB_PATH) -> None:
    """寫入分區與各縣市預報資料 (使用 INSERT OR REPLACE)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 儲存分區
    insert_regions_sql = """
        INSERT OR REPLACE INTO TemperatureForecasts (regionName, dataDate, mint, maxt)
        VALUES (?, ?, ?, ?)
    """
    rows_reg = [
        (row["regionName"], row["dataDate"], row["mint"], row["maxt"])
        for _, row in df_regions.iterrows()
    ]
    cursor.executemany(insert_regions_sql, rows_reg)

    # 儲存各縣市
    insert_counties_sql = """
        INSERT OR REPLACE INTO CountyForecasts (countyName, regionName, dataDate, mint, maxt, weatherDesc)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    rows_county = [
        (row["countyName"], row["regionName"], row["dataDate"], row["mint"], row["maxt"], row["weatherDesc"])
        for _, row in df_counties.iterrows()
    ]
    cursor.executemany(insert_counties_sql, rows_county)

    conn.commit()
    conn.close()
    print("[INFO] 成功儲存", len(rows_reg), "筆分區資料與", len(rows_county), "筆縣市詳細資料！")


def update_weather_pipeline(api_key: str = DEFAULT_API_KEY, db_path: str = DB_PATH) -> None:
    """完整資料擷取與儲存流水線"""
    init_database(db_path)

    print("[INFO] 正在擷取分區天氣預報 (F-C0032-003)...")
    raw_regions = fetch_json(API_URL_REGIONS, api_key)
    df_regions = parse_region_forecasts(raw_regions)

    print("[INFO] 正在擷取全台縣市詳細預報 (F-C0032-005)...")
    raw_counties = fetch_json(API_URL_COUNTIES, api_key)
    df_counties = parse_county_forecasts(raw_counties)

    save_data(df_regions, df_counties, db_path)


if __name__ == "__main__":
    update_weather_pipeline()
