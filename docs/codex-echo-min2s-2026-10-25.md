# Echo retry 2 秒門檻驗收（2026-10-25）

## 範圍

驗證本機 commit `d92704f`：echo retry 預設關閉；本次驗收明確設定 `MOSA_ASR_ECHO_RETRY=1`，`MOSA_ASR_ECHO_MIN_MS` 留空以使用暫定預設 2000 ms。只有實際送入第二次 ASR 的音訊長度達到門檻才重辨；短於門檻或無法取得長度時略過。

本輪沒有修改程式、模型、提示詞、VAD、斷句或預設。所有重播和評分輸出都保留在本機 quality/，本報告是唯一要提交的檔案。

## 驗證環境與測試

| 指令 | 結果 |
|---|---:|
| `.venv-win\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` | 81 項通過 |
| `.venv-win\Scripts\python.exe -m unittest discover -s windows -p "test_*.py"` | 32 項通過 |
| `npm test` | 64 項通過 |

Git HEAD 為 `d92704f91f1b78d35d5376eb70c2f6037bfdec4b`。目標資料夾原有的已修改、刪除及未追蹤檔案均保留，沒有納入提交。

兩輪服務啟動時都確認 `ready=true`、`restart_required=false`、ASR `small`、翻譯模型 `qwen2.5:7b`、endpoint `conservative`，且輪次開始時定稿與 echo 計數為 0。health 的 tuning 顯示 `asr_echo_retry=true`、`asr_echo_min_ms=2000`；重播使用 `MOSA_EVAL_ASR=stream-en`。

第一次 FLEURS 重播完整跑完，但輸出環境變數多帶了 `quality/\`，評測器再加一次目錄後未能保存。該次資料沒有採用；完整重啟服務後，以正確的新檔名重新重播並成功保存。

## GPU 記錄與限制

| 輪次 | 開始前 | 結束後 |
|---|---|---|
| FLEURS | 成功重播前沒有另取即時快照。最近的啟動前快照（在第一次未保存重播前）：2580 MHz、41.12°C、14%、31.10 W、1258 MiB / 8188 MiB | 2580 MHz、44.49°C、15%、31.72 W、6277 MiB / 8188 MiB |
| 正向控制 | 未單獨記錄開始前快照 | 2580 MHz、44.38°C、16%、31.57 W、6255 MiB / 8188 MiB |

GPU 使用率在整個工作期間約 13–16%。Windows WDDM 無法從本次快照判定是哪個程序造成，因此不能聲稱 GPU 完全閒置或把小幅延遲差異完全歸因於程式設定。程序檢查未見 Flight Simulator；本次結果的 latency comparability 由 scorer 另行判定。

## FLEURS 正規化組

結果檔：`quality/echo-min2s-fleurs.json`。比較檔：`quality/echo-min2s-fleurs-scorer-2026-10-25.json`。評分器版本：2026-10-25.1；同一份正規化 reference，共 126 句。

| 指標 | Guard off A/C | Guard on B/D（原始無門檻） | Guard on、2000 ms |
|---|---:|---:|---:|
| chat-only 定稿 | 8 | 0 | 1 |
| WER（原始） | 16.31% | 13.67% | 13.75% |
| WER（數字正規化） | 16.24% | 13.60% | 13.67% |
| chrF | 30.00 / 29.88 | 30.96 / 30.98 | 30.84 |
| 覆蓋／漏句 | 126 / 0 | 126 / 0 | 126 / 0 |
| ASR 數字遺失標記 | 9 | 5 | 5 |
| 翻譯數字遺失標記 | 6 | 3 | 3 |
| 缺否定標記 | 1 | 0 | 0 |
| Capture→final p50 / p95 | A: 6904 / 8083 ms；C: 6901 / 8058 ms | B: 6916 / 8066 ms；D: 6941 / 8174 ms | 6896 / 8076 ms |
| 停句後→final p50 / p95 | A: 1301 / 2492 ms；C: 1328 / 2336 ms | B: 1338 / 2368 ms；D: 1358 / 2403 ms | 1327 / 2330 ms |

新一輪與原 guard-on B/D 的 scorer 狀態為「A/B on tuning.asr_echo_min_ms」，Ollama tokens/s 代理在比較範圍內。延遲數字只代表這幾次重播，不是統計顯著性結論。WER 比原 guard-on 高 0.08 個百分點（數字正規化高 0.07 個百分點），chrF 低 0.12–0.14；數字、否定和漏句標記相同。

本輪 health 統計：217 個 final、27 次 retry（27 次結果有改變）、7 次因音訊長度不足而略過；retry 時間 p50/p95 為 156/235 ms。與原 guard-on 相比，chat-only 定稿從 0 增至 1。該定稿的實際重辨音訊長度只有 320 ms，因此依門檻正確略過；極短片段仍可能留下 chat 幻聽。

## 合成正向控制

結果檔：`quality/chat-controls-tts-min2s.json`。比較檔：`quality/chat-controls-tts-min2s-check.json`。

| 類別 | 樣本 | 保留 chat | 遺失 | retry | retry 後遺失 |
|---|---:|---:|---:|---:|---:|
| after_cut | 40 | 40 | 0 | 1 | 0 |
| after_pause | 10 | 10 | 0 | 0 | 0 |
| alone | 10 | 10 | 0 | 0 | 0 |

關閉組也是 60/60 保留 chat，沒有遺失或 retry。開啟 2000 ms 門檻後，正向控制 health 記錄 1 次 retry、1 次內容變更、18 次短音訊略過，retry 時間 109 ms。唯一 retry 樣本為 `chat-hi-chat-1-after-cut-6300`：chat 有保留，但辨識結果多出不屬於短句的內容。故本輪沒有發生 guard 吃掉真的 chat，但較長片段仍可能被重試並引入額外辨識文字。

這是 Windows 內建合成語音拼接而成的控制素材，發音比真人清楚，不代表所有口音、背景噪音或直播情況。

## 結論與未驗證事項

- 正向控制達成此批素材的安全條件：60/60 保留 chat，retry 後遺失為 0。
- FLEURS 的數字與否定標記維持原 guard-on 水準，WER、chrF 只有小幅波動；但有 1 個 320 ms 的 chat-only 定稿未被修正，表示 2 秒門檻會以短回聲漏網作為保守代價。
- 2 秒門檻是從同一批資料擬合出的暫定值，不是普遍邊界。正向控制有一個較長片段仍觸發 retry 並加出額外文字。
- 本次只測一個 FLEURS 正規化重播及一批合成語音；沒有新增真人錄音或 Twitch 長時間直播驗證。GPU 開始快照不完整，且 Windows WDDM 無法確認背景 GPU 使用來源。
- echo retry 的程式預設仍保持關閉；本報告不建議僅憑這批素材恢復預設開啟。GPU/真人直播驗證仍需另行安排。

## 本機結果檔

- `quality/echo-min2s-fleurs.json`
- `quality/echo-min2s-fleurs-scorer-2026-10-25.json`
- `quality/chat-controls-tts-min2s.json`
- `quality/chat-controls-tts-min2s-check.json`

以上資料檔沒有提交 GitHub，也沒有加入本次 commit。
