import urllib.request, re, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = ""
for i in range(6):
    try:
        req = urllib.request.Request("https://t.me/s/dny8837", headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        if len(re.findall(r'data-post="dny8837/', html)) > 5:
            break
        time.sleep(4)
    except Exception as e:
        print("retry", i, e)
        time.sleep(4)
posts = re.findall(r'data-post="dny8837/(d+)"', html)
print("POSTS:", posts)
# 每条消息的 text + 媒体
for m in re.finditer(r'<div class="tgme_widget_message[^"]*" data-post="dny8837/(d+)"(.*?)(?=<div class="tgme_widget_message|$)', html, re.S):
    pid, body = m.group(1), m.group(2)
    txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', body, re.S)
    text = re.sub(r"<[^>]+>", "", txt.group(1))[:50] if txt else ""
    vids = len(re.findall(r'<video', body))
    player = len(re.findall(r'video_player', body))
    photo = len(re.findall(r'photo_wrap', body))
    print(f"#{pid} v={vids} p={player} ph={photo} text={text!r}")
