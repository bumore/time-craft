#!/usr/bin/env python3
"""
键盘/鼠标钩子模块 - 事件驱动的精确输入统计
替代原来每30秒轮询2秒的采样方案

原理：
- WH_KEYBOARD_LL: 每次键盘按下/释放时，Windows 调用回调
- WH_MOUSE_LL: 每次鼠标按下/释放时，Windows 调用回调
- 回调在 GetMessage 所在线程执行，需要消息泵
- 主线程通过线程安全的计数器读取数据

防卡死机制：
- 钩子线程心跳 (_last_heartbeat)，消息泵每循环更新
- is_alive() 检测心跳是否超时（默认5秒）
- restart() 安全重启钩子线程
- 钩子线程异常自动标记死亡状态
"""
import ctypes
import ctypes.wintypes
import threading
import time
import sys
from datetime import datetime

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── 日志 ──
_log_file = None

def set_log_file(path):
    """设置日志文件路径（由 active_monitor 调用）"""
    global _log_file
    _log_file = path

def _log(level, msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] [{level}] [hook] {msg}"
    print(line, file=sys.stderr)
    if _log_file:
        try:
            with open(_log_file, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass

# ── 钩子常量 ──
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MOUSEWHEEL = 0x020A
WM_QUIT = 0x0012
HC_ACTION = 0

# ── VK 码分类 ──
CHAR_VK_RANGES = [
    (0x30, 0x39),   # 数字 0-9
    (0x41, 0x5A),   # 字母 A-Z
    (0x60, 0x69),   # 小键盘数字
    (0x6A, 0x6F),   # 小键盘运算符
]

CHAR_VK_SINGLE = {0x20, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xC1, 0xC2}

FUNCTION_VKS = {
    0x08, 0x09, 0x0D, 0x10, 0x11, 0x12, 0x14, 0x1B,
    0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E,
    0x5B, 0x5C, 0x90, 0x91,
}
FUNCTION_VK_RANGES = [(0x70, 0x87), (0x96, 0xA7)]

VK_CONTROL = 0x11
VK_C = 0x43
VK_V = 0x56


def is_char_vk(vk):
    """判断是否是可输入字符的VK"""
    if vk in FUNCTION_VKS:
        return False
    for start, end in FUNCTION_VK_RANGES:
        if start <= vk <= end:
            return False
    if vk in CHAR_VK_SINGLE:
        return True
    for start, end in CHAR_VK_RANGES:
        if start <= vk <= end:
            return True
    return False


# ── KBDLLHOOKSTRUCT 结构体 ──
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.wintypes.POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


# ── 计数器（线程安全）──
class InputCounters:
    """线程安全的输入计数器"""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self.keys = 0          # 总按键次数（按下）
            self.chars = 0         # 可输入字符数（按下）
            self.clicks = 0        # 鼠标点击次数
            self.scroll_up = 0     # 向上滚动次数
            self.scroll_down = 0   # 向下滚动次数
            self.copy_count = 0    # Ctrl+C 次数
            self.paste_count = 0   # Ctrl+V 次数
            self._ctrl_down = False
            self._c_down = False
            self._v_down = False

    def on_key_down(self, vk):
        with self._lock:
            self.keys += 1
            if is_char_vk(vk):
                self.chars += 1
            # Ctrl+C / Ctrl+V 检测（必须 Ctrl 先按）
            if vk == VK_CONTROL:
                self._ctrl_down = True
            elif vk == VK_C:
                self._c_down = True
                if self._ctrl_down:
                    self.copy_count += 1
            elif vk == VK_V:
                self._v_down = True
                if self._ctrl_down:
                    self.paste_count += 1

    def on_key_up(self, vk):
        with self._lock:
            if vk == VK_CONTROL:
                self._ctrl_down = False
            elif vk == VK_C:
                self._c_down = False
            elif vk == VK_V:
                self._v_down = False

    def on_mouse_click(self):
        with self._lock:
            self.clicks += 1

    def on_scroll(self, up=True):
        with self._lock:
            if up:
                self.scroll_up += 1
            else:
                self.scroll_down += 1

    def read_and_reset(self):
        """读取当前计数并重置，返回快照"""
        with self._lock:
            snapshot = {
                "keys": self.keys,
                "chars": self.chars,
                "clicks": self.clicks,
                "scroll_up": self.scroll_up,
                "scroll_down": self.scroll_down,
                "copy": self.copy_count,
                "paste": self.paste_count,
            }
            self.keys = 0
            self.chars = 0
            self.clicks = 0
            self.scroll_up = 0
            self.scroll_down = 0
            self.copy_count = 0
            self.paste_count = 0
            self._ctrl_down = False
            self._c_down = False
            self._v_down = False
            return snapshot

    def read(self):
        """只读取，不重置"""
        with self._lock:
            return {
                "keys": self.keys,
                "chars": self.chars,
                "clicks": self.clicks,
                "scroll_up": self.scroll_up,
                "scroll_down": self.scroll_down,
                "copy": self.copy_count,
                "paste": self.paste_count,
            }


# ── 全局状态 ──
_counters = InputCounters()
_hook_thread = None
_hook_thread_id = None
_keyboard_hook = None
_mouse_hook = None
_kb_callback = None   # 防止 GC 回收 ctypes 回调对象
_mouse_callback = None

# 心跳与存活检测
_hook_alive = False          # 钩子线程是否存活
_last_heartbeat = 0          # 上次心跳时间戳
_HEARTBEAT_TIMEOUT = 5.0     # 心跳超时阈值（秒）
_lock_restart = threading.Lock()  # 防止并发重启

# 鼠标移动距离（独立线程，每100ms采样）
_mouse_pos_lock = threading.Lock()
_last_mouse_x = 0
_last_mouse_y = 0
_total_mouse_dist = 0.0
_mouse_sample_thread = None
_mouse_sample_running = False


# ── 钩子回调 ──
# CFUNCTYPE 必须在模块级别定义
LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
)
LowLevelMouseProc = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
)


def _keyboard_hook_proc(nCode, wParam, lParam):
    """键盘钩子回调"""
    if nCode == HC_ACTION:
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode
        if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
            _counters.on_key_down(vk)
        elif wParam in (WM_KEYUP, 0x0105):  # WM_KEYUP=0x0101, WM_SYSKEYUP=0x0105
            _counters.on_key_up(vk)
    return user32.CallNextHookEx(_keyboard_hook, nCode, wParam, lParam)


def _mouse_hook_proc(nCode, wParam, lParam):
    """鼠标钩子回调"""
    if nCode == HC_ACTION:
        if wParam == WM_LBUTTONDOWN:
            _counters.on_mouse_click()
        elif wParam == WM_RBUTTONDOWN:
            _counters.on_mouse_click()
        elif wParam == WM_MOUSEWHEEL:
            ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            # mouseData 高16位是滚轮增量，正值向上，负值向下
            delta = ctypes.c_short((ms.mouseData >> 16) & 0xFFFF).value
            _counters.on_scroll(up=(delta > 0))
    return user32.CallNextHookEx(_mouse_hook, nCode, wParam, lParam)


# ── 钩子线程 ──
def _hook_thread_func():
    """钩子线程：安装钩子 + 消息泵（带心跳和异常保护）"""
    global _keyboard_hook, _mouse_hook, _hook_thread_id, _kb_callback, _mouse_callback
    global _hook_alive, _last_heartbeat

    try:
        _hook_thread_id = kernel32.GetCurrentThreadId()

        # 创建回调对象（必须保持引用，防止 GC）
        _kb_callback = LowLevelKeyboardProc(_keyboard_hook_proc)
        _mouse_callback = LowLevelMouseProc(_mouse_hook_proc)

        # 安装键盘钩子
        _keyboard_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            _kb_callback,
            0,  # 低级钩子用0即可，GetModuleHandleW(None) 在某些系统上返回无效句柄
            0,
        )
        if not _keyboard_hook:
            _log("ERROR", "键盘钩子安装失败")

        # 安装鼠标钩子
        _mouse_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            _mouse_callback,
            0,  # 同上
            0,
        )
        if not _mouse_hook:
            _log("ERROR", "鼠标钩子安装失败")

        # 如果两个钩子都没装上，直接退出
        if not _keyboard_hook and not _mouse_hook:
            _log("ERROR", "两个钩子都安装失败，钩子线程退出")
            _hook_alive = False
            return

        _hook_alive = True
        _last_heartbeat = time.time()
        _log("INFO", f"钩子安装成功 (kb={bool(_keyboard_hook)}, mouse={bool(_mouse_hook)})")

        # 消息泵 - 必须，否则钩子不会触发
        # GetMessageW 会阻塞直到有消息，但钩子回调会在消息到达时执行
        msg = ctypes.wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            _last_heartbeat = time.time()  # 每次消息循环更新心跳
            if ret == 0 or ret == -1:
                # WM_QUIT received 或错误
                _log("INFO", f"消息泵退出 (GetMessageW returned {ret})")
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    except Exception as e:
        _log("ERROR", f"钩子线程异常退出: {e}")
    finally:
        # 清理钩子
        if _keyboard_hook:
            user32.UnhookWindowsHookEx(_keyboard_hook)
            _keyboard_hook = None
        if _mouse_hook:
            user32.UnhookWindowsHookEx(_mouse_hook)
            _mouse_hook = None
        _hook_alive = False
        _hook_thread_id = None
        _log("WARN", "钩子线程已退出，标记为死亡")


# ── 公共 API ──
def start():
    """启动钩子 + 鼠标采样（后台线程）"""
    global _hook_thread, _mouse_sample_thread, _mouse_sample_running
    if _hook_thread and _hook_thread.is_alive():
        _log("INFO", "钩子线程已在运行，跳过启动")
        return
    _counters.reset()
    init_mouse_position()

    # 启动键盘/鼠标钩子线程
    _hook_thread = threading.Thread(target=_hook_thread_func, daemon=True, name="hook-thread")
    _hook_thread.start()

    # 启动鼠标位置采样线程（每100ms）
    _mouse_sample_running = True
    _mouse_sample_thread = threading.Thread(target=_mouse_sample_thread_func, daemon=True, name="mouse-sample")
    _mouse_sample_thread.start()

    # 等待钩子安装完成
    for _ in range(50):
        time.sleep(0.05)
        if _keyboard_hook:
            break

    if _keyboard_hook:
        _log("INFO", "钩子启动完成")
    else:
        _log("WARN", "钩子启动等待超时，键盘钩子可能未就绪")


def stop():
    """停止钩子 + 鼠标采样"""
    global _hook_thread, _hook_thread_id, _kb_callback, _mouse_callback
    global _mouse_sample_thread, _mouse_sample_running

    _log("INFO", "正在停止钩子...")
    # 停止鼠标采样线程
    _mouse_sample_running = False
    if _mouse_sample_thread:
        _mouse_sample_thread.join(timeout=2)
        _mouse_sample_thread = None
    # 停止钩子线程
    if _hook_thread_id:
        user32.PostThreadMessageW(_hook_thread_id, WM_QUIT, 0, 0)
        if _hook_thread:
            _hook_thread.join(timeout=3)
    _hook_thread = None
    _hook_thread_id = None
    _kb_callback = None
    _mouse_callback = None
    _log("INFO", "钩子已停止")


def is_alive():
    """检查钩子线程是否存活（基于心跳）"""
    if not _hook_alive:
        return False
    elapsed = time.time() - _last_heartbeat
    if elapsed > _HEARTBEAT_TIMEOUT:
        _log("WARN", f"钩子心跳超时 ({elapsed:.1f}s > {_HEARTBEAT_TIMEOUT}s)")
        return False
    return True


def restart():
    """安全重启钩子线程"""
    global _lock_restart
    if not _lock_restart.acquire(blocking=False):
        _log("WARN", "已有重启进行中，跳过")
        return False

    try:
        _log("INFO", "正在重启钩子线程...")
        stop()
        time.sleep(0.5)
        start()
        alive = is_alive()
        if alive:
            _log("INFO", "钩子线程重启成功")
        else:
            _log("ERROR", "钩子线程重启后仍不健康")
        return alive
    finally:
        _lock_restart.release()


def read_counters(reset=False):
    """读取输入计数"""
    if reset:
        return _counters.read_and_reset()
    return _counters.read()


def get_mouse_distance_and_reset():
    """获取鼠标移动距离并重置"""
    global _total_mouse_dist
    with _mouse_pos_lock:
        dist = int(_total_mouse_dist)
        _total_mouse_dist = 0.0
        return dist


def update_mouse_distance():
    """采样鼠标位置并累加距离（由内部线程调用）"""
    global _last_mouse_x, _last_mouse_y, _total_mouse_dist
    cur_x, cur_y = ctypes.c_long(), ctypes.c_long()
    user32.GetCursorPos(ctypes.byref(cur_x), ctypes.byref(cur_y))
    with _mouse_pos_lock:
        dx = cur_x.value - _last_mouse_x
        dy = cur_y.value - _last_mouse_y
        _total_mouse_dist += (dx * dx + dy * dy) ** 0.5
        _last_mouse_x = cur_x.value
        _last_mouse_y = cur_y.value


def _mouse_sample_thread_func():
    """鼠标位置采样线程，每100ms采样一次"""
    while _mouse_sample_running:
        try:
            update_mouse_distance()
        except Exception as e:
            _log("WARN", f"鼠标采样异常: {e}")
        time.sleep(0.1)


def init_mouse_position():
    """初始化鼠标位置基准点"""
    global _last_mouse_x, _last_mouse_y
    cur_x, cur_y = ctypes.c_long(), ctypes.c_long()
    user32.GetCursorPos(ctypes.byref(cur_x), ctypes.byref(cur_y))
    _last_mouse_x = cur_x.value
    _last_mouse_y = cur_y.value
