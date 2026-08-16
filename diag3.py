import urllib.request, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = urllib.request.urlopen("https://t.me/s/dny8837", timeout=30).read().decode("utf-8", "ignore")
print("HTML length:", len(html))
# 所有 video 标签
vids = re.findall(r"<video[^>]*>", html)
print("VIDEO TAGS:", len(vids))
for v in vids[:6]:
    print("  ", v[:300])
# 所有 video_player 链接
players = re.findall(r'<a class="tgme_widget_message_video_player"[^>]*>', html)
print("VIDEO_PLAYER LINKS:", len(players))
for p in players[:6]:
    print("  ", p[:300])
# photo wrap
photos = re.findall(r'<a class="tgme_widget_message_photo_wrap"[^>]*>', html)
print("PHOTO WRAPS:", len(photos))
for p in photos[:3]:
    print("  ", p[:200])
# 找一条视频消息的完整 HTML（含 data-post）
msgs = re.findall(r'<div class="tgme_widget_message[^"]*" data-post="([^"]+)"[^>]*>(.*?)</div>s*</div>', html, re.S)
print("MESSAGES:", len(msgs))
for pid, body in msgs[:8]:
    has_video = "<video" in body
    has_player = "video_player" in body
    has_photo = "photo_wrap" in body
    has_doc = "document" in body
    txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', body, re.S)
    text = re.sub(r"<[^>]+>", "", txt.group(1))[:60] if txt else ""
    print(f"  #{pid} video={has_video} player={has_player} photo={has_photo} doc={has_doc} text={text!r}")
