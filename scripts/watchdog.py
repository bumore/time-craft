#!/usr/bin/env python3
"""
active_monitor 守护进程（watchdog）

每60秒检查一次 active_monitor 的心跳文件。
如果心跳超过120秒未更新，说明主进程卡死，自动杀死并重启。

心跳文件: E:/bumoren/time-craft/data/active/heartbeat
日志文件: E:/bumoren/time-craft/data/watchdog.log

用法:
  python watchdog.py          # 前台运行
  pythonw watchdog.py         # 后台运行（无窗口）
"""
import os
import sys
import json
import time
import subprocess
import logging
from datetime import datetime

# ── 配置 ──
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
HEARTBEAT_FILE = os.path.join(DATA_DIR, "active", "heartbeat")
LOG_FILE = os.path.join(DATA_DIR, "watchdog.log")
MONITOR_SCRIPT = os.path.join(SCRIPTS_DIR, "active_monitor.py")

CHECK_INTERVAL = 60     # 检查间隔（秒）
HEARTBEAT_TIMEOUT = 120  # 心跳超时阈值（秒）
MAX_RESTARTS = 20        # 单日最大重启次数
COOLDOWN_AFTER_RESTART = 30  # 重启后等待时间（秒）

# ── 日志 ──
os.makedirs(DATA_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stderr),
    ]
)
log = logging.getLogger('watchdog')


def read_heartbeat():
    """读取心跳文件"""
    try:
        if not os.path.exists(HEARTBEAT_FILE):
            return None
        with open(HEARTBEAT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def is_heartbeat_stale(hb):
    """检查心跳是否过期"""
    if not hb or 'ts' not in hb:
        return True
    elapsed = time.time() - hb['ts']
    return elapsed > HEARTBEAT_TIMEOUT


def find_monitor_process():
    """查找 active_monitor.py 进程"""
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where',
             f"commandline like '%active_monitor%' and commandline not like '%watchdog%'",
             'get', 'processid,commandline', '/format:list'],
            capture_output=True, text=True, encoding='gbk', timeout=10
        )
        pids = []
        for line in result.stdout.strip().split('\n'):
            if line.startswith('ProcessId='):
                pid = line.split('=')[1].strip()
                if pid and pid.isdigit():
                    pids.append(int(pid))
        return pids
    except Exception as e:
        log.error(f"查找进程失败: {e}")
        return []


def kill_process(pid):
    """杀死进程"""
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                      capture_output=True, timeout=10)
        log.info(f"已杀死进程 PID={pid}")
        return True
    except Exception as e:
        log.error(f"杀死进程 PID={pid} 失败: {e}")
        return False


def start_monitor():
    """启动 active_monitor.py"""
    try:
        # 使用 pythonw 无窗口启动，或 python -u
        proc = subprocess.Popen(
            [sys.executable, '-u', MONITOR_SCRIPT],
            cwd=SCRIPTS_DIR,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
        log.info(f"已启动 active_monitor.py (PID={proc.pid})")
        return proc.pid
    except Exception as e:
        log.error(f"启动 active_monitor.py 失败: {e}")
        return None


def write_watchdog_heartbeat():
    """写watchdog自己的心跳"""
    try:
        hb = {
            "ts": time.time(),
            "pid": os.getpid(),
            "type": "watchdog",
        }
        hb_file = os.path.join(DATA_DIR, "watchdog_heartbeat")
        with open(hb_file, 'w', encoding='utf-8') as f:
            json.dump(hb, f)
    except Exception:
        pass


def run():
    """主循环"""
    log.info(f"Watchdog 已启动 (PID={os.getpid()})")
    log.info(f"检查间隔: {CHECK_INTERVAL}s, 心跳超时: {HEARTBEAT_TIMEOUT}s")
    log.info(f"监控脚本: {MONITOR_SCRIPT}")
    log.info(f"心跳文件: {HEARTBEAT_FILE}")

    today = datetime.now().strftime('%Y-%m-%d')
    restart_count = 0

    while True:
        try:
            # 跨天重置重启计数
            new_day = datetime.now().strftime('%Y-%m-%d')
            if new_day != today:
                today = new_day
                restart_count = 0
                log.info(f"跨天，重启计数已重置")

            # 写watchdog心跳
            write_watchdog_heartbeat()

            # 读取 active_monitor 心跳
            hb = read_heartbeat()

            if is_heartbeat_stale(hb):
                log.warning(f"心跳过期或不存在 (last_hb={hb})")

                # 查找现有进程
                pids = find_monitor_process()
                if pids:
                    log.warning(f"发现 active_monitor 进程: {pids}，心跳过期，判定为卡死")
                    for pid in pids:
                        kill_process(pid)
                    time.sleep(2)

                # 检查重启次数
                if restart_count >= MAX_RESTARTS:
                    log.error(f"今日已重启 {restart_count} 次，达到上限，不再重启。等待人工介入。")
                    time.sleep(CHECK_INTERVAL * 5)  # 长等待
                    continue

                # 启动新进程
                restart_count += 1
                log.info(f"正在启动 active_monitor (第{restart_count}次)...")
                new_pid = start_monitor()
                if new_pid:
                    log.info(f"等待 {COOLDOWN_AFTER_RESTART}s 让新进程初始化...")
                    time.sleep(COOLDOWN_AFTER_RESTART)

                    # 验证新进程是否正常
                    new_hb = read_heartbeat()
                    if new_hb and not is_heartbeat_stale(new_hb):
                        log.info(f"新进程心跳正常 (pid={new_hb.get('pid')})")
                    else:
                        log.warning(f"新进程心跳仍不正常，将继续监控")
                else:
                    log.error("启动失败，等待下次检查")
            else:
                # 心跳正常
                hooks_ok = hb.get('hooks_alive', False)
                seg_count = hb.get('segments', 0)
                pid = hb.get('pid', '?')
                if not hooks_ok:
                    log.warning(f"进程活着(pid={pid})但钩子不健康, segments={seg_count}")
                # 正常时不打印，减少日志噪音

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            log.info("Watchdog 被 Ctrl+C 停止")
            break
        except Exception as e:
            log.error(f"Watchdog 循环异常: {e}", exc_info=True)
            time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    run()
