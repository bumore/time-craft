#!/usr/bin/env python3
"""
浏览器活跃标签监控 - 每30秒检测前台窗口，记录真实活跃时长
输入统计使用键盘/鼠标钩子（事件驱动，精确计数）
"""
import os
import sys
import json
import time
import ctypes
import logging
from datetime import datetime
from collections import defaultdict

# 导入钩子模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import input_hook

# ── 配置 ──
HOME = os.path.expanduser("~")
DATA_DIR = "E:\\bumoren\\time-craft\\data"
os.makedirs(DATA_DIR, exist_ok=True)

ACTIVE_DIR = os.path.join(DATA_DIR, "active")
os.makedirs(ACTIVE_DIR, exist_ok=True)

POLL_INTERVAL = 30  # 秒
IDLE_THRESHOLD = 120  # 2分钟无操作视为空闲
HEARTBEAT_FILE = os.path.join(ACTIVE_DIR, "heartbeat")
LOG_FILE = os.path.join(DATA_DIR, "active_monitor.log")
HOOK_CHECK_INTERVAL = 3  # 每N个循环检查一次钩子健康

# ── 日志 ──
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stderr),
    ]
)
log = logging.getLogger('active_monitor')

# 将日志文件路径传给 input_hook
input_hook.set_log_file(LOG_FILE)

# 浏览器标识
def parse_idea_title(title):
    """从IDEA窗口标题解析项目名、模块名、文件名"""
    # 格式: [APP:idea64.exe] putian-water [E:/putian-water] – E:\putian-water\ly-modules\ly-device\src\main\java\com\ly\mqtt\MqttTestController.java
    # 或: putian-water [E:/putian-water] – path/to/file.java - IntelliJ IDEA
    
    # 去掉 [APP:xxx.exe] 前缀
    clean = title
    if "[APP:" in clean:
        clean = clean.split("]", 1)[1].strip()
    
    project = None
    module = None
    filename = None
    
    # 提取项目名: 在 "[" 之前的第一个词
    bracket_idx = clean.find("[")
    if bracket_idx > 0:
        project = clean[:bracket_idx].strip().split(" ")[0]
    
    # 提取文件路径: 在 "–" 或 "-" 之后的部分
    for sep in ["–", " - "]:
        if sep in clean:
            parts = clean.split(sep, 1)
            if len(parts) > 1:
                file_path = parts[1].strip()
                # 去掉末尾的 " - IntelliJ IDEA"
                if " - IntelliJ IDEA" in file_path:
                    file_path = file_path.replace(" - IntelliJ IDEA", "").strip()
                
                # 提取文件名
                if file_path and ("\\" in file_path or "/" in file_path):
                    filename = file_path.replace("\\", "/").split("/")[-1]
                    
                    # 提取模块名: src 之前的路径部分
                    path_parts = file_path.replace("\\", "/").split("/")
                    src_idx = None
                    for i, p in enumerate(path_parts):
                        if p == "src":
                            src_idx = i
                            break
                    
                    if src_idx and project:
                        project_idx = None
                        for i, p in enumerate(path_parts):
                            if p == project:
                                project_idx = i
                                break
                        
                        if project_idx is not None and src_idx > project_idx:
                            module_parts = path_parts[project_idx+1:src_idx]
                            if module_parts:
                                module = "/".join(module_parts)
                elif file_path.lower() in ["terminal", "[terminal]", "terminal -"]:
                    filename = "[终端]"
                elif file_path.lower() not in ["run", "debug", "run -", "debug -"]:
                    filename = f"[{file_path}]"
            break
    
    return project, module, filename

BROWSER_SUFFIXES = {
    "Google Chrome": "Chrome",
    "Microsoft Edge": "Edge",
    "Firefox": "Firefox",
}

# ── Windows API ──
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]

# 窗口样式常量
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

def is_taskbar_window(hwnd):
    """判断窗口是否在任务栏中显示"""
    if not user32.IsWindowVisible(hwnd):
        return False
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return False
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if ex_style & WS_EX_TOOLWINDOW:
        return False
    if ex_style & WS_EX_APPWINDOW:
        return True
    owner = user32.GetWindow(hwnd, 4)  # GW_OWNER
    if owner == 0:
        return True
    return False

def get_foreground_info():
    """获取前台窗口信息"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None, None

    # 窗口标题
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return None, None, None
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    # 进程ID
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    return hwnd, title, pid.value

def get_idle_seconds():
    """获取用户空闲时间（秒）"""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if user32.GetLastInputInfo(ctypes.byref(lii)):
        elapsed = kernel32.GetTickCount() - lii.dwTime
        return elapsed / 1000.0
    return 0

def parse_browser_title(title):
    """从窗口标题解析浏览器和标签标题"""
    for suffix, browser_name in BROWSER_SUFFIXES.items():
        if title.endswith(f" - {suffix}"):
            tab_title = title[:-(len(suffix) + 3)].strip()
            return browser_name, tab_title
    return None, None

def get_process_name(pid):
    """获取进程名"""
    try:
        import psutil
        return psutil.Process(pid).name()
    except (ImportError, Exception):
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "process", "where", f"ProcessId={pid}", "get", "Name", "/value"],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("Name="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return "unknown"

def load_today_log():
    """加载今日活跃记录"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(ACTIVE_DIR, f"{today}.json")
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"segments": [], "input_data": [], "summary": {}}

def save_today_log(log_data):
    """保存今日活跃记录"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(ACTIVE_DIR, f"{today}.json")
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)


def write_heartbeat(segments_count=0):
    """写心跳文件，供 watchdog 检测"""
    try:
        hb = {
            "ts": time.time(),
            "pid": os.getpid(),
            "hooks_alive": input_hook.is_alive(),
            "segments": segments_count,
        }
        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            json.dump(hb, f)
    except Exception:
        pass

def enrich_segment(seg):
    """为段添加IDEA项目/模块/文件信息"""
    title = seg.get("title", "")
    if "IntelliJ IDEA" in title or ("[APP:" in title and "idea64" in title.lower()):
        project, module, filename = parse_idea_title(title)
        if project:
            seg["idea_project"] = project
        if module:
            seg["idea_module"] = module
        if filename:
            seg["idea_file"] = filename
    return seg

def run_monitor():
    """主监控循环（持续运行）"""
    log.info(f"活跃标签监控已启动 (每{POLL_INTERVAL}秒检测，钩子模式，空闲阈值{IDLE_THRESHOLD}秒)")
    log.info(f"日志文件: {LOG_FILE}")
    log.info(f"心跳文件: {HEARTBEAT_FILE}")

    # 启动键盘/鼠标钩子
    input_hook.start()
    log.info("键盘/鼠标钩子已启动")

    log_data = load_today_log()
    segments = log_data.get("segments", [])

    # 当前状态
    current_title = None
    current_browser = None
    current_start = None
    last_save_time = time.time()
    loop_count = 0
    last_hook_check = 0
    hook_restart_count = 0
    MAX_HOOK_RESTARTS = 10  # 单次运行最大重启次数，防止无限重启

    try:
        while True:
            loop_count += 1
            now = time.time()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # ── 钩子健康检查（每 HOOK_CHECK_INTERVAL 个循环）──
            if loop_count - last_hook_check >= HOOK_CHECK_INTERVAL:
                last_hook_check = loop_count
                if not input_hook.is_alive():
                    if hook_restart_count < MAX_HOOK_RESTARTS:
                        hook_restart_count += 1
                        log.warning(f"钩子不健康，尝试重启 (第{hook_restart_count}次)...")
                        if input_hook.restart():
                            log.info("钩子重启成功")
                        else:
                            log.error("钩子重启失败")
                    else:
                        log.error(f"钩子已重启{MAX_HOOK_RESTARTS}次仍不稳定，跳过健康检查")

            # ── 写心跳 ──
            write_heartbeat(len(segments))

            # 检查是否跨天，如果是则保存并重置
            today = datetime.now().strftime("%Y-%m-%d")
            if segments and segments[-1].get("date") != today:
                log_data["segments"] = segments
                save_today_log(log_data)
                segments = []
                log_data = {"segments": [], "summary": {}}
                log.info(f"跨天重置，新日期: {today}")

            # 检查空闲
            idle = get_idle_seconds()
            if idle > IDLE_THRESHOLD:
                if current_title:
                    # 用户离开了，结束当前段
                    duration = now - current_start
                    if duration >= 10:  # 至少10秒才算
                        segments.append(enrich_segment({
                            "title": current_title,
                            "browser": current_browser,
                            "start": datetime.fromtimestamp(current_start).strftime("%Y-%m-%d %H:%M:%S"),
                            "end": now_str,
                            "duration_sec": int(duration),
                            "date": today,
                        }))
                    current_title = None
                    current_browser = None
                    current_start = None
                time.sleep(POLL_INTERVAL)
                continue

            # 获取前台窗口
            hwnd, title, pid = get_foreground_info()

            # 过滤系统窗口（只排除桌面和无标题窗口）
            if not title or len(title) < 3:
                time.sleep(POLL_INTERVAL)
                continue

            if title and title != current_title:
                # 窗口切换了
                if current_title and current_start:
                    duration = now - current_start
                    if duration >= 10:
                        segments.append(enrich_segment({
                            "title": current_title,
                            "browser": current_browser,
                            "start": datetime.fromtimestamp(current_start).strftime("%Y-%m-%d %H:%M:%S"),
                            "end": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
                            "duration_sec": int(duration),
                            "date": today,
                        }))

                # 检测是否是浏览器
                browser, tab_title = parse_browser_title(title)
                if browser:
                    current_title = tab_title
                    current_browser = browser
                else:
                    # 非浏览器窗口，记录为桌面应用
                    proc_name = get_process_name(pid) if pid else "unknown"
                    current_title = f"[APP:{proc_name}] {title}"
                    current_browser = None

                current_start = now

            # 定期保存（每60秒）
            if now - last_save_time > 60:
                log_data["segments"] = segments
                save_today_log(log_data)
                last_save_time = now
                active_count = len(segments)
                if current_title:
                    elapsed = int(now - current_start)
                    log.info(f"当前: {current_title[:40]} ({elapsed}s) | 累计段数: {active_count}")

            # 从钩子读取输入计数并重置
            counters = input_hook.read_counters(reset=True)
            mouse_dist = input_hook.get_mouse_distance_and_reset()

            input_data = log_data.get("input_data", [])
            input_data.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "keys": counters["keys"],
                "clicks": counters["clicks"],
                "scroll_up": counters["scroll_up"],
                "scroll_down": counters["scroll_down"],
                "mouse_dist": mouse_dist,
                "copy": counters["copy"],
                "paste": counters["paste"],
                "chars": counters["chars"],
                "app": current_title.split("] ")[-1][:30] if current_title else None,
                "date": today,
            })
            log_data["input_data"] = input_data

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        # 停止钩子
        input_hook.stop()

        # 保存最后一段
        if current_title and current_start:
            duration = time.time() - current_start
            if duration >= 10:
                segments.append(enrich_segment({
                    "title": current_title,
                    "browser": current_browser,
                    "start": datetime.fromtimestamp(current_start).strftime("%Y-%m-%d %H:%M:%S"),
                    "end": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_sec": int(duration),
                    "date": datetime.now().strftime("%Y-%m-%d"),
                }))
        log_data["segments"] = segments
        save_today_log(log_data)
        log.info(f"监控已停止 (Ctrl+C)，共记录 {len(segments)} 个活跃段")

    except Exception as e:
        log.error(f"主循环未捕获异常: {e}", exc_info=True)
        # 尝试保存数据
        try:
            log_data["segments"] = segments
            save_today_log(log_data)
            log.info("异常后数据已保存")
        except Exception as save_err:
            log.error(f"异常后保存数据失败: {save_err}")

def generate_active_report(date_str=None):
    """生成活跃时长报告"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    log_file = os.path.join(ACTIVE_DIR, f"{date_str}.json")
    if not os.path.exists(log_file):
        return f"📊 {date_str} 没有活跃监控数据（监控服务可能未运行）"

    with open(log_file, "r", encoding="utf-8") as f:
        log_data = json.load(f)

    segments = log_data.get("segments", [])
    if not segments:
        return f"📊 {date_str} 没有记录到活跃时段"

    # 统计
    total_active = sum(s["duration_sec"] for s in segments)
    browser_time = defaultdict(float)
    title_time = defaultdict(float)

    for s in segments:
        dur_min = s["duration_sec"] / 60
        if s.get("browser"):
            browser_time[s["browser"]] += dur_min
            title_time[s["title"]] += dur_min
        else:
            # 非浏览器应用
            app_name = s["title"].split("]")[0].replace("[APP:", "") if "[APP:" in s["title"] else s["title"][:30]
            title_time[f"[桌面] {app_name}"] += dur_min

    # 格式化
    lines = []
    lines.append(f"🖥 {date_str} 活跃时长报告")
    lines.append("=" * 35)

    hours = int(total_active // 3600)
    mins = int((total_active % 3600) // 60)
    time_str = f"{hours}小时{mins}分钟" if hours > 0 else f"{mins}分钟"
    lines.append(f"⏱ 总活跃时长: {time_str}")
    lines.append(f"📊 活跃段数: {len(segments)}")
    lines.append("")

    # 浏览器分布
    if browser_time:
        lines.append("🌐 浏览器分布:")
        lines.append("-" * 35)
        for browser, t in sorted(browser_time.items(), key=lambda x: -x[1]):
            m = int(t)
            pct = t / (total_active / 60) * 100 if total_active > 0 else 0
            lines.append(f"  {browser}: {m}分钟 ({pct:.0f}%)")
        lines.append("")

    # Top 活跃窗口
    lines.append("🔝 最活跃的页面/应用:")
    lines.append("-" * 35)
    top_items = sorted(title_time.items(), key=lambda x: -x[1])[:15]
    for i, (title, t) in enumerate(top_items, 1):
        m = int(t)
        if m >= 1:
            lines.append(f"  {i}. {title[:45]}  ({m}分钟)")
    lines.append("")

    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        date = sys.argv[2] if len(sys.argv) > 2 else None
        print(generate_active_report(date))
    else:
        run_monitor()
