# 正控制錄音：確認 echo guard 不會吃掉真的「chat」

Echo guard（`MOSA_ASR_ECHO_RETRY`）在硬切後的辨識結果幾乎只剩詞表詞（Twitch、chat）時，會拿掉提示詞重辨一次。FLEURS 素材沒有人真的說「chat」，所以要用你自己的錄音，確認講者真的說「chat」時它不會被弄丟。

## 1. 錄音（約 10 分鐘）

在專案資料夾建立 `recordings\`（已加入 `.gitignore`，不會被提交）。任何錄音軟體都可以，wav、m4a、mp3 都行；音量正常、環境安靜即可。

**長段落：檔名 `long-1.wav`～`long-5.wav`**，每段用平常語速**一口氣念完、中間不要停頓**，至少 8 秒。不要念到 chat 這個字。

1. Okay so the plan for today is to finish the second level, collect every hidden key we can find, and then try the boss fight again before we stop for dinner tonight.
2. I picked up this keyboard last week and honestly the switches feel a lot smoother than my old one, although the software still crashes whenever I try to change the lighting.
3. If we go left at the bridge we should reach the camp before the storm starts, but if we wait any longer the whole valley floods and we lose all the supplies we carried.
4. The update added three new maps, a ranked mode with seasonal rewards, and a replay system that finally lets you watch your own matches from any angle you want.
5. Remember to drink some water and stretch your shoulders every hour, because sitting in the same position for that long is really not great for your back or your wrists.

**短句：每個檔案只說一個短句**，前後各留一點安靜。檔名就是句子內容，數字只是編號：

| 檔名 | 要說的話 |
|---|---|
| `chat-chat-1.wav`、`chat-chat-2.wav`、`chat-chat-3.wav` | chat |
| `chat-thanks-chat-1.wav`、`chat-thanks-chat-2.wav` | thanks chat |
| `chat-okay-chat-1.wav`、`chat-okay-chat-2.wav` | okay chat |
| `chat-and-chat-1.wav` | and chat |
| `chat-hi-chat-1.wav` | hi chat |
| `chat-what-do-you-think-chat-1.wav` | what do you think chat |

最後一句故意包含詞表以外的字，guard 不應觸發，用來對照。

## 2. 組合測試素材（不用 GPU）

```powershell
.venv-win\Scripts\python.exe windows\build_chat_controls.py recordings --out quality/eval/chat-controls
```

由於很難剛好在 6 秒硬切時說出 chat，工具會**拼接**：把長段落在 5.7／5.9／6.1／6.3 秒附近最安靜的位置剪斷，接 0.15 秒間隔與短句，讓硬切落在短句附近。另外每個短句再產生「停頓 1.5 秒後說」（不會硬切，guard 不應觸發）與「單獨說」兩種對照。10 個短句會產生 60 個樣本。這是拼接音訊，不是自然直播。

## 3. 重播 guard 關閉、開啟各一次（會用 GPU，約 10–15 分鐘）

每次換設定都要完整重啟服務，確認 health ready、`restart_required=false`、`tuning.asr_echo_retry` 符合該輪。

```powershell
# 關閉：重啟服務前設定 MOSA_ASR_ECHO_RETRY=0
$env:MOSA_EVAL_ASR="stream-en"; $env:MOSA_EVAL_OUTPUT="chat-controls-off.json"
node windows/evaluate_live.mjs quality/eval/chat-controls/chat-controls.manifest.json
# 開啟：重啟服務（不設定，預設開啟）
$env:MOSA_EVAL_OUTPUT="chat-controls-on.json"
node windows/evaluate_live.mjs quality/eval/chat-controls/chat-controls.manifest.json
```

## 4. 比對

```powershell
.venv-win\Scripts\python.exe windows\check_chat_controls.py quality\chat-controls-off.json quality\chat-controls-on.json --save quality\chat-controls-check.json
```

每個樣本檢查定稿裡「chat」出現次數是否達到該句應有的次數，以及 guard 是否重試。重點看 **lost after retry**：重試後 chat 不見的樣本數，也就是 guard 誤傷。關閉與開啟都弄丟的是辨識本身的問題，不算 guard 造成。`after_pause`、`alone` 兩類不應出現重試。

**判斷：** 開啟組 lost after retry 為 0，且 chat 保留數不低於關閉組，才支持 guard 維持預設開啟。只錄一個人的聲音、樣本數少，結論只限於這組錄音。
