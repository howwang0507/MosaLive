# MosaLive 離線工具與品質診斷｜2026-11-08

工作跨 2026-11-07／11-08 午夜；結果目錄沿用本輪開始日期。

## 執行範圍與驗證

- 全部為既有 JSON、程式碼和模型目錄的離線讀取；未啟動 MosaLive、Ollama、Chrome 擷取或任何模型推論，未下載模型。Python 分析與測試皆由暫用 runner 先設 `BELOW_NORMAL_PRIORITY_CLASS` 後執行；未改系統電源、遊戲或 GPU 設定。
- 保留既有未提交的 UI、README、啟動檔、models.py 等修改；只提交本輪離線工具、測試與報告，沒有 push、tag 或 release。
- 既有 `tests/test_fleurs_eval.py` 23 項、本輪單位測試 3 項、診斷工具 10 項，全數通過（共 36 項）。現有測試顯示的 Downloading 是 mock 網址測試，不是實際下載。未跑會載入模型的 Windows 服務測試，也未重跑 GPU。
- 單位測試在舊程式上有 5 個 alias 子案例失敗，修改後通過。診斷工具屬新增 CLI／分析能力，舊稿沒有同等測試介面，未宣稱這 10 項有相同的舊版紅綠對照。

## 1. 單位正規化與 A/B/C 重新評分

評分器更新為 `2026-11-07.1`。只在數字正規化口徑統一 km／kilometer(s)／kilometre(s)、kg／kilogram(s)、GHz／gigahertz；%／percent 原本就等同，本輪保留並加測。原始 WER 的 tokenizer 不變；不換算數值或尺度，保留正負號、小數點，kg 與 km 仍不同。

| 輪次 | 原始 WER（前後相同） | 正規化 WER：舊 → 新 | 錯字數：舊 → 新 |
|---|---:|---:|---:|
| A-default | 16.31% | 16.24% → 16.13% | 443 → 440 |
| B-breath | 14.66% | 14.59% → 14.48% | 398 → 395 |
| C-soft3500 | 13.16% | 13.05% → 12.94% | 356 → 353 |

每輪分母皆為 2,728 個正規化參考詞；少掉的全是 **3 次 km → kilometers 寫法差異**，沒有把真正聽錯修好。此素材沒有 kg 或 GHz 別名改分的實例，它們只有單元測試驗證。以同一 JSON 核對，原始 WER、chrF、覆蓋與品質標記、延遲、預覽旁路及 Ollama 統計均與舊比較檔完全相同。

## 2. 正式診斷工具

`windows/diagnose_errors.py` 取代 `Claude outputs/diagnose_errors.py`；舊稿移除前另留本機備份，其他 Claude outputs 文件未動。reference 改為必填參數；所有 JSON 讀寫指定 UTF-8；支援多檔、多 result，拒絕覆寫輸出，對斷線／丟音／播放重設／overflow 拒絕宣稱精確對齊。

| 輪次 | 漏字 D | 多字 I | 辨錯字 S | 邊界／句中／不確定 | 數字／疑似專有名詞 |
|---|---:|---:|---:|---|---|
| A-default | 167 | 90 | 183 | 278／142／20 | 22／77 |
| B-breath | 154 | 49 | 192 | 238／137／20 | 23／74 |
| C-soft3500 | 93 | 65 | 195 | 217／132／4 | 19／78 |

**分類是啟發式：** 邊界指每筆定稿前後各 2 個 hypothesis token，不是音訊層級判斷；漏字以兩側最近 hypothesis token 估計，兩側不一致或無錨點列「不確定」。專有名詞依非句首大寫詞估計（排除 I），不是 NER 或人工確認。數字是數值 token 錯誤，不等於數字旗標。短字幕大部分 token 本來就在邊界，不能用錯誤數較多來推論「硬切造成」。

## 3. 翻譯與辨識分開看

| 輪次 | 入選／126 句 | 原文完全一致 | 原文 1 個 word error |
|---|---:|---:|---:|
| A-default | 48 | 29 | 19 |
| B-breath | 54 | 30 | 24 |
| C-soft3500 | 52 | 27 | 25 |

「完全一致」指既有 raw tokenizer 的英文 token 一致（忽略大小寫和標點），不是原始字串逐位元相同。採原始 WER 口徑全文對齊再篩選，不藉單位正規化掩蓋辨識差異。每句各算 chrF；每輪最低 10 句（原文、實際辨識、譯文、參考譯文）見 [樣本附錄](codex-offline-translation-samples-2026-11-08.md)，完整入選列也在新 JSON。
完全一致的 ASR 樣本仍可見殘留英文、輸出疑似截斷與異常字元，值得下一輪排查翻譯輸出／後處理；這裡只列候選，不做語意評分。同義改寫、人名保留亦可能得到低 chrF；1 個 ASR word error 仍可能是關鍵專名，不能把整組當成純翻譯準確率。各輪入選句不同，不能拿最低分或入選數直接排名翻譯模型。

## 4. 原文 Agreement 旁路

以 AST 只擷取 `windows/live_audio.py` 的純 `Agreement` 類別（未匯入 live_audio 或 VAD），依各 seq 的非定稿 `phase=asr` 原文順序重演，與事件中的 `stable_original` 比對；`commit_samples` 的 ASR 事件屬強制定稿，另列、不送入 update。

| 輪次 | 非定稿更新 | 重演不一致 | 已確認原文後來被撤回 | stable→final 配對數 | 字元距離 p50／p95 |
|---|---:|---:|---:|---:|---|
| A-default | 1016 | 0 | 99 | 367 | 14／32 |
| B-breath | 1059 | 0 | 107 | 385 | 12／32 |
| C-soft3500 | 944 | 0 | 90 | 303 | 15／32 |

這批紀錄足以重演**已收到的原文 Agreement 更新**；三輪所有 ASR 事件都有 stable_original。撤回定義為：同 seq 上一個非空穩定原文不再是後續穩定原文的完整前綴，含縮短、清空、改字及強制定稿衝突。其中 Agreement update／強制定稿衝突分別為 A 81／18、B 91／16、C 68／22。這是字元前綴變動（可能包含標點變更），不是辨識錯誤率；stage 細分保留在新 JSON。
字元距離使用評分器既有的中文 NFKC＋去空白標點口徑，計算每一個已收到的完整 stable 譯文對該 seq 定稿的 Levenshtein 距離；不是只取每句第一次預覽，因此配對數不同於舊報告。它包含自然追加的尾端，不能解讀成「改寫了多少字」。
**仍不足：** 無法重建未送出的內部更新、reset／跳過原因，也沒有 Chrome 實際 DOM 採用事件。下一次 GPU／Chrome 測試可額外記 session／generation／seq、單調 update ID、Agreement reset 原因、更新前後穩定原文、是否 final／重用、翻譯所依據的 source-update ID，以及 DOM 採用的原文／譯文、phase、單調時間戳。這輪未加正式記錄、不補測，也未驗證新 Agreement 策略的效果。

## 5. 下一輪模型準備（只讀）

- ASR：`windows/models.py` 由 `MOSA_ASR_MODEL` 讀取，fallback `small`；launcher 繼承環境變數。但 `START_WINDOWS.bat` 明寫 `MOSA_ASR_MODEL=small`，會覆蓋事先設定，所以不能只在該批次檔前設 large-v3-turbo 就當作已切換。未來可在臨時 PowerShell 環境直接啟動 launcher，測完還原，不修改預設。**本輪沒有執行。**
- 本機套件的 alias 已列 `large-v3-turbo → mobiuslabsgmbh/faster-whisper-large-v3-turbo`。使用者 Hugging Face 快取有 snapshot `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`，model.bin 為 **1,617,884,929 bytes（約 1.51 GiB）**，config、tokenizer、vocabulary、preprocessor 檔均存在。只有檔案存在與大小核對，未載入、未驗證模型完整性或 CUDA 相容。
- 服務使用的 `download_root` 是專案 `.models/windows`，這裡目前只有 small，與上面的使用者快取不同。未來測試應將臨時 `MOSA_ASR_MODEL` 指向既有 snapshot 的**完整路徑**，並設 `HF_HUB_OFFLINE=1`；已讀原始碼確認本機目錄會直接使用。不能假設僅設 alias 就會重用另一個 cache。沒有複製模型、沒有下載。
- 翻譯模型：目前磁碟上的 README、START_WINDOWS.bat、models.py fallback、launch.py fallback 都是 **qwen2.5:7b**，未見差異。A/B/C 保存的 `health.models.translation` 亦皆為 qwen2.5:7b（ASR small、CUDA）。這是**既有快照**，不是當下服務 health；目前 runtime 未驗證，為遵守遊戲期間限制沒有連線或啟動服務。本輪未修改這些檔案。

## 重現方式與檔案

以下皆為離線命令；本輪實際透過臨時低優先權 runner 執行這些 entry points：

```powershell
.venv-win/Scripts/python.exe -X utf8 tests/test_unit_normalization.py
.venv-win/Scripts/python.exe -X utf8 tests/test_offline_diagnostics.py
.venv-win/Scripts/python.exe -X utf8 tests/test_fleurs_eval.py
$ref="quality/eval/baseline-20261024-active-20dBFS/fleurs-en-zh-20min-seed2026-active-20dBFS.reference.json"
$runs=@("quality/endpoint-ab-20261107-210028/A-default.json","quality/endpoint-ab-20261107-212610/B-breath.json","quality/endpoint-ab-20261107-212610/C-soft3500.json")
.venv-win/Scripts/python.exe -X utf8 windows/score_eval.py @runs --reference $ref --save quality/另取新檔名-comparison.json
.venv-win/Scripts/python.exe -X utf8 windows/diagnose_errors.py @runs --reference $ref --save quality/另取新檔名-diagnostics.json
```

本輪新檔在 `quality/offline-diagnostics-20261107/`：`comparison-2026-11-07.1.json`、`diagnostics.json`（初版分析）、`diagnostics-final.json`（最終工具輸出）、`audit-details.json`（舊版對齊與純 Agreement 重演）。全部留在本機、不提交；原 A/B/C、reference 和舊比較檔未覆寫。

## 本機提交

- `d754845`：單位別名正規化、版本號與回歸測試。
- 04d9388：正式診斷工具與 10 項測試。
- 本報告與低 chrF 樣本另成一個文件 commit；未推送。
