#!/usr/bin/env python3
"""
浏览器浏览记录监控 - 时间管理与效率分析
功能：
  1. 定期采集 Chrome/Edge 浏览历史
  2. 网站分类（工作/社交/娱乐/学习/新闻/其他）
  3. 计算浏览时长
  4. 生成每日效率报告
"""
import os
import sys
import json
import sqlite3
import shutil
import tempfile
from datetime import datetime, timedelta
from urllib.parse import urlparse
from collections import defaultdict

# ── 配置 ──
HOME = os.path.expanduser("~")
DATA_DIR = "E:\\bumoren\\time-craft\\data"
os.makedirs(DATA_DIR, exist_ok=True)

STATE_FILE = os.path.join(DATA_DIR, "state.json")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
os.makedirs(DAILY_DIR, exist_ok=True)

# 浏览器历史数据库路径
BROWSERS = {
    "Chrome": os.path.join(HOME, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "History"),
    "Edge": os.path.join(HOME, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "History"),
}

# ── 网站分类 ──
CATEGORIES = {
    "🏢 工作/开发": [
        "github.com", "gitlab.com", "bitbucket.org", "jira", "confluence",
        "notion.so", "figma.com", "slack.com", "trello.com", "linear.app",
        "vercel.com", "netlify.com", "heroku.com", "aws.amazon.com",
        "console.cloud.google", "azure.microsoft", "stackoverflow.com",
        "stackexchange.com", "docs.python.org", "developer.mozilla.org",
        "npmjs.com", "pypi.org", "crates.io", "nuget.org",
        "code.visualstudio.com", "jetbrains.com", "postman.com",
        "docker.com", "kubernetes.io", "terraform.io",
        "cloudflare.com", "digitalocean.com", "linode.com",
        "xiaomimimo.com", "packyapi.com", "api.", "developer.",
        "dev.", "console.", "dashboard.", "admin.", "panel.",
        "cutecloud", "cloudflare", "vercel", "railway.app",
        "render.com", "fly.io", "supabase.com", "firebase",
        "gitee.com", "coding.net", "aliyun.com", "tencent.com",
        "huaweicloud.com", "uos.", "deepin.", "linux.do",
        "mosquitto.org", "emqx.com", "mqtt", "rabbitmq",
    ],
    "💬 社交/通讯": [
        "weibo.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
        "linkedin.com", "reddit.com", "discord.com", "telegram.org",
        "web.whatsapp.com", "zhihu.com", "douban.com", "xiaohongshu.com",
        "bilibili.com", "douyin.com", "tiktok.com", "threads.net",
        "mastodon", "qq.com", "weixin.qq.com", "tieba.baidu.com",
        "nga.cn", "v2ex.com", "hupu.com", "soul-app",
    ],
    "🎬 娱乐/视频": [
        "youtube.com", "netflix.com", "twitch.tv", "iqiyi.com",
        "youku.com", "v.qq.com", "mgtv.com", "disneyplus.com",
        "hbomax.com", "spotify.com", "music.163.com", "y.qq.com",
        "kugou.com", "kuwo.cn", "acfun.cn", "acg.", "anime",
        "gaming", "game.", "steam", "epicgames.com",
        "playstation.com", "xbox.com", "nintendo.com",
    ],
    "📰 新闻/资讯": [
        "news", "bbc.com", "cnn.com", "reuters.com", "theguardian.com",
        "nytimes.com", "washingtonpost.com", "36kr.com", "huxiu.com",
        "ithome.com", "sspai.com", "infoq.cn", "toutiao.com",
        "sina.com.cn", "163.com", "ifeng.com",
        "techcrunch.com", "theverge.com", "arstechnica.com", "wired.com",
        "engadget.com", "hackernews", "news.ycombinator.com",
        "cls.cn", "wallstreetcn.com", "xueqiu.com", "eastmoney.com",
        "jiemian.com", "caixin.com", "yicai.com",
    ],
    "📚 学习/知识": [
        "wikipedia.org", "medium.com", "dev.to", "hashnode.dev",
        "coursera.org", "udemy.com", "edx.org", "khanacademy.org",
        "leetcode.com", "hackerrank.com", "codeforces.com",
        "arxiv.org", "scholar.google", "researchgate.net",
        "openai.com", "anthropic.com", "huggingface.co",
        "zhuanlan.zhihu.com", "juejin.cn", "cnblogs.com",
        "csdn.net", "segmentfault.com", "runoob.com", "w3school",
        "geeksforgeeks.org", "javabetter.cn", "vipc6.com",
        "imooc.com", "icourse163.org", "baike.com", "doc.",
        "docs.", "tutorial", "learn.", "course.", "lesson.",
        "deepseek.com", "chat.deepseek.com", "chat.openai.com",
        "claude.ai", "gemini.google", "kimi.", "doubao.",
        "tongyi.", "baichuan.", "zhipu.", "moonshot",
        "ai.", "llm.", "gpt.", "blog.", "post.",
    ],
    "🛒 购物": [
        "taobao.com", "tmall.com", "jd.com", "pinduoduo.com",
        "amazon.com", "amazon.cn", "ebay.com", "aliexpress.com",
        "suning.com", "dangdang.com", "vip.com", "yangkeduo",
        "xiaomiyoupin.com", "mi.com", "huawei.com", "shop.",
        "store.", "mall.", "buy.", "price.",
    ],
    "🔧 工具/效率": [
        "translate.google", "deepl.com", "grammarly.com",
        "drive.google.com", "docs.google.com", "sheets.google.com",
        "dropbox.com", "onedrive.live.com", "icloud.com",
        "mail.google.com", "outlook.live.com", "mail.qq.com",
        "calendar.google.com", "1password.com", "bitwarden.com",
        "regex101.com", "crontab.guru", "jsonformatter",
        "tinypng.com", "remove.bg", "canva.com",
        "baidu.com", "google.com/search", "bing.com",
        "cn.bing.com", "sogou.com", "so.com", "yandex",
        "duckduckgo.com", "search.", "maps.", "weather.",
        "calculator", "convert", "download.", "tool.",
        "online.", "free.", "pdf.", "image.", "video.",
    ],
}

def classify_url(url):
    """根据URL分类"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower() + parsed.path.lower()
    except Exception:
        return "🌐 其他"

    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in domain:
                return category
    return "🌐 其他"

def get_domain(url):
    """提取主域名"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url

def load_state():
    """加载上次运行状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_timestamps": {}, "last_run": None}

def save_state(state):
    """保存运行状态"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def filter_today(entries, date_str):
    """只保留指定日期的记录"""
    return [e for e in entries if e.get("datetime", "").startswith(date_str)]

def read_browser_history(db_path, browser_name, after_timestamp=None):
    """读取浏览器历史记录（复制数据库避免锁）"""
    if not os.path.exists(db_path):
        return []

    tmp_path = None
    try:
        # 复制数据库到临时文件，避免浏览器锁定
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(tmp_fd)
        shutil.copy2(db_path, tmp_path)

        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Chrome/Edge 使用 WebKit 时间戳（微秒，起点 1601-01-01）
        query = "SELECT url, title, visit_count, last_visit_time FROM urls"
        params = []
        if after_timestamp:
            query += " WHERE last_visit_time > ?"
            params.append(after_timestamp)
        query += " ORDER BY last_visit_time DESC LIMIT 5000"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        entries = []
        # WebKit 时间戳转换常量
        WEBKIT_EPOCH = datetime(1601, 1, 1)

        for url, title, visit_count, last_visit_time in rows:
            if last_visit_time and last_visit_time > 0:
                try:
                    visit_dt = WEBKIT_EPOCH + timedelta(microseconds=last_visit_time)
                    unix_ts = visit_dt.timestamp()
                except (OverflowError, OSError):
                    continue
            else:
                continue

            # 只保留最近7天的记录
            if (datetime.now() - visit_dt).days > 7:
                continue

            entries.append({
                "url": url,
                "title": title or "",
                "visit_count": visit_count or 1,
                "timestamp": unix_ts,
                "datetime": visit_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "browser": browser_name,
                "domain": get_domain(url),
                "category": classify_url(url),
            })

        return entries

    except Exception as e:
        print(f"  ⚠ 读取 {browser_name} 失败: {e}", file=sys.stderr)
        return []
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

def compute_browsing_sessions(entries, gap_minutes=30):
    """
    将浏览记录按时间分组为"会话"，计算每个会话的时长。
    同一域名连续访问间隔 < gap_minutes 算作一次会话。
    """
    if not entries:
        return []

    # 按时间排序
    sorted_entries = sorted(entries, key=lambda x: x["timestamp"])

    sessions = []
    current_domain = None
    session_start = None
    session_entries = []

    for entry in sorted_entries:
        domain = entry["domain"]
        ts = entry["timestamp"]

        if current_domain == domain and session_start:
            time_gap = (ts - session_start) / 60  # 分钟
            if time_gap < gap_minutes:
                # 同一会话
                session_entries.append(entry)
                continue

        # 新会话
        if current_domain and session_entries:
            duration = (session_entries[-1]["timestamp"] - session_entries[0]["timestamp"]) / 60
            sessions.append({
                "domain": current_domain,
                "category": session_entries[0]["category"],
                "title": session_entries[-1]["title"],
                "start_time": session_entries[0]["datetime"],
                "end_time": session_entries[-1]["datetime"],
                "duration_min": max(duration, 0.5),  # 至少30秒
                "page_count": len(session_entries),
            })

        current_domain = domain
        session_start = ts
        session_entries = [entry]

    # 最后一个会话
    if current_domain and session_entries:
        duration = (session_entries[-1]["timestamp"] - session_entries[0]["timestamp"]) / 60
        sessions.append({
            "domain": current_domain,
            "category": session_entries[0]["category"],
            "title": session_entries[-1]["title"],
            "start_time": session_entries[0]["datetime"],
            "end_time": session_entries[-1]["datetime"],
            "duration_min": max(duration, 0.5),
            "page_count": len(session_entries),
        })

    return sessions

def extract_app_name(title, browser=None):
    """从窗口标题提取应用名"""
    if browser:
        return browser
    if "[APP:" in title:
        exe = title.split("]")[0].replace("[APP:", "").strip()
        name = exe.replace(".exe", "").replace(".EXE", "")
        # 常见进程名映射
        APP_MAP = {
            "idea64": "IntelliJ IDEA",
            "idea": "IntelliJ IDEA",
            "Code": "VSCode",
            "devenv": "Visual Studio",
            "WeChat": "微信", "Weixin": "微信", "WeChatApp": "微信",
            "QQ": "QQ",
            "DingTalk": "钉钉",
            "Feishu": "飞书",
            "Lark": "飞书",
            "notepad++": "Notepad++",
            "explorer": "资源管理器",
            "ms-teams": "Teams",
            "slack": "Slack",
            "typora": "Typora",
            "postman": "Postman",
            "navicat": "Navicat",
            "apifox": "Apifox",
            "mqttx": "MQTTX",
            "termius": "Termius",
            "cc-switch": "CC Switch",
            "cutecloud": "CuteCloud",
        }
        return APP_MAP.get(name, name)
    # 窗口标题解析
    if "IntelliJ IDEA" in title or "IntelliJ" in title:
        return "IntelliJ IDEA"
    if "Visual Studio Code" in title:
        return "VSCode"
    if "微信" in title:
        return "微信"
    if "QQ" in title and "Google Chrome" not in title:
        return "QQ"
    if "钉钉" in title:
        return "钉钉"
    if "飞书" in title or "Lark" in title:
        return "飞书"
    if "Postman" in title:
        return "Postman"
    if "Typora" in title:
        return "Typora"
    if "Navicat" in title:
        return "Navicat"
    # 默认取第一段
    return title.split(" - ")[0].split(" | ")[0].strip()[:25]

# 浏览器进程名集合
BROWSER_PROCESSES = {"Chrome", "Edge", "Firefox", "chrome", "edge", "firefox"}

def get_all_taskbar_programs():
    """枚举当前所有任务栏/托盘程序"""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000

        def is_taskbar(hwnd):
            if not user32.IsWindowVisible(hwnd):
                return False
            if user32.GetWindowTextLengthW(hwnd) == 0:
                return False
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ex & WS_EX_TOOLWINDOW:
                return False
            if ex & WS_EX_APPWINDOW:
                return True
            return user32.GetWindow(hwnd, 4) == 0

        EnumWindows = user32.EnumWindows
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        programs = {}

        def callback(hwnd, _):
            if is_taskbar(hwnd):
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    import psutil
                    proc = psutil.Process(pid.value).name().replace(".exe", "").replace(".EXE", "")
                except Exception:
                    proc = "unknown"
                if proc not in programs:
                    programs[proc] = 1
                else:
                    programs[proc] += 1
            return True

        EnumWindows(WNDENUMPROC(callback), 0)
        return programs
    except Exception:
        return {}

def generate_hierarchical_report(entries, sessions, active_segments, report_date=None):
    """生成分级统计报告"""
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    lines = []
    lines.append(f"📊 {report_date} 效率报告")
    lines.append("=" * 38)

    # ── Level 1: 程序活跃时长 ──
    app_time = defaultdict(float)
    app_order = []  # 保持出现顺序

    if active_segments:
        for seg in active_segments:
            app = extract_app_name(seg.get("title", ""), seg.get("browser"))
            if app not in app_time:
                app_order.append(app)
            app_time[app] += seg.get("duration_sec", 0) / 60
    else:
        # 降级：用浏览器历史数据估算
        if sessions:
            browser_total = defaultdict(float)
            for s in sessions:
                browser_total["Chrome"] += s["duration_min"]
            for b, t in browser_total.items():
                app_time[b] = t
                app_order.append(b)

    # 枚举当前所有任务栏程序
    all_programs = get_all_taskbar_programs()

    # 系统组件过滤
    SYSTEM_PROCS = {
        "TextInputHost", "ApplicationFrameHost", "SystemSettings",
        "SearchHost", "StartMenuExperienceHost", "ShellExperienceHost",
        "RuntimeBroker", "backgroundTaskHost", "MusNotification",
        "CompPkgSrv", "SecurityHealthSystray",
    }

    # 当前打开的程序集合（用于标记状态）
    current_open = set()
    for proc_name in all_programs:
        if proc_name in SYSTEM_PROCS:
            continue
        display = extract_app_name(f"[APP:{proc_name}.exe] ", None)
        current_open.add(display.lower())

    # 合并：活跃监控的程序 + 任务栏中未被使用的程序
    for proc_name in all_programs:
        if proc_name in SYSTEM_PROCS:
            continue
        display = extract_app_name(f"[APP:{proc_name}.exe] ", None)
        # 检查是否已存在（大小写不敏感匹配）
        found = False
        for existing in app_time:
            if existing.lower() == display.lower():
                found = True
                break
        if not found:
            app_time[display] = 0

    total_active = sum(app_time.values())

    # ── 总览 ──
    lines.append("")
    total_sec = sum(s.get("duration_sec", 0) for s in active_segments) if active_segments else 0
    h = int(total_sec // 3600)
    m = int((total_sec % 3600) // 60)
    if h > 0:
        active_str = f"{h}小时{m}分钟"
    elif m > 0:
        active_str = f"{m}分钟"
    else:
        active_str = "不足1分钟"

    lines.append(f"⏱ 总活跃时长: {active_str}")
    lines.append(f"📱 使用程序数: {len(app_time)}")
    lines.append("")

    # ── Level 1 列表 ──
    lines.append("📱 程序使用时长 (Level 1)")
    lines.append("-" * 38)

    # 进程名图标映射
    APP_ICONS = {
        "Chrome": "🌐", "Edge": "🌐", "Firefox": "🌐",
        "IntelliJ IDEA": "💻", "VSCode": "💻", "Visual Studio": "💻",
        "QQ": "💬", "微信": "💬", "Weixin": "💬", "钉钉": "📌", "飞书": "📌",
        "Teams": "📌", "Slack": "💬",
        "Postman": "🔧", "Navicat": "🔧", "Typora": "📝",
        "Apifox": "🔧", "MQTTX": "🔧", "Termius": "🔧",
        "Notepad++": "📝", "cc-switch": "▪", "CuteCloud": "☁",
        "explorer": "📂", "资源管理器": "📂",
    }

    sorted_apps = sorted(app_time.items(), key=lambda x: -x[1])
    for app, t in sorted_apps:
        m = int(t)
        icon = APP_ICONS.get(app, "▪")

        if m == 0:
            # 未使用，不显示
            continue

        if total_active > 0:
            pct = t / total_active * 100
            pct_str = f"{pct:.0f}%"
        else:
            pct_str = "0%"
        bar_len = min(int((t / max(total_active, 1)) * 40), 20) if total_active > 0 else 0
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"  {icon} {app}: {m}分钟 ({pct_str})")
        lines.append(f"     {bar}")

    # ══════════════════════════════════════
    # ── Level 2: 浏览器网站详情 ──
    # ══════════════════════════════════════
    if sessions:
        lines.append("")
        lines.append("🌐 浏览器网站详情 (Level 2)")
        lines.append("=" * 38)

        # 按浏览器分组
        browser_sessions = defaultdict(list)
        for s in sessions:
            browser_sessions["Chrome"].append(s)

        for browser, bsessions in browser_sessions.items():
            if browser not in app_time:
                continue

            # 域名时长统计
            domain_time = defaultdict(float)
            domain_title = {}
            for s in bsessions:
                domain_time[s["domain"]] += s["duration_min"]
                if s["title"]:
                    domain_title[s["domain"]] = s["title"]

            for domain, t in sorted(domain_time.items(), key=lambda x: -x[1]):
                m = int(t)
                if m >= 1:
                    title = domain_title.get(domain, "")[:25]
                    lines.append(f"  {domain}  {m}分钟")

    # ══════════════════════════════════════
    # ── Level 2: IDEA 项目详情 ──
    # ══════════════════════════════════════
    if active_segments:
        idea_segments = [s for s in active_segments if s.get("idea_project")]
        if idea_segments:
            # 项目时长
            project_time = defaultdict(float)
            project_modules = defaultdict(lambda: defaultdict(float))
            project_files = defaultdict(lambda: defaultdict(float))

            for seg in idea_segments:
                proj = seg["idea_project"]
                dur = seg.get("duration_sec", 0) / 60
                project_time[proj] += dur

                mod = seg.get("idea_module")
                if mod:
                    project_modules[proj][mod] += dur

                fname = seg.get("idea_file")
                if fname:
                    project_files[proj][fname] += dur

            lines.append("")
            lines.append("💻 IDEA 项目详情 (Level 2)")
            lines.append("=" * 38)

            for proj in sorted(project_time.keys(), key=lambda p: -project_time[p]):
                pt = project_time[proj]
                pm = int(pt)

                if pm == 0:
                    continue

                lines.append(f"")
                lines.append(f"  📁 {proj}: {pm}分钟")

                # 模块时长
                if project_modules[proj]:
                    for mod, mt in sorted(project_modules[proj].items(), key=lambda x: -x[1]):
                        mm = int(mt)
                        if mm >= 1:
                            lines.append(f"    ├─ 模块 {mod}: {mm}分钟")

                # 文件 Top 5
                if project_files[proj]:
                    for fname, ft in sorted(project_files[proj].items(), key=lambda x: -x[1])[:5]:
                        fm = int(ft)
                        if fm >= 1:
                            lines.append(f"    ├─ 文件 {fname}: {fm}分钟")

    # ══════════════════════════════════════
    # ── 输入活动统计 ──
    # ══════════════════════════════════════
    # 读取活跃窗口数据（含 input_data）
    active_data = get_active_data(report_date)
    input_records = active_data.get("input_data", []) if active_data else []
    if input_records:
        today_records = [r for r in input_records if r.get("date") == report_date]
        if today_records:
            total_keys = sum(r["keys"] for r in today_records)
            total_clicks = sum(r["clicks"] for r in today_records)
            total_mouse_dist = sum(r["mouse_dist"] for r in today_records)
            total_copy = sum(r.get("copy", 0) for r in today_records)
            total_paste = sum(r.get("paste", 0) for r in today_records)
            total_chars = sum(r.get("chars", 0) for r in today_records)

            # 打字活跃时段（按小时聚合）
            hourly_keys = defaultdict(int)
            for r in today_records:
                hour = r["time"][:13]  # "2026-05-26 14"
                hourly_keys[hour] += r["keys"]

            # 打字活跃时段（keys > 阈值的时段）
            active_hours = sorted(hourly_keys.items(), key=lambda x: -x[1])

            lines.append("")
            lines.append("⌨ 鼠标键盘活动")
            lines.append("=" * 38)
            lines.append(f"  ⌨ 总按键: {total_keys} 次")
            lines.append(f"  📝 输入字数: {total_chars} 字")
            lines.append(f"  🖱 总点击: {total_clicks} 次")
            lines.append(f"  📏 鼠标移动: {total_mouse_dist} 像素")
            lines.append(f"  📋 复制: {total_copy} 次")
            lines.append(f"  📄 粘贴: {total_paste} 次")

            # 活跃度曲线
            if active_hours:
                lines.append("")
                lines.append("  📈 活跃度曲线 (按键/时段):")
                max_keys = max(v for _, v in active_hours) if active_hours else 1
                for hour, keys in active_hours:
                    if keys > 0:
                        bar_len = int(keys / max(max_keys, 1) * 20)
                        bar = "█" * bar_len + "░" * (20 - bar_len)
                        hour_label = hour.split(" ")[1] + ":00"
                        lines.append(f"    {hour_label} {bar} {keys}")

    return "\n".join(lines)

def run_collect():
    """采集浏览记录"""
    state = load_state()
    last_ts = state.get("last_timestamps", {})
    today = datetime.now().strftime("%Y-%m-%d")

    all_entries = []
    new_last_ts = {}

    for browser, db_path in BROWSERS.items():
        if not os.path.exists(db_path):
            continue

        after = last_ts.get(browser)
        entries = read_browser_history(db_path, browser, after)
        print(f"  {browser}: 读取 {len(entries)} 条记录")

        if entries:
            max_ts = max(e["timestamp"] for e in entries)
            new_last_ts[browser] = int(max_ts * 1_000_000)  # 转为 WebKit 微秒
        elif browser in last_ts:
            new_last_ts[browser] = last_ts[browser]

        all_entries.extend(entries)

    # 保存新记录到当日文件
    daily_file = os.path.join(DAILY_DIR, f"{today}.json")
    existing = []
    if os.path.exists(daily_file):
        with open(daily_file, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # 合并去重（基于 url + timestamp）
    seen = set()
    merged = []
    for e in existing + all_entries:
        key = (e["url"], e.get("timestamp", 0))
        if key not in seen:
            seen.add(key)
            merged.append(e)

    merged.sort(key=lambda x: x.get("timestamp", 0))

    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # 更新状态
    state["last_timestamps"] = {**last_ts, **new_last_ts}
    state["last_run"] = datetime.now().isoformat()
    save_state(state)

    print(f"  总计: {len(all_entries)} 条新记录, 累计 {len(merged)} 条")

    return merged

def get_active_data(date_str):
    """读取活跃监控数据"""
    active_file = os.path.join(DATA_DIR, "active", f"{date_str}.json")
    if not os.path.exists(active_file):
        return None
    try:
        with open(active_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def run_report(date_str=None):
    """生成报告（含活跃时长）"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    daily_file = os.path.join(DAILY_DIR, f"{date_str}.json")
    if not os.path.exists(daily_file):
        return f"📊 {date_str} 没有找到浏览记录数据。"

    with open(daily_file, "r", encoding="utf-8") as f:
        all_entries = json.load(f)

    # 只保留当天数据
    entries = filter_today(all_entries, date_str)

    sessions = compute_browsing_sessions(entries)

    # 读取活跃窗口数据
    active_data = get_active_data(date_str)
    active_segments = active_data.get("segments", []) if active_data else []

    report = generate_hierarchical_report(entries, sessions, active_segments, date_str)

    # 保存报告
    report_file = os.path.join(DAILY_DIR, f"{date_str}_report.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    return report

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        date = sys.argv[2] if len(sys.argv) > 2 else None
        print(run_report(date))
    else:
        print("🔍 采集浏览记录...")
        entries = run_collect()
        print("✅ 采集完成")
        # 如果是手动运行，同时生成报告
        if len(sys.argv) > 1 and sys.argv[1] == "full":
            print("\n" + run_report())
