# TG Forwarder Bot v2.2 —— 云端无痕搬运机器人

GitHub Actions 云端运行，每 5 分钟自动同步，24 小时不间断，电脑关机也不影响。

## 功能
- **多源频道**：`SOURCE=@a,@b` 逗号分隔，任一源有新消息即同步到所有目标
- **无痕搬运**：`MODE=repost` 下载重传，去除"来自 @源频道"水印
- **图片水印处理**：`WM_MODE=crop_bottom/cover_bottom/crop_corner/cover_corner`
- **广告过滤**：内置 60+ 关键词 + 可选 LLM 智能判断（`AD_LLM=true`）
- **文案改写**：`REWRITE=true` + `LLM_API_KEY`，LLM 去营销腔重写
- **编辑同步**：源消息被编辑，目标原地更新（`EDIT_SYNC=true`）

## 部署步骤（GitHub 网页操作，约 10 分钟）

1. 新建**公开**仓库（Public，免费无限额度）→ 上传本目录所有文件（含 `.github` 隐藏目录）
2. Settings → Secrets and variables → Actions：
   - **Secrets**：`BOT_TOKEN`、`LLM_API_KEY`（DeepSeek `sk-` 开头的 key）
   - **Variables**：
     | 名字 | 值 |
     |---|---|
     | SOURCE | `@源频道1,@源频道2` |
     | DEST | `@目标频道` |
     | MODE | `repost` |
     | WM_MODE | `crop_bottom` |
     | WM_AMOUNT | `0.08` |
     | AD_FILTER | `true` |
     | AD_LLM | `true` |
     | REWRITE | `true` |
     | EDIT_SYNC | `true` |
     | LLM_BASE_URL | `https://api.deepseek.com` |
     | LLM_MODEL | `deepseek-chat` |
3. Actions → tg-sync → **Run workflow** 手动跑一次验证
4. 之后每 5 分钟自动运行

## 权限要求
- **源频道**：机器人加入成为**普通成员**即可（无需管理员）
- **目标频道**：机器人必须是**管理员**（频道只有管理员能发）

## 常见报错
| 日志 | 解决 |
|---|---|
| getMe 失败 401 | BOT_TOKEN 填错 |
| chat not found | 机器人没进源频道 |
| Forbidden | 目标频道没给管理员 |
| 409 | 先访问 `https://api.telegram.org/bot<TOKEN>/deleteWebhook` |

## 本地自检
```bash
pip install pillow
python test_cloud.py   # 22 项测试
```
