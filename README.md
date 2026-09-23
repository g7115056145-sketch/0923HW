# Taiwan Weather Forecast 台灣氣象預報互動系統 🌤️

本專案依據 **「AI 創新微課程 Taiwan Weather Forecast 從氣象資料到互動式天氣預報應用」** 課程架構打造，串接中央氣象署（CWA）Open Data 開放資料平臺，將氣溫預報資料結構化儲存至 SQLite 資料庫，並運用 Streamlit 與 Folium 建立現代化互動式天氣儀表板。

---

## 📌 技術架構與特色

- **API 資料擷取（步驟 3~6）**：使用 Python `requests` 串接中央氣象署未來一週天氣預報 API（`F-C0032-003`），解析 JSON 結構並提取全台各大分區最高溫（`MaxT`）與最低溫（`MinT`）。
- **資料清洗與結構化（步驟 7）**：使用 `pandas` 整理時間序列資料與計算日溫差、平均溫。
- **SQLite 資料庫儲存（步驟 8~10、步驟 20）**：
  - 建立 `data.db` 資料庫與 `TemperatureForecasts` 資料表。
  - 設計 `UNIQUE(regionName, dataDate)` 約束與 `INSERT OR REPLACE` 機制，確保重複執行時不重複插入資料。
  - 內建 SQL 驗證查詢。
- **Streamlit 視覺化 Web App（步驟 11~16）**：
  - 地區下拉式選單切換（北部地區、中部地區、南部地區、東北部地區、東部地區、東南部地區等）。
  - 一週最高溫與最低溫互動折線圖（雙線比較、點提示 Tooltip）。
  - 詳細數據表格與統計指標小卡（本週最高溫、最低溫、平均溫、日溫差）。
- **Folium 台灣地圖視覺化（步驟 17~19）**：
  - 日期選擇切換器：動態觀察指定日期的全台氣溫分佈。
  - 氣溫分級著色標記：
    - 🔵 `< 20°C`（寒冷/涼爽）
    - 🟢 `20°C ~ 25°C`（舒適宜人）
    - 🟠 `25°C ~ 30°C`（溫暖偏熱）
    - 🔴 `> 30°C`（炎熱高溫）
  - 互動 Popup：點擊地圖標記即時顯示分區名稱、預報最高溫、最低溫與平均溫。

---

## 🗄️ 資料庫設計 (Database Schema)

資料庫檔案名稱：`data.db`  
資料表名稱：`TemperatureForecasts`

```sql
CREATE TABLE IF NOT EXISTS TemperatureForecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regionName TEXT NOT NULL,
    dataDate TEXT NOT NULL,
    mint REAL NOT NULL,
    maxt REAL NOT NULL,
    UNIQUE(regionName, dataDate)
);
```

---

## 🚀 快速開始

### 1. 安裝所需套件
```powershell
pip install -r requirements.txt
```

### 2. 執行資料擷取並初始化資料庫
```powershell
python fetch_data.py
```
> 執行完畢後會自動於根目錄產出 `data.db`，並在終端機輸出 SQL 驗證結果。

### 3. 啟動 Streamlit 互動 Web 應用
```powershell
python -m streamlit run app.py
```
> 終端機會顯示本地伺服器網址（通常為 `http://localhost:8501`），瀏覽器將自動開啟互動儀表板。
