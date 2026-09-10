#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
輪播/多圖發布器 — 把多張圖發成 IG 輪播、FB 多圖貼文、LINE 多圖訊息。
讀 content json（預設 lifeplanning/_carousel.json）：
  { "images": ["posts/lifeplanning/lp01.png", ...],  # 依序，最多 10 張（IG 上限）
    "caption": "IG/FB 內文",
    "line_intro": "LINE 開頭文字（可省略）" }

圖片需先 commit 上 GitHub（呼叫端負責），本器用 GitHub Pages 公開網址取用。
需要環境變數：FB_PAGE_ID, FB_PAGE_TOKEN, IG_USER_ID, LINE_TOKEN, USER_ID
              PAGES_BASE_URL 或 GITHUB_REPOSITORY（本機預設誠毅 Pages）
可選：CONTENT_JSON、ONLY（如 "ig,fb"）
"""
import os, sys, json, time
import urllib.request, urllib.parse, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONTENT = os.path.join(ROOT, "lifeplanning", "_carousel.json")
DEFAULT_PAGES = "https://jennyih0227-stack.github.io/chengyi-autopost"


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_dotenv():
    envp = os.path.join(ROOT, ".env")
    if not os.path.exists(envp):
        return
    for line in open(envp, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def pages_base():
    if os.environ.get("PAGES_BASE_URL"):
        return os.environ["PAGES_BASE_URL"].rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        o, n = repo.split("/", 1)
        return f"https://{o}.github.io/{n}"
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
    for i in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(interval)
    raise RuntimeError(f"圖片超時未上線：{url}")


# ---------- IG 輪播 ----------
def post_instagram(urls, caption):
    ig = os.environ["IG_USER_ID"]; token = os.environ["FB_PAGE_TOKEN"]
    children = []
    for u in urls:
        resp = _open_json(urllib.request.Request(
            f"https://graph.facebook.com/v21.0/{ig}/media",
            data=urllib.parse.urlencode({
                "image_url": u, "is_carousel_item": "true", "access_token": token
            }).encode()))
        cid = resp.get("id")
        if not cid:
            raise RuntimeError(f"IG 子項失敗：{resp}")
        children.append(cid)
    time.sleep(6)
    car = _open_json(urllib.request.Request(
        f"https://graph.facebook.com/v21.0/{ig}/media",
        data=urllib.parse.urlencode({
            "media_type": "CAROUSEL", "children": ",".join(children),
            "caption": caption, "access_token": token
        }).encode()))
    container = car.get("id")
    if not container:
        raise RuntimeError(f"IG 輪播容器失敗：{car}")
    time.sleep(6)
    pub = _open_json(urllib.request.Request(
        f"https://graph.facebook.com/v21.0/{ig}/media_publish",
        data=urllib.parse.urlencode({
            "creation_id": container, "access_token": token
        }).encode()))
    if "id" not in pub:
        raise RuntimeError(f"IG 發布失敗：{pub}")
    log("  ✓ Instagram 輪播發送成功")


# ---------- FB 多圖 ----------
def post_facebook(urls, caption):
    page = os.environ["FB_PAGE_ID"]; token = os.environ["FB_PAGE_TOKEN"]
    fbids = []
    for u in urls:
        resp = _open_json(urllib.request.Request(
            f"https://graph.facebook.com/v21.0/{page}/photos",
            data=urllib.parse.urlencode({
                "url": u, "published": "false", "access_token": token
            }).encode()))
        if "id" not in resp:
            raise RuntimeError(f"FB 圖片上傳失敗：{resp}")
        fbids.append(resp["id"])
    params = {"message": caption, "access_token": token}
    for i, mid in enumerate(fbids):
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": mid})
    resp = _open_json(urllib.request.Request(
        f"https://graph.facebook.com/v21.0/{page}/feed",
        data=urllib.parse.urlencode(params).encode()))
    if "id" not in resp:
        raise RuntimeError(f"FB 多圖貼文失敗：{resp}")
    log("  ✓ Facebook 多圖貼文成功")


# ---------- LINE 多圖 ----------
def post_line(urls, intro):
    token = os.environ["LINE_TOKEN"]; uid = os.environ["USER_ID"]
    msgs = []
    if intro:
        msgs.append({"type": "text", "text": intro})
    for u in urls:
        msgs.append({"type": "image", "originalContentUrl": u, "previewImageUrl": u})
    # LINE 每次 push 最多 5 則，分批送
    for i in range(0, len(msgs), 5):
        batch = msgs[i:i + 5]
        _open_json(urllib.request.Request(
            "https://api.line.me/v2/bot/message/push",
            data=json.dumps({"to": uid, "messages": batch}).encode(),
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json"}), timeout=60)
    log("  ✓ LINE 多圖發送成功")


def main():
    load_dotenv()
    path = os.environ.get("CONTENT_JSON", DEFAULT_CONTENT)
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    base = pages_base()
    urls = [base + "/" + img for img in c["images"]]
    caption = c["caption"]
    only = {p.strip() for p in os.environ.get("ONLY", "").split(",") if p.strip()}
    want = lambda n: not only or n in only

    log(f"發布輪播：{len(urls)} 張圖")
    log("等待圖片上線…")
    for u in urls:
        wait_until_live(u)
    log("  ✓ 全部圖片已上線")

    errors = []
    plan = [
        ("ig", "Instagram", lambda: post_instagram(urls, caption)),
        ("fb", "Facebook", lambda: post_facebook(urls, caption)),
        ("line", "LINE", lambda: post_line(urls, c.get("line_intro", ""))),
    ]
    for key, name, fn in plan:
        if not want(key):
            continue
        try:
            fn()
        except Exception as e:
            log(f"  ✗ {name} 失敗：{e}"); errors.append(name)

    if errors:
        log("=== 有平台失敗：" + "、".join(errors) + " ==="); sys.exit(1)
    log("全部完成 ✓")


if __name__ == "__main__":
    main()
