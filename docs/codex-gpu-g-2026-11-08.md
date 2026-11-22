# G 輪：翻譯異常修譯試驗｜2026-11-08

## 條件與驗證

Windows、RTX 4060 Ti 8 GB；沿用 C 輪 FLEURS 126 句、small CUDA、conservative、soft cut 3500 ms、qwen2.5:7b、context 2048、停頓推測開、echo retry 關。G 以暫時環境變數 `MOSA_OUTPUT_ANOMALY_REPAIR=1` 啟動，其餘設定相同；C、G 各只有一次完整執行，不作統計顯著性結論。G 音訊 1289473 ms、耗時約 1301 秒，掉音、重連、overflow、播放重設均為 0。

Windows `.venv-gpu-test` 中 `test_output_anomalies.py` 7 項、`test_numeric_translation.py` 8 項、`test_translation_engine.py` 3 項全部通過。G 的環境變數由本輪啟動腳本設定；health 的 tuning 不含此開關，因此既有評分器的設定比較無法識別此差異。

## C／G 整體比較

| 指標 | C：關閉 | G：開啟 |
|---|---:|---:|
| 原始／正規化 WER | 13.16%／12.94% | 13.16%／12.94% |
| chrF | 30.03 | 30.23 |
| 定稿／人工複核定稿 | 230／13 | 230／20 |
| 翻譯數字遺失旗標（參考句） | 5 | 5 |
| 缺否定詞旗標（參考句） | 0 | 0 |
| 掃描器異常候選定稿 | 7 | 7 |
| 異常候選未被當時 quality_flags 標記 | 7 | 0 |
| 說完至定稿 p50／p95 ms | 1058.6／1703.6 | 1188.0／2052.3 |
| 開口至定稿 p50／p95 ms | 5516.5／7471.0 | 5766.5／7845.4 |

逐參考句比對既有評分器旗標：G 沒有新增數字遺失或缺否定標記的句子。這些旗標不是對語意或實際數字正確性的完整人工檢查。WER 不變；chrF 是文字相似度，不是翻譯準確率。

延遲可比性檢查為 `machine speed differs`：自有 ASR p50 140 → 156 ms（+11%，超過經驗門檻），Ollama 最近 200 次 tokens/s p50 56.8 → 51.3。評分器的 tuning 沒列試驗開關，也無法自動識別 C/G 的異常修譯差異。以上整體延遲數字不得直接歸因於試驗。

## 觸發與殘留

G 共 13 筆觸發修譯；修譯前旗標為 `uppercased_source_word` 9、`replacement_character` 1、`code_residue` 1、既有 `number_mismatch` 1、`possible_missing_negation` 1。前 11 筆由異常類旗標觸發；同一筆可有多個旗標，本輪各筆剛好分開。掃描器在 G 修譯後仍標示 7 筆，全部曾修譯，均為大寫英文候選（seq 58、70、105、151、185、196、231）；C 亦為 7 筆候選，兩輪候選並非全部相同。G 的 seq 159 亂碼旗標與 seq 196 程式殘字旗標修後消失，但 seq 196 改為大寫英文候選。

人工抽查候選：seq 19 的 EARLY 與 seq 105 的 TOUR 為原文一般詞殘留，觸發有依據；seq 70 的 GREAT PYRAMID 對應原文 Great Pyramid 專名，可視為可能誤觸發，需人工確認專名大小寫政策。seq 54 的數字與 seq 66 的否定旗標屬原有檢查而非本次新增異常類，不能僅憑旗標斷定譯文錯誤。重播事件保留觸發前旗標，但沒有保留每筆修譯前完整譯文，因而無法對全部 13 筆判定誤觸發或逐筆證明修前修後的語意變化。

G 修譯定稿的 nmt_ms 共 13 筆，p50／p95 為 1547／2000 ms；未修譯定稿 217 筆為 609／969 ms。以相同 seq 且原文相同的 13 組 C/G 配對，G 減 C 的 nmt_ms 差值 p50／p95 為 813／1250 ms；因機器速度不同、句子及生成長度不同，此值是觀察差距，不是嚴格的單次修譯因果成本。

## 直接串流重跑

重播結束時 Ollama 已停止，第一次直接呼叫收到 11434 連線拒絕；已保留 `direct-stream.jsonl` 失敗紀錄。之後只啟動本次專用 Ollama，對 A seq 18、116、150、187 與 E seq 134、231 各 3 次呼叫 `translation_messages` 組出的訊息，使用 stream、temperature 0、num_ctx 2048、num_predict 160；逐行原始 NDJSON bytes 以 base64 保存於 `direct-stream-retry.jsonl`。所有 18 次重試收到回應。

既有事件沒有保存原次呼叫的完整 messages、前文與詞庫快照；此次使用空前文、空詞庫，是近似條件，不能宣稱與原請求完全相同。A seq 18 的 U+FFFD 在 3/3 次的 Ollama 返回內容出現；E seq 231 的 `!!");` 在 2/3 次返回內容出現。這證實兩種異常在這些近似重跑中已存在於模型串流的 message content，而非必須經過 MosaLive 後處理才產生；不能據此斷定所有異常的來源或排除其他串流問題。temperature 0 下 E seq 231 仍有 1 次不同輸出。

## 檔案與清理

C/G 掃描 `CG-anomalies.json`、比較 `CG-comparison.json`、G 原始事件、score、speed、健康狀態及 GPU 抽樣都位於 `quality/endpoint-G-20261108-130951/`；舊結果未覆蓋。G 的 Ollama 為 100% GPU，重播後 GPU 使用 7631／8188 MiB。MosaLive 測試程序及直接重跑新啟動的 Ollama 均已停止，確認 8787、8790 沒有監聽。沒有修改正式預設或 START_WINDOWS.bat；只在本機提交本報告，不 push。