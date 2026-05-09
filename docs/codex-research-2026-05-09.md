# FBGroupPosterPro SaaS 化技術研究報告

**日期：** 2026-05-09  
**研究工具：** Codex CLI (gpt-5.4, xhigh reasoning) × 4 並行  
**背景：** Python aiohttp + Selenium (undetected-chromedriver) + Next.js 桌面 app，目標 SaaS 化，服務台灣房仲/電商/小編

---

## Q1 — 2026 年 FB Selenium 反偵測最佳實務

### 背景

現況用 undetected-chromedriver 3.5.5，需要評估是否還適合做為 SaaS 的主力反偵測工具，並找出更佳的替代方案組合。

### 比較表

| 工具 | Meta 偵測/封鎖風險 | 內建真實鼠標+打字節奏 | GitHub 維護狀態 | 從 UC 遷移成本 |
|---|---|---|---|---|
| undetected-chromedriver 3.5.5 | **高** | 無 | 套件 3.5.5 發布 2024-02-17；repo 有 commit 到 2025-07-05，但節奏慢 | 最低（現用） |
| Playwright + playwright-stealth | 偏高 | 無（需手動 delay） | Playwright 本體活躍；stealth fork 到 2026-04-04，維護者自稱只適合「最簡單」偵測 | 中高（Selenium API 重寫） |
| **Patchright** | **中** | 無 | Python repo 2026-02-19；PyPI 2026-03-07；driver release 2026-04-12，屬活躍 | 中高（Playwright 風格重寫） |
| **Camoufox（Firefox-based）** | 中，但波動大 | **部分**（humanized mouse 有；打字節奏無明確保證） | 2026-04-10 仍有 commit，但官方文件警告 2026 版 experimental | 高（API 與瀏覽器行為差異） |
| NoDriver | 中偏高 | 無 | UC 作者的 successor；repo 2025-11-09；2026 仍有 issue activity | 中（同作者，async，比 Playwright 類順） |
| botasaurus | 中偏高 / 證據不足 | 部分（humancursor） | repo 2026-03-18，活躍 | 很高（framework 級切換） |

### 關鍵洞察

Meta 的封鎖不只看 `navigator.webdriver`，2025-2026 年更常見的是 **IP/ASN、帳號年齡、cookie 歷史、時區/語系一致性、互動節奏、重複行為圖譜** 綜合判斷。**從桌面 app 變成 SaaS，風險上升往往比「換哪個 stealth 套件」還大。**

### 推薦方案

**A 主用：Patchright**
- 2025-2026 維護最穩定、更新最積極
- 技術路線比 playwright-stealth 更深，直接處理 `Runtime.enable`、`Console.enable`、預設 command flags 等核心洩漏面
- 官方明確最佳實務：用真實 Chrome、persistent context、`headless=False`、不要亂加自訂 UA/header
- 與 aiohttp async 架構方向一致

**B 備援：Camoufox**
- 提供 Firefox 指紋第二條路，對某些 Chromium 系封鎖有分流價值
- 有內建 humanized mouse
- 因 2026 版仍 experimental 且有 Facebook-specific detect issue，適合備援而非主線

**過渡策略（最低風險）：** UC 3.5.5 → NoDriver → Patchright + Camoufox

### 實作要點

1. 用 persistent profile，不要每次 fresh profile
2. 一個帳號固定綁一條 proxy、一個 profile、一組 timezone/locale
3. 盡量用 residential/mobile proxy，避免 datacenter ASN
4. 優先 headed 模式，不要預設 headless
5. 登入/2FA 與日常操作分 lane，長期重用 session
6. 加外部 humanization 層（多數工具無完整內建）
7. SaaS 架構避免共用雲端瀏覽器池，多租戶共用 IP/ASN 會打掉 stealth 優勢

---

## Q2 — 桌面 SaaS License Server 架構

### 背景

現有 Vercel proxy 已收 `licenseKey + deviceId`，但缺少啟用、心跳、撤銷邏輯。目標客戶是台灣房仲/電商/小編。

### 付款方案比較

| 方案 | 台灣公司可直接用 | 台灣客戶支付覆蓋 | 訂閱/定期扣款 | 開發速度 | 費率重點 | 結論 |
|---|---|---|---|---|---|---|
| Stripe | **不適合主方案** | 低到中 | 最強，內建 Billing | 最快 | 2.9%+30¢，國際卡+1.5% | 截至 2026-05-09 官方 global 沒有 Taiwan，台灣主體不建議 |
| **TapPay** | 可以 | 中到高 | 可以（card_key/token 做 recurring） | 中快 | 開辦 NT$5,000、年費 NT$11,000、國內卡 2.75%、國外卡 3.5% | **主方案首選** |
| 綠界 ECPay | 可以 | **高** | 可以（偏固定制） | 簡單導轉快 | 國內卡 2.75%、ATM 1%、超商 NT$30+5% 營業稅 | 年繳/ATM/超商備援最佳 |

**結論：台灣主體 + 台灣客戶 + 桌面 SaaS = TapPay 主、ECPay 輔。**

### device_id 設計方案

不要用 MAC address。正確做法：

```text
install_uuid = UUIDv4()  # 首次安裝產生，存 Keychain/Credential Manager

fp_components = {
  platform_uuid,       # 權重 40
  board_uuid,          # 權重 30
  system_disk_uuid,    # 權重 20
  cpu_model_cores      # 權重 10
}

component_hashes = SHA256(normalize(value))
device_claim = SHA256(install_uuid + canonical_json(component_hashes))
device_id = base64url(HMAC(server_secret, device_claim))
```

- **分數 >= 60 視為同裝置**（換 WiFi 不踢人，整台複製到別台通常失敗）
- 不要納入：MAC address、IP、hostname、WiFi SSID

### 試用期防破解

- 試用期一定以**伺服器 UTC 時間**為準，本地時鐘只顯示 UI
- 第一次啟動必須聯網，伺服器記錄 `trial_started_at`、`trial_expires_at`
- 回傳簽名 trial token（含 `expires_at`、`grace_until`、`revoke_version`）
- 試用期離線寬限只給 **24 小時**（trial 最易被 freeze-clock 破解）

### 心跳設計

| 機制 | 頻率 | 用途 |
|---|---|---|
| `light revoke check` | 每 2 分鐘（app 活躍時） | 幾分鐘內撤銷生效 |
| `full heartbeat` | 啟動/喚醒/重連/每 4 小時 ±20% jitter | 更新 license、seat、device、policy |

- 付費版離線寬限：**72 小時**
- 試用版離線寬限：**24 小時**
- 降級策略：0~24h 靜默重試 → 24~72h 顯示警告 → 72h+ 停用核心功能（保留查看、付款入口）

### Kill Switch 設計

```
管理員撤銷 → license.status=revoked, revoke_version++ → KV/Redis 熱快取
→ 客戶端每 2 分鐘 light revoke check 拿到 revoked=true → 立即清 session lease → 停用發文
```

- 線上客戶端：2~5 分鐘內失效
- 離線客戶端：離線寬限到期後失效（無法做到真正即時）

### 互動時序圖

```mermaid
sequenceDiagram
    actor Buyer as 客戶
    actor Admin as 管理員
    participant Client as Desktop App
    participant API as Vercel API / License Server
    participant PSP as TapPay / ECPay

    Buyer->>Client: 選方案並開始付款
    Client->>API: POST /checkout/create
    API->>PSP: 建立付款單
    PSP-->>Client: payment_url
    Buyer->>PSP: 完成付款
    PSP-->>API: Webhook: payment_succeeded
    API->>API: 建立 subscription + license (status=active)
    API-->>Client: licenseKey

    Buyer->>Client: 輸入 licenseKey
    Client->>API: POST /license/activate {licenseKey, install_uuid, fp_hashes}
    API-->>Client: signed offline_ticket(72h) + session_lease(10m)

    loop App active (每2分鐘)
        Client->>API: GET /license/revoke-check
        API-->>Client: ok / revoked / expired
    end

    loop Full heartbeat (每4小時)
        Client->>API: POST /license/heartbeat
        API-->>Client: new offline_ticket + policy
    end

    Admin->>API: Revoke license
    API->>API: status=revoked; revoke_version++
    API-->>Client: revoked=true on next check
    Client->>Client: 停用發文/排程，保留唯讀與付款入口
```

### 推薦技術棧

**Vercel API + Postgres（權威資料）+ KV/Redis（熱路徑 revoke check）+ 簽名 lease token**

---

## Q3 — FB Selector 自我修復

### 背景

現有 `selenium_engine.py` 中 hardcode 了中英文 aria-label XPath fallback。Facebook 不定期改 DOM 導致 selector 失效需人工維護。

### 開源框架比較

| 方案 | 現況 | 真正能力 | 適合 FB 發文 app？ |
|---|---|---|---|
| SeleniumBase | 持續維護中 | 主要是 smart-waiting、click/type helpers，不是真正 locator healing | 適合 L1/L2 基底，不夠當完整解法 |
| Healenium | release 2.2.1 於 2026-03-31 | 以成功 baseline 自動 heal `NoSuchElement` | 適合大型 QA/grid；對單一發文服務偏重（需 proxy+backend+Postgres） |
| **AutoHeal Locator** | PyPI 1.0.11 於 2026-02-16 | AI DOM + 視覺 + cache + strategy | **最值得 PoC 的 Python 方案** |
| IntelliHeal | PyPI 0.1.8 於 2026-01-22 | AI 自癒 Selenium/Appium locator | 可觀察，但 ecosystem 小 |
| Stagehand | v3.6.3 於 2026-03-31，很活躍 | AI-native browser automation + self-healing + caching | 適合新架構，不適合直接替換現有本地 Selenium app |

### LLM DOM 辨識可行性

**可行，但不要把 LLM 當每次發文的主路徑。**

成本/延遲估算：

| 模式 | 建議模型 | 單次 API 成本 | 延遲（推估） | 建議用途 |
|---|---|---|---|---|
| DOM heal | gpt-4.1-mini | ~$0.001-$0.01 | ~0.8s-2.5s | 預設 L3 |
| DOM heal | Claude Sonnet 4 | ~$0.03-$0.07 | ~1.5s-4s | 較難案例 |
| Vision heal | gpt-4o | ~$0.004-$0.012 | ~2s-6s | L4 最後 fallback |

關鍵前提：**不要把整頁 Facebook DOM 原封不動丟給模型**。先用 JS 抽精簡 snapshot（只保留可互動節點 + aria/role 屬性），再只送 active composer container subtree。

### 推薦分層 fallback 架構

| Layer | 做法 | 延遲 | 成本 |
|---|---|---|---|
| L1 | Hardcoded selectors + locale variants（現有保留） | 最低 | 0 |
| L2 | 本地 fuzzy matching（先找 active composer 容器，在容器內找 editor/post button） | 很低 | 0 |
| L3 | LLM 看 pruned DOM snapshot（只在失敗時啟動，回傳 ranked candidates + confidence） | 中 | 低 |
| L4 | Vision + DOM hit-test（預設關閉，只截 composer 區塊，不整頁） | 最高 | 低到中 |

L2 設計重點：
1. 先找可見且 active 的 composer 容器
2. 在容器內找 editor（`[contenteditable="true"]`、`[role="textbox"]`、`aria-multiline="true"`）
3. 在同容器內找 post button（`role="button"` + label 匹配 `post|貼文|發佈|發布`）

L3 輸出：嚴格 JSON `{target_type, candidate_selector, selector_type, confidence, reason, container_signature}`

**Heal 成功後不要立刻覆蓋 L1**：進 cache → 連續成功 3 次 → promote 成 L2 → 人工審查升 L1。

### 推薦核心模組結構

```
selector_registry.py   - L1 hardcoded + locale variants
dom_snapshot.py        - JS 抽 visible interactive nodes
fuzzy_matcher.py       - L2 本地打分
llm_healer.py          - L3 DOM-heal
vision_healer.py       - L4 screenshot-heal
selector_cache.py      - healed selector cache / promotion
validator.py           - 點擊前後驗證
artifacts.py           - 存 DOM、screenshot、logs
```

### 實作建議

**短期**：自己寫 L2 fuzzy + L3 DOM-heal
**中期**：PoC AutoHeal Locator
**不建議一開始上 Healenium**（太重）
**Vision 保留為 L4，預設關閉**

---

## Q4 — 多帳號健康分數演算法

### 背景

需要一套帳號健康分數機制，避免 Meta 一次波及多個客戶帳號。

### 業界標竿洞察

| 工具 | 2025-2026 可見做法 | 可借鑑點 |
|---|---|---|
| Buffer | 官方 API 發文、內建 daily posting limits、duplicate preflight、draft approval | API lane 幾乎不吃客戶 IP 風險 |
| Hootsuite | 組織/權限管理；Instagram 某些情境改走 mobile notification workflow；reconnect/token lifecycle 當正式流程 | unsupported surface 不硬自動化，改 human-in-the-loop |
| SocialPilot | 把平台錯誤結構化；對 policy reject 不自動重試；一鍵 pause sharing | 建立 error taxonomy → risk event |
| Postiz | OAuth connect/refresh；`find-slot` API 回傳下一可用時段 | 把「下一個安全可發時段」做成 API |
| Jasper | Brand Voice / Style Guide / Permission Settings | 內容治理前置化，先降低重複化再進 scheduler |

**核心結論**：業界做法不是「偽裝」，而是「快停機器」：優先官方 API、結構化平台錯誤、unsupported surface 轉人工。

### 輸入訊號設計

| 訊號 | 量化方法 | 子分數公式 |
|---|---|---|
| 被攔截次數 | 事件加權（captcha=1, 重新登入=2, SMS checkpoint=3, temp block=4, 人工驗證=6），半衰期 14 天 | `S_block = 100 * exp(-0.35 * B)` |
| 發文間隔人性化 | 最近 30 則的 CV=std/mean，加 slot_repeat_ratio | `S_timing = 100 * (1 - 0.6*p_cv - 0.4*p_slot)` |
| 被刪帖比例 | 平台刪除/拒發權重高，使用者自刪低，半衰期 21 天 | `S_delete = 100 * exp(-8 * delete_ratio)` |
| 帳號年齡 | 以建立日或第一個可信成功發文日計 | `S_age = min(100, 20 + 20 * log2(1 + age_days/30))` |
| Proxy/IP 品質 | datacenter_asn、shared_accounts_same_ip_24h、impossible_geo_jumps_30d | `S_ip = max(0, 100 - 40*p_dc - 35*p_reuse - 25*p_geo)` |
| 發文內容相似度 | simhash + embedding cosine，比對最近 30 則與近 7 天跨帳號 | `S_content = max(0, 100 - 80*dup_rate - 40*near_dup_rate)` |

最佳發文間隔 CV 區間：**0.25 ~ 0.45**（太規律和太亂都不好）

### 健康分數公式

```text
raw_score =
  0.30 * S_block   +
  0.15 * S_timing  +
  0.15 * S_delete  +
  0.10 * S_age     +
  0.15 * S_ip      +
  0.15 * S_content

score = clamp(0, 100, raw_score - lane_penalty)
```

**lane_penalty**：官方 API = 0 / mobile-assist = 5 / **Selenium/browser = 10**

**Threshold**：
- **> 70**：健康，正常發文
- **40 ~ 70**：警告，自動降速
- **< 40**：暫停

**Hard stop 規則（不靠平均分稀釋，直接蓋帽）**：
- 72h 內出現 temporary lock / manual verification → `score = min(score, 39)`
- 24h 內 2 次以上 captcha/checkpoint → `score = min(score, 39)`
- 7 天內平台刪帖率 >= 15%（樣本 >= 10）→ `score = min(score, 39)`
- 同 cluster 24h 內 2 個以上帳號被驗證挑戰 → 整個 cluster pause

### 多帳號 Cluster Score

單帳號分數不夠，Meta/X 常常同內容/同 IP/同資產關聯一起波及：

```text
effective_score = min(account_score, cluster_score)

cluster_score =
  100
  - 35 * I(shared_verification_24h >= 2)
  - 25 * min(1, dup_burst_6h / 3)
  - 20 * min(1, shared_ip_accounts_24h / 5)
  - 20 * min(1, same_window_posts_15m / 4)
```

### 自動降速策略

| 分數區間 | 策略 |
|---|---|
| > 70 | throughput 100%；最小間隔照原設定 |
| 55-70 | throughput 70%；最小間隔 x1.5；禁止 exact duplicate |
| 40-55 | throughput 40%；最小間隔 x2.5；只允許高差異內容；同 IP group 一次只跑 1 個 active publish |
| < 40 | 停止自動發文；只允許 reconnect/人工檢查/token refresh |

**時間隨機化**：
- 健康區：`scheduled_at = preferred_slot + truncnorm(0, σ=12~18min, range=±30~45min)`
- 警告區：`σ=25~35min`，`range=±60~90min`

**Warm-up（pause 後）**：Day 1 = 25% → Day 2-3 = 50% → Day 4+ 無新事件才回正常速率

### Python 核心資料結構

```python
@dataclass
class RiskEvent:
    account_id: str
    platform: str
    event_type: str   # captcha / checkpoint / temp_block / post_deleted / ...
    severity: float
    ts: datetime
    meta: dict[str, Any]

@dataclass
class HealthSnapshot:
    account_id: str
    raw_score: float
    display_score: float
    band: str         # healthy / warning / paused
    next_allowed_at: datetime | None
    subscores: dict[str, float]

async def preflight(account_id: str, draft_id: str) -> HealthSnapshot:
    snap = await scorer.compute(account_id, draft_id)
    if snap.display_score < 40:
        raise RuntimeError("account paused")
    return snap
```

**aiohttp 控制平面端點**：`/preflight`、`/publish-result`、`/risk-event`、`/health/{account_id}`

**Selenium worker**：跑在獨立 process，不在 aiohttp event loop 內；所有 worker 發文前先打 `preflight`；captcha/checkpoint/policy reject 一律不自動重試。

---

## 綜合結論：FBGroupPosterPro SaaS 化的最關鍵 3 個技術決策

### 決策一：Patchright 取代 undetected-chromedriver（最高優先）

這是整個 SaaS 化工程最值得做的單一替換。UC 3.5.5 於 2024 年 2 月已凍結，Patchright 是 2026 年在 Meta 平台封鎖率最低、維護最積極的替代工具。遷移成本是中高（需從 Selenium API 遷到 Playwright 風格），但這是建立在 SaaS 上的核心競爭力，無法迴避。**務必搭配 persistent profile（不要每次 fresh）+ residential proxy（不要 datacenter）+ headed 模式（不要 headless）**，三者缺一整體效果大打折扣。不這麼做，無論換哪個 stealth 工具，SaaS 化後帳號封禁率都會明顯上升。

### 決策二：TapPay + 自建 License Server 取代現有半成品（緊急修補）

現有的 Vercel proxy 只收到 `licenseKey + deviceId`，沒有啟用、心跳、撤銷邏輯，等於是一個開著的大門。截至 2026-05-09，Stripe 官方仍未正式支援台灣主體，所以台灣 SaaS 的唯一有效選擇是 TapPay（定期扣款）+ ECPay（年繳/ATM 備援）。device_id 必須改掉 MAC address 設計，改用 `HMAC(install_uuid + 硬體指紋加權)` + 分數比對（>= 60 才算同裝置）。試用期的到期判斷必須走伺服器 UTC 時間，不能靠本地時鐘。kill switch 靠 2 分鐘 polling 的 light revoke check 即可達到幾分鐘內生效。

### 決策三：帳號健康分數 + Cluster Guard 才能規模化（SaaS 差異化功能）

這是「有做和沒做」差別最大的一個決策。沒有這套機制，一旦 SaaS 上有 10 個以上客戶同時用同樣的 IP group 或 content family 發文，Meta 一次就能把整批帳號踢掉。健康分數的核心是：`S_block` 佔 30% 權重（最關鍵的衰減訊號），Selenium/browser lane 要扣 10 分 penalty，hard stop 規則不能靠平均分數稀釋。更關鍵的是 **cluster_score 機制**：`effective_score = min(account_score, cluster_score)`，24h 內同 cluster 有 2 個帳號被驗證挑戰就整個 cluster pause。這是目前所有業界標竿（Buffer/SocialPilot/Hootsuite）都在做的底線，只是他們走官方 API 所以風險自動降低，FBGroupPosterPro 走 Selenium lane 必須用分數系統來補這個缺口。

---

*研究來源：GitHub repos、官方文件、PyPI release history、Reddit 社群實測、平台官方政策頁面（詳細 URL 見各題節）*
