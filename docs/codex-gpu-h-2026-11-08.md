# H 輪 turbo＋Gemma 重播｜2026-11-08

**更新：後續依 15% 門檻重跑已完整完成，最新結論見文末；以下保留首次失敗與預檢紀錄。**

## 結論

**H 沒有完成，無法評分，也無法認定符合預設候選條件；依本次判定規則，建議暫時維持 qwen。** E 的完整數據可參考 `docs/codex-gpu-de-2026-11-08.md`；H 沒有完整事件 JSON，不能計算 WER、chrF、人工複核、數字或否定標記、異常數與延遲百分位，四項候選條件均未驗證，不是宣稱它們均已失敗。

## 實際執行

直接以 `.venv-gpu-test` 啟動 `windows/launch.py`，暫時環境變數使用本機 large-v3-turbo snapshot、`HF_HUB_OFFLINE=1`、`MOSA_NMT_MODEL=gemma3:4b`、soft cut 3500 ms、breath cut 關，與 E 的斷句條件相同；未下載或複製模型，未更改正式預設和批次檔。啟動前確認 8787、8790、11434 無監聽。health 確認 ready、ASR 載入、翻譯可用、restart_required=false、計數歸零；Ollama 顯示 gemma3:4b、100% GPU、context 2048。

開始前 nvidia-smi 顯示整張 GPU 已用 4406／8188 MiB、利用率 36%，程序清單沒有列出來源；不能保證測試環境空閒。H 於完成 104 段定稿後停滯約三分鐘，服務 health 仍顯示可用、errors=0，但查看時已累積 14 個 canceled_batches，音訊進度落後牆上時間。最後一筆抽樣為牆上 792 秒、處理音訊約 690 秒、定稿仍 104 段。為避免無限占用 GPU，已手動終止本次 H 程序樹；因此重播沒有產生完整結果 JSON，replay.log 為空，不能做異常掃描或評分。

27 筆約 30 秒 GPU 抽樣中，記憶體使用最高 **7680／8188 MiB**（僅抽樣峰值，非持續量測的絕對峰值），各次 `ollama ps` 均顯示 Gemma 100% GPU。停滯時另一次即時查詢為 7599 MiB、GPU 利用率 100%。這些現象不足以判定停滯根因或斷言顯存不足；需在可確認其他 GPU 程序狀態的環境重跑並保留更完整服務與客戶端事件日誌。

## 產物與清理

本次資料保存在 `quality/endpoint-H-20261108-150402/`：啟動前 health、GPU、Ollama 狀態，27 筆 monitor，及服務／重播日誌。狀態檔最後仍寫 `running`，因測試程序被手動終止；這不是目前程序狀態。終止程序後確認 8787、8790、11434 無監聽；GPU 記憶體降至 2606 MiB，但當時利用率仍為 98%，來源未確認，不代表整台電腦 GPU 閒置。僅本機提交本報告，不 push。
## 重跑前檢查：未開始

依重跑指示進行約 60 秒、每約 1 秒的 NVIDIA GPU 取樣，共 57 筆。第 0.08 秒與第 1.14 秒的利用率皆為 **11%**，其餘 55 筆低於 10%；顯存最高 **1014 MiB**，低於 2.5 GB。因存在 2 筆未滿足「連續 60 秒低於 10%」，本輪依指示沒有啟動 H、MosaLive 或 Ollama，也沒有執行重播與看門狗。取樣無法覆蓋樣本間瞬間變化，即使通過也只能說抽樣期間通過。

`nvidia-smi --query-compute-apps` 與完整程序清單在另一時間點列出 Chrome（PID 7432）、Discord（18208）、Claude（8312、24464）、NVIDIA Overlay（13888、14932）、Windows Explorer（9944）與其他桌面程序；WDDM 對各程序顯存皆回報 N/A。Windows GPU Engine 效能計數器抽樣列出 PID 1376 約 0.38%、PID 1932 約 0.25% 的 3D 引擎使用，之後查詢時已無法取得這兩個 PID 的程序名稱。這些程序清單與 11% 取樣並非同時記錄，無法判定哪個程序造成尖峰，不應把上述程序當成已確認的肇因。沒有關閉任何使用者程序。

預檢原始取樣保存在本機工作區 `whatsub-prototype/tmp/mosalive-H-preflight.json`。上一輪 H 的失敗與未驗證結論仍適用；本次沒有新重播結果、評分或模型變更。
## 15% 門檻重跑：完整結果

使用者將開跑前 GPU 門檻調整為低於 15%，顯存仍低於 2.5 GB。約 60 秒共 57 筆取樣，最高 14%、1035 MiB，全部符合；每秒抽樣不能保證間隔內沒有尖峰。NVIDIA 程序清單包含 Chrome、Discord、Claude、NVIDIA Overlay 與 Windows 桌面程序，WDDM 的個別顯存為 N/A；Windows GPU Engine 計數器亦已讀取，無法將 GPU 峰值歸因至特定程序。三個服務埠於啟動前無監聽。

以本機 turbo snapshot、Gemma 4B 與 C／E 相同 soft cut 3500 ms 啟動；ready、ASR 已載入、翻譯可用、restart_required=false、計數歸零均通過。僅暫時設定模型和環境變數，沒有下載或複製模型，也沒有修改預設。重播完整 1289473 ms 音訊，耗時約 1299 秒；掉音、重連、overflow、播放重設均為 0，43 次 health 抽樣的 canceled_batches 最大值為 0，看門狗未觸發。

| 指標 | E：turbo＋qwen | H：turbo＋Gemma |
|---|---:|---:|
| 原始／正規化 WER | 8.25%／8.10% | 8.25%／8.10% |
| chrF | 31.31 | 29.64 |
| 需人工複核定稿 | 9 | 8 |
| 翻譯數字遺失／缺否定標記 | 4／0 | 4／0 |
| 異常掃描候選定稿 | 14 | 0 |
| 說完到定稿 p50／p95 ms | 1158.5／1802.3 | 1095.4／1623.6 |
| 開口到定稿 p50／p95 ms | 5700.5／7422.5 | 5537.0／7315.7 |
| 翻譯 nmt_ms p50／p95 ms | 532／968 | 485／797 |

四項指定門檻在本次觀察均符合：異常候選 14→0；說完到定稿 p50 較低；數字與否定旗標未增加；chrF 下降 1.67（不超過 2）。因此 **H 可列為建議預設候選**。這是各一次的 FLEURS 離線重播與規則候選，chrF 並非語意準確率；既有純翻譯測試曾發現 Gemma 遺漏 UN 專家身分，正式改預設前仍需真人語意複核及真實 Chrome／Twitch 顯存驗收。此次未修改預設。

E/H 延遲可比性工具標示 `A/B on translation`（使用自有 ASR p50 判斷機器速度），只是經驗警戒檢查；兩輪均為單次，不作顯著性推論。H 最近 200 筆 ASR p50／p95 為 188／484 ms、翻譯 485／797 ms，Ollama 88 tokens/s p50。43 筆 GPU 抽樣全部顯示 Gemma 100% GPU，顯存抽樣峰值 6085／8188 MiB，不是連續量測絕對峰值。每筆監測含 timing 與 canceled_batches。

結果及監測保存在 `quality/endpoint-H2-20261108-162443/`，包含 H 原始事件、health、speed、GPU 抽樣、`EH-anomalies.json` 和 `EH-comparison.json`。本輪程序已結束，確認 8787、8790、11434 均無監聽；不 push。