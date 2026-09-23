"""
app.py - Taiwan Weather Dashboard 台灣氣象預報互動 Web App
具備分區到縣市的「點選放大下鑽 (Drill-Down / Zoom-In)」功能：
- 點選全台總覽：宏觀顯示各大分區氣象資訊。
- 點選特定分區（例如「中部地區」）：地圖自動平移並放大 (Zoom In)，顯示中部各縣市（臺中、彰化、南投、雲林、嘉義市、嘉義縣）的詳細天氣指標、氣溫與視覺化比較。
"""

import os
import sqlite3
import folium
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
        margin-bottom: 1.2rem;
    }
    .region-banner {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 10px;
        margin-bottom: 15px;
        display: flex;
        justify-content: space-between;
        align-items: center;
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

# 分區地理坐標與縮放設定
REGION_VIEW_CONFIG = {
    "全台總覽": {"center": [23.7, 120.9], "zoom": 7.3, "icon": "🇹🇼"},
    "北部地區": {"center": [24.95, 121.35], "zoom": 9.3, "icon": "🏙️"},
    "中部地區": {"center": [23.95, 120.65], "zoom": 9.2, "icon": "🌾"},
    "南部地區": {"center": [22.75, 120.45], "zoom": 9.0, "icon": "☀️"},
    "東北部地區": {"center": [24.75, 121.75], "zoom": 9.8, "icon": "🌊"},
    "東部地區": {"center": [23.85, 121.45], "zoom": 8.8, "icon": "⛰️"},
    "東南部地區": {"center": [22.75, 121.14], "zoom": 9.2, "icon": "🏝️"},
    "澎湖地區": {"center": [23.57, 119.58], "zoom": 10.5, "icon": "🚢"},
    "金門地區": {"center": [24.45, 118.38], "zoom": 11.0, "icon": "🧱"},
    "馬祖地區": {"center": [26.16, 119.95], "zoom": 11.5, "icon": "⚓"},
}

# 全台 22 縣市精準地理坐標
COUNTY_COORDINATES = {
    "基隆市": [25.1276, 121.7392],
    "臺北市": [25.0375, 121.5637],
    "新北市": [25.0118, 121.4658],
    "桃園市": [24.9936, 121.3010],
    "新竹市": [24.8039, 120.9647],
    "新竹縣": [24.8383, 121.0177],
    "苗栗縣": [24.5602, 120.8214],
    "臺中市": [24.1632, 120.6403],
    "彰化縣": [24.0817, 120.5385],
    "南投縣": [23.9100, 120.9719],
    "雲林縣": [23.7092, 120.4313],
    "嘉義市": [23.4800, 120.4491],
    "嘉義縣": [23.4518, 120.2559],
    "臺南市": [22.9997, 120.2270],
    "高雄市": [22.6273, 120.3014],
    "屏東縣": [22.5519, 120.5487],
    "宜蘭縣": [24.7570, 121.7530],
    "花蓮縣": [23.9872, 121.6016],
    "臺東縣": [22.7583, 121.1444],
    "澎湖縣": [23.5711, 119.5793],
    "金門縣": [24.4491, 118.3766],
    "連江縣": [26.1558, 119.9519],
}


def get_color_by_temperature(avg_temp: float) -> str:
    """依平均溫度區分顏色標記"""
    if avg_temp < 20.0:
        return "#3B82F6"   # < 20°C 藍色
    elif 20.0 <= avg_temp < 25.0:
        return "#10B981"   # 20 - 25°C 綠色
    elif 25.0 <= avg_temp <= 30.0:
        return "#F59E0B"   # 25 - 30°C 橘色
    else:
        return "#EF4444"   # > 30°C 紅色


def get_weather_emoji(desc: str) -> str:
    """根據天氣敘述匹配表情符號"""
    if not desc:
        return "🌤️"
    if "雨" in desc or "雷" in desc:
        return "🌧️"
    if "陰" in desc:
        return "☁️"
    if "多雲" in desc:
        return "⛅"
    if "晴" in desc:
        return "☀️"
    return "🌤️"


@st.cache_data(ttl=600)
def load_forecast_data(db_path: str = DB_PATH):
    """從 SQLite 資料庫讀取分區與縣市預報資料"""
    if not os.path.exists(db_path):
        fetch_data.update_weather_pipeline(db_path=db_path)

    conn = sqlite3.connect(db_path)
    
    # 讀取分區預報
    df_regions = pd.read_sql_query(
        "SELECT id, regionName, dataDate, mint, maxt FROM TemperatureForecasts ORDER BY dataDate ASC, regionName ASC",
        conn
    )
    if not df_regions.empty:
        df_regions["avg_temp"] = ((df_regions["mint"] + df_regions["maxt"]) / 2.0).round(1)
        df_regions["temp_diff"] = (df_regions["maxt"] - df_regions["mint"]).round(1)

    # 讀取縣市細緻預報
    df_counties = pd.read_sql_query(
        "SELECT id, countyName, regionName, dataDate, mint, maxt, weatherDesc FROM CountyForecasts ORDER BY dataDate ASC, countyName ASC",
        conn
    )
    if not df_counties.empty:
        df_counties["avg_temp"] = ((df_counties["mint"] + df_counties["maxt"]) / 2.0).round(1)
        df_counties["temp_diff"] = (df_counties["maxt"] - df_counties["mint"]).round(1)

    conn.close()
    return df_regions, df_counties


def main():
    # 初始化 session state
    if "current_view_region" not in st.session_state:
        st.session_state["current_view_region"] = "全台總覽"

    # 標題
    st.markdown('<div class="main-header">🌤️ Taiwan Weather Forecast 台灣天氣預報系統</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">整合中央氣象署 OpenData API × SQLite 資料庫 × 縣市分區下鑽放大 × Streamlit 視覺化</div>', unsafe_allow_html=True)

    # 側邊欄控制
    with st.sidebar:
        st.header("⚙️ 系統設定與同步")
        api_key_input = st.text_input(
            "CWA API Key 授權碼",
            value=fetch_data.DEFAULT_API_KEY,
            type="password",
            help="中央氣象署開放資料平臺會員授權碼"
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
        st.markdown("### 💡 實作特色亮點")
        st.markdown("""
        - **分區深入下鑽**：點選任一分區，地圖**自動平移放大**並呈現該區各縣市即時預報！
        - **縣市氣象對比**：提供縣市級別溫差比較、即時天氣現象與折線走勢。
        - **嚴格資料庫架構**：完全相容課程指定的 `TemperatureForecasts`，並擴充 `CountyForecasts`。
        """)

    # 載入資料
    df_regions, df_counties = load_forecast_data()
    if df_regions.empty or df_counties.empty:
        st.warning("⚠️ 目前資料庫內尚無資料，請點擊側邊欄按鈕更新！")
        return

    all_dates = sorted(df_regions["dataDate"].unique().tolist())
    all_regions = [r for r in list(REGION_VIEW_CONFIG.keys()) if r != "全台總覽"]

    # 建立頁籤
    tab_map, tab_trend, tab_data = st.tabs([
        "🗺️ 台灣地圖與分區縣市放大下鑽",
        "📈 一週氣溫走勢與天氣現象",
        "📋 資料庫檢視 (分區 & 縣市)"
    ])

    # ==========================================
    # Tab 1: 地圖視覺化與放大下鑽
    # ==========================================
    with tab_map:
        # 上方控制列：選擇預報日期 與 選擇聚焦視角
        col_date, col_view = st.columns([1, 2])
        with col_date:
            selected_date = st.selectbox(
                "📅 選擇預報日期",
                options=all_dates,
                index=0
            )

        with col_view:
            view_options = ["全台總覽"] + all_regions
            current_idx = view_options.index(st.session_state["current_view_region"]) if st.session_state["current_view_region"] in view_options else 0
            
            selected_region_view = st.selectbox(
                "🔍 探索分區視野 (選擇分區自動放大顯示各縣市)",
                options=view_options,
                index=current_idx,
                format_func=lambda x: f"{REGION_VIEW_CONFIG.get(x, {}).get('icon', '')} {x}"
            )
            # 若選單變更，更新 session_state
            if selected_region_view != st.session_state["current_view_region"]:
                st.session_state["current_view_region"] = selected_region_view
                st.rerun()

        active_view = st.session_state["current_view_region"]
        cfg = REGION_VIEW_CONFIG.get(active_view, REGION_VIEW_CONFIG["全台總覽"])

        # 頂部提示條與「返回全台總覽」快捷按鈕
        if active_view != "全台總覽":
            col_b1, col_b2 = st.columns([3, 1])
            with col_b1:
                st.info(f"🔎 目前已放大至 **{active_view}**！地圖已聚焦並顯示該分區轄下各縣市的詳細氣候預報。")
            with col_b2:
                if st.button("🔙 返回全台總覽", use_container_width=True):
                    st.session_state["current_view_region"] = "全台總覽"
                    st.rerun()

        # 建立 Folium 地圖物件
        m = folium.Map(
            location=cfg["center"],
            zoom_start=cfg["zoom"],
            tiles="CartoDB positron"
        )

        # 判斷當前模式：全台總覽 vs 分區深入下鑽
        if active_view == "全台總覽":
            # --- 模式 A: 顯示全台各大分區 ---
            sub_df = df_regions[df_regions["dataDate"] == selected_date]
            
            for _, row in sub_df.iterrows():
                region = row["regionName"]
                center_coords = REGION_VIEW_CONFIG.get(region, {}).get("center")
                if not center_coords:
                    continue

                avg = row["avg_temp"]
                mint = row["mint"]
                maxt = row["maxt"]
                color = get_color_by_temperature(avg)

                popup_html = f"""
                <div style="font-family: Arial, sans-serif; min-width: 170px;">
                    <h4 style="margin: 0 0 5px 0; color: #1E3A8A;">📍 {region}</h4>
                    <div style="font-size: 13px; line-height: 1.6;">
                        <b>預報日期：</b> {selected_date}<br>
                        <b>平均溫度：</b> <span style="color: {color}; font-weight: bold;">{avg:.1f}°C</span><br>
                        <b>最高溫 (MaxT)：</b> <span style="color: #DC2626;">{maxt:.1f}°C</span><br>
                        <b>最低溫 (MinT)：</b> <span style="color: #2563EB;">{mint:.1f}°C</span><br>
                        <b>日夜溫差：</b> {row['temp_diff']:.1f}°C
                    </div>
                    <div style="margin-top: 8px; font-size: 12px; color: #6B7280;">
                        💡 點選上方選單選擇「{region}」即可放大檢視轄下各縣市！
                    </div>
                </div>
                """
                folium.CircleMarker(
                    location=center_coords,
                    radius=15,
                    popup=folium.Popup(popup_html, max_width=260),
                    tooltip=f"{region}: 平均 {avg:.1f}°C (點擊查看詳情)",
                    color="#FFFFFF",
                    weight=2,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.88
                ).add_to(m)

                folium.map.Marker(
                    center_coords,
                    icon=folium.DivIcon(
                        html=f"""
                        <div style="
                            font-size: 11px;
                            font-weight: bold;
                            color: #1F2937;
                            background-color: rgba(255,255,255,0.85);
                            border-radius: 4px;
                            padding: 2px 6px;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
                            width: 65px;
                            text-align: center;
                            transform: translate(-32px, 14px);
                        ">{region}</div>
                        """
                    )
                ).add_to(m)

        else:
            # --- 模式 B: 深入下鑽特定分區，顯示轄下各縣市！ ---
            sub_counties = df_counties[
                (df_counties["regionName"] == active_view) & 
                (df_counties["dataDate"] == selected_date)
            ]

            for _, row in sub_counties.iterrows():
                county = row["countyName"]
                coords = COUNTY_COORDINATES.get(county)
                if not coords:
                    continue

                avg = row["avg_temp"]
                mint = row["mint"]
                maxt = row["maxt"]
                diff = row["temp_diff"]
                wx = row["weatherDesc"]
                emoji = get_weather_emoji(wx)
                color = get_color_by_temperature(avg)

                popup_html = f"""
                <div style="font-family: Arial, sans-serif; min-width: 175px;">
                    <h4 style="margin: 0 0 5px 0; color: #1E3A8A;">🏙️ {county}</h4>
                    <div style="font-size: 13px; line-height: 1.6;">
                        <b>所屬分區：</b> {active_view}<br>
                        <b>天氣現象：</b> {emoji} {wx}<br>
                        <b>平均溫度：</b> <span style="color: {color}; font-weight: bold;">{avg:.1f}°C</span><br>
                        <b>最高溫 (MaxT)：</b> <span style="color: #DC2626;">{maxt:.1f}°C</span><br>
                        <b>最低溫 (MinT)：</b> <span style="color: #2563EB;">{mint:.1f}°C</span><br>
                        <b>日夜溫差：</b> {diff:.1f}°C
                    </div>
                </div>
                """

                # 縣市圓圈標記
                folium.CircleMarker(
                    location=coords,
                    radius=16,
                    popup=folium.Popup(popup_html, max_width=260),
                    tooltip=f"{county} {emoji}: {mint:.0f}~{maxt:.0f}°C ({wx})",
                    color="#FFFFFF",
                    weight=3,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.9
                ).add_to(m)

                # 縣市名與天氣 Emoji 懸浮標籤
                folium.map.Marker(
                    coords,
                    icon=folium.DivIcon(
                        html=f"""
                        <div style="
                            font-size: 12px;
                            font-weight: bold;
                            color: #111827;
                            background-color: rgba(255,255,255,0.92);
                            border: 1px solid #D1D5DB;
                            border-radius: 5px;
                            padding: 2px 6px;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
                            width: 76px;
                            text-align: center;
                            transform: translate(-38px, 16px);
                        ">{emoji} {county}</div>
                        """
                    )
                ).add_to(m)

        # 渲染地圖
        st_folium(m, width="100%", height=520, returned_objects=[])

        # 圖例說明
        st.markdown("""
        <div class="legend-box">
            <b>🎨 氣溫色階標準：</b>
            <span style="color: #3B82F6; font-weight: bold;">●</span> &lt; 20°C (涼冷) &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #10B981; font-weight: bold;">●</span> 20°C ~ 25°C (舒適) &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #F59E0B; font-weight: bold;">●</span> 25°C ~ 30°C (偏暖) &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color: #EF4444; font-weight: bold;">●</span> &gt; 30°C (炎熱)
        </div>
        """, unsafe_allow_html=True)

        # 快速分區導覽快捷按鈕列 (當在全台總覽時)
        if active_view == "全台總覽":
            st.markdown("#### ⚡ 快速放大下鑽各大分區：")
            btn_cols = st.columns(len(all_regions))
            for i, r_name in enumerate(all_regions):
                with btn_cols[i]:
                    r_icon = REGION_VIEW_CONFIG[r_name]["icon"]
                    if st.button(f"{r_icon} {r_name[:2]}", key=f"btn_jump_{r_name}", use_container_width=True):
                        st.session_state["current_view_region"] = r_name
                        st.rerun()

        # 當處於分區放大下鑽模式時：顯示該分區各縣市對比數據！
        if active_view != "全台總覽":
            st.markdown("---")
            st.markdown(f"### 🏙️ {active_view} 各縣市詳細預報指標 ({selected_date})")
            
            sub_counties_display = df_counties[
                (df_counties["regionName"] == active_view) & 
                (df_counties["dataDate"] == selected_date)
            ].sort_values("maxt", ascending=False)

            # 縣市卡片橫向呈現
            card_cols = st.columns(len(sub_counties_display)) if len(sub_counties_display) <= 6 else st.columns(4)
            for idx, (_, c_row) in enumerate(sub_counties_display.iterrows()):
                col_target = card_cols[idx % len(card_cols)]
                with col_target:
                    c_emoji = get_weather_emoji(c_row['weatherDesc'])
                    col_target.metric(
                        f"{c_emoji} {c_row['countyName']}",
                        f"{c_row['avg_temp']:.1f}°C",
                        f"最高 {c_row['maxt']:.0f}°C / 最低 {c_row['mint']:.0f}°C",
                        help=f"天氣狀況：{c_row['weatherDesc']} | 日夜溫差：{c_row['temp_diff']:.1f}°C"
                    )

            # 縣市最高溫與最低溫比較圖
            st.markdown(f"#### 📊 {active_view} 各縣市最高溫與最低溫對比")
            bar_df = pd.melt(
                sub_counties_display,
                id_vars=["countyName"],
                value_vars=["maxt", "mint"],
                var_name="指標",
                value_name="氣溫"
            )
            bar_df["指標"] = bar_df["指標"].map({"maxt": "最高溫 MaxT", "mint": "最低溫 MinT"})

            bar_chart = alt.Chart(bar_df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("countyName:N", title="縣市名稱"),
                y=alt.Y("氣溫:Q", title="氣溫 (°C)", scale=alt.Scale(zero=False)),
                color=alt.Color(
                    "指標:N",
                    scale=alt.Scale(domain=["最高溫 MaxT", "最低溫 MinT"], range=["#EF4444", "#3B82F6"]),
                    title="指標"
                ),
                xOffset="指標:N",
                tooltip=["countyName", "指標", alt.Tooltip("氣溫:Q", format=".1f")]
            ).properties(height=300)

            st.altair_chart(bar_chart, use_container_width=True)

    # ==========================================
    # Tab 2: 一週趨勢圖 (支援分區與縣市級別)
    # ==========================================
    with tab_trend:
        st.subheader("未來一週氣溫走勢圖")

        trend_type = st.radio(
            "選擇分析維度：",
            ["📍 依地理分區 (課程標準)", "🏙️ 依個別縣市 (細部觀測)"],
            horizontal=True
        )

        if "地理分區" in trend_type:
            selected_r = st.selectbox("選擇分區：", options=all_regions, index=all_regions.index("中部地區") if "中部地區" in all_regions else 0)
            target_trend_df = df_regions[df_regions["regionName"] == selected_r].sort_values("dataDate").copy()
            unit_title = f"{selected_r} 未來一週"
        else:
            all_county_names = sorted(df_counties["countyName"].unique().tolist())
            selected_c = st.selectbox("選擇縣市：", options=all_county_names, index=all_county_names.index("臺中市") if "臺中市" in all_county_names else 0)
            target_trend_df = df_counties[df_counties["countyName"] == selected_c].sort_values("dataDate").copy()
            unit_title = f"{selected_c} 未來一週"

        # 指標摘要
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("本週最高溫", f"{target_trend_df['maxt'].max():.1f}°C")
        m2.metric("本週最低溫", f"{target_trend_df['mint'].min():.1f}°C")
        m3.metric("本週平均溫", f"{target_trend_df['avg_temp'].mean():.1f}°C")
        m4.metric("最大日溫差", f"{target_trend_df['temp_diff'].max():.1f}°C")

        # 折線圖
        st.markdown(f"#### 📈 {unit_title} 氣溫走勢圖")
        melted_trend = pd.melt(
            target_trend_df,
            id_vars=["dataDate"],
            value_vars=["maxt", "mint"],
            var_name="氣溫類型",
            value_name="溫度"
        )
        melted_trend["氣溫類型"] = melted_trend["氣溫類型"].map({"maxt": "最高氣溫 (MaxT)", "mint": "最低氣溫 (MinT)"})

        line_chart = alt.Chart(melted_trend).mark_line(point=True, strokeWidth=3).encode(
            x=alt.X("dataDate:N", title="日期 (Date)"),
            y=alt.Y("溫度:Q", title="氣溫 (°C)", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "氣溫類型:N",
                scale=alt.Scale(domain=["最高氣溫 (MaxT)", "最低氣溫 (MinT)"], range=["#DC2626", "#2563EB"]),
                title="指標"
            ),
            tooltip=["dataDate", "氣溫類型", alt.Tooltip("溫度:Q", format=".1f")]
        ).properties(height=340).interactive()

        st.altair_chart(line_chart, use_container_width=True)

        # 資料表格
        st.markdown(f"#### 📋 {unit_title} 詳細預報數據表格")
        cols_to_show = ["dataDate", "mint", "maxt", "avg_temp", "temp_diff"]
        col_names = ["日期 (Date)", "最低溫 MinT (°C)", "最高溫 MaxT (°C)", "平均溫 (°C)", "日溫差 (°C)"]
        if "weatherDesc" in target_trend_df.columns:
            cols_to_show.append("weatherDesc")
            col_names.append("天氣現象描述")

        disp_df = target_trend_df[cols_to_show].copy()
        disp_df.columns = col_names
        st.dataframe(disp_df, use_container_width=True, hide_index=True)

    # ==========================================
    # Tab 3: 資料庫檢視
    # ==========================================
    with tab_data:
        st.subheader("SQLite 資料庫內容 (data.db)")
        table_choice = st.radio("選擇要查詢的資料表：", ["TemperatureForecasts (分區預報 - 課程規格)", "CountyForecasts (全台縣市詳細預報)"], horizontal=True)

        if "TemperatureForecasts" in table_choice:
            st.write(f"📊 目前共有 {len(df_regions)} 筆分區預報資料：")
            st.dataframe(df_regions, use_container_width=True, hide_index=True)
        else:
            st.write(f"📊 目前共有 {len(df_counties)} 筆全台縣市詳細預報資料：")
            st.dataframe(df_counties, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
