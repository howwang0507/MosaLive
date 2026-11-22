# MosaLive 換氣切點與軟切點 A/B 驗證

日期為 2026-11-07。這輪在 Windows、RTX 4060 Ti 8 GB、既有本機模型上完成三次完整重播。

## 範圍與環境

- 測試模型為 Faster-Whisper small、CUDA int8_float16、Ollama qwen2.5:7b。三輪翻譯模型皆為 100% GPU，context 2048。
- 保留 conservative、停頓 896 ms、最長片段 6016 ms、預覽間隔 2000 ms、停頓推測開啟、echo retry 關閉。每輪只改一個實驗選項。
- A 使用原預設，B 設 MOSA_BREATH_CUT=1，C 設 MOSA_SOFT_CUT_MS=3500，短換氣門檻維持 192 ms。這些設定只傳入測試程序，正式預設仍為關閉。
- 每輪完整停止本輪啟動的 MosaLive 後重新啟動。開始前均確認 ready=true、ASR 載入、翻譯可用、restart_required=false、音訊及定稿計數為 0。
- 目前 HEAD 為 c0ee339，工作區含使用者既有修改及上一輪 UX 修改。此次測試未修改正式程式。服務指紋為 93286c168a0e5728。
- 三輪 network client SHA-256 完全相同，為 1da5136984842d3dec3b89d3c2ba6d2f50bcc1d5b520dd32b3054fec258cbffc。
- 測試使用啟動檔既有的 .venv-gpu-test。評測程序設定 HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1，使用既有快取。

## 素材與有效執行

使用既有 FLEURS 英文 126 句、自訂有效語音 RMS 約 -20 dBFS 的串接素材。音訊長度 1,289.473 秒，約 21 分 29 秒。時間軸指紋為 1c23e4896191bf2c807e7456106da0cafdc7f5081caf8579ff8d52033cc8032b。

來源為 google/fleurs，CC BY 4.0，固定資料 revision 70bb2e84b976b7e960aa89f1c648e09c59f894dd。沿用既有素材，未重新建置。

執行順序為預設短測、完整 A、未完成 B、換氣短測、軟切短測、完整 B、完整 C。三次約一分鐘的短測均完成重播及評分。

第一次完整 B 在開頭約半分鐘後中止，評測子程序回傳非零，沒有留下完整 JSON，replay.log 為空，服務日誌沒有對應錯誤。當時的 runner 未保存退出碼，原因未確認。該次排除，保留原日誌，重新啟動後 B 的短測及完整測試成功。沒有以這次失敗推定換氣演算法故障。

## 整體品質與延遲

| 指標 | A 預設 | B 換氣切點 | C 軟切 3500 ms |
|---|---:|---:|---:|
| WER 原始 | 16.31% | 14.66% | 13.16% |
| WER 數字正規化 | 16.24% | 14.59% | 13.05% |
| chrF | 30.01 | 29.91 | 30.03 |
| 覆蓋句數 | 126 | 126 | 126 |
| 僅邊界 | 0 | 0 | 0 |
| 漏句 | 0 | 0 | 0 |
| ASR 數字遺失標記 | 9 | 7 | 7 |
| 翻譯數字遺失標記 | 6 | 5 | 5 |
| 缺否定標記 | 1 | 1 | 0 |
| 語音起點至定稿可用 p50 / p95 ms | 6689.6 / 7734.9 | 6633.4 / 7651.0 | 5516.5 / 7471.0 |
| 語音結尾至定稿可用 p50 / p95 ms | 1162.4 / 2036.4 | 1185.8 / 1967.7 | 1058.6 / 1703.6 |
| 參考片段結束至最後相關定稿可用 p50 / p95 ms | 257.6 / 1367.3 | 236.0 / 1321.5 | 37.0 / 993.7 |
| 最後相關定稿指標量到的參考句數 | 126 | 126 | 126 |
| 該指標負值數 | 46 | 48 | 59 |
| 定稿數 | 217 | 224 | 230 |
| chat-only 定稿 | 8 | 8 | 6 |
| reviewed 定稿 | 5 | 3 | 3 |
| 需人工複核定稿 | 21 | 18 | 13 |

評分器為 2026-10-25.1。數字與否定項目是自動複核標記，本輪沒有全面人工語意評分。以上時間是重播客戶端收到事件的可用時間，未包含真實 Chrome 擷取、擴充功能訊息與 DOM 繪製。參考片段結束指標的負值保留，不能當成負延遲。

## 斷句分布

| 輪次 | 斷句原因 | 定稿數 | 語音起點至定稿可用 p50 / p95 ms | 語音結尾至定稿可用 p50 ms |
|---|---|---:|---:|---:|
| A-default | continuous_limit | 121 | 7001.5 / 7826.1 | 1024.5 |
| A-default | silence | 96 | 4262.0 / 6472.0 | 1186.7 |
| B-breath | breath_cut | 61 | 6949.8 / 7693.2 | 1337.6 |
| B-breath | continuous_limit | 61 | 7006.1 / 7767.6 | 1003.2 |
| B-breath | silence | 102 | 4158.9 / 6404.9 | 1187.3 |
| C-soft3500 | continuous_limit | 59 | 7024.8 / 7908.2 | 1012.4 |
| C-soft3500 | silence | 39 | 2818.6 / 3550.7 | 1154.0 |
| C-soft3500 | soft_pause | 132 | 5173.7 / 6871.8 | 1015.2 |

## 預覽改寫旁路

| 指標 | A 預設 | B 換氣切點 | C 軟切 3500 ms |
|---|---:|---:|---:|
| 有 stable 預覽的定稿占比 | 96.3% | 97.3% | 93.9% |
| 首版 stable 與最終定稿前綴不一致 | 58.4% | 58.3% | 65.3% |
| stable 早於定稿可用 p50 ms | 3396.8 | 3231.6 | 2657.0 |
| 首版 stable 至定稿配對數 | 209 | 218 | 216 |
| 逐字編輯距離 p50 / p95 字元 | 19 / 38 | 18 / 39 | 18 / 38 |
| 正規化編輯距離 p50 / p95 | 0.837 / 1.000 | 0.818 / 1.000 | 0.846 / 1.000 |

新增的旁路編輯距離只在分析腳本內計算。每個 seq 取第一次收到的非空 stable 譯文與該 seq 定稿，去前後空白後，使用 Unicode 字元 Levenshtein 距離，除以兩者較長字串長度。它包含新增的尾端文字、標點與格式變更，所以不是「已顯示文字被改寫」的比例。它代表客戶端收到的文字差異，不能當成畫面已顯示字數或翻譯語意準確率。正式評分器與顯示規則沒有在這輪改動。

## 機器速度與延遲可比性

| 指標 | A 預設 | B 換氣切點 | C 軟切 3500 ms |
|---|---:|---:|---:|
| Ollama tokens/s p50 | 56 | 56.3 | 56.8 |
| 最近 200 句 ASR p50 / p95 ms | 125 / 578 | 94 / 562 | 125 / 531 |
| 最近 200 句 NMT p50 / p95 ms | 469 / 922 | 16 / 859 | 515 / 859 |
| 最近 200 句 NMT 排隊 p50 / p95 ms | 0 / 0 | 0 / 0 | 0 / 0 |
| 翻譯模型 GPU 佔比 | 100% | 100% | 100% |
| 丟音訊 / 重連 / 服務錯誤 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

近期 ASR、NMT 統計包含推測沿用、快取等路徑，尤其 B 的 NMT p50 為 16 ms，不能解讀成模型生成本身突然加速。Ollama tokens/s 與逐事件可用時間應一起解讀。

- A-default vs B-breath 為 `A/B on tuning.breath_cut`。速度代理為 Ollama tokens/s p50。
- A-default vs C-soft3500 為 `A/B on tuning.soft_cut_ms`。速度代理為 Ollama tokens/s p50。
- B-breath vs C-soft3500 為 `A/B on tuning.breath_cut, tuning.soft_cut_ms (confounded)`。速度代理為 Ollama tokens/s p50。

評分器使用 10% 經驗警戒值，沒有做統計顯著性檢定。B 與 C 同時差兩個設定，因此不能由兩者直接歸因某一個選項的效果。

## GPU 抽樣

各輪前後保存 nvidia-smi 的 SM 時脈、溫度、利用率、功耗與記憶體，重播期間每約 30 秒額外抽樣。開始前未見 Flight Simulator 等常見遊戲程序。這是程序名稱檢查，不能排除所有背景 GPU 用途。

| 輪次 | 開始前 GPU CSV 數值 | 結束後 GPU CSV 數值 |
|---|---|---|
| A-default | 2580 MHz, 40.79, 2 %, 28.09 W, 5627 MiB, 8188 MiB | 2745 MHz, 43.08, 1 %, 32.79 W, 6108 MiB, 8188 MiB |
| B-breath | 2580 MHz, 41.45, 1 %, 28.16 W, 5632 MiB, 8188 MiB | 2580 MHz, 43.66, 1 %, 32.53 W, 6108 MiB, 8188 MiB |
| C-soft3500 | 2580 MHz, 42.59, 1 %, 28.34 W, 5632 MiB, 8188 MiB | 2745 MHz, 43.96, 1 %, 32.84 W, 6108 MiB, 8188 MiB |

CSV 欄位依序為 SM MHz、溫度、GPU 利用率、功耗、已用 MiB、總 MiB。三輪尾端 GPU 佔比與 ollama ps 均保存於各自的 speed 檔。

## 判讀與下一步

1. 這批素材支持把 3.5 秒軟切點列為下一輪真人直播測試的優先候選。相對 A，語音起點至定稿可用中位數縮短 1173.1 ms，WER 降低 3.15 個百分點，翻譯數字標記減少 1 句，缺否定標記從 1 變為 0。chrF 只增加 0.02，不能宣稱翻譯語意品質有實質提升。
2. 換氣切點將 continuous_limit 定稿從 121 降至 61，另外產生 61 個 breath_cut。WER 降低 1.65 個百分點，整體可用時間中位數只縮短 56.2 ms，這批觀察的主要價值在切割位置與辨識結果。
3. 軟切點的首版 stable 與定稿前綴不一致比例由 58.4% 升至 65.3%。這支持先處理預覽穩定性與改寫度量，再考慮把提前顯示預設打開。
4. 三輪各只有一次有效執行，順序固定，B 額外有一次未完成嘗試及重跑前短測。尚無 ABBA 或 ABAB，也未人工逐句驗證翻譯語意，不能證明所有情境準確率不變。
5. 自然 Twitch 片段的相同區段、真實 Chrome 擷取、DOM 採用時間尚未驗收。Chrome 啟動擷取需要使用者手勢，這輪未操作該流程。
6. 原文端 Agreement 已存在，下一項應先做 shadow 評測，檢查其穩定原文是否仍撤回，以及對應譯文的編輯距離，再決定正式顯示策略。日韓語、重疊說話、背景音樂與噪音也仍需獨立素材。

## 指令與檔案

每輪以暫時環境變數啟動 `.venv-gpu-test\Scripts\python.exe -u windows\launch.py`，並設定 `MOSA_NO_BROWSER=1`。

```powershell
node windows/evaluate_live.mjs quality/eval/baseline-20261024-active-20dBFS/fleurs-en-zh-20min-seed2026-active-20dBFS.manifest.json
.venv-gpu-test\Scripts\python.exe windows/score_eval.py <A結果> <B結果> <C結果> --save <新比較檔>
.venv-gpu-test\Scripts\python.exe windows/speed_report.py --save <新速度檔>
nvidia-smi --query-gpu=clocks.sm,temperature.gpu,utilization.gpu,power.draw,memory.used,memory.total --format=csv
```

- A 與首次中止的 B 日誌位於 `quality/endpoint-ab-20261107-210028/`。
- 有效 B、C、短測與三輪並列評分位於 `quality/endpoint-ab-20261107-212610/`。
- 分析及執行腳本位於目前 Codex 工作區的 `tmp/mosalive-endpoint-ab-20261107/`。
- 既有素材、舊評分與使用者工作區變更均保留。測試結束後已停止本輪 MosaLive 服務，8787、8790 連接埠已釋放。
- 本輪前已通過 Node 71 項、Python tests 81 項、Windows tests 32 項。這輪沒有新增正式程式修正，只有量測與報告。
- 僅本報告可加入本機版本紀錄，quality JSON、GPU 快照、日誌與素材不加入 Git。
