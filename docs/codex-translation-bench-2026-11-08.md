# 純翻譯基準｜2026-11-08

## 條件

Windows、RTX 4060 Ti 8 GB，FLEURS 英文 126 句，正規化素材對應 reference；不啟動 MosaLive、不執行 ASR 或重播。`translation_bench.py` 使用 `translation_messages(source, [], [])`，不帶前文和詞庫，與正式流程不同。每個變體各兩次，共 252 次；順序固定，temperature 0、context 2048、num_predict 160。chrF 是相對參考譯文的逐句字元相似度平均，不是翻譯準確率；異常、數字和否定均為待核對的規則旗標，不等於人工確認錯誤。

Windows `.venv-gpu-test` 測試 `test_translation_bench.py` 4 項、`test_output_anomalies.py` 8 項均通過。qwen 先執行 5 句 × 3 變體 × 2 次的煙霧測試，30 次呼叫均無錯誤；之後執行完整 756 次。Ollama qwen2.5:7b 為 100% GPU，暖載後整卡使用 6074／8188 MiB。

## 彙總（每列 252 次呼叫）

| 模型／變體 | 亂碼 U+FFFD | 程式殘字 | 一般英文全大寫 | 中文逐字空格 | 異常聯集 | 疑似人名大小寫 | 數字旗標 | 否定旗標 | 平均 chrF | 耗時 p50／p95 ms | 呼叫錯誤 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| qwen baseline | 1 | 0 | 15 | 0 | 15 | 9 | 10 | 2 | 31.22 | 844／1281 | 0 |
| qwen caps_rule | 4 | 0 | 17 | 0 | 17 | 6 | 11 | 2 | 30.82 | 859／1328 | 0 |
| qwen acronym_reword | 2 | 0 | 16 | 0 | 16 | 10 | 10 | 4 | 30.75 | 875／1344 | 0 |
| gemma3:4b baseline | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 2 | 28.22 | 734／984 | 0 |

單次呼叫可同時有多個旗標，不能把四類相加當聯集；旗標與人名判斷均依工具啟發式。Gemma 沒有被四類規則抓到異常，不代表語意正確。Gemma 暖載時 `ollama ps` 顯示 100% GPU、模型 2.8 GB、context 2048；整卡使用 6567／8188 MiB。兩次 VRAM 快照含桌面等其他程序，且模型切換後的時間點不同，不能直接相減得出模型獨占用量。

## 重複及抽查

以同變體、同句的兩次譯文逐字比較：qwen baseline 有 42／126 句不同、1 句異常旗標不同；caps_rule 46／126、1 句旗標不同；acronym_reword 0／126、0 句旗標不同。Gemma baseline 0／126、0 句旗標不同。baseline 兩輪異常候選分別為 7、8；caps_rule 為 8、9；acronym_reword 均為 8；Gemma 均為 0。這是兩次執行觀察，temperature 0 仍不保證每次相同，也不能推論所有環境都會重現。

以同 repeat 的 baseline 比較：caps_rule 沒有使 baseline 的候選消失，第一輪新增索引 83、第二輪新增索引 1；acronym_reword 第一輪新增索引 83，第二輪無新增或消失。索引 83 的 baseline 正常包含 TogiNet Radio，兩種變體卻輸出 `INTERNET �`，同時觸發大寫和亂碼；caps_rule 第二輪索引 1 多出 `TODAY`。以上是少量候選抽查，不能視為完整人工評分。

這 126 句內未找到 NASA 或 GPU 原文，因此這兩個縮寫是否被誤譯**未驗證**。有 AI 與 UN：qwen 各變體把 AI 譯為「人工智慧」、UN 可譯為「聯合國」或保留 UN，屬可接受的縮寫翻譯候選；索引 57 的 qwen 保留人名 Danielle Lantagne，Gemma 譯作「丹尼爾·蘭塔涅」，但省略 UN 專家身分，值得人工複核。索引 20 的兩種修改提示詞輸出仍含一般英文 `Deals with`，現有全大寫規則未抓到，顯示異常旗標不涵蓋所有未翻譯英文。

## 產物及清理

原始逐次結果與 summary 分別在 `quality/translation-bench-20261108/`、`quality/translation-bench-20261108-gemma3-4b/`；煙霧測試另在 `quality/translation-bench-20261108-smoke/`。本機 `ollama list` 只有 qwen2.5:7b、gemma3:4b，沒有下載模型。測試結束已停止本次啟動的 Ollama 程序，11434 無監聽；整卡 GPU 使用降至 2983／8188 MiB，餘量包含其他桌面程序。

qwen 三變體結果沒有顯示修改提示詞降低異常候選；Gemma 候選為零但 chrF 較低且有漏掉 UN 身分的例子。是否採用任何變體或模型仍需更多素材和人工語意評估，本次不更改正式預設。