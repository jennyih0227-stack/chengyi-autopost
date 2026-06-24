# 誠毅傳承｜三平台自動發文系統

設定一次，之後 **Telegram / Facebook / Instagram** 每天自動發文，你的電腦關著也照發。
引擎跑在 **GitHub Actions**（免費雲端排程），用你現有的 `jennyih0227-stack` 帳號即可。

---

## 整體運作方式

```
schedule.csv（你填哪天發第幾則）
        ↓
GitHub Actions（每天台灣早上 8:00 自動觸發）
        ↓
post.py（找出今天該發的那則）
        ↓
   Telegram ＋ Facebook ＋ Instagram 同時發布
```

你平常只需要：偶爾打開 `schedule.csv` 看排程、或加新貼文。其餘全自動。

---

## 設定步驟總覽

| 步驟 | 做什麼 | 難度 | 必要性 |
|------|--------|------|--------|
| 1 | 申請 Telegram Bot | ⭐ 很簡單 | Telegram 必做 |
| 2 | 取得 Facebook 粉專 Token | ⭐⭐⭐ 較繁瑣 | FB/IG 必做 |
| 3 | 取得 Instagram User ID | ⭐⭐ 中等 | IG 必做 |
| 4 | 把專案推上 GitHub | ⭐⭐ 中等 | 必做 |
| 5 | 在 GitHub 填入金鑰（Secrets） | ⭐ 很簡單 | 必做 |
| 6 | 測試 + 啟用 | ⭐ 很簡單 | 必做 |

建議**先把 Telegram 跑通**（10 分鐘內可完成），確認整套流程沒問題，再處理較花時間的 FB/IG。

---

## 步驟 1：Telegram Bot（最簡單，先做這個）

1. 在 Telegram 搜尋 **@BotFather**，傳 `/newbot`，依指示命名。
2. 它會給你一串 **token**（像 `123456:ABC-DEF...`），這就是 `TG_BOT_TOKEN`。
3. 建立一個 Telegram **頻道**（Channel），把你的 Bot 加進去設為**管理員**。
4. `TG_CHAT_ID` 填你的頻道公開名稱，例如 `@chengyichuancheng`。
   - 若是私人頻道/群組，需要數字 ID，可把 Bot 加進去後傳訊息，用 `https://api.telegram.org/bot<TOKEN>/getUpdates` 查 `chat.id`。

> ✅ 完成後可先本地測試（見最後一節），看 Bot 是否成功發圖文。

---

## 步驟 2：Facebook 粉專 Token

> 這段是整套最花時間的，但只需做一次。FB 與 IG 共用同一組 Token。

1. 前往 **developers.facebook.com**，用你的 FB 帳號登入，建立一個「應用程式」(App)，類型選**商業 (Business)**。
2. 在左側選單加入產品 **Facebook 登入** 或直接用 **Graph API 工具**。
3. 進入 **工具 → Graph API Explorer**：
   - 右上選你的 App。
   - 點「取得權杖 → 取得粉專存取權杖」，授權勾選這些權限：
     `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
     `instagram_basic`, `instagram_content_publish`, `business_management`
4. 取得 **粉專 ID**：在 Explorer 輸入 `me/accounts` 送出，回傳中找到你粉專的 `id` → 這是 `FB_PAGE_ID`，旁邊的 `access_token` 是短期粉專權杖。
5. **換成長期權杖**（短期約 1 小時就失效）：
   - 用 `工具 → 存取權杖偵錯工具`，貼上權杖，點「延長存取權杖」，可得約 60 天的長期權杖。
   - 進階做法可換「永不過期」的粉專權杖（教學見 Meta 文件「Page Access Token」），建議之後再優化。
   - 這串長期權杖就是 `FB_PAGE_TOKEN`。

> ⚠️ Token 會過期。若哪天 FB/IG 發文失敗，多半是 Token 到期，重做第 4–5 步換新即可。

---

## 步驟 3：Instagram User ID

> 前提：你的 IG 必須是**商業帳號或創作者帳號**，且已**連結到上面那個 FB 粉專**（在 IG App → 設定 → 帳號 → 連結粉專）。

1. 在 Graph API Explorer 輸入：
   `{FB_PAGE_ID}?fields=instagram_business_account`
2. 回傳的 `instagram_business_account.id` 就是 `IG_USER_ID`。

### IG 圖片網址（重要）

IG 的 API 規定：**圖片必須是「公開網址」**，不能直接上傳檔案。
好消息——你的圖片已經放在這個專案的 `posts/images/`，推上 GitHub 後可用 **GitHub Pages** 直接當公開圖床：

1. 專案推上 GitHub 後，到 repo 的 **Settings → Pages**，
   Source 選 `main` 分支、根目錄，存檔。
2. 幾分鐘後你的圖片網址會是：
   `https://jennyih0227-stack.github.io/chengyi-autopost/posts/images/01_人生如秤.jpg`
3. 把基底網址（到 images 為止）填進 `IG_IMAGE_BASE_URL`：
   `https://jennyih0227-stack.github.io/chengyi-autopost/posts/images`

> Telegram 和 Facebook 是直接上傳檔案，不需要圖片網址；只有 IG 需要。

---

## 步驟 4：推上 GitHub

最快的方式是用 **Claude Code**。在這個專案資料夾打開 Claude Code，告訴它：

> 「把這個資料夾初始化成 git repo，建立一個叫 chengyi-autopost 的 GitHub repo，推上去」

或手動指令：

```bash
cd chengyi-autopost
git init
git add .
git commit -m "誠毅傳承自動發文系統"
gh repo create chengyi-autopost --public --source=. --push
```

> `.env` 已被 `.gitignore` 排除，金鑰不會外洩。

---

## 步驟 5：在 GitHub 填入金鑰（Secrets）

到 repo 的 **Settings → Secrets and variables → Actions → New repository secret**，
逐一新增（名稱要完全一致）：

| Secret 名稱 | 值 |
|-------------|-----|
| `TG_BOT_TOKEN` | 步驟 1 的 Bot token |
| `TG_CHAT_ID` | 你的頻道（如 `@chengyichuancheng`）|
| `FB_PAGE_ID` | 步驟 2 的粉專 ID |
| `FB_PAGE_TOKEN` | 步驟 2 的長期 Token |
| `IG_USER_ID` | 步驟 3 的 IG User ID |
| `IG_IMAGE_BASE_URL` | 步驟 3 的圖片基底網址 |

> 只想先跑 Telegram？只填前兩個，schedule.csv 把 fb/ig 欄改成 N 即可。

---

## 步驟 6：測試與啟用

1. 到 repo 的 **Actions** 分頁，找到「誠毅傳承每日自動發文」。
2. 點 **Run workflow**，可在 `override_date` 填一個 schedule.csv 裡有的日期來測試（例如 `2026-07-01`），手動跑一次看是否成功發布。
3. 成功後就不用管了——它每天台灣早上 8:00 自動發。

### 改發文時間

編輯 `.github/workflows/autopost.yml` 的 cron。注意是 **UTC 時間**，台灣要 −8 小時：

| 想在台灣幾點發 | cron 寫法 |
|---------------|-----------|
| 08:00 | `0 0 * * *` |
| 12:00 | `0 4 * * *` |
| 20:00 | `0 12 * * *` |

---

## 日常使用

### 改排程
打開 `posts/schedule.csv`：
- `date`：發文日期
- `post_id`：對應第幾則語錄（1–30）
- `ig` / `fb` / `tg`：填 `Y` 發、`N` 不發

改完推上 GitHub（或用 Claude Code 幫你推）即可生效。

### 加新語錄
1. 圖片放進 `posts/images/`
2. 在 `posts/posts.json` 新增一筆（照現有格式）
3. 在 `schedule.csv` 排日期

---

## 疑難排解

| 症狀 | 可能原因 | 解法 |
|------|---------|------|
| FB/IG 發文失敗 | Token 過期 | 重做步驟 2 換新 Token，更新 Secret |
| IG 失敗、FB 正常 | 圖片網址不通 | 確認 GitHub Pages 已啟用、網址正確 |
| Telegram 沒發出 | Bot 不是管理員 | 把 Bot 設為頻道管理員 |
| 整個沒跑 | 當天 schedule 無資料 | 檢查 schedule.csv 日期 |
| Actions 沒自動觸發 | repo 太久沒活動被停用 | GitHub 會發信通知，點一下重新啟用 |

---

## 安全提醒

- 所有金鑰只存在 GitHub Secrets 與你本地的 `.env`，**絕不**寫進程式碼。
- `.env` 已被 git 忽略，不會被推上去。
- 若 Token 不慎外洩，到 Meta/BotFather 重新產生即可作廢舊的。
