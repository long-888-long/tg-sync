#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：打印 #6668 embed 页 HTML 中所有 video/player/media 相关片段"""
import re
import json
import os
import base64
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

result = []
for pid in [6668, 6672]:
    url = "https://t.me/dny8837/{}?embed=1".format(pid)
    try:
        html = fetch(url)
        result.append("=== post #{} embed page size: {} ===".format(pid, len(html)))
        # 找所有 video/player/media 相关片段
        for m in re.finditer(r'.{0,80}(?:video|player|media|src=|data-src).{0,120}', html, re.I):
            snippet = m.group(0).replace('\n', ' ')
            result.append("  ...{}...".format(snippet[:220]))
        # 检查是否有 tgme_widget_message_video_player
        result.append("  has video_player class: {}".format('tgme_widget_message_video_player' in html))
        result.append("  has <video: {}".format('<video' in html))
        result.append("  has tgme_widget_message_photo_wrap: {}".format('tgme_widget_message_photo_wrap' in html))
        result.append("  has text_not_supported: {}".format('text_not_supported' in html))
    except Exception as e:
        result.append("post #{}: ERROR {}".format(pid, e))

out = "\n".join(result)
print(out)

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