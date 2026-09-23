# Taiwan Weather Forecast 台灣氣象預報互動系統 🌤️

本專案依據 **「AI 創新微課程 Taiwan Weather Forecast 從氣象資料到互動式天氣預報應用」** 課程架構打造，串接中央氣象署（CWA）Open Data 開放資料平臺，將氣溫預報資料結構化儲存至 SQLite 資料庫，並運用 Streamlit 與 Folium 建立現代化互動式天氣儀表板。

---

## 📌 技術架構與特色亮點

- **API 資料擷取（步驟 3~6）**：
  - 使用 Python `requests` 串接中央氣象署未來一週天氣預報 API：
    - `F-C0032-003`：全台主要分區預報（北部、中部、南部、東北部、東部、東南部、離島等）。
    - `F-C0032-005`：全台 22 縣市細緻逐日預報與天氣現象描述（`Wx`）。
- **資料清洗與結構化（步驟 7）**：使用 `pandas` 整理時間序列資料，計算日溫差與每日平均溫。
- **SQLite 資料庫儲存（步驟 8~10、步驟 20）**：
  - 建立 `data.db` 資料庫，包含課程規範之 `TemperatureForecasts` 表與擴充之 `CountyForecasts` 表。
  - 設計 `UNIQUE` 約束與 `INSERT OR REPLACE` 機制，確保重複執行時不重複插入資料。
- **🗺️ 地圖放大與分區縣市下鑽（進階優化）**：
  - **全台宏觀模式**：一覽全台各大地理分區之氣候分佈。
  - **分區深入模式（Zoom In）**：點選任一分區（例如「中部地區」），地圖自動平移放大，切換呈現該分區轄下各縣市（臺中市、彰化縣、南投縣、雲林縣、嘉義市、嘉義縣）的標記、天氣圖示、氣溫指標與橫向對比圖表。
  - 提供快捷「🔙 返回全台總覽」按鈕。
- **Streamlit 視覺化 Web App（步驟 11~19）**：
  - 一週最高溫與最低溫互動折線圖（支援分區與個別縣市維度切換）。
  - 詳細數據表格與統計指標小卡（本週最高溫、最低溫、平均溫、日溫差）。
  - 氣溫四級顏色視覺化（藍 <20°C、綠 20~25°C、橘 25~30°C、紅 >30°C）。

---

## 🗄️ 資料庫設計 (Database Schema)

資料庫檔案名稱：`data.db`

### 1. 分區預報資料表（課程標準）
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

### 2. 縣市細部預報資料表（下鑽放大功能使用）
```sql
CREATE TABLE IF NOT EXISTS CountyForecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    countyName TEXT NOT NULL,
    regionName TEXT NOT NULL,
    dataDate TEXT NOT NULL,
    mint REAL NOT NULL,
    maxt REAL NOT NULL,
    weatherDesc TEXT,
    UNIQUE(countyName, dataDate)
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
> 執行完畢後會自動於根目錄產出 `data.db`，並在終端機輸出抓取與寫入筆數。

### 3. 啟動 Streamlit 互動 Web 應用
```powershell
python -m streamlit run app.py
```
> 終端機會顯示本地伺服器網址（通常為 `http://localhost:8501`），瀏覽器將自動開啟互動儀表板。
