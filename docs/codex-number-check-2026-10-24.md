# 數字檢查修正驗收報告（2026-10-24）

## 範圍與結論

本輪驗證本機 `41462ea`（`fix(quality): stop false number mismatches that trigger needless repair passes`），不改模型、提示詞、VAD、斷句、佇列或預設設定。只重播既有正規化素材，並以評分器 2026-10-24.3 對本輪與先前基準重新評分。

**結論：** 對同一份 21 分鐘素材，服務端的 `reviewed` 和 `quality_repair_attempted` 都由 33 降至 4，`number_mismatch` 由 31 降至 2。ASR WER 與 scorer 的譯文數字遺失數持平；chrF 有小幅波動，且延遲單次對照不能歸因於此修正。人工檢視兩個剩餘服務端標記：一個是時間格式誤報，另一個是需要處理的 ASR／譯文數字不一致。

## 驗證環境與前置核對

- `HEAD`：`41462ea`；目標 commit 存在，改動包含 `windows/quality_checks.py`、`windows/score_eval.py` 與數字測試。
- ASR：`small`；翻譯：`qwen2.5:7b`；裝置：CUDA。
- endpoint：`conservative`。`MOSA_EVAL_ASR=stream-en`。
- 本輪與舊基準 tuning 一致：推測定稿開啟、preview 2000 ms、max segment 6016 ms、pause 896 ms、breath cut 關閉、soft cut 0 ms、soft pause 192 ms。
- 前置健康檢查：`ready=true`、`restart_required=false`、ASR 已載入、翻譯可用，計數歸零。
- 重要版本註記：舊結果 health 的 runtime `code_revision` 是 `3a4adba241e5e6c3`，本輪是 `412a6b3a0dece5b0`；Git `HEAD` 仍是 `41462ea`。工作目錄原先已有使用者未提交修改，其中 `windows/models.py` 將預設 NMT 改為 Gemma，但當前實際載入及舊基準均為 `qwen2.5:7b`，所以有效模型設定一致。未修改或提交這些既有差異。
- 原先暫停的第一次重播在約 9 分鐘處中止，未產生結果檔，不納入本報告。其後完整重啟服務，從頭重跑。

### 自動測試

| 指令 | 結果 |
|---|---:|
| `.venv-win\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` | 58 通過 |
| `.venv-win\Scripts\python.exe -m unittest discover -s windows -p "test_*.py"` | 32 通過 |
| `npm test` | 64 通過 |

## 重播與資料完整性

素材與參考均沿用 `quality/eval/baseline-20261024-active-20dBFS/` 中的 FLEURS 正規化組。舊、新結果使用同一個 reference：`fleurs-en-zh-20min-seed2026-active-20dBFS.reference.json`。重播指令：

```powershell
$env:MOSA_EVAL_ASR='stream-en'
$env:MOSA_EVAL_OUTPUT='level-normalized-41462ea.json'
node windows\evaluate_live.mjs quality\eval\baseline-20261024-active-20dBFS\fleurs-en-zh-20min-seed2026-active-20dBFS.manifest.json
```

| 檢查 | 本輪結果 |
|---|---:|
| 收到音訊 | 1,289,473 ms（約 21 分 29 秒） |
| final 數／唯一 seq | 217／217 |
| 掉音／重播音訊 | 0／0 ms |
| reconnect／播放重設／overflow | 0／0／0 |
| 服務 errors／canceled batches | 0／0 |
| 參考句覆蓋／邊界／漏句 | 126／0／0 |

## 新舊結果對照

兩份結果皆重新以 `windows/score_eval.py`（2026-10-24.3）評分；百分位採 nearest-rank。舊結果的品質旗標和數字錯誤計數也以新 scorer 重算。

| 指標 | 舊：`level-normalized-20261024.json` | 新：`level-normalized-41462ea.json` |
|---|---:|---:|
| Final 數 | 217 | 217 |
| Final `reviewed=true` | 33 | 4 |
| Final `quality_repair_attempted=true` | 33 | 4 |
| Final `number_mismatch` 旗標 | 31 | 2 |
| ASR WER（原始） | 16.31% | 16.31% |
| ASR WER（數字正規化） | 16.24% | 16.24% |
| 翻譯 chrF（文件級） | 30.15 | 29.89 |
| Scorer 翻譯數字遺失句 | 6 | 6 |
| 參考句覆蓋／邊界／漏句 | 126／0／0 | 126／0／0 |
| `nmt_ms` p50／p95 | 515／1,469 ms | 687／1,265 ms |
| `capture_to_caption_ms` p50／p95 | 6,757.7／7,974.2 ms | 7,058.2／8,442.4 ms |
| `after_speech_ms` p50／p95 | 1,254.4／2,275.9 ms | 1,473.8／2,874.0 ms |

延遲是各一次執行的觀察值；執行時段、模型狀態與 GPU 負載都可能造成波動，不能據此判定修正讓延遲變慢。舊、新皆有 217 個 final、0 掉音及 0 重連，故 scorer 的句數與 WER 可直接對照。chrF 差 0.26 分，沒有標準答案人工語意評分，不能據此宣稱翻譯品質退步。

## 剩餘服務端 `number_mismatch` 逐句人工核對

| Final／參考句 | ASR 原文與譯文 | 判定 |
|---|---|---|
| Final 50／FLEURS 句 27 | 原文：`and JackR Boothang leave between 6.30 and 7.30.`；譯文：`JACKR Boothang在下午6點30分到7點30分之間離開。` 參考句同樣是 06:30 至 07:30。 | **誤報。** 兩個時刻都保留，差異是英文以小數點寫時間、中文以「點／分」表達。數字守門仍把兩種表記視為不一致，這是本輪剩下的 false positive。 |
| Final 89／FLEURS 句 47 | 原文：`half inches was roll up for storage.`；譯文：`捲起儲存時，其長度為29又3/4英寸。` 同一句前一個 final 譯為 `29又3/4英寸乘以24英寸`。參考尺寸為 29¾ × 24½ 英寸。 | **是真實待修問題，不是單純誤報。** 這一段 ASR 沒辨出尺寸；合看相鄰字幕，第一段把 24½ 縮成 24，後一段又重複 29¾。此旗標正確要求人工檢查，但問題同時涉及跨段上下文與 ASR 漏字。 |

## Scorer 的 6 個譯文數字遺失句

下列 scorer 指標檢查的是「辨識字幕是否覆蓋標準原文數值」，與服務端 `number_mismatch`（辨識文字對該 final 譯文）不是同一個計數；兩個數字不能互換。逐句核對後，六句都值得人工修正或複核：

| FLEURS 句／ID | 標準答案中的數字 | 本輪觀察 | 判讀 |
|---|---|---|---|
| 4／1735 | two generations | ASR／譯文未覆蓋該數字與對應子句 | 漏辨識，需修正 |
| 6／1883 | 2017、March | ASR 在 `tr-` 處中斷，譯文未包含 2017 年 3 月通車資訊 | 漏辨識，需修正 |
| 21／1835 | magnitude 6.5 | ASR 漏掉數值子句，譯文亦無 6.5 | 漏辨識，需修正 |
| 30／1811 | 802.11n、2.4 GHz | ASR 僅保留後段 `5.0 G-HC frequencies`，譯文也缺前兩個數值 | 漏辨識，需修正 |
| 39／1718 | 100 years | ASR／譯文在 `Some tax agents` 後截斷，缺 100 年 | 句尾漏辨識，需修正 |
| 47／1682 | 29¾ × 24½ inches | 合併相關字幕後出現 29¾ × 24，另一段再重複 29¾；24½ 的 ½ 遺失 | 真實數值錯誤；需修正並複核分段 |

## 結果檔與限制

- 新即時重播：`quality/level-normalized-41462ea.json`。
- scorer 2026-10-24.3 對照：`quality/level-normalized-41462ea-report.json`。
- 本報告只提交報告 Markdown；兩份 JSON 僅留在本機，不加入 commit。
- 數字旗標數及修譯數下降符合修正目的；WER 和 scorer 數字遺失數沒有改善，代表這項修正是減少誤報與不必要修譯，不是提升 ASR 數字召回。
- 整段評測只跑一次；延遲與 chrF 的小幅差異都可能來自執行變異。沒有額外語意標註者，因此未將 chrF 當成翻譯準確率。