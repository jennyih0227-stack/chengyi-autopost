#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日哲學 — 生成 + 渲染
1. 用 Gemini 生成今日哲學（小故事 / 人生哲學 / 今日啟示）
2. 套進 philosophy/template.html，用 Playwright 渲染成 JPG
3. 圖片存到 posts/daily/<date>.jpg（之後由 workflow commit 上 GitHub Pages 當圖床）
4. 文案內容寫到 philosophy/_content.json（同一個 job 內傳給發文腳本，不會 commit）

需要的環境變數：
  GEMINI_KEY        Gemini API 金鑰
  OVERRIDE_DATE     （選填）強制指定日期 YYYY-MM-DD，留空用今天
"""
import os, json, re, time
from datetime import date, timezone, timedelta
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHIL_DIR = os.path.join(ROOT, "philosophy")
DAILY_DIR = os.path.join(ROOT, "posts", "daily")
TEMPLATE = os.path.join(PHIL_DIR, "template.html")
CONTENT_JSON = os.path.join(PHIL_DIR, "_content.json")

GEMINI_MODEL = "gemini-2.5-flash"

PROMPT = """請生成今日的人生哲學內容,繁體中文,台灣用語,格式如下:

【今日小故事】
(一則約150字的生活哲學小故事)

【人生哲學】
(一句凝練的人生哲學,約20字,最多不超過28字)

【今日啟示】
(一句可實踐的人生啟示,約15字)

請直接輸出內容,不要加任何前言。"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def taiwan_today():
    return os.environ.get("OVERRIDE_DATE") or \
        datetime_now_tw().date().isoformat()


def datetime_now_tw():
    from datetime import datetime
    return datetime.now(timezone(timedelta(hours=8)))


def gen_text():
    key = os.environ["GEMINI_KEY"]
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={key}")
    data = json.dumps({"contents": [{"parts": [{"text": PROMPT}]}]}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    if "candidates" not in resp:
        raise RuntimeError(f"Gemini 沒正常回傳：{resp}")
    return resp["candidates"][0]["content"]["parts"][0]["text"]


def parse_sections(text):
    """把三段內容拆出來。找不到就盡量降級處理。"""
    def grab(label, nexts):
        # 抓 【label】 到 下一個 【 或 結尾
        m = re.search(r"【" + label + r"】\s*(.*?)(?=【|$)", text, re.S)
        return m.group(1).strip() if m else ""

    story = grab("今日小故事", None)
    quote = grab("人生哲學", None)
    revelation = grab("今日啟示", None)
    # 清掉可能殘留的括號說明與多餘空行
    for junk in ("(", "（"):
        pass
    story = re.sub(r"\s*\n\s*", "", story).strip()
    quote = quote.strip().strip("「」\"")
    revelation = revelation.strip().strip("「」\"")
    if not (story and quote and revelation):
        raise RuntimeError(f"內容解析失敗，原文：\n{text}")
    return story, quote, revelation


def quote_to_html(quote):
    """在中文逗號後換行，讓金句排版好看；避免尾端空行。"""
    q = quote.replace("，", "，<br>")
    # 若結尾多一個 <br> 去掉
    q = re.sub(r"<br>\s*$", "", q)
    return q


def render_card(the_date, quote, revelation, out_path):
    from playwright.sync_api import sync_playwright
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    html = (html
            .replace("{{DATE}}", the_date.replace("-", "."))
            .replace("{{QUOTE_HTML}}", quote_to_html(quote))
            .replace("{{REVELATION}}", revelation))
    render_html = os.path.join(PHIL_DIR, "_render.html")
    with open(render_html, "w", encoding="utf-8") as f:
        f.write(html)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(device_scale_factor=2).new_page()
        page.goto("file://" + render_html.replace("\\", "/"))
        page.wait_for_timeout(2800)  # 等 Google Fonts 載入
        card = page.query_selector(".card")
        card.screenshot(path=out_path, type="jpeg", quality=92)
        browser.close()
    try:
        os.remove(render_html)
    except OSError:
        pass


def main():
    os.makedirs(DAILY_DIR, exist_ok=True)
    today = taiwan_today()
    log(f"生成 {today} 的每日哲學…")

    raw = gen_text()
    story, quote, revelation = parse_sections(raw)
    log(f"  金句：{quote}")
    log(f"  啟示：{revelation}")

    img_name = f"{today}.jpg"
    out_path = os.path.join(DAILY_DIR, img_name)
    render_card(today, quote, revelation, out_path)
    size_kb = os.path.getsize(out_path) // 1024
    log(f"  ✓ 卡片已渲染：posts/daily/{img_name}（{size_kb} KB）")

    content = {
        "date": today,
        "story": story,
        "quote": quote,
        "revelation": revelation,
        "image_file": f"posts/daily/{img_name}",
    }
    with open(CONTENT_JSON, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    log(f"  ✓ 文案已寫入 philosophy/_content.json")


if __name__ == "__main__":
    main()
