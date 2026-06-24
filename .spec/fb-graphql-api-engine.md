# Spec: FB 發文/抓permalink/刪文 改走 GraphQL API（取代脆弱 DOM）

> spec_id: spec-fb-graphql-api-engine
> created: 2026-06-23
> status: ✅ DONE + VERIFIED（2026-06-24，整合進產品引擎並實機驗證）
> task_level: full（FB 逆向 + selenium_engine 重構）
> machine: Beaver(Windows，產品+session 在這) + M4 協調

## ✅ 交付前驗收閘（2026-06-24，逐項實證）

逆向取得的關鍵事實（皆親自攔截、HTTP 200 實證）：
- delete mutation：`useCometFeedStoryDeleteMutation` doc_id=`36213403264942057`，story_id=base64(`S:_I{actor}:{post}:{post}`)，FB 成功回 `story_delete.deleted_story_id`。
- compose mutation：`ComposerStoryCreateMutation` doc_id=`27638478529090712`；回應含 post_id + `/posts/` permalink。
- timeline 讀取：`ProfileCometTimelineFeedRefetchQuery` doc_id=`27592098867143956`。
- selenium-wire 不相容問題：用「頁面注入 fetch/XHR hook（CDP addScriptToEvaluateOnNewDocument）」取代，零額外依賴。
- mbasic 死路：FB 對此帳號強制升級 mtouch，已棄用。

| ID | 需求 | 結果 | 證據 |
|----|------|------|------|
| FR-1 | 抓 permalink | ✅ | compose 回應攔到 post_id + permalink；整合測試 [3] 通過 |
| FR-2 | 刪文走 GraphQL | ✅ | 純 requests 刪除回 200 + `deleted_story_id`；engine.delete_post→True |
| FR-3 | 取 doc_id + 健康檢查 | ✅ | 三個 doc_id 記為常數；delete 回 `doc_id_stale`/`ok` 結構供 fallback |
| FR-4 | selenium_engine 整合 | ✅ | `_do_post` 回 post_id+permalink、`delete_post` GraphQL 優先 + DOM fallback、scheduler 接上、DB v5 fb_post_id；50-route boot OK |
| FR-5 | 清掉舊測試貼文 | ✅ | 牆已掃描確認乾淨（含 fbpverify x7q2，FB 已自動移除機械字樣貼文）；測試貼文皆即發即刪 |

**Ray(Codex) 覆核**：抓到 P1-1（capture buffer 不清空→跨篇 post_id 污染→誤刪風險）等，全數修復；雙發測試證實兩篇得到不同 post_id。

**已知限制 / 待 Rain 決策**：
- doc_id 會 rotate：已做 stale 偵測 + DOM fallback，但**失效路徑未實測**（只驗成功路徑）。真失效時靠 fallback 保底，doc_id 需手動更新常數。
- FB 風控：純機械字樣貼文（含 "auto"/"程式自動"）會被 FB 秒移除——**產品實際發文措辭要自然**，且同帳號別猛發。
- `_fbcookies.json` 為明文 session（Beaver 本機），屬既有狀態，未納入本次。

## 1. 背景（今晚 2026-06-23 得到的起點）
DOM 爬 m.facebook.com React 版抓 permalink/刪文全失敗（class 混淆、巢狀深、貼文 async GraphQL 載入、page_source 沒內容）。
fusion 多模型共識：**改走 API 路線**（E Graph API > B 內部GraphQL > A CDP > D role錨點 > C 單篇頁）。

## 2. 已確認的關鍵事實（別重摸）
- ✅ **FB session 已持久化**：Beaver `~/.fbgroupposter/profiles/account_1`（已登入）+ DB Account id=1（cookies 加密）+ 明文 `_fbcookies.json`(7 cookies: c_user/xs/datr/fr/sb)
- ✅ FB user_id（c_user）= **100002466584274**，profile = facebook.com/chenyu.lin.795873
- ✅ 從頁面抽得到 **`fb_dtsg`(len69) + `lsd`**（`"DTSGInitialData",[],{"token":"..."}` / `"LSD",[],{"token":"..."}`）→ **B 路線可行**
- ❌ 頁面沒有 EAA access_token → E 路線要另外換 token（adsmanager/business 頁面或 GraphQL Authorization header）
- ⚠️ **selenium-wire 不相容**：Python 3.12 + 新 setuptools 缺 pkg_resources。要嘛 `pip install "setuptools<81"`，要嘛**改用 selenium 4 內建 `driver.execute_cdp_cmd`（Network domain）**或純 `requests`
- ✅ **發文 DOM 流程已驗證可用**（保留當備援）：m.facebook 點 `div[role=button]` 文字「發表近況更新」→ /composer/ → `contenteditable` 打字 → `div[role=button]` 文字「發佈」→ 上牆

## 3. 需求
| ID | 優先 | 需求 | 驗收 |
|----|------|------|------|
| FR-1 | MUST | 抓 permalink：發文時 CDP/wire 攔 GraphQL response 取 story_fbid/post_id，或合成 `facebook.com/{userid}/posts/{postid}` | 發一篇→拿到正確可開啟的 permalink |
| FR-2 | MUST | 刪文：用 fb_dtsg+cookies POST FB GraphQL delete mutation（或 Graph API DELETE /{post_id}） | 刪掉指定 post→profile 上消失 |
| FR-3 | MUST | 取 doc_id：從真實請求複製 compose/delete 的 doc_id+variables（doc_id 會變→寫成可更新常數+健康檢查） | 記錄抓法，doc_id 失效有明確錯誤 |
| FR-4 | SHOULD | selenium_engine 的 _do_post 抓 permalink + delete_post 改 API 版（取代今晚標 UNVERIFIED 的 mbasic 選擇器） | 整合進產品、scheduler 自動刪除走這條 |
| FR-5 | MUST | 清掉今晚那篇測試貼文（marker: fbpverify x7q2）若還在 | — |

## 4. 建議實作順序
1. 修 selenium-wire（setuptools<81）或改 CDP `execute_cdp_cmd('Network.enable')` + `Network.getResponseBody`
2. 載入 profile，攔 GraphQL，找含 marker 的 response → 看 post_id/story_fbid 真實欄位結構
3. 開 Chrome DevTools 手動發+刪一次，從 Network 複製真實 delete mutation（doc_id/variables/headers: fb_dtsg,lsd,jazoest,x-fb-friendly-name）
4. 用 requests 重放 delete → 驗證 → 包成函式
5. 同法做 compose（或保留 DOM 發文+CDP 抓 id 的混合：DOM 發文已驗證可用）
6. 改 selenium_engine + 測 scheduler 自動刪除真的會刪

## 5. 風險
- doc_id 變動 → 健康檢查 + 從備援 DOM 路線 fallback
- FB 風控：同帳號別猛發、保留隨機間隔
- 對外發文是真動作：測試只在 Rain 自己塗鴉牆 + 立即刪
