# ASR Prompt Echo Guard Windows 實測報告（2026-10-25）

## 結論

在本機 Windows、CUDA 與真實 faster-whisper／Ollama 模型下，對同一份正規化 FLEURS 英中素材交替重播兩次：關閉 guard 的 A/C 組各有 8 句 final 只剩 `chat`／`and chat`；開啟 guard 的 B/D 組各為 0 句。B/D 各有 34 次 guard 重試，34 次都採用了不同於 prompt echo 的結果。當中 7 句有帶重試標記的 final，對照參考稿後都移除了錯誤的 `chat` 並恢復了部分應有內容。

同時，開啟組的 WER、數字遺漏與否定詞標記在這份測試素材上較好；但 latency scorer 將 B/D 標記為設定不同，因此不把它們的 ASR 或停句後延遲與 A/C 比較。素材沒有任何講者真的只說 `chat` 的正控制句，故無法用這次評測判斷該情境下 guard 會不會誤觸。

## 範圍與環境

- 基線：`8605ee5`（完整 commit `8605ee524e3ab312e2f6fba7d20cabea518be5cb`）。
- 同一素材及 reference：`fleurs-en-zh-20min-seed2026-active-20dBFS`；四輪 reference timeline SHA-256 均為 `1c23e4896191bf2c807e7456106da0cafdc7f5081caf8579ff8d52033cc8032b`，評分沒有 alignment warning。
- ASR：`small`、CUDA、`MOSA_EVAL_ASR=stream-en`；翻譯：`qwen2.5:7b`／Ollama；endpoint 為 conservative。其他設定維持相同：speculative final 開、preview 2000 ms、max segment 6016 ms、pause 896 ms、breath cut 關、soft cut 0 ms、soft pause 192 ms。
- 每輪均完整重啟服務，health 顯示 ready、ASR 已載入、翻譯可用、`restart_required=false`、計數歸零，且 `tuning.asr_echo_retry` 符合該輪狀態。每輪 `dropped_audio_ms=0`、`reconnects=0`、`replayed_audio_ms=0`。
- 每輪開始和結束前各記錄一次 `nvidia-smi` 指定欄位。開始前確認 Flight Simulator 已關閉；四輪期間未發現遊戲程序。GPU 讀數是起訖快照，不代表整輪平均值。
- 四輪順序：A 關 → B 開 → C 關 → D 開；每輪約 21–22 分鐘。較早在遊戲仍開啟時開始的未完成 A 嘗試已中止，沒有結果檔，也沒有納入評分。

## 測試

在同一基線 `8605ee5` 上，開始重播前執行：

| 指令 | 結果 |
|---|---:|
| `.venv-win\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` | 73 通過 |
| `.venv-win\Scripts\python.exe -m unittest discover -s windows -p "test_*.py"` | 32 通過 |
| `npm test` | 64 通過 |

本輪只有評測資料與報告新增，沒有改程式碼或測試。

## 四輪結果

### 辨識與翻譯品質

| 輪次 | Guard | chat-only final | WER 原始 | WER 數字正規化 | chrF | 覆蓋／漏句 | ASR 數字遺漏 | 翻譯數字遺漏 | 缺否定標記 | 待人工檢視句數 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 關 | 8 | 16.31% | 16.24% | 30.00 | 126／0 | 9 | 6 | 1 | 10 |
| B | 開 | 0 | 13.67% | 13.60% | 30.96 | 126／0 | 5 | 3 | 0 | 5 |
| C | 關 | 8 | 16.31% | 16.24% | 29.88 | 126／0 | 9 | 6 | 1 | 10 |
| D | 開 | 0 | 13.67% | 13.60% | 30.98 | 126／0 | 5 | 3 | 0 | 5 |

A/C 的辨識品質統計完全一致；B/D 也一致。這支持本次素材上的重播結果可重現，但仍是同一份 126 句資料，不等同跨素材或直播品質保證。涵蓋率四輪都是 126/126，沒有 boundary-only 句；ASR 數字正負號變更與需人工確認負值皆為 0。

### Guard 重試與逐句對照

| 輪次 | `/health` retries／changed | retry_ms p50／p95 | 帶重試標記的 final | 帶重試標記的 preview seq |
|---|---:|---:|---:|---|
| A | 0／0 | — | 0 | — |
| B | 34／34 | 141／282 ms | 7 | 6、9、15、27、39、41、88、102、114、130、155、195、200 |
| C | 0／0 | — | 0 | — |
| D | 34／34 | 141／281 ms | 7 | 6、9、15、27、39、41、88、102、114、130、155、195、200 |

同一個 retry 標記會沿用到多次 partial／draft／stable 畫面更新；因此 preview seq 是不同字幕序列的數量，不是重試呼叫次數。重試總數以服務 `/health` 的 34 次為準。

B/D 兩輪帶重試的 final 都是同一組序列，對照標準稿如下。表中的 final 是重試後被採用的 ASR；它仍可能有其他辨識誤差。

| Seq／FLEURS reference | Prompt echo | 重試後 final 的相符片段 |
|---|---|---|
| 6／1795 | `and chat.` | `envelopes are present … vote` |
| 9／1735 | `and chat.` | `… just two generations … breeding between` |
| 15／1883 | `chat.` | `traffic until March 2017` |
| 27／1667 | `and chat.` | `one of the guys or gals` |
| 41／1835 | `and chat.` | `will be issued because the quake … magnitude 6.5 requirement` |
| 102／1847 | `and chat.` | `issues with the Singapore Prime Minister …` |
| 155／1689 | `and chat.` | `Under normal circumstances, traveling through multiple countries` |

這七筆 reference 都是完整語句，沒有講者只說 `chat`；重試結果清除了 prompt echo，並恢復了與 reference 相符的詞。關閉組另外在 seq 189 出現 `and chat.`，但 B/D 沒有該序列的 final 事件，且它沒有 retry 標記；不把這一筆算成 guard 成功修正。整體 chat-only final 從 8 降至 0，其中可直接歸因於帶重試標記的 final 有 7 句。

**False trigger 判斷：**這份 reference 完全沒有 `chat` 或 `comments` 字詞，也沒有講者單獨說 `chat` 的正控制樣本。因此可以確認本輪 7 個帶 retry 標記的 final 都是 prompt echo，未發現它們把正確的單字 `chat` 改壞；但「真實講者只說 chat 時會不會被誤觸」仍無法驗證，不能宣稱 false-trigger rate 為零。

## 延遲與 GPU

Scorer 2026-10-24.4 先判斷 latency comparability：C 相對 A 標記為 `comparable`；B、D 相對 A 都是 `settings differ`（`asr_echo_retry` tuning 不同）。因此只比較 A/C 的 ASR 與 after-speech 分布。以下數值由各輪 216–217 筆 final event 計算 nearest-rank p50／p95。

| 輪次 | Scorer 可比性 | ASR p50／p95 | after_speech p50／p95 |
|---|---|---:|---:|
| A（關） | 基準 | 156／718 ms | 1301／2492 ms |
| B（開） | 不可與 A 比（設定不同） | 157／688 ms | 1338／2368 ms |
| C（關） | 可與 A 比 | 156／703 ms | 1328／2336 ms |
| D（開） | 不可與 A 比（設定不同） | 171／734 ms | 1358／2403 ms |

A→C（同為關閉且 scorer 可比）的 ASR p50 相同；ASR p95 低 15 ms，after-speech p50 高 26 ms、p95 低 156 ms。這些是兩次重播之間的觀察值，沒有足夠依據宣稱有速度改善。B/D 雖列出各自量得的數字，但不與 A/C 推論延遲差異。

| 輪次 | GPU 前：SM 時脈／溫度／使用率／功耗 | GPU 後：SM 時脈／溫度／使用率／功耗 |
|---|---|---|
| A | 2580 MHz／40.96°C／9%／30.28 W | 2580 MHz／43.52°C／15%／31.92 W |
| B | 2580 MHz／42.53°C／13%／32.56 W | 2580 MHz／43.63°C／12%／32.17 W |
| C | 2580 MHz／42.59°C／15%／32.17 W | 2580 MHz／43.86°C／12%／31.81 W |
| D | 2580 MHz／42.53°C／8%／31.03 W | 2580 MHz／44.24°C／17%／33.14 W |

Guard 開啟兩輪 Ollama 最近 200 次請求的 tokens/s p50 分別為 47.2（B）、43.3（D）；關閉兩輪為 46.9（A）、46.8（C）。這不是端到端 latency 比較，也不取代 scorer 的可比性判定。重試延遲本身在 B/D 為 p50 141 ms、p95 約 281 ms。

## 評估檔與限制

- 四輪重播：`quality/echo-retry-off-A-20261025.json`、`quality/echo-retry-on-B-20261025.json`、`quality/echo-retry-off-C-20261025.json`、`quality/echo-retry-on-D-20261025.json`。
- 並列評分：`quality/echo-retry-20261025-scorer.json`，版本 `2026-10-24.4`。
- GPU 起訖快照：`quality/echo-retry-gpu-20261024-valid.log`。
- 本機為真實 Windows／CUDA／模型執行；沒有測正式直播、非 FLEURS 音質或講者真的只說 `chat` 的控制案例。分數反映此素材和這次設定，不可外推為普遍準確率或延遲承諾。
- 既有未提交工作保持原樣；沒有修改或提交它們。沒有 push、tag 或 release。

## 建議

這份基準支持 prompt echo guard 能改善該 FLEURS 英語辨識樣本：兩組開啟輪的 WER 與錯誤指標一致變好，且 7 個受重試 final 均從 prompt echo 改為與標準稿相符的片段。若要決定產品預設，下一次評測應補入有標準答案、確實只說 `chat`／`comments` 的正控制音訊，再測 false trigger；也應加入更多口音、背景音與真實 Twitch 語音。現有資料不足以判定這些情況下的誤觸風險。
