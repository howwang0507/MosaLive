# MosaLive 桌面版（Windows App）

撰寫日期：2026-11-22。版本 0.4.0。

## 這是什麼

把原本的「Chrome 擴充功能＋本機服務＋.bat 啟動檔」包成一個 Windows 程式：

- **控制台視窗**：環境檢查、一鍵安裝缺少的元件、啟動／停止字幕服務、字幕設定。
- **字幕框**：永遠在最上層的透明視窗，疊在任何程式上（Chrome、Edge、YouTube App、會議軟體、本機影片）。可拖曳、調整大小，鎖定後滑鼠可以點穿。
- **聲音來源**：電腦正在播放的聲音（Windows 系統音訊 loopback），不再限定 Chrome 分頁。
- **系統匣圖示**：關閉視窗後字幕繼續運作；從右下角圖示打開控制台或結束程式。

辨識與翻譯仍然是原本的本機服務（`windows/launch.py` → `windows/models.py` 與 `server.mjs`），模型、VAD、斷句與預設值都沒有改：Faster-Whisper large-v3-turbo＋Ollama gemma3:4b＋3.5 秒軟切點。Chrome 擴充功能照舊可以使用，兩者共用同一個服務。

## 給使用者：安裝與第一次使用

1. 執行 `MosaLive-Setup-0.4.0.exe`（安裝到使用者自己的資料夾，不需要系統管理員）。
2. 打開 MosaLive，看「環境檢查」：
   - 缺 Python 3.11 或 Ollama：按「安裝」，會用 Windows 內建的 winget 安裝；沒有 winget 時會打開官方下載頁。
   - 缺 Python 環境、GPU 元件、翻譯模型、語音辨識模型：按「一鍵安裝缺少的項目」。下載量合計約數 GB，每一步開始前都會先詢問。
3. 上方顯示「字幕服務已就緒」後，播放影片或直播，按「開始字幕」。
4. 把字幕框拖到想要的位置，勾選「鎖定字幕框」。

快速鍵：`Alt+Shift+S` 開始／停止字幕，`Alt+Shift+L` 鎖定／解鎖字幕框，`Alt+Shift+D` 切換雙字幕／繁中／原文。

關閉 App 時預設會停止它啟動的字幕服務，釋放顯示卡記憶體；Ollama 是共用程式，會繼續執行（和 `START_WINDOWS.bat` 相同）。

## 給開發者：從原始碼執行與打包

- 從原始碼執行：雙擊 `START_DESKTOP_APP.bat`（第一次會 `npm install`）。開發模式直接使用專案裡現有的 `.venv-gpu-test` 或 `.venv-win`。
- 打包安裝檔：雙擊 `BUILD_DESKTOP_APP.bat`，會先跑單元測試，再輸出 `dist\desktop\MosaLive-Setup-<版本>.exe`。
- 單元測試：`cd desktop` 後 `npm test`；啟動器的 `MOSA_NODE` 測試在 `tests/test_launcher_node.py`。

### 檔案位置

| 內容 | 位置 |
|---|---|
| App 程式 | `desktop/`（`main.js` 主程式、`lib/` 服務管理與檢查、`renderer/` 畫面） |
| 安裝後的服務程式 | 安裝資料夾 `resources\runtime\`（`server.mjs`、`web/`、`windows/*.py` 等） |
| 安裝版的 Python 環境 | `%LOCALAPPDATA%\MosaLive\python`（更新 App 不會刪除） |
| 服務紀錄 | `%LOCALAPPDATA%\MosaLive\logs\service.log`（超過 2 MB 自動換檔） |
| 設定 | `%APPDATA%\MosaLive\settings.json` |
| 語音辨識模型 | 使用者的 Hugging Face 快取（`launch.py` 原本就會找這裡） |

### 設計重點

- **不重寫服務**：App 直接執行 `windows/launch.py`，沿用它的 Ollama 檢查、模型選擇、當機重啟與預設值。唯一的修改是 `launch.py` 讀取 `MOSA_NODE`，讓 `server.mjs` 改用 App 內建的 Node（Electron），使用者不必另外安裝 Node.js。
- **字幕管線共用**：App 的頁面直接載入 `web/engine.js`、`web/live-client.js`、`web/worklet.js`，與瀏覽器測試頁是同一份程式。
- **不改橋接服務的安全檢查**：`server.mjs` 只接受自己的網址與 Chrome 擴充功能。App 的請求由主程式轉送（`mosalive://app/api/...` → `127.0.0.1:8787`），只開放 `/live/frame` 與 `/health` 兩個端點。
- **停止服務不會關掉 Ollama**：先列出 `launch.py` 的子程序，結束它們（Ollama 除外），再結束 `launch.py`。
- **不自動下載模型**：所有下載都要使用者按按鈕並確認。

## 已驗證與尚未驗證

已驗證（2026-11-22，Linux 雲端環境）：

- `desktop` 單元測試 21 項通過（路徑、環境檢查、安裝順序、服務狀態、停止服務不關 Ollama、設定檔防呆、網址白名單、字幕顯示邏輯）。
- `tests/test_launcher_node.py` 2 項通過。
- 用 Electron 實際開啟 App，接上**模擬的**橋接服務：控制台、環境檢查、測試音訊 → 字幕框顯示雙字幕、切換繁中、調整字級、鎖定、停止字幕都正常，畫面沒有錯誤訊息；打包後的版本也測過同一流程。

尚未驗證（需要在 Windows 實機測）：

- Windows 系統音訊（loopback）擷取、透明字幕框疊在全螢幕影片上。
- 用真實模型跑完整流程：App 啟動 `launch.py`、模型載入、延遲與顯示卡記憶體。
- winget 安裝 Python／Ollama、建立 Python 環境、下載模型的實際過程。
- 安裝檔沒有程式碼簽章，第一次執行時 Windows SmartScreen 可能出現警告，需要按「其他資訊 → 仍要執行」。

## 已知限制

- 擷取的是「整台電腦的聲音」，通知音、背景音樂也會被辨識；看直播時建議關掉其他聲音。
- 仍需要 NVIDIA 顯示卡（建議 8 GB）。App 目前沒有提供 CPU 模式（`START_WINDOWS_CPU_ASR.bat` 可以用 CPU，但非常慢）。
- 只有 Windows 版，沒有手機版。
