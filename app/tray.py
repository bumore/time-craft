#!/usr/bin/env python3
"""
TimeCraft 托盘图标模块
- 托盘图标 + 右键菜单
- 实时数据展示
- 报告弹窗（tkinter）
- 启停监控
"""
import os
import sys
import json
import threading
from datetime import datetime
from PIL import Image, ImageDraw
import pystray
try:
    from report_window import show_report_window
except ModuleNotFoundError:
    from app.report_window import show_report_window

# 路径配置：打包后用 exe 所在目录，开发时用脚本目录
if getattr(sys, 'frozen', False):
    PROJECT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
ACTIVE_DIR = os.path.join(DATA_DIR, "active")
PIXELS_PER_METER = 96 * 39.37007874


def load_today_data():
    """加载今日活跃数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(ACTIVE_DIR, f"{today}.json")
    if not os.path.exists(file_path):
        return {"segments": [], "input_data": []}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"segments": [], "input_data": []}
        return data
    except Exception:
        return {"segments": [], "input_data": []}


def summarize_clicks(input_data):
    """汇总点击数，兼容旧数据。"""
    total_clicks = 0
    left_clicks = 0
    right_clicks = 0
    for record in input_data:
        if "left_clicks" in record or "right_clicks" in record:
            left = record.get("left_clicks", 0)
            right = record.get("right_clicks", 0)
            left_clicks += left
            right_clicks += right
            total_clicks += left + right
        else:
            total_clicks += record.get("clicks", 0)
    return total_clicks, left_clicks, right_clicks


def summarize_scrolls(input_data):
    """汇总滚轮次数。"""
    total_scroll_up = sum(record.get("scroll_up", 0) for record in input_data)
    total_scroll_down = sum(record.get("scroll_down", 0) for record in input_data)
    return total_scroll_up, total_scroll_down, total_scroll_up + total_scroll_down


def format_mouse_distance(mouse_dist):
    """格式化鼠标移动距离，附带米制近似值。"""
    meters = mouse_dist / PIXELS_PER_METER
    return f"{mouse_dist} 像素 (约{meters:.2f}米)"


def normalize_app_name(app_name):
    """统一程序展示名，去掉可读性差的 .exe 后缀。"""
    if not isinstance(app_name, str):
        return "未知"
    name = app_name.strip()
    if name.lower().endswith(".exe"):
        name = name[:-4]
    return name or "未知"


def build_report_model():
    """构建报告数据模型。"""
    data = load_today_data()
    segments = data.get("segments", [])
    input_data = data.get("input_data", [])

    total_sec = sum(s.get("duration_sec", 0) for s in segments)
    total_keys = sum(d.get("keys", 0) for d in input_data)
    total_clicks, left_clicks, right_clicks = summarize_clicks(input_data)
    total_scroll_up, total_scroll_down, total_scroll = summarize_scrolls(input_data)
    total_chars = sum(d.get("chars", 0) for d in input_data)
    total_mouse_dist = sum(d.get("mouse_dist", 0) for d in input_data)
    total_copy = sum(d.get("copy", 0) for d in input_data)
    total_paste = sum(d.get("paste", 0) for d in input_data)

    app_time = {}
    browser_pages = {}
    for s in segments:
        title = s.get("title", "未知")
        browser = s.get("browser")
        if browser:
            app = browser
            browser_pages.setdefault(browser, {})
            browser_pages[browser][title] = browser_pages[browser].get(title, 0) + s.get("duration_sec", 0)
        elif "[APP:" in title:
            app = title.split("]")[0].replace("[APP:", "")
        elif " - " in title:
            app = title.split(" - ")[-1]
        else:
            app = title[:20]
        app = browser or normalize_app_name(app)
        app_time[app] = app_time.get(app, 0) + s.get("duration_sec", 0)

    app_items = []
    for app, sec in sorted(app_time.items(), key=lambda x: -x[1])[:10]:
        pct = (sec / total_sec * 100) if total_sec > 0 else 0
        pages = []
        if app in browser_pages:
            for page, page_sec in sorted(browser_pages[app].items(), key=lambda x: -x[1])[:5]:
                pages.append({
                    "name": page,
                    "duration": format_duration(page_sec),
                    "pct": (page_sec / sec * 100) if sec > 0 else 0,
                })
        app_items.append({
            "name": app,
            "duration": format_duration(sec),
            "pct": pct,
            "is_browser": app in browser_pages,
            "pages": pages,
        })

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "segments": segments,
        "total_sec": total_sec,
        "total_duration": format_duration(total_sec),
        "segments_count": len(segments),
        "keyboard": {
            "total_keys": total_keys,
            "total_chars": total_chars,
        },
        "clipboard": {
            "copy": total_copy,
            "paste": total_paste,
        },
        "mouse": {
            "total_clicks": total_clicks,
            "left_clicks": left_clicks,
            "right_clicks": right_clicks,
            "total_scroll": total_scroll,
            "scroll_up": total_scroll_up,
            "scroll_down": total_scroll_down,
            "distance": format_mouse_distance(total_mouse_dist),
        },
        "apps": app_items,
    }


def get_realtime_stats():
    """获取实时统计数据"""
    report = build_report_model()
    return {
        "total_sec": report["total_sec"],
        "total_keys": report["keyboard"]["total_keys"],
        "total_chars": report["keyboard"]["total_chars"],
        "total_clicks": report["mouse"]["total_clicks"],
        "left_clicks": report["mouse"]["left_clicks"],
        "right_clicks": report["mouse"]["right_clicks"],
        "total_scroll_up": report["mouse"]["scroll_up"],
        "total_scroll_down": report["mouse"]["scroll_down"],
        "total_scroll": report["mouse"]["total_scroll"],
        "total_mouse_dist": report["mouse"]["distance"],
        "segments_count": report["segments_count"],
    }


def format_duration(seconds):
    """格式化时长"""
    if seconds < 60:
        return f"{seconds}s"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m"


def trim_text(text, max_length):
    """截断过长文本，避免报告窗口频繁换行。"""
    if text is None:
        return ""
    text = str(text).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def append_report_section(lines, title, rows):
    """追加统一样式的报告分组。"""
    if lines and lines[-1] != "":
        lines.append("")
    lines.append(title)
    for row in rows:
        lines.append(f"  {row}")


def format_metric_rows(pairs, columns=2, prefix=""):
    """将指标拆成更易扫读的多行。"""
    visible_pairs = [(label, value) for label, value in pairs if value is not None and value != ""]
    rows = []
    for index in range(0, len(visible_pairs), columns):
        chunk = visible_pairs[index : index + columns]
        cells = [f"{label}：{value}" for label, value in chunk]
        rows.append(f"{prefix}{'    '.join(cells)}")
    return rows


def create_icon_image():
    """创建托盘图标"""
    # 64x64 的简单图标
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 画一个圆形背景
    draw.ellipse([4, 4, 60, 60], fill=(52, 152, 219, 255))  # 蓝色

    # 画一个时钟指针
    draw.line([(32, 32), (32, 16)], fill="white", width=3)  # 时针
    draw.line([(32, 32), (44, 32)], fill="white", width=2)  # 分针

    return img


def generate_report():
    """生成今日报告文本"""
    report = build_report_model()
    segments = report["segments"]

    if not segments:
        return "TimeCraft 效率报告\n\n今日暂无监控数据"

    lines = [f"TimeCraft 效率报告", report["date"]]

    append_report_section(
        lines,
        "⚡ 活跃概览",
        format_metric_rows(
            [
                ("总活跃时长", report["total_duration"]),
                ("活跃段数", report["segments_count"]),
            ],
            columns=2,
        ),
    )
    append_report_section(
        lines,
        "⌨️ 键盘统计",
        format_metric_rows(
            [
                ("总按键", f"{report['keyboard']['total_keys']} 次"),
                ("字符键", f"{report['keyboard']['total_chars']} 次"),
            ],
            columns=2,
        ),
    )
    append_report_section(
        lines,
        "📋 剪贴板统计",
        format_metric_rows(
            [
                ("复制", f"{report['clipboard']['copy']} 次"),
                ("粘贴", f"{report['clipboard']['paste']} 次"),
            ],
            columns=2,
        ),
    )
    append_report_section(
        lines,
        "🖱️ 鼠标统计",
        format_metric_rows(
            [
                ("总点击", f"{report['mouse']['total_clicks']} 次"),
                ("左键", f"{report['mouse']['left_clicks']} 次"),
                ("右键", f"{report['mouse']['right_clicks']} 次"),
                ("滚轮", f"{report['mouse']['total_scroll']} 次"),
                ("向上", f"{report['mouse']['scroll_up']} 次"),
                ("向下", f"{report['mouse']['scroll_down']} 次"),
                ("移动", report["mouse"]["distance"]),
            ],
            columns=2,
        ),
    )

    if lines[-1] != "":
        lines.append("")
    lines.append("💻 程序统计")
    if not report["apps"]:
        lines.append("  暂无程序活跃记录")
    for item in report["apps"]:
        app_name = trim_text(item["name"], 26)
        lines.append(f"  ■ {app_name}")
        for row in format_metric_rows(
            [
                ("时长", item["duration"]),
                ("占比", f"{item['pct']:.1f}%"),
            ],
            columns=2,
            prefix="    ▸ ",
        ):
            lines.append(row)
        for page in item["pages"]:
            page_name = trim_text(page["name"], 36)
            lines.append(f"    ↳ {page_name}")
            lines.append(f"      时长：{page['duration']}")
        lines.append("")

    if lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


class TrayApp:
    """托盘应用类"""

    def __init__(self, monitor_manager):
        self.monitor = monitor_manager
        self.icon = None
        self._update_timer = None

    def create_menu(self):
        """创建右键菜单"""
        stats = get_realtime_stats()
        duration_str = format_duration(stats["total_sec"])

        return pystray.Menu(
            # 实时数据（不可点击）
            pystray.MenuItem(
                f"⏱ 活跃: {duration_str}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            # 查看报告
            pystray.MenuItem("📋 查看报告", self.show_report),
            pystray.Menu.SEPARATOR,
            # 退出
            pystray.MenuItem("❌ 退出", self.quit_app),
        )

    def update_menu(self):
        """定时更新菜单"""
        if self.icon:
            self.icon.update_menu()
        # 每5秒更新一次
        self._update_timer = threading.Timer(5.0, self.update_menu)
        self._update_timer.daemon = True
        self._update_timer.start()

    def show_report(self, icon=None, item=None):
        """显示报告弹窗"""
        report_data = build_report_model()
        show_report_window(report_data, "TimeCraft 效率报告")

    def quit_app(self, icon=None, item=None):
        """退出应用"""
        if self._update_timer:
            self._update_timer.cancel()
        self.monitor.stop()
        # 强制退出整个进程
        os._exit(0)

    def run(self):
        """运行托盘应用"""
        image = create_icon_image()
        self.icon = pystray.Icon(
            "time-craft",
            image,
            "TimeCraft 效率监控",
            menu=self.create_menu(),
        )

        # 启动菜单更新定时器
        self.update_menu()

        # 运行（阻塞）
        self.icon.run()
