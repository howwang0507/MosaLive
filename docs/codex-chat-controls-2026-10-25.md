# Echo guard 合成語音正控制驗收

日期：2026-10-25  
測試類型：Windows System.Speech 合成語音；非真人錄音、非自然直播。合成發音較清楚，結果可能偏樂觀，只代表本次素材。  
程式基線：正控制工具 2278e3b；echo guard 8605ee5；配對評分器 d5fd1eb。未修改程式、模型、提示詞或預設值。

## 執行環境與準備

- 素材由已安裝的 System.Speech 英文聲音合成；啟用的聲音輪替為 Microsoft Zira Desktop、Microsoft David Desktop、Microsoft Mark、Microsoft Zira、Microsoft David。五段長句及十個短句的逐檔映射記在 recordings/tts/tts-voice-info.txt。
- 去除靜音後，五段長音訊分別長 9.22、8.92、7.78、8.82、8.54 秒；拼接器確認都符合至少 6.45 秒的門檻。樣本共 60：40 after_cut、10 after_pause、10 alone，涵蓋 6 種短句。
- 首次以 .venv-win 啟動時因缺少 cublas64_12.dll 失敗，沒有開始重播。改用 START_WINDOWS.bat 優先採用的既有 .venv-gpu-test 環境；未安裝套件或下載模型。
- 兩輪 ASR 均為 small / CUDA，翻譯 qwen2.5:7b；ASR 模式 stream-en。每輪前都完整重啟服務，確認 ready、ASR 與翻譯可用、restart_required=false，且設定分別為 asr_echo_retry=false/true、計數為 0。
- 每輪 60 筆全數完成、ID 無重複、dropped_audio_ms=0。guard-off 與 guard-on 的 health finals=110，endpoint 計數為 continuous_limit 40、silence 70。

## 結果摘要

| Guard | 類別 | 樣本 | chat 保留 | 遺失 | 有 retry 的樣本 | retry 後遺失 |
|---|---|---:|---:|---:|---:|---:|| 關 | after_cut | 40 | 40 | 0 | 0 | 0 |
| 關 | after_pause | 10 | 10 | 0 | 0 | 0 |
| 關 | alone | 10 | 10 | 0 | 0 | 0 |
| 開 | after_cut | 40 | 39 | 1 | 18 | 1 |
| 開 | after_pause | 10 | 10 | 0 | 0 | 0 |
| 開 | alone | 10 | 10 | 0 | 0 | 0 |

guard-on /health 記錄 20 次重試、16 次改變結果，retry 延遲 p50 94 ms、p95 141 ms。比較工具在 final 序列上找到 18 個不同 hard-cut 樣本帶有 retry 標記；after_pause 與 alone 都沒有重試。服務的 retry 次數是請求數，評分器的 18 是帶標記 final 的樣本數，兩者統計單位不同。

**判斷：** guard-off 三類全部保留 chat（60/60）；guard-on 保留 59/60。唯一遺失發生在 chat-chat-1-after-cut-6300：off 的 final 是 chat，on 的 echo 是 chat，重試後 final 變成 long is left.。它只在 guard-on 遺失，屬於本素材上的 guard false trigger，不是兩組都失敗的 ASR 漏辨。故本次結果**未達到**「retry 後遺失為 0 且保留數不低於 off」的條件，不能用這次驗收支持 guard 預設開啟。這只是單一合成聲音環境下的結果，不直接外推到真人或所有說話人。

## 每個帶 retry 標記的 hard-cut 樣本

下表列出 guard-on 每個帶 retry 標記的樣本、重試前 echo 字串、重試後所有 final 原文，以及 guard-off 同樣本的 final。唯一 lost-after-retry 樣本以「誤觸」標示。

| 樣本 | 口說短句 | Echo 原文 | Guard-on final 原文（重試後） | Guard-off final 原文 | 判定 |
|---|---|---|---|---|---|
| chat-and-chat-1-after-cut-5700 | and chat | and chat | Okay, so the plan for today is to finish the second level collect every hidden key we can find and<br>and chat. | Okay, so the plan for today is to finish the second level collect every hidden key we can find and<br>and chat | chat 保留 |
| chat-and-chat-1-after-cut-6100 | and chat | and chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>floods and chat. | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>and chat | chat 保留 |
| chat-chat-1-after-cut-5700 | chat | chat | I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although<br>chat | I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although<br>chat | chat 保留 |
| chat-chat-1-after-cut-5900 | chat | chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>chat | chat 保留 |
| chat-chat-1-after-cut-6300 | chat | chat | Remember to drink some water and stretch your shoulders every hour, because sitting in the same position for that<br>long is left. | Remember to drink some water and stretch your shoulders every hour, because sitting in the same position for that<br>chat | 誤觸：retry 後 chat 遺失 |
| chat-chat-2-after-cut-5700 | chat | chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley f-<br>chat. | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley f-<br>chat | chat 保留 |
| chat-chat-3-after-cut-5700 | chat | chat | The update added three new maps, a ranked mode with seasonal rewards, and a replay system that f***ed up.<br>chat. | The update added three new maps, a ranked mode with seasonal rewards, and a replay system that f***ed up.<br>chat | chat 保留 |
| chat-chat-3-after-cut-5900 | chat | chat | Remember to drink some water and stretch your shoulders every hour, because sitting in the same position for that<br>chat. | Remember to drink some water and stretch your shoulders every hour, because sitting in the same position for that<br>chat | chat 保留 |
| chat-hi-chat-1-after-cut-5700 | hi chat | Hi chat | Remember to drink some water and stretch your shoulders every hour, because sitting in the same position<br>Hi chat | Remember to drink some water and stretch your shoulders every hour, because sitting in the same position<br>Hi chat | chat 保留 |
| chat-hi-chat-1-after-cut-5900 | hi chat | Hi chat | Okay, so the plan for today is to finish the second level, collect every hidden key we can find.<br>Hi chat | Okay, so the plan for today is to finish the second level, collect every hidden key we can find.<br>Hi chat | chat 保留 |
| chat-hi-chat-1-after-cut-6100 | hi chat | Hi chat | I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although the s-<br>Hi chat. | I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although the s-<br>Hi chat | chat 保留 |
| chat-hi-chat-1-after-cut-6300 | hi chat | Hi chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>floods and we lose high chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>Hi chat | chat 保留 |
| chat-okay-chat-1-after-cut-5700 | okay chat | Okay chat | Okay, so the plan for today is to finish the second level collect every hidden key we can find<br>OK chat. | Okay, so the plan for today is to finish the second level collect every hidden key we can find<br>Okay chat | chat 保留 |
| chat-okay-chat-1-after-cut-5900 | okay chat | Okay chat | I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although the s-<br>soft? ok chat. | I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although the s-<br>Okay chat | chat 保留 |
| chat-okay-chat-1-after-cut-6100 | okay chat | Okay chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>floods. Okay chat. | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>Okay chat | chat 保留 |
| chat-okay-chat-2-after-cut-5700 | okay chat | Okay chat | I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although<br>OK Chat | I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although<br>Okay chat | chat 保留 |
| chat-okay-chat-2-after-cut-5900 | okay chat | Ok, chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>ok chat | If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley flow<br>Ok, chat | chat 保留 |
| chat-okay-chat-2-after-cut-6100 | okay chat | Ok chat | The update added three new maps, a ranked mode with seasonal rewards, and a replay system that final...<br>Finally let's... Okay chat. | The update added three new maps, a ranked mode with seasonal rewards, and a replay system that final...<br>Ok chat | chat 保留 |
## GPU 快照

| 輪次 | 時點 | SM 時脈 | 溫度 | 使用率 | 功耗 | 顯存 |
|---|---|---:|---:|---:|---:|---:|
| Guard off | 前 | 2580 MHz | 41.18°C | 14% | 31.42 W | 6196 MiB |
| Guard off | 後 | 2580 MHz | 44.30°C | 12% | 31.50 W | 6221 MiB |
| Guard on | 前 | 2580 MHz | 43.16°C | 13% | 31.25 W | 6214 MiB |
| Guard on | 後 | 2580 MHz | 44.63°C | 13% | 31.71 W | 6208 MiB |

重播前檢查沒有發現 Flight Simulator 或 Ollama 程序；Windows WDDM 的 nvidia-smi 未提供可歸因的程序清單，桌面／Chrome 顯示工作仍可能使用 GPU。重播後停止了 MosaSub Live launcher；Ollama 依 launcher 設計作為共用服務保留。測試後 GPU 顯存回到約 1222 MiB。

## 本機資料與限制

- Guard-off：quality/chat-controls-tts-off.json
- Guard-on：quality/chat-controls-tts-on.json
- 比較輸出：quality/chat-controls-tts-check.json
- GPU 起訖快照：quality/chat-controls-tts-gpu-*.csv
- 合成來源音檔在 recordings/tts/；拼接樣本在 quality/eval/chat-controls-tts/。資料均為本機評測素材，未納入此 commit。
- 本次沒有真人錄音、沒有自然直播環境，也沒有涵蓋其他口音／麥克風／背景噪音；false-trigger 率不能由 60 個合成樣本推廣估計。
- 未修改產品預設。此次負向樣本表示需要先釐清 false trigger，再決定 guard 的預設策略。