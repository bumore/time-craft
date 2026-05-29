#!/usr/bin/env python3
"""
TimeCraft 托盘应用入口
- 启动监控线程
- 启动托盘图标
- 管理生命周期
"""
import os
import sys
import threading
import signal
import logging

# 路径配置：打包后用 exe 所在目录，开发时用脚本目录
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后：exe 所在目录
    PROJECT_DIR = os.path.dirname(sys.executable)
    SCRIPTS_DIR = os.path.join(sys._MEIPASS, "scripts")
else:
    # 开发模式：脚本所在目录的上级
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
    SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

# 数据目录
DATA_DIR = os.path.join(PROJECT_DIR, "data")

# 导入现有模块
import active_monitor

# 导入托盘模块
from tray import TrayApp

ACTIVE_DIR = os.path.join(DATA_DIR, "active")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ACTIVE_DIR, exist_ok=True)

LOG_FILE = os.path.join(DATA_DIR, "app.log")
log = logging.getLogger("timecraft")


def _configure_logger(log_file):
    """为托盘主进程配置独立日志，避免被其他模块的 basicConfig 吞掉。"""
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    for handler in list(log.handlers):
        log.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    log.setLevel(logging.INFO)
    log.propagate = False

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    log.addHandler(stream_handler)


_configure_logger(LOG_FILE)
active_monitor.configure_runtime_paths(
    data_dir=DATA_DIR,
    log_file=os.path.join(DATA_DIR, "active_monitor.log"),
)


class MonitorManager:
    """监控管理器"""

    def __init__(self):
        self._monitor_thread = None
        self._running = False
        self._lock = threading.Lock()
        self._stop_event = None

    def is_running(self):
        """检查监控是否在运行"""
        return bool(
            self._running
            and self._monitor_thread
            and self._monitor_thread.is_alive()
        )

    def start(self):
        """启动监控"""
        with self._lock:
            if self._monitor_thread and self._monitor_thread.is_alive():
                log.warning("监控已在运行")
                return

            log.info("启动监控...")
            self._running = True
            self._stop_event = threading.Event()

            # 在新线程中启动监控
            self._monitor_thread = threading.Thread(
                target=self._run_monitor,
                args=(self._stop_event,),
                daemon=True,
                name="monitor-thread",
            )
            self._monitor_thread.start()

    def _run_monitor(self, stop_event):
        """监控线程入口"""
        current_thread = threading.current_thread()
        try:
            active_monitor.configure_runtime_paths(
                data_dir=DATA_DIR,
                log_file=os.path.join(DATA_DIR, "active_monitor.log"),
            )
            active_monitor.run_monitor(stop_event=stop_event)
        except Exception as e:
            log.error(f"监控线程异常: {e}", exc_info=True)
        finally:
            with self._lock:
                self._running = False
                if self._monitor_thread is current_thread:
                    self._monitor_thread = None
                if self._stop_event is stop_event:
                    self._stop_event = None
            log.info("监控线程已退出")

    def stop(self):
        """停止监控"""
        with self._lock:
            thread = self._monitor_thread
            stop_event = self._stop_event
            if not thread or not thread.is_alive():
                self._running = False
                self._monitor_thread = None
                self._stop_event = None
                return

            log.info("停止监控...")
            self._running = False
            if stop_event:
                stop_event.set()

        # 等待线程结束
        thread.join(timeout=5)

        with self._lock:
            if self._monitor_thread is thread and not thread.is_alive():
                self._monitor_thread = None
            if self._stop_event is stop_event and (not thread.is_alive()):
                self._stop_event = None

        log.info("监控已停止")


def main():
    """主函数"""
    log.info("=" * 50)
    log.info("TimeCraft 托盘应用启动")
    log.info(f"项目目录: {PROJECT_DIR}")
    log.info(f"数据目录: {os.path.join(PROJECT_DIR, 'data')}")
    log.info("=" * 50)

    # 创建监控管理器
    monitor = MonitorManager()

    # 默认启动监控
    monitor.start()

    # 创建并运行托盘应用
    tray = TrayApp(monitor)

    # 处理 Ctrl+C
    def signal_handler(sig, frame):
        log.info("收到退出信号")
        tray.quit_app()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 运行托盘（阻塞）
    try:
        tray.run()
    except KeyboardInterrupt:
        log.info("用户中断")
    finally:
        monitor.stop()
        log.info("应用退出")


if __name__ == "__main__":
    main()
