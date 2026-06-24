# Spec: 手機遙控桌面引擎（方案 B — Tailscale-based）

> spec_id: spec-mobile-remote-control-b
> created: 2026-06-24
> status: draft → 實作中
> machine: M4（開發/repo）→ Beaver（打包驗證）
> 決策授權：Rain 選了 B 並授權我判斷

## 1. 目標
客戶手機能遙控自家 PC 上跑的 FBGroupPosterPro 引擎（看狀態、發文、排程、自動下架）。手機**不跑**任何自動化（Selenium/Chrome 在 PC）。

## 2. 架構決策（我的判斷，Rain 授權）
- **走 Tailscale，不自建雲端 relay。** 客戶 PC 與手機都加入客戶自己的 tailnet；手機 PWA 直連 PC 的 tailnet IP。
  - 理由：複用 Rain 已驗證的「客戶裝 Tailscale + 填機器資料就能用」可賣模型（見 memory nexpilot-native-is-sellable）；**零雲端成本**、**客戶住宅 IP（FB 風險最低）**、私有網路安全。
  - 雲端 relay（NexDesk 式 device 外撥 hub）列為 **Phase 2**，給「不裝 Tailscale / 零設定」的更高收費 tier。
- **手機端 = 既有 Next.js 前端做成 RWD + PWA**（可加到主畫面像 App），API base 指向 PC tailnet IP。不另做原生 App（先 PWA，足夠賣）。

## 3. 需求（FR）
| ID | 優先 | 需求 | 驗收 |
|----|------|------|------|
| FR-1 | MUST | 後端可綁 0.0.0.0/tailnet（非只 127.0.0.1），由設定/env 控制，預設仍只 localhost（安全預設） | 開啟遠端後手機同網段可連 |
| FR-2 | MUST | **存取權杖 (access token) 閘**：遠端請求須帶 token 才放行；localhost 請求豁免（桌面 UI 免 token） | 無 token 的遠端請求 401；有 token 200 |
| FR-3 | MUST | CORS 放寬到可接受跨來源（因 token 才是真 auth），不再寫死 localhost | 手機 PWA 跨來源呼叫不被擋 |
| FR-4 | MUST | 「遠端存取」設定面板：一鍵開啟遠端、顯示 PC tailnet URL + token + **QR code**（手機掃 → 開 PWA 預填 URL+token） | 掃 QR 後手機直接進已連線的 UI |
| FR-5 | MUST | 前端 PWA：manifest + service worker + icons，可「加到主畫面」；API base 可設定（存 localStorage，來自 QR/手動） | 手機可安裝、離線殼可開、連對後端 |
| FR-6 | SHOULD | 前端 RWD：8 頁在手機窄螢幕可用（導航、表單、終端串流） | iPhone 寬度逐頁不破版 |
| FR-7 | MUST | token 與 license 綁定：未啟用授權不可開遠端 | 試用/付費才可遠端 |

## 4. 安全要點（不可妥協）
- token 高熵（secrets.token_urlsafe），存本機加密設定；可重置（撤銷舊手機）。
- 遠端模式預設**關**；開啟要明示。綁 0.0.0.0 一定同時啟 token 閘。
- token 比對用常數時間比較；失敗有節流/紀錄。
- QR 只在本機 UI 顯示（不外傳）。

## 5. 分階段
- **Phase 1（本批）**：FR-1/2/3/5/7 後端基礎 + PWA 基礎 + API base 設定 + 遠端面板與 QR。
- **Phase 2**：FR-6 全頁 RWD 打磨（含 xterm 終端手機化）+ 雲端 relay tier。

## 6. 風險 / 已知限制
- 客戶要會裝 Tailscale（給圖文教學/精靈）；不裝就只能等 Phase 2 relay。
- PC 要開著引擎才連得到（B 的本質）。
- FB 風險不變（同桌面版）。
- 終端即時串流(SSE/WS)在手機 PWA 跨 tailnet 的穩定性需實測（沿用桌面既有串流）。

## 7. 交付前驗收閘（待實作後逐項補 ✅/⚠️/❌）
（實作完成後回填）
