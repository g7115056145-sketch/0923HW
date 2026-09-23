"""
app.py - Taiwan Weather Dashboard 互動式天氣預報 Web App
涵蓋課程步驟：
- 步驟 11: Streamlit 入門與版面配置
- 步驟 12: 從 SQLite 資料庫 (data.db) 讀取資料
- 步驟 13: 下拉選單選擇地區
- 步驟 14: 繪製一週最高與最低氣溫折線圖
- 步驟 15: 顯示資料表格與統計摘要
- 步驟 16: 整合 Web App 介面
- 步驟 17: 台灣地圖視覺化 (使用 Folium + streamlit-folium)
- 步驟 18: 選擇日期顯示地圖與氣溫級距著色
- 步驟 19: 完整成果展示 (Taiwan Weather Dashboard)
"""

import os
import sqlite3
import folium
from folium import plugins
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import altair as alt

import fetch_data

# 頁面配置
st.set_page_config(
    page_title="Taiwan Weather Dashboard 台灣天氣預報",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂高質感樣式
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F3F4F6;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #3B82F6;
    }
    .legend-box {
        padding: 10px 15px;
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        font-size: 0.9rem;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

DB_PATH = "data.db"

# 各分區地理坐標（緯度, 經度）供地圖標記使用
REGION_COORDINATES = {
    "北部地區": [25.0330, 121.5654],     # 台北
    "中部地區": [24.1477, 120.6736],     # 台中
    "南部地區": [22.6273, 120.3014],     # 高雄
    "東北部地區": [24.7570, 121.7530],   # 宜蘭
    "東部地區": [23.9872, 121.6016],     # 花蓮
    "東南部地區": [22.7583, 121.1444],   # 台東
    "澎湖地區": [23.5711, 119.5793],     # 澎湖
    "金門地區": [24.4491, 118.3766],     # 金門
    "馬祖地區": [26.1558, 119.9519],     # 馬祖
}


def get_color_by_temperature(avg_temp: float) -> str:
    """步驟 18: 依平均溫度區分顏色標記"""
    if avg_temp < 20.0:
        return "#3B82F6"   # < 20°C 藍色
    elif 20.0 <= avg_temp < 25.0:
        return "#10B981"   # 20 - 25°C 綠色
    elif 25.0 <= avg_temp <= 30.0:
        return "#F59E0B"   # 25 - 30°C 橘色
    else:
        return "#EF4444"   # > 30°C 紅色


@st.cache_data(ttl=600)
def load_forecast_data(db_path: str = DB_PATH) -> pd.DataFrame:
    """步驟 12: 從 SQLite 資料庫查詢 TemperatureForecasts 資料"""
    if not os.path.exists(db_path):
        # 若資料庫尚未產生，自動連線抓取
        fetch_data.update_weather_pipeline(db_path=db_path)

    conn = sqlite3.connect(db_path)
    query = """
        SELECT id, regionName, dataDate, mint, maxt 
        FROM TemperatureForecasts 
        ORDER BY dataDate ASC, regionName ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if not df.empty:
        df["avg_temp"] = ((df["mint"] + df["maxt"]) / 2.0).round(1)
        df["temp_diff"] = (df["maxt"] - df["mint"]).round(1)
    return df


def main():
    # 標題區域
    st.markdown('<div class="main-header">🌤️ Taiwan Weather Forecast 台灣天氣預報系統</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">整合中央氣象署 OpenData API × SQLite 資料庫 × Folium 互動地圖 × Streamlit 視覺化</div>', unsafe_allow_html=True)

    # 側邊欄控制項
    with st.sidebar:
        st.header("⚙️ 系統設定與同步")
        api_key_input = st.text_input(
            "CWA API Key 授權碼",
            value=fetch_data.DEFAULT_API_KEY,
            type="password",
            help="中央氣象署開放資料平台會員授權碼"
        )

        if st.button("🔄 立即重新從氣象署抓取最新資料", use_container_width=True):
            with st.spinner("正在連線氣象署並更新 SQLite 資料庫..."):
                try:
                    fetch_data.update_weather_pipeline(api_key=api_key_input, db_path=DB_PATH)
                    st.cache_data.clear()
                    st.success("✅ 資料庫更新成功！")
                except Exception as e:
                    st.error(f"❌ 更新失敗: {e}")

        st.markdown("---")
        st.markdown("### 📚 實作項目說明")
        st.markdown("""
        - **資料來源**：中央氣象署 F-C0032-003
        - **資料庫**：SQLite (`TemperatureForecasts`)
        - **預報期間**：未來一週（7天）逐日預報
        - **分區範圍**：全台各大主要地理分區
        """)

    # 讀取資料
    df = load_forecast_data()
    if df.empty:
        st.warning("⚠️ 目前資料庫內尚無資料，請點擊側邊欄按鈕更新！")
        return

    all_regions = sorted(df["regionName"].unique().tolist())
    all_dates = sorted(df["dataDate"].unique().tolist())

    # 分頁標籤：地圖視覺化 vs 分區趨勢圖 vs 完整資料庫
    tab_map, tab_trend, tab_data = st.tabs([
        "🗺️ 台灣地圖視覺化 (步驟 17-18)",
        "📈 一週分區氣溫趨勢 (步驟 13-16)",
        "📋 資料庫檢視與查詢 (步驟 10, 12)"
    ])

    # ==========================================
    # Tab 1: 台灣地圖視覺化
    # ==========================================
    with tab_map:
        st.subheader("選擇日期顯示互動天氣地圖")
        col_ctrl, col_stats = st.columns([1, 2])

        with col_ctrl:
            selected_date = st.selectbox(
                "📅 選擇預報日期 (步驟 18)",
                options=all_dates,
                index=0,
                help="切換不同日期以觀察全台各分區預報氣溫變化"
            )

        date_df = df[df["dataDate"] == selected_date].copy()

        with col_stats:
            if not date_df.empty:
                max_row = date_df.loc[date_df["maxt"].idxmax()]
                min_row = date_df.loc[date_df["mint"].idxmin()]
                c1, c2, c3 = st.columns(3)
                c1.metric("全台預測最高溫", f"{max_row['maxt']}°C", f"{max_row['regionName']}")
                c2.metric("全台預測最低溫", f"{min_row['mint']}°C", f"{min_row['regionName']}")
                c3.metric("全台當日平均溫", f"{date_df['avg_temp'].mean():.1f}°C")

        # 建立 Folium 地圖 (以台灣中心 23.7, 120.9 定位)
        m = folium.Map(
            location=[23.7, 120.9],
            zoom_start=7.3,
            tiles="CartoDB positron"
        )

        for _, row in date_df.iterrows():
            region = row["regionName"]
            coords = REGION_COORDINATES.get(region)
            if not coords:
                continue

            mint = row["mint"]
            maxt = row["maxt"]
            avg = row["avg_temp"]
            color = get_color_by_temperature(avg)

            # HTML Popup 彈跳資訊視窗 (步驟 18)
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; min-width: 150px;">
                <h4 style="margin: 0 0 5px 0; color: #1E3A8A;">📍 {region}</h4>
                <div style="font-size: 13px; line-height: 1.5;">
                    <b>預報日期：</b> {selected_date}<br>
                    <b>平均溫度：</b> <span style="color: {color}; font-weight: bold;">{avg:.1f}°C</span><br>
                    <b>最高溫 (MaxT)：</b> <span style="color: #DC2626;">{maxt:.1f}°C</span><br>
                    <b>最低溫 (MinT)：</b> <span style="color: #2563EB;">{mint:.1f}°C</span><br>
                    <b>日夜溫差：</b> {row['temp_diff']:.1f}°C
                </div>
            </div>
            """
            popup = folium.Popup(popup_html, max_width=250)

            # 繪製圓形標記
            folium.CircleMarker(
                location=coords,
                radius=14,
                popup=popup,
                tooltip=f"{region}: 平均 {avg:.1f}°C (點擊查看詳情)",
                color="#FFFFFF",
                weight=2,
                fill=True,
                fill_color=color,
                fill_opacity=0.85
            ).add_to(m)

            # 在標記上方標註分區名稱
            folium.map.Marker(
                coords,
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        font-size: 11px;
                        font-weight: bold;
                        color: #1F2937;
                        background-color: rgba(255,255,255,0.75);
                        border-radius: 4px;
                        padding: 1px 4px;
                        width: 60px;
                        text-align: center;
                        transform: translate(-30px, 15px);
                    ">{region}</div>
                    """
                )
            ).add_to(m)

        # 顯示地圖
        st_folium(m, width="100%", height=500, returned_objects=[])

        # 圖例說明 (步驟 18 溫度級距)
        st.markdown("""
        <div class="legend-box">
            <b>🎨 平均氣溫顏色分級說明：</b>
            <span style="color: #3B82F6; font-weight: bold;">●</span> &lt; 20°C (寒冷/涼爽) &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #10B981; font-weight: bold;">●</span> 20°C ~ 25°C (舒適宜人) &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #F59E0B; font-weight: bold;">●</span> 25°C ~ 30°C (溫暖偏熱) &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #EF4444; font-weight: bold;">●</span> &gt; 30°C (炎熱高溫)
        </div>
        """, unsafe_allow_html=True)

    # ==========================================
    # Tab 2: 一週分區氣溫趨勢
    # ==========================================
    with tab_trend:
        st.subheader("一週最高與最低氣溫走勢")

        # 步驟 13: 下拉選單選擇地區
        default_index = all_regions.index("中部地區") if "中部地區" in all_regions else 0
        selected_region = st.selectbox(
            "📍 選擇地區 (Select Region - 步驟 13)",
            options=all_regions,
            index=default_index
        )

        region_df = df[df["regionName"] == selected_region].sort_values("dataDate").copy()

        # 重點指標摘要卡片
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("本週最高溫", f"{region_df['maxt'].max():.1f}°C")
        col_m2.metric("本週最低溫", f"{region_df['mint'].min():.1f}°C")
        col_m3.metric("本週平均溫", f"{region_df['avg_temp'].mean():.1f}°C")
        col_m4.metric("最大日溫差", f"{region_df['temp_diff'].max():.1f}°C")

        # 步驟 14: 繪製一週最高與最低氣溫折線圖
        st.markdown(f"#### 📈 {selected_region} 未來一週最高溫 (MaxT) 與最低溫 (MinT) 折線圖")

        # 轉成長格式供 Altair 繪製雙折線圖
        melted_df = pd.melt(
            region_df,
            id_vars=["dataDate"],
            value_vars=["maxt", "mint"],
            var_name="氣溫類型",
            value_name="溫度"
        )
        type_mapping = {"maxt": "最高氣溫 (MaxT)", "mint": "最低氣溫 (MinT)"}
        melted_df["氣溫類型"] = melted_df["氣溫類型"].map(type_mapping)

        chart = alt.Chart(melted_df).mark_line(point=True, strokeWidth=3).encode(
            x=alt.X("dataDate:N", title="預報日期 (Date)"),
            y=alt.Y("溫度:Q", title="氣溫 (°C)", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "氣溫類型:N",
                scale=alt.Scale(
                    domain=["最高氣溫 (MaxT)", "最低氣溫 (MinT)"],
                    range=["#DC2626", "#2563EB"]
                ),
                title="指標"
            ),
            tooltip=["dataDate", "氣溫類型", alt.Tooltip("溫度:Q", format=".1f")]
        ).properties(
            height=350
        ).interactive()

        st.altair_chart(chart, use_container_width=True)

        # 步驟 15: 顯示資料表格
        st.markdown(f"#### 📋 {selected_region} 未來一週預報數據表格")
        display_df = region_df[["dataDate", "mint", "maxt", "avg_temp", "temp_diff"]].copy()
        display_df.columns = ["日期 (Date)", "最低溫 MinT (°C)", "最高溫 MaxT (°C)", "平均溫 (°C)", "日溫差 (°C)"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ==========================================
    # Tab 3: 完整資料庫檢視 (步驟 10, 12)
    # ==========================================
    with tab_data:
        st.subheader("SQLite 資料庫內容 (TemperatureForecasts 資料表)")
        st.write("此處顯示從 SQLite `data.db` 讀取的原始結構化資料（共", len(df), "筆紀錄）：")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filter_region = st.multiselect("篩選地區", options=all_regions, default=all_regions[:3])
        with col_f2:
            filter_date = st.multiselect("篩選日期", options=all_dates, default=all_dates)

        filtered_df = df[
            (df["regionName"].isin(filter_region)) &
            (df["dataDate"].isin(filter_date))
        ]
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
