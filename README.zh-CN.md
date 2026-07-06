# discord-alert-bridge

语言：[English](README.md) | 简体中文

把指定 Discord 频道的新消息转发到 **Lark / 飞书**、**Gmail** 或 **钉钉**。

项目自带本地 Web 控制台，可以编辑配置、启动/停止监听、发送测试通知、查看日志，以及查看最近捕获到的消息。

## 功能

- 监听一个或多个 Discord 频道链接或频道 ID。
- 解析频道、发送人、消息正文、附件和 embed。
- 使用交互式卡片转发到 Lark / 飞书。
- 通过 SMTP 转发到 Gmail。
- 通过自定义机器人 Webhook 转发到钉钉。
- 本地管理页面：`http://127.0.0.1:8765`。
- 支持本地控制台登录。
- 支持“测试通知”，不启动 Discord 监听也能测试 Lark / Gmail / 钉钉。
- 支持运行日志、当前会话日志、清空日志和最近消息记录。

## 重要说明

当前项目从 `DISCORD_USER_TOKEN` 读取 Discord 凭据。自动化个人 Discord 账号可能违反 Discord 服务条款，也可能带来账号风险。请只在你有授权且理解风险的环境中使用。不要提交 token、Webhook URL、邮箱密码、日志或消息历史。

本文档不会说明如何获取或提取 Discord 用户 token。

## 快速开始

### 1. 安装

```bash
cd /Users/jione/CodeProject/JionepythonProject/discord-alert-bridge

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

如果使用已有 Conda 环境：

```bash
cd /Users/jione/CodeProject/JionepythonProject/discord-alert-bridge
/opt/anaconda3/envs/discord-alert-bridge/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

### 2. 配置

可以编辑 `.env`，也可以用 Web 控制台配置。

最低配置示例：

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change_this_password

DISCORD_USER_TOKEN=replace_with_authorized_token
DISCORD_CHANNEL_URLS=https://discord.com/channels/YOUR_GUILD_ID/YOUR_CHANNEL_ID

LARK_ENABLED=true
LARK_WEBHOOK_URL=https://open.larksuite.com/open-apis/bot/v2/hook/replace_me
```

Gmail 和钉钉可以同时开启，完整变量见 [.env.example](.env.example)。

### 3. 启动 Web 控制台

```bash
cd /Users/jione/CodeProject/JionepythonProject/discord-alert-bridge
python3 admin.py
```

或者使用 Conda 环境：

```bash
/opt/anaconda3/envs/discord-alert-bridge/bin/python admin.py
```

打开：

```text
http://127.0.0.1:8765
```

macOS 也可以双击：

```text
start_admin.command
```

### 4. 启动监听

在 Web 控制台保存配置后，点击 **启动监听**。

也可以直接命令行运行：

```bash
python3 main.py
```

或者以可编辑包安装：

```bash
pip install -e .
discord-alert-bridge
discord-alert-bridge-admin
```

## Web 控制台

本地控制台支持：

- 登录和退出登录。
- 保存 `.env` 配置。
- 粘贴 Discord 频道链接后自动填入服务器 ID 和频道 ID。
- 启动、停止、切换监听进程。
- 不启动 Discord 监听，直接发送测试通知。
- 查看当前会话日志。
- 清空日志。
- 按频道查看最近记录的消息。

`.env.example` 中的默认控制台账号为：

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme
```

如果要长期运行控制台，请修改 `ADMIN_PASSWORD`。

## 配置说明

### 管理后台

| 变量 | 说明 |
| --- | --- |
| `ADMIN_USERNAME` | 本地 Web 控制台账号。 |
| `ADMIN_PASSWORD` | 本地 Web 控制台密码。 |

### Discord

| 变量 | 说明 |
| --- | --- |
| `DISCORD_USER_TOKEN` | Gateway 客户端使用的授权 Discord 用户 token，请妥善保管。 |
| `DISCORD_CHANNEL_URLS` | 一个或多个 Discord 频道链接，多个用英文逗号分隔。 |
| `DISCORD_CHANNEL_IDS` | 可选，显式频道 ID。 |
| `DISCORD_ALLOWED_GUILD_IDS` | 可选，服务器 ID 白名单。 |
| `DISCORD_GATEWAY_PROXY` | 留空=库/系统默认；`none`=直连；也可以填显式代理，例如 `socks5://127.0.0.1:7890`。 |
| `ALERT_PREFIX` | 转发通知前缀。 |
| `LOG_LEVEL` | `DEBUG`、`INFO`、`WARNING` 或 `ERROR`。 |

频道链接格式：

```text
https://discord.com/channels/GUILD_ID/CHANNEL_ID
```

### Lark / 飞书

| 变量 | 说明 |
| --- | --- |
| `LARK_ENABLED` | 设置为 `true` 开启 Lark 转发。 |
| `LARK_WEBHOOK_URL` | 自定义机器人 Webhook URL。 |
| `LARK_SECRET` | 可选，加签 secret。 |

### Gmail

| 变量 | 说明 |
| --- | --- |
| `GMAIL_ENABLED` | 设置为 `true` 开启 Gmail 转发。 |
| `SMTP_HOST` | SMTP 服务器，默认 `smtp.gmail.com`。 |
| `SMTP_PORT` | SMTP 端口，默认 `587`。 |
| `SMTP_STARTTLS` | 设置为 `true` 使用 STARTTLS。 |
| `SMTP_USERNAME` | SMTP 用户名。 |
| `SMTP_PASSWORD` | SMTP 密码或 Gmail App Password。 |
| `SMTP_FROM` | 发件人地址。 |
| `SMTP_TO` | 收件人地址，多个用英文逗号分隔。 |

Gmail 通常需要在开启两步验证后使用 App Password。

### 钉钉

| 变量 | 说明 |
| --- | --- |
| `DINGTALK_ENABLED` | 设置为 `true` 开启钉钉转发。 |
| `DINGTALK_WEBHOOK_URL` | 自定义机器人 Webhook URL。 |
| `DINGTALK_SECRET` | 可选，加签 secret。 |

## 运行时文件

程序可能创建这些本地文件：

| 文件 | 用途 |
| --- | --- |
| `.env` | 本地密钥和配置。 |
| `admin.log` | 管理后台日志。 |
| `bridge.log` | 监听进程日志。 |
| `.bridge.pid` | 正在运行的监听进程 ID。 |
| `.admin.pid` | 手动启动后台时的进程 ID。 |
| `messages.json` | 最近记录的转发消息。 |

这些文件已被 Git 忽略，因为它们可能包含 token、Webhook URL 或消息内容。

## 开发与测试

```bash
pip install -e ".[test]"
python3 -m unittest discover -s tests -v
```

## 项目结构

```text
discord-alert-bridge/
├── discord_alert_bridge/
│   ├── admin.py            # 管理 API 和进程控制
│   ├── admin_auth.py       # 本地控制台认证
│   ├── admin_ui.py         # Web 控制台 HTML/CSS/JS
│   ├── config.py           # 环境变量配置
│   ├── discord_gateway.py  # Discord Gateway 监听
│   ├── formatting.py       # 通知格式化
│   ├── forwarders.py       # Lark / Gmail / 钉钉转发
│   ├── message_store.py    # 最近消息存储
│   ├── models.py           # 共享数据模型
│   └── paths.py            # 项目路径
├── admin.py                # Web 控制台入口
├── main.py                 # 监听入口
├── .env.example            # 配置模板
├── requirements.txt
└── tests/
```

## 安全检查

分享或发布仓库前执行：

```bash
git status
git check-ignore -v .env bridge.log messages.json
```

确认没有提交：

- `.env`
- 任何 token 或 Webhook URL
- Gmail 密码或 App Password
- `bridge.log`、`admin.log` 或归档日志
- `messages.json`
- 真实服务器、频道或消息历史数据

如果 token、Webhook 或密码可能泄露，请立即轮换。

## 许可证

MIT License，见 [LICENSE](LICENSE)。
