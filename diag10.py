import urllib.request, re, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = ""
for i in range(5):
    try:
        req = urllib.request.Request("https://t.me/s/dny8837", headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        if len(re.findall(r'data-post="dny8837/', html)) > 5:
            break
        time.sleep(3)
    except Exception as e:
        print("retry", i, e)
        time.sleep(3)
print("HTML length:", len(html))
posts = re.findall(r'data-post="dny8837/(d+)"', html)
print("POSTS:", posts)
# 找"老婆"相关消息
for m in re.finditer(r'<div class="tgme_widget_message[^"]*" data-post="dny8837/(d+)"(.*?)(?=<div class="tgme_widget_message|$)', html, re.S):
    pid, body = m.group(1), m.group(2)
    txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', body, re.S)
    text = re.sub(r"<[^>]+>", "", txt.group(1))[:80] if txt else ""
    if "老婆" in text or "勾引" in text or "大白" in text:
        print("===== FOUND #" + pid, "text:", repr(text))
        vids = re.findall(r'<video[^>]*>', body)
        print("  videos:", len(vids))
        for v in vids[:3]: print("   ", v[:150])
        print("  video_player:", len(re.findall(r'video_player', body)))
        print("  photo_wrap:", len(re.findall(r'photo_wrap', body)))
        print("  classes:", sorted(set(re.findall(r'class="([^"]*)"', body)))[:12])
