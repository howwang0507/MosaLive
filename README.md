# MosaSub Live

MosaSub Live 是 Windows 本機執行的瀏覽器即時跨語字幕原型。使用者在 Chrome 選擇正在播放的分頁後，系統擷取該分頁音訊，在本機完成人聲斷句、語音辨識與繁體中文翻譯，最後把字幕直接疊加在原播放器上。

目前版本為 **0.3.6**，主要針對英文、日文與韓文直播。預設使用 Faster-Whisper large-v3-turbo（CUDA `int8_float16`）、Ollama gemma3:4b 與 3.5 秒軟切點；先前的 Faster-Whisper small＋Ollama qwen2.5:7b 保留為備用啟動檔。模型、音訊與翻譯流程都在本機執行；Twitch、YouTube 等影音來源本身仍需要網路。

## 下載桌面版（MosaLive App）

不想自己架設的話，可以直接下載 Windows 安裝檔：到本頁右側的 **Releases**，下載最新版的 `MosaLive-Setup-<版本>.exe`。

- 需要：Windows 10／11 64 位元、NVIDIA 顯示卡（建議 8 GB 以上）、約 15 GB 可用空間與網路（第一次要下載模型）。
- 安裝後打開 MosaLive，依「環境檢查」按「一鍵安裝缺少的項目」，等上方顯示「字幕服務已就緒」，再按「開始字幕」。
- 安裝檔沒有數位簽章，Windows 可能跳出 SmartScreen 警告：按「其他資訊」→「仍要執行」。
- 聲音與文字都在你的電腦上處理，不會上傳雲端。字幕由機器產生，可能有錯。

詳細說明：[docs/DESKTOP_APP.md](docs/DESKTOP_APP.md)

## 目前功能

- 指定 Chrome 影音分頁收音，不需要擷取整個桌面或麥克風。
- 自動多語辨識，或鎖定英文、日文、韓文。鎖定模式會將指定語言代碼直接交給 Faster-Whisper；若內容可能切換語言，應使用自動多語。
- 僅繁中、僅原文及原文＋繁中三種字幕模式。
- 階梯式 Silero VAD、暫定字幕、定稿字幕與只顯示定稿選項。
- 字級、背景透明度、文字描邊、字幕位置、點擊穿透與依字數自動停留。
- 播放器跳播、換片、長時間停滯與來源重建時清除舊音訊，避免恢復後出現過期字幕。
- Prompt 歷史淨化、靜態術語庫、直播 `chat` 語境修正，以及數字、否定詞、漏譯與中英混雜檢查。
- 兩包並發上限、16 秒音訊緩衝、16 筆翻譯快取及有限重試，避免長播工作無界累積。
- 服務健康檢查、每分鐘統計、錯誤回報及翻譯失敗時保留原文。
- 快捷鍵：`Alt+S` 開始／停止、`Alt+C` 清除字幕、`Alt+D` 切換字幕語言。

說話者辨識已移除。實播中辨識準確度不足，額外計算與畫面標籤也無法提供可靠價值。

## 快速開始

1. 安裝 Python 3.11、Node.js 22 以上、Ollama、Chrome，以及 Faster-Whisper CUDA 所需的 CUDA 12／cuDNN 9。
2. 執行 `INSTALL_WINDOWS.bat` 安裝 Python 依賴，並下載 gemma3:4b、qwen2.5:7b 與 large-v3-turbo（約 1.6 GB）。
3. 執行 `CHECK_ENV.bat` 檢查版本、連接埠與 CUDA；需要真模型抽測時執行 `CHECK_REAL_MODEL.bat`。
4. 執行 `START_WINDOWS.bat`，等候畫面顯示 `READY`。
5. 開啟 `chrome://extensions`，啟用開發人員模式，選擇「載入未封裝項目」，載入本專案的 `extension` 資料夾。
6. 開啟並播放 Twitch、YouTube 或其他影音分頁，點擊 MosaSub 圖示，再按「翻譯此分頁」。

### 啟動檔

| 檔案 | 辨識 | 翻譯 | 用途 |
| --- | --- | --- | --- |
| `START_WINDOWS.bat` | large-v3-turbo | gemma3:4b | 預設；本機找不到 turbo 時自動改用 small，不會自動下載 |
| `START_WINDOWS_SMALL_QWEN.bat` | small | qwen2.5:7b | 先前預設，turbo 或 gemma 不可用時使用 |
| `START_WINDOWS_CPU_ASR.bat` | small（CPU） | gemma3:4b | 沒有可用的 NVIDIA 顯卡 |

三個啟動檔都使用 3.5 秒軟切點；`START_WINDOWS_LOW_LATENCY.bat` 保留給舊捷徑，行為與預設相同。

修改擴充套件程式後，必須在 `chrome://extensions` 按「重新載入」，並重新整理影音分頁。Chrome 的 `tabCapture` 安全規則要求使用者主動點擊擴充套件，程式無法在背景自行取得分頁音訊權限。

完整安裝與排錯方式請見 [WINDOWS_README.md](WINDOWS_README.md)。

## 辨識模式

| 選項 | 實際行為 | 適用情境 |
| --- | --- | --- |
| 自動多語 | Faster-Whisper 使用 `language=None` 自動判斷 | 多語聊天或語言可能切換 |
| 鎖定英文 | Faster-Whisper 使用 `language="en"` | 內容主要為英文 |
| 鎖定日文 | Faster-Whisper 使用 `language="ja"` | 內容主要為日文 |
| 鎖定韓文 | Faster-Whisper 使用 `language="ko"` | 內容主要為韓文 |

鎖定語言是 Whisper 的解碼設定，不是字元過濾器。模糊音訊、外語人名或背景音仍可能產生誤字；選錯語言時，模型會嘗試把其他語言硬辨識成所選語言。

## 本機架構

```text
Chrome tabCapture
  → AudioWorklet（16 kHz 單聲道）
  → Node 8787（HTTP／NDJSON 橋接）
  → Python 8790（Silero VAD＋Faster-Whisper）
  → TranslationEngine
  → Ollama gemma3:4b
  → 品質檢查
  → 原分頁 DOM Overlay
```

播放器發生跳播、換片或來源重建時，前端會重設 AudioWorklet、增加結果世代編號並建立新後端 Session，使舊批次回呼失效。詳見 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 已驗證範圍

- RTX 4060 Ti 8GB 本機以 FLEURS 英文 126 句重播比較（每組各一次）：large-v3-turbo＋gemma3:4b＋3.5 秒軟切的英文辨識 WER 為 8.25%（原 small＋qwen2.5:7b 預設 16.31%），翻譯輸出異常候選 0 句（turbo＋qwen 為 14 句），說完到定稿中位數約 1.1 秒，重播中顯存抽樣峰值約 6.1／8.2 GB。這是朗讀素材的單次結果，尚未完成真人直播與 Chrome 實際擷取驗收；詳見 docs/codex-gpu-de-2026-11-08.md 與 docs/codex-gpu-h-2026-11-08.md。自訂 MOSA_ASR_MODEL 或 MOSA_NMT_MODEL 時，請以健康檢查回報的實際模型解讀結果。
- 單段驗證曾觀察辨識約 337 ms、翻譯約 808 ms。這是模型計算時間，不包含收音與 VAD 等待，也不是直播準確率。
- 英、日、韓鎖定模式已用既有合成音訊確認請求標頭會到達 Faster-Whisper，且結果回報指定語言。
- 目前自動化檢查涵蓋字幕顯示、設定保存、音訊重送、Session 重設、Prompt 防重複、翻譯降級與語言鎖定。
- 歷史版本完成過 60 分鐘監測；目前程式仍需再做最新版真人 Twitch 長播驗收，才能更新長播品質結論。

## 已知限制

- 收音單位是整個分頁；同一分頁的多個播放器會被混合。
- Twitch 以外網站尚未全部完成真人實播驗收，不能宣稱所有網站皆相容。
- Whisper 對口音、背景音、同音詞與專有名詞仍可能誤辨（small 比 large-v3-turbo 更明顯），翻譯模型無法可靠修復錯誤原文。
- 遊戲、Chrome、Whisper 與 Ollama 可能共用顯卡資源。資源不足會增加延遲或造成降級，但不會直接改變模型能力。
- CTranslate2 翻譯介面目前只是備援骨架，尚未配置可用的 NMT 模型與 tokenizer。
- 臺語、客語與族語後續使用公司既有模型；本儲存庫未包含權重，也尚未完成介接。

## 文件索引

- [WINDOWS_README.md](WINDOWS_README.md)：安裝、啟動、Chrome 載入與排錯。
- [ARCHITECTURE.md](ARCHITECTURE.md)：資料流、排程、重設與記憶體上限。
- [docs/UPDATE_0.3.6.md](docs/UPDATE_0.3.6.md)：目前版本變更與驗證界線。
- [docs/PROMPT_FLUSH_ENGINE_UPDATE.md](docs/PROMPT_FLUSH_ENGINE_UPDATE.md)：Prompt 防幻覺、Flush 與翻譯介面。
- [docs/BOSS_REQUIREMENTS_AUDIT.md](docs/BOSS_REQUIREMENTS_AUDIT.md)：會議需求完成狀態。
- [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)：交付與驗收範圍。
- [docs/MosaSub_Live_校園組作品提案規劃書_20260913.docx](docs/MosaSub_Live_校園組作品提案規劃書_20260913.docx)：依官方格式整理的匿名評審閱讀版。
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)：第三方元件與授權資訊。

## 隱私與授權

一般收音不保存音訊。只有使用者主動回報錯誤時，最近字幕與修正內容才會存入 Chrome 本機儲存，最多 30 筆，不會由本專案自動上傳。

模型權重、Python、Node.js、Ollama、CUDA DLL 與其他公司專案不包含在本儲存庫。第三方程式和模型必須依各自授權使用；本專案不把開源模型宣稱為自行訓練。
