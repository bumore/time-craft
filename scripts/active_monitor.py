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
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ACTIVE_DIR = os.path.join(DATA_DIR, "active")
os.makedirs(ACTIVE_DIR, exist_ok=True)

POLL_INTERVAL = 30  # 秒
IDLE_THRESHOLD = 120  # 2分钟无操作视为空闲
HEARTBEAT_FILE = os.path.join(ACTIVE_DIR, "heartbeat")
LOG_FILE = os.path.join(DATA_DIR, "active_monitor.log")
HOOK_CHECK_INTERVAL = 3  # 每N个循环检查一次输入采样器健康
ENABLE_INPUT_STATS = os.environ.get("TIMECRAFT_ENABLE_INPUT_STATS", "1") != "0"
PIXELS_PER_METER = 96 * 39.37007874

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
    return load_log_for_date(datetime.now().strftime("%Y-%m-%d"))


def load_log_for_date(date_str):
    """加载指定日期的活跃记录"""
    log_file = os.path.join(ACTIVE_DIR, f"{date_str}.json")
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"segments": [], "input_data": [], "summary": {}}


def save_log_for_date(log_data, date_str):
    """保存指定日期的活跃记录"""
    log_file = os.path.join(ACTIVE_DIR, f"{date_str}.json")
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)


def write_heartbeat(segments_count=0):
    """写心跳文件，供 watchdog 检测"""
    try:
        hb = {
            "ts": time.time(),
            "pid": os.getpid(),
            "hooks_alive": True if not ENABLE_INPUT_STATS else input_hook.is_alive(),
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


def append_segment(segments, title, browser, start_ts, end_ts, date_str):
    """将一个活跃段追加到结果中。"""
    duration = end_ts - start_ts
    if duration < 10:
        return
    segments.append(enrich_segment({
        "title": title,
        "browser": browser,
        "start": datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S"),
        "end": datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d %H:%M:%S"),
        "duration_sec": int(duration),
        "date": date_str,
    }))


def format_mouse_distance(mouse_dist):
    """格式化鼠标移动距离，附带米制近似值。"""
    meters = mouse_dist / PIXELS_PER_METER
    return f"{mouse_dist} 像素 (约{meters:.2f}米)"


def wait_or_stop(stop_event, timeout):
    """等待下一轮轮询；如果收到停止信号则返回 True。"""
    if stop_event is None:
        time.sleep(timeout)
        return False
    return stop_event.wait(timeout)


def run_monitor(stop_event=None):
    """主监控循环（持续运行）"""
    log.info(f"活跃标签监控已启动 (每{POLL_INTERVAL}秒检测，空闲阈值{IDLE_THRESHOLD}秒)")
    log.info(f"日志文件: {LOG_FILE}")
    log.info(f"心跳文件: {HEARTBEAT_FILE}")
    log.info(f"输入统计: {'开启' if ENABLE_INPUT_STATS else '关闭'}")

    if ENABLE_INPUT_STATS:
        input_hook.start()
        log.info("输入采样器已启动")
    else:
        log.warning("已禁用输入统计，相关数据将显示为 0")

    current_log_date = datetime.now().strftime("%Y-%m-%d")
    log_data = load_log_for_date(current_log_date)
    segments = log_data.get("segments", [])
    log_data.setdefault("input_data", [])

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
        while not (stop_event and stop_event.is_set()):
            loop_count += 1
            now_dt = datetime.now()
            now = time.time()
            today = now_dt.strftime("%Y-%m-%d")
            now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

            if today != current_log_date:
                day_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                day_start_ts = day_start.timestamp()
                if current_title and current_start and current_start < day_start_ts:
                    append_segment(
                        segments,
                        current_title,
                        current_browser,
                        current_start,
                        day_start_ts,
                        current_log_date,
                    )
                    current_start = day_start_ts

                log_data["segments"] = segments
                save_log_for_date(log_data, current_log_date)
                current_log_date = today
                log_data = load_log_for_date(current_log_date)
                log_data.setdefault("input_data", [])
                segments = log_data.get("segments", [])
                log.info(f"跨天重置，新日期: {current_log_date}")

            # ── 钩子健康检查（每 HOOK_CHECK_INTERVAL 个循环）──
            if ENABLE_INPUT_STATS and loop_count - last_hook_check >= HOOK_CHECK_INTERVAL:
                last_hook_check = loop_count
                if not input_hook.is_alive():
                    if hook_restart_count < MAX_HOOK_RESTARTS:
                        hook_restart_count += 1
                        log.warning(f"输入采样器不健康，尝试重启 (第{hook_restart_count}次)...")
                        if input_hook.restart():
                            log.info("输入采样器重启成功")
                        else:
                            log.error("输入采样器重启失败")
                    else:
                        log.error(f"输入采样器已重启{MAX_HOOK_RESTARTS}次仍不稳定，跳过健康检查")

            # ── 写心跳 ──
            write_heartbeat(len(segments))

            # 检查空闲
            idle = get_idle_seconds()
            if idle > IDLE_THRESHOLD:
                if current_title:
                    # 用户离开了，结束当前段
                    append_segment(
                        segments,
                        current_title,
                        current_browser,
                        current_start,
                        now,
                        current_log_date,
                    )
                    current_title = None
                    current_browser = None
                    current_start = None
                if wait_or_stop(stop_event, POLL_INTERVAL):
                    break
                continue

            # 获取前台窗口
            hwnd, title, pid = get_foreground_info()

            # 过滤系统窗口（只排除桌面和无标题窗口）
            if not title or len(title) < 3:
                if wait_or_stop(stop_event, POLL_INTERVAL):
                    break
                continue

            if title and title != current_title:
                # 窗口切换了
                if current_title and current_start:
                    append_segment(
                        segments,
                        current_title,
                        current_browser,
                        current_start,
                        now,
                        current_log_date,
                    )

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
                save_log_for_date(log_data, current_log_date)
                last_save_time = now
                active_count = len(segments)
                if current_title:
                    elapsed = int(now - current_start)
                    log.info(f"当前: {current_title[:40]} ({elapsed}s) | 累计段数: {active_count}")

            # 读取输入计数并重置
            if ENABLE_INPUT_STATS:
                counters = input_hook.read_counters(reset=True)
                mouse_dist = input_hook.get_mouse_distance_and_reset()
            else:
                counters = {
                    "keys": 0,
                    "clicks": 0,
                    "left_clicks": 0,
                    "right_clicks": 0,
                    "scroll_up": 0,
                    "scroll_down": 0,
                    "copy": 0,
                    "paste": 0,
                    "chars": 0,
                }
                mouse_dist = 0

            input_data = log_data.get("input_data", [])
            input_data.append({
                "time": now_str,
                "keys": counters["keys"],
                "clicks": counters["clicks"],
                "left_clicks": counters["left_clicks"],
                "right_clicks": counters["right_clicks"],
                "scroll_up": counters["scroll_up"],
                "scroll_down": counters["scroll_down"],
                "mouse_dist": mouse_dist,
                "copy": counters["copy"],
                "paste": counters["paste"],
                "chars": counters["chars"],
                "app": current_title.split("] ")[-1][:30] if current_title else None,
                "date": current_log_date,
            })
            log_data["input_data"] = input_data

            if wait_or_stop(stop_event, POLL_INTERVAL):
                break

    except KeyboardInterrupt:
        log.info("监控收到 Ctrl+C，准备退出")

    except Exception as e:
        log.error(f"主循环未捕获异常: {e}", exc_info=True)
    finally:
        if ENABLE_INPUT_STATS:
            try:
                input_hook.stop()
            except Exception as stop_err:
                log.error(f"停止输入采样器失败: {stop_err}")

        end_dt = datetime.now()
        end_ts = end_dt.timestamp()
        end_date = end_dt.strftime("%Y-%m-%d")
        if end_date != current_log_date:
            day_start = end_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            day_start_ts = day_start.timestamp()
            if current_title and current_start and current_start < day_start_ts:
                append_segment(
                    segments,
                    current_title,
                    current_browser,
                    current_start,
                    day_start_ts,
                    current_log_date,
                )
                current_start = day_start_ts
            log_data["segments"] = segments
            try:
                save_log_for_date(log_data, current_log_date)
            except Exception as save_err:
                log.error(f"退出前保存 {current_log_date} 数据失败: {save_err}")
            current_log_date = end_date
            log_data = load_log_for_date(current_log_date)
            log_data.setdefault("input_data", [])
            segments = log_data.get("segments", [])

        if current_title and current_start:
            append_segment(
                segments,
                current_title,
                current_browser,
                current_start,
                end_ts,
                current_log_date,
            )

        log_data["segments"] = segments
        try:
            save_log_for_date(log_data, current_log_date)
            log.info(f"监控已停止，共记录 {len(segments)} 个活跃段")
        except Exception as save_err:
            log.error(f"退出前保存数据失败: {save_err}")

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
