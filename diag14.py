import urllib.request, re, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 预览页已知消息（diag7 抓到）：6637,6639,6640,6642,6643,6644,6653,6655,6656,6657,6659,6660,6661,6662,6663,6664,6665,6666,6668
# 空隙 ID：6638,6641,6645-6652,6654,6658,6667
gaps = [6638, 6641] + list(range(6645, 6653)) + [6654, 6658, 6667]
for pid in gaps:
    url = f"https://t.me/dny8837/{pid}?embed=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        tm = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.S)
        text = re.sub(r"<[^>]+>", "", tm.group(1))[:60] if tm else ""
        vids = len(re.findall(r'<video[^>]*src="', html))
        photos = len(re.findall(r'photo_wrap', html))
        if text or vids or photos:
            print(f"#{pid} v={vids} ph={photos} text={text!r}")
        else:
            print(f"#{pid} EMPTY")
    except Exception as e:
        print(f"#{pid} ERROR {e}")
    time.sleep(1)
