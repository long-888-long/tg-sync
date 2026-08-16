# -*- coding: utf-8 -*-
"""临时诊断：分析预览页视频消息的文字结构"""
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except Exception:
    HAS_BS4 = False

def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else "dny8837"
    print("=== 诊断频道: @" + channel + " ===")
    html = fetch("https://t.me/s/" + channel)
    print("页面大小:", len(html))

    if not HAS_BS4:
        print("无 bs4，用正则分析")
        # 找 video 消息块
        blocks = re.findall(r'<div class="tgme_widget_message" data-post="([^"]+)".*?</div>\s*</div>\s*</div>', html, re.S)
        print("消息块数:", len(blocks))
        # 简单统计
        print("video 元素数:", len(re.findall(r'tgme_widget_message_video', html)))
        print("text div 数:", len(re.findall(r'tgme_widget_message_text', html)))
        return

    soup = BeautifulSoup(html, "html.parser")
    msgs = soup.select("div.tgme_widget_message")
    print("消息总数:", len(msgs))
    video_count = 0
    for m in msgs:
        post = m.get("data-post", "?")
        video = m.select_one("video.tgme_widget_message_video")
        if not video:
            continue
        video_count += 1
        has_src = bool(video.get("src"))
        t = m.select_one("div.tgme_widget_message_text")
        text = t.get_text(" ", strip=True) if t else ""
        print("---")
        print("post:", post, "| video有src:", has_src)
        print("text div 存在:", t is not None, "| text内容:", repr(text[:80]))
        # 检查文字在哪个容器
        if not t:
            # 找所有可能的文字容器
            for sel in ["div.tgme_widget_message_text",
                        "div.js-message_text",
                        "div.tgme_widget_message_caption",
                        "span.tgme_widget_message_caption"]:
                el = m.select_one(sel)
                if el:
                    print("  找到", sel, ":", repr(el.get_text(" ", strip=True)[:80]))
    print("\n含 video 的消息数:", video_count)

if __name__ == "__main__":
    main()
