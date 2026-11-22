# 開源研究與第一輪改善（2026-09-08）

## 參考來源

- [Whisper-Streaming](https://github.com/ufal/whisper_streaming)，commit `6da90b44b7e50d79695e68166d2a2c7609c75abb`，MIT。檢視 HypothesisBuffer.flush：對連續兩次辨識的共同前綴提交定稿。尚未導入此演算法；需要重複辨識、音訊重疊及定稿去重，不能只縮短現有分段。
- [livetl](https://github.com/kallyas/livetl)，commit `6dd52d37cd263cb02e420ad2f82ba97eba878184`。檢視 vad.py、asr.py、mt.py：人聲偵測、停頓邊界、長句軟上限、跳過翻譯。下載副本未找到 LICENSE，僅研究設計，未複製其實作或執行安裝脚本。
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper#vad-filter)：使用已安裝 1.2.1 內的 Silero ONNX 人聲偵測；沒有另下載大型模型。

參考庫位於工作區 `_research`；目前應用不依賴那些資料夾。修改前程式備份位於 `backups/before-stream-improvements`。

## 已實作

1. 後端先執行 Silero 人聲偵測，無人聲直接回空結果；有語音則保留帶前後緩衝的片段再交給 Whisper。最短語音 120ms、靜音分隔 350ms、語音邊界緩衝 200ms。保留原來的低音量及 no_speech 過濾。
2. 前端依然是音量分段，並非神經串流 VAD：不足 3 秒維持 450ms 靜音門檻；超過 3 秒接受 240ms 靜音，6 秒仍為硬上限。不做硬切重疊，避免沒有去重時出現雙重字幕。
3. 僅原文模式透過 X-Mosa-Display 傳到後端，ASR 完成即回傳，translation_ms 為 0。Chrome 與網頁都支援啟動時及收音中切換；正在處理的片段維持原模式，下一段套用新模式。
4. 未採用一般短語黑名單，例如 Thank you 與謝謝可能是真實語音，不應無條件刪除。

## 本機驗證

RTX 4060 Ti 8GB；Whisper small CUDA int8_float16；Qwen2.5 3B。
以下為合成英日音檔及 3 秒 440Hz 純音的測試，不是直播準確率評分。
改後數字取排除首輪後三次的中位數，包含本機 HTTP；不包含收音分段等待與畫面渲染。

| 樣本／模式 | 改後耗時 |
| --- | --- |
| 日文／原文＋翻譯 | 835.8ms |
| 日文／僅原文 | 273.4ms |
| 英文／原文＋翻譯 | 740.1ms |
| 英文／僅原文 | 247.5ms |
| 純音／原文＋翻譯 | 9.7ms |

改前暖機後單次日文約 714ms、英文約 667ms、純音約 1456ms。
純音處理大幅減少；正常語音多了 VAD 成本，未證明全面加速。
英日辨識測試句保留，英文標點有改變。日文翻譯仍可能保留「こんにちは」。另外比較的簡短翻譯提示未解決問題，未套用。

原始改後結果：`benchmark-live.json`。重跑：`.venv-gpu-test\Scripts\python.exe windows\benchmark_live.py`，需要 8787/8790 服務運行。

20 項 Node 測試、6 項後端測試通過。包含非語音跳過 ASR、僅原文跳過翻譯、收音中切換模式、軟停頓及 5 分鐘連續分段驗證。

## 待實播驗證

小聲、短促語音可能被 VAD 漏掉；音樂或遊戲聲仍可能誤判成人聲。240ms 停頓可能切斷尚未說完的句子。需要英日真人直播音訊與人工對照評估，不能從兩個合成音檔推論普遍準確率提升。
下一輪可比較翻譯模型，以及實作有重疊和穩定定稿的串流辨識；目前未實作 LocalAgreement 或跨片段語言鎖定。
