#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：抓取 dny8837 预览页，分析最新消息的视频/标签结构，结果写回仓库"""
import re
import json
import os
import base64
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

html = fetch("https://t.me/s/dny8837")
out = []
out.append("PAGE SIZE: %d" % len(html))

msgs = re.findall(r'<div class="tgme_widget_message[^"]*" data-post="([^"]+)"', html)
out.append("POSTS: %s" % str(msgs[-15:]))

blocks = re.findall(r'(<div class="tgme_widget_message[^>]*data-post="([^"]+)"[^>]*>.*?</div>\s*</div>\s*</div>)', html, re.S)
out.append("BLOCKS: %d" % len(blocks))

for i, (block, post) in enumerate(blocks[-5:]):
    has_video = '<video' in block
    has_video_player = 'tgme_widget_message_video_player' in block
    has_photo = 'tgme_widget_message_photo_wrap' in block
    has_text = 'tgme_widget_message_text' in block
    text_not_supported = 'text_not_supported_wrap' in block
    tm = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
    text = re.sub(r'<[^>]+>', '', tm.group(1)).strip() if tm else ''
    vsrc = re.findall(r'<video[^>]*src="([^"]+)"', block)
    out.append("--- %s ---" % post)
    out.append("  video: %s (%d src) | player: %s | photo: %s | text: %s | not_supported: %s" % (
        has_video, len(vsrc), has_video_player, has_photo, has_text, text_not_supported))
    out.append("  text: %r" % text[:80])
    if vsrc:
        out.append("  vsrc[0]: %s" % vsrc[0][:100])

result = "\n".join(out)
print(result)

# 写回仓库
gh_token = os.environ.get("GITHUB_TOKEN", "")
if gh_token:
    try:
        # 获取当前文件 sha
        req = urllib.request.Request(
            "https://api.github.com/repos/long-888-long/tg-sync/contents/diag_result.txt",
            headers={"Authorization": "token " + gh_token, "User-Agent": "diag", "Accept": "application/vnd.github+json"})
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            sha = json.loads(resp.read().decode())["sha"]
        except Exception:
            sha = None
        body = json.dumps({
            "message": "diag result",
            "content": base64.b64encode(result.encode("utf-8")).decode(),
            "sha": sha
        }).encode("utf-8")
        req2 = urllib.request.Request(
            "https://api.github.com/repos/long-888-long/tg-sync/contents/diag_result.txt",
            data=body, method="PUT",
            headers={"Authorization": "token " + gh_token, "User-Agent": "diag",
                     "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
        resp2 = urllib.request.urlopen(req2, timeout=15)
        print("RESULT UPLOADED:", resp2.status)
    except Exception as e:
        print("UPLOAD FAILED:", e)