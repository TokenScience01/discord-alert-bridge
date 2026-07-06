from __future__ import annotations

import html
import json
from typing import Callable

from .admin_auth import auth_required

FieldRenderer = Callable[..., str]


def render_login_page(error: str = "") -> str:
    error_html = (
        f'<p class="login-error">{html.escape(error)}</p>' if error else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>登录 · Discord Alert Bridge</title>
  {_base_styles()}
</head>
<body class="login-body">
  <main class="login-shell">
    <section class="login-card">
      <div class="brand compact">
        <div class="brand-mark" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M7 8.5h3v7H7v-7Zm7 0h3v7h-3v-7Z" fill="currentColor"/><path d="M4 4h16v16H4V4Z" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div>
          <h1>Discord Alert Bridge</h1>
          <p>登录管理控制台</p>
        </div>
      </div>
      {error_html}
      <form id="loginForm" class="login-form">
        <label class="field">
          <span>账号</span>
          <input id="username" name="username" type="text" autocomplete="username" required>
        </label>
        <label class="field">
          <span>密码</span>
          <input id="password" name="password" type="password" autocomplete="current-password" required>
        </label>
        <button class="btn btn-primary btn-full" type="submit">登录</button>
      </form>
    </section>
  </main>
  <script>
    const form = document.querySelector("#loginForm");
    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const button = form.querySelector("button");
      button.disabled = true;
      try {{
        const response = await fetch("/api/login", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            username: form.username.value,
            password: form.password.value,
          }}),
        }});
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.message || "登录失败");
        window.location.href = "/";
      }} catch (error) {{
        let box = document.querySelector(".login-error");
        if (!box) {{
          box = document.createElement("p");
          box.className = "login-error";
          form.before(box);
        }}
        box.textContent = error.message;
      }} finally {{
        button.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


def render_page(
    config: dict[str, str],
    *,
    field: FieldRenderer,
    select: FieldRenderer,
    toggle: FieldRenderer,
    config_fields: list[str],
    secret_fields: set[str],
) -> str:
    auth_enabled = auth_required()
    logout_btn = (
        '<button class="btn btn-ghost btn-sm" id="logoutBtn" type="button">退出</button>'
        if auth_enabled
        else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Discord Alert Bridge</title>
  {_base_styles()}
  <style>
    .app {{ display: flex; min-height: 100vh; }}
    .sidebar {{
      width: 248px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      padding: 20px 14px;
      background: rgba(10, 11, 15, 0.72);
      backdrop-filter: blur(20px);
      box-shadow: 1px 0 0 rgba(255,255,255,0.05);
      position: sticky;
      top: 0;
      height: 100vh;
    }}
    .sidebar-brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 4px 10px 20px;
    }}
    .sidebar-brand h1 {{
      margin: 0;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: -0.02em;
      text-wrap: balance;
    }}
    .sidebar-brand p {{
      margin: 2px 0 0;
      font-size: 11px;
      color: var(--muted);
    }}
    .nav-section {{
      color: var(--muted);
      font-size: 10px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      padding: 14px 12px 6px;
    }}
    .nav-item {{
      width: 100%;
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 42px;
      padding: 10px 12px;
      border: 0;
      border-radius: 12px;
      background: transparent;
      color: var(--muted);
      text-align: left;
      font-weight: 500;
      box-shadow: none;
      transition: background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
    }}
    .nav-item:hover {{ background: var(--surface-2); color: var(--text); }}
    .nav-item.active {{
      background: rgba(88, 101, 242, 0.14);
      color: #fff;
      box-shadow: var(--shadow-border-accent);
    }}
    .nav-icon {{
      width: 20px;
      text-align: center;
      font-size: 15px;
      line-height: 1;
    }}
    .sidebar-spacer {{ flex: 1; }}
    .power-card {{
      padding: 14px;
      border-radius: 16px;
      background: var(--surface-1);
      box-shadow: var(--shadow-border);
    }}
    .power-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .power-label {{
      font-size: 12px;
      font-weight: 600;
      color: var(--muted);
    }}
    .power-status {{
      font-size: 13px;
      font-weight: 700;
    }}
    .power-status.running {{ color: var(--ok); }}
    .power-status.stopped {{ color: var(--danger); }}
    .power-switch {{
      width: 100%;
      min-height: 44px;
      border-radius: 12px;
      padding: 10px 14px 10px 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      font-weight: 600;
      transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.12s ease;
    }}
    .power-switch .switch-track {{
      width: 44px;
      height: 26px;
      border-radius: 999px;
      background: rgba(255,255,255,0.1);
      position: relative;
      flex-shrink: 0;
      transition: background 0.2s ease;
    }}
    .power-switch .switch-thumb {{
      position: absolute;
      top: 3px;
      left: 3px;
      width: 20px;
      height: 20px;
      border-radius: 999px;
      background: #fff;
      box-shadow: 0 2px 6px rgba(0,0,0,0.35);
      transition: transform 0.2s cubic-bezier(0.2, 0, 0, 1);
    }}
    .power-switch.running {{
      background: rgba(59, 165, 93, 0.12);
      box-shadow: inset 0 0 0 1px rgba(59, 165, 93, 0.25);
      color: #b8f0c8;
    }}
    .power-switch.running .switch-track {{ background: var(--ok); }}
    .power-switch.running .switch-thumb {{ transform: translateX(18px); }}
    .power-switch:not(.running) {{
      background: rgba(255,255,255,0.04);
      box-shadow: var(--shadow-border);
      color: var(--text);
    }}
    .power-switch .switch-icons {{
      position: relative;
      width: 16px;
      height: 16px;
      margin-right: 2px;
    }}
    .power-switch .switch-icons span {{
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      font-size: 11px;
      opacity: 0;
      filter: blur(4px);
      transform: scale(0.25);
      transition: opacity 0.3s cubic-bezier(0.2, 0, 0, 1),
                  transform 0.3s cubic-bezier(0.2, 0, 0, 1),
                  filter 0.3s cubic-bezier(0.2, 0, 0, 1);
    }}
    .power-switch.running .icon-on,
    .power-switch:not(.running) .icon-off {{
      opacity: 1;
      filter: blur(0);
      transform: scale(1);
    }}
    .main {{
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 28px;
      position: sticky;
      top: 0;
      z-index: 10;
      background: rgba(10, 11, 15, 0.8);
      backdrop-filter: blur(16px);
      box-shadow: 0 1px 0 rgba(255,255,255,0.05);
    }}
    .page-title {{ margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.03em; text-wrap: balance; }}
    .page-desc {{ margin: 4px 0 0; font-size: 13px; color: var(--muted); text-wrap: pretty; }}
    .topbar-actions {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .content {{ padding: 0 28px 32px; flex: 1; }}
    .view {{ display: none; }}
    .view.active {{ display: block; }}
    .view.active .enter-1 {{ animation: enter 0.34s cubic-bezier(0.2, 0, 0, 1) both; }}
    .view.active .enter-2 {{ animation: enter 0.34s cubic-bezier(0.2, 0, 0, 1) 0.08s both; }}
    .view.active .enter-3 {{ animation: enter 0.34s cubic-bezier(0.2, 0, 0, 1) 0.16s both; }}
    .no-animate .view.active .enter-1,
    .no-animate .view.active .enter-2,
    .no-animate .view.active .enter-3 {{ animation: none; }}
    @keyframes enter {{
      from {{ opacity: 0; transform: translateY(10px); filter: blur(4px); }}
      to {{ opacity: 1; transform: translateY(0); filter: blur(0); }}
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 14px;
      margin-bottom: 14px;
    }}
    .status-hero {{
      padding: 22px;
      border-radius: 20px;
      background: var(--surface-1);
      box-shadow: var(--shadow-border);
      position: relative;
      overflow: hidden;
    }}
    .status-hero::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: radial-gradient(ellipse 70% 80% at 0% 0%, rgba(88,101,242,0.18), transparent 60%);
      pointer-events: none;
    }}
    .status-hero.running::before {{
      background: radial-gradient(ellipse 70% 80% at 0% 0%, rgba(59,165,93,0.2), transparent 60%);
    }}
    .status-row {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .status-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--danger);
      box-shadow: 0 0 0 4px rgba(237,66,69,0.15);
    }}
    .status-dot.running {{
      background: var(--ok);
      box-shadow: 0 0 0 4px rgba(59,165,93,0.18);
      animation: pulse 2s ease-in-out infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ box-shadow: 0 0 0 4px rgba(59,165,93,0.18); }}
      50% {{ box-shadow: 0 0 0 8px rgba(59,165,93,0.08); }}
    }}
    .status-title {{ font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }}
    .status-meta {{ color: var(--muted); font-size: 13px; margin-top: 4px; text-wrap: pretty; }}
    .checklist {{
      display: grid;
      gap: 8px;
      margin-top: 18px;
    }}
    .check-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(255,255,255,0.03);
      font-size: 13px;
    }}
    .check-item.ok {{ color: #b8f0c8; }}
    .check-item.warn {{ color: #ffd89a; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    .metric {{
      padding: 16px;
      border-radius: 16px;
      background: var(--surface-1);
      box-shadow: var(--shadow-border);
    }}
    .metric span {{
      display: block;
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
    }}
    .metric strong {{ font-size: 18px; font-weight: 700; }}
    .card {{
      padding: 20px;
      border-radius: 20px;
      background: var(--surface-1);
      box-shadow: var(--shadow-border);
    }}
    .card-title {{
      margin: 0 0 4px;
      font-size: 15px;
      font-weight: 700;
      text-wrap: balance;
    }}
    .card-desc {{
      margin: 0 0 16px;
      font-size: 13px;
      color: var(--muted);
      text-wrap: pretty;
    }}
    .preview-list {{ display: grid; gap: 10px; }}
    .preview-item {{
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);
      cursor: pointer;
      transition: background 0.18s ease, box-shadow 0.18s ease, transform 0.12s ease;
    }}
    .preview-item:hover {{ background: rgba(255,255,255,0.05); }}
    .preview-item:active {{ transform: scale(0.98); }}
    .preview-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .preview-author {{ color: var(--text); font-weight: 600; }}
    .preview-body {{
      font-size: 13px;
      line-height: 1.5;
      text-wrap: pretty;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .inbox {{
      display: grid;
      grid-template-columns: 240px minmax(0, 1fr);
      gap: 14px;
      min-height: 520px;
    }}
    .channel-pane, .feed-pane {{
      border-radius: 20px;
      background: var(--surface-1);
      box-shadow: var(--shadow-border);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .pane-head {{
      padding: 16px 18px 12px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--muted);
      box-shadow: 0 1px 0 rgba(255,255,255,0.05);
    }}
    .channel-list {{
      flex: 1;
      overflow: auto;
      padding: 8px;
    }}
    .channel-item {{
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 42px;
      padding: 10px 12px;
      border: 0;
      border-radius: 12px;
      background: transparent;
      color: var(--muted);
      text-align: left;
      box-shadow: none;
      transition: background 0.18s ease, color 0.18s ease;
    }}
    .channel-item:hover {{ background: var(--surface-2); color: var(--text); }}
    .channel-item.active {{
      background: rgba(88,101,242,0.14);
      color: #fff;
      box-shadow: var(--shadow-border-accent);
    }}
    .channel-item .name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 500;
    }}
    .channel-item .badge {{
      font-variant-numeric: tabular-nums;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
      flex-shrink: 0;
    }}
    .channel-item.active .badge {{ background: rgba(88,101,242,0.25); }}
    .feed-list {{
      flex: 1;
      overflow: auto;
      padding: 14px;
      display: grid;
      gap: 10px;
      align-content: start;
    }}
    .msg-card {{
      padding: 14px 16px;
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);
      animation: enter 0.3s cubic-bezier(0.2, 0, 0, 1) both;
    }}
    .msg-card:nth-child(1) {{ animation-delay: 0ms; }}
    .msg-card:nth-child(2) {{ animation-delay: 50ms; }}
    .msg-card:nth-child(3) {{ animation-delay: 100ms; }}
    .msg-card:nth-child(4) {{ animation-delay: 150ms; }}
    .msg-card:nth-child(5) {{ animation-delay: 200ms; }}
    .msg-meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      font-size: 12px;
      color: var(--muted);
    }}
    .msg-author {{ color: #fff; font-weight: 600; }}
    .msg-tag {{
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(88,101,242,0.16);
      color: #c9cdff;
      font-size: 11px;
    }}
    .msg-body {{
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.55;
      text-wrap: pretty;
      font-size: 14px;
    }}
    .empty {{
      padding: 48px 24px;
      text-align: center;
      color: var(--muted);
      text-wrap: pretty;
    }}
    .form-card {{
      padding: 22px;
      border-radius: 20px;
      background: var(--surface-1);
      box-shadow: var(--shadow-border);
      margin-bottom: 14px;
    }}
    .form-card h3 {{
      margin: 0 0 6px;
      font-size: 16px;
      font-weight: 700;
      text-wrap: balance;
    }}
    .form-card p {{
      margin: 0 0 18px;
      font-size: 13px;
      color: var(--muted);
      text-wrap: pretty;
    }}
    .provider-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .provider-card {{
      padding: 18px;
      border-radius: 18px;
      background: var(--surface-1);
      box-shadow: var(--shadow-border);
    }}
    .provider-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 14px;
      padding-bottom: 14px;
      box-shadow: 0 1px 0 rgba(255,255,255,0.05);
    }}
    .provider-name {{ font-weight: 700; font-size: 15px; }}
    .provider-fields {{ display: grid; gap: 12px; }}
    .log-panel {{
      border-radius: 20px;
      background: #08090d;
      box-shadow: var(--shadow-border);
      overflow: hidden;
    }}
    .log-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 18px;
      box-shadow: 0 1px 0 rgba(255,255,255,0.05);
      background: rgba(255,255,255,0.02);
    }}
    .log-box {{
      min-height: 480px;
      max-height: calc(100vh - 220px);
      overflow: auto;
      padding: 16px 18px;
      font: 12px/1.65 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .session-label {{ font-size: 12px; color: var(--muted); text-wrap: pretty; }}
    .save-bar {{
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%) translateY(80px);
      opacity: 0;
      pointer-events: none;
      z-index: 40;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      border-radius: 16px;
      background: rgba(20, 22, 28, 0.96);
      box-shadow: var(--shadow-elevated);
      transition: transform 0.25s cubic-bezier(0.2, 0, 0, 1), opacity 0.25s ease;
    }}
    .save-bar.visible {{
      transform: translateX(-50%) translateY(0);
      opacity: 1;
      pointer-events: auto;
    }}
    .save-bar span {{ font-size: 13px; color: var(--muted); }}
    #toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 50;
      max-width: min(380px, calc(100vw - 48px));
      padding: 12px 16px;
      border-radius: 14px;
      background: rgba(20, 22, 28, 0.96);
      box-shadow: var(--shadow-elevated);
      opacity: 0;
      transform: translateY(8px);
      pointer-events: none;
      transition: opacity 0.22s ease, transform 0.22s ease;
      text-wrap: pretty;
    }}
    #toast.visible {{ opacity: 1; transform: translateY(0); }}
    #toast.ok {{ box-shadow: inset 0 0 0 1px rgba(59,165,93,0.3), var(--shadow-elevated); color: #b8f0c8; }}
    #toast.error {{ box-shadow: inset 0 0 0 1px rgba(237,66,69,0.3), var(--shadow-elevated); color: #ffb4b6; }}
    @media (max-width: 1100px) {{
      .hero-grid, .provider-grid {{ grid-template-columns: 1fr; }}
      .inbox {{ grid-template-columns: 1fr; min-height: auto; }}
      .channel-pane {{ max-height: 200px; }}
    }}
    @media (max-width: 860px) {{
      .app {{ flex-direction: column; }}
      .sidebar {{
        width: 100%;
        height: auto;
        position: static;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 4px;
        padding: 12px;
      }}
      .sidebar-brand, .nav-section, .sidebar-spacer {{ display: none; }}
      .nav-item {{ width: auto; flex: 1 1 auto; justify-content: center; padding: 8px 10px; }}
      .power-card {{ width: 100%; }}
      .topbar {{ padding: 14px 16px; flex-direction: column; align-items: flex-start; }}
      .content {{ padding: 0 16px 24px; }}
    }}
  </style>
</head>
<body class="no-animate">
  <div class="app">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-mark" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M7 8.5h3v7H7v-7Zm7 0h3v7h-3v-7Z" fill="currentColor"/><path d="M4 4h16v16H4V4Z" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div>
          <h1>Alert Bridge</h1>
          <p>Discord 转发控制台</p>
        </div>
      </div>

      <div class="nav-section">监控</div>
      <button class="nav-item active" data-view="overview" type="button">
        <span class="nav-icon">◉</span>概览
      </button>
      <button class="nav-item" data-view="messages" type="button">
        <span class="nav-icon">✉</span>消息流
      </button>

      <div class="nav-section">配置</div>
      <button class="nav-item" data-view="listen" type="button">
        <span class="nav-icon">◎</span>监听设置
      </button>
      <button class="nav-item" data-view="notify" type="button">
        <span class="nav-icon">◈</span>通知设置
      </button>
      <button class="nav-item" data-view="logs" type="button">
        <span class="nav-icon">≡</span>运行日志
      </button>
      <button class="nav-item" data-view="account" type="button">
        <span class="nav-icon">◌</span>账户
      </button>

      <div class="sidebar-spacer"></div>

      <div class="power-card">
        <div class="power-top">
          <span class="power-label">监听状态</span>
          <span id="powerStatusText" class="power-status stopped tabular-nums">已停止</span>
        </div>
        <button class="power-switch" id="toggleBtn" type="button" aria-label="切换监听">
          <span class="switch-icons" aria-hidden="true">
            <span class="icon-off">▶</span>
            <span class="icon-on">■</span>
          </span>
          <span id="toggleLabel">启动监听</span>
          <span class="switch-track"><span class="switch-thumb"></span></span>
        </button>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div>
          <h2 class="page-title" id="pageTitle">概览</h2>
          <p class="page-desc" id="pageDesc">查看运行状态、配置就绪情况与最新消息。</p>
        </div>
        <div class="topbar-actions">
          <button class="btn btn-ghost btn-sm" id="testBtn" type="button">测试通知</button>
          <button class="btn btn-primary btn-sm" id="saveBtn" type="button">保存配置</button>
          {logout_btn}
        </div>
      </header>

      <div class="content">
        <section class="view active" id="view-overview">
          <div class="hero-grid enter-1">
            <div class="status-hero" id="statusHero">
              <div class="status-row">
                <span class="status-dot" id="statusDot"></span>
                <div>
                  <div class="status-title" id="statusTitle">监听已停止</div>
                  <div class="status-meta" id="statusMeta">在左侧打开开关，开始接收 Discord 消息。</div>
                </div>
              </div>
              <div class="checklist" id="checklist"></div>
            </div>
            <div class="metric-grid">
              <div class="metric"><span>进程 PID</span><strong id="pidValue" class="tabular-nums">-</strong></div>
              <div class="metric"><span>消息总数</span><strong id="messageCountValue" class="tabular-nums">0</strong></div>
              <div class="metric"><span>转发出口</span><strong id="forwardersValue">-</strong></div>
              <div class="metric"><span>配置状态</span><strong id="readyValue">-</strong></div>
            </div>
          </div>
          <div class="card enter-2">
            <h3 class="card-title">最新消息</h3>
            <p class="card-desc">点击消息可跳转到对应频道视图。</p>
            <div class="preview-list" id="previewList"></div>
          </div>
        </section>

        <section class="view" id="view-messages">
          <div class="inbox enter-1">
            <div class="channel-pane">
              <div class="pane-head">频道</div>
              <div class="channel-list" id="channelList"></div>
            </div>
            <div class="feed-pane">
              <div class="pane-head" id="feedTitle">全部消息</div>
              <div class="feed-list" id="messageList"></div>
            </div>
          </div>
        </section>

        <section class="view" id="view-listen">
          <div class="form-card enter-1">
            <h3>Discord 连接</h3>
            <p>填写用户 Token 与要监听的频道链接，保存后启动监听。</p>
            <div class="grid">
              {field("DISCORD_USER_TOKEN", "User Token", config, secret=True, full=True)}
              {field("DISCORD_CHANNEL_URLS", "频道链接（逗号分隔）", config, full=True)}
              {field("DISCORD_CHANNEL_IDS", "频道 ID（自动填充）", config)}
              {field("DISCORD_ALLOWED_GUILD_IDS", "服务器 ID（自动填充）", config)}
            </div>
          </div>
          <div class="form-card enter-2">
            <h3>通知格式</h3>
            <p>控制转发到 Lark / 邮件等渠道时的消息前缀与日志级别。</p>
            <div class="grid">
              {field("ALERT_PREFIX", "通知前缀", config)}
              {select("LOG_LEVEL", "日志级别", config, ["DEBUG", "INFO", "WARNING", "ERROR"])}
            </div>
          </div>
        </section>

        <section class="view" id="view-notify">
          <div class="provider-grid enter-1">
            <div class="provider-card">
              <div class="provider-head">
                <span class="provider-name">Gmail</span>
              </div>
              <div class="provider-fields">
                {toggle("GMAIL_ENABLED", "启用 Gmail", config)}
                {toggle("SMTP_STARTTLS", "启用 STARTTLS", config)}
                {field("SMTP_HOST", "SMTP Host", config)}
                {field("SMTP_PORT", "SMTP Port", config)}
                {field("SMTP_USERNAME", "用户名", config)}
                {field("SMTP_PASSWORD", "密码", config, secret=True)}
                {field("SMTP_FROM", "发件人", config)}
                {field("SMTP_TO", "收件人", config)}
              </div>
            </div>
            <div class="provider-card">
              <div class="provider-head">
                <span class="provider-name">Lark</span>
              </div>
              <div class="provider-fields">
                {toggle("LARK_ENABLED", "启用 Lark", config)}
                {field("LARK_WEBHOOK_URL", "Webhook URL", config, full=True)}
                {field("LARK_SECRET", "签名 Secret", config, secret=True)}
              </div>
            </div>
            <div class="provider-card">
              <div class="provider-head">
                <span class="provider-name">钉钉</span>
              </div>
              <div class="provider-fields">
                {toggle("DINGTALK_ENABLED", "启用钉钉", config)}
                {field("DINGTALK_WEBHOOK_URL", "Webhook URL", config, full=True)}
                {field("DINGTALK_SECRET", "签名 Secret", config, secret=True)}
              </div>
            </div>
          </div>
        </section>

        <section class="view" id="view-logs">
          <div class="log-panel enter-1">
            <div class="log-toolbar">
              <span class="session-label" id="sessionValue">本次会话：未启动</span>
              <button class="btn btn-ghost btn-sm" id="clearLogBtn" type="button">清空日志</button>
            </div>
            <div class="log-box" id="logBox"></div>
          </div>
        </section>

        <section class="view" id="view-account">
          <div class="form-card enter-1">
            <h3>后台账户</h3>
            <p>修改管理后台的登录账号与密码。</p>
            <div class="grid">
              {field("ADMIN_USERNAME", "登录账号", config)}
              {field("ADMIN_PASSWORD", "登录密码", config, secret=True)}
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>

  <div class="save-bar" id="saveBar">
    <span>配置已修改，尚未保存</span>
    <button class="btn btn-primary btn-sm" id="saveBarBtn" type="button">立即保存</button>
    <button class="btn btn-ghost btn-sm" id="discardBtn" type="button">撤销</button>
  </div>
  <p id="toast" role="status" aria-live="polite"></p>

  <script>
    const fields = {json.dumps(config_fields)};
    const PAGE_META = {{
      overview: {{ title: "概览", desc: "查看运行状态、配置就绪情况与最新消息。" }},
      messages: {{ title: "消息流", desc: "按频道浏览已归档的 Discord 消息。" }},
      listen: {{ title: "监听设置", desc: "配置 Discord Token 与监听频道。" }},
      notify: {{ title: "通知设置", desc: "启用并配置 Gmail、Lark、钉钉转发。" }},
      logs: {{ title: "运行日志", desc: "查看当前会话日志，排查连接与转发问题。" }},
      account: {{ title: "账户", desc: "管理后台登录账号与密码。" }},
    }};
    let activeChannel = "all";
    let savedConfig = {{}};
    let dirty = false;
    let toastTimer = null;

    const toggleBtn = document.querySelector("#toggleBtn");
    const toggleLabel = document.querySelector("#toggleLabel");
    const saveBtn = document.querySelector("#saveBtn");
    const saveBar = document.querySelector("#saveBar");
    const saveBarBtn = document.querySelector("#saveBarBtn");
    const discardBtn = document.querySelector("#discardBtn");
    const testBtn = document.querySelector("#testBtn");
    const clearLogBtn = document.querySelector("#clearLogBtn");
    const logoutBtn = document.querySelector("#logoutBtn");
    const toast = document.querySelector("#toast");
    const logBox = document.querySelector("#logBox");
    const channelList = document.querySelector("#channelList");
    const messageList = document.querySelector("#messageList");
    const previewList = document.querySelector("#previewList");
    const feedTitle = document.querySelector("#feedTitle");

    document.querySelectorAll(".nav-item").forEach((btn) => {{
      btn.addEventListener("click", () => switchView(btn.dataset.view));
    }});

    function switchView(name) {{
      document.querySelectorAll(".nav-item").forEach((item) => {{
        item.classList.toggle("active", item.dataset.view === name);
      }});
      document.querySelectorAll(".view").forEach((view) => {{
        view.classList.toggle("active", view.id === "view-" + name);
      }});
      const meta = PAGE_META[name] || PAGE_META.overview;
      document.querySelector("#pageTitle").textContent = meta.title;
      document.querySelector("#pageDesc").textContent = meta.desc;
      document.body.classList.remove("no-animate");
    }}

    function allInputs() {{
      return Array.from(document.querySelectorAll("input[name], select[name]"));
    }}

    async function request(path, options = {{}}) {{
      const response = await fetch(path, {{
        headers: {{ "Content-Type": "application/json" }},
        ...options,
      }});
      if (response.status === 401) {{
        window.location.href = "/login";
        throw new Error("未登录");
      }}
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }}

    function collectConfig() {{
      const values = {{}};
      fields.forEach((name) => {{
        const input = document.querySelector(`[name="${{name}}"]`);
        if (!input) return;
        values[name] = input.type === "checkbox" ? String(input.checked) : input.value;
      }});
      return values;
    }}

    function applyConfig(config, markSaved = true) {{
      allInputs().forEach((input) => {{
        const name = input.name;
        if (!fields.includes(name)) return;
        if (input.type === "checkbox") {{
          input.checked = ["1", "true", "yes", "on"].includes(String(config[name] || "").toLowerCase());
        }} else {{
          input.value = config[name] || "";
        }}
      }});
      autofillDiscordIds();
      if (markSaved) {{
        savedConfig = collectConfig();
        setDirty(false);
      }}
    }}

    function setDirty(value) {{
      dirty = value;
      saveBar.classList.toggle("visible", dirty);
    }}

    function parseDiscordChannelRefs(value) {{
      const channelIds = new Set();
      const guildIds = new Set();
      String(value || "").split(",").map((item) => item.trim()).filter(Boolean).forEach((ref) => {{
        const urlMatch = ref.match(/(?:https?:\\/\\/)?(?:canary\\.|ptb\\.)?discord(?:app)?\\.com\\/channels\\/(\\d+|@me)\\/(\\d+)(?:\\/\\d+)?/i);
        const pairMatch = ref.match(/^(\\d{{15,25}})\\/(\\d{{15,25}})$/);
        if (urlMatch) {{
          if (urlMatch[1] !== "@me") guildIds.add(urlMatch[1]);
          channelIds.add(urlMatch[2]);
        }} else if (pairMatch) {{
          guildIds.add(pairMatch[1]);
          channelIds.add(pairMatch[2]);
        }}
      }});
      return {{
        channelIds: Array.from(channelIds).sort(),
        guildIds: Array.from(guildIds).sort(),
      }};
    }}

    function autofillDiscordIds() {{
      const channelUrlInput = document.querySelector('[name="DISCORD_CHANNEL_URLS"]');
      const channelIdInput = document.querySelector('[name="DISCORD_CHANNEL_IDS"]');
      const guildIdInput = document.querySelector('[name="DISCORD_ALLOWED_GUILD_IDS"]');
      if (!channelUrlInput || !channelIdInput || !guildIdInput) return;
      const parsed = parseDiscordChannelRefs(channelUrlInput.value);
      if (parsed.channelIds.length) channelIdInput.value = parsed.channelIds.join(",");
      if (parsed.guildIds.length) guildIdInput.value = parsed.guildIds.join(",");
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }}

    function formatLogLine(line) {{
      const safe = escapeHtml(line);
      if (!line.trim()) return `<span class="log-line log-muted">${{safe}}</span>`;
      if (line.includes("Bridge session started")) return `<span class="log-line log-banner">${{safe}}</span>`;
      if (/\\bERROR\\b/.test(line)) return `<span class="log-line log-error">${{safe}}</span>`;
      if (/\\bWARNING\\b/.test(line)) return `<span class="log-line log-warn">${{safe}}</span>`;
      if (/Forwarded Discord message|Stored Discord message/.test(line)) return `<span class="log-line log-ok">${{safe}}</span>`;
      if (/\\bINFO\\b/.test(line)) return `<span class="log-line log-info">${{safe}}</span>`;
      return `<span class="log-line">${{safe}}</span>`;
    }}

    function renderLog(text) {{
      const content = text && text.trim() ? text : "（暂无日志，启动监听后这里会显示输出）";
      logBox.innerHTML = content.split("\\n").map(formatLogLine).join("");
      logBox.scrollTop = logBox.scrollHeight;
    }}

    function renderChannelList(channels) {{
      const total = channels.reduce((sum, item) => sum + (item.message_count || 0), 0);
      const items = [
        `<button class="channel-item ${{activeChannel === "all" ? "active" : ""}}" data-channel="all" type="button">
          <span class="name">全部频道</span><span class="badge tabular-nums">${{total}}</span>
        </button>`,
        ...channels.map((item) => `
          <button class="channel-item ${{activeChannel === item.channel_id ? "active" : ""}}" data-channel="${{item.channel_id}}" type="button">
            <span class="name"># ${{escapeHtml(item.channel_name)}}</span>
            <span class="badge tabular-nums">${{item.message_count || 0}}</span>
          </button>`),
      ];
      channelList.innerHTML = items.join("");
      channelList.querySelectorAll(".channel-item").forEach((btn) => {{
        btn.addEventListener("click", async () => {{
          activeChannel = btn.dataset.channel;
          await refreshMessages();
        }});
      }});
    }}

    function renderMessages(messages) {{
      if (!messages.length) {{
        messageList.innerHTML = `<div class="empty">暂无消息。<br>启动左侧开关后，新消息会出现在这里。</div>`;
        return;
      }}
      messageList.innerHTML = messages.map((item) => `
        <article class="msg-card">
          <div class="msg-meta">
            <div><span class="msg-author">${{escapeHtml(item.author || "未知用户")}}</span> · ${{escapeHtml(item.forwarded_at || "")}}</div>
            <span class="msg-tag"># ${{escapeHtml(item.channel_name || item.channel_id)}}</span>
          </div>
          <div class="msg-body">${{escapeHtml(item.content || "（无文字内容）")}}</div>
        </article>
      `).join("");
    }}

    function renderPreview(messages) {{
      if (!messages.length) {{
        previewList.innerHTML = `<div class="empty">暂无消息，启动监听后这里会显示最新动态。</div>`;
        return;
      }}
      previewList.innerHTML = messages.slice(0, 5).map((item) => `
        <div class="preview-item" data-channel="${{item.channel_id}}">
          <div class="preview-head">
            <span><span class="preview-author">${{escapeHtml(item.author || "未知")}}</span> · #${{escapeHtml(item.channel_name || "")}}</span>
            <span class="tabular-nums">${{escapeHtml(item.forwarded_at || "")}}</span>
          </div>
          <div class="preview-body">${{escapeHtml(item.content || "（无文字内容）")}}</div>
        </div>
      `).join("");
      previewList.querySelectorAll(".preview-item").forEach((item) => {{
        item.addEventListener("click", async () => {{
          activeChannel = item.dataset.channel;
          switchView("messages");
          await refreshMessages();
        }});
      }});
    }}

    async function refreshMessages() {{
      const query = activeChannel === "all" ? "" : `?channel_id=${{encodeURIComponent(activeChannel)}}`;
      const data = await request("/api/messages" + query);
      renderChannelList(data.channels || []);
      renderMessages(data.messages || []);
      renderPreview(data.messages || []);
      document.querySelector("#messageCountValue").textContent = String(data.total || 0);
      if (activeChannel === "all") {{
        feedTitle.textContent = "全部消息";
      }} else {{
        const current = (data.channels || []).find((c) => c.channel_id === activeChannel);
        feedTitle.textContent = current ? "# " + current.channel_name : "频道消息";
      }}
    }}

    function renderChecklist(summary) {{
      const items = [];
      const tokenOk = !summary.missing.includes("Discord User Token") && !(summary.errors || []).some((e) => e.includes("Token"));
      const channelOk = !summary.missing.includes("Discord Channel");
      const forwarderOk = !summary.missing.includes("Forwarder");
      items.push(`<div class="check-item ${{tokenOk ? "ok" : "warn"}}">${{tokenOk ? "✓" : "!"}} Discord Token 已配置</div>`);
      items.push(`<div class="check-item ${{channelOk ? "ok" : "warn"}}">${{channelOk ? "✓" : "!"}} 监听频道已设置</div>`);
      items.push(`<div class="check-item ${{forwarderOk ? "ok" : "warn"}}">${{forwarderOk ? "✓" : "!"}} 至少启用一个通知出口</div>`);
      if (!summary.ready && (summary.errors || []).length) {{
        summary.errors.forEach((err) => {{
          items.push(`<div class="check-item warn">! ${{escapeHtml(err)}}</div>`);
        }});
      }}
      document.querySelector("#checklist").innerHTML = items.join("");
    }}

    function updatePower(running) {{
      toggleBtn.classList.toggle("running", running);
      document.querySelector("#powerStatusText").textContent = running ? "运行中" : "已停止";
      document.querySelector("#powerStatusText").classList.toggle("running", running);
      document.querySelector("#powerStatusText").classList.toggle("stopped", !running);
      toggleLabel.textContent = running ? "停止监听" : "启动监听";

      const hero = document.querySelector("#statusHero");
      const dot = document.querySelector("#statusDot");
      hero.classList.toggle("running", running);
      dot.classList.toggle("running", running);
      document.querySelector("#statusTitle").textContent = running ? "正在监听 Discord" : "监听已停止";
      document.querySelector("#statusMeta").textContent = running
        ? "新消息会自动转发并归档到消息流。"
        : "在左侧打开开关，开始接收 Discord 消息。";
    }}

    function renderStatus(status) {{
      const running = Boolean(status.running);
      updatePower(running);
      document.querySelector("#pidValue").textContent = status.pid || "-";
      document.querySelector("#forwardersValue").textContent =
        status.summary.enabled_forwarders.length ? status.summary.enabled_forwarders.join("、") : "未启用";
      document.querySelector("#readyValue").textContent =
        status.summary.ready ? "已就绪" : "待完善";
      document.querySelector("#sessionValue").textContent =
        "本次会话：" + (status.session_started_at || "未启动");
      renderChecklist(status.summary);
      renderLog(status.log || "");
      if (status.messages && status.messages.items) {{
        renderPreview(status.messages.items);
      }}
    }}

    function setToast(message, type = "") {{
      toast.textContent = message;
      toast.className = type + (message ? " visible" : "");
      if (toastTimer) clearTimeout(toastTimer);
      if (message) {{
        toastTimer = setTimeout(() => toast.classList.remove("visible"), 3200);
      }}
    }}

    async function saveConfig() {{
      saveBtn.disabled = true;
      saveBarBtn.disabled = true;
      try {{
        const data = await request("/api/config", {{
          method: "POST",
          body: JSON.stringify(collectConfig()),
        }});
        applyConfig(collectConfig());
        renderStatus(data.status);
        setToast("配置已保存", "ok");
      }} catch (error) {{
        setToast("保存失败: " + error.message, "error");
      }} finally {{
        saveBtn.disabled = false;
        saveBarBtn.disabled = false;
      }}
    }}

    async function toggleBridge() {{
      toggleBtn.disabled = true;
      try {{
        if (!toggleBtn.classList.contains("running")) {{
          if (dirty) await saveConfig();
          else {{
            const current = collectConfig();
            const data = await request("/api/config", {{
              method: "POST",
              body: JSON.stringify(current),
            }});
            applyConfig(collectConfig());
            renderStatus(data.status);
          }}
        }}
        const data = await request("/api/toggle", {{ method: "POST", body: "{{}}" }});
        renderStatus(data.status);
        setToast(data.message, data.ok ? "ok" : "error");
      }} catch (error) {{
        setToast("操作失败: " + error.message, "error");
      }} finally {{
        toggleBtn.disabled = false;
      }}
    }}

    async function sendTestAlert() {{
      testBtn.disabled = true;
      try {{
        if (dirty) await saveConfig();
        const data = await request("/api/test-alert", {{ method: "POST", body: "{{}}" }});
        renderStatus(data.status);
        setToast(data.message, data.ok ? "ok" : "error");
      }} catch (error) {{
        setToast("测试失败: " + error.message, "error");
      }} finally {{
        testBtn.disabled = false;
      }}
    }}

    async function clearLog() {{
      clearLogBtn.disabled = true;
      try {{
        const data = await request("/api/clear-log", {{ method: "POST", body: "{{}}" }});
        renderStatus(data.status);
        setToast(data.message, "ok");
      }} catch (error) {{
        setToast("清空失败: " + error.message, "error");
      }} finally {{
        clearLogBtn.disabled = false;
      }}
    }}

    async function refresh() {{
      try {{
        const data = await request("/api/status");
        renderStatus(data);
      }} catch (error) {{
        setToast("状态刷新失败: " + error.message, "error");
      }}
    }}

    saveBtn.addEventListener("click", saveConfig);
    saveBarBtn.addEventListener("click", saveConfig);
    discardBtn.addEventListener("click", () => applyConfig(savedConfig));
    toggleBtn.addEventListener("click", toggleBridge);
    testBtn.addEventListener("click", sendTestAlert);
    clearLogBtn.addEventListener("click", clearLog);
    if (logoutBtn) {{
      logoutBtn.addEventListener("click", async () => {{
        await request("/api/logout", {{ method: "POST", body: "{{}}" }});
        window.location.href = "/login";
      }});
    }}

    allInputs().forEach((input) => {{
      input.addEventListener("input", () => {{
        if (input.name === "DISCORD_CHANNEL_URLS") autofillDiscordIds();
        setDirty(JSON.stringify(collectConfig()) !== JSON.stringify(savedConfig));
      }});
      input.addEventListener("change", () => {{
        if (input.name === "DISCORD_CHANNEL_URLS") autofillDiscordIds();
        setDirty(JSON.stringify(collectConfig()) !== JSON.stringify(savedConfig));
      }});
    }});

    request("/api/config")
      .then((data) => applyConfig(data.config))
      .then(refresh)
      .then(refreshMessages)
      .finally(() => {{
        requestAnimationFrame(() => document.body.classList.remove("no-animate"));
      }});
    setInterval(refresh, 2500);
    setInterval(refreshMessages, 4000);
  </script>
</body>
</html>"""


def _base_styles() -> str:
    return """
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      color-scheme: dark;
      --bg: #0a0b0f;
      --surface-1: rgba(20, 22, 28, 0.96);
      --surface-2: rgba(255, 255, 255, 0.05);
      --text: #eceef2;
      --muted: #8b919b;
      --accent: #5865f2;
      --ok: #3ba55d;
      --danger: #ed4245;
      --shadow-border: 0 0 0 1px rgba(255, 255, 255, 0.08);
      --shadow-border-hover: 0 0 0 1px rgba(255, 255, 255, 0.13);
      --shadow-border-accent: 0 0 0 1px rgba(88, 101, 242, 0.35);
      --shadow-elevated: 0 16px 40px rgba(0, 0, 0, 0.45), 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font: 14px/1.5 "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
      background:
        radial-gradient(ellipse 90% 70% at 0% -20%, rgba(88, 101, 242, 0.22), transparent 55%),
        radial-gradient(ellipse 60% 50% at 100% 0%, rgba(59, 165, 93, 0.08), transparent 50%),
        var(--bg);
      color: var(--text);
    }
    .brand-mark {
      width: 40px; height: 40px; border-radius: 14px;
      background: linear-gradient(145deg, #5865f2, #7289da);
      box-shadow: 0 8px 20px rgba(88, 101, 242, 0.35);
      display: grid; place-items: center; color: #fff; flex-shrink: 0;
    }
    .btn {
      min-height: 40px; min-width: 40px;
      border: 0; border-radius: 12px;
      padding: 9px 16px;
      font: inherit; font-weight: 600; cursor: pointer;
      color: var(--text);
      background: rgba(255, 255, 255, 0.05);
      box-shadow: var(--shadow-border);
      transition: background 0.18s ease, box-shadow 0.18s ease, transform 0.12s ease;
    }
    .btn:hover:not(:disabled) { background: rgba(255,255,255,0.08); box-shadow: var(--shadow-border-hover); }
    .btn:active:not(:disabled) { transform: scale(0.96); }
    .btn:disabled { opacity: 0.5; cursor: wait; transform: none; }
    .btn-primary {
      background: linear-gradient(180deg, #5865f2, #4752c4);
      box-shadow: 0 8px 20px rgba(88, 101, 242, 0.3);
      color: #fff;
    }
    .btn-primary:hover:not(:disabled) { box-shadow: 0 10px 24px rgba(88, 101, 242, 0.38); }
    .btn-ghost { background: transparent; box-shadow: none; color: var(--muted); }
    .btn-ghost:hover:not(:disabled) { background: var(--surface-2); color: var(--text); }
    .btn-sm { min-height: 36px; padding: 7px 12px; font-size: 13px; border-radius: 10px; }
    .btn-full { width: 100%; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .field { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
    .field.full, .field:has(input.full) { grid-column: 1 / -1; }
    .field span, label.field > span, .field label {
      font-weight: 600; font-size: 12px; color: #b0b5be; letter-spacing: 0.01em;
    }
    input, select {
      width: 100%; min-height: 42px; border: 0; border-radius: 10px;
      padding: 10px 12px;
      background: rgba(0,0,0,0.28); color: var(--text); font: inherit;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.07);
      transition: box-shadow 0.18s ease;
    }
    input:focus, select:focus {
      outline: none;
      box-shadow: inset 0 0 0 1px rgba(88,101,242,0.6), 0 0 0 3px rgba(88,101,242,0.15);
    }
    .switch {
      display: inline-flex; align-items: center; gap: 10px;
      min-height: 42px; padding: 10px 12px;
      border-radius: 10px; background: rgba(0,0,0,0.2);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05);
      cursor: pointer;
    }
    .switch input {
      width: 18px; min-height: 18px; accent-color: var(--accent);
      box-shadow: none; padding: 0;
    }
    .tabular-nums { font-variant-numeric: tabular-nums; }
    .log-line { display: block; }
    .log-error { color: #ff8e90; }
    .log-warn { color: #ffd56a; }
    .log-info { color: #8fd3ff; }
    .log-ok { color: #7ddea2; }
    .log-banner { color: #c9cdff; font-weight: 700; }
    .log-muted { color: #5c6573; }
    .login-body { display: grid; place-items: center; min-height: 100vh; padding: 24px; }
    .login-shell { width: min(400px, 100%); }
    .login-card {
      padding: 28px; border-radius: 20px;
      background: var(--surface-1);
      box-shadow: var(--shadow-elevated);
    }
    .login-card h1 { margin: 0; font-size: 18px; font-weight: 700; text-wrap: balance; }
    .login-card p { margin: 4px 0 0; font-size: 12px; color: var(--muted); }
    .login-form { display: grid; gap: 14px; margin-top: 20px; }
    .login-error { color: #ffb4b6; margin: 0 0 12px; text-wrap: pretty; font-size: 13px; }
    @media (max-width: 760px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>"""