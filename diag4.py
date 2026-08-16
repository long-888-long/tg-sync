import urllib.request, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = urllib.request.urlopen("https://t.me/s/dny8837", timeout=30).read().decode("utf-8", "ignore")
# 提取完整消息块
for pid in ["6655", "6637"]:
    m = re.search(r'(<div class="tgme_widget_message[^"]*" data-post="dny8837/' + pid + r'".*?)(?=<div class="tgme_widget_message|$)', html, re.S)
    if m:
        block = m.group(1)
        print("===== #" + pid + " HTML length:", len(block))
        # 打印 video 相关标签
        for v in re.findall(r'<video[^>]*>', block):
            print("VIDEO TAG:", v[:200])
        # 打印 video_player 链接
        for p in re.findall(r'<a class="tgme_widget_message_video_player"[^>]*>', block):
            print("PLAYER LINK:", p[:200])
        # 打印 text div
        t = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', block, re.S)
        if t:
            print("TEXT DIV:", re.sub(r"<[^>]+>", "", t.group(1))[:100])
        # 打印所有 class 名
        classes = set(re.findall(r'class="([^"]*)"', block))
        print("CLASSES:", sorted(classes))
    else:
        print("===== #" + pid + " NOT FOUND")
