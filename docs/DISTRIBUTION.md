# 取得與發布方式

查核日期：2026-09-10。

目前採公司私人 GitHub 儲存庫提供原始碼，Chrome 以「載入未封裝項目」安裝。這適合內部原型試用，使用者仍須安裝並啟動本機推論服務。

正式商店路徑：註冊並設定開發者帳號，準備擴充套件 ZIP，上傳開發者控制台，填寫商店資訊、隱私、發布對象與測試說明，再提交審查。上架擴充套件不會自動安裝 Python、Ollama 或模型，因此本機服務的安装體驗必須另行處理。來源：[Chrome 官方發布流程](https://developer.chrome.com/docs/webstore/publish)。

目前由使用者點擊擴充套件啟動分頁擷取，符合 tabCapture 需要使用者觸發的使用方式；它擷取的是分頁媒體串流，不提供同頁播放器隔離承諾。來源：[Chrome tabCapture API](https://developer.chrome.com/docs/extensions/reference/api/tabCapture)。

提交商店前的專案工作：補齊圖示、商店截圖、實際資料流說明、本機服務安裝說明與可重現測試步驟；完成跨網站驗證；確認中斷收音和錯誤狀態對使用者足夠清楚。此文件是發布準備方案，本次沒有提交商店審查。
