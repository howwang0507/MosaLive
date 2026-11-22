# MosaSub Live Windows 安裝與測試指南

本文件適用於 MosaSub Live 0.3.6。專案是原始碼形式的本機原型，不是免安裝 EXE。

## 1. 建議環境

- Windows 10 22H2 或 Windows 11，64 位元。
- Python 3.11、Node.js 22 以上、Google Chrome、Ollama。
- NVIDIA 顯卡；目前主要測試設備為 RTX 4060 Ti 8GB。
- Faster-Whisper CUDA 路徑需要 CUDA 12 的 cuBLAS 與 cuDNN 9。
- 建議至少 32 GB 系統記憶體與 20 GB 可用磁碟空間，實際用量取決於模型與其他程式。

Ollama 能使用 NVIDIA GPU，不代表 Faster-Whisper 所需的 CUDA DLL 已齊全。若缺少 `cublas64_12.dll` 或 `cudnn64_9.dll`，請先依 NVIDIA 官方方式安裝並重新開啟終端機。

## 2. 首次安裝

1. 將專案放在一般資料夾，不要直接在 ZIP 壓縮檔內執行。
2. 確認 Ollama 已安裝並可在背景啟動。
3. 雙擊 `INSTALL_WINDOWS.bat`。
4. 安裝器會建立 Python 環境、安裝依賴，並下載設定的 Ollama 翻譯模型。模型權重不會提交到 Git。
5. 安裝完成後執行 `CHECK_ENV.bat`。CUDA 裝置數應大於零，8787 與 8790 連接埠不應被其他程式占用。

若只想排查 CUDA，可用 `START_WINDOWS_CPU_ASR.bat` 讓語音辨識改走 CPU；翻譯模型由 Ollama 自行決定裝置。CPU 模式較慢，不代表 GPU 驗收成功。

## 3. 啟動服務

1. 雙擊 `START_WINDOWS.bat`。
2. 啟動器會檢查 Ollama 與設定模型，接著啟動 Python 推論服務（8790）及 Node 橋接服務（8787）。
3. 看到 `READY: http://localhost:8787` 後再開始收音。
4. 瀏覽器可開啟 `http://localhost:8787` 使用本地測試頁。
5. 在啟動視窗按 `Ctrl+C` 可停止本次啟動的服務；獨立執行的 Ollama 不會因此關閉。

重複執行啟動器時，它會辨識既有的 MosaSub 健康端點並避免重複載入模型。若磁碟程式碼已變更，健康資訊會顯示需要重啟。

## 4. 載入 Chrome 擴充套件

1. Chrome 開啟 `chrome://extensions`。
2. 開啟右上角「開發人員模式」。
3. 點擊「載入未封裝項目」，選擇專案內的 `extension` 資料夾。
4. 開啟並播放影音分頁。
5. 點擊 MosaSub 圖示，選擇目標分頁，前往該分頁後按「翻譯此分頁」。

Chrome 的 `tabCapture` 必須由使用者在目標分頁主動點擊啟動，程式無法自動略過這項安全限制。更新擴充套件程式後，要在擴充功能頁按「重新載入」，再重新整理影音分頁。

## 5. 使用建議

- 單一語言直播可選「鎖定英文／日文／韓文」。鎖定模式會直接設定 Faster-Whisper 的 `language` 參數。
- 直播可能混用語言時，選「自動多語」。
- 只想閱讀中文時選「僅繁中」；語言學習可選「雙字幕」。
- 覺得文字跳動時開啟「只顯示定稿」。
- 字幕遮住播放器控制時，可移動字幕、調整透明度或開啟點擊穿透；右側 × 可停止收音並關閉字幕框。
- 同一分頁存在多個播放器時，請暫停不需要的播放器，否則聲音會混在一起。

## 6. 環境與真模型檢查

`CHECK_ENV.bat` 檢查 Python、Node.js、Ollama、連接埠、服務 PID、CUDA 裝置與擴充套件版本。

`CHECK_REAL_MODEL.bat` 會使用專案內的合成音訊，真正呼叫 Faster-Whisper 與 Ollama。通過代表本機推論路徑可運作，不代表真人直播準確率，也不包含完整收音與 VAD 等待時間。

## 7. 常見問題

### 顯示「尚未產生字幕」

確認播放器有聲音、分頁沒有靜音、後端健康頁顯示 ready，並查看面板是「低音量」、「持續收音」還是「處理已暫停」。背景音樂可能有能量但不會被 VAD 判定為人聲。

### 字幕完全停止

先停止收音，再重新啟動同一分頁。仍無法恢復時，關閉舊啟動視窗、重新執行 `START_WINDOWS.bat`，然後重新整理影音分頁。

### Chrome 顯示 Out of Memory

這通常是 Chrome／影音頁面或整體 RAM、VRAM 壓力，不等於 MosaSub Python 一定洩漏。先關閉不需要的影音分頁與高負載程式，查看工作管理員各程序私有記憶體及 `nvidia-smi` 整卡顯存，再判斷來源。

### 選了英文仍出現錯字

語言鎖定只固定 Whisper 解碼語言，不能修復噪音、口音、同音詞或不完整斷句。選錯語言時，其他語言會被硬辨識成所選語言。若原文正確但中文錯誤，才屬翻譯層問題。

### 玩遊戲時延遲增加

遊戲、Faster-Whisper 和 Ollama 會競爭 RTX 顯存及算力。可降低遊戲材質設定、關閉不必要的 GPU 程式，或改用較輕的翻譯模型。把 Chrome 影片解碼交給內顯可降低部分獨顯負載，但不會直接提高翻譯準確率。

## 8. 驗收邊界

- 合成音訊測試用於驗證程式路徑與錯誤處理，不等同真人直播品質。
- 單段模型時間不等同停句到字幕出現的端到端延遲。
- 工作管理員與 `nvidia-smi` 顯示的整卡用量包含遊戲、Chrome 與其他程式。
- 最新版仍需進行真人 Twitch 長播、廣告切換、換畫質與全螢幕操作驗收。

詳細技術資料見 [ARCHITECTURE.md](ARCHITECTURE.md) 與 [docs/UPDATE_0.3.6.md](docs/UPDATE_0.3.6.md)。
