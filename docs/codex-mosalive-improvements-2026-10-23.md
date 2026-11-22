# MosaLive 翻譯準確度與速度檢查報告

日期：2026-10-23。僅本機提交，未 push、tag 或 release。

## 專案確認與範圍

- 專案：`C:\Users\howwa\Downloads\voxmosa\中華電信比賽\MosaSub-Live-Windows`。
- 遠端身分：`Voxmosa/mosasub-live`；版本 0.3.6，開始檢查時 HEAD 為 `e6b7e6a`。
- 已建立題名為 `mosalive` 的分支聊天；未宣稱已變更聊天所屬專案。
- 開始時已有模型設定、擴充套件、伺服器、文件等未提交變更，以及既有評測 JSON 刪除。本輪未修改或提交它們；Gemma 模型設定保持使用者原狀。
- 已有的穩定字幕判定、有限快取／上下文、播放重設取消、雙批次管線及階段時間指標沒有重寫。

## 本輪修正與 commits

### 1. 數字誤判造成不必要的二次翻譯

Commit：`c3a391c`。

原先正確的數字翻譯也可能被判錯：英文複合數字與逗號分組小數沒有正確對應，例如英文 125 的文字形式與數字 125。這會觸發額外修譯，增加等待，也可能讓原本正確的譯文被再次改寫。

修正 `windows/quality_checks.py`：辨識支援的英文百、千、百萬、十億組合，正規化數字分組與小數零；保留各自獨立的數字，不把「one and two」直接加成 3。使用字串處理小數，避免浮點精度損失。未增加依賴、改提示詞或換模型。

新增 `tests/test_numeric_translation.py` 與可重跑的 `windows/benchmark_numeric_guard.py`。

- RED：修正前，數值等價測試與模擬 ASGI 路由測試失敗；正確譯文仍觸發 2 次翻譯。
- GREEN：數值等價通過；錯誤數值仍被攔截；同一受控路由只呼叫 1 次翻譯。
- 侷限：不是通用數學或所有語言的數值解析器；中文萬／億、口述分數、正負號及各地小數格式等未完整涵蓋。

### 2. 修復 Chrome 擷取測試的失真與等待

Commit：`6cb4fdd`。

既有測試未模擬服務健康檢查，且固定呼叫第一個訊息監聽器，不符合目前背景程式的多監聽器行為。只更新測試環境與訊息派送，並加入服務未就緒不可啟動擷取的案例；未修改既有未提交的擴充套件程式。

- RED：有時間上限的原完整 Node 測試為 58 項，54 通過、2 失敗、2 取消。
- GREEN：擷取相關 8 項通過；完整 Node 測試增加新案例後 59 項全通過。

## 已實測：受控比較

指令：

```powershell
.venv-win\Scripts\python.exe windows/benchmark_numeric_guard.py --baseline-ref e6b7e6a
```

以 Git 舊版本守門函式在記憶體中比較目前函式，同一現行路由、合成音訊及固定假翻譯器，交替各跑 5 次，沒有使用私人影片或真正模型。

| 指標 | 舊守門函式 | 修正後 |
| --- | --- | --- |
| 每次翻譯呼叫數 | 2 | 1 |
| 不必要修譯 | 每次發生 | 未發生 |
| 模擬管線 nmt_ms 中位數 | 47.0 ms | 16.0 ms |

假翻譯器每次設定等待 20 ms；Windows 計時解析度會讓讀值量化。上述毫秒數不能視為真模型加速幅度，也不代表實際端到端延遲。可靠結論是此案例少了一次不必要的推論。

受控量測輸出：`%TEMP%\mosalive-numeric-benchmark-20261023.json`。

## 已實測：回歸與語法

```powershell
npm test
.venv-win\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
.venv-win\Scripts\python.exe -m unittest discover -s windows -p 'test_*.py'
node --check server.mjs
node --check extension/background.js
git diff --check
```

- Node：59 項通過，含同步檔案檢查。
- Python tests：12 項通過；windows：32 項通過。
- Node 語法與 windows Python AST 解析通過；diff 空白檢查通過。
- 此專案沒有 `npm run check` 或 `npm run test:python`，因此執行上列實際可用的對應驗證，而非宣稱不存在的指令通過。
- 驗證是在保留既有未提交變更的現行工作目錄執行，不是乾淨 HEAD 的獨立驗收。
- 完整輸出：`%TEMP%\mosalive-node-final-20261023.log`、`mosalive-python-final-20261023.log`、`mosalive-windows-final-20261023.log`。

## 未驗證與推論

實際連線檢查時，8787、8790 健康端點及 11434 Ollama 端點均無法連線。因此沒有宣稱 ASR 已載入、翻譯模型已就緒或 GPU 推論成功。未啟動可能自動下載模型的正常啟動流程；未下載、升級或修改模型，未動私人媒體、MosaSub 資料或容器。

程式碼可確認已有 ASR／翻譯排隊、推論及擷取到字幕等時間指標，但沒有量到本輪真實 VAD、ASR、翻譯、渲染各階段延遲。

後續仍需在既有模型服務啟動後驗證：

1. 用固定且有標準答案的素材測人名、數字、否定句、中英混雜與背景音；記錄錯誤率，而非主觀宣稱更準。
2. 分別量首次字幕、穩定字幕及語句結束後延遲的 p50／p95；包含翻譯佇列與 UI，不只推論時間。
3. 真人連續使用與 Twitch／分頁切換長時間測試，觀察字幕回跳、延遲累積、記憶體與恢復能力。
4. 目前執行中的服務不會自動載入 Python 修正；正式驗證前需確認載入新版。此次沒有擅自停止或重啟服務。

建議先做這些可比較的真實量測，再決定分段策略、詞庫或模型調整；本輪不憑受控測試更換預設模型。
