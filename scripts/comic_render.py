#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
九宮格漫畫 — 渲染
讀 comic/_script.json（由對話中即時生成的劇本），套進 comic/template.html，
用 Playwright 渲染成 JPG，存到 posts/comic/<slug>.jpg，
並寫出 comic/_content.json（image_file / caption / threads_caption）供發布用。

_script.json 格式：
{
  "title_html": "誠毅<span class=\"accent\">小劇場</span>",
  "subtitle": "保險其實沒那麼複雜 · 用故事講給你聽",
  "ep": "01",
  "slug": "insurance-health",
  "panels": [
    {"num":1,"emoji":"💪","who":"阿明","line":"我超健康，<br>保險不用啦！"},
    ... 共 9 格，最後一格 {"num":9,"final":true,"emoji":"❤️","line":"健康時的準備","tag":"是給家人最好的愛"}
  ],
  "caption": "IG/FB 內文",
  "threads_caption": "Threads 精簡內文"
}
"""
import os, json, sys
from html import escape

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMIC_DIR = os.path.join(ROOT, "comic")
OUT_DIR = os.path.join(ROOT, "posts", "comic")
TEMPLATE = os.path.join(COMIC_DIR, "template.html")
SCRIPT_JSON = os.path.join(COMIC_DIR, "_script.json")
CONTENT_JSON = os.path.join(COMIC_DIR, "_content.json")


def panel_html(p):
    num = f'<div class="num">{escape(str(p["num"]))}</div>'
    emoji = f'<div class="emoji">{p.get("emoji","")}</div>'
    if p.get("final"):
        tag = f'<div class="tag">{p["tag"]}</div>' if p.get("tag") else ""
        return (f'<div class="panel final">{num}{emoji}'
                f'<div class="line">{p["line"]}</div>{tag}</div>')
    who = f'<span class="who">{p["who"]}：</span>' if p.get("who") else ""
    return (f'<div class="panel">{num}{emoji}'
            f'<div class="line">{who}{p["line"]}</div></div>')


def render(script):
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    grid = "\n    ".join(panel_html(p) for p in script["panels"])
    html = (html
            .replace("{{TITLE_HTML}}", script.get("title_html", "誠毅<span class=\"accent\">小劇場</span>"))
            .replace("{{SUBTITLE}}", script.get("subtitle", ""))
            .replace("{{EP}}", str(script.get("ep", "01")))
            .replace("{{GRID}}", grid))
    render_html = os.path.join(COMIC_DIR, "_render.html")
    with open(render_html, "w", encoding="utf-8") as f:
        f.write(html)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = script.get("slug", "comic")
    out_path = os.path.join(OUT_DIR, f"{slug}.jpg")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(device_scale_factor=2).new_page()
        page.goto("file://" + render_html.replace("\\", "/"))
        page.wait_for_timeout(2500)
        page.query_selector(".card").screenshot(path=out_path, type="jpeg", quality=92)
        browser.close()
    try:
        os.remove(render_html)
    except OSError:
        pass
    return out_path, slug


def main():
    with open(SCRIPT_JSON, encoding="utf-8") as f:
        script = json.load(f)
    if len(script.get("panels", [])) != 9:
        print(f"⚠️ 需要正好 9 格，目前 {len(script.get('panels', []))} 格")
        sys.exit(1)
    out_path, slug = render(script)
    size_kb = os.path.getsize(out_path) // 1024
    print(f"✓ 漫畫已渲染：posts/comic/{slug}.jpg（{size_kb} KB）")

    content = {
        "image_file": f"posts/comic/{slug}.jpg",
        "caption": script.get("caption", ""),
        "threads_caption": script.get("threads_caption", script.get("caption", "")),
    }
    with open(CONTENT_JSON, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    print("✓ 文案已寫入 comic/_content.json")


if __name__ == "__main__":
    main()
