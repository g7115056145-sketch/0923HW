import streamlit as st
import pandas as pd
import sqlite3
from streamlit_folium import st_folium
import folium
from fetch_data import update_weather_pipeline   # 會自動抓最新資料

# -------------------------------------------------
# 1️⃣ 只在第一次啟動時抓取最新天氣資料並寫入 data.db
# -------------------------------------------------
@st.cache_resource
def load_data():
    # 讓程式自動呼叫一次 fetch_data 的 pipeline
    update_weather_pipeline()
    conn = sqlite3.connect("data.db")
    df_region = pd.read_sql_query("SELECT * FROM TemperatureForecasts", conn)
    df_county = pd.read_sql_query("SELECT * FROM CountyForecasts", conn)
    conn.close()
    return df_region, df_county

df_region, df_county = load_data()

# -------------------------------------------------
# 2️⃣ UI 設定
# -------------------------------------------------
st.set_page_config(page_title="台灣天氣預報互動儀表板", layout="wide")
st.title("🇹🇼 台灣天氣預報互動儀表板")
st.caption("資料來源：中央氣象署 CWA Open Data")

# ---- 側邊欄：選擇分區或全台 ----
region = st.sidebar.selectbox(
    "選擇分區 (或全台總覽)",
    options=["全台總覽"] + sorted(df_region["regionName"].unique())
)

# -------------------------------------------------
# 3️⃣ 地圖顯示 (Folium + Streamlit‑Folium)
# -------------------------------------------------
# 先建立一張基礎地圖（全台中心、適合的 zoom）
m = folium.Map(location=[23.7, 121], zoom_start=7, tiles="CartoDB positron")

# 這裡先用簡單的範例座標，實際可依需求自行填入每個分區/縣市的經緯度
# ──────────────────────────────────────────────────────────────────────────────
CITY_COORDS = {
    # region (示範座標，可自行調整)
    "北部地區": [25.05, 121.5],
    "中部地區": [23.9, 120.7],
    "南部地區": [22.7, 120.3],
    "東北部地區": [25.0, 121.8],
    "東部地區": [23.5, 121.6],
    "東南部地區": [22.5, 120.8],
    "澎湖地區": [23.5, 119.5],
    "金門地區": [24.4, 118.3],
    "馬祖地區": [26.2, 119.9],
    # 縣市座標（僅示範幾個，完整可自行補上）
    "臺北市": [25.04, 121.56],
    "新北市": [25.01, 121.46],
    "臺中市": [24.15, 120.65],
    "高雄市": [22.63, 120.30],
    # …其他縣市依需求自行加入
}
# ──────────────────────────────────────────────────────────────────────────────

if region == "全台總覽":
    # 在全台模式下只顯示分區的平均氣溫
    for _, row in df_region.iterrows():
        coord = CITY_COORDS.get(row["regionName"])
        if not coord:
            continue
        folium.CircleMarker(
            location=coord,
            radius=8,
            color="red" if row["maxt"] > 30 else "orange" if row["maxt"] > 25 else "green",
            fill=True,
            popup=f"{row['regionName']}: {row['mint']}~{row['maxt']}°C",
        ).add_to(m)
else:
    # 顯示所選分區下的所有縣市
    sub = df_county[df_county["regionName"] == region]
    for _, r in sub.iterrows():
        coord = CITY_COORDS.get(r["countyName"])
        if not coord:
            continue
        folium.Marker(
            location=coord,
            popup=f"{r['countyName']}: {r['mint']}~{r['maxt']}°C",
            icon=folium.Icon(color="blue"),
        ).add_to(m)

st_folium(m, width=800, height=600)

# -------------------------------------------------
# 4️⃣ 折線圖、表格（Streamlit 原生圖表）
# -------------------------------------------------
if region != "全台總覽":
    df_plot = sub.set_index("dataDate")[["mint", "maxt"]]
    st.subheader(f"{region} 各縣市每日最高/最低溫")
    st.line_chart(df_plot)
else:
    df_plot = df_region.set_index("dataDate")[["mint", "maxt"]]
    st.subheader("全台分區每日最高/最低溫")
    st.line_chart(df_plot)

# 原始資料表格
st.subheader("資料表格")
st.dataframe(df_region if region == "全台總覽" else sub)
