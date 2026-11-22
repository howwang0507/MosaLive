# Chrome 真實擷取：conservative／adaptive 斷句延遲驗收

日期：2026-10-23（Asia/Taipei）。基線 `a37e4b7`，本輪只量測、只提交本報告，不 push、tag 或 release。

## 結論先說

adaptive 在這段 VOD 的**典型定稿等待較短，但長尾沒有改善，不能宣稱全面更快或更準**。共同且避開早期紀錄缺口的約 13:00～21:59 範圍，定稿延遲 p50 從 4,451.8 降為 3,775.2 ms（少 676.6 ms，約 15.2%）；p95 從 7,174.9 增為 7,309.5 ms。

沒有 GPU 卸載到 CPU 或翻譯排隊的證據。共同範圍的平均延遲約 68～69% 是**仍在收集這一句語音**，而不是 GPU 推論；兩輪的 6 秒硬切上限都還在。使用者目前選擇「僅繁中＋只顯示定稿」，所以較早抵達的原文與暫定譯文不會立即顯示，也會影響體感。

有兩項重要限制：conservative 只有 82／89 句、adaptive 只有 94／98 句保有逐句資料；既有 capture_to_caption_ms 是重建音訊時鐘的估計，**不是聲卡到螢幕像素的實測時間**。以下不把缺漏補零，也不提供沒有標準答案的準確率。

## 素材、環境與控制條件

- 公開素材：[Jinnytty Twitch VOD 2906543890](https://www.twitch.tv/videos/2906543890)，不是私人影片；有日常交談與背景聲，並非純英文朗讀資料集。
- 兩頁播放同一 VOD，名義片段 11:59～21:59，1× 速度；一次只播放及擷取一頁，另一頁暫停。未下載影片或使用 MosaSub 使用者資料。
- conservative 起點由介面與使用者確認為 11:59，暫停後讀值 1319.748 秒；adaptive 起點實際讀值 719.283 秒，暫停後 1319.999 秒。皆約 10 分鐘，邊界不是逐 sample 相同。
- Chrome 原有 MosaLive 擴充功能，真實 tabCapture、AudioWorklet、Node bridge、Faster-Whisper 與 Ollama 路徑。兩輪均由使用者在目標頁面按「翻譯此分頁」並播放，沒有繞過擷取手勢。
- qwen2.5:7b、small CUDA，RTX 4060 Ti（8,188 MiB），context 2048。服務由既有 START_WINDOWS.bat 選擇 .venv-gpu-test 啟動，測試則依現有指令使用 .venv-win。
- 設定一致：displayMode=zh、finalOnly=true、review=false、asrMode=stream-en。未改這些使用者選項、模型、提示詞、num_ctx、鎖、排隊或斷句參數。
- 每輪完整重啟本次已核對的 launcher 服務樹，只在該次程序設定 MOSA_ENDPOINT_MODE。啟動時限制 HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1，沒有下載、升級或替換模型。
- 每輪開始前皆確認 ready=true、ASR loaded、translation available、restart_required=false，endpoint_mode 正確，endpoint_counts 為空。實際字幕產生另外證實推論可用；不只憑「模型已安裝」判定。
- 只做 conservative → adaptive 一組，未做反向順序或重複試驗；不能宣稱統計顯著或排除所有順序、背景工作與 ASR 非決定性影響。

## 收集方法與資料完整性

先檢查既有工具：extension/session-stats.js、popup、windows/evaluate_live.mjs、兩份 summarize 工具、monitor_live.py、speed_report.py 與 health。SessionStats 只有每分鐘分位數與最近 10 句，無法還原完整逐句分布；evaluate_live 是 WAV 重播，不符合本輪真 Chrome 擷取要求，因此沒有拿它替代擷取。

最小額外收集是在**既有頁面的擴充功能內容腳本**設暫時 DevTools 記錄點，條件始終回傳 false，不暫停程式：

1. overlay.js 第 212 行附近讀取送達的 partial／final 事件。
2. 第 196、205 行附近讀取字幕 DOM 已採用的文字，區分收到訊息與真的填入面板。
3. 經 Runtime.consoleAPICalled 讀入本次有限長度的診斷集合，沿用事件的階段欄位；每個 seq 保留 final、第一筆原文／譯文及第一筆採用紀錄。未改正式來源檔、回呼行為或正式緩衝區。
4. 將診斷集合匯出為本機 JSON，再移入 quality/；沒有傳到外部服務。conservative 的瀏覽器下載等待逾時，但檔案實際已產生，已從磁碟確認與驗證，未重複下載替代數據。
5. health／GPU 使用既有 monitor_live.py，結束時使用 speed_report.py。分析百分位沿用 summarize_evaluation.percentile 的 nearest-rank 定義。

conservative 開頭重新連線時有紀錄缺口，保留 82 個 final，DOM 採用紀錄為 78 個；adaptive 早期一次 DevTools 緩衝截斷，保留 94 個 final，DOM 採用紀錄為 94 個。整輪 health 分別有 89、98 個 final，差額 7、4 句不補造。首次原文／譯文數值表示**第一次已記錄的事件**，缺口附近不保證是該句真正的首次事件。

另用 VOD 當下 currentTime 與事件 wall time 校準約略語音時間，只取開始不早於 13:00、結束不晚於 21:59 的共同範圍，避開已知開頭缺口；得到 79、87 句。這是約 9 分鐘的次級對照，不冒充完整 10 分鐘逐句資料，也不是逐字人工對齊。

### 本機產物（未加入 Git）

- quality/endpoint-conservative-20261023-events.json
- quality/endpoint-adaptive-20261023-events.json
- quality/endpoint-conservative-20261023.json、quality/endpoint-adaptive-20261023.json（speed_report）
- quality/endpoint-conservative-20261023-monitor.jsonl 與 .summary.json
- quality/endpoint-adaptive-20261023-monitor.jsonl 與 .summary.json

monitor 的視窗與 VOD 播放視窗不同：conservative monitor 是中途開始、延續到暫停後，summary 的 70 句是 monitor 自己的差值，**不是整片的 89 句**；adaptive monitor 從零開始，共 660 秒，包含啟動與尾端靜音。不能把接收的靜音音訊秒數當成影片播放長度。

## 整輪健康計數與 GPU

起始 endpoint_counts 兩輪皆為空；下表為結束值減起始值。影片暫停後 final 與 endpoint_counts 不再增加。

| 指標 | conservative | adaptive |
| --- | ---: | ---: |
| 整輪 final | 89 | 98 |
| 每分鐘 final（以名義 10 分鐘） | 8.9 | 9.8 |
| silence | 66 | 71 |
| confirmed_sentence | 0 | 8 |
| continuous_limit | 23 | 19 |
| continuous_limit／final | 25.8% | 19.4% |
| 處理錯誤 | 0 | 0 |
| monitor 失敗取樣／後端重啟 | 0／0 | 0／0 |
| Translator on GPU | 100% | 100% |
| ollama ps PROCESSOR | 100% GPU | 100% GPU |
| 模型 VRAM／模型大小 | 4369／4369 MiB | 4369／4369 MiB |
| 結束整卡已用／總量快照 | 6292／8188 MiB | 6296／8188 MiB |

本片段的 conservative 硬切約四分之一，adaptive 接近五分之一。這只驗證本 VOD 的片段，不能回推舊 dinah／mira 監測的 60 分鐘數字一定正確。GPU 用量為快照或離散取樣，不是連續峰值。

## 延遲：各自實際保留的逐句資料

單位 ms，欄位為 p50／p95。除 DOM 採用列外，樣本分別為 82、94 句。這不是同樣本數或完全相同的句子邊界。

| 指標 | conservative | adaptive |
| --- | ---: | ---: |
| 首次已記錄原文事件 capture_to_caption_ms | 1227.5／1798.2 | 1201.8／1944.1 |
| 首次已記錄譯文事件 capture_to_caption_ms | 2521.7／4346.7 | 2535.1／4201.1 |
| 原文首次真的顯示 | 未驗證：原文隱藏，0 筆 | 未驗證：原文隱藏，0 筆 |
| 譯文首次 DOM 採用所屬事件（78／94 筆） | 4271.7／7174.9 | 3695.6／7309.5 |
| final capture_to_caption_ms | 4451.8／7136.9 | 3695.6／7309.5 |
| final after_speech_ms | 1485.3／2075.1 | 1351.2／1972.8 |
| asr_ms | 110／328 | 125／468 |
| asr_queue_ms | 0／0 | 0／0 |
| nmt_ms | 438／922 | 406／1172 |
| nmt_queue_ms | 0／0 | 0／0 |
| delivery_wait_ms | 0／0.1 | 0／0.1 |
| speech_end_ms − speech_start_ms | 2816／6016 | 2304／6016 |
| endpoint_silence_ms | 896／896 | 800／800 |

訊息中的 capture_to_caption_ms 在 offscreen liveInput 交付事件時已計算。DOM 記錄點確認面板採用，但表中仍使用該事件的既有時鐘；**沒有測到 offscreen→內容腳本傳送、瀏覽器 paint 與實體螢幕的完整額外延遲**，不可把它們當成零。原文與部分暫定譯文雖已抵達，finalOnly=true 仍會隱藏預覽，所以第一、二列不能稱為使用者已看見字幕。

speed_report 的完整 89／98 句統計另外是 ASR 110／344 與 125／484，翻譯 438／922 與 421／1172；它與上表分母不同，不能混成一組數據。Windows 計時解析度及四捨五入也會影響 0 ms 的讀值。

### 避開開頭缺口的共同範圍（約 13:00～21:59）

| 指標 | conservative（79 句） | adaptive（87 句） |
| --- | ---: | ---: |
| final capture_to_caption_ms p50／p95 | 4451.8／7174.9 | 3775.2／7309.5 |
| after_speech_ms p50／p95 | 1488.6／2092.2 | 1351.2／1972.8 |
| 片段門檻靜音 p50／p95 | 896／896 | 800／800 |

定稿中位數少 676.6 ms，但 p95 多 134.6 ms；停句後等待中位數少 137.4 ms。只有一組試驗，不能以這些差值宣稱因果效果或統計顯著。

## 品質代價代理指標

| 指標 | conservative | adaptive |
| --- | ---: | ---: |
| final 不以句尾標點結束（逐句範圍） | 57／82（69.5%） | 52／94（55.3%） |
| quality_flags 非空（逐句範圍） | 5／82（6.1%） | 5／94（5.3%） |
| needs_human_review（逐句範圍） | 11／82（13.4%） | 15／94（16.0%） |
| 修譯（整輪 health／speed_report） | 7／89（約 7.9%） | 6／98（約 6.1%） |
| translation_cache_hit 明確標記數（逐句範圍） | 7／82 | 12／94 |

以上不是準確率。adaptive 本來就使用標點作為提早定稿條件之一，標點比例改善不等於語意更正確；人工複核標記反而增加。快取只計 metadata 明確標記，不代表所有沿用結果；沒有為了量測關閉快取。相同素材仍出現不同 ASR 與譯文，需聽原影片判斷，不能憑警告數替兩模式打分。

### 同時點附近 10 組人工比較素材

以下為 ASR／翻譯輸出的**節錄**，不代表正確答案；約時點是事件與播放器時鐘換算，分段不同時可能對應附近不同短句。原文最多 8 個詞、譯文最多 24 字，完整機器輸出留在本機 events JSON。建議回到 VOD 附近聽完整上下文。

| 約時點 | conservative 原文／譯文節錄 | adaptive 原文／譯文節錄 |
| --- | --- | --- |
| 13:00 | This is the top that I got yesterday,…／這是我昨天得到的那件， yeah，還不錯… | This is the top that I got yesterday,…／這是我昨天得到的,top還不錯，yeah不賴… |
| 14:00 | and then Chloe got Joey sick and then…／然後克莉歐讓喬伊也生病了然後… | Oh／哦 |
| 15:00 | If you know／如果你知道 | If you know...／如果你知道... |
| 16:00 | I'm gonna see if there are sushi roe…／我 gonna 看看是否有壽司卵 如果我終於可以… | If I can finally hit sushi, oh my…／如果我終於能吃到壽司，老天我真愛吃壽司，對吧？… |
| 17:00 | I let this way like a bag of…／我把頭裡這件事放下，像放下了包袱一樣。 | This way I get back up my head…／這樣我就可以提提精神再喝啤酒了 |
| 18:00 | is your shareholder Singapore?／你的股東是新加坡嗎？ | Is this your share order Singapore?／這是你的 singapore 訂單嗎？ |
| 19:00 | You will／你將會 | Google／Google |
| 20:00 | Uber had, they had Uber before but not…／Uber之前有提供但現在沒有再提供了。 | They had Uber before but not anymore／他們之前有用過Uber，但現在沒有再用了。 |
| 21:00 | Are you chasing taxi laders too? Chasing taxi?…／你也在追 Taxi 運駛員嗎？追 Taxi？老天… | Are you chasing taxi laders too? Chasing taxi?…／你在追 Taxi 領導人嗎？追 Taxi？老天啊… |
| 21:40 | got refunded for? Oh no. Well let me…／申請退款的是什麼？Oh不。讓我查一下因為昨天我試… | got refunded for? Oh no. Well let me…／申請退款是因為什麼？Oh不。讓我查一下因為昨天我… |

## 瓶頸判斷：等待與推論各占多少？

共同範圍依每句加總後取平均，可精確核對的既有時鐘恆等式是：capture_to_caption = 語音片段長度 + after_speech。

| 觀察量平均 | conservative | adaptive |
| --- | ---: | ---: |
| capture_to_caption | 4730.2 ms | 4271.5 ms |
| 語音片段累積 | 3281.0 ms（69.4%） | 2890.3 ms（67.7%） |
| 語音結束後至交付 | 1449.2 ms（30.6%） | 1381.2 ms（32.3%） |
| 記錄到的門檻靜音 | 671.2 ms | 636.3 ms |
| ASR | 147.4 ms | 162.2 ms |
| 翻譯 | 497.6 ms | 451.2 ms |

前三列是同一公式的分解；後三列是額外階段觀察，**不是可保證互斥相加的因果分解**。預覽、已備妥的 ASR、管線重疊與批次時鐘會影響它們：逐句範圍內有 4／82、9／94 句，直接相減會得到負殘差，因此沒有把殘差硬填成「傳輸時間」。沒有把各項 p95 相加當成總 p95。

已量到的主要現象：

1. 最大份額是等待句子累積；兩模式片段 p95 都是 6016 ms，長句仍會等到約 6 秒硬切。這不是「停句後還等 6 秒」，而是從這句開始講到定稿，原本就包含尚未講完的時間。
2. adaptive 的靜音門檻中位數少 96 ms，但典型片段也變短；不能把全部 0.68 秒中位差都歸給靜音門檻。
3. 推論不是零成本，翻譯與 ASR 尾端也有變慢的案例；但沒有 CPU 卸載、翻譯排隊或過度修譯主導整體等待的證據。
4. 首次原文訊息約 1.2 秒、首次譯文訊息約 2.5 秒就到，但目前隱藏預覽。對這個使用者設定，應先量「是否顯示暫定字幕」的體感代價，再只為縮短等待去切碎長句。

## 建議下一輪只測的選項（本輪未實作）

- 保留 conservative 預設。adaptive 可作候選，先補 A→B→B→A、多次相同素材、完整無缺漏事件，再決定是否改預設；目前不足以確認品質代價可接受。
- 測顯示暫定字幕、而非只顯示定稿：可能較早看見內容，但會有文字修訂與閱讀干擾。先測偏好，不自動修改使用者設定。
- 若硬切長尾仍不滿意，可測約 4 秒上限：預期減少長句首次定稿等待；風險是更多半句、專有名詞切斷、上下文變少，以及更高 ASR／翻譯呼叫量。
- 可另測預覽翻譯頻率（例如從約 2 秒縮短），預期更早出現暫定譯文；風險是 GPU 工作與修訂增加、排隊反而上升。
- 沒有標準字幕、語意人工審核、螢幕 paint 量測、反向重複試驗，這些均為未驗證；沒有提供 CER 或翻譯準確率分數。

## 驗證與收尾

```powershell
.venv-win\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.venv-win\Scripts\python.exe -m unittest discover -s windows -p "test_*.py"
npm test
# 分別在兩輪結束時：
.venv-win\Scripts\python.exe windows/speed_report.py --save quality/endpoint-<mode>-20261023.json
# 本輪既有監測工具：
.venv-win\Scripts\python.exe windows/monitor_live.py --minutes 10 --interval 10 --output quality/endpoint-conservative-20261023-monitor.jsonl
.venv-win\Scripts\python.exe windows/monitor_live.py --minutes 11 --interval 10 --output quality/endpoint-adaptive-20261023-monitor.jsonl
```

- Python 18＋32 項、Node 59 項全部通過。這是回歸檢查，不替代真擷取結果。
- 兩份事件 JSON 的 final 數、endpoint_counts 合計與每句延遲恆等式通過額外檢查。
- 沒有正式程式修正，因此沒有「舊程式失敗／新程式通過」的修正案例；本輪只提交報告。
- 使用者已停止兩頁擷取；影片保持暫停。暫時除錯記錄代理已停用，未留下正式路徑收集器；量測曾產生本機 Console 診斷訊息。
- 最後以未設定 MOSA_ENDPOINT_MODE 的正常啟動流程恢復 conservative；重新確認 ready=true、ASR loaded、translation available、restart_required=false。未更改持久化預設。
- 既有 dirty 檔、三份評測 JSON 刪除、未追蹤 navigation-resume 測試與前輪量測檔均保留，未還原、格式化或加入本輪 commit。
