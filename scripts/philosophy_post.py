#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日哲學 — 四平台發布
讀 philosophy/_content.json（由 philosophy_gen.py 產生），把當日卡片 + 文案發到：
  LINE（圖 + 文字）／Facebook 粉專（圖文）／Instagram（圖文）／Threads（圖文）

圖片托管：卡片已由 workflow commit 到 GitHub，本腳本用 GitHub Pages 公開網址取用，
先輪詢確認圖片已上線，再發給需要網址的平台（LINE / IG / Threads）。
Facebook 直接上傳檔案，不需網址。

需要的環境變數：
  LINE_TOKEN, USER_ID
  FB_PAGE_ID, FB_PAGE_TOKEN
  IG_USER_ID
  THREADS_USER_ID, THREADS_ACCESS_TOKEN
  GITHUB_REPOSITORY  （Actions 自動提供，格式 owner/repo；本機測試可用 PAGES_BASE_URL 覆蓋）
可選：
  PAGES_BASE_URL     圖床基底網址，覆蓋自動推導
  ONLY               只發指定平台，逗號分隔，例如 "line" 或 "line,fb"
"""
import os, json, sys, time
import urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_JSON = os.path.join(ROOT, "philosophy", "_content.json")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_content():
    with open(CONTENT_JSON, encoding="utf-8") as f:
        return json.load(f)


def pages_base_url():
    override = os.environ.get("PAGES_BASE_URL")
    if override:
        return override.rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}"
    raise RuntimeError("找不到圖床網址：請設 GITHUB_REPOSITORY 或 PAGES_BASE_URL")


def build_caption(c, with_tags=True):
    lines = [
        "【今日小故事】", c["story"], "",
        "【人生哲學】", c["quote"], "",
        "【今日啟示】", c["revelation"], "",
        "—— 熊誠毅｜誠毅傳承　資產管理 × 財富傳承",
        "誠於心 · 毅於行 · 傳於世 · 承於志",
    ]
    if with_tags:
        lines.append("")
        lines.append("#每日哲學 #誠毅傳承 #人生智慧 #財富傳承")
    return "\n".join(lines)


def wait_until_live(url, tries=40, interval=10):
    """輪詢圖片網址，直到 GitHub Pages 建置完成、可公開存取。"""
    log(f"等待圖片上線：{url}")
    for i in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200:
                    log(f"  ✓ 圖片已上線（第 {i} 次嘗試）")
                    return True
        except urllib.error.HTTPError as e:
            if e.code not in (404, 403):
                log(f"  嘗試 {i}：HTTP {e.code}")
        except Exception as e:
            log(f"  嘗試 {i}：{e}")
        time.sleep(interval)
    raise RuntimeError(f"圖片超時仍未上線：{url}")


# ---------- LINE ----------
def post_line(image_url, c):
    token = os.environ["LINE_TOKEN"]
    user_id = os.environ["USER_ID"]
    text = build_caption(c, with_tags=False)
    body = json.dumps({
        "to": user_id,
        "messages": [
            {"type": "image",
             "originalContentUrl": image_url,
             "previewImageUrl": image_url},
            {"type": "text", "text": text},
        ],
    }).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push", data=body,
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()
    log("  ✓ LINE 發送成功")


# ---------- Facebook 粉專（用公開圖片網址，較穩、附重試）----------
def post_facebook(image_url, c):
    page_id = os.environ["FB_PAGE_ID"]
    token = os.environ["FB_PAGE_TOKEN"]
    caption = build_caption(c)
    url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
    data = urllib.parse.urlencode({
        "url": image_url, "caption": caption, "access_token": token
    }).encode()
    last = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, data=data), timeout=120) as r:
                resp = json.load(r)
            if "id" in resp or "post_id" in resp:
                log("  ✓ Facebook 發送成功")
                return
            last = resp
        except urllib.error.HTTPError as e:
            try:
                last = e.read().decode(errors="ignore")
            except Exception:
                last = f"HTTP {e.code}"
            log(f"  Facebook 第 {attempt} 次失敗（HTTP {e.code}），重試中…")
        except Exception as e:
            last = str(e)
            log(f"  Facebook 第 {attempt} 次失敗（{e}），重試中…")
        time.sleep(6)
    raise RuntimeError(f"Facebook 回傳異常：{last}")


# ---------- Instagram ----------
def post_instagram(image_url, c):
    ig_user = os.environ["IG_USER_ID"]
    token = os.environ["FB_PAGE_TOKEN"]  # IG 用同一組 Page Token
    caption = build_caption(c)
    create = f"https://graph.facebook.com/v21.0/{ig_user}/media"
    data = urllib.parse.urlencode({
        "image_url": image_url, "caption": caption, "access_token": token
    }).encode()
    with urllib.request.urlopen(
            urllib.request.Request(create, data=data), timeout=120) as r:
        resp = json.load(r)
    container = resp.get("id")
    if not container:
        raise RuntimeError(f"IG 建立容器失敗：{resp}")
    time.sleep(5)
    publish = f"https://graph.facebook.com/v21.0/{ig_user}/media_publish"
    data2 = urllib.parse.urlencode({
        "creation_id": container, "access_token": token
    }).encode()
    with urllib.request.urlopen(
            urllib.request.Request(publish, data=data2), timeout=120) as r:
        resp2 = json.load(r)
    if "id" not in resp2:
        raise RuntimeError(f"IG 發布失敗：{resp2}")
    log("  ✓ Instagram 發送成功")


# ---------- Threads ----------
def _open_json(req, timeout=120):
    """送出請求並回傳 JSON；若是 HTTP 錯誤，把 Meta 回傳的詳細訊息一併拋出。"""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode(errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"HTTP {e.code} — {body}") from None


def build_threads_caption(c):
    """Threads 內文上限 500 字，且只吃單一 hashtag；用精簡版避免被擋。"""
    lines = [
        c["quote"], "",
        "【今日啟示】" + c["revelation"], "",
        "—— 熊誠毅｜誠毅傳承",
        "#每日哲學",
    ]
    text = "\n".join(lines)
    if len(text) > 480:
        text = text[:477] + "…"
    return text


def post_threads(image_url, c):
    user_id = os.environ["THREADS_USER_ID"]
    token = os.environ["THREADS_ACCESS_TOKEN"]
    caption = build_threads_caption(c)
    create = f"https://graph.threads.net/v1.0/{user_id}/threads"
    data = urllib.parse.urlencode({
        "media_type": "IMAGE", "image_url": image_url,
        "text": caption, "access_token": token
    }).encode()
    resp = _open_json(urllib.request.Request(create, data=data))
    container = resp.get("id")
    if not container:
        raise RuntimeError(f"Threads 建立容器失敗：{resp}")
    status_url = (f"https://graph.threads.net/v1.0/{container}"
                  f"?fields=status,error_message"
                  f"&access_token={urllib.parse.quote(token)}")
    for _ in range(20):
        time.sleep(3)
        st = _open_json(urllib.request.Request(status_url), timeout=60)
        if st.get("status") == "FINISHED":
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads 圖片處理失敗：{st}")
    publish = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    data2 = urllib.parse.urlencode({
        "creation_id": container, "access_token": token
    }).encode()
    resp2 = _open_json(urllib.request.Request(publish, data=data2))
    if "id" not in resp2:
        raise RuntimeError(f"Threads 發布失敗：{resp2}")
    log("  ✓ Threads 發送成功")


def main():
    c = load_content()
    image_url = pages_base_url() + "/" + c["image_file"]
    only = {p.strip() for p in os.environ.get("ONLY", "").split(",") if p.strip()}

    def want(name):
        return not only or name in only

    log(f"發布 {c['date']} 每日哲學｜金句：{c['quote']}")

    # 四平台都用公開圖片網址，發文前先確認圖片已上線
    if any(want(p) for p in ("line", "fb", "ig", "threads")):
        wait_until_live(image_url)

    errors = []
    plan = [
        ("line", "LINE", lambda: post_line(image_url, c)),
        ("fb", "Facebook", lambda: post_facebook(image_url, c)),
        ("ig", "Instagram", lambda: post_instagram(image_url, c)),
        ("threads", "Threads", lambda: post_threads(image_url, c)),
    ]
    for key, name, fn in plan:
        if not want(key):
            continue
        try:
            fn()
        except Exception as e:
            msg = f"  ✗ {name} 失敗：{e}"
            log(msg)
            errors.append(msg)

    if errors:
        log("=== 有平台發送失敗 ===")
        for e in errors:
            log(e)
        sys.exit(1)
    log("全部平台發送完成 ✓")


if __name__ == "__main__":
    main()
