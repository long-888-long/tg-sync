# TG Forwarder Bot v2.3 —— 云端无痕搬运机器人（含公开频道抓取模式）

GitHub Actions 云端运行，每 5 分钟自动同步，24 小时不间断，电脑关机也不影响。

## 功能
- **两种搬运模式**：
  - `MODE=repost`：机器人加入源频道，下载重传无痕搬运（需源频道加机器人）
  - **`MODE=scrape`（新增，推荐给无法加机器人的公开频道）**：机器人**不需要加入源频道**，直接抓取公开预览页 `t.me/s/频道名`，检测新消息后搬运到你的频道——**不需要源频道管理员的任何操作**
- **多源频道**：`SOURCE=@a,@b` 逗号分隔，任一源有新消息即同步到所有目标
- **无痕搬运**：媒体下载后重传，去除"来自 @源频道"水印；文案自动清除 @提及 和 t.me 链接
- **图片水印处理**：`WM_MODE=crop_bottom/cover_bottom/crop_corner/cover_corner`（裁掉/遮盖频道印在图片底部的水印）
- **广告过滤**：内置 60+ 关键词 + 可选 LLM 智能判断（`AD_LLM=true`）
- **文案改写**：`REWRITE=true` + `LLM_API_KEY`，LLM 去营销腔重写
- **编辑同步**（repost 模式）：源消息被编辑，目标原地更新（`EDIT_SYNC=true`）

## 部署步骤（GitHub 网页操作，约 10 分钟）

1. 新建**公开**仓库（Public，免费无限额度）→ 上传本目录所有文件（含 `.github` 隐藏目录）
2. Settings → Secrets and variables → Actions：
   - **Secrets**：`BOT_TOKEN`、`LLM_API_KEY`（DeepSeek `sk-` 开头的 key）
   - **Variables**：
     | 名字 | 值 |
     |---|---|
     | MODE | `scrape` （源频道无法加机器人时用这个） |
     | SOURCE | `@公开频道1,@公开频道2` |
     | DEST | `@目标频道` |
     | WM_MODE | `crop_bottom` |
     | WM_AMOUNT | `0.08` |
     | AD_FILTER | `true` |
     | AD_LLM | `true` |
     | REWRITE | `true` |
     | EDIT_SYNC | `true` |
     | SCRAPE_CATCHUP | `false` （首次运行不搬历史；想搬历史设 true） |
     | LLM_BASE_URL | `https://api.deepseek.com` |
     | LLM_MODEL | `deepseek-chat` |
3. Actions → tg-sync → **Run workflow** 手动跑一次验证
4. 之后每 5 分钟自动运行

## 权限要求
- **scrape 模式**：源频道是公开频道即可，机器人**无需加入源频道**；目标频道机器人必须是**管理员**
- **repost 模式**：源频道机器人加入成为普通成员即可（无需管理员）

## scrape 模式说明（诚实限制）
- 公开预览页只能看到**最近约 20 条**消息；每 5 分钟抓一次，高频频道的新消息不会漏
- 文字、图片能完整搬运；视频/文件部分能拿到原文件，拿不到时跳过
- 私有频道（无 @用户名）不能用 scrape 模式

## 常见报错
| 日志 | 解决 |
|---|---|
| getMe 失败 401 | BOT_TOKEN 填错 |
| chat not found | 目标频道机器人不在/私有频道名填错 |
| Forbidden | 目标频道没给机器人管理员 |
| 409 | 先访问 `https://api.telegram.org/bot<TOKEN>/deleteWebhook` |
| 抓取失败/页面无消息 | 频道是私有的、或被风控，稍后自动重试 |

## 本地自检
```bash
pip install pillow beautifulsoup4
python test_cloud.py   # 29 项测试
```
