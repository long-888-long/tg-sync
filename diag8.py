import urllib.request, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
def grab(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        vids = re.findall(r'<video[^>]*>', html)
        print(url, "| len:", len(html), "| videos:", len(vids))
        for v in vids[:3]: print("   ", v[:130])
        # photo
        photos = re.findall(r'photo_wrap[^>]*style="[^"]*url\([\'"]?([^\'")]+)', html)
        print("   photos:", len(photos))
        return html
    except Exception as e:
        print(url, "ERROR:", e)
        return None

# 验证 #6668 的 embed 页（bot 搬运的那条）
grab("https://t.me/dny8837/6668?embed=1")
# 验证 #6667 的 embed 页（预览页没有的那条）
grab("https://t.me/dny8837/6667?embed=1")
