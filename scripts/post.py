#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
誠毅傳承 — 三平台自動發文腳本
讀取 schedule.csv，找出「今天」該發的貼文，發布到 Telegram / Facebook / Instagram。

所有密鑰透過環境變數（GitHub Secrets）注入，不寫死在程式裡。
需要的環境變數：
  TG_BOT_TOKEN, TG_CHAT_ID
  FB_PAGE_ID, FB_PAGE_TOKEN
  IG_USER_ID, IG_IMAGE_BASE_URL   (IG 需要圖片公開網址)
"""
import os, csv, json, sys, time
from datetime import date
import urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(ROOT, "posts")
IMG_DIR = os.path.join(POSTS_DIR, "images")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def load_posts():
    with open(os.path.join(POSTS_DIR, "posts.json"), encoding="utf-8") as f:
        return {p["id"]: p for p in json.load(f)}

def todays_jobs():
    today = os.environ.get("OVERRIDE_DATE") or date.today().isoformat()
    jobs = []
    with open(os.path.join(POSTS_DIR, "schedule.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["date"].strip() == today:
                jobs.append(row)
    return today, jobs

# ---------- Telegram ----------
def post_telegram(post):
    token = os.environ["TG_BOT_TOKEN"]
    chat_id = os.environ["TG_CHAT_ID"]
    img = os.path.join(IMG_DIR, post["image_square"])
    caption = post["tg_caption"]
    # 用 multipart 上傳圖片 + 文字（sendPhoto，caption 上限 1024 字，足夠）
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    boundary = "----cyboundary"
    parts = []
    def field(name, value):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    field("chat_id", chat_id)
    field("caption", caption)
    field("parse_mode", "HTML")
    with open(img, "rb") as fp:
        imgdata = fp.read()
    parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; "
                  f"filename=\"{post['image_square']}\"\r\nContent-Type: image/jpeg\r\n\r\n").encode())
    parts.append(imgdata)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.load(r)
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram 失敗: {resp}")
    log("  ✓ Telegram 發布成功")

# ---------- Facebook 粉專 ----------
def post_facebook(post):
    page_id = os.environ["FB_PAGE_ID"]
    token = os.environ["FB_PAGE_TOKEN"]
    img = os.path.join(IMG_DIR, post["image_fb"])
    caption = post["fb_caption"]
    # FB 用 /photos 端點：直接上傳圖片 + 文字
    url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
    boundary = "----cyboundary"
    parts = []
    def field(name, value):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    field("caption", caption)
    field("access_token", token)
    with open(img, "rb") as fp:
        imgdata = fp.read()
    parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"source\"; "
                  f"filename=\"{post['image_fb']}\"\r\nContent-Type: image/jpeg\r\n\r\n").encode())
    parts.append(imgdata)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    if "id" not in resp and "post_id" not in resp:
        raise RuntimeError(f"Facebook 失敗: {resp}")
    log("  ✓ Facebook 發布成功")

# ---------- Instagram ----------
def post_instagram(post):
    ig_user = os.environ["IG_USER_ID"]
    token = os.environ["FB_PAGE_TOKEN"]  # IG 用同一組 Page Token
    base = os.environ["IG_IMAGE_BASE_URL"].rstrip("/")
    image_url = f"{base}/{urllib.parse.quote(post['image_square'])}"
    caption = post["ig_caption"]
    # 步驟1：建立 media container
    create = f"https://graph.facebook.com/v21.0/{ig_user}/media"
    data = urllib.parse.urlencode({
        "image_url": image_url, "caption": caption, "access_token": token
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(create, data=data), timeout=120) as r:
        resp = json.load(r)
    container = resp.get("id")
    if not container:
        raise RuntimeError(f"IG 建立容器失敗: {resp}")
    time.sleep(5)  # 等 IG 處理圖片
    # 步驟2：發布
    publish = f"https://graph.facebook.com/v21.0/{ig_user}/media_publish"
    data2 = urllib.parse.urlencode({
        "creation_id": container, "access_token": token
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(publish, data=data2), timeout=120) as r:
        resp2 = json.load(r)
    if "id" not in resp2:
        raise RuntimeError(f"IG 發布失敗: {resp2}")
    log("  ✓ Instagram 發布成功")

PLATFORMS = {"tg": post_telegram, "fb": post_facebook, "ig": post_instagram}
NAMES = {"tg": "Telegram", "fb": "Facebook", "ig": "Instagram"}

def main():
    posts = load_posts()
    today, jobs = todays_jobs()
    if not jobs:
        log(f"今天 {today} 沒有排定的貼文，結束。")
        return
    errors = []
    for job in jobs:
        pid = int(job["post_id"])
        post = posts.get(pid)
        if not post:
            log(f"找不到貼文 id={pid}，略過")
            continue
        log(f"發布第 {pid} 則：{post['title']}")
        for key, fn in PLATFORMS.items():
            if job.get(key, "").strip().upper() == "Y":
                try:
                    fn(post)
                except Exception as e:
                    msg = f"  ✗ {NAMES[key]} 失敗：{e}"
                    log(msg)
                    errors.append(msg)
    if errors:
        log("=== 有錯誤發生 ===")
        for e in errors: log(e)
        sys.exit(1)
    log("全部完成 ✓")

if __name__ == "__main__":
    main()
