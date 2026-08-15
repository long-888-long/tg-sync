# -*- coding: utf-8 -*-
"""
自动更新引流关键词库 (update_keywords.py)
=========================================
每周由 GitHub Actions 自动运行：
1. 调用 DeepSeek LLM 生成最新的引流/广告关键词、引流话术模式、AFF 跟踪参数
2. 与现有 keywords.json 合并去重
3. 自动跑「安全测试」：普通链接 / 入群链接 / 正常通知 / 正常新闻 必须 0 误杀；
   广告样本必须全部命中。测试不通过则放弃本次更新（保护线上规则）。
4. 通过后输出新 keywords.json（workflow 会提交回仓库并触发 bot 重新部署）

安全设计（防止误杀正常链接）：
- 白名单 whitelist：命中白名单词的消息直接放行
- 链接判定与关键词判定分离：普通 t.me 链接（无参数）永远不算广告
- 新词必须先过测试集才能入库
"""
import json
import os
import re
import sys
import time
import urllib.request

# ---------------- 内置测试集（安全护栏） ----------------
# (名称, 文本, 预期: True=广告/引流应过滤, False=正常应放行)
SAFE_TESTS = [
    ("普通tme链接", "资源在 https://t.me/hshsjk9", False),
    ("入群链接-公开群", "欢迎加入讨论 https://t.me/joinchat/AbCdEf", False),
    ("入群链接-公开频道", "更多内容 https://t.me/mychannel", False),
    ("正常通知", "影视可以更新了，这是海豚群\nhttps://t.me/hshsjk9", False),
    ("正常新闻", "三星用 Claude Code 提速芯片设计，数周工作缩至数天仍需复核", False),
    ("正常分享", "分享一个好看的电影，资源在 t.me/hshsjk9", False),
    ("技术文章", "Python 3.13 发布了，新增了这些特性，详见官方文档", False),
    ("普通域名链接", "新闻 https://github.com/long-888-long/tg-sync", False),
    ("正常群公告", "【公告】本群每周三晚8点直播，欢迎准时参加", False),
]

AD_TESTS = [
    ("aff-tme-start", "资源下载 https://t.me/hshsjk9?start=aff_123", True),
    ("aff-tme-ref", "看这里 t.me/abc?ref=xyz", True),
    ("aff-普通域名", "详情 https://example.com/?ref=abc123", True),
    ("私有邀请链接", "进群 https://t.me/+AbCdEf123", True),
    ("加群引导", "点我加群领取福利", True),
    ("私聊引导", "想了解私聊我", True),
    ("注册送红包", "现在注册即送5元红包", True),
    ("博彩宣传", "稳赚不赔，日入过万，加群咨询", True),
    ("贷款广告", "无抵押贷款，秒到账，加微信办理", True),
    ("宣传文案", "海豚py研究院，接口完全免费，请勿上当受骗", True),
]

# 内置基础关键词（与 bot.py 对齐，用于生成时的去重参考）
BASE_KEYWORDS = [
    "广告", "推广", "特价", "秒杀", "返利", "代购", "贷款", "借款", "博彩", "赌博",
    "加微信", "加v", "扫码", "二维码", "转账", "红包", "优惠券", "满减", "包邮",
    "代理", "加盟", "兼职", "刷单", "招代理", "私聊我", "点击链接", "点击下方",
    "限时", "抢购", "拼团", "团购", "直销", "传销", "荐股", "炒股群", "稳赚",
    "日入", "月入", "躺赚", "零风险", "高收益", "稳赚不赔", "刷流水", "跑分",
    "完全免费", "免费接口", "免费开放", "永久免费", "限免", "白嫖", "免费领取", "免费体验",
    "上当受骗", "勿上当", "谨防受骗", "别被骗", "官方认证", "官方唯一", "正规平台",
    "强烈推荐", "推荐大家", "欢迎使用", "欢迎体验", "快来", "速来", "别错过", "错过可惜",
]

BASE_HIDDEN = [
    r"点我(?:加|进|入)?群", r"私[聊信]我", r"加(?:我|V|v|VX|薇|微信|QQ)",
    r"扫(?:码)?(?:加|进|入)?群", r"点击?(?:下方|链接|这里|上面)?(?:的)?(?:链接|按钮|查看|进群)",
    r"(?:主页|简介|签名|置顶|评论区|个人资料|频道)(?:里|中|有|查看|看|见)",
    r"(?:进|加)群(?:领|看|获取|福利|红包)", r"[Vv](?:我|信)|扣我|戳我|找我|私我",
    r"联系我", r"群(?:号|链接|二维码|入口)", r"拉(?:你|我)?进群",
    r"(?:通过|使用|输入|填写)(?:我|本人|本群|本频道)?的?(?:链接|邀请|邀请码|邀请链接)",
    r"(?:输入|填写|使用|复制)邀请码", r"注册(?:即|就|立)?(?:送|返|立减|得|领取)",
    r"邀请码[:：]?[A-Za-z0-9_-]{3,}", r"点击(?:注册|申请|领取|参与)",
    r"(?:关注|订阅)(?:我|本|我们|频道)?(?:后|即可|领取|获取)",
]

BASE_AFF_PARAMS = ["start", "startapp", "aff", "ref", "code", "invite", "rid", "uid", "promo",
                   "from", "source", "clickid", "subid", "siteid", "pid", "mid", "sid", "tag",
                   "chl", "share_ref", "utm_source", "utm_medium", "utm_campaign", "utm_content",
                   "aff_sub", "aff_id", "affcode", "refcode", "invite_code", "invitecode"]

# 白名单：命中这些词的消息跳过关键词判定（防止误杀正常内容）。
# 注意：不能包含可能出现在广告里的词（如"加群""进群""免费"），
# 因为广告消息也可能含这些词。这里只放"正常内容专属"的安全词。
BASE_WHITELIST = [
    "群公告", "群规", "群管理", "入群链接", "群文件", "群相册",
    "欢迎加入", "本群", "讨论区", "交流区", "资源分享", "分享资源",
    "技术分享", "学习资料", "开源项目", "官方文档", "使用教程", "安装教程",
    "新闻速递", "每日更新", "周报", "月报", "更新日志", "版本发布",
]


def load_existing(path="keywords.json"):
    """加载现有词库（不存在则返回空结构）"""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"ad_keywords": [], "hidden_link_patterns": [], "aff_params": [], "whitelist": []}


def _extract_json(text):
    """鲁棒 JSON 提取：整个是 JSON → 正则 → raw_decode 扫描。失败返回 None。"""
    if not text:
        return None
    t = text.strip()
    # 去掉可能的代码块包裹
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.S)
    t = re.sub(r"\s*```$", "", t, flags=re.S)
    # 1. 整体尝试
    try:
        return json.loads(t)
    except Exception:
        pass
    # 2. 贪婪正则 { ... }
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # 3. raw_decode 扫描（找第一个合法 JSON 对象）
    dec = json.JSONDecoder()
    for i in range(len(t)):
        if t[i] == "{":
            try:
                obj, _ = dec.raw_decode(t[i:])
                return obj
            except Exception:
                continue
    return None


def llm_generate(llm_api_key, base_url, model):
    """调用 DeepSeek 生成新的引流关键词/话术/AFF参数。返回 dict 或 None。"""
    prompt = (
        "你是中文网络内容安全专家。请根据最新的引流/广告手段，生成一份「Telegram 频道引流广告识别词库」。\n"
        "要求：\n"
        "1. ad_keywords：50-80 个最新中文广告/引流关键词（免费诱惑、博彩、贷款、刷单、返利、加群引流、"
        "私聊引流、邀请注册、代购、VPN、影视资源收费等），每个 2-8 字，不要与下面示例重复。\n"
        "2. hidden_link_patterns：15-25 条最新「汉字隐藏链接」引流话术正则（引导加群/私聊/看主页/注册），"
        "用 Python 正则风格，如 r'私信我领取'、r'主页(?:有|见|看)'。不要包含纯词如'入群''进群'这类正常词。\n"
        "3. aff_params：10-20 个最新 AFF/跟踪链接参数名（如 share_id、affcode、channel_code 等），纯英文小写。\n"
        "4. whitelist：10-20 个正常词（入群/进群/群规/公告/通知/分享/资源/直播/新闻/教程/文档/开源/更新等），"
        "防止误杀正常内容。\n"
        "只输出 JSON，格式：{\"ad_keywords\": [...], \"hidden_link_patterns\": [...], \"aff_params\": [...], \"whitelist\": [...]}。"
        "不要输出任何其他文字。"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 8000,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + llm_api_key}
    url = base_url.rstrip("/") + "/chat/completions"
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            # 推理模型兼容：content 为空时从 reasoning_content 提取
            if not content:
                content = (msg.get("reasoning_content") or "").strip()
            # 鲁棒 JSON 提取：整个是 JSON → 正则 → 扫描式 raw_decode
            parsed = _extract_json(content)
            if parsed is not None:
                return parsed
            last_err = "no valid JSON in response"
        except Exception as e:
            last_err = str(e)
        if attempt < 2:
            print("LLM attempt %d failed (%s), retrying..." % (attempt + 1, last_err))
    print("LLM generate failed:", last_err)
    return None


def merge(dst, src_list, max_len=300):
    """合并去重（保序）"""
    out = []
    seen = set()
    for item in list(dst) + list(src_list or []):
        item = str(item).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out[:max_len]


def safe_check(keywords, hidden, aff_params, whitelist):
    """安全测试：正常样本必须 0 误杀，广告样本必须全命中。返回 (通过, 失败详情) """
    fails = []

    def is_ad(text):
        low = text.lower()
        # 1. 汉字隐藏链接/引流话术
        for p in list(BASE_HIDDEN) + list(hidden):
            try:
                if re.search(p, text):
                    return True
            except Exception:
                continue
        # 2. t.me 带跟踪参数
        for m in re.finditer(r"(?:https?://)?(?:t\.me|telegram\.me)/[^\s?#]+\?[^\s]+", text):
            qs = re.split(r"[&;]", m.group(0).split("?", 1)[1])
            for p in qs:
                k = p.split("=")[0].strip().lower()
                if k in list(BASE_AFF_PARAMS) + list(aff_params) or "aff" in k or "ref" in k:
                    return True
        # 3. 私有邀请链接 t.me/+xxx
        for m in re.finditer(r"(?:t\.me|telegram\.me)/\+[A-Za-z0-9_-]+", text):
            return True
        # 4. 任意域名带跟踪参数
        for m in re.finditer(r"https?://[^\s]+", text):
            if "?" in m.group(0):
                qs = re.split(r"[&;]", m.group(0).split("?", 1)[1])
                for p in qs:
                    k = p.split("=")[0].strip().lower()
                    if k in list(BASE_AFF_PARAMS) + list(aff_params) or "aff" in k or "ref" in k:
                        return True
        # 5. 关键词（白名单不豁免——白名单只用于生成词库时剔除，避免误杀）
        for k in list(BASE_KEYWORDS) + list(keywords):
            if k and k.lower() in low:
                return True
        return False

    for name, text, expect in SAFE_TESTS:
        got = is_ad(text)
        if got != expect:
            fails.append(f"SAFE-FAIL [{name}]: expect={expect} got={got} text={text[:40]}")
    for name, text, expect in AD_TESTS:
        got = is_ad(text)
        if got != expect:
            fails.append(f"AD-FAIL [{name}]: expect={expect} got={got} text={text[:40]}")
    return len(fails) == 0, fails


def main():
    llm_key = os.environ.get("LLM_API_KEY", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
    model = os.environ.get("LLM_MODEL", "deepseek-chat").strip()
    out_path = os.environ.get("KEYWORDS_OUT", "keywords.json").strip() or "keywords.json"

    existing = load_existing(out_path)
    new_data = None
    if llm_key:
        print("calling LLM to generate new keywords...")
        new_data = llm_generate(llm_key, base_url, model)
        if not new_data:
            print("LLM generation failed, keep existing")
    else:
        print("no LLM_API_KEY, keep existing")

    keywords = merge(existing.get("ad_keywords", []), (new_data or {}).get("ad_keywords", []))
    hidden = merge(existing.get("hidden_link_patterns", []), (new_data or {}).get("hidden_link_patterns", []))
    aff_params = merge(existing.get("aff_params", []), (new_data or {}).get("aff_params", []))
    whitelist = merge(BASE_WHITELIST, (new_data or {}).get("whitelist", []))
    whitelist = list(dict.fromkeys(whitelist))

    # 生成护栏：剔除与白名单重叠的关键词/话术（白名单词不能当广告词，防止误杀）
    whitelist_low = {w.lower() for w in whitelist if w}
    keywords = [k for k in keywords if k.lower() not in whitelist_low]
    hidden = [p for p in hidden if not any(w in p for w in whitelist if w)]

    # 安全测试：不过就放弃更新
    ok, fails = safe_check(keywords, hidden, aff_params, whitelist)
    if not ok:
        print("SAFETY CHECK FAILED - keeping existing keywords.json")
        for f in fails:
            print("  -", f)
        sys.exit(0)  # 不更新，也不报错（避免 workflow 红叉）

    result = {
        "ad_keywords": keywords,
        "hidden_link_patterns": hidden,
        "aff_params": aff_params,
        "whitelist": whitelist,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"keywords.json updated: {len(keywords)} kw, {len(hidden)} hidden, "
          f"{len(aff_params)} aff, {len(whitelist)} whitelist")
    print("SAFETY CHECK PASSED")


if __name__ == "__main__":
    main()
