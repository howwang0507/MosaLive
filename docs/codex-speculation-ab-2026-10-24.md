# 停頓推測與穩定譯文：Windows／Chrome A、B、C 驗收

實測：2026-10-23 晚間至 2026-10-24 凌晨（Asia/Taipei）。報告日期：2026-10-24。
驗證對象：70abd2d；量測使用必要診斷修正 243f437。僅本機提交，不 push、tag、release，JSON 不提交。

## 結論

1. 停頓推測確實降低典型定稿等待，但本輪不是完整縮短 500 ms。A／B 的 silence after_speech p50 為 1533.9／1166.6 ms，差 367.3 ms；39 組唯一、原文正規化相同且皆為 silence 的配對句，逐對減少量中位數為 **356.0 ms**。單次試驗不等於統計顯著或準確率結論。
2. 沒有看到翻譯排隊惡化。B 推測翻譯 102 次，67 次被定稿沿用，未沿用 35 次；C 為 108／67／41。三輪 final 的 nmt_queue p50／p95 均為 0／0 ms。「未沿用」不等於完全沒用，部分可能曾作預覽。
3. 提前顯示有體感收益，也有不可忽略的改寫。C 每句首次實際採用譯文的延遲 p50／p95 為 2491.7／4221.6 ms；78／97 句曾先顯示 stable。這 78 句的首次 stable 比 final 早的時間中位數為 1641.8 ms，但首次 stable 與 final 的正規化譯文有 54／78 不同，45／78 不符合前綴關係。不能把 stable 說成不會改。
4. 建議 **stablePreview 維持預設關閉**，由使用者選擇。推測維持既有設定供後續重測。本輪沒有改預設、斷句上限、提示詞、模型、context、鎖或排隊；約七秒的硬切長尾仍在。

## 素材、環境與控制

- 公開素材：[Jinnytty Twitch VOD 2906543890](https://www.twitch.tv/videos/2906543890)。使用者手動按「翻譯此分頁」，真實 Chrome tabCapture；未下載影片或使用私人素材。
- 原訂 11:59 起，經使用者同意改約 11:48 起。下表列實際邊界，**不是逐 sample 相同**。
- Windows、RTX 4060 Ti、8188 MiB、驅動 621.01。ASR small／CUDA、翻譯 qwen2.5:7b、context 2048。三輪 Ollama PROCESSOR 均為 100% GPU；模型 placement 4369／4369 MiB。
- 真服務由既有 START_WINDOWS.bat 選擇 .venv-gpu-test；兩個 Python 環境均實測為 3.11.9。單元測試用 .venv-win，不把替身測試當真模型。
- 每輪完整重啟已核對的本次 launcher 程序樹，子程序使用 HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1，未下載或更換模型。
- 每輪確認 ready=true、ASR loaded、translation available、restart_required=false、conservative。tuning 均為 max_segment=6016、pause=896、preview_interval=2000 ms。A speculative_final=false，B／C=true。
- displayMode=zh、finalOnly=true、review=false、asrMode=stream-en；A／B stablePreview=false，C=true，均由真內容腳本事件中的設定確認。
- 使用者手動重載擴充功能；載入的 overlay 已確認含新版 stablePreview。C 真事件與 DOM 證明選項生效。跨瀏覽器重開後的設定保存未實測；自動化保存測試通過。

| 輪次 | 推測 | 提前顯示 | VOD 起點秒 | VOD 終點秒 | 影片長度秒 |
|---|---|---|---:|---:|---:|
| A | 關 | 關 | 708.056495 | 1310.885870 | 602.829375 |
| B | 開 | 關 | 708.056495 | 1308.773708 | 600.717213 |
| C | 開 | 開 | 710.222866 | 1314.326424 | 604.103558 |

C 起點晚 2.166 秒；終點亦差數秒。共同影片範圍 710.223～1308.774 秒，但沒有逐幀對齊及連續 VOD 時鐘軌跡，**下列整輪分位數不是共同區間的精確配對統計**。另提供相同原文的有限配對。

B 牆鐘約 620.0 秒、影片推進約 600.7 秒，差約 19.3 秒；原因未定位，可能有播放器等待或排程，不能排除干擾。A、C 差額不到 1 秒。未做反向 C→B→A，不能排除順序、快取、背景工作與 ASR 非決定性。

## 收集方式與完整性

沿用前輪已檢查的 session-stats／popup、evaluate_live、summarize、monitor_live、speed_report 與 health。既有分鐘分位數與最近句子不足以保留完整分布，WAV 重播不能替代真 Chrome，因此沿用前輪臨時 DevTools 唯讀記錄，沒有新增正式路徑或依賴。

- 在 overlay 接收 final／stable 及寫入字幕 DOM 處設不暫停的記錄點，約每 25 秒取出；保存原事件與 performance.now。不收帳號、Cookie、token 或私人影音。
- DOM 延遲估計 = capture_to_caption_ms + DOM 採用時鐘 − 內容腳本接收事件時鐘，包含上一句最低閱讀時間造成的延後。
- 依 seq、type、phase、speech_end_ms、translation、capture_to_caption_ms 配對。已記錄的 DOM 事件全部有對應接收事件；不以缺值補零。
- 這是應用程式音訊時鐘估計＋DOM 寫入觀察，**不是聲卡到螢幕像素的外部量測**，未測顯示器 paint；記錄點也可能有小幅負擔。
- A 曾因跨回覆記錄器失聯，廢棄約 35 秒試跑，再退回起點量完整十分鐘。留下 5 筆累計與可能的早段快取，不能宣稱完全冷啟動。
- A 開始 health finals=5、結束=101，增量 96，實記 95，缺 1 筆原因未證實。分位數只用 95 筆。B／C 起始均 0，實記 95／97，與 health 一致。三輪記錄截斷均 0；A 計數差仍如實保留。
- monitor 各 51 樣本，設定 interval=10 秒，但查詢耗時使實際約 12 秒；含少量開頭／暫停後樣本，不說成精確每 10 秒。

本機資料（不提交）：

~~~text
quality/speculation-A-20261023-events.json
quality/speculation-A-20261023.json
quality/speculation-A-20261023-r2-monitor.jsonl
quality/speculation-B-20261023-events.json
quality/speculation-B-20261023.json
quality/speculation-B-20261023-monitor.jsonl
quality/speculation-C-20261024-events.json
quality/speculation-C-20261024.json
quality/speculation-C-20261024-monitor.jsonl
~~~

另有廢棄試跑 monitor，不作結果。JSONL 可能含本機程序快照，不應直接公開。

## 三輪結果

每格 **p50／p95，ms**；nearest-rank。A 排除試跑，使用實記逐句資料，不用混入試跑的 health timing。

| 指標 | A | B | C |
|---|---:|---:|---:|
| final capture_to_caption | 4566.0／7293.8 | 3985.7／7085.9 | 3705.3／7162.6 |
| final after_speech | 1496.8／2015.4 | 1155.0／1724.3 | 1135.5／1682.2 |
| 每句首次真正顯示譯文 | 4566.6／7294.3 | 3986.3／7086.5 | 2491.7／4221.6 |
| final DOM 採用 | 4566.6／7294.3 | 3986.3／7086.5 | 3706.0／7163.3 |
| stable DOM，所有更新事件 | 無 | 無 | 3131.4／6247.9 |
| final asr_ms | 109.0／438.0 | 0／218.0 | 0／250.0 |
| final asr_queue_ms | 0／0 | 0／0 | 0／0 |
| final nmt_ms | 406.0／1094.0 | 0／672.0 | 0／672.0 |
| final nmt_queue_ms | 0／0 | 0／0 | 0／0 |
| final delivery_wait_ms | 0／0.4 | 0／0.7 | 0／0.7 |
| speech_end − speech_start | 2752／6016 | 2560／6016 | 2528／6016 |

final ASR／NMT=0 表示沿用或快取，**不是整句沒有計算成本**。所有 stable 接收事件的 ASR p50／p95：A 94／157、B 94／203、C 94／234；NMT：A 359／672、B 375／609、C 391／563 ms。stable 可能重複引用既有結果，不能直接累加成總運算量。

| endpoint_reason | A：n；final 延遲；after_speech | B：n；final 延遲；after_speech | C：n；final 延遲；after_speech |
|---|---|---|---|
| silence | 73；3552.3／6297.2；1533.9／2008.5 | 76；3245.8／5788.6；1166.6／1660.7 | 76；3131.7／5737.1；1145.9／1538.2 |
| continuous_limit | 22；6970.4／8117.5；1101.0／2101.5 | 19；6874.2／7884.6；1045.3／1868.6 | 21；6975.0／7494.8；972.2／2022.8 |

A silence 實記 73，health 增量 74；缺的 1 筆不猜其延遲。

| 計數／品質代理 | A | B | C |
|---|---:|---:|---:|
| health final 增量 | 96 | 95 | 97 |
| 實記 final／final DOM | 95／95 | 95／95 | 97／97 |
| endpoint 增量 silence／continuous_limit | 74／22 | 76／19 | 76／21 |
| continuous_limit 佔 health finals | 22.9% | 20.0% | 21.6% |
| 每分鐘 final，按影片推進 | 9.6 | 9.5 | 9.6 |
| quality_flags 非空 | 6／95，6.3% | 5／95，5.3% | 4／97，4.1% |
| needs_human_review | 14／95，14.7% | 13／95，13.7% | 18／97，18.6% |
| reviewed 修譯 | 7／95，7.4% | 5／95，5.3% | 4／97，4.1% |
| final 原文無句尾標點 | 56／95，58.9% | 66／95，69.5% | 62／97，63.9% |
| final translation_cache_hit | 9 | 68 | 68 |
| health errors 增量 | 0 | 0 | 0 |

標點判定為去尾空白／引號後有無 . ! ? 。 ！ ？；不是語意評分。flags 中 number_mismatch／possible_missing_negation 分別 A 4／2、B 4／1、C 2／2。沒有標準答案，不宣稱 C 比 A 準。cache_hit 含推測沿用，不等於跨句快取。B canceled_batches=1，原因未定位，不計作 health errors，也不掩蓋。

## 推測命中與資源

| 指標 | A | B | C |
|---|---:|---:|---:|
| speculative_translations | 0 | 102 | 108 |
| speculative_translation_reused | 0 | 67 | 67 |
| speculative_asr_reused | 0 | 70 | 70 |
| 譯文沿用／停頓定稿 | 不適用 | 67／76，88.2% | 67／76，88.2% |
| attempts − reused（未沿用） | 0 | 35 | 41 |
| Ollama PROCESSOR | 100% GPU | 100% GPU | 100% GPU |
| 模型 GPU placement MiB | 4369／4369 | 4369／4369 | 4369／4369 |
| 全 GPU 顯存取樣 min～max MiB | 5999～6064 | 6059～6123 | 5824～5890 |
| GPU 利用率取樣 p50／p95 | 4%／95% | 4%／58% | 6%／60% |
| monitor 非 ready | 0／51 | 0／51 | 0／51 |

顯存差異不是換模型或 CPU 卸載的證據，背景圖形與配置也影響。未量每次 kernel 或總耗能，不宣稱推測免費。

## C：提前顯示與改寫

- 142 次 stable DOM 更新，涵蓋 78／97 句（80.4%）；其餘 19 句首次譯文為 final。
- 97 句各取首次顯示的 p50／p95 為 2491.7／4221.6 ms，不能和全部 142 次更新的分布混用。
- 78 句內配對首次 stable DOM 與 final DOM，提早時間 p50／p95 **1641.8／4756.5 ms**，不是兩份分位數直接相減。
- 去空白／標點後，首次 stable 與 final 不同 54／78（69.2%）；final 不以首次 stable 為前綴 45／78（57.7%）。只是字串代理，「你」這類短前綴也可能通過，不能當語意安全判斷。
- 若比 final 前最後一次 stable：不同 21／78（26.9%），前綴不一致 19／78（24.4%）。雖會收斂，使用者一開始仍看過可改寫版本。
- C final 比 B 快不能歸因於 UI 加速推論，邊界、ASR、播放與非決定性均有差異。

以下依順序前 10 組實際 stable→final 短例，供人工比較，不自行評分。這些是機器輸出，**不宣稱正確**；長句節錄，完整只留本機 JSON。

| seq | 首次 stable → final 節錄 | 提早 ms |
|---:|---|---:|
| 0 | 這是雙倍酷炫。 → 相同 | 9.5 |
| 1 | 卡拉OK很好，yeah，但不是在這裡。 → 相同 | 82.0 |
| 2 | 卡拉OK只有在這裡才很棒 → 卡拉OK只有在韓國才很棒，因為那裡比較便宜 | 1947.5 |
| 3 | 你。 → 你不是天使，謝謝你這麼愛我… | 3238.5 |
| 4 | 你在等誰？ → 你是不是坐火車去？不是，我坐計程車去。 | 2397.9 |
| 5 | 我應該戴帽子還是不戴？ → 相同 | 0.7 |
| 7 | 你是否在潛這片結冰的湖裡？ → 我好想玩Frozen Fabulous… | 3579.6 |
| 8 | 不那麼fabulous → 不那麼fabulous 不那麼fabulous | 2789.2 |
| 10 | 這是那件我最喜歡的上衣 → 這件是我昨天得到的，yeah，還不錯 | 2286.1 |
| 11 | 脖子上也塗一點防曬霜。 → 相同 | 560.8 |

## 瓶頸：實測與推論

**已實測：** A／B／C 平均 final E2E 為 4611.8／4233.2／4220.0 ms；其中 speech_end−speech_start 平均 3127.6／3024.5／3051.2 ms，約佔 67.8%／71.4%／72.3%。這是仍收集本句語音，不是純靜音等待。after_speech 平均 1484.2／1208.7／1168.8 ms。三輪約兩成 hard cut，speech duration p95=6016 ms。

**已實測：** final 路徑 ASR＋NMT 平均 603.5／217.6／227.1 ms；B／C 降低部分是計算提前，不是模型變快。stage 不是完整牆鐘分解，餘額還含端點、輸送、排程，不能全貼成 GPU 或 VAD。

**有限配對：** 原文去空白／標點、轉小寫後完全相同、各輪唯一且都是 silence，A／B 有 39 組。after_speech 中位數 1552.8／1165.7 ms；每組 A−B 中位數 356.0 ms、p95 717.0 ms。偏向辨識穩定句，不能代表全部句子或證明因果。

**推論：** 主要長尾不是翻譯被擠到 CPU／排隊，而是本句累積與定稿。推測改善停頓後計算等待，stable 讓部分長句不等 final 才出字；兩者沒有消除錯譯或長句。無標準稿、外部時間基準、反向重跑，不能證明品質可接受或泛化到其他直播。

## 必要修正與驗證

本機 commit **243f437** 修正推測命中計數歸屬。

- 舊 70abd2d 在推測關閉、普通 preview／cache 沿用時可能仍計 speculative_translation_reused；Windows 模擬探針實得 attempts=0、reused=1。
- 新增 test_disabled_does_not_count_ordinary_preview_as_speculation 與 test_existing_preview_without_pause_speculation_is_not_a_hit，舊程式兩項實際失敗，修後通過。
- 真發起推測才存 pause key＋來源文字，final 必須開啟推測且來源吻合才計命中。不改推論、提示詞、端點或排隊。
- staging 排除使用者 models.py 預設模型 hunk，未提交其他 dirty 檔案。

實測前及三輪後皆通過：

~~~powershell
.venv-win\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
# 25 通過，原 23 加 2 項回歸
.venv-win\Scripts\python.exe -m unittest discover -s windows -p "test_*.py"
# 32 通過
npm test
# 64 通過
Get-ChildItem extension\*.js | ForEach-Object { node --check $_.FullName }
# 全部通過
git diff --check
# 通過；既有 LF/CRLF 提示未據此格式化
~~~

實際服務與量測指令：

~~~powershell
# 各輪只在子程序設定 conservative、MOSA_SPECULATIVE_FINAL=0 或 1
START_WINDOWS.bat
Invoke-RestMethod http://localhost:8787/health
.venv-win\Scripts\python.exe windows\monitor_live.py --minutes 10.3 --interval 10 --output quality\speculation-A-20261023-r2-monitor.jsonl
.venv-win\Scripts\python.exe windows\monitor_live.py --minutes 10.3 --interval 10 --output quality\speculation-B-20261023-monitor.jsonl
.venv-win\Scripts\python.exe windows\monitor_live.py --minutes 10.3 --interval 10 --output quality\speculation-C-20261024-monitor.jsonl
.venv-win\Scripts\python.exe windows\speed_report.py --save quality\speculation-A-20261023.json
.venv-win\Scripts\python.exe windows\speed_report.py --save quality\speculation-B-20261023.json
.venv-win\Scripts\python.exe windows\speed_report.py --save quality\speculation-C-20261024.json
ollama ps
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
~~~

分析使用一次性 Python 標準庫讀 JSON：取 observer_kind=event 且 type=final、按 endpoint_reason 分組、nearest-rank、依前述鍵配對 DOM、依 seq 取首／末 stable；不新增正式依賴。報告自身 hash 由提交後 git log 取得，不填循環 hash。

## 建議、未驗證與收尾

1. 維持 stablePreview 預設關閉。若推出低延遲模式，明示暫定可修訂，找真人評估改寫干擾。數字、否定、地點不能憑 stable 名稱保證。
2. 推測典型停頓約少 0.36～0.39 秒，未見 queue p95 增長，建議保留作後續測試；尚無反向試驗，不宣稱全面更快。35／41 次未沿用要持續觀察。
3. 可另輪獨立測 MOSA_MAX_SEGMENT_MS=4000：預期降低硬切長句等待，風險是碎句、更多計算與錯譯。另獨立測 MOSA_PREVIEW_INTERVAL_MS=1000：可能早出字，也可能增加改寫、負載。**本輪都沒改值。**
4. 未驗證：反向試驗、其他題材／語言、真人閱讀評分、標準稿準確率、外部音畫時間、B 牆鐘差額、A 缺 1 筆原因、長時記憶體／熱降頻、跨瀏覽器重開保存。
5. 上輪 11:59～21:59 報告只作歷史參考，不用舊分位數充當本輪完全相同對照。
6. 已移除三頁 DevTools 記錄器、影片均暫停，已請使用者停止 C 擷取並取消提前顯示。未收到確認，不宣稱 UI 偏好已恢復。C 服務保持 conservative、推測開啟，未持久化修改環境變數。

交付限此報告與 243f437 必要修正。使用者既有變更、模型與 JSON 均未提交，未上傳 GitHub。
