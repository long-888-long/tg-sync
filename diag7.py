import urllib.request, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = urllib.request.urlopen("https://t.me/s/dny8837", timeout=30).read().decode("utf-8", "ignore")
print("HTML length:", len(html))
# 所有 data-post（宽松匹配）
posts = re.findall(r'data-post="([^"]+)"', html)
print("POSTS:", posts[:30])
# 所有 video 标签数量
print("VIDEO TAGS:", len(re.findall(r'<video', html)))
# 找 6667/6668 的痕迹
for pid in ["6667", "6668"]:
    found = pid in html
    print("#" + pid, "in html:", found)
    if found:
        idx = html.find(pid)
        print("  context:", html[max(0,idx-100):idx+200].replace("\n", " ")[:300])
