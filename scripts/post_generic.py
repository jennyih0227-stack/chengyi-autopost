#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用發布器 — 把「一張圖 + 文案」發到 LINE / FB / IG / Threads。
給九宮格漫畫（或任何單圖貼文）用；讀一份 content json：
  { "image_file": "posts/comic/xxx.jpg",
    "caption": "IG/FB/LINE 內文",
    "threads_caption": "Threads 精簡內文（可省略，省略則用 caption 前 480 字）" }

圖片托管：先把圖 commit 上 GitHub（由呼叫端負責），本器用 GitHub Pages 公開網址取用，
輪詢確認上線後再發給需要網址的平台。

需要環境變數：
  LINE_TOKEN, USER_ID, FB_PAGE_ID, FB_PAGE_TOKEN, IG_USER_ID,
  THREADS_USER_ID, THREADS_ACCESS_TOKEN
  PAGES_BASE_URL 或 GITHUB_REPOSITORY（推導圖床網址；本機預設用誠毅的 Pages）
可選：
  CONTENT_JSON  content json 路徑（預設 comic/_content.json）
  ONLY          只發指定平台，逗號分隔，如 "ig,fb"
"""
import os, json, sys, time
import urllib.request, urllib.parse, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONTENT = os.path.join(ROOT, "comic", "_content.json")
DEFAULT_PAGES = "https://jennyih0227-stack.github.io/chengyi-autopost"


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_dotenv():
    """本機執行時，從 chengyi-autopost/.env 載入金鑰；已存在的環境變數優先（GitHub Actions）。"""
    envp = os.path.join(ROOT, ".env")
    if not os.path.exists(envp):
        return
    for line in open(envp, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def pages_base():
    if os.environ.get("PAGES_BASE_URL"):
        return os.environ["PAGES_BASE_URL"].rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}"
    return DEFAULT_PAGES


def _open_json(req, timeout=120):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode(errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"HTTP {e.code} — {body}") from None


def wait_until_live(url, tries=40, interval=10):
    log(f"等待圖片上線：{url}")
    for i in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as r:
                if r.status == 200:
                    log(f"  ✓ 圖片已上線（第 {i} 次）")
                    return
        except urllib.error.HTTPError as e:
            if e.code not in (404, 403):
                log(f"  嘗試 {i}：HTTP {e.code}")
        except Exception as e:
            log(f"  嘗試 {i}：{e}")
        time.sleep(interval)
    raise RuntimeError(f"圖片超時未上線：{url}")


def post_line(image_url, caption):
    body = json.dumps({
        "to": os.environ["USER_ID"],
        "messages": [
            {"type": "image", "originalContentUrl": image_url, "previewImageUrl": image_url},
            {"type": "text", "text": caption},
        ],
    }).encode()
    _open_json(urllib.request.Request(
        "https://api.line.me/v2/bot/message/push", data=body,
        headers={"Authorization": "Bearer " + os.environ["LINE_TOKEN"],
                 "Content-Type": "application/json"}), timeout=60)
    log("  ✓ LINE 發送成功")


def post_facebook(image_url, caption):
    page_id = os.environ["FB_PAGE_ID"]; token = os.environ["FB_PAGE_TOKEN"]
    url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
    data = urllib.parse.urlencode({"url": image_url, "caption": caption,
                                   "access_token": token}).encode()
    last = None
    for attempt in range(1, 4):
        try:
            resp = _open_json(urllib.request.Request(url, data=data))
            if "id" in resp or "post_id" in resp:
                log("  ✓ Facebook 發送成功"); return
            last = resp
        except Exception as e:
            last = str(e); log(f"  Facebook 第 {attempt} 次失敗，重試…")
        time.sleep(6)
    raise RuntimeError(f"Facebook 失敗：{last}")


def post_instagram(image_url, caption):
    ig = os.environ["IG_USER_ID"]; token = os.environ["FB_PAGE_TOKEN"]
    create = f"https://graph.facebook.com/v21.0/{ig}/media"
    resp = _open_json(urllib.request.Request(create, data=urllib.parse.urlencode(
        {"image_url": image_url, "caption": caption, "access_token": token}).encode()))
    container = resp.get("id")
    if not container:
        raise RuntimeError(f"IG 建立容器失敗：{resp}")
    time.sleep(5)
    pub = f"https://graph.facebook.com/v21.0/{ig}/media_publish"
    resp2 = _open_json(urllib.request.Request(pub, data=urllib.parse.urlencode(
        {"creation_id": container, "access_token": token}).encode()))
    if "id" not in resp2:
        raise RuntimeError(f"IG 發布失敗：{resp2}")
    log("  ✓ Instagram 發送成功")


def post_threads(image_url, caption):
    uid = os.environ["THREADS_USER_ID"]; token = os.environ["THREADS_ACCESS_TOKEN"]
    if len(caption) > 480:
        caption = caption[:477] + "…"
    create = f"https://graph.threads.net/v1.0/{uid}/threads"
    resp = _open_json(urllib.request.Request(create, data=urllib.parse.urlencode(
        {"media_type": "IMAGE", "image_url": image_url, "text": caption,
         "access_token": token}).encode()))
    container = resp.get("id")
    if not container:
        raise RuntimeError(f"Threads 建立容器失敗：{resp}")
    status_url = (f"https://graph.threads.net/v1.0/{container}"
                  f"?fields=status,error_message&access_token={urllib.parse.quote(token)}")
    for _ in range(20):
        time.sleep(3)
        st = _open_json(urllib.request.Request(status_url), timeout=60)
        if st.get("status") == "FINISHED":
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads 圖片處理失敗：{st}")
    pub = f"https://graph.threads.net/v1.0/{uid}/threads_publish"
    resp2 = _open_json(urllib.request.Request(pub, data=urllib.parse.urlencode(
        {"creation_id": container, "access_token": token}).encode()))
    if "id" not in resp2:
        raise RuntimeError(f"Threads 發布失敗：{resp2}")
    log("  ✓ Threads 發送成功")


def main():
    load_dotenv()
    path = os.environ.get("CONTENT_JSON", DEFAULT_CONTENT)
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    caption = c["caption"]
    threads_caption = c.get("threads_caption", caption)
    image_url = pages_base() + "/" + c["image_file"]
    only = {p.strip() for p in os.environ.get("ONLY", "").split(",") if p.strip()}
    want = lambda n: not only or n in only

    log(f"發布單圖貼文：{c['image_file']}")
    if any(want(p) for p in ("line", "fb", "ig", "threads")):
        wait_until_live(image_url)

    errors = []
    plan = [
        ("line", "LINE", lambda: post_line(image_url, caption)),
        ("fb", "Facebook", lambda: post_facebook(image_url, caption)),
        ("ig", "Instagram", lambda: post_instagram(image_url, caption)),
        ("threads", "Threads", lambda: post_threads(image_url, threads_caption)),
    ]
    for key, name, fn in plan:
        if not want(key):
            continue
        try:
            fn()
        except Exception as e:
            log(f"  ✗ {name} 失敗：{e}"); errors.append(name)

    if errors:
        log("=== 有平台失敗：" + "、".join(errors) + " ===")
        sys.exit(1)
    log("全部平台發送完成 ✓")


if __name__ == "__main__":
    main()
