# MosaLive Windows 真模型速度驗收

日期：2026-10-23（Asia/Taipei）。驗證提交 `62275e6`、`1ecaadb`，僅本機提交本報告，不 push、tag 或 release。

## 結論

Windows venv 的三套測試全部通過。兩輪均使用真 Faster-Whisper small CUDA 與既有 Qwen2.5:7b，服務完成啟動，`ready=true`、`asr_loaded=true`、翻譯可用、`restart_required=false`。各輪送入相同 245.120 秒音訊，約 250 秒實時重播，產生 40 個 final 字幕事件。

四項環境設定套用後，模型仍為 100% GPU，模型 VRAM 與整卡快照用量各少 52 MiB；翻譯 p95 沒有改善。不能宣稱此次設定讓翻譯加速。這是短音檔重播且大量命中快取的工作負載，不是 40 句不同內容，也不是一般直播或長時間品質驗收。

## 1. 測試與改動範圍

在專案根目錄，以實際 `.venv-win`（未安裝替身套件）執行：

```powershell
.venv-win\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.venv-win\Scripts\python.exe -m unittest discover -s windows -p "test_*.py"
npm test
```

| 套件 | 結果 | 失敗／修正 |
| --- | --- | --- |
| tests Python | 18 通過 | 無 |
| windows Python | 32 通過 | 無 |
| Node | 59 通過，0 失敗／取消／跳過 | 無 |

數字守門案例包含萬／億、12萬5千、3.5億、350 million、twelve hundred、a hundred，以及錯誤數值不可放行。診斷測試包含 GPU 部分卸載警告、模型不在記憶體／服務不可用、200 筆統計上限與健康回應欄位。單元測試內的模擬服務仍是模擬，不將其當真 GPU 測試；以下串流重播另外使用實際模型。

沒有失敗需要歸因或修正，所以未建立 worktree 比較舊版本，也未修改正式程式。沒有可報告的「修正前失敗／修正後通過」案例，因本輪僅驗收。所有既有未提交變更，包括模型預設、START_WINDOWS.bat、extension、server.mjs、文件與 JSON 刪除，以及 navigation-resume 測試，均未修改或加入本輪 commit。

## 2. 啟動與對照控制

- 顯示卡：NVIDIA GeForce RTX 4060 Ti，nvidia-smi 回報總量 8,188 MiB。
- `START_WINDOWS.bat` 選擇既有 `.venv-gpu-test` 啟動執行服務；單元測試則依指定使用 `.venv-win`。兩輪服務都沿用相同啟動檔與環境，沒有切換 venv。
- 啟動前限制 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，禁止 Hugging Face 下載；`MOSA_NO_BROWSER=1` 避免自動開瀏覽器。未下載、升級或替換任何模型。
- 初次檢查沒有發現 Ollama 程序；執行 `ollama list` 時現有安裝的 Ollama 自行啟動桌面 app／server（約 21:43:32）。因此 before 是本輪 CLI 觸發的桌面 Ollama，不是原先就已執行，也不是 launcher 啟動。launcher 隨後確認 Ollama 已在執行並輸出設定提示。
- before 的四項使用者環境變數未設定；尚未執行 SET_OLLAMA_SPEED.bat。未直接讀取 before Ollama 的內部有效配置，不能斷言其程式預設值。
- before 完成後執行 `SET_OLLAMA_SPEED.bat < nul`，四次 setx 均成功。完整結束本輪已核對的 MosaLive 與 Ollama app 程序樹，再將 User 設定讀入新啟動程序，重新執行 START_WINDOWS.bat。after 由 launcher 啟動 Ollama，兩輪的 Ollama 啟動途徑因此不同。
- 保存值：`OLLAMA_FLASH_ATTENTION=1`、`OLLAMA_KV_CACHE_TYPE=q8_0`、`OLLAMA_NUM_PARALLEL=1`、`OLLAMA_MAX_LOADED_MODELS=1`。這些值留在目前 Windows 使用者環境，符合指定操作；可由使用者環境變數設定移除以撤銷。
- 兩輪模型都是 qwen2.5:7b（既有 digest 前綴 845dbda0ea48），ASR small CUDA，context 2048；沒有改提示詞、num_ctx、鎖、排隊或模型設定。這是同版本設定前後比較，不是兩個 commit 與舊程式的速度比較。
- 每輪均等到 `/health` ready 且 restart_required=false 才送音訊；健康資訊的 translation.available 只表示模型存在，另由預熱完成及實際 final 字幕確認真推論可用。

## 3. 固定素材與量測方法

使用倉庫既有 `web/test-en.wav`，不是私人影片；未複製或上傳素材。

- SHA-256：`E05EFF4A0AE4B4BC942B1F411A1162318BEF272E72F74C6F43843D083DE75016`。
- 單聲道、16 kHz、PCM16、106,560 samples，6.660 秒。
- 以 Node 匯入既有 `web/live-client.js` 的 liveInput；每次原音檔後附 1 秒數位靜音，重播 32 次。以每 5,120 samples／320 ms 的速率送入，最後 flush，等待 idle 後停止。
- 使用 `asrMode=stream-en`，quality 保持 liveInput 預設 false（沒有額外開啟 review）；同一 bridge `/live/frame`、原有最多兩批次及緩衝設計，未改程式。
- before／after 各為全新模型服務與串流 session，沒有沿用前輪服務的翻譯快取或統計。每輪內部重複內容仍會命中快取。
- 這是真 ASR／翻譯／既有 liveInput 管線測試；未透過 Chrome tabCapture、AudioWorklet 或 DOM 顯示，因此瀏覽器擷取、UI 延遲與實際直播體驗未驗證。

保存命令：

```powershell
.venv-win\Scripts\python.exe windows\speed_report.py --save quality\speed-before.json
# 執行 SET_OLLAMA_SPEED.bat，結束並重啟本輪服務，重播相同素材後：
.venv-win\Scripts\python.exe windows\speed_report.py --save quality\speed-after.json
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits
```

speed_report 也實際呼叫 ollama ps。兩份 JSON 留在本機 `quality/`，沒有加入 Git。

## 4. 實測 before／after

| 指標 | before | after |
| --- | --- | --- |
| 翻譯模型 | qwen2.5:7b | qwen2.5:7b |
| ASR／裝置 | small／cuda | small／cuda |
| ready／ASR loaded／translation available | true／true／true | true／true／true |
| restart_required | false | false |
| Translator on GPU | 100% | 100% |
| ollama ps PROCESSOR | 100% GPU | 100% GPU |
| 模型 VRAM／模型大小（Ollama MiB） | 4421／4421 | 4369／4369 |
| 整卡已用／總量（nvidia-smi MiB） | 6334／8188 | 6282／8188 |
| 快照 GPU utilization | 2% | 3% |
| ASR p50／p95（ms） | 125／156 | 125／141 |
| 翻譯排隊 p50／p95（ms） | 0／0 | 0／0 |
| 翻譯 p50／p95（ms） | 0／547 | 0／547 |
| 修譯比例 | 0% | 0% |
| timing captions／translated | 40／40 | 40／40 |
| liveInput final 事件數 | 40 | 40 |
| 接收音訊 | 245.120 秒 | 245.120 秒 |
| 重播經過時間 | 249.651 秒 | 250.661 秒 |
| 錯誤／重連／自動恢復 | 0／0／0 | 0／0／0 |
| 丟棄／重播／結束時待送音訊 | 0／0／0 ms | 0／0／0 ms |

VRAM 是完成後快照，不是峰值；Ollama 模型占用與整卡占用不同。GPU utilization 也是當下瞬時值，不能拿 2%／3% 推論整段沒有使用 GPU。後測中途另量到 48% utilization，但未連續採樣，峰值仍未驗證。

百分位沿用現有 timing_summary：排序後取 `min(n-1, int(q*n))` 索引並四捨五入。Windows 計時有解析度限制；0 ms 不表示沒有所有處理成本。translated 計數也包含快取結果，不等於 40 次不同的模型推論；快取命中數未另量測。

## 5. 瓶頸判斷與界線

**已實測：** 此工作負載沒有模型被擠到 CPU（兩輪 100% GPU）、翻譯排隊（p95=0）、過度修譯（0%）或音訊堆積／丟棄。ASR p50 相同，p95 少 15 ms；只有各一輪且無連續環境採樣，不能將差異歸因於設定。翻譯 p95 完全相同，沒有量到加速。

**程式碼推論／未驗證：** 多數翻譯耗時為 0 與重播快取一致，因此不能用這組 p50 代表真模型生成速度。未獨立分離快取與非快取延遲，未量 VAD／顯示端，無法據此指定一般直播的主要瓶頸。數字守門的新情境通過 Windows 單元測試，但未逐句送入真模型做數字翻譯品質評分。

## 6. 下一步與交付狀態

1. 目前不建議僅因記憶體用量而換模型：設定後仍是 100% GPU。若未來實測低於 100%，可另比較 gemma3:4b、qwen2.5:3b 或 START_WINDOWS_CPU_ASR.bat，由使用者先決定，不自動切換。
2. 以有授權、至少 30 句不同內容的固定音訊補測；在不改提示詞及快取邏輯下，另外標記快取命中，區分冷／熱翻譯 p50／p95。此次未建構或下載新素材。
3. 補真正 Chrome 擷取到畫面的端到端 p50／p95、VAD 等待、長時間連續直播、30 分鐘以上閒置保活驗證；目前未驗證。
4. 兩個 commit 的 Windows 測試和真模型基本相容性已驗收，但不等於翻譯準確率或一般直播速度提升已證明。
5. 未修改任何既有 dirty 檔、模型或私人媒體，未操作容器或 MosaSub 使用者資料。僅提交本報告；量測 JSON 不提交。服務保持後測就緒狀態，四項使用者設定保留。
