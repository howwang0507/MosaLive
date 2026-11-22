# 韓文與翻譯更新（2026-09-08）

## 已套用

- Whisper small 的 language=None 本來就包含韓文自動辨識，本次新增韓文音訊端到端驗證、測試網頁韓文選項、字幕選項標示。仍保留英文、日文及其他 Whisper 語言。
- 預設翻譯改成 qwen2.5:7b；保留 MOSA_NMT_MODEL 覆寫能力。安裝腳本同步下載 7B。
- 最後一則使用者訊息只放待翻譯原文，前文、詞庫與校對草稿作為獨立參考訊息，避免重譯前文。提示要求保留否定、數量、時態，避免添加行動或解釋。
- 增加英文 ultimate、teammate 及韓文 방송、궁극기、재사용 대기시간 詞庫。詞庫沿用 ja/zh 欄位格式，ja 現在是通用來源文字欄位。
- 啟動批次檔優先使用本機已驗證的 .venv-gpu-test，啟動器將該環境的 CUDA DLL 目錄加入子程序 PATH；找不到時沿用原來的 .venv-win。

## 模型比較

使用同一組 8 句自編英日韓診斷句，比較 3B、7B，另測試 7B 搭配新版提示與詞庫。這是人工檢查的範例集，不是正式翻譯準確率或盲測。

明顯改善範例：

- 韓文「어제는 졌지만 오늘은 아직 한 번도 지지 않았어요.」：3B 回覆「雖然昨天已經開始了，但今天還沒有停止過。」；新版 7B 回覆「昨天輸了，但今天還沒有輸過。」
- 日文問候直播句：3B 留下大段日文；新版 7B 完整轉成「各位，你好。今天，我將把日語的直播翻譯成中文。」
- 韓文直播句：新版搭配詞庫，將 방송 翻成「直播」。

仍有限制：部分命令句的語氣、等待隊友的表達不夠自然，模型仍可能改寫細節。不能由 8 句測試宣稱普遍提高某個百分比。

原始結果：translation-eval-qwen2.5-3b.json、translation-eval-qwen2.5-7b.json、translation-eval-qwen2.5-7b-current.json。
可重跑 windows/translation_eval.py qwen2.5:7b --current。

## GPU 與完整流程

Whisper small 和 Qwen2.5 7B 同時載入，Ollama 顯示 100% GPU；本次觀察顯存約 6.3GB / 8GB（隨其他程式改變）。
暖機後三次中位数，音訊送出後到最終結果，包含 HTTP、不含收音等待及畫面渲染：

| 合成音訊 | 辨識＋翻譯 | 僅原文 |
| --- | --- | --- |
| 日文 | 758ms | 185ms |
| 英文 | 715ms | 172ms |
| 韓文（6.384 秒） | 678ms | 198ms |

原始結果：benchmark-live-multilingual.json。不同時段負載不同，不能和先前數字直接當作模型速度提升的證據。相同文字診斷句比較中，7B 的翻譯比 3B 慢。

韓文測試原句：여러분 안녕하세요. 오늘은 한국어 방송을 중국어로 번역합니다.
韓文檔案以 edge-tts 7.2.8 的 ko-KR-SunHiNeural 合成，轉為 16kHz mono PCM16 WAV。只有這句自編文字送至線上 TTS；字幕辨識與翻譯仍在本機執行，線上 TTS 並非應用執行依賴。

27 項程式測試通過（20 Node、7 Python）；英日韓音訊串流 API 與韓文 WAV 網址實测成功。Chrome 擴充套件版本 0.1.6，需重新載入擴充套件並重新整理 Twitch。

## 模型來源

- https://ollama.com/library/qwen2.5:7b
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct

新模型下載約 4.7GB。原有 3B 留在硬碟，可用 MOSA_NMT_MODEL=qwen2.5:3b 回退；不會自動在顯存不足時偷偷切成 3B。
