#!/usr/bin/env python3
import ctypes
import ctypes.wintypes
import threading
import time
from datetime import datetime

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

try:
    dwmapi = ctypes.windll.dwmapi
except OSError:
    dwmapi = None

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)

user32.DefWindowProcW.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.restype = ctypes.wintypes.HWND
user32.UnregisterClassW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.HINSTANCE]
user32.UnregisterClassW.restype = ctypes.wintypes.BOOL
user32.IsWindow.restype = ctypes.wintypes.BOOL
user32.IsWindow.argtypes = [ctypes.wintypes.HWND]
user32.GetClientRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]
user32.GetClientRect.restype = ctypes.wintypes.BOOL
user32.FillRect.restype = ctypes.c_int
user32.FillRect.argtypes = [
    ctypes.wintypes.HDC,
    ctypes.POINTER(ctypes.wintypes.RECT),
    ctypes.wintypes.HBRUSH,
]
user32.InvalidateRect.restype = ctypes.wintypes.BOOL
user32.InvalidateRect.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.POINTER(ctypes.wintypes.RECT),
    ctypes.wintypes.BOOL,
]
user32.ShowWindow.restype = ctypes.wintypes.BOOL
user32.SetForegroundWindow.restype = ctypes.wintypes.BOOL
user32.SetWindowTextW.restype = ctypes.wintypes.BOOL
user32.SetWindowTextW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPCWSTR]
user32.BringWindowToTop.restype = ctypes.wintypes.BOOL
user32.SetActiveWindow.restype = ctypes.wintypes.HWND
user32.DrawTextW.restype = ctypes.c_int
user32.DrawTextW.argtypes = [
    ctypes.wintypes.HDC,
    ctypes.wintypes.LPCWSTR,
    ctypes.c_int,
    ctypes.POINTER(ctypes.wintypes.RECT),
    ctypes.wintypes.UINT,
]
user32.SetScrollInfo.restype = ctypes.c_int
user32.SetScrollInfo.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_void_p, ctypes.wintypes.BOOL]
user32.ShowScrollBar.restype = ctypes.wintypes.BOOL
user32.ShowScrollBar.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.wintypes.BOOL]
gdi32.CreateFontW.restype = ctypes.wintypes.HANDLE
gdi32.CreateSolidBrush.restype = ctypes.wintypes.HANDLE
gdi32.CreateSolidBrush.argtypes = [ctypes.wintypes.COLORREF]
gdi32.CreatePen.restype = ctypes.wintypes.HANDLE
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.wintypes.COLORREF]
gdi32.SelectObject.restype = ctypes.wintypes.HANDLE
gdi32.SelectObject.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.HANDLE]
gdi32.SaveDC.restype = ctypes.c_int
gdi32.SaveDC.argtypes = [ctypes.wintypes.HDC]
gdi32.RestoreDC.restype = ctypes.wintypes.BOOL
gdi32.RestoreDC.argtypes = [ctypes.wintypes.HDC, ctypes.c_int]
gdi32.IntersectClipRect.restype = ctypes.c_int
gdi32.IntersectClipRect.argtypes = [
    ctypes.wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
]
gdi32.DeleteObject.restype = ctypes.wintypes.BOOL
gdi32.DeleteObject.argtypes = [ctypes.wintypes.HANDLE]
gdi32.RoundRect.restype = ctypes.wintypes.BOOL
gdi32.RoundRect.argtypes = [
    ctypes.wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
]
gdi32.SetBkMode.restype = ctypes.c_int
gdi32.SetBkMode.argtypes = [ctypes.wintypes.HDC, ctypes.c_int]
gdi32.SetTextColor.restype = ctypes.wintypes.COLORREF
gdi32.SetTextColor.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.COLORREF]
gdi32.SetBkColor.restype = ctypes.wintypes.COLORREF
gdi32.SetBkColor.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.COLORREF]

SW_SHOW = 5
SW_RESTORE = 9
WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_SIZE = 0x0005
WM_CLOSE = 0x0010
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A
WM_VSCROLL = 0x0115
WM_NCHITTEST = 0x0084

WS_VISIBLE = 0x10000000
WS_POPUP = 0x80000000
WS_EX_APPWINDOW = 0x00040000

IDC_ARROW = 32512
HTCLIENT = 1
HTCAPTION = 2
TRANSPARENT = 1

SB_VERT = 1
SB_LINEUP = 0
SB_LINEDOWN = 1
SB_PAGEUP = 2
SB_PAGEDOWN = 3
SB_THUMBPOSITION = 4
SB_THUMBTRACK = 5
SB_TOP = 6
SB_BOTTOM = 7

SIF_RANGE = 0x0001
SIF_PAGE = 0x0002
SIF_POS = 0x0004
SIF_ALL = SIF_RANGE | SIF_PAGE | SIF_POS

DT_LEFT = 0x0000
DT_CENTER = 0x0001
DT_RIGHT = 0x0002
DT_VCENTER = 0x0004
DT_WORDBREAK = 0x0010
DT_SINGLELINE = 0x0020
DT_CALCRECT = 0x0400
DT_NOPREFIX = 0x0800
DT_END_ELLIPSIS = 0x8000

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWCP_ROUND = 2

HEADER_HEIGHT = 60
WINDOW_PADDING = 8
CARD_GAP = 12
CARD_PADDING_X = 16
CARD_PADDING_Y = 16
METRIC_TILE_HEIGHT = 68
METRIC_TILE_GAP = 10
SECTION_TITLE_HEIGHT = 22
CLOSE_BUTTON_SIZE = 24
DRAG_REGION_BOTTOM = 56
SCROLL_STEP = 56
APP_BLOCK_GAP = 10
MAX_CONTENT_WIDTH = 576

_report_window_state = {
    "thread": None,
    "hwnd": None,
    "state": None,
}
_report_window_lock = threading.Lock()


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


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", ctypes.wintypes.HDC),
        ("fErase", ctypes.wintypes.BOOL),
        ("rcPaint", ctypes.wintypes.RECT),
        ("fRestore", ctypes.wintypes.BOOL),
        ("fIncUpdate", ctypes.wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


class SCROLLINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("fMask", ctypes.c_uint),
        ("nMin", ctypes.c_int),
        ("nMax", ctypes.c_int),
        ("nPage", ctypes.c_uint),
        ("nPos", ctypes.c_int),
        ("nTrackPos", ctypes.c_int),
    ]


user32.BeginPaint.restype = ctypes.wintypes.HDC
user32.BeginPaint.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.EndPaint.restype = ctypes.wintypes.BOOL
user32.EndPaint.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]


def _rgb(red, green, blue):
    return red | (green << 8) | (blue << 16)


def _make_rect(left, top, right, bottom):
    return ctypes.wintypes.RECT(int(left), int(top), int(right), int(bottom))


def _rect_width(rect):
    return rect[2] - rect[0]


def _rect_height(rect):
    return rect[3] - rect[1]


def _point_in_rect(point_x, point_y, rect):
    return rect[0] <= point_x <= rect[2] and rect[1] <= point_y <= rect[3]


def _create_font(height, weight, face):
    return gdi32.CreateFontW(
        -height,
        0,
        0,
        0,
        weight,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        face,
    )


def _set_dwm_color(hwnd, attr, color_value):
    if not dwmapi:
        return
    color = ctypes.c_uint(color_value)
    dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(color), ctypes.sizeof(color))


def _set_dwm_int(hwnd, attr, value):
    if not dwmapi:
        return
    data = ctypes.c_int(value)
    dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(data), ctypes.sizeof(data))


def _apply_window_style(hwnd):
    try:
        _set_dwm_int(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
        _set_dwm_color(hwnd, DWMWA_CAPTION_COLOR, _rgb(247, 248, 250))
        _set_dwm_color(hwnd, DWMWA_TEXT_COLOR, _rgb(31, 41, 55))
        _set_dwm_color(hwnd, DWMWA_BORDER_COLOR, _rgb(229, 231, 235))
    except Exception:
        return


def _format_report_date(date_text):
    if not date_text:
        return datetime.now().strftime("%Y-%m-%d")

    text = str(date_text).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def _build_subtitle_text(report_date=None):
    return f"{_format_report_date(report_date)}  ·  {datetime.now().strftime('%H:%M')} 更新"


def _is_live_window(hwnd):
    return bool(hwnd) and bool(user32.IsWindow(hwnd))


def _focus_report_window(hwnd):
    if not _is_live_window(hwnd):
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    user32.SetActiveWindow(hwnd)
    user32.SetForegroundWindow(hwnd)
    return True


def _trim_text(text, max_length):
    if text is None:
        return ""
    text = str(text).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _empty_report_data():
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "segments": [],
        "total_duration": "0s",
        "segments_count": 0,
        "keyboard": {"total_keys": 0, "total_chars": 0},
        "clipboard": {"copy": 0, "paste": 0},
        "mouse": {
            "total_clicks": 0,
            "left_clicks": 0,
            "right_clicks": 0,
            "total_scroll": 0,
            "scroll_up": 0,
            "scroll_down": 0,
            "distance": "0 像素 (约0.00米)",
        },
        "apps": [],
        "legacy_text": "",
    }


def _normalize_report_data(report_data):
    if not isinstance(report_data, dict):
        data = _empty_report_data()
        if report_data is not None:
            data["legacy_text"] = str(report_data)
        return data

    data = _empty_report_data()
    data.update(report_data)

    keyboard = data.get("keyboard")
    if not isinstance(keyboard, dict):
        keyboard = {}
    data["keyboard"] = {
        "total_keys": keyboard.get("total_keys", 0),
        "total_chars": keyboard.get("total_chars", 0),
    }

    clipboard = data.get("clipboard")
    if not isinstance(clipboard, dict):
        clipboard = {}
    data["clipboard"] = {
        "copy": clipboard.get("copy", 0),
        "paste": clipboard.get("paste", 0),
    }

    mouse = data.get("mouse")
    if not isinstance(mouse, dict):
        mouse = {}
    data["mouse"] = {
        "total_clicks": mouse.get("total_clicks", 0),
        "left_clicks": mouse.get("left_clicks", 0),
        "right_clicks": mouse.get("right_clicks", 0),
        "total_scroll": mouse.get("total_scroll", 0),
        "scroll_up": mouse.get("scroll_up", 0),
        "scroll_down": mouse.get("scroll_down", 0),
        "distance": mouse.get("distance", "0 像素 (约0.00米)"),
    }

    apps = data.get("apps")
    if not isinstance(apps, list):
        apps = []
    normalized_apps = []
    for app in apps:
        if not isinstance(app, dict):
            continue
        pages = app.get("pages")
        if not isinstance(pages, list):
            pages = []
        normalized_apps.append(
            {
                "name": app.get("name", "未知程序"),
                "duration": app.get("duration", "0s"),
                "pct": float(app.get("pct", 0) or 0),
                "is_browser": bool(app.get("is_browser", False)),
                "pages": [
                    {
                        "name": page.get("name", "网页"),
                        "duration": page.get("duration", "0s"),
                    }
                    for page in pages
                    if isinstance(page, dict)
                ],
            }
        )
    data["apps"] = normalized_apps

    segments = data.get("segments")
    if not isinstance(segments, list):
        segments = []
    data["segments"] = segments
    return data


def _draw_text(hdc, text, rect, font, color, flags):
    old_font = gdi32.SelectObject(hdc, font)
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color)
    draw_rect = _make_rect(*rect)
    user32.DrawTextW(hdc, str(text), -1, ctypes.byref(draw_rect), flags | DT_NOPREFIX)
    gdi32.SelectObject(hdc, old_font)


def _measure_text(hdc, text, font, width, flags):
    old_font = gdi32.SelectObject(hdc, font)
    measure_rect = _make_rect(0, 0, max(1, int(width)), 0)
    user32.DrawTextW(
        hdc,
        str(text),
        -1,
        ctypes.byref(measure_rect),
        flags | DT_CALCRECT | DT_NOPREFIX,
    )
    gdi32.SelectObject(hdc, old_font)
    return measure_rect.bottom - measure_rect.top


def _metric_item(label, value, span=1):
    return {"label": label, "value": value, "span": span}


def _normalize_metric_items(metrics):
    normalized = []
    for item in metrics:
        if isinstance(item, dict):
            normalized.append(
                {
                    "label": item.get("label", ""),
                    "value": item.get("value", ""),
                    "span": max(1, int(item.get("span", 1) or 1)),
                }
            )
        else:
            label, value = item
            normalized.append({"label": label, "value": value, "span": 1})
    return normalized


def _metric_grid_rows(metrics, columns):
    rows = 0
    current = 0
    for item in _normalize_metric_items(metrics):
        span = min(columns, item["span"])
        if current + span > columns:
            rows += 1
            current = 0
        current += span
        if current >= columns:
            rows += 1
            current = 0
    if current:
        rows += 1
    return max(1, rows)


def _draw_round_rect(hdc, rect, fill_color, border_color, radius=18):
    brush = gdi32.CreateSolidBrush(fill_color)
    pen = gdi32.CreatePen(0, 1, border_color)
    old_brush = gdi32.SelectObject(hdc, brush)
    old_pen = gdi32.SelectObject(hdc, pen)
    gdi32.RoundRect(hdc, rect[0], rect[1], rect[2], rect[3], radius, radius)
    gdi32.SelectObject(hdc, old_brush)
    gdi32.SelectObject(hdc, old_pen)
    gdi32.DeleteObject(brush)
    gdi32.DeleteObject(pen)


def _draw_window_frame(hdc, client_width, client_height, state):
    colors = state["colors"]
    frame_rect = (1, 1, max(1, client_width - 1), max(1, client_height - 1))
    _draw_round_rect(hdc, frame_rect, colors["root"], colors["frame"], radius=20)


def _draw_badge(hdc, rect, text, font, fill_color, border_color, text_color):
    _draw_round_rect(hdc, rect, fill_color, border_color, radius=14)
    _draw_text(hdc, text, rect, font, text_color, DT_CENTER | DT_VCENTER | DT_SINGLELINE)


def _draw_card_header(hdc, rect, title, state, icon=None):
    colors = state["colors"]
    fonts = state["fonts"]
    text_left = rect[0] + CARD_PADDING_X
    if icon:
        icon_rect = (
            rect[0] + CARD_PADDING_X,
            rect[1] + CARD_PADDING_Y - 1,
            rect[0] + CARD_PADDING_X + 22,
            rect[1] + CARD_PADDING_Y + SECTION_TITLE_HEIGHT,
        )
        _draw_text(hdc, icon, icon_rect, fonts["section_icon"], colors["title"], DT_LEFT | DT_VCENTER | DT_SINGLELINE)
        text_left += 24
    else:
        dot_rect = (
            rect[0] + CARD_PADDING_X,
            rect[1] + CARD_PADDING_Y + 5,
            rect[0] + CARD_PADDING_X + 10,
            rect[1] + CARD_PADDING_Y + 15,
        )
        _draw_round_rect(hdc, dot_rect, colors["accent"], colors["accent"], radius=6)
        text_left += 18
    text_rect = (
        text_left,
        rect[1] + CARD_PADDING_Y - 2,
        rect[2] - CARD_PADDING_X,
        rect[1] + CARD_PADDING_Y + SECTION_TITLE_HEIGHT,
    )
    _draw_text(hdc, title, text_rect, fonts["section"], colors["title"], DT_LEFT | DT_SINGLELINE)


def _metric_card_height(metric_count, columns):
    rows = _metric_grid_rows(metric_count, columns)
    return CARD_PADDING_Y * 2 + SECTION_TITLE_HEIGHT + 12 + rows * METRIC_TILE_HEIGHT + (rows - 1) * METRIC_TILE_GAP


def _draw_metric_tile(hdc, rect, label, value, state):
    colors = state["colors"]
    fonts = state["fonts"]
    _draw_round_rect(hdc, rect, colors["chip"], colors["chip_border"], radius=16)
    label_rect = (rect[0] + 12, rect[1] + 10, rect[2] - 12, rect[1] + 28)
    value_rect = (rect[0] + 12, rect[1] + 26, rect[2] - 12, rect[3] - 10)
    value_font = fonts["value_compact"] if len(str(value)) > 16 else fonts["value"]
    _draw_text(hdc, label, label_rect, fonts["label"], colors["muted"], DT_LEFT | DT_SINGLELINE)
    _draw_text(hdc, value, value_rect, value_font, colors["title"], DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS)


def _draw_metric_card(hdc, rect, title, metrics, columns, state, icon=None):
    colors = state["colors"]
    _draw_round_rect(hdc, rect, colors["card"], colors["border"], radius=22)
    _draw_card_header(hdc, rect, title, state, icon)

    inner_left = rect[0] + CARD_PADDING_X
    inner_top = rect[1] + CARD_PADDING_Y + SECTION_TITLE_HEIGHT + 12
    inner_width = rect[2] - rect[0] - CARD_PADDING_X * 2
    tile_gap = METRIC_TILE_GAP
    tile_width = int((inner_width - tile_gap * (columns - 1)) / columns)
    row = 0
    col = 0

    for item in _normalize_metric_items(metrics):
        span = min(columns, item["span"])
        if col + span > columns:
            row += 1
            col = 0
        tile_left = inner_left + col * (tile_width + tile_gap)
        tile_top = inner_top + row * (METRIC_TILE_HEIGHT + tile_gap)
        tile_right = tile_left + tile_width * span + tile_gap * (span - 1)
        tile_rect = (
            tile_left,
            tile_top,
            tile_right,
            tile_top + METRIC_TILE_HEIGHT,
        )
        _draw_metric_tile(hdc, tile_rect, item["label"], item["value"], state)
        col += span
        if col >= columns:
            row += 1
            col = 0


def _calc_apps_card_height(apps):
    height = CARD_PADDING_Y * 2 + SECTION_TITLE_HEIGHT + 10
    if not apps:
        return height + 58
    for app in apps:
        is_browser = bool(app.get("is_browser", False))
        page_count = len(app.get("pages", []))
        block_height = 40
        if page_count:
            block_height += page_count * 24 + 8
        elif is_browser:
            block_height += 24
        height += block_height + APP_BLOCK_GAP
    return height


def _draw_apps_card(hdc, rect, apps, state, icon=None):
    colors = state["colors"]
    fonts = state["fonts"]
    _draw_round_rect(hdc, rect, colors["card"], colors["border"], radius=22)
    _draw_card_header(hdc, rect, "程序统计", state, icon)

    content_left = rect[0] + CARD_PADDING_X
    content_right = rect[2] - CARD_PADDING_X
    y = rect[1] + CARD_PADDING_Y + SECTION_TITLE_HEIGHT + 12

    if not apps:
        empty_rect = (content_left, y + 6, content_right, y + 40)
        _draw_text(hdc, "今日暂无程序活跃记录", empty_rect, fonts["body"], colors["muted"], DT_LEFT | DT_SINGLELINE)
        return

    for app in apps:
        app_name = _trim_text(app.get("name", "未知程序"), 28)
        duration = app.get("duration", "0s")
        pct = f"{app.get('pct', 0):.1f}%"
        is_browser = bool(app.get("is_browser", False))
        pages = app.get("pages", [])
        block_height = 40
        if pages:
            block_height += len(pages) * 24 + 8
        elif is_browser:
            block_height += 24
        block_rect = (content_left, y, content_right, y + block_height)
        _draw_round_rect(hdc, block_rect, colors["chip"], colors["chip_border"], radius=16)

        title_rect = (content_left + 14, y + 10, content_right - 150, y + 32)
        _draw_text(hdc, app_name, title_rect, fonts["body_bold"], colors["title"], DT_LEFT | DT_SINGLELINE)

        pct_badge = (content_right - 70, y + 8, content_right - 12, y + 30)
        duration_badge = (content_right - 148, y + 8, content_right - 76, y + 30)
        _draw_badge(hdc, duration_badge, duration, fonts["badge"], colors["accent_soft"], colors["accent_border"], colors["accent_text"])
        _draw_badge(hdc, pct_badge, pct, fonts["badge"], colors["chip"], colors["chip_border"], colors["body"])

        detail_y = y + 40

        for page in pages:
            page_name = _trim_text(page.get("name", "网页"), 42)
            page_duration = page.get("duration", "0s")
            page_name_rect = (content_left + 30, detail_y, content_right - 92, detail_y + 18)
            page_duration_rect = (content_right - 84, detail_y, content_right - 14, detail_y + 18)

            dot_rect = (content_left + 14, detail_y + 6, content_left + 20, detail_y + 12)
            _draw_round_rect(hdc, dot_rect, colors["muted_soft"], colors["muted_soft"], radius=4)
            _draw_text(hdc, page_name, page_name_rect, fonts["small"], colors["body"], DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS)
            _draw_text(hdc, page_duration, page_duration_rect, fonts["small"], colors["muted"], DT_RIGHT | DT_SINGLELINE)
            detail_y += 24

        if is_browser and not pages:
            empty_line_rect = (content_left + 14, detail_y, content_right - 14, detail_y + 18)
            _draw_text(hdc, "暂无网页细分记录", empty_line_rect, fonts["small"], colors["muted"], DT_LEFT | DT_SINGLELINE)

        y += block_height + APP_BLOCK_GAP


def _build_cards(report, client_width):
    cards = []
    available_width = max(320, client_width - WINDOW_PADDING * 2)
    content_width = min(MAX_CONTENT_WIDTH, available_width)
    content_left = max(WINDOW_PADDING, int((client_width - content_width) / 2))
    y = HEADER_HEIGHT

    if not report.get("segments"):
        empty_height = 170
        cards.append(
            {
                "kind": "empty",
                "rect": (content_left, y, content_left + content_width, y + empty_height),
            }
        )
        return cards, empty_height + WINDOW_PADDING

    overview_metrics = [
        _metric_item("总活跃时长", report.get("total_duration", "0s")),
        _metric_item("活跃段数", str(report.get("segments_count", 0))),
    ]
    overview_height = _metric_card_height(overview_metrics, 2)
    cards.append(
        {
            "kind": "metrics",
            "title": "活跃概览",
            "icon": "⚡",
            "rect": (content_left, y, content_left + content_width, y + overview_height),
            "metrics": overview_metrics,
            "columns": 2,
        }
    )
    y += overview_height + CARD_GAP

    keyboard_metrics = [
        _metric_item("总按键", f"{report['keyboard']['total_keys']} 次"),
        _metric_item("字符键", f"{report['keyboard']['total_chars']} 次"),
    ]
    clipboard_metrics = [
        _metric_item("复制", f"{report['clipboard']['copy']} 次"),
        _metric_item("粘贴", f"{report['clipboard']['paste']} 次"),
    ]
    half_width = int((content_width - CARD_GAP) / 2)
    small_card_height = _metric_card_height(keyboard_metrics, 2)
    cards.append(
        {
            "kind": "metrics",
            "title": "键盘统计",
            "icon": "⌨️",
            "rect": (content_left, y, content_left + half_width, y + small_card_height),
            "metrics": keyboard_metrics,
            "columns": 2,
        }
    )
    cards.append(
        {
            "kind": "metrics",
            "title": "剪贴板统计",
            "icon": "📋",
            "rect": (
                content_left + half_width + CARD_GAP,
                y,
                content_left + content_width,
                y + small_card_height,
            ),
            "metrics": clipboard_metrics,
            "columns": 2,
        }
    )
    y += small_card_height + CARD_GAP

    mouse_columns = 3
    mouse_metrics = [
        _metric_item("总点击", f"{report['mouse']['total_clicks']} 次"),
        _metric_item("左键", f"{report['mouse']['left_clicks']} 次"),
        _metric_item("右键", f"{report['mouse']['right_clicks']} 次"),
        _metric_item("滚轮", f"{report['mouse']['total_scroll']} 次"),
        _metric_item("向上", f"{report['mouse']['scroll_up']} 次"),
        _metric_item("向下", f"{report['mouse']['scroll_down']} 次"),
        _metric_item("移动", report["mouse"]["distance"], span=3),
    ]
    mouse_height = _metric_card_height(mouse_metrics, mouse_columns)
    cards.append(
        {
            "kind": "metrics",
            "title": "鼠标统计",
            "icon": "🖱️",
            "rect": (content_left, y, content_left + content_width, y + mouse_height),
            "metrics": mouse_metrics,
            "columns": mouse_columns,
        }
    )
    y += mouse_height + CARD_GAP

    apps_height = _calc_apps_card_height(report.get("apps", []))
    cards.append(
        {
            "kind": "apps",
            "icon": "💻",
            "rect": (content_left, y, content_left + content_width, y + apps_height),
            "apps": report.get("apps", []),
        }
    )
    y += apps_height + WINDOW_PADDING
    return cards, y - HEADER_HEIGHT


def _set_scroll(hwnd, state, client_height):
    visible_height = max(1, client_height - HEADER_HEIGHT)
    max_scroll = max(0, state["content_height"] - visible_height)
    state["scroll_y"] = max(0, min(state["scroll_y"], max_scroll))
    user32.ShowScrollBar(hwnd, SB_VERT, False)


def _clamp_scroll(hwnd, state, new_scroll):
    client_rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client_rect))
    client_height = client_rect.bottom - client_rect.top
    visible_height = max(1, client_height - HEADER_HEIGHT)
    max_scroll = max(0, state["content_height"] - visible_height)
    bounded = max(0, min(int(new_scroll), max_scroll))
    if bounded == state["scroll_y"]:
        return
    state["scroll_y"] = bounded
    _set_scroll(hwnd, state, client_height)
    user32.InvalidateRect(hwnd, None, True)


def _refresh_existing_window(report_data, title):
    with _report_window_lock:
        hwnd = _report_window_state["hwnd"]
        state = _report_window_state["state"]

    if not _is_live_window(hwnd) or state is None:
        return False

    normalized_report = _normalize_report_data(report_data)
    state["report"] = normalized_report
    state["title_text"] = title
    state["subtitle_text"] = _build_subtitle_text(normalized_report.get("date"))
    state["scroll_y"] = 0
    state["layout_dirty"] = True
    state["last_error"] = None
    user32.SetWindowTextW(hwnd, title)
    user32.InvalidateRect(hwnd, None, True)
    return _focus_report_window(hwnd)


def _run_report_window(report_data, title):
    hinstance = kernel32.GetModuleHandleW(None)
    class_name = f"TimeCraftReportWindow_{kernel32.GetCurrentThreadId()}_{int(time.time() * 1000)}"
    normalized_report = _normalize_report_data(report_data)

    colors = {
        "root": _rgb(244, 247, 250),
        "card": _rgb(255, 255, 255),
        "border": _rgb(226, 232, 240),
        "frame": _rgb(214, 223, 234),
        "title": _rgb(15, 23, 42),
        "body": _rgb(51, 65, 85),
        "muted": _rgb(100, 116, 139),
        "muted_soft": _rgb(203, 213, 225),
        "accent": _rgb(14, 165, 233),
        "accent_soft": _rgb(240, 249, 255),
        "accent_border": _rgb(186, 230, 253),
        "accent_text": _rgb(3, 105, 161),
        "chip": _rgb(248, 250, 252),
        "chip_border": _rgb(226, 232, 240),
        "close_hover": _rgb(241, 245, 249),
    }
    fonts = {
        "title": None,
        "subtitle": None,
        "section": None,
        "label": None,
        "value": None,
        "value_compact": None,
        "body": None,
        "body_bold": None,
        "small": None,
        "badge": None,
        "close": None,
    }
    state = {
        "hwnd": None,
        "report": normalized_report,
        "title_text": title,
        "subtitle_text": _build_subtitle_text(normalized_report.get("date")),
        "colors": colors,
        "fonts": fonts,
        "root_brush": gdi32.CreateSolidBrush(colors["root"]),
        "close_rect": (0, 0, 0, 0),
        "close_hot": False,
        "scroll_y": 0,
        "content_height": 0,
        "cards": [],
        "layout_dirty": True,
        "last_error": None,
    }

    def update_layout(hwnd):
        client_rect = ctypes.wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client_rect))
        client_width = client_rect.right - client_rect.left
        client_height = client_rect.bottom - client_rect.top
        state["close_rect"] = (
            client_width - WINDOW_PADDING - CLOSE_BUTTON_SIZE,
            12,
            client_width - WINDOW_PADDING,
            12 + CLOSE_BUTTON_SIZE,
        )
        state["cards"], state["content_height"] = _build_cards(state["report"], client_width)
        state["layout_dirty"] = False
        _set_scroll(hwnd, state, client_height)

    def paint_window(hwnd):
        paint = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(paint))
        try:
            if state["layout_dirty"]:
                update_layout(hwnd)
            client_rect = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(client_rect))
            user32.FillRect(hdc, ctypes.byref(client_rect), state["root_brush"])

            client_width = client_rect.right - client_rect.left
            client_height = client_rect.bottom - client_rect.top
            _draw_window_frame(hdc, client_width, client_height, state)

            header_title_rect = (WINDOW_PADDING, 11, client_width - 84, 33)
            header_subtitle_rect = (WINDOW_PADDING, 35, client_width - 84, 50)
            close_rect = state["close_rect"]

            _draw_text(hdc, state["title_text"], header_title_rect, fonts["title"], colors["title"], DT_LEFT | DT_VCENTER | DT_SINGLELINE)
            _draw_text(hdc, state["subtitle_text"], header_subtitle_rect, fonts["subtitle"], colors["muted"], DT_LEFT | DT_VCENTER | DT_SINGLELINE)

            if state["close_hot"]:
                _draw_round_rect(hdc, close_rect, colors["close_hover"], colors["close_hover"], radius=14)
            _draw_text(hdc, "×", close_rect, fonts["close"], colors["muted"], DT_CENTER | DT_VCENTER | DT_SINGLELINE)

            saved_dc = gdi32.SaveDC(hdc)
            gdi32.IntersectClipRect(hdc, 0, HEADER_HEIGHT, client_width, client_height)
            for card in state["cards"]:
                card_rect = card["rect"]
                visible_rect = (
                    card_rect[0],
                    card_rect[1] - state["scroll_y"],
                    card_rect[2],
                    card_rect[3] - state["scroll_y"],
                )
                if visible_rect[3] < HEADER_HEIGHT or visible_rect[1] > client_height:
                    continue

                if card["kind"] == "metrics":
                    _draw_metric_card(
                        hdc,
                        visible_rect,
                        card["title"],
                        card["metrics"],
                        card["columns"],
                        state,
                        card.get("icon"),
                    )
                elif card["kind"] == "apps":
                    _draw_apps_card(hdc, visible_rect, card["apps"], state, card.get("icon"))
                else:
                    _draw_round_rect(hdc, visible_rect, colors["card"], colors["border"], radius=22)
                    _draw_text(
                        hdc,
                        "今日暂无监控数据",
                        (visible_rect[0] + 24, visible_rect[1] + 54, visible_rect[2] - 24, visible_rect[1] + 88),
                        fonts["body_bold"],
                        colors["title"],
                        DT_LEFT | DT_SINGLELINE,
                    )
                    legacy_text = state["report"].get("legacy_text", "")
                    if legacy_text:
                        _draw_text(
                            hdc,
                            _trim_text(legacy_text.replace("\r", " ").replace("\n", " "), 80),
                            (visible_rect[0] + 24, visible_rect[1] + 88, visible_rect[2] - 24, visible_rect[1] + 120),
                            fonts["body"],
                            colors["muted"],
                            DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS,
                        )
                    else:
                        _draw_text(
                            hdc,
                            "先正常使用一段时间，报告卡片会在这里自动出现。",
                            (visible_rect[0] + 24, visible_rect[1] + 88, visible_rect[2] - 24, visible_rect[1] + 120),
                            fonts["body"],
                            colors["muted"],
                            DT_LEFT | DT_SINGLELINE,
                        )
            gdi32.RestoreDC(hdc, saved_dc)
            state["last_error"] = None
        except Exception as exc:
            state["last_error"] = repr(exc)
            client_rect = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(client_rect))
            user32.FillRect(hdc, ctypes.byref(client_rect), state["root_brush"])
            _draw_window_frame(hdc, client_rect.right - client_rect.left, client_rect.bottom - client_rect.top, state)
            fallback_rect = (
                WINDOW_PADDING,
                HEADER_HEIGHT,
                client_rect.right - WINDOW_PADDING,
                HEADER_HEIGHT + 164,
            )
            _draw_round_rect(hdc, fallback_rect, colors["card"], colors["border"], radius=22)
            _draw_text(
                hdc,
                "报告渲染失败",
                (fallback_rect[0] + 24, fallback_rect[1] + 28, fallback_rect[2] - 24, fallback_rect[1] + 58),
                fonts["body_bold"],
                colors["title"],
                DT_LEFT | DT_SINGLELINE,
            )
            _draw_text(
                hdc,
                _trim_text(state["last_error"], 110),
                (fallback_rect[0] + 24, fallback_rect[1] + 70, fallback_rect[2] - 24, fallback_rect[1] + 108),
                fonts["body"],
                colors["muted"],
                DT_LEFT | DT_WORDBREAK,
            )
        finally:
            user32.EndPaint(hwnd, ctypes.byref(paint))

    def window_proc(hwnd, msg, wparam, lparam):
        if msg == WM_CREATE:
            state["hwnd"] = hwnd
            fonts["title"] = _create_font(16, 600, "Microsoft YaHei UI")
            fonts["subtitle"] = _create_font(9, 400, "Segoe UI")
            fonts["section"] = _create_font(14, 600, "Segoe UI")
            fonts["section_icon"] = _create_font(15, 400, "Segoe UI Emoji")
            fonts["label"] = _create_font(10, 400, "Segoe UI")
            fonts["value"] = _create_font(17, 600, "Segoe UI")
            fonts["value_compact"] = _create_font(14, 600, "Segoe UI")
            fonts["body"] = _create_font(13, 400, "Microsoft YaHei UI")
            fonts["body_bold"] = _create_font(14, 600, "Microsoft YaHei UI")
            fonts["small"] = _create_font(11, 400, "Microsoft YaHei UI")
            fonts["badge"] = _create_font(10, 500, "Segoe UI")
            fonts["close"] = _create_font(15, 600, "Segoe UI")
            with _report_window_lock:
                _report_window_state["hwnd"] = hwnd
                _report_window_state["state"] = state
            update_layout(hwnd)
            return 0

        if msg == WM_ERASEBKGND:
            return 1

        if msg == WM_SIZE:
            update_layout(hwnd)
            user32.InvalidateRect(hwnd, None, True)
            return 0

        if msg == WM_PAINT:
            paint_window(hwnd)
            return 0

        if msg == WM_NCHITTEST:
            point = ctypes.wintypes.POINT(
                ctypes.c_short(lparam & 0xFFFF).value,
                ctypes.c_short((lparam >> 16) & 0xFFFF).value,
            )
            user32.ScreenToClient(hwnd, ctypes.byref(point))
            if _point_in_rect(point.x, point.y, state["close_rect"]):
                return HTCLIENT
            if 0 <= point.y <= DRAG_REGION_BOTTOM:
                return HTCAPTION
            return HTCLIENT

        if msg == WM_MOUSEMOVE:
            point_x = ctypes.c_short(lparam & 0xFFFF).value
            point_y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            hot = _point_in_rect(point_x, point_y, state["close_rect"])
            if hot != state["close_hot"]:
                state["close_hot"] = hot
                user32.InvalidateRect(hwnd, None, True)
            return 0

        if msg == WM_LBUTTONUP:
            point_x = ctypes.c_short(lparam & 0xFFFF).value
            point_y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            if _point_in_rect(point_x, point_y, state["close_rect"]):
                user32.DestroyWindow(hwnd)
                return 0
            return 0

        if msg == WM_MOUSEWHEEL:
            delta = ctypes.c_short((wparam >> 16) & 0xFFFF).value
            _clamp_scroll(hwnd, state, state["scroll_y"] - int(delta / 120) * SCROLL_STEP)
            return 0

        if msg == WM_VSCROLL:
            action = wparam & 0xFFFF
            current = state["scroll_y"]
            client_rect = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(client_rect))
            page_step = max(80, client_rect.bottom - client_rect.top - HEADER_HEIGHT)

            if action == SB_LINEUP:
                current -= SCROLL_STEP
            elif action == SB_LINEDOWN:
                current += SCROLL_STEP
            elif action == SB_PAGEUP:
                current -= page_step
            elif action == SB_PAGEDOWN:
                current += page_step
            elif action in (SB_THUMBPOSITION, SB_THUMBTRACK):
                current = (wparam >> 16) & 0xFFFF
            elif action == SB_TOP:
                current = 0
            elif action == SB_BOTTOM:
                current = state["content_height"]

            _clamp_scroll(hwnd, state, current)
            return 0

        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0

        if msg == WM_DESTROY:
            with _report_window_lock:
                if _report_window_state["hwnd"] == hwnd:
                    _report_window_state["thread"] = None
                    _report_window_state["hwnd"] = None
                    _report_window_state["state"] = None
            for font in fonts.values():
                if font:
                    gdi32.DeleteObject(font)
            if state["root_brush"]:
                gdi32.DeleteObject(state["root_brush"])
                state["root_brush"] = None
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    wndproc = WNDPROC(window_proc)
    wnd_class = WNDCLASSW()
    wnd_class.lpfnWndProc = wndproc
    wnd_class.hInstance = hinstance
    wnd_class.hCursor = user32.LoadCursorW(None, ctypes.wintypes.LPCWSTR(IDC_ARROW))
    wnd_class.hbrBackground = state["root_brush"]
    wnd_class.lpszClassName = class_name
    if not user32.RegisterClassW(ctypes.byref(wnd_class)):
        raise ctypes.WinError()

    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    width = 592
    height = 620
    x = max(60, (screen_w - width) // 2)
    y = max(40, (screen_h - height) // 2)

    hwnd = user32.CreateWindowExW(
        WS_EX_APPWINDOW,
        class_name,
        title,
        WS_POPUP | WS_VISIBLE,
        x,
        y,
        width,
        height,
        None,
        None,
        hinstance,
        None,
    )
    if not hwnd:
        user32.UnregisterClassW(class_name, hinstance)
        raise ctypes.WinError()

    _apply_window_style(hwnd)
    user32.ShowWindow(hwnd, SW_SHOW)
    user32.UpdateWindow(hwnd)
    user32.SetForegroundWindow(hwnd)

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    user32.UnregisterClassW(class_name, hinstance)


def show_report_window(report_data, title="TimeCraft 效率报告"):
    if _refresh_existing_window(report_data, title):
        return
    thread = threading.Thread(
        target=_run_report_window,
        args=(report_data, title),
        daemon=True,
        name="report-window",
    )
    with _report_window_lock:
        _report_window_state["thread"] = thread
    thread.start()
