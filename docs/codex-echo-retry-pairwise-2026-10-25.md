# Echo guard：四輪結果的配對重評

日期：2026-10-25  
評分器：2026-10-25.1（本機 commit d5fd1eb）  
範圍：只重讀四輪既有 JSON，沒有重播、載入 ASR／翻譯模型或使用 GPU；原始結果與參考素材未修改。

## 結果檔

- A：quality/echo-retry-off-A-20261025.json（guard 關）
- B：quality/echo-retry-on-B-20261025.json（guard 開）
- C：quality/echo-retry-off-C-20261025.json（guard 關）
- D：quality/echo-retry-on-D-20261025.json（guard 開）
- 新評分輸出：quality/echo-retry-20261025-scorer-2026-10-25.1.json

## 配對可比性

每一對都重新判斷設定差異及速度指標。A/B、A/D、B/C、C/D 都只差 tuning.asr_echo_retry，評分器排除會受重試影響的 ASR 時間，以 Ollama tokens/s p50 作為機器速度代理；相差均在 10% 經驗警戒值內。A/C（關）及 B/D（開）設定一致，兩種速度代理均可用且相近。

| 配對 | 判定 | 可用速度代理 |
|---|---|---|
| A vs B | 單一設定 A/B：echo guard | Ollama tokens/s |
| C vs D | 單一設定 A/B：echo guard | Ollama tokens/s |
| A vs D | 單一設定 A/B：echo guard | Ollama tokens/s |
| B vs C | 單一設定 A/B：echo guard | Ollama tokens/s |
| A vs C | 同設定可比 | Ollama tokens/s、ASR p50 |
| B vs D | 同設定可比 | Ollama tokens/s、ASR p50 |

10% 是經驗警戒線，不是統計檢定。資料只有每種設定兩次重播，不能視為顯著性結論。

## 品質與延遲

| 指標 | Guard 關 A/C | Guard 開 B/D |
|---|---:|---:|
| 原始 WER | 16.31% | 13.67% |
| 數字正規化 WER | 16.24% | 13.60% |
| chrF | 30.00 / 29.88 | 30.96 / 30.98 |
| 覆蓋／邊界／漏句 | 每輪 126 / 0 / 0 | 每輪 126 / 0 / 0 |
| ASR 數字遺漏標記 | 每輪 9 | 每輪 5 |
| 翻譯數字遺漏標記 | 每輪 6 | 每輪 3 |
| 否定缺標記 | 每輪 1 | 每輪 0 |
| ASR chat 類單獨輸出 | 每輪 8 | 每輪 0 |
| ASR p50 / p95 | A 156 / 718 ms；C 156 / 703 ms | B 157 / 688 ms；D 171 / 734 ms |
| 停句後至定稿 p50 / p95 | A 1301 / 2492 ms；C 1328 / 2336 ms | B 1338 / 2368 ms；D 1358 / 2403 ms |
| 擷取至定稿 p50 / p95 | A 6904 / 8083 ms；C 6901 / 8058 ms | B 6916 / 8066 ms；D 6941 / 8174 ms |
| Ollama tokens/s p50 | 46.9 / 46.8 | 47.2 / 43.3 |

開啟時每輪有 34 次重試，34 次都改變文字；重試時間 p50 約 141 ms、p95 約 281 ms。停句後至定稿 p50 在兩組配對各增加約 37 ms、30 ms。相同設定重跑的 p50 差約 26 ms（關）及 20 ms（開），所以只能說觀測到約 30 ms 的小幅增加，無法把它和執行波動可靠分開。p95 的配對方向不一致，也不足以證明延遲退步。

四輪的 WER、數字與否定標記都呈現 guard 開啟時較好，且單獨輸出 chat 類的結果由 8 降至 0；這是同一素材上的兩次重播配對，不代表普遍準確率保證。chrF 小幅增加，不單獨視為語意正確性的證明。

## 誤觸與限制

這份 FLEURS 參考沒有講者刻意只說 chat 或 thanks chat 的正向控制片段，因此無法用本輪素材確認 guard 是否會把真實的單字 chat 誤當提示詞回聲。仍需錄製短控制音訊，逐句聽取初次輸出與重試結果。數字與否定標記也是待人工複核訊號，不是語意評分。

## 驗證

- 四份既有結果由 scorer 2026-10-25.1 成功重評；新 JSON 使用新檔名，未覆寫舊評分。
- tests/test_fleurs_eval.py exit code：0。
- npm test exit code：0。
- 未執行完整資料集重播、未啟動模型，未量 GPU；未驗證 Chrome 正向控制錄音。

完整 unittest discover 的兩套（tests 與 windows）曾啟動，但在本受限工作階段超過 90 秒沒有輸出，已中止；它們沒有完成，不能視為通過或失敗。受限沙箱內首次執行時，Python 暫存檔原子替換遇到 PermissionError，npm 的兩個 localhost API 測試遇到 EACCES；在允許本機測試服務與暫存檔操作的執行環境重跑後，針對性 Python 與完整 npm 測試均通過。
