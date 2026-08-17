import urllib.request, re, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = ""
for i in range(6):
    try:
        req = urllib.request.Request("https://t.me/s/dny8837", headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        if "tgme_widget_message" in html:
            break
        time.sleep(4)
    except Exception as e:
        print("retry", i, e)
        time.sleep(4)
print("HTML length:", len(html))
print("has tgme_widget_message:", "tgme_widget_message" in html)
print("has data-post:", "data-post" in html)
print("has text_not_supported:", "text_not_supported" in html)
print("has video tag:", "<video" in html)
# 打印页面开头 500 字符
print("HEAD:", html[:500].replace("\n", " "))
# 找所有 data-post 出现的位置
idxs = [m.start() for m in re.finditer(r'data-post="', html)]
print("data-post count:", len(idxs))
for i in idxs[:5]:
    print("  ctx:", html[i:i+80])
