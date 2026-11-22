# 3202cb1 預設啟動與 Chrome 驗證｜2026-11-08

## 自動測試

- `.venv-gpu-test\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_*.py`：執行 110 項，失敗，輸出 18 個 error。`tests/test_translation_bench.py` 在模組匯入時直接把 stub 放進 `sys.modules['models']`，未還原；後續測試因此取得缺少 `app`、`METRICS`、`create_translator` 等屬性的假模組，且 `reload` 報 module not in sys.modules。這是明確的測試隔離問題，不能因單獨通過就說完整測試通過。
- 分別在獨立 Python 程序執行先前受影響的 `test_asr_echo_retry.py`、`test_breath_cut.py`、`test_numeric_translation.py`、`test_translation_engine.py`、`test_speed_metrics.py`：各 9、9、8、3、6 項通過。未逐一重跑所有受影響檔案，因此不能排除其他失敗原因。
- `node --test tests/*.test.mjs`：71 項通過、0 失敗。
- 完整日誌在共用工作區 `whatsub-prototype/tmp/mosalive-3202-verification/`。測試期間輸出的 FLEURS 下載訊息屬測試 mock，沒有下載模型。

## 預設與備案啟動

- `START_WINDOWS.bat`，僅設定 `MOSA_NO_BROWSER=1` 和 offline 環境：記錄印出 `ASR model: large-v3-turbo` 與使用者既有快取 snapshot 路徑；health ready、ASR loaded、翻譯可用，asr=large-v3-turbo、translation=gemma3:4b、soft_cut_ms=3500、restart_required=false。`ollama ps` 顯示 Gemma 100% GPU、context 2048；暖載後整卡 5744／8188 MiB（含其他程序）。
- 停止後執行 `START_WINDOWS_SMALL_QWEN.bat`：health ready，asr=small、translation=qwen2.5:7b、soft_cut_ms=3500；`ollama ps` 顯示 qwen 100% GPU。兩次實際啟動日誌、health、Ollama 與 VRAM 快照均保存在上述工作區。

## Chrome／Twitch

再次以預設批次檔啟動 ready，使用 computer use 在真實 Chrome 開啟指定 Twitch VOD 的 11:48 網址。影片載入並播放至約 12:01 後暫停。Chrome 視窗處於最小化；computer use 取得原生視窗時回報 window minimized，嘗試切換可操作視窗時應用程式存取核准逾時，無法操作 Chrome 工具列及擴充功能的「翻譯此分頁」。沒有繞過 Chrome 擷取手勢，也沒有聲稱成功擷取。

因此未完成 10 分鐘擷取，VRAM 峰值、全程 Ollama GPU 比率、說完／開口到定稿 p50/p95、掉音及錯誤、session 統計和與舊設定的可比結果均**未驗證**。已有的暖載快照不是這些數據。需要 Chrome 原生視窗可被操作後重試。

## 清理

本輪預設服務、備案服務和由它們啟動的程序樹均已停止；確認 8787、8790、11434 沒有監聽。沒有修改預設、批次檔或使用者既有未提交修改；僅本機提交本報告，不 push。