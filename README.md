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

## 📱 手機遙控設定（給客戶）

用**手機**操作裝在電腦上的 FBPoster Pro。手機與電腦透過 **Tailscale** 私有網路直連，**不經雲端**、免額外費用、安全。

### 你需要
- 一台裝了 FBPoster Pro 並**保持開機**的 Windows 電腦
- 你的手機
- 免費 [Tailscale](https://tailscale.com/) 帳號

### 步驟
1. **電腦**裝 Tailscale（https://tailscale.com/download ）並登入。
2. **手機**裝 Tailscale App，用**同一帳號**登入。
3. 電腦上打開 FBPoster Pro → 左側 **📱 手機遙控** → **啟用遠端**（需先完成授權）→ 依提示**重啟一次** App。
4. 回「手機遙控」頁會出現 **QR Code**，用手機掃描 → 開啟手機版網頁 → 瀏覽器選單「**加入主畫面**」即像 App。

### 常見問題
- **連不上**：確認手機/電腦的 Tailscale 都「已連線」、且電腦 App 開著。
- **看不到 QR**：電腦還沒裝/登入 Tailscale，回步驟 1。
- **換手機/防外流**：「手機遙控」頁點 **重新產生 Token**，舊手機立即失效。
- **電腦關機就連不到**：對，引擎在電腦跑，電腦要開著。

### 安全
- 走你自己的 Tailscale 私有網路，外人連不到。
- QR 內含存取密鑰（Token），**勿外流/截圖給他人**；可隨時重產失效。
- Facebook 看到的仍是你電腦的家用 IP（風險最低）。

---

## 分支
- `feat/fb-graphql-delete-engine`：FB 刪文/permalink 改走內部 GraphQL（取代脆弱 DOM）。
- `feat/mobile-remote-b`：手機遙控（Tailscale-based）後端 token 閘 + 前端 PWA/遠端面板/本地 QR。

詳見各 `.spec/*.md`。
