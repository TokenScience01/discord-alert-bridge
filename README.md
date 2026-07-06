# discord-alert-bridge

Language: English | [简体中文](README.zh-CN.md)

Forward messages from selected Discord channels to **Lark / Feishu**, **Gmail**, or **DingTalk**.

The project includes a local web console for editing configuration, starting or stopping the bridge, sending a test notification, viewing logs, and reviewing recently captured messages.

## Features

- Monitor one or more Discord channel URLs or channel IDs.
- Parse channel, author, message content, attachments, and embeds.
- Forward to Lark / Feishu with an interactive card layout.
- Forward to Gmail through SMTP.
- Forward to DingTalk through a custom robot webhook.
- Local admin console at `http://127.0.0.1:8765`.
- Optional admin login for the local console.
- Test notification button for validating Lark / Gmail / DingTalk without starting Discord monitoring.
- Runtime log, per-session log view, clear-log action, and recent-message storage.

## Important Notice

This project currently reads Discord credentials from `DISCORD_USER_TOKEN`. Automating a personal Discord account may violate Discord's terms and can put the account at risk. Use only in environments where you have authorization and understand the risk. Do not commit tokens, webhook URLs, email passwords, logs, or message history.

This README intentionally does not describe how to obtain or extract a Discord user token.

## Quick Start

### 1. Install

```bash
cd /Users/jione/CodeProject/JionepythonProject/discord-alert-bridge

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

If you are using the existing Conda environment:

```bash
cd /Users/jione/CodeProject/JionepythonProject/discord-alert-bridge
/opt/anaconda3/envs/discord-alert-bridge/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure

Edit `.env`, or use the web console.

Minimum fields:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change_this_password

DISCORD_USER_TOKEN=replace_with_authorized_token
DISCORD_CHANNEL_URLS=https://discord.com/channels/YOUR_GUILD_ID/YOUR_CHANNEL_ID

LARK_ENABLED=true
LARK_WEBHOOK_URL=https://open.larksuite.com/open-apis/bot/v2/hook/replace_me
```

Gmail and DingTalk can be enabled at the same time. See [.env.example](.env.example) for all variables.

### 3. Start The Admin Console

```bash
cd /Users/jione/CodeProject/JionepythonProject/discord-alert-bridge
python3 admin.py
```

Or with the Conda environment:

```bash
/opt/anaconda3/envs/discord-alert-bridge/bin/python admin.py
```

Open:

```text
http://127.0.0.1:8765
```

On macOS, you can also double-click:

```text
start_admin.command
```

### 4. Start Monitoring

In the web console, save the configuration and click **Start Listening**.

You can also run the bridge directly:

```bash
python3 main.py
```

Or install the package in editable mode:

```bash
pip install -e .
discord-alert-bridge
discord-alert-bridge-admin
```

## Web Console

The local console supports:

- Login and logout.
- Saving `.env` configuration.
- Auto-filling guild ID and channel ID from Discord channel URLs.
- Starting, stopping, and toggling the bridge process.
- Sending a test notification without Discord monitoring.
- Viewing the current session log.
- Clearing the log.
- Viewing recently recorded messages grouped by channel.

Default console credentials come from `.env.example`:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme
```

Change `ADMIN_PASSWORD` before keeping the console running.

## Configuration

### Admin

| Variable | Description |
| --- | --- |
| `ADMIN_USERNAME` | Local web console username. |
| `ADMIN_PASSWORD` | Local web console password. |

### Discord

| Variable | Description |
| --- | --- |
| `DISCORD_USER_TOKEN` | Authorized Discord user token used by the gateway client. Keep it private. |
| `DISCORD_CHANNEL_URLS` | One or more Discord channel URLs, comma-separated. |
| `DISCORD_CHANNEL_IDS` | Optional explicit channel IDs. |
| `DISCORD_ALLOWED_GUILD_IDS` | Optional guild allow-list. |
| `DISCORD_GATEWAY_PROXY` | Empty = library/system default; `none` = direct connection; or an explicit proxy such as `socks5://127.0.0.1:7890`. |
| `ALERT_PREFIX` | Prefix used in forwarded notifications. |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |

Channel URL format:

```text
https://discord.com/channels/GUILD_ID/CHANNEL_ID
```

### Lark / Feishu

| Variable | Description |
| --- | --- |
| `LARK_ENABLED` | Set to `true` to enable Lark forwarding. |
| `LARK_WEBHOOK_URL` | Custom bot webhook URL. |
| `LARK_SECRET` | Optional signing secret. |

### Gmail

| Variable | Description |
| --- | --- |
| `GMAIL_ENABLED` | Set to `true` to enable Gmail forwarding. |
| `SMTP_HOST` | SMTP server, defaults to `smtp.gmail.com`. |
| `SMTP_PORT` | SMTP port, defaults to `587`. |
| `SMTP_STARTTLS` | Set to `true` for STARTTLS. |
| `SMTP_USERNAME` | SMTP username. |
| `SMTP_PASSWORD` | SMTP password or Gmail App Password. |
| `SMTP_FROM` | Sender address. |
| `SMTP_TO` | Recipient addresses, comma-separated. |

For Gmail, an App Password is usually required when two-step verification is enabled.

### DingTalk

| Variable | Description |
| --- | --- |
| `DINGTALK_ENABLED` | Set to `true` to enable DingTalk forwarding. |
| `DINGTALK_WEBHOOK_URL` | Custom robot webhook URL. |
| `DINGTALK_SECRET` | Optional signing secret. |

## Runtime Files

The app may create these local files:

| File | Purpose |
| --- | --- |
| `.env` | Local secrets and configuration. |
| `admin.log` | Admin console log. |
| `bridge.log` | Bridge runtime log. |
| `.bridge.pid` | Running bridge process ID. |
| `.admin.pid` | Admin process ID when started manually. |
| `messages.json` | Recently recorded forwarded messages. |

These files are ignored by Git because they may contain tokens, webhook URLs, or message content.

## Development

```bash
pip install -e ".[test]"
python3 -m unittest discover -s tests -v
```

## Project Structure

```text
discord-alert-bridge/
├── discord_alert_bridge/
│   ├── admin.py            # Admin API and process control
│   ├── admin_auth.py       # Local console authentication
│   ├── admin_ui.py         # Web console HTML/CSS/JS
│   ├── config.py           # Environment configuration
│   ├── discord_gateway.py  # Discord Gateway listener
│   ├── formatting.py       # Notification formatting
│   ├── forwarders.py       # Lark / Gmail / DingTalk forwarding
│   ├── message_store.py    # Recent-message storage
│   ├── models.py           # Shared data models
│   └── paths.py            # Project paths
├── admin.py                # Admin console entrypoint
├── main.py                 # Bridge entrypoint
├── .env.example            # Configuration template
├── requirements.txt
└── tests/
```

## Security Checklist

Before sharing or publishing this repository:

```bash
git status
git check-ignore -v .env bridge.log messages.json
```

Make sure you did not commit:

- `.env`
- Any token or webhook URL
- Gmail passwords or App Passwords
- `bridge.log`, `admin.log`, or archived logs
- `messages.json`
- Real guild, channel, or message history data

Rotate any token, webhook, or password that may have been exposed.

### Discord User Token Risk

This project currently uses a **Discord user token + Gateway** approach for local testing, without requiring a bot invitation.

> **Warning**: Automating a normal user account may violate the [Discord Terms of Service](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots) and can lead to account action. Use it only for personal local testing and at your own risk.

If a token or webhook may have leaked, rotate it immediately.

## License

MIT License. See [LICENSE](LICENSE).
