# Prompt、播放器重設與翻譯介面更新

日期：2026-09-11

## 實作範圍

- `windows/quality_checks.py`：新增 `sanitize_prompt(candidate_prompt: str, recent_transcripts: list[str]) -> str` 與 `has_repeating_ngrams(text: str) -> bool`。使用標準函式庫 SequenceMatcher，比對前 10 筆以內的歷史；相似度 > 0.85、重複循環、純符號或音樂套話不加入動態歷史。每筆最多 300 字。高信心的真實道別仍顯示，只有低信心／較高無語音機率時才抑制這類輸出。
- `windows/models.py`：每個 session 使用 deque(maxlen=10)，只加入通過 ASR 品質與文字過濾的定稿；翻譯前文仍維持最多 2 筆。20 秒語音間隔與 session 重設清理歷史。ASR initial_prompt 保持只有 asr_glossary.json 靜態詞彙，condition_on_previous_text=False；沒有重新引入生成歷史。正常前文引用不與自身比對，定稿候選只與先前已收錄定稿比較。
- `extension/playback.js`：emptied、stalled、seeking、pause、來源變更、播放器替換與 adstart/adend 觸發重設；廣告 DOM 標記轉換提供輔助偵測。500ms 內合併事件，短 waiting 維持原策略。廣告事件與 DOM 標記不是瀏覽器標準，也無法保證偵測所有 Twitch 廣告。
- `extension/live-client.js`、`web/live-client.js`：沿用 restart() 的 generation++、取消請求與 X-Mosa-Supersedes；重設立即送零音訊 flush 包，無須等播放器恢復。舊回呼不再通過 current()。後端沿用既有 session 取消流程，不新增 HTTP 路由或 NDJSON 格式。
- `extension/worklet.js`、`web/worklet.js`：抽出 resetAudioState()；清理採樣相位、累積和、數量與待送音訊後才回覆 resetDone。flush 仍表示送出尾段；reset 才是丟棄尾段，兩者不可混用。

## 翻譯介面

`TranslationEngine.tokens(self, text, context, terms, draft=None)` 回傳非同步 token iterator。`OllamaTranslator` 委派原有 HTTP 串流邏輯；呼叫端持有既有 nmt_gate 與每 session 的 translation_lock，鎖排程不變。

`MOSA_NMT_ENGINE=ollama` 為預設。`MOSA_NMT_ENGINE=ctranslate2` 選到預留骨架，在載入模型前明確拒絕啟動；尚缺模型、tokenizer、語言標記及推論 adapter，並非可用的 NMT。未新增 pip 依賴或下載模型。

## 開源查核

參考入口：

- https://github.com/ufal/whisper_streaming/blob/main/whisper_online.py
- https://github.com/collabora/WhisperLive
- https://github.com/antor44/Audio-Transcription
- https://github.com/cyberofficial/Synthalingua
- https://github.com/TheDeathDragon/LiveTranslate

Whisper Streaming 提供 local agreement 與緩衝裁切的參考；LiveTranslate 公開說明以 LLM API 做翻譯，不能據此稱其已有 NLLB/Opus-MT 介面。本次是依本專案協議自行實作，未複製第三方程式碼，也未確認所有提案中的具體機制都存在於上述專案。0.85 為本次指定策略，非上游效能保證。

## 驗證與限制

本次執行結果：Node 全套 54/54；pipeline.test.mjs 單獨 3/3（包含雙端檔案一致性）；tests/ Python 新增 8/8；windows/ Python 既有 31/31；git diff --check 通過。pipeline 的 3 項已包含於 Node 全套，勿重複加總。

新增 Python 測試放在 tests/test_prompt_guard.py 與 tests/test_translation_engine.py；前端新增／擴充 tests/live-client.test.mjs、tests/playback.test.mjs、tests/worklet.test.mjs。涵蓋正常前文、跨輪重複、日韓文字、音樂套話、信心判定、上限、翻譯引擎委派、保留介面報錯、後端 reset、舊回呼與重採樣殘值。

執行方式：

```powershell
node --test tests/*.test.mjs
node --test tests/pipeline.test.mjs
.\.venv-gpu-test\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
.\.venv-gpu-test\Scripts\python.exe -m unittest discover -s windows -p 'test_*.py'
```

單元／協議測試使用替身，不代表已完成新版本 Twitch 長播、真模型準確率或顯存測試。CTranslate2 骨架不提供效能收益。生效需重啟後端、重新載入 Chrome 擴充套件及影片分頁，再由使用者點選翻譯此分頁。
