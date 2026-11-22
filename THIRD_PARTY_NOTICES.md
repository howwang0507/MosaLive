# 開源元件與參考來源

本次直接重用已發行的推論元件與模型，沒有將第三方專案冒充為原創。

* faster-whisper 1.2.1（MIT）：https://github.com/SYSTRAN/faster-whisper
  原有辨識引擎，並重用套件附帶的 Silero v6 ONNX 工作階段。
* Silero VAD（MIT）：https://github.com/snakers4/silero-vad
  新流程持續保存每個收音工作階段的神經網路狀態，以人聲機率決定斷句。
* sherpa-onnx 1.13.7（Apache-2.0）：https://github.com/k2-fsa/sherpa-onnx
  直接使用 SpeakerEmbeddingExtractor CPU API；使用方式參考官方
  python-api-examples/speaker-identification.py，沒有複製該示範檔。
* WeSpeaker（Apache-2.0 程式庫）：https://github.com/wenet-e2e/wespeaker
  模型由 sherpa-onnx 官方 speaker-recongition-models release 提供。
  檔名 wespeaker_en_voxceleb_resnet34.onnx；SHA256：
  5ef208a9da1453335308a6b6f4e6dfbd7e183a38b604de0a57664f45d257fe94。
  模型上游來源與資料說明以該 release 及 WeSpeaker 模型文件為準。
* WhisperStreaming（MIT）：https://github.com/ufal/whisper_streaming
  參考兩次假設共同前綴（LocalAgreement）的公開方法；本次為配合
  現有 Chrome 與 faster-whisper 流程自行實作，未複製上游程式碼。

套件發行物內保留原有授權。licenses/ 另存主要依賴上游授權原文，
不得移除其版權與授權聲明。此清單不代表本專案與任何上游有官方合作。

## 0.3.0 新增來源

* sherpa-onnx 的 OnlineRecognizer / OnlineStream：直接使用已安裝套件的
  串流 Transducer API，依套件 Apache-2.0 授權保留聲明。
* 英文／日文模型：PengChengStarling 八語 Zipformer，2025-02-10 ONNX 轉換。
  [上游專案](https://github.com/PCL-Voice/PengChengStarling)、
  [官方轉換模型卡](https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-ar_en_id_ja_ru_th_vi_zh-2025-02-10)。
* 韓文模型：sherpa-onnx-streaming-zipformer-korean-2024-06-16。
  兩組模型均由 [sherpa-onnx 官方 asr-models release](https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models)
  下載；實際 URL 與 SHA256 記錄於 `.models/streaming/sources.json`。
  下載包未提供可據以確認的獨立權重授權聲明，不能將推論程式的 Apache-2.0
  直接套用到模型權重。本次在本機評估，程式內提供下載器，不重新打包散布權重。
* 真人評估語料：Google FLEURS，CC-BY-4.0，
  [資料集與引用資訊](https://huggingface.co/datasets/google/fleurs)。
  使用英文、日文、韓文 test split 各前 4 筆；音訊轉成單聲道 16kHz PCM16，
  原始逐字稿保留。這是朗讀語音，不是 Twitch 直播資料，也沒有人工中文譯文。
  所有 row ID、下載 URL、轉檔說明與來源 SHA256 見 `quality/real-manifest.json`。
* pyarrow 21.0.0（Apache-2.0）：只用於讀取評估語料 Parquet，
  不屬於直播執行依賴。[Apache Arrow](https://arrow.apache.org/)。
