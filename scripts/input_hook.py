#!/usr/bin/env python3
"""
安全输入采样模块。

默认通过后台轮询统计输入：
- `GetAsyncKeyState` 检测按键和鼠标按下沿
- `GetCursorPos` 累加鼠标移动距离

滚轮不再使用全局低层钩子，而是通过隐藏窗口接收 Raw Input，
优先保证“绝不拖死鼠标”。
"""
import ctypes
import ctypes.wintypes
import math
import os
import sys
import threading
import time
from datetime import datetime

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
LRESULT = ctypes.c_ssize_t

user32.DefWindowProcW.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterRawInputDevices.restype = ctypes.wintypes.BOOL
user32.GetRawInputData.restype = ctypes.wintypes.UINT

# ── 日志 ──
_log_file = None


def set_log_file(path):
    """设置日志文件路径（由 active_monitor 调用）。"""
    global _log_file
    _log_file = path


def _log(level, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] [input] {msg}"
    print(line, file=sys.stderr)
    if _log_file:
        try:
            with open(_log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


# ── 常量 ──
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_CAPITAL = 0x14
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_NUMLOCK = 0x90
VK_SCROLL = 0x91
VK_C = 0x43
VK_V = 0x56

CHAR_VK_RANGES = [
    (0x30, 0x39),  # 0-9
    (0x41, 0x5A),  # A-Z
    (0x60, 0x69),  # numpad 0-9
    (0x6A, 0x6F),  # numpad ops
]

CHAR_VK_SINGLE = {0x20, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE}

FUNCTION_VKS = {
    VK_BACK, VK_TAB, VK_RETURN, VK_SHIFT, VK_CONTROL, VK_MENU, VK_CAPITAL,
    VK_ESCAPE, VK_SPACE, VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN, VK_INSERT, VK_DELETE,
    VK_LWIN, VK_RWIN, VK_NUMLOCK, VK_SCROLL,
}

FUNCTION_VK_RANGES = [
    (0x70, 0x87),  # F1-F24
]

POLLED_KEY_VKS = sorted(
    FUNCTION_VKS
    | CHAR_VK_SINGLE
    | set(range(0x30, 0x3A))
    | set(range(0x41, 0x5B))
    | set(range(0x60, 0x70))
    | set(range(0x6A, 0x70))
)

POLLED_MOUSE_VKS = [VK_LBUTTON, VK_RBUTTON]
POLL_INTERVAL_SEC = 0.02
HEARTBEAT_TIMEOUT_SEC = 2.0
WM_INPUT = 0x00FF
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_CLIPBOARDUPDATE = 0x031D
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100
HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_MOUSE = 0x02
RI_MOUSE_WHEEL = 0x0400
WHEEL_DELTA = 120
UINT_ERROR = 0xFFFFFFFF

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.wintypes.HINSTANCE),
        ("hIcon", ctypes.wintypes.HANDLE),
        ("hCursor", ctypes.wintypes.HANDLE),
        ("hbrBackground", ctypes.wintypes.HANDLE),
        ("lpszMenuName", ctypes.wintypes.LPCWSTR),
        ("lpszClassName", ctypes.wintypes.LPCWSTR),
    ]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage", ctypes.c_ushort),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("hwndTarget", ctypes.wintypes.HWND),
    ]


class RAWMOUSEBUTTONS(ctypes.Structure):
    _fields_ = [
        ("usButtonFlags", ctypes.c_ushort),
        ("usButtonData", ctypes.c_ushort),
    ]


class RAWMOUSEBUTTONSUNION(ctypes.Union):
    _anonymous_ = ("buttons",)
    _fields_ = [
        ("ulButtons", ctypes.c_ulong),
        ("buttons", RAWMOUSEBUTTONS),
    ]


class RAWMOUSE(ctypes.Structure):
    _anonymous_ = ("button_union",)
    _fields_ = [
        ("usFlags", ctypes.c_ushort),
        ("button_union", RAWMOUSEBUTTONSUNION),
        ("ulRawButtons", ctypes.c_ulong),
        ("lLastX", ctypes.c_long),
        ("lLastY", ctypes.c_long),
        ("ulExtraInformation", ctypes.c_ulong),
    ]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", ctypes.c_ushort),
        ("Flags", ctypes.c_ushort),
        ("Reserved", ctypes.c_ushort),
        ("VKey", ctypes.c_ushort),
        ("Message", ctypes.wintypes.UINT),
        ("ExtraInformation", ctypes.c_ulong),
    ]


class RAWHID(ctypes.Structure):
    _fields_ = [
        ("dwSizeHid", ctypes.wintypes.DWORD),
        ("dwCount", ctypes.wintypes.DWORD),
        ("bRawData", ctypes.c_ubyte * 1),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", ctypes.wintypes.DWORD),
        ("dwSize", ctypes.wintypes.DWORD),
        ("hDevice", ctypes.wintypes.HANDLE),
        ("wParam", ctypes.wintypes.WPARAM),
    ]


class RAWINPUTDATA(ctypes.Union):
    _fields_ = [
        ("mouse", RAWMOUSE),
        ("keyboard", RAWKEYBOARD),
        ("hid", RAWHID),
    ]


class RAWINPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", RAWINPUTDATA),
    ]


user32.RegisterRawInputDevices.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICE),
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
user32.GetRawInputData.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.wintypes.UINT),
    ctypes.wintypes.UINT,
]


def is_char_vk(vk):
    """判断是否是可输入字符的 VK。"""
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


class InputCounters:
    """线程安全的输入计数器。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self.keys = 0
            self.chars = 0
            self.left_clicks = 0
            self.right_clicks = 0
            self.scroll_up = 0
            self.scroll_down = 0
            self.copy_count = 0
            self.paste_count = 0

    def on_key_down(self, vk, ctrl_down, shift_down, alt_down):
        with self._lock:
            self.keys += 1
            if is_char_vk(vk) and not ctrl_down and not alt_down:
                self.chars += 1
            if (vk == VK_V and ctrl_down) or (vk == VK_INSERT and shift_down):
                self.paste_count += 1

    def on_mouse_click(self, button):
        with self._lock:
            if button == "left":
                self.left_clicks += 1
            elif button == "right":
                self.right_clicks += 1

    def on_scroll(self, up, steps=1):
        with self._lock:
            if up:
                self.scroll_up += steps
            else:
                self.scroll_down += steps

    def on_clipboard_copy(self, count=1):
        with self._lock:
            self.copy_count += count

    def read_and_reset(self):
        with self._lock:
            snapshot = {
                "keys": self.keys,
                "chars": self.chars,
                "clicks": self.left_clicks + self.right_clicks,
                "left_clicks": self.left_clicks,
                "right_clicks": self.right_clicks,
                "scroll_up": self.scroll_up,
                "scroll_down": self.scroll_down,
                "copy": self.copy_count,
                "paste": self.paste_count,
            }
            self.keys = 0
            self.chars = 0
            self.left_clicks = 0
            self.right_clicks = 0
            self.scroll_up = 0
            self.scroll_down = 0
            self.copy_count = 0
            self.paste_count = 0
            return snapshot

    def read(self):
        with self._lock:
            return {
                "keys": self.keys,
                "chars": self.chars,
                "clicks": self.left_clicks + self.right_clicks,
                "left_clicks": self.left_clicks,
                "right_clicks": self.right_clicks,
                "scroll_up": self.scroll_up,
                "scroll_down": self.scroll_down,
                "copy": self.copy_count,
                "paste": self.paste_count,
            }


_counters = InputCounters()
_sampler_thread = None
_sampler_stop_event = None
_event_thread = None
_event_stop_event = None
_event_ready_event = None
_event_hwnd = None
_event_wndproc = None
_heartbeat_lock = threading.Lock()
_last_heartbeat = 0.0
_mouse_pos_lock = threading.Lock()
_last_mouse_x = 0
_last_mouse_y = 0
_total_mouse_dist = 0.0
_prev_key_states = {}
_prev_mouse_states = {}
_last_clipboard_seq = 0
_clipboard_listener_active = False
_raw_input_listener_active = False


def _is_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _set_heartbeat(ts=None):
    global _last_heartbeat
    with _heartbeat_lock:
        _last_heartbeat = time.time() if ts is None else ts


def _get_heartbeat():
    with _heartbeat_lock:
        return _last_heartbeat


def _get_cursor_pos():
    point = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def _initialize_states():
    global _prev_key_states, _prev_mouse_states, _last_mouse_x, _last_mouse_y, _total_mouse_dist
    global _last_clipboard_seq
    _prev_key_states = {vk: _is_down(vk) for vk in POLLED_KEY_VKS}
    _prev_mouse_states = {vk: _is_down(vk) for vk in POLLED_MOUSE_VKS}
    x, y = _get_cursor_pos()
    with _mouse_pos_lock:
        _last_mouse_x = x
        _last_mouse_y = y
        _total_mouse_dist = 0.0
    _last_clipboard_seq = user32.GetClipboardSequenceNumber()


def _sample_once():
    global _last_mouse_x, _last_mouse_y, _total_mouse_dist, _last_clipboard_seq

    ctrl_down = _is_down(VK_CONTROL)
    shift_down = _is_down(VK_SHIFT)
    alt_down = _is_down(VK_MENU)
    for vk in POLLED_KEY_VKS:
        is_down = _is_down(vk)
        was_down = _prev_key_states.get(vk, False)
        if is_down and not was_down:
            _counters.on_key_down(vk, ctrl_down, shift_down, alt_down)
        _prev_key_states[vk] = is_down

    for vk in POLLED_MOUSE_VKS:
        is_down = _is_down(vk)
        was_down = _prev_mouse_states.get(vk, False)
        if is_down and not was_down:
            _counters.on_mouse_click("left" if vk == VK_LBUTTON else "right")
        _prev_mouse_states[vk] = is_down

    cur_x, cur_y = _get_cursor_pos()
    with _mouse_pos_lock:
        dx = cur_x - _last_mouse_x
        dy = cur_y - _last_mouse_y
        _total_mouse_dist += math.hypot(dx, dy)
        _last_mouse_x = cur_x
        _last_mouse_y = cur_y

    if not _clipboard_listener_active:
        clipboard_seq = user32.GetClipboardSequenceNumber()
        if clipboard_seq and _last_clipboard_seq and clipboard_seq != _last_clipboard_seq:
            diff = clipboard_seq - _last_clipboard_seq
            _counters.on_clipboard_copy(diff if diff > 0 else 1)
        if clipboard_seq:
            _last_clipboard_seq = clipboard_seq


def _register_raw_mouse_input(hwnd):
    raw_input_device = RAWINPUTDEVICE(
        usUsagePage=HID_USAGE_PAGE_GENERIC,
        usUsage=HID_USAGE_GENERIC_MOUSE,
        dwFlags=RIDEV_INPUTSINK,
        hwndTarget=hwnd,
    )
    if user32.RegisterRawInputDevices(
        ctypes.byref(raw_input_device),
        1,
        ctypes.sizeof(RAWINPUTDEVICE),
    ):
        return True
    _log("WARN", f"注册 Raw Input 鼠标失败: {ctypes.WinError()}")
    return False


def _handle_raw_input(lparam):
    raw_size = ctypes.wintypes.UINT(0)
    header_size = ctypes.sizeof(RAWINPUTHEADER)
    result = user32.GetRawInputData(
        ctypes.wintypes.HANDLE(lparam),
        RID_INPUT,
        None,
        ctypes.byref(raw_size),
        header_size,
    )
    if result == UINT_ERROR:
        raise ctypes.WinError()
    if raw_size.value < ctypes.sizeof(RAWINPUT):
        return

    raw_buffer = (ctypes.c_ubyte * raw_size.value)()
    result = user32.GetRawInputData(
        ctypes.wintypes.HANDLE(lparam),
        RID_INPUT,
        raw_buffer,
        ctypes.byref(raw_size),
        header_size,
    )
    if result == UINT_ERROR:
        raise ctypes.WinError()
    if result < header_size:
        return

    raw = ctypes.cast(raw_buffer, ctypes.POINTER(RAWINPUT)).contents
    if raw.header.dwType != RIM_TYPEMOUSE:
        return

    if not (raw.mouse.usButtonFlags & RI_MOUSE_WHEEL):
        return

    wheel_delta = ctypes.c_short(raw.mouse.usButtonData).value
    steps = abs(wheel_delta) // WHEEL_DELTA
    if steps <= 0:
        return
    _counters.on_scroll(wheel_delta > 0, steps=steps)


def _window_proc(hwnd, msg, wparam, lparam):
    global _event_hwnd
    if msg == WM_INPUT:
        try:
            _handle_raw_input(lparam)
        except Exception as e:
            _log("WARN", f"处理滚轮输入失败: {e}")
        return 0
    if msg == WM_CLIPBOARDUPDATE:
        try:
            clipboard_seq = user32.GetClipboardSequenceNumber()
            if clipboard_seq:
                global _last_clipboard_seq
                if _last_clipboard_seq and clipboard_seq != _last_clipboard_seq:
                    diff = clipboard_seq - _last_clipboard_seq
                    _counters.on_clipboard_copy(diff if diff > 0 else 1)
                _last_clipboard_seq = clipboard_seq
        except Exception as e:
            _log("WARN", f"处理剪贴板更新失败: {e}")
        return 0
    if msg == WM_CLOSE:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        try:
            user32.RemoveClipboardFormatListener(hwnd)
        except Exception:
            pass
        _event_hwnd = None
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _event_loop(stop_event, ready_event):
    global _event_hwnd, _event_wndproc, _clipboard_listener_active, _raw_input_listener_active

    class_name = f"TimeCraftInputWindow_{os.getpid()}"
    hinstance = kernel32.GetModuleHandleW(None)
    _event_wndproc = WNDPROC(_window_proc)

    wnd_class = WNDCLASSW()
    wnd_class.lpfnWndProc = _event_wndproc
    wnd_class.hInstance = hinstance
    wnd_class.lpszClassName = class_name

    atom = user32.RegisterClassW(ctypes.byref(wnd_class))
    if not atom:
        _log("WARN", "注册输入事件窗口类失败，滚轮/剪贴板事件可能不可用")

    hwnd = user32.CreateWindowExW(
        0,
        class_name,
        class_name,
        0,
        0,
        0,
        0,
        0,
        None,
        None,
        hinstance,
        None,
    )
    if not hwnd:
        _log("WARN", "创建输入事件窗口失败，滚轮/剪贴板事件将不可用")
        ready_event.set()
        return

    _event_hwnd = hwnd
    _raw_input_listener_active = _register_raw_mouse_input(hwnd)
    if _raw_input_listener_active:
        _log("INFO", "Raw Input 鼠标监听已启动")

    if not user32.AddClipboardFormatListener(hwnd):
        _log("WARN", "注册剪贴板监听失败，复制统计将退化为轮询")
        _clipboard_listener_active = False
    else:
        _clipboard_listener_active = True

    ready_event.set()
    _log("INFO", "输入事件窗口已启动")

    msg = ctypes.wintypes.MSG()
    while not stop_event.is_set():
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret <= 0:
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    if _event_hwnd:
        try:
            user32.PostMessageW(_event_hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass
    _clipboard_listener_active = False
    _raw_input_listener_active = False
    _log("INFO", "输入事件窗口已退出")


def _sampler_loop(stop_event):
    _log("INFO", "输入采样线程已启动")
    _initialize_states()
    _set_heartbeat()

    try:
        while not stop_event.is_set():
            _sample_once()
            _set_heartbeat()
            stop_event.wait(POLL_INTERVAL_SEC)
    except Exception as e:
        _log("ERROR", f"输入采样线程异常退出: {e}")
    finally:
        _set_heartbeat(0.0)
        _log("WARN", "输入采样线程已退出")


def start():
    """启动输入采样线程。"""
    global _sampler_thread, _sampler_stop_event
    global _event_thread, _event_stop_event, _event_ready_event
    if _sampler_thread and _sampler_thread.is_alive():
        _log("INFO", "输入采样线程已在运行，跳过启动")
        return

    _counters.reset()
    _event_stop_event = threading.Event()
    _event_ready_event = threading.Event()
    _event_thread = threading.Thread(
        target=_event_loop,
        args=(_event_stop_event, _event_ready_event),
        daemon=True,
        name="input-event-window",
    )
    _event_thread.start()
    _event_ready_event.wait(timeout=1)

    _sampler_stop_event = threading.Event()
    _sampler_thread = threading.Thread(
        target=_sampler_loop,
        args=(_sampler_stop_event,),
        daemon=True,
        name="input-sampler",
    )
    _sampler_thread.start()

    for _ in range(50):
        time.sleep(0.02)
        if is_alive():
            _log("INFO", "输入采样器启动完成")
            return
    _log("WARN", "输入采样器启动等待超时")


def stop():
    """停止输入采样线程。"""
    global _sampler_thread, _sampler_stop_event
    global _event_thread, _event_stop_event, _event_ready_event, _event_hwnd
    global _clipboard_listener_active, _raw_input_listener_active
    _log("INFO", "正在停止输入采样器...")
    if _sampler_stop_event:
        _sampler_stop_event.set()
    if _sampler_thread:
        _sampler_thread.join(timeout=2)
    _sampler_thread = None
    _sampler_stop_event = None

    if _event_stop_event:
        _event_stop_event.set()
    if _event_hwnd:
        try:
            user32.PostMessageW(_event_hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass
    if _event_thread:
        _event_thread.join(timeout=2)
    _event_thread = None
    _event_stop_event = None
    _event_ready_event = None
    _event_hwnd = None
    _clipboard_listener_active = False
    _raw_input_listener_active = False

    _set_heartbeat(0.0)
    _log("INFO", "输入采样器已停止")


def is_alive():
    """检查输入采样线程是否存活。"""
    if not (_sampler_thread and _sampler_thread.is_alive()):
        return False
    elapsed = time.time() - _get_heartbeat()
    if elapsed > HEARTBEAT_TIMEOUT_SEC:
        _log("WARN", f"输入采样心跳超时 ({elapsed:.1f}s > {HEARTBEAT_TIMEOUT_SEC}s)")
        return False
    return True


def restart():
    """安全重启输入采样线程。"""
    _log("INFO", "正在重启输入采样器...")
    stop()
    time.sleep(0.2)
    start()
    alive = is_alive()
    if alive:
        _log("INFO", "输入采样器重启成功")
    else:
        _log("ERROR", "输入采样器重启后仍不健康")
    return alive


def read_counters(reset=False):
    """读取输入计数。"""
    if reset:
        return _counters.read_and_reset()
    return _counters.read()


def get_mouse_distance_and_reset():
    """获取鼠标移动距离并重置。"""
    global _total_mouse_dist
    with _mouse_pos_lock:
        dist = int(_total_mouse_dist)
        _total_mouse_dist = 0.0
        return dist
