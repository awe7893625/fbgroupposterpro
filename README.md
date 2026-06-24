# FBGroupPosterPro

桌面工具：用瀏覽器自動化把貼文發到多個 Facebook 社團，含 AI 文案/改圖、排程、到期自動下架。
後端 Python(aiohttp) + Selenium/undetected-chromedriver；前端 Next.js（靜態匯出，由後端 serve）；
桌面殼 PyQt 系統匣 app，本地 `127.0.0.1:3080`。

## 建置（Windows）
```powershell
# 需 Python 3.11+ / Node 18+ / Inno Setup（ISCC.exe）
powershell -ExecutionPolicy Bypass -File build\build_win.ps1 -InnoSetup C:\InnoSetup6\ISCC.exe
# 產物：dist\FBGroupPosterPro\（免安裝）+ dist\FBGroupPosterPro-Setup-1.0.0.exe（安裝包）
```
- `build\build_win.spec` 用 `collect_submodules('backend')` 強制打包整個 backend（含延遲導入的模組）。
- 安裝精靈為英文（Inno 不附非官方繁中語言檔）；App UI 為中文。

## 客戶下載 / 使用
1. 安裝 `FBGroupPosterPro-Setup-1.0.0.exe`（或解壓 portable 版跑 `FBGroupPosterPro.exe`）。
2. 啟用授權（trial / 付費 key）。
3. 綁自己的 Facebook（開瀏覽器登入自己帳號，自行通過驗證）。
4. 加社團 → AI 文案+改圖 → 發文 → 到期自動下架。

---

## 📱 手機遙控（給客戶，零設定）

用**手機**操作裝在電腦上的 FBPoster Pro。**客戶完全不用設定網路**——電腦上的 App 會自動「對外撥號」連到中繼伺服器（`relay.konggoo.uk`），手機掃 QR 即可連上。免裝 Tailscale、免設定防火牆。

### 你需要
- 一台裝了 FBPoster Pro 並**保持開機**的 Windows 電腦（能上網即可）
- 你的手機

### 步驟（30 秒）
1. 電腦打開 FBPoster Pro → 左側 **📱 手機遙控** → **啟用遠端**（需先完成授權）。
2. 出現 **QR Code + 配對碼**。
3. 手機相機掃 QR → 開啟手機版網頁 → 瀏覽器選單「**加入主畫面**」即像一個 App。

完成！手機就能遙控電腦發文了。

### 常見問題
- **連不上**：確認電腦能上網、且 FBPoster Pro 開著；面板顯示「正在連線到中繼伺服器」表示還在連。
- **換手機 / 怕外流**：「手機遙控」頁點 **重新產生 Token**，舊 QR 立即失效。
- **電腦關機就連不到**：對，引擎在電腦跑，電腦要開著。

### 安全 / 架構
- 資料路徑：手機 → `relay.konggoo.uk`（只負責轉送）→ 你的電腦。中繼**不解密、不留存**你的內容。
- 每個 `/api` 請求都需要**存取金鑰（Token）**端到端驗證；光知道配對碼無法控制你的電腦。
- QR 內含 Token，**勿外流/截圖給他人**；可隨時重產失效。
- 中繼伺服器（relay server / Cloudflare Tunnel）部署見 `relay/relay_server.py`；launchd 服務 `ai.fbgp.relay` + `ai.fbgp.relay-tunnel`。

---

## 分支
- `feat/fb-graphql-delete-engine`：FB 刪文/permalink 改走內部 GraphQL（取代脆弱 DOM）。
- `feat/mobile-remote-b`：手機遙控（Tailscale-based）後端 token 閘 + 前端 PWA/遠端面板/本地 QR。

詳見各 `.spec/*.md`。
