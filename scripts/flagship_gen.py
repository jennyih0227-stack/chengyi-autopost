#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旗艦插畫 — 用 Gemini 生插畫（不含文字）→ 疊上乾淨中文字 → 輸出成品。
讀 flagship/_spec.json：
{
  "slug": "recruit",
  "art_prompt": "英文的插畫描述，務必要求 no text/no words/no letters",
  "title_html": "一個人走得快<br><span class=\"hl\">一群人走得遠</span>",
  "message": "一句補充訊息"
}

需要環境變數：GEMINI_KEY
"""
import os, sys, json, base64
import urllib.request, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FDIR = os.path.join(ROOT, "flagship")
OUT_DIR = os.path.join(ROOT, "posts", "flagship")
SPEC = os.path.join(FDIR, "_spec.json")
TEMPLATE = os.path.join(FDIR, "template.html")
ART = os.path.join(FDIR, "_art.png")

# 依序嘗試的生圖模型（不同帳號可用的可能不同）
IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp-image-generation",
]


def gen_image(prompt, key):
    last_err = None
    for model in IMAGE_MODELS:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={key}")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode(errors="ignore")
            except Exception:
                pass
            last_err = f"[{model}] HTTP {e.code} — {body[:400]}"
            print("  嘗試失敗：" + last_err)
            continue
        except Exception as e:
            last_err = f"[{model}] {e}"
            print("  嘗試失敗：" + last_err)
            continue
        # 從回應取出圖片
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    print(f"  ✓ 生圖成功（模型：{model}）")
                    return base64.b64decode(inline["data"])
        last_err = f"[{model}] 回應中沒有圖片：{json.dumps(data)[:400]}"
        print("  無圖片：" + last_err)
    raise RuntimeError("所有生圖模型都失敗。最後錯誤：" + str(last_err))


def compose(spec):
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    html = (html
            .replace("{{TITLE_HTML}}", spec.get("title_html", ""))
            .replace("{{MESSAGE}}", spec.get("message", "")))
    render_html = os.path.join(FDIR, "_render.html")
    with open(render_html, "w", encoding="utf-8") as f:
        f.write(html)
    os.makedirs(OUT_DIR, exist_ok=True)
    slug = spec.get("slug", "flagship")
    out = os.path.join(OUT_DIR, f"{slug}.jpg")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(device_scale_factor=2).new_page()
        pg.goto("file://" + render_html.replace("\\", "/"))
        pg.wait_for_timeout(2500)
        pg.query_selector(".card").screenshot(path=out, type="jpeg", quality=92)
        b.close()
    for f in (render_html, ART):
        try:
            os.remove(f)
        except OSError:
            pass
    return out


def main():
    key = os.environ.get("GEMINI_KEY")
    if not key:
        print("✗ 缺 GEMINI_KEY"); sys.exit(1)
    with open(SPEC, encoding="utf-8") as f:
        spec = json.load(f)
    print(f"生成插畫：{spec.get('slug')}")
    img = gen_image(spec["art_prompt"], key)
    with open(ART, "wb") as f:
        f.write(img)
    print(f"  插畫暫存：{len(img)//1024} KB")
    out = compose(spec)
    print(f"✓ 旗艦成品：posts/flagship/{os.path.basename(out)}（{os.path.getsize(out)//1024} KB）")


if __name__ == "__main__":
    main()
