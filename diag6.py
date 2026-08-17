import urllib.request, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = urllib.request.urlopen("https://t.me/s/dny8837", timeout=30).read().decode("utf-8", "ignore")
print("HTML length:", len(html))
# 所有消息的 data-post
posts = re.findall(r'data-post="dny8837/(d+)"', html)
print("POSTS on page:", posts[:25])
# 检查 6667 和 6668 是否存在
for pid in ["6667", "6668"]:
    m = re.search(r'<div class="tgme_widget_message[^"]*" data-post="dny8837/' + pid + r'".*?(?=<div class="tgme_widget_message|$)', html, re.S)
    if m:
        block = m.group(1)
        print("===== #" + pid + " len:", len(block))
        vids = re.findall(r'<video[^>]*>', block)
        print("  videos:", len(vids))
        for v in vids[:3]: print("   ", v[:120])
        player = re.findall(r'video_player', block)
        print("  video_player:", len(player))
        txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', block, re.S)
        print("  text:", repr(re.sub(r"<[^>]+>", "", txt.group(1))[:60]) if txt else "NONE")
        classes = set(re.findall(r'class="([^"]*)"', block))
        print("  classes:", sorted(classes)[:10])
    else:
        print("===== #" + pid + " NOT ON PAGE")
