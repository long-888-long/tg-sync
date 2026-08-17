#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证修复后的三层提取逻辑：抓 #6668 和 #6672 的 embed 页，确认能提取到视频"""
import re
import json
import os
import base64
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

def extract_media(html):
    """模拟修复后的三层提取"""
    out = []
    for m in re.finditer(r'<video[^>]*src="([^"]+)"', html):
        out.append({"type": "video", "url": m.group(1)})
    for m in re.finditer(r'<video[^>]*data-src="([^"]+)"', html):
        if not any(x["url"] == m.group(1) for x in out):
            out.append({"type": "video", "url": m.group(1)})
    for m in re.finditer(r'<a class="tgme_widget_message_video_player"[^>]*href="([^"]+)"', html):
        href = m.group(1)
        if not any(x["url"] == href for x in out):
            out.append({"type": "video", "url": href})
    return out

result = []
for pid in [6668, 6672]:
    url = "https://t.me/dny8837/{}?embed=1".format(pid)
    try:
        html = fetch(url)
        media = extract_media(html)
        result.append("post #{}: {} media extracted".format(pid, len(media)))
        for m in media:
            result.append("  {}: {}".format(m["type"], m["url"][:90]))
        # 也检查文字
        tm = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.S)
        if tm:
            text = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
            result.append("  text: {}".format(text[:60]))
    except Exception as e:
        result.append("post #{}: ERROR {}".format(pid, e))

out = "\n".join(result)
print(out)

# 写回仓库
gh_token = os.environ.get("GITHUB_TOKEN", "")
if gh_token:
    try:
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
            "content": base64.b64encode(out.encode("utf-8")).decode(),
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