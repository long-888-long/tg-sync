#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG Forwarder Bot v2.2 - 无痕搬运机器人（GitHub Actions 云端版）
功能：多源频道实时同步 / repost 无痕搬运 / 图片水印处理 / 广告过滤 / LLM 文案改写 / 编辑同步
依赖：pillow（图片处理）、requests 可选（用标准库 urllib 实现，零第三方依赖）
"""
import json
import os
import re
import sys
import time
import base64
import hashlib
import mimetypes
import urllib.request
import urllib.parse
import urllib.error
from io import BytesIO

try:
    from PIL import Image, ImageFilter, ImageDraw
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except Exception:
    HAS_BS4 = False

VERSION = "2.8"
API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 60

# ---------------- 配置 ----------------
class Config:
    def __init__(self):
        self.token = os.environ.get("BOT_TOKEN", "").strip()
        self.source = self._split(os.environ.get("SOURCE", ""))
        self.dest = self._split(os.environ.get("DEST", ""))
        self.mode = os.environ.get("MODE", "repost").strip().lower() or "repost"
        self.wm_mode = os.environ.get("WM_MODE", "crop_bottom").strip().lower() or "off"
        self.wm_pos = os.environ.get("WM_POS", "auto").strip().lower() or "auto"
        self.wm_amount = float(os.environ.get("WM_AMOUNT", "0.08") or 0.08)
        self.ad_filter = os.environ.get("AD_FILTER", "true").strip().lower() == "true"
        self.ad_keywords = self._split(os.environ.get("AD_KEYWORDS", ""))
        self.ad_llm = os.environ.get("AD_LLM", "false").strip().lower() == "true"
        self.rewrite = os.environ.get("REWRITE", "false").strip().lower() == "true"
        self.rewrite_prompt = os.environ.get("REWRITE_PROMPT", "").strip()
        self.edit_sync = os.environ.get("EDIT_SYNC", "true").strip().lower() == "true"
        self.llm_api_key = os.environ.get("LLM_API_KEY", "").strip()
        self.llm_base_url = (os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").strip().rstrip("/"))
        self.llm_model = os.environ.get("LLM_MODEL", "deepseek-chat").strip()
        self.llm_timeout = float(os.environ.get("LLM_TIMEOUT", "60") or 60)  # 推理模型需要更长超时
        self.state_file = os.environ.get("STATE_FILE", "state.json").strip()
        self.workflow = os.environ.get("WORKFLOW", "").strip()
        self.replace_mentions = os.environ.get("REPLACE_MENTIONS", "").strip()
        self.scrape_catchup = os.environ.get("SCRAPE_CATCHUP", "false").strip().lower() == "true"
        self.extra_hidden = []
        self.extra_aff_params = []
        self.whitelist = []
        self._load_keywords_file()

    def _load_keywords_file(self):
        """从 keywords.json 加载动态词库（存在时合并到内置词库）。
        文件不存在或损坏时静默跳过，只用内置词库，不影响运行。"""
        try:
            path = os.environ.get("KEYWORDS_FILE", "keywords.json").strip()
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _set_dynamic_keywords(data)
            self.extra_hidden = data.get("hidden_link_patterns", []) or []
            self.extra_aff_params = data.get("aff_params", []) or []
            self.whitelist = data.get("whitelist", []) or []
            extra_kw = data.get("ad_keywords", []) or []
            if extra_kw:
                self.ad_keywords = list(dict.fromkeys(list(self.ad_keywords) + extra_kw))
        except Exception:
            # 词库文件异常不影响主流程
            pass

    @staticmethod
    def _split(s):
        if not s:
            return []
        return [x.strip() for x in s.replace("，", ",").split(",") if x.strip()]

    def validate(self):
        errs = []
        if not self.token:
            errs.append("缺少 BOT_TOKEN（Telegram 机器人 Token）")
        if not self.source:
            errs.append("缺少 SOURCE（源频道，多个用逗号分隔，如 @a,@b）")
        if not self.dest:
            errs.append("缺少 DEST（目标频道）")
        if self.mode not in ("forward", "copy", "repost", "scrape"):
            errs.append("MODE 只能是 forward/copy/repost/scrape")
        if self.mode == "scrape" and not HAS_BS4:
            errs.append("MODE=scrape 需要安装 beautifulsoup4（requirements.txt 已包含）")
        if self.wm_mode not in ("off", "crop_bottom", "crop_corner", "cover_bottom", "cover_corner", "remove"):
            errs.append("WM_MODE 只能是 off/crop_bottom/crop_corner/cover_bottom/cover_corner/remove")
        if self.wm_pos not in ("auto", "bottom_right", "bottom_left", "top_right", "top_left", "bottom_center"):
            errs.append("WM_POS 只能是 auto/bottom_right/bottom_left/top_right/top_left/bottom_center")
        if not (0 < self.wm_amount < 0.5):
            errs.append("WM_AMOUNT 需在 0~0.5 之间")
        if self.rewrite and not self.llm_api_key:
            errs.append("REWRITE=true 需要配置 LLM_API_KEY")
        if self.ad_llm and not self.llm_api_key:
            errs.append("AD_LLM=true 需要配置 LLM_API_KEY")
        return errs


# ---------------- HTTP 工具 ----------------
def api_call(token, method, params=None, files=None, timeout=TIMEOUT):
    """调用 Telegram Bot API。files: {field: (filename, data, mime)}"""
    url = API.format(token=token, method=method)
    if files:
        boundary = "----TF" + hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
        body = BytesIO()
        parts = []
        for k, v in (params or {}).items():
            if v is None:
                continue
            parts.append(
                ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (boundary, k, str(v))).encode("utf-8")
            )
        for k, (fname, data, mime) in files.items():
            parts.append(
                ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                 "Content-Type: %s\r\n\r\n" % (boundary, k, fname, mime)).encode("utf-8")
            )
            parts.append(data)
            parts.append(b"\r\n")
        parts.append(("--%s--\r\n" % boundary).encode("utf-8"))
        for p in parts:
            body.write(p)
        data = body.getvalue()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    else:
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return {"ok": False, "error_code": e.code, "description": body.get("description", str(e))}
    except Exception as e:
        return {"ok": False, "error_code": 0, "description": str(e)}


# ---------------- 文本工具 ----------------
MENTION_RE = re.compile(r"@[A-Za-z0-9_]{4,32}")
LINK_RE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/[^\s]+")
AFF_PARAM_KEYS = ("start", "startapp", "aff", "ref", "code", "invite", "rid", "uid", "promo", "from", "source", "clickid", "subid", "siteid", "pid", "mid", "sid", "tag", "chl", "share_ref")

TRACK_PARAM_KEYS = AFF_PARAM_KEYS + ("clickid", "subid", "siteid", "pid", "mid", "sid", "tag", "chl", "share_ref", "utm_source", "utm_medium", "utm_campaign", "utm_content", "aff_sub", "aff_id", "affcode", "refcode", "invite_code", "invitecode")

# 动态词库（由 keywords.json 加载后注入，无则用内置）
_EXTRA_AFF_PARAMS = []
_EXTRA_HIDDEN = []
_EXTRA_WHITELIST = []


def _set_dynamic_keywords(data):
    """注入 keywords.json 的动态词库（模块级，供各检测函数使用）。"""
    global _EXTRA_AFF_PARAMS, _EXTRA_HIDDEN, _EXTRA_WHITELIST
    if not data:
        return
    _EXTRA_AFF_PARAMS = list(data.get("aff_params", []) or [])
    _EXTRA_HIDDEN = list(data.get("hidden_link_patterns", []) or [])
    _EXTRA_WHITELIST = list(data.get("whitelist", []) or [])

def _is_aff_link(link):
    """判断 t.me 链接是否带引流/AFF 跟踪参数（如 ?start=aff_xxx / ?ref=xxx / ?aff=xxx）"""
    m = re.match(r"(?:https?://)?(?:t\.me|telegram\.me)/([^\s?#]+)(?:\?([^\s]+))?", link, re.IGNORECASE)
    if not m:
        return False
    query = m.group(2) or ""
    keys = AFF_PARAM_KEYS + tuple(_EXTRA_AFF_PARAMS)
    for p in re.split(r"[&;]", query):
        key = p.split("=")[0].strip().lower()
        if key in keys or "aff" in key or "ref" in key:
            return True
    return False


def _is_tracking_link(link):
    """判断任意链接是否带引流/AFF 跟踪参数（不限于 t.me），或是否为私有邀请链接。
    - https://example.com/?ref=abc   → True
    - https://t.me/+AbCdEf123        → True（私有邀请链接）
    - https://t.me/hshsjk9           → False（普通公开链接）
    - https://github.com/xxx         → False
    """
    m = re.match(r"(?:https?://)?([^\s?#]+)(?:\?([^\s]+))?", link, re.IGNORECASE)
    if not m:
        return False
    domain = m.group(1).lower()
    # 私有邀请链接 t.me/+xxx 或 telegram.me/+xxx
    if re.match(r"(?:t\.me|telegram\.me)/\+", domain):
        return True
    query = m.group(2) or ""
    keys = TRACK_PARAM_KEYS + tuple(_EXTRA_AFF_PARAMS)
    for p in re.split(r"[&;]", query):
        key = p.split("=")[0].strip().lower()
        if key in keys or "aff" in key or "ref" in key:
            return True
    return False

AD_DEFAULT_KEYWORDS = [
    "广告", "推广", "特价", "秒杀", "返利", "代购", "贷款", "借款", "博彩", "赌博",
    "加微信", "加v", "扫码", "二维码", "转账", "红包", "优惠券", "满减", "包邮",
    "代理", "加盟", "兼职", "刷单", "招代理", "私聊我", "点击链接", "点击下方",
    "限时", "抢购", "拼团", "团购", "直销", "传销", "荐股", "炒股群", "稳赚",
    "日入", "月入", "躺赚", "零风险", "高收益", "稳赚不赔", "刷流水", "跑分",
    "办证", "发票", "代开发票", "外挂", "破解", "会员低价", "充值优惠", "tg群",
    "电报群", "频道链接", "点我", "私信我", "详情咨询", "有意者", "名额有限",
    # 宣传/引流文案
    "完全免费", "免费接口", "免费开放", "免费使用", "限免", "免费送", "白嫖",
    "上当受骗", "勿上当", "不要上当", "请勿上当", "谨防受骗", "别被骗",
    "全免费", "永久免费", "免费资源", "免费领取", "免费体验", "试用", "内测",
    "官方认证", "官方唯一", "正规平台", "信誉", "良心", "强烈推荐", "推荐大家",
    "欢迎使用", "欢迎体验", "快来", "速来", "别错过", "错过可惜",
]


# 汉字隐藏链接/引流话术模式（如"点我加群""扫码进群""主页有"等）
HIDDEN_LINK_PATTERNS = [
    r"点我(?:加|进|入)?群",
    r"私[聊信]我",
    r"加(?:我|V|v|VX|薇|微信|QQ)",
    r"扫(?:码)?(?:加|进|入)?群",
    r"点击?(?:下方|链接|这里|上面)?(?:的)?(?:链接|按钮|查看|进群)",
    r"(?:主页|简介|签名|置顶|评论区|个人资料|频道)(?:里|中|有|查看|看|见)",
    r"(?:进|加)群(?:领|看|获取|福利|红包)",
    r"[Vv](?:我|信)|扣我|戳我|找我|私我",
    r"联系我",
    r"群(?:号|链接|二维码|入口)",
    r"拉(?:你|我)?进群",
    # 邀请码/注册类引流话术
    r"(?:通过|使用|输入|填写)(?:我|本人|本群|本频道)?的?(?:链接|邀请|邀请码|邀请链接)",
    r"(?:输入|填写|使用|复制)邀请码",
    r"注册(?:即|就|立)?(?:送|返|立减|得|领取)",
    r"邀请码[:：]?[A-Za-z0-9_-]{3,}",
    r"点击(?:注册|申请|领取|参与)",
    r"(?:关注|订阅)(?:我|本|我们|频道)?(?:后|即可|领取|获取)",
]


def contains_hidden_link_ad(text):
    """检测汉字隐藏链接/引流话术。命中说明消息带有引导用户去加群/私聊/看主页的引流意图。"""
    if not text:
        return False
    for p in list(HIDDEN_LINK_PATTERNS) + list(_EXTRA_HIDDEN):
        try:
            if re.search(p, text):
                return True
        except Exception:
            continue
    return False


FOOTER_PATTERNS = [
    # 频道/群组引流尾巴：在XX频道 / XX水群 / 投稿通道 / 频道链接 等
    r"在[\u4e00-\u9fa5A-Za-z0-9_-]{1,20}(?:频道|群|群组)",
    r"[\u4e00-\u9fa5A-Za-z0-9_-]{1,20}(?:水群|交流群|吹水群|闲聊群|茶馆)",
    r"投稿通道?",
    r"频道(?:链接|地址|入口)",
    r"@[A-Za-z0-9_]{3,32}",
]


def _strip_footer(text):
    """删除消息末尾的频道/群组引流尾巴（如 '🌸 在花频道 · 茶馆水群 · 投稿通道'）。
    只删末尾独立成行的引流行，不动正文。"""
    if not text:
        return text
    lines = text.split("\n")
    # 从末尾往前删，直到遇到不像引流尾巴的行
    end = len(lines)
    while end > 0:
        line = lines[end - 1].strip()
        if not line:
            end -= 1
            continue
        # 纯装饰符号行（🌸 · 。● etc）也删
        if re.fullmatch(r"[\s·•●○★☆🌸💬📢🔥✨]+\s*", line):
            end -= 1
            continue
        hit = any(re.search(p, line) for p in FOOTER_PATTERNS)
        if hit:
            end -= 1
            continue
        break
    out = "\n".join(lines[:end]).strip()
    return out


def strip_trace(text, cfg):
    """清洗文本痕迹：删除指向源频道的 @提及/t.me 链接 和 aff 引流链接，保留其他普通链接。
    再删除末尾的频道/群组引流尾巴。replace_mentions 为空则删除，否则替换为指定文字。"""
    if not text:
        return text
    repl = cfg.replace_mentions
    out = text
    for s in cfg.source:
        name = s.lstrip("@")
        if not name:
            continue
        out = re.sub(r"@%s\b" % re.escape(name), repl, out, flags=re.IGNORECASE)
        out = re.sub(r"(?:https?://)?(?:t\.me|telegram\.me)/%s\b" % re.escape(name), repl, out, flags=re.IGNORECASE)
    # aff 引流链接删除；普通 t.me 链接保留
    out = re.sub(
        r"(?:https?://)?(?:t\.me|telegram\.me)/[^\s?#]+\?[^\s]+",
        lambda m: "" if _is_aff_link(m.group(0)) else m.group(0),
        out,
    )
    out = _strip_footer(out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def contains_ad(text, extra_keywords):
    """关键词 + aff/跟踪链接 + 私有邀请链接 + 汉字隐藏链接广告检测
    检测顺序：话术 → 链接 → 关键词；白名单只在关键词环节豁免（防止误杀），
    不豁免话术/链接检测（那些是更强的引流信号）。"""
    if not text:
        return False
    if contains_hidden_link_ad(text):
        return True
    # t.me 带跟踪参数（如 ?start=aff_xxx）
    for m in re.finditer(r"(?:https?://)?(?:t\.me|telegram\.me)/[^\s?#]+\?[^\s]+", text):
        if _is_aff_link(m.group(0)):
            return True
    # 任意链接带跟踪参数 / 私有邀请链接 t.me/+xxx
    for m in re.finditer(r"https?://[^\s]+", text):
        if _is_tracking_link(m.group(0)):
            return True
    for m in re.finditer(r"(?:t\.me|telegram\.me)/\+[A-Za-z0-9_-]+", text):
        if _is_tracking_link(m.group(0)):
            return True
    low = text.lower()
    # 白名单：命中白名单词的消息跳过关键词判定（但上面的话术/链接检测已过，仍可能被拦）
    if any(w and w.lower() in low for w in _EXTRA_WHITELIST):
        return False
    kw = set(AD_DEFAULT_KEYWORDS)
    kw.update(extra_keywords or [])
    for k in kw:
        if k and k.lower() in low:
            return True
    return False


# ---------------- LLM ----------------
def llm_judge_ad(text, cfg):
    """用 LLM 判断是否广告。返回 True=广告 / False=非广告。异常时返回 None（按非广告处理）。"""
    if not cfg.llm_api_key:
        return None
    sys_p = "你是广告内容审核助手。判断以下消息是否为广告/营销/推广内容。只回答：广告 或 非广告。"
    try:
        out = _llm_call(cfg, sys_p, text)
        # 兼容 LLM 输出带标点/换行/前后缀（如"广告。""结论：广告"）
        if not out:
            return None
        out_l = out.strip().lower()
        # 否定语义优先："非广告"/"不是广告"/"不广告" → 非广告
        if "非广告" in out_l or "不是广告" in out_l or "不是" in out_l or "不广告" in out_l:
            return False
        return "广告" in out_l
    except Exception:
        return None


def llm_rewrite(text, cfg):
    """用 LLM 改写文案。返回改写后的文本。"""
    if not cfg.llm_api_key:
        return strip_trace(text, cfg)
    sys_p = cfg.rewrite_prompt or (
        "你是文案编辑。请改写以下 Telegram 频道消息："
        "1.保留全部关键信息（时间/地点/人物/数字/事件）和普通链接（如 t.me/xxx）；"
        "2.去除营销腔、广告词、@提及和引流链接（带 start/aff/ref/code 等跟踪参数的链接）；"
        "3.语言简洁自然，不增删事实。直接输出改写后的内容，不要任何解释。"
    )
    try:
        out = _llm_call(cfg, sys_p, text)
        if _valid_rewrite(out):
            return out
        print("LLM 改写输出无效，降级用原文")
        return strip_trace(text, cfg)
    except Exception:
        return strip_trace(text, cfg)


def _valid_rewrite(out):
    """校验 LLM 改写输出是否可用：非空、不是思考过程/拒绝语/应答腔。"""
    if not out:
        return False
    bad = ("请提供", "提供原文", "无法改写", "不能改写", "需要你提供", "请发送原文", "请把原文",
           "根据你的要求", "思考过程", "reasoning", "作为AI", "作为 AI", "很抱歉", "抱歉")
    # 注：不用裸词"原文"，避免误伤正文本身含"原文"的正常改写结果
    for b in bad:
        if b in out:
            return False
    # 应答腔开头（AI 客套话而非改写结果）
    bad_prefix = ("好的，我来", "好的,我来", "没问题，", "没问题,", "可以的，", "可以的,",
                  "我来帮你", "我帮你", "我可以", "当然可以", "好的！", "好的!")
    for p in bad_prefix:
        if out.startswith(p):
            return False
    return True


def _llm_call(cfg, sys_p, user_msg):
    url = cfg.llm_base_url + "/chat/completions"
    payload = {
        "model": cfg.llm_model,
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 8000,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + cfg.llm_api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=cfg.llm_timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    text = (msg.get("content") or "").strip()
    return text


# ---------------- 图片水印处理 ----------------
try:
    import numpy as _np
    import cv2 as _cv2
    HAS_CV2 = True
except Exception:
    HAS_CV2 = False


def _detect_wm_region(img, pos):
    """确定水印区域 (x, y, w, h)。pos=auto 时用边缘能量自动选角。"""
    w, h = img.size
    rw, rh = int(w * 0.5), int(h * 0.15)
    regions = {
        "bottom_right": (w - rw, h - rh, rw, rh),
        "bottom_left": (0, h - rh, rw, rh),
        "top_right": (w - rw, 0, rw, rh),
        "top_left": (0, 0, rw, rh),
        "bottom_center": (int(w * 0.25), h - rh, int(w * 0.5), rh),
    }
    if pos in regions:
        return regions[pos]
    # auto：选边缘能量最高的角（水印文字=高边缘）
    best_name, best_score = "bottom_right", -1.0
    gray = img.convert("L")
    for name, (x, y, rw2, rh2) in regions.items():
        crop = gray.crop((x, y, x + rw2, y + rh2))
        edges = crop.filter(ImageFilter.FIND_EDGES)
        score = sum(edges.getdata())
        if score > best_score:
            best_score, best_name = score, name
    return regions[best_name]


def _remove_wm_inpaint(img, region):
    """OpenCV 修复去水印：ROI 内检测与背景差异大的像素（水印文字/logo）并用周围内容修复填充。失败返回 None。"""
    if not HAS_CV2:
        return None
    x, y, rw, rh = region
    arr = _np.array(img)
    roi = arr[y:y + rh, x:x + rw].copy()
    if roi.size == 0:
        return None
    gray = _cv2.cvtColor(roi, _cv2.COLOR_RGB2GRAY)
    bg = _cv2.medianBlur(gray, 21)
    diff = _cv2.absdiff(gray, bg)
    _, mask = _cv2.threshold(diff, 22, 255, _cv2.THRESH_BINARY)
    mask = _cv2.morphologyEx(mask, _cv2.MORPH_OPEN, _np.ones((2, 2), _np.uint8))
    mask = _cv2.dilate(mask, _np.ones((3, 3), _np.uint8), iterations=1)
    if int(mask.sum()) < 20:
        return None  # 该区域没有明显水印
    res = _cv2.inpaint(roi, mask, 3, _cv2.INPAINT_TELEA)
    arr[y:y + rh, x:x + rw] = res
    return Image.fromarray(arr)


def process_media_bytes(raw, cfg, kind="photo"):
    """按 WM_MODE 处理图片字节；视频由 ffmpeg 处理（GitHub runner 自带）。"""
    if kind == "video":
        return process_video_bytes(raw, cfg)
    if kind != "photo" or cfg.wm_mode == "off" or not HAS_PIL:
        return raw
    try:
        img = Image.open(BytesIO(raw))
        img = img.convert("RGB")
        w, h = img.size
        amount = max(0.02, min(0.3, cfg.wm_amount))
        if cfg.wm_mode == "remove":
            region = _detect_wm_region(img, cfg.wm_pos)
            img2 = _remove_wm_inpaint(img, region)
            if img2 is not None:
                img = img2
            else:
                # 降级：对水印区域做模糊遮盖（无 cv2 或未检测到水印时）
                blur = img.filter(ImageFilter.GaussianBlur(12))
                x, y, rw, rh = region
                band = blur.crop((x, y, x + rw, y + rh))
                img.paste(band, (x, y))
        elif cfg.wm_mode == "crop_bottom":
            crop_h = int(h * amount)
            img = img.crop((0, 0, w, h - crop_h))
        elif cfg.wm_mode == "crop_corner":
            crop_h = int(h * amount)
            crop_w = int(w * amount)
            img = img.crop((0, 0, w - crop_w, h - crop_h))
        elif cfg.wm_mode in ("cover_bottom", "cover_corner"):
            blur = img.filter(ImageFilter.GaussianBlur(12))
            if cfg.wm_mode == "cover_bottom":
                band_h = int(h * amount)
                band = blur.crop((0, h - band_h, w, h))
                img.paste(band, (0, h - band_h))
            else:
                band_h = int(h * amount)
                band_w = int(w * amount)
                band = blur.crop((w - band_w, h - band_h, w, h))
                img.paste(band, (w - band_w, h - band_h))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except Exception:
        return raw


def process_video_bytes(raw, cfg):
    """视频水印：用 ffmpeg 裁剪底部。失败返回原字节。
    remove（智能修复）对视频不可行，自动降级为 crop_bottom 裁剪兜底。"""
    mode = cfg.wm_mode
    if mode == "remove":
        mode = "crop_bottom"  # 视频无法 inpaint，裁剪兜底
    if mode not in ("crop_bottom", "crop_corner"):
        return raw
    vf = ("crop=in_w:in_h*%.2f:0:0" % (1 - cfg.wm_amount)) if mode == "crop_bottom" \
        else ("crop=in_w*%.2f:in_h*%.2f:0:0" % (1 - cfg.wm_amount, 1 - cfg.wm_amount))
    try:
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".in.mp4", delete=False) as fi:
            fi.write(raw)
            in_path = fi.name
        out_path = in_path.replace(".in.mp4", ".out.mp4")
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-vf", vf, "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "28", "-c:a", "copy", out_path],
            capture_output=True, timeout=180,
        )
        if r.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "rb") as fo:
                data = fo.read()
            os.unlink(in_path)
            os.unlink(out_path)
            return data
        os.unlink(in_path)
        return raw
    except Exception:
        return raw
# ---------------- 消息搬运 ----------------
def resolve_chat(cfg, cid):
    r = api_call(cfg.token, "getChat", {"chat_id": cid})
    if r.get("ok"):
        return r["result"].get("username") or r["result"].get("title") or cid
    return None


def get_me(cfg):
    r = api_call(cfg.token, "getMe")
    if r.get("ok"):
        return r["result"]
    return None


def build_caption(text, caption_len=1024):
    if not text:
        return None
    return text[:caption_len]


def send_text(cfg, chat_id, text):
    return api_call(cfg.token, "sendMessage", {"chat_id": chat_id, "text": text})


def send_photo(cfg, chat_id, raw, caption=None):
    return api_call(cfg.token, "sendPhoto", {"chat_id": chat_id, "caption": caption},
                    {"photo": ("p.jpg", raw, "image/jpeg")})


def send_video(cfg, chat_id, raw, caption=None):
    return api_call(cfg.token, "sendVideo", {"chat_id": chat_id, "caption": caption},
                    {"video": ("v.mp4", raw, "video/mp4")})


def send_animation(cfg, chat_id, raw, caption=None):
    return api_call(cfg.token, "sendAnimation", {"chat_id": chat_id, "caption": caption},
                    {"animation": ("a.gif", raw, "image/gif")})


def send_document(cfg, chat_id, raw, fname, caption=None):
    return api_call(cfg.token, "sendDocument", {"chat_id": chat_id, "caption": caption},
                    {"document": (fname, raw, "application/octet-stream")})


def send_audio(cfg, chat_id, raw, fname, caption=None):
    return api_call(cfg.token, "sendAudio", {"chat_id": chat_id, "caption": caption},
                    {"audio": (fname, raw, "audio/mpeg")})


def download_file(cfg, file_id):
    r = api_call(cfg.token, "getFile", {"file_id": file_id})
    if not r.get("ok"):
        return None
    path = r["result"]["file_path"]
    url = "https://api.telegram.org/file/bot{}/{}".format(cfg.token, path)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return resp.read()
    except Exception:
        return None


MEDIA_HANDLERS = [
    ("video", "video", "send_video", "video/mp4"),
    ("animation", "animation", "send_animation", "image/gif"),
    ("photo", "photo", "send_photo", "image/jpeg"),
    ("document", "document", "send_document", "application/octet-stream"),
    ("audio", "audio", "send_audio", "audio/mpeg"),
    ("voice", "voice", "send_audio", "audio/ogg"),
]


def forward_message(cfg, msg, state):
    """搬运单条消息到所有目标。返回 [(dest, new_msg_id), ...]"""
    results = []
    text = msg.get("text") or msg.get("caption") or ""
    # 1. 广告过滤
    if cfg.ad_filter:
        if contains_ad(text, cfg.ad_keywords):
            return results
        if cfg.ad_llm:
            j = llm_judge_ad(text, cfg)
            if j is True:
                return results
    # 2. 文本清洗/改写
    clean_text = strip_trace(text, cfg)
    if cfg.rewrite and clean_text:
        clean_text = llm_rewrite(clean_text, cfg)
        clean_text = strip_trace(clean_text, cfg)
    # 3. 发送
    for dest in cfg.dest:
        msg_id = _send_one(cfg, dest, msg, clean_text)
        if msg_id is not None:
            results.append((dest, msg_id))
    return results


def _send_one(cfg, dest, msg, clean_text):
    mtype, media_key, handler_name, _mime = None, None, None, None
    for name, key, handler, mime in MEDIA_HANDLERS:
        if msg.get(key):
            mtype, media_key, handler_name, _mime = name, key, handler, mime
            break
    caption = build_caption(clean_text) if clean_text else None
    if mtype is None:
        if not clean_text:
            print("跳过空内容消息（清洗后无正文）")
            return None
        r = send_text(cfg, dest, clean_text)
        return r["result"]["message_id"] if r.get("ok") else None
    # 有媒体：先下载
    file_id = msg[media_key][-1]["file_id"] if isinstance(msg[media_key], list) else msg[media_key]["file_id"]
    raw = download_file(cfg, file_id)
    if raw is None:
        # 下载失败：降级为转发原消息
        r = api_call(cfg.token, "forwardMessage", {"chat_id": dest, "from_chat_id": msg["chat"]["id"], "message_id": msg["message_id"]})
        return r["result"]["message_id"] if r.get("ok") else None
    # 水印处理
    if cfg.mode == "repost":
        raw = process_media_bytes(raw, cfg, kind=mtype if mtype in ("photo", "video") else "other")
    handler = globals()[handler_name]
    if handler_name == "send_document":
        fname = msg[media_key].get("file_name") or "file.bin"
        r = handler(cfg, dest, raw, fname, caption)
    elif handler_name == "send_audio":
        fname = "audio.mp3"
        r = handler(cfg, dest, raw, fname, caption)
    else:
        r = handler(cfg, dest, raw, caption)
    if r.get("ok"):
        return r["result"]["message_id"]
    if cfg.mode == "repost":
        # repost 失败（如文件过大）：回退 forward
        r2 = api_call(cfg.token, "forwardMessage", {"chat_id": dest, "from_chat_id": msg["chat"]["id"], "message_id": msg["message_id"]})
        return r2["result"]["message_id"] if r2.get("ok") else None
    return None


def edit_sync(cfg, edit, state):
    """源消息被编辑 → 所有目标原地更新"""
    msg = edit.get("message") or edit.get("edited_message") or {}
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")
    text = msg.get("text") or msg.get("caption") or ""
    if cfg.ad_filter and contains_ad(text, cfg.ad_keywords):
        return 0
    clean = strip_trace(text, cfg)
    if cfg.rewrite and clean:
        clean = llm_rewrite(clean, cfg)
        clean = strip_trace(clean, cfg)
    links = state.get("links", [])
    updated = 0
    for dest, old_id, src_id, src_chat in links:
        if src_id == msg_id and src_chat == chat_id:
            r = api_call(cfg.token, "editMessageText",
                         {"chat_id": dest, "message_id": old_id, "text": clean or "[已清空]"})
            if r.get("ok"):
                updated += 1
    return updated


# ---------------- 公开频道抓取搬运（MODE=scrape） ----------------
SCRAPE_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch_page(username):
    """抓取 t.me/s/<username> 公开预览页 HTML（无需登录/加入）"""
    url = "https://t.me/s/{}".format(username.lstrip("@"))
    req = urllib.request.Request(url, headers={"User-Agent": SCRAPE_UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_messages(html):
    """解析预览页，返回消息列表 [{post_id, text, media, datetime}]"""
    if not HAS_BS4:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for wrap in soup.select("div.tgme_widget_message"):
        post = wrap.get("data-post", "")
        try:
            post_id = int(post.split("/")[-1])
        except Exception:
            continue
        m = {"post_id": post_id, "text": "", "media": None, "media_list": [], "datetime": "",
                "post_url": "https://t.me/{}/{}".format(username, post_id),
                "has_video_player": False}
        t = wrap.select_one("div.tgme_widget_message_text")
        if t:
            m["text"] = t.get_text("\n", strip=True)
        tm = wrap.select_one("time")
        if tm:
            m["datetime"] = tm.get("datetime", "")
        # 图片（一条消息可能多张）
        for photo in wrap.select("a.tgme_widget_message_photo_wrap"):
            mm = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", photo.get("style", ""))
            if mm:
                m["media_list"].append({"type": "photo", "url": mm.group(1)})
        # 视频（一条消息可能多个；懒加载时 src 为空，用 data-src 兜底）
        for video in wrap.select("video.tgme_widget_message_video"):
            url = video.get("src") or video.get("data-src")
            if url:
                m["media_list"].append({"type": "video", "url": url})
        # 文件（可能多个）
        for doc in wrap.select("a.tgme_widget_message_document"):
            if doc.get("href"):
                m["media_list"].append({"type": "document", "url": doc["href"],
                                        "fname": doc.get_text(strip=True) or "file.bin"})
        # 检测 video_player 链接（预览页占位时媒体缺失，需用 embed 页兜底）
        if wrap.select_one("a.tgme_widget_message_video_player"):
            m["has_video_player"] = True
        # 兼容旧字段：media = 第一个媒体
        if m["media_list"]:
            m["media"] = m["media_list"][0]
        out.append(m)
    return out


def fetch_url_bytes(url):
    """下载媒体原始字节（用于去水印重传）"""
    req = urllib.request.Request(url, headers={"User-Agent": SCRAPE_UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()

def fetch_embed_media(username, post_id):
    """预览页占位时，用单条消息 embed 页兜底提取媒体 URL 列表"""
    url = "https://t.me/{}/{}?embed=1".format(username, post_id)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception:
        return []
    out = []
    for m in re.finditer(r'<video[^>]*src="([^"]+)"', html):
        out.append({"type": "video", "url": m.group(1)})
    for m in re.finditer(r'<a class="tgme_widget_message_photo_wrap"[^>]*style="[^"]*url\([\'"]?([^\'")]+)', html):
        out.append({"type": "photo", "url": m.group(1)})
    return out




def send_scraped(cfg, dest, msg):
    """把抓取到的消息发送到目标频道。返回 message_id 或 None（被过滤/失败）"""
    text = msg.get("text") or ""
    if cfg.ad_filter:
        if contains_ad(text, cfg.ad_keywords):
            print("  [过滤] 广告关键词命中: {}".format(text[:40]))
            return None
        if cfg.ad_llm:
            j = llm_judge_ad(text, cfg)
            if j is True:
                print("  [过滤] LLM判定广告: {}".format(text[:40]))
                return None
    clean = strip_trace(text, cfg)
    if cfg.rewrite and clean:
        clean = llm_rewrite(clean, cfg)
        clean = strip_trace(clean, cfg)
    caption = build_caption(clean) if clean else None
    media_list = msg.get("media_list") or ([msg["media"]] if msg.get("media") else [])
    if not media_list and msg.get("has_video_player"):
        # 预览页占位（媒体未渲染）：用 embed 页兜底提取
        try:
            username = msg["post_url"].split("/")[-2]
            post_id = msg["post_id"]
            media_list = fetch_embed_media(username, post_id)
            if media_list:
                print("  [embed兜底] 从 embed 页提取到 {} 个媒体".format(len(media_list)))
        except Exception:
            media_list = []
    if not media_list:
        if not clean:
            # 原消息为纯链接/提及（被防溯源清洗删光），或 LLM 改写后为空：跳过不搬运
            print("跳过空内容消息（清洗后无正文）")
            return None
        r = send_text(cfg, dest, clean)
        return r["result"]["message_id"] if r.get("ok") else None
    # 逐个发送所有媒体（多视频/多图片/混合），caption 只挂第一个
    first_mid = None
    for i, media in enumerate(media_list):
        try:
            raw = fetch_url_bytes(media["url"])
        except Exception:
            print("媒体下载失败: {}".format(media["url"]))
            continue
        cap = caption if i == 0 else None
        mtype = media["type"]
        if mtype == "photo":
            if cfg.wm_mode != "off":
                raw = process_media_bytes(raw, cfg, kind="photo")
            r = send_photo(cfg, dest, raw, cap)
        elif mtype == "video":
            if cfg.wm_mode != "off":
                raw = process_media_bytes(raw, cfg, kind="video")
            print("  [发送视频] caption={}".format(repr(cap)))
            r = send_video(cfg, dest, raw, cap)
            if r.get("ok"):
                print("  [视频发送成功] message_id={}".format(r["result"]["message_id"]))
            else:
                print("  [视频发送失败] {} {}".format(r.get("error_code"), r.get("description")))
        else:
            r = send_document(cfg, dest, raw, media.get("fname", "file.bin"), cap)
        if r.get("ok") and first_mid is None:
            first_mid = r["result"]["message_id"]
    return first_mid


def scrape_sync(cfg, state):
    """抓取所有源频道公开预览页，搬运新消息。返回搬运条数。"""
    seen = state.setdefault("scrape_seen", {})
    total = 0
    for src in cfg.source:
        username = src.lstrip("@")
        if not username:
            continue
        try:
            html = fetch_page(username)
        except Exception as e:
            print("抓取失败 {}: {}".format(username, e))
            continue
        msgs = parse_messages(html)
        if not msgs:
            print("{} 页面无消息（可能被风控/需要验证）".format(username))
            continue
        latest = max(m["post_id"] for m in msgs)
        last = seen.get(username, 0)
        print("{} 最新 #{}，上次 #{}（新消息 {} 条）".format(username, latest, last, max(0, latest - last)))
        if last == 0 and not cfg.scrape_catchup:
            seen[username] = latest
            print("{} 已初始化（最新 #{}），不搬运历史".format(username, latest))
            continue
        new_msgs = sorted([m for m in msgs if m["post_id"] > last], key=lambda x: x["post_id"])
        for m in new_msgs:
            # 防重复保险：跳过本次运行中已处理的 post（并发场景双保险）
            if m["post_id"] <= seen.get(username, 0):
                continue
            sent = False
            for dest in cfg.dest:
                mid = send_scraped(cfg, dest, m)
                if mid is not None:
                    sent = True
                    total += 1
            if sent:
                print("已搬运 {} #{} ({})".format(username, m["post_id"], m["datetime"] or "?"))
            # 立即更新 seen 并保存，防止并发/中断导致重复搬运
            seen[username] = max(seen.get(username, 0), m["post_id"])
            save_state(cfg, state)
    save_state(cfg, state)
    print("本次抓取搬运 {} 条".format(total))
    return total


# ---------------- 状态 ----------------
def load_state(cfg):
    try:
        with open(cfg.state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"offset": 0, "links": []}


def save_state(cfg, state):
    try:
        with open(cfg.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_updates(cfg, offset):
    r = api_call(cfg.token, "getUpdates", {"offset": offset, "timeout": 5, "allowed_updates": json.dumps(["message", "edited_message", "channel_post", "edited_channel_post"])})
    return r


def is_from_source(msg, cfg):
    chat = msg.get("chat", {})
    cid = chat.get("id")
    username = chat.get("username") or ""
    uname = ("@" + username) if username else ""
    for s in cfg.source:
        s = s.strip()
        if s.startswith("@"):
            if uname.lower() == s.lower():
                return True
        else:
            try:
                if cid == int(s):
                    return True
            except Exception:
                pass
    return False


def main():
    cfg = Config()
    errs = cfg.validate()
    if errs:
        print("配置错误：")
        for e in errs:
            print(" - " + e)
        print("请检查 GitHub 仓库的 Secrets / Variables 设置。")
        sys.exit(1)
    # getMe 验证 token
    me = get_me(cfg)
    if not me:
        print("getMe 失败：BOT_TOKEN 无效或网络不可用")
        sys.exit(1)
    print("机器人: @{}".format(me.get("username", "?")))
    print("规则: {} -> {}".format(",".join(cfg.source), ",".join(cfg.dest)))
    print("模式: {} | 水印: {} | 广告过滤: {} | 改写: {}".format(
        cfg.mode, cfg.wm_mode, cfg.ad_filter, cfg.rewrite))
    # 检查源/目标可访问（scrape 模式源频道无需加入，跳过源检查）
    for c in (cfg.dest if cfg.mode == "scrape" else cfg.source + cfg.dest):
        name = resolve_chat(cfg, c)
        if name is None:
            print("警告: 无法访问 {}（机器人不在其中或无权限）".format(c))
    state = load_state(cfg)
    if cfg.mode == "scrape":
        print("抓取模式: 源频道无需机器人加入，直接读取公开预览页")
        scrape_sync(cfg, state)
        return
    offset = int(state.get("offset", 0))
    if cfg.workflow == "init":
        # 手动触发初始化：保留历史 offset（默认 0 会搬最近 24h 消息）
        print("初始状态已就绪 offset={}".format(offset))
        save_state(cfg, state)
        return
    # 只处理最近 1 天的消息，避免历史刷屏
    limit_ts = time.time() - 24 * 3600
    processed = 0
    while True:
        r = get_updates(cfg, offset)
        if not r.get("ok"):
            print("getUpdates 失败: {} {}".format(r.get("error_code"), r.get("description")))
            break
        updates = r.get("result", [])
        if not updates:
            break
        for u in updates:
            offset = max(offset, u["update_id"] + 1)
            if "channel_post" in u:
                msg = u["channel_post"]
            elif "message" in u:
                msg = u["message"]
            elif "edited_channel_post" in u:
                if cfg.edit_sync:
                    edit_sync(cfg, {"message": u["edited_channel_post"]}, state)
                continue
            elif "edited_message" in u:
                if cfg.edit_sync:
                    edit_sync(cfg, {"message": u["edited_message"]}, state)
                continue
            else:
                continue
            # 只处理源频道的消息 + 24h 内
            if not is_from_source(msg, cfg):
                continue
            if msg.get("date", 0) < limit_ts:
                continue
            results = forward_message(cfg, msg, state)
            for dest, new_id in results:
                state.setdefault("links", []).append([dest, new_id, msg.get("message_id"), msg.get("chat", {}).get("id")])
            if results:
                processed += 1
                print("已搬运 1 条 -> {}".format(",".join(d for d, _ in results)))
        save_state(cfg, state)
        if len(updates) < 100:
            break
    print("本次运行完成，新搬运 {} 条".format(processed))


if __name__ == "__main__":
    main()
