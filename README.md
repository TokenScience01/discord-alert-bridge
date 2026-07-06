# discord-alert-bridge

把指定 Discord 频道的新消息转发到 **Lark / 飞书**、**Gmail** 或 **钉钉**。

自带本地 Web 配置页，可保存配置、启动监听、测试通知、查看日志。

## 功能

- 监听一个或多个 Discord 频道
- 自动解析频道名、发送人、消息内容
- Lark 卡片式通知（频道 / 发送人 / 内容分区展示）
- 支持 Gmail SMTP、钉钉 Webhook
- 本地配置页：`http://127.0.0.1:8765`
- 日志按会话分隔，支持一键清空

## 截图

配置页为深色 Discord 风格界面；Lark 通知为紫色标题卡片。

## 快速开始

### 1. 克隆并安装

```bash
git clone https://github.com/TokenScience01/discord-alert-bridge.git
cd discord-alert-bridge

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. 编辑 `.env`

至少配置以下内容：

```env
DISCORD_USER_TOKEN=your_discord_user_token
DISCORD_CHANNEL_URLS=https://discord.com/channels/YOUR_GUILD_ID/YOUR_CHANNEL_ID

LARK_ENABLED=true
LARK_WEBHOOK_URL=https://open.larksuite.com/open-apis/bot/v2/hook/replace_me
```

也支持同时开启 Gmail / 钉钉，详见 [.env.example](.env.example)。

### 3. 启动

**Web 配置页（推荐）**

```bash
python3 admin.py
```

浏览器打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)，保存配置后点击「启动监听」。

macOS 也可以双击 `start_admin.command`。

**命令行**

```bash
python3 main.py
```

或安装为可编辑包：

```bash
pip install -e .
discord-alert-bridge
discord-alert-bridge-admin
```

## 配置说明

### Discord

| 变量 | 说明 |
|------|------|
| `DISCORD_USER_TOKEN` | Discord 用户 Token（仅建议本地测试） |
| `DISCORD_CHANNEL_URLS` | 频道链接，逗号分隔多个 |
| `DISCORD_CHANNEL_IDS` | 可选，显式频道 ID |
| `DISCORD_ALLOWED_GUILD_IDS` | 可选，限制服务器 ID |
| `DISCORD_GATEWAY_PROXY` | 留空=系统代理；`none`=直连；或 `socks5://127.0.0.1:7890` |

频道链接示例：

```text
https://discord.com/channels/1234567890123456789/1234567890123456789
```

### Lark / 飞书

1. 在飞书群中添加「自定义机器人」
2. 复制 Webhook URL 到 `LARK_WEBHOOK_URL`
3. 若启用了签名校验，填写 `LARK_SECRET`

Lark 通知示例：

```text
┌─────────────────────────┐
│  channel-name · Alice   │
├─────────────────────────┤
│ 频道         发送人      │
│ general      Alice      │
├─────────────────────────┤
│ 消息正文内容...          │
└─────────────────────────┘
```

### Gmail

- 建议开启两步验证后创建 [App Password](https://myaccount.google.com/apppasswords)
- 填入 `SMTP_PASSWORD`
- `SMTP_TO` 支持逗号分隔多个收件人

### 钉钉

使用自定义机器人 Webhook；配置 `DINGTALK_SECRET` 时自动加签。

## 开发与测试

```bash
pip install -e ".[test]"
python3 -m unittest discover -s tests -v
```

## 项目结构

```text
discord-alert-bridge/
├── discord_alert_bridge/
│   ├── admin.py          # Web 配置页
│   ├── config.py         # 环境变量加载
│   ├── discord_gateway.py# Discord Gateway 监听
│   ├── formatting.py     # 消息格式化
│   └── forwarders.py     # Lark / Gmail / 钉钉转发
├── admin.py              # 配置页入口
├── main.py               # 监听入口
├── .env.example          # 配置模板（可提交）
└── tests/
```

## 安全与隐私

### 不要提交敏感信息

以下内容**已被 `.gitignore` 排除**，请勿手动加入版本库：

- `.env`（Token、Webhook、邮箱密码）
- `*.log`（日志可能包含 Webhook URL）
- `.bridge.pid`、`.admin.pid`

首次开源前请确认：

```bash
git status
git check-ignore -v .env bridge.log
```

### Discord 用户 Token 风险

本项目当前使用 **Discord 用户 Token + Gateway** 方案，便于本地测试，无需邀请 Bot。

> **警告**：自动化普通用户账号可能违反 [Discord 服务条款](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots)，存在封号风险。请仅用于个人本地测试，风险自负。

如果 Token 或 Webhook 曾经泄露，请立即轮换。

### 代理环境

若本机开启了 Clash / V2Ray 等 SOCKS 代理，需安装 `python-socks`（已包含在 `requirements.txt`）。连接异常时可设置：

```env
DISCORD_GATEWAY_PROXY=none
```

## 开源协议

本项目采用 [MIT License](LICENSE)。

## 贡献

欢迎提交 Issue 和 Pull Request。

贡献前请：

1. 不要提交真实 Token、Webhook、个人频道 ID
2. 运行测试：`python3 -m unittest discover -s tests -v`
3. 保持 `.env.example` 使用占位符

## 免责声明

本软件按「原样」提供，作者不对账号封禁、消息漏发、服务中断或任何间接损失负责。使用前请遵守 Discord、飞书、Google、钉钉等平台的服务条款与当地法律法规。