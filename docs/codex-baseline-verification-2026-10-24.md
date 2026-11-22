# 62bfb50 Windows 驗證、煙霧測試與正式預設基準

日期：2026-10-24（Asia/Taipei）。專案：MosaSub-Live-Windows。
驗證基線 62bfb50；必要修正 49691e1、97d13d9。只在本機 commit，不 push、tag 或 release。

## 結論

- **工程流程已實測跑通：** 公開 FLEURS 真下載、固定版本、素材產生、Windows 真模型定速重播、評分與健康快照，全部完成。
- **62bfb50 原樣未通過真資料煙霧：** 遇到浮點 WAV 不支援，以及固定音量裁切刪除有效語音兩項問題，均先補 RED／GREEN 回歸測試再修正。
- 正式素材實際 **1289.473 秒（21 分 29.473 秒）**，126 個參考句；完整送達 1289473 ms，193 個唯一 final，與後端完全一致；掉音、重連、佇列溢位、服務錯誤均 0。
- **品質尚未合格，也未證明不退步：** 原始 WER 29.22%、數字正規化 WER 29.18%、自訂 document chrF 25.72。音訊時間未覆蓋 9 句，29 句被列為人工複核。這是現況比較基準，不是可公開宣稱的準確率驗收。
- 沒有改模型、提示詞、num_ctx、搜尋強度、排隊／鎖或正式預設。未開始換氣切點、640 ms 或低延遲 A/B。

## 1. 驗證 62bfb50 的範圍

已核對：

- 下載 Request 不再加入 Authorization；解析一次資料 commit，三份檔案都使用相同 commit，並記錄 SHA-256。
- 數字評分區分 raw／normalized WER，保留負號與小數；無音訊重疊的近邊界不算 covered。
- nearest-rank 分位數、可用時間命名、最近 200 次 Ollama 請求與 tokens/s 說明已納入程式和文件。
- .cache/、quality/eval/ 已被 git check-ignore 確認排除。
- 初始 Windows 自動測試：tests 46、windows 32、Node 64 全過。這不是引用 Claude 的 Linux 結果，是本機執行。
- 本輪沿用已有評測與監測工具，沒有新增正式處理路徑或生產依賴。

### 必要修正 A：浮點 WAV

本機 commit **49691e1**。

真下載後，build_fleurs_eval.py 在 Python 3.11 報 wave.Error: unknown format: 3。真 FLEURS 錄音有 IEEE float WAV，原解碼器只接受 PCM16。

- RED：新增 test_decodes_fleurs_float_wav_and_resamples_stereo，以 float32、8 kHz、雙聲道 WAV 重現舊程式錯誤。
- 修法：重用已安裝 faster_whisper.audio.decode_audio，輸出 mono 16 kHz，不另裝套件；只改評測素材解碼，不改 ASR 模型。
- GREEN：focused 11、tests 47、windows 32、Node 64 通過，真資料成功產生素材。

### 必要修正 B：低音量語音被裁掉

本機 commit **97d13d9**。

第一次煙霧低分後抽查，發現一個完整參考句的原音訊 12.12 秒，被固定 RMS=.01 的 trim 裁成 **0.22 秒**。該錄音 RMS 中位數約 .00186，少量較大聲音觸發門檻，其他有效低音量語音反而被刪除。不能拿這份素材驗證模型。

- RED：新增 test_trim_preserves_quiet_speech_around_louder_click；舊裁切輸出 3840 samples，少於有效語音的 16000 samples。
- 修法：只移除接近數位靜音的頭尾（RMS 閾值 1/32768），保留原錄音音量與 100 ms 邊緣；不進行增益正規化。文件同步說明原背景聲／停頓仍可能保留。
- GREEN：focused 12、tests 48、windows 32、Node 64 通過。正式素材最短參考音訊為 3.6 秒，已不再有該 0.22 秒異常。
- 原先素材與測量保留，不覆寫或刪除；正式資料另外建立 baseline-20261024 目錄。另有 seed2027 的建置檢查素材，未採作基準。

## 2. 環境與有效設定

- Windows、RTX 4060 Ti、8188 MiB、驅動 621.01。
- 使用既有 START_WINDOWS.bat，實際啟動 .venv-gpu-test；測試套件使用 .venv-win（Python 3.11.9）。
- ASR small／CUDA，翻譯 qwen2.5:7b，context 2048。Ollama PROCESSOR 為 100% GPU，placement 4369／4369 MiB。
- conservative；speculative_final=true；preview_interval_ms=2000；max_segment_ms=6016；pause_ms=896；breath_cut=false；soft_cut_ms=0；soft_pause_ms=192。
- 重播 ASR mode=stream-en；沒有更改正式預設值。環境限制 HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1，沒有下載模型。
- 開始前服務 ready、ASR loaded、translation available、restart_required=false，finals=0、errors=0。
- 為正式基準只重啟本輪已核對的測試啟動器 24336；正式 launcher PID 21880。沒有終止其他專案或 Ollama。
- 正式監測本地時間 16:39:04～17:01:04，重播約早於監測起點 11 秒開始，監測尾段包含重播完成後空檔。
- 工作區原有 START_WINDOWS.bat、models.py、launch.py、server.mjs 等未提交變更保留。因此結果是「該 commit 加保留的本機工作區」，不是乾淨 checkout 的結果。實際 code_revision=3a4adba241e5e6c3。

執行時重要檔案 SHA-256（不包含內容）：

| 檔案 | SHA-256 |
|---|---|
| windows/models.py | BF821E0882AB40CFE859257AD4E06F612E4DAEEFF1A0BD333879C95DA9874AB0 |
| windows/launch.py | 2179FB72048C7943231A32EA7B5F7CE883FE2F2CACB2DA59B326956F4E949736 |
| server.mjs | 6EC2F2C63F10D844F897D73A22137E94575705158D20E48B7C0795AB80873BA9 |
| START_WINDOWS.bat | 8CD8EF5E8C0896E9161409D39541160C695165119FDA05610388F9A64BD33550 |
| web/live-client.js | D7020FD0650051F2834CFCC1FC3EFAE407FA50554144F11407C68C4DF70A5B49 |

## 3. 資料版本與重現

公開資料 google/fleurs，CC BY 4.0，[官方資料卡](https://huggingface.co/datasets/google/fleurs)。
版本固定 **70bb2e84b976b7e960aa89f1c648e09c59f894dd**，不是每次取浮動 main。

| 來源 | bytes | SHA-256 |
|---|---:|---|
| en_us/test.tsv | 367864 | 74c046239374deeb60fa63f258f907388093a32bcaa3140965f70ef05c79f7ca |
| cmn_hans_cn/test.tsv | 491487 | 5734461648f816181d7dab5fc79204b18c4b9bc2cd5138225b25c72d18385d21 |
| en_us/audio/test.tar.gz | 289851356 | d9c2e37b41aacd41bc283554a0a82b5476b36887049774ecb2819dcaaa55a356 |

正式音檔 SHA-256：**8A11CEBFF3FD351CF0060502929736C89689F45877EDE0055AC0E1919ADB6275**。
seed=2026，126 句；number 標記 37、negation 14、condition 13（標記可重疊）。
中文參考由簡體經 OpenCC s2twp 轉換，不等於台灣人工審校譯文。

--minutes 20 是建置選句預算，非截斷到精確 1200 秒；保留音訊與串接間隔後實際 1289.473 秒。下輪應沿用同一份 WAV 與參考檔，不重新產生來比較。朗讀串接不是自然直播，也沒有真 Chrome 擷取／DOM 呈現。

實際主要指令：

~~~powershell
.venv-win\Scripts\python.exe windows\build_fleurs_eval.py --minutes 1
# 初次真下載成功，但解碼失敗；修正後先試建，再發現裁切問題。
.venv-win\Scripts\python.exe windows\build_fleurs_eval.py --minutes 1 --seed 2026 --revision 70bb2e84b976b7e960aa89f1c648e09c59f894dd --out quality/eval/conservative-trim-smoke
$env:MOSA_EVAL_ASR='stream-en'
$env:MOSA_EVAL_OUTPUT='eval/smoke-trim-fixed-20261024.json'
node windows/evaluate_live.mjs quality/eval/conservative-trim-smoke/fleurs-en-zh-1min-seed2026.manifest.json
.venv-win\Scripts\python.exe windows\score_eval.py quality/eval/smoke-trim-fixed-20261024.json --save quality/eval/smoke-trim-fixed-20261024-score.json

.venv-win\Scripts\python.exe windows\build_fleurs_eval.py --minutes 20 --revision 70bb2e84b976b7e960aa89f1c648e09c59f894dd --out quality/eval/baseline-20261024
# 正式前重啟本輪服務、確認健康與計數為零。
$env:MOSA_EVAL_OUTPUT='eval/baseline-20261024/run-default.json'
node windows/evaluate_live.mjs quality/eval/baseline-20261024/fleurs-en-zh-20min-seed2026.manifest.json
.venv-win\Scripts\python.exe windows\monitor_live.py --minutes 22 --interval 15 --output quality/eval/baseline-20261024/monitor.jsonl
.venv-win\Scripts\python.exe windows\score_eval.py quality/eval/baseline-20261024/run-default.json --save quality/eval/baseline-20261024/score-default.json
.venv-win\Scripts\python.exe windows\speed_report.py --save quality/eval/baseline-20261024/speed-after.json
~~~

所有資料與原始結果只留本機 quality/eval/，不加入 Git。

## 4. 煙霧結果

| 指標 | 修正後 |
|---|---:|
| 影片音訊長度 | 64877 ms（約 1 分 5 秒） |
| 參考句／final | 6／10 |
| 掉音／重連／溢位 | 0／0／0 |
| WER raw／normalized | 23.81%／23.81% |
| document chrF | 17.04 |
| 音訊時間覆蓋 | 6／6 |
| 參考句尾延遲可測句數 | 0；p50／p95=None |

煙霧通過的是下載→建置→真模型重播→評分的工程鏈路，不是品質認證。「覆蓋」僅指音訊時間重疊，不能證明整句都已正確辨識。先前錯誤裁切煙霧 WER 34.01%、chrF 15.31，不作正式比較，因輸入音訊不同。

## 5. 正式完整性與品質

| 指標 | 實測 |
|---|---:|
| 參考音訊／用戶端接收音訊 | 1289473／1289473 ms |
| 後端 audio_samples | 20631568，對應 16000 Hz 完整音訊 |
| final／唯一 seq／health final | 193／193／193 |
| 掉音／重播音訊／重連／自動復原 | 全 0 |
| queue_audio／in_flight／overflow／playback_reset | 結束時全 0 |
| health errors／canceled_batches／recent_errors | 0／0／空 |
| WER raw／normalized | **29.22%／29.18%** |
| 自訂 document chrF | **25.72** |
| 音訊時間覆蓋／邊界附近／未覆蓋 | 117／0／9（共126句） |
| ASR 數字遺失標記 | 12 句 |
| 翻譯數字遺失標記 | 19 句 |
| 否定缺標記 | 1 句 |
| ASR 正負號改變／負數待複核 | 0／0 |
| 人工複核清單 | 29 句 |
| final quality_flags／needs_human_review／reviewed | 27／51／27 |
| final translation_cache_hit | 87 |

人工複核 reference index（0 起算）：

~~~text
3,4,6,11,12,13,14,16,17,27,29,30,32,33,35,36,39,40,43,44,45,46,47,48,71,87,91,92,108
~~~

這些是自動標記，尚未逐句聽音與人工確認。數字檢查不是漏譯的完整證據，未覆蓋也需查 VAD、低音量、錄音邊界等原因；沒有把所有原因直接歸咎模型。此次未任意放大低音量片段或改詞庫來美化分數。

chrF 是目前工具去空白／標點後的 document 字元 n-gram 分數，並非可直接與其他產品或標準工具配置混比的排名。原始 WER、normalized WER 與 chrF 都不是「正確率」。沒有新策略對照組，不能宣稱準確率不退步。

## 6. 速度與資源

下表 nearest-rank，單位 ms，每格 p50／p95；取完整 193 個 final，不用服務端可能截到最近 200 筆的摘要替代整輪。

| 指標 | p50／p95 |
|---|---:|
| capture_to_caption | **6632.0／7771.1** |
| after_speech | **1224.5／2075.3** |
| ASR | 109.0／531.0 |
| ASR queue | 0／0 |
| NMT | 453.0／1218.0 |
| NMT queue | 0／0 |
| delivery_wait | 0／0.2 |

| endpoint | 句數 | capture_to_caption p50／p95 | after_speech p50 |
|---|---:|---:|---:|
| continuous_limit | 101（52.3%） | 7041.5／8062.4 | 1137.1 |
| silence | 92 | 3947.2／6617.0 | 1235.3 |

與 Twitch 素材相比硬切比例高，但不同素材不可直接算改善／退步百分比。此基準適合下一輪用完全相同輸入比較。

**參考句尾延遲有重要限制：** score_eval 得到 p50=979.0、p95=4888.6 ms，但只找到 **3／126 句**可用的句尾匹配；不應作主指標或稱為完整句子的延遲。原始錄音尾端與 VAD 語音尾端並不相同，現有「距參考尾端300 ms」條件過於稀疏。保留原結果，不補零或事後放寬條件。下一輪若要此指標，需可靠語音／字詞對齊。

預覽只是 client 收到事件，不代表畫面顯示：

- 任意翻譯 preview：187／193；比 final 早的 p50／p95 3148.2／5161.3 ms；final 不以前綴開頭比例 49.2%。
- stable phase：181／193；提早 p50／p95 3181.3／5139.0 ms；前綴不一致 64.1%。
- 沒有做 LocalAgreement，也沒有開啟 UI 預設；不能拿旁路數字當實際觀看收益。

推測 attempts=114、translation reused=80、ASR reused=83；停頓定稿譯文沿用 80／92（87.0%），未沿用 34 次。未沿用不等於完全無用途。

監測共77筆、實際1320.02秒，無失敗樣本或後端重啟，GPU placement 最低仍為100%。全GPU顯存取樣5986～7624 MiB、利用率p50／p95=1%／74%。包含重播尾端空檔，沒有把顯存變動或全系統GPU利用率直接判成洩漏。監測開始比重播晚約11秒，因此它的累計差值 finals=191、音訊1278.273秒，不是遺失；完整性以重播原始metrics與health歸零後累計為準。

Ollama 結束時最近200次已完成請求（不是整輪全請求）：

| 階段 | p50／p95 ms |
|---|---:|
| first content token | 250／391 |
| load | 4.2／6.9 |
| prompt processing | 34.5／81.7 |
| generation | 213.6／646.8 |
| wall | 484／1016 |

tokens/s p50=58.2；輸入token p50／p95=329／378，輸出10／27。77筆全程摘要中first-token p95介於282～453 ms，但這是重疊視窗，不相加為總量，也不宣稱全程精確請求分位數。

## 7. 最終測試、版本與剩餘事項

正式重播後再次實跑：

~~~powershell
.venv-win\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
# 48/48，含新增2項回歸
.venv-win\Scripts\python.exe -m unittest discover -s windows -p "test_*.py"
# 32/32，這台Windows不需跳過那2項
npm test
# 64/64
Get-ChildItem extension\*.js | ForEach-Object { node --check $_.FullName }
# 全通過
~~~

合計144項通過。測試內預期故障診斷的RuntimeError不是正式重播服務錯誤。報告提交前另檢查git diff whitespace；只staging本輪檔案。

- 49691e1：浮點WAV相容與RED／GREEN測試。
- 97d13d9：保留低音量語音裁切修正、RED／GREEN測試、文件。
- 本報告另一本機commit，hash以最終git log為準。

下一步應先人工複核29句、調查9個未覆蓋句及低音量案例，再決定要不要加入自然連續語音基準。既有document品質分數與完整final事件可供同素材比較；參考句尾延遲只有3筆，先不要拿來調參。未做新模型、音量處理或LocalAgreement，未做真Chrome／DOM驗收。

保留原工作區修改、私人檔案與模型，沒有推送或發布。下載快取、所有WAV／參考／JSON／JSONL僅留本機並被Git忽略。只留下本輪預設測試服務21880，未做持久環境設定修改。
