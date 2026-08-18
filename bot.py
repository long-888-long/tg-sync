#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG Forwarder Bot v3.0 - 账号版（Telethon）无痕搬运机器人
功能：多源频道实时同步 / 无痕搬运 / 广告过滤 / LLM 文案改写 / 标签保留 / 图片视频去水印 / 防重复
运行：GitHub Actions 云端，session 从 Secrets 读取
"""
import json
import os
import re
import sys
import time
import base64
import urllib.request
import urllib.parse
import urllib.error

print("[账号版] 启动中...", flush=True)

# Telethon
from telethon import TelegramClient
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument, DocumentAttributeFilename

print("[账号版] Telethon 加载完成", flush=True)

# 公共 API ID/Hash（Telegram 官方示例凭证）
API_ID = int(os.environ.get("API_ID", "2040"))
API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")

VERSION = "3.0"

# ---------------- 配置 ----------------
class Config:
    def __init__(self):
        self.session_b64 = os.environ.get("BOT_SESSION", "").strip()
        self.source = self._split(os.environ.get("SOURCE", ""))
        self.dest = self._split(os.environ.get("DEST", ""))
        self.wm_mode = os.environ.get("WM_MODE", "remove").strip().lower() or "off"
        self.wm_pos = os.environ.get("WM_POS", "auto").strip().lower() or "auto"
        self.wm_amount = float(os.environ.get("WM_AMOUNT", "0.08") or 0.08)
        self.ad_filter = os.environ.get("AD_FILTER", "true").strip().lower() == "true"
        self.ad_llm = os.environ.get("AD_LLM", "true").strip().lower() == "true"
        self.rewrite = os.environ.get("REWRITE", "true").strip().lower() == "true"
        self.llm_base = os.environ.get("LLM_BASE_URL", "https://llmhost.net/v1").strip().rstrip("/")
        self.llm_key = os.environ.get("LLM_API_KEY", "").strip()
        self.llm_model = os.environ.get("LLM_MODEL", "deepseek-v4-flash").strip()
        self.state_file = os.environ.get("STATE_FILE", "state.json").strip()
        self.rewrite_prompt = os.environ.get("REWRITE_PROMPT", "").strip()

    @staticmethod
    def _split(s):
        return [x.strip() for x in (s or "").split(",") if x.strip()]

# ---------------- 词库加载 ----------------
def load_keywords():
    """加载 keywords.json（不存在/损坏时用内置兜底）"""
    kw = {
        "ad_keywords": ["广告", "推广", "特价", "优惠", "加微信", "扫码", "返利", "代购",
                        "贷款", "博彩", "兼职", "刷单", "加群", "进群", "私聊", "私信",
                        "完全免费", "免费接口", "上当受骗", "官方认证", "强烈推荐", "快来",
                        "速来", "别错过", "白嫖", "限免", "免费领取", "免费体验", "永���免费",
                        "免费开放", "推荐大家", "欢迎使用", "欢迎体验", "正规平台", "官方唯一",
                        "错过可惜", "投稿通道", "频道链接", "群号", "群二维码", "群链接",
                        "出售域名", "域名注册", "域名交易",
                        "TRX", "USDT", "闪租能量", "指令能量", "时间能量", "笔数能量",
                        "秒租能量", "兑换TRX", "USDT/TRX", "电报会员", "账号商城", "eSIM卡",
                        "多链地址监控", "自助服务", "秒租", "直送", "用户名直送", "转U",
                        "区块链操作", "#AD", "#ad", "闪租", "租能量", "能量兑换", "币兑换",
                        "彩票", "六合彩", "时时彩", "棋牌", "百家乐", "老虎机", "赌场",
                        "下注", "投注", "赔率", "开奖", "秒开", "捕鱼", "电玩城", "娱乐城",
                        "代充", "代练", "外挂", "脚本辅助", "破解版", "私服", "点卡充值",
                        "充值卡", "游戏币", "元宝", "钻石充值", "皮肤代充", "加速器", "翻墙",
                        "梯子", "机场订阅", "节点订阅", "科学上网", "SSR订阅", "V2Ray", "Clash订阅",
                        "外汇", "荐股", "炒股群", "内幕消息", "��赚", "翻倍收益", "理财", "投资群",
                        "数字货币", "挖矿", "矿机", "量化交易", "带单", "喊单", "资金盘", "传销",
                        "分销", "招代理", "加盟", "微商", "薅羊毛", "红包群", "助力", "砍价群",
                        "色情", "成人", "约炮", "裸聊", "福利姬", "私密照", "黄色资源",
                        "跑分", "洗钱", "黑产", "接码", "卡商", "号商", "养号", "实名认证",
                        "解封", "代收", "代付", "出款", "回款", "秒到账", "秒结", "日结",
                        "躺赚", "睡后收入", "副业赚钱", "日入过万", "月入十万", "零门槛",
                        "无需押金", "一部手机", "在家兼职", "宝妈兼职", "学生兼职", "打字员",
                        "点赞兼职", "刷视频赚钱", "看广告赚钱", "邀请好友赚钱", "推广返佣"],
        "hidden_link_patterns": ["点我加群", "扫码进群", "拉你进群", "进群领", "私聊我", "私信我",
                                 "私我", "联系我", "加我微信", "加V", "V我", "扣我", "主页有",
                                 "简介有", "评论区见", "置顶有", "通过我的链接注册", "输入邀请码",
                                 "注册即送", "邀请码", "点击获取", "点击链接", "点击查看", "点击加入",
                                 "点击下载", "点击关注", "点击进入", "点击了解", "点击领取", "点击注册",
                                 "点击添加", "点击进群", "点击安装", "点击体验", "点击使用", "点击访问",
                                 "获取链接", "获取方式", "获取地址", "获取资源", "获取教程", "获取安装包",
                                 "领取链接", "领取方式", "领取地址", "领取资源", "私信获取", "私聊获取",
                                 "联系获取", "加我获取", "关注获取", "回复获取", "后台获取", "主页获取",
                                 "简介获取", "置顶获取", "评论区获取", "点击上方", "点击下方", "点击头像",
                                 "点击名片", "点击关注", "点击订阅", "点击转发", "点击收藏"],
        "aff_params": ["start", "aff", "ref", "code", "invite", "from", "source", "utm_source",
                       "utm_medium", "utm_campaign", "channel", "promo", "bonus", "reward"],
        "whitelist": ["群公告", "群规", "入群链接", "技术分享", "新闻", "教程", "公告"]
    }
    try:
        if os.path.exists("keywords.json"):
            with open("keywords.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in kw:
                if isinstance(data.get(k), list):
                    # 合并去重（内置基础词 + 远程词库，一个都不丢）
                    kw[k] = list(dict.fromkeys(kw[k] + data[k]))
    except Exception:
        pass
    return kw

# ---------------- 广告检测 ----------------
def is_aff_link(url):
    """检测 aff/引流链接（带跟踪参数）"""
    try:
        if "t.me/+" in url:
            return True  # 私有邀请链接
        parsed = urllib.parse.urlparse(url)
        if not parsed.query:
            return False
        params = urllib.parse.parse_qs(parsed.query)
        for p in params:
            if p.lower() in KEYWORDS["aff_params"]:
                return True
    except Exception:
        pass
    return False

def contains_ad(text, use_llm=True):
    """广告检测：关键词 + 话术 + aff链接 + 可选LLM"""
    if not text:
        return False
    # 关键词检测
    for kw in KEYWORDS["ad_keywords"]:
        if kw and kw in text:
            return True
    # 隐藏链接话术
    for pat in KEYWORDS["hidden_link_patterns"]:
        if pat and pat in text:
            return True
    # aff 链接检测
    for m in re.finditer(r'https?://[^\s"\']+', text):
        if is_aff_link(m.group(0)):
            return True
    # LLM 智能判断
    if use_llm and cfg.ad_llm:
        try:
            out = llm_call("判断以下消息是否为广告引流，只回复\"广告\"或\"非广告\"：\n" + text[:500])
            if out and "广告" in out and "非广告" not in out:
                return True
        except Exception:
            pass
    return False

# ---------------- 防溯源清洗 ----------------
def strip_trace(text):
    """清洗：删源频道提及/aff链接/引流尾巴，保留普通链接和#标签"""
    if not text:
        return text
    # 删除 @提及（保留 #标签）
    text = re.sub(r'@[\w_]{3,32}', '', text)
    # 删除 aff 链接（带跟踪参数的）
    def _clean_url(m):
        url = m.group(0)
        if is_aff_link(url):
            return ''
        return url
    text = re.sub(r'https?://[^\s"\']+', _clean_url, text)
    # 删除引流尾巴行（在XX频道/投稿通道/水群等）
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if re.search(r'(在|来|进|加|欢迎|这是|去)[\w\u4e00-\u9fa5]{0,8}(频道|群|水群|交流群|茶馆|投稿|入口)', s):
            continue
        # 单独出现的引流词（无动词前缀）
        if re.match(r'^(投稿通道|频道链接|频道入口|群号|群链接|群二维码|交流群|水群|茶馆|入群|进��|加群)$', s):
            continue
        if re.match(r'^[🌸🌹🌺✨🌟⭐💫·●○•]+$', s):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned).strip()

# ---------------- LLM 调用 ----------------
def llm_call(prompt, max_tokens=8000):
    """调用 LLM（中转站兼容），最多 3 次重试"""
    if not cfg.llm_key:
        return ""
    url = cfg.llm_base + "/chat/completions"
    body = json.dumps({
        "model": cfg.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }).encode("utf-8")
    for attempt in range(1, 3):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + cfg.llm_key
            })
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = ""
            if data.get("choices"):
                msg = data["choices"][0].get("message", {})
                content = (msg.get("content") or "").strip()
                # 推理模型：content 为空时尝试 reasoning
                if not content:
                    content = (msg.get("reasoning") or msg.get("reasoning_content") or "").strip()
            if content:
                return content
        except Exception as e:
            print(f"[LLM] 尝试 {attempt}/3 失败: {e}")
            time.sleep(2)
    return ""

def valid_rewrite(out):
    """校验 LLM 改写输出：拒绝语/应答腔/空 → 无效"""
    if not out:
        return False
    s = out.strip()
    if len(s) < 2:
        return False
    bad = ["请提供", "请发送", "无法", "抱歉", "我不能", "好的，我来", "没问题，", "当然可以",
           "以下是", "这是改写", "原文如下", "请把", "请将"]
    for b in bad:
        if s.startswith(b) or b in s[:30]:
            return False
    return True

def rewrite_text(text):
    """LLM 文案改写（失败降级用原文）"""
    if not cfg.rewrite:
        return text
    prompt = cfg.rewrite_prompt or (
        "请改写以下Telegram频道消息，要求：\n"
        "1. 必须保留原文的全部信息（包括所有#标签、数字、专有名词、完整句子）\n"
        "2. 保留所有普通链接\n"
        "3. 只删除营销腔、广告词、引流话术（如'快来''速来''别错过'等）\n"
        "4. 不要删减正常内容，不要添加新内容\n"
        "5. 语言自然简洁，直接输出改写结果，不要任何解释\n\n"
        "原文：\n" + text[:2000]
    )
    out = llm_call(prompt)
    if valid_rewrite(out):
        return out.strip()
    return text

# ---------------- 图片/视频水印处理 ----------------
def process_media_bytes(raw, is_video=False):
    """水印处理：remove 智能去除 / crop 裁剪 / cover 遮盖（失败返回原数据）"""
    try:
        if is_video:
            # 视频：remove 降级为裁剪
            mode = cfg.wm_mode if cfg.wm_mode != "remove" else "crop_bottom"
            return _process_video(raw, mode)
        else:
            return _process_image(raw)
    except Exception as e:
        print(f"[水印] 处理失败，用原图: {e}")
        return raw

def _process_image(raw):
    """图片：智能去水印（OpenCV inpaint）或裁剪/遮盖"""
    try:
        import io
        import numpy as np
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        mode = cfg.wm_mode
        if mode == "remove":
            # 真正的智能去水印：OpenCV inpaint（检测水印像素，用周围内容修复填充）
            try:
                import cv2
                # 转 OpenCV 格式
                img_rgb = img.convert("RGB")
                cv_img = cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2BGR)
                # 定位水印区域
                amount = cfg.wm_amount
                pos = cfg.wm_pos if cfg.wm_pos != "auto" else None
                # 构建候选区域列表
                candidates = []
                if pos is None:
                    # auto 模式：扫描上下左右四条边
                    candidates = [
                        (0, 0, w, int(h * amount)),           # top: 整个顶部
                        (0, int(h * (1 - amount)), w, h),     # bottom: 整个底部
                        (0, 0, int(w * 0.5), int(h * amount)),# top_left
                        (int(w * 0.5), 0, w, int(h * amount)),# top_right
                        (0, int(h * (1 - amount)), int(w * 0.5), h),  # bottom_left
                        (int(w * 0.5), int(h * (1 - amount)), w, h),  # bottom_right
                    ]
                elif pos in ("bottom", "bottom_center"):
                    candidates = [(0, int(h * (1 - amount)), w, h)]
                elif pos == "bottom_right":
                    candidates = [(int(w * 0.6), int(h * (1 - amount)), w, h)]
                elif pos == "bottom_left":
                    candidates = [(0, int(h * (1 - amount)), int(w * 0.4), h)]
                elif pos == "top":
                    candidates = [(0, 0, w, int(h * amount))]
                elif pos == "top_right":
                    candidates = [(int(w * 0.6), 0, w, int(h * amount))]
                elif pos == "top_left":
                    candidates = [(0, 0, int(w * 0.4), int(h * amount))]
                else:
                    candidates = [(0, int(h * (1 - amount)), w, h)]
                # 对每个候选区域检测水印，有就修复
                kernel = np.ones((3, 3), np.uint8)
                for (x1, y1, x2, y2) in candidates:
                    if y2 <= y1 or x2 <= x1:
                        continue
                    region = cv_img[y1:y2, x1:x2]
                    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                    edges = cv2.Canny(gray, 50, 150)
                    mask = cv2.dilate(edges, kernel, iterations=2)
                    if mask.sum() < 500:
                        continue  # 该区域无水印，跳过
                    repaired_region = cv2.inpaint(region, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
                    cv_img[y1:y2, x1:x2] = repaired_region
                # 转回 PIL
                img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
            except Exception as e:
                print(f"[水印] OpenCV inpaint 失败，降级模糊遮盖: {e}")
                from PIL import ImageFilter
                region = img.crop(box).filter(ImageFilter.GaussianBlur(radius=15))
                img.paste(region, box)
        elif mode.startswith("crop"):
            amount = cfg.wm_amount
            if mode == "crop_bottom":
                img = img.crop((0, 0, w, int(h * (1 - amount))))
            elif mode == "crop_corner":
                img = img.crop((0, 0, int(w * 0.95), int(h * 0.95)))
        elif mode.startswith("cover"):
            from PIL import ImageDraw
            amount = cfg.wm_amount
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            if mode == "cover_bottom":
                draw.rectangle([0, int(h * (1 - amount)), w, h], fill=(30, 30, 30, 200))
            elif mode == "cover_corner":
                draw.rectangle([int(w * 0.7), int(h * 0.7), w, h], fill=(30, 30, 30, 200))
            img = Image.alpha_composite(img.convert("RGBA"), overlay)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except Exception:
        return raw

def _process_video(raw, mode):
    """视频：ffmpeg 裁剪底部（remove 降级）"""
    try:
        import subprocess, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(raw)
            in_path = f.name
        out_path = in_path + "_out.mp4"
        if mode == "crop_bottom":
            cmd = ["ffmpeg", "-y", "-i", in_path, "-vf", "crop=in_w:in_h*0.92:0:0", "-c:v", "libx264", "-preset", "fast", out_path]
        else:
            cmd = ["ffmpeg", "-y", "-i", in_path, "-c", "copy", out_path]
        subprocess.run(cmd, capture_output=True, timeout=180)
        with open(out_path, "rb") as f:
            result = f.read()
        os.unlink(in_path)
        if os.path.exists(out_path):
            os.unlink(out_path)
        return result if result else raw
    except Exception as e:
        print(f"[视频水印] 失败: {e}")
        return raw

# ---------------- 搬运主流程 ----------------
def extract_hidden_links(msg):
    """提取消息实体里的隐藏链���（MessageEntityTextUrl / MessageEntityUrl），还原显示"""
    links = []
    try:
        entities = getattr(msg, "entities", None) or []
        for ent in entities:
            url = getattr(ent, "url", None)
            if url:
                links.append(url)
    except Exception:
        pass
    # 去重保序
    seen = set()
    out = []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

async def forward_message(client, msg, dest_entity):
    """搬运单条消息：过滤 → 清洗 → 改写 → 去水印 → 发送"""
    text = msg.message or ""
    # 提取隐藏链接（实体里的 URL，如"👉🏻点击获取"实际链接在 entities 里）
    hidden_links = extract_hidden_links(msg)
    if hidden_links:
        # 把隐藏链接还原显示到文本末尾
        text = text + "\n\n" + "\n".join(hidden_links)
    # 广告过滤
    if cfg.ad_filter and contains_ad(text):
        print(f"[过滤] 广告命中，跳过 #{msg.id}")
        return False
    # 防溯源清洗
    cleaned = strip_trace(text)
    # LLM 改写
    if cfg.rewrite and cleaned:
        cleaned = rewrite_text(cleaned)
    caption = cleaned[:1024] if cleaned else None

    # 媒体处理（带超时，用临时文件避免大文件内存问题）
    media_path = None
    is_video = False
    is_image = False
    file_name = None
    if msg.media:
        try:
            import tempfile
            tmpdir = tempfile.mkdtemp(prefix="tgfb_")
            if isinstance(msg.media, MessageMediaPhoto):
                is_image = True
                file_name = f"photo_{msg.id}.jpg"
                media_path = await asyncio.wait_for(
                    client.download_media(msg.media, file=os.path.join(tmpdir, file_name)), timeout=120)
            elif isinstance(msg.media, MessageMediaDocument):
                doc = msg.media.document
                # 提取文件名
                for a in doc.attributes:
                    if isinstance(a, DocumentAttributeFilename):
                        file_name = a.file_name
                        break
                if not file_name:
                    file_name = f"file_{msg.id}"
                # 判断类型
                for a in doc.attributes:
                    if hasattr(a, "video") and a.video:
                        is_video = True
                        break
                    if hasattr(a, "w") and hasattr(a, "h"):
                        is_image = True
                media_path = await asyncio.wait_for(
                    client.download_media(msg.media, file=os.path.join(tmpdir, file_name)), timeout=300)
        except asyncio.TimeoutError:
            print(f"[媒体] 下载超时 #{msg.id}")
            media_path = None
        except Exception as e:
            print(f"[媒体] 下载失败 #{msg.id}: {e}")
            media_path = None

    # 水印处理（只处理图片/视频，APK等文件原样发送）
    if media_path and os.path.exists(media_path) and (is_image or is_video):
        try:
            with open(media_path, "rb") as f:
                raw = f.read()
            processed = process_media_bytes(raw, is_video=is_video)
            if processed != raw:
                with open(media_path, "wb") as f:
                    f.write(processed)
        except Exception as e:
            print(f"[水印] 处理失败 #{msg.id}: {e}")

    # 发送
    try:
        if media_path and os.path.exists(media_path):
            result = await client.send_file(dest_entity, media_path, caption=caption,
                                            force_document=not (is_image or is_video))
            print(f"[发送] 媒体 #{msg.id} → {cfg.dest} (caption={'有' if caption else '无'}, file={file_name})")
        else:
            if caption:
                result = await client.send_message(dest_entity, caption)
                print(f"[发送] 文字 #{msg.id} → {cfg.dest}")
            else:
                print(f"[跳过] #{msg.id} 无内容")
                return False
        return True
    except Exception as e:
        print(f"[发送] 失败 #{msg.id}: {e}")
        return False

# ---------------- 主流程 ----------------
async def main():
    global cfg, KEYWORDS
    cfg = Config()
    KEYWORDS = load_keywords()

    if not cfg.session_b64:
        print("FATAL: BOT_SESSION 未配置")
        sys.exit(1)
    if not cfg.source or not cfg.dest:
        print("FATAL: SOURCE/DEST 未配置")
        sys.exit(1)

    # 解码 session
    try:
        session_bytes = base64.b64decode(cfg.session_b64)
        session_path = "/tmp/forward_session.session"
        with open(session_path, "wb") as f:
            f.write(session_bytes)
    except Exception as e:
        print(f"FATAL: session 解码失败: {e}")
        sys.exit(1)

    # 加载 state
    state = {}
    if os.path.exists(cfg.state_file):
        try:
            with open(cfg.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}

    client = TelegramClient(session_path, API_ID, API_HASH, connection_retries=2, timeout=20)
    print("[账号版] 正在连接 Telegram...", flush=True)
    try:
        await asyncio.wait_for(client.connect(), timeout=60)
    except asyncio.TimeoutError:
        print("FATAL: 连接 Telegram 超时（网络问题）", flush=True)
        sys.exit(1)
    print("[账号版] 连接成功，��查 session...", flush=True)
    try:
        authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=30)
    except asyncio.TimeoutError:
        print("FATAL: session 验证超时（session 可能已失效，需要重新登录生成新 session）", flush=True)
        sys.exit(1)
    if not authorized:
        print("FATAL: session 未授权（可能已失效，需要重新登录生成新 session）", flush=True)
        sys.exit(1)

    try:
        me = await asyncio.wait_for(client.get_me(), timeout=30)
    except asyncio.TimeoutError:
        print("FATAL: get_me 超时（session 可能已失效）", flush=True)
        sys.exit(1)
    print(f"[账号版] 登录成功: {me.first_name} (ID: {me.id})")

    # 解析源频道和目标频道（带超时）
    sources = []
    for s in cfg.source:
        try:
            entity = await asyncio.wait_for(client.get_entity(s), timeout=30)
            sources.append((s, entity))
            print(f"[账号版] 源频道 {s}: ✅ 已加入")
        except asyncio.TimeoutError:
            print(f"[账号版] 源频道 {s}: ❌ 解析超时")
        except Exception as e:
            print(f"[账号版] 源频道 {s}: ❌ 无法访问 ({e})")
    dest_entities = []
    for d in cfg.dest:
        try:
            entity = await asyncio.wait_for(client.get_entity(d), timeout=30)
            dest_entities.append(entity)
            print(f"[账号版] 目标频道 {d}: ✅ 可访问")
        except asyncio.TimeoutError:
            print(f"[账号版] 目标频道 {d}: ❌ 解析超时")
        except Exception as e:
            print(f"[账号版] 目标频道 {d}: ❌ 无法访问 ({e})")

    if not sources or not dest_entities:
        print("FATAL: 源/目标频道不可用")
        sys.exit(1)

    # 遍历源频道，检查新消息
    total_forwarded = 0
    # 兼容旧 state 结构（scrape_seen），避免重复搬运
    seen_map = state.get("scrape_seen", state)
    MAX_TOTAL = 3  # 单次运行最多处理 3 条，防止运行过长
    for name, entity in sources:
        if total_forwarded >= MAX_TOTAL:
            print(f"[账号版] 已达单次处理上限 {MAX_TOTAL} 条，剩余频道下次运行处理")
            break
        seen = seen_map.get(name, 0)
        try:
            # 获取频道最新消息（带超时，每个源最多 1 条防止运行过长）
            msgs = []
            async def _collect():
                nonlocal msgs
                async for msg in client.iter_messages(entity, limit=20, reverse=True):
                    if msg.id > seen:
                        msgs.append(msg)
                        if len(msgs) >= 1:
                            break
            try:
                await asyncio.wait_for(_collect(), timeout=60)
            except asyncio.TimeoutError:
                print(f"[账号版] {name}: 拉取消息超时")
                continue
            if not msgs:
                print(f"[账号版] {name}: 最新 #{seen}，无新消息")
                continue
            # 首次运行（seen=0）：只初始化记录最新消息，不搬运历史
            if seen == 0:
                latest_id = max(m.id for m in msgs)
                if "scrape_seen" not in state:
                    state["scrape_seen"] = {}
                state["scrape_seen"][name] = latest_id
                with open(cfg.state_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False)
                print(f"[账号版] {name}: 首次初始化，记录最新 #{latest_id}，不搬运历史")
                continue
            latest = max(m.id for m in msgs)
            print(f"[账号版] {name}: 发现新消息 {len(msgs)} 条 (#{seen+1}~#{latest})")
            for msg in sorted(msgs, key=lambda m: m.id):
                for dest in dest_entities:
                    ok = await forward_message(client, msg, dest)
                    if ok:
                        total_forwarded += 1
                # 每条处理后立即更新 state（保持 scrape_seen 结构兼容）
                if "scrape_seen" not in state:
                    state["scrape_seen"] = {}
                state["scrape_seen"][name] = msg.id
                with open(cfg.state_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False)
        except Exception as e:
            print(f"[账号版] {name}: 处理异常: {e}")

    print(f"[账号版] 本次搬运 {total_forwarded} 条")
    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())