#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地測試工具 — 推上 GitHub 前先在自己電腦驗證金鑰是否正確。
用法：
  1. 複製 .env.example 為 .env，填入你的金鑰
  2. python scripts/test_local.py tg     # 只測 Telegram
  3. python scripts/test_local.py all 5  # 測全部平台，發第 5 則
"""
import os, sys

# 讀取 .env（簡易版，不需額外套件）
def load_env():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post as P

def main():
    platform = sys.argv[1] if len(sys.argv) > 1 else "tg"
    pid = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    posts = P.load_posts()
    p = posts[pid]
    print(f"測試發布第 {pid} 則：{p['title']}")
    targets = ["tg", "fb", "ig"] if platform == "all" else [platform]
    for t in targets:
        try:
            P.PLATFORMS[t](p)
        except Exception as e:
            print(f"  ✗ {P.NAMES[t]} 失敗：{e}")

if __name__ == "__main__":
    main()
