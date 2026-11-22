# 字幕延遲設定

所有設定都是啟動前設定的環境變數；不設定就使用預設值。設定值不合法時，服務會在啟動時直接報錯，不會默默改用其他值。目前生效的值可在 `http://localhost:8787/health` 的 `models.tuning` 查看，或執行 `windows\speed_report.py`。

| 變數 | 預設 | 作用 |
|---|---|---|
| `MOSA_SPECULATIVE_FINAL` | `1` | 停頓 416 ms 時先辨識並翻譯整句；之後若只有靜音，定稿直接沿用。`0` 關閉。 |
| `MOSA_BREATH_CUT` | `0`（關） | 設 `1` 開啟：講到上限時，切在最近 1.5 秒內最明顯的換氣處，後半段留給下一句；找不到換氣就照舊硬切。改善切點位置，不會讓字幕更早出現。尚未用真實語音驗證，所以預設關閉。 |
| `MOSA_SOFT_CUT_MS` | `0`（關） | 一句超過此長度後，只要出現短換氣就定稿。設 0 關閉，開啟時至少 1500。`START_WINDOWS_LOW_LATENCY.bat` 使用 3500。 |
| `MOSA_SOFT_PAUSE_MS` | `192` | 搭配上一項：多長的換氣算數（96–800）。 |
| `MOSA_MAX_SEGMENT_MS` | `6016` | 一句最長多久就一定切（2000–10000）。 |
| `MOSA_PAUSE_MS` | `896` | conservative 模式下，靜音多久視為一句結束（320–2000）。 |
| `MOSA_PREVIEW_INTERVAL_MS` | `2000` | 同一句的預覽翻譯最短間隔（500–5000）。 |
| `MOSA_ASR_ECHO_RETRY` | `0`（關） | 設 `1` 開啟：硬切後的片段若辨識結果幾乎只有 `asr_glossary.json` 的詞（例如只剩「and chat.」），且實際重辨的音訊至少 `MOSA_ASR_ECHO_MIN_MS` 長，就拿掉提示詞重新辨識一次，其他設定不變、最多一次。2026-10-25 合成正控制中曾把真的「chat」改掉，所以在 GPU 重跑確認前預設關閉。觸發、略過次數與額外時間見 `/health` 的 `models.asr_echo_retry`。 |
| `MOSA_ASR_ECHO_MIN_MS` | `2000` | echo retry 的最短音訊長度（500–10000）；較短或無法取得長度就不重試。**暫定門檻**：真的 chat 片段量得 0.58–1.76 秒、幻聽片段 2.34–6.14 秒，但 2 秒是用同一批資料推得，不是已驗證的分界。 |
| `MOSA_NMT_KEEP_ALIVE` | `30m` | 翻譯模型閒置多久後卸載。 |

斷句原因會記在 `/health` 的 `metrics.endpoint_counts`：`silence`（停頓）、`breath_cut`（在換氣處切）、`soft_pause`（低延遲模式短換氣）、`continuous_limit`（找不到換氣的硬切）、`confirmed_sentence`（adaptive）、`flush`（停止時送出）。

字幕面板的「提前顯示穩定譯文」會較早顯示暫定譯文，但 2026-10-24 實測約七成會在定稿時改寫，所以預設關閉。
