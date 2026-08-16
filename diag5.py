import urllib.request, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
def grab(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        vids = re.findall(r'<video[^>]*>', html)
        print(url)
        print("  len:", len(html), "videos:", len(vids))
        for v in vids[:3]:
            print("  ", v[:150])
        # 也找 og:video 或 twitter:player
        for m in re.findall(r'<meta property="(?:og:video|twitter:player:stream)" content="([^"]+)"', html)[:3]:
            print("  META:", m[:150])
        return html
    except Exception as e:
        print(url, "ERROR:", e)
        return None

# 1. 单条消息页
grab("https://t.me/dny8837/6655")
# 2. embed 页
grab("https://t.me/dny8837/6655?embed=1")
# 3. 带单参数的 embed
grab("https://t.me/dny8837/6655?single")
