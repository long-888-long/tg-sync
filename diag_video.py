#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：抓取 dny8837 预览页，分析最新消息的视频/标签结构"""
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

html = fetch("https://t.me/s/dny8837")
print("PAGE SIZE:", len(html))

# 提取所有消息块
msgs = re.findall(r'<div class="tgme_widget_message[^"]*" data-post="([^"]+)"', html)
print("POSTS:", msgs[-15:])

# 找最新几条消息的完整块
blocks = re.findall(r'(<div class="tgme_widget_message[^>]*data-post="([^"]+)"[^>]*>.*?</div>\s*</div>\s*</div>)', html, re.S)
print("BLOCKS:", len(blocks))

# 对最后 5 个块分析结构
for i, (block, post) in enumerate(blocks[-5:]):
    has_video = '<video' in block
    has_video_player = 'tgme_widget_message_video_player' in block
    has_photo = 'tgme_widget_message_photo_wrap' in block
    has_text = 'tgme_widget_message_text' in block
    text_not_supported = 'text_not_supported_wrap' in block
    # 提取文字
    tm = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
    text = re.sub(r'<[^>]+>', '', tm.group(1)).strip() if tm else ''
    # 提取视频 src
    vsrc = re.findall(r'<video[^>]*src="([^"]+)"', block)
    print(f"--- {post} ---")
    print(f"  video: {has_video} ({len(vsrc)} src) | video_player: {has_video_player} | photo: {has_photo} | text: {has_text} | not_supported: {text_not_supported}")
    print(f"  text: {text[:80]!r}")
    if vsrc:
        print(f"  vsrc[0]: {vsrc[0][:100]}")