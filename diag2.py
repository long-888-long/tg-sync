# -*- coding: utf-8 -*-
"""诊断2：云端真实跑 send_scraped 全链路（不实际发送），定位视频 caption 丢失环节"""
import os
import sys
import importlib.util

spec = importlib.util.spec_from_file_location("bot", "bot.py")
bot = importlib.util.module_from_spec(spec)
sys.modules["bot"] = bot
spec.loader.exec_module(bot)

# 配置
class Cfg:
    token = os.environ.get("BOT_TOKEN", "")
    llm_api_key = os.environ.get("LLM_API_KEY", "")
    llm_base_url = os.environ.get("LLM_BASE_URL", "https://cn2.llmhost.net/v1")
    llm_model = os.environ.get("LLM_MODEL", "deepseek-v4-flash")
    llm_timeout = 90
    ad_filter = True
    ad_keywords = []
    ad_llm = True
    rewrite = True
    rewrite_prompt = None
    wm_mode = "remove"
    wm_amount = 0.08
    wm_pos = "auto"
    source = ["@dny8837"]
    dest = ["@Pinwin_3"]
    state_file = "state.json"
    scrape_catchup = False
    replace_mentions = ""
    footer_remove = True

cfg = Cfg()

# 抓取 dny8837 预览页
print("=== 抓取 @dny8837 ===")
html = bot.fetch_page("dny8837")
msgs = bot.parse_messages(html)
print("解析消息数:", len(msgs))

# 找最新视频消息
video_msgs = [m for m in msgs if m.get("media") and m["media"]["type"] == "video"]
print("视频消息数:", len(video_msgs))
if not video_msgs:
    print("没有视频消息，退出")
    sys.exit(0)

# 取最新 3 条视频消息，完整跑 send_scraped 逻辑（不发送）
for m in sorted(video_msgs, key=lambda x: x["post_id"])[-3:]:
    print("\n" + "=" * 50)
    print("post:", m["post_id"], "| text:", repr(m["text"]))
    text = m.get("text") or ""
    # 1. 广告关键词
    hit = bot.contains_ad(text, []) if cfg.ad_filter else False
    print("步骤1 广告关键词:", "命中" if hit else "未命中")
    # 2. LLM 广告判断
    if cfg.ad_filter and cfg.ad_llm and not hit:
        j = bot.llm_judge_ad(text, cfg)
        print("步骤2 LLM广告判断:", j)
        if j is True:
            print(">>> 被 LLM 判定为广告，整条不搬！")
            continue
    # 3. strip_trace
    clean = bot.strip_trace(text, cfg)
    print("步骤3 strip_trace 后:", repr(clean))
    # 4. LLM 改写
    if cfg.rewrite and clean:
        clean2 = bot.llm_rewrite(clean, cfg)
        print("步骤4 LLM改写 后:", repr(clean2))
        clean = clean2
        clean = bot.strip_trace(clean, cfg)
        print("步骤4b 二次清洗:", repr(clean))
    # 5. caption
    caption = bot.build_caption(clean) if clean else None
    print("步骤5 caption:", repr(caption))
    print(">>> 结论:", "caption 正常" if caption else "caption 为空！标签会丢失！")
