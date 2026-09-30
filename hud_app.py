import os
import platform
import subprocess
import tkinter as tk
from typing import Optional, Tuple
from analyzer import AntigravityContextAnalyzer, ChatContextStats

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

FONT_MAIN = "SF Pro Text" if IS_MACOS else "Segoe UI"
FONT_MONO = "Menlo" if IS_MACOS else "Consolas"

# Native Antigravity / Google DeepMind Dark Carbon Theme
THEME = {
    "bg": "#131314",       # Deep carbon background
    "surface": "#1e1f22",  # Elevated pill surface
    "border": "#2b2d31",   # Subtle 1px hairline border
    "text": "#e3e3e3",     # Primary crisp text
    "muted": "#8e918f",    # Neutral muted gray
    "accent": "#a8c7fa",   # Soft Google blue
    "sys": "#c58af9",      # Soft lavender (Rules/Skills)
    "msg": "#8ab4f8",      # Soft blue (Chat)
    "tool": "#fdd663",     # Soft warm gold (Tools/Files)
    "think": "#78d9ec",    # Soft cyan (Thinking)
}

WIN_W = 248
WIN_H = 88
WIN_H_MINI = 26

def fmt_k(tokens: int) -> str:
    if tokens >= 1000:
        return f"{tokens / 1000:.1f}k"
    return str(tokens)

# Windows Win32 API imports (conditional to avoid crash on macOS)
if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    dwmapi = ctypes.windll.dwmapi
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)


def _get_antigravity_rect_windows(
    hud_rect: Optional[Tuple[int, int, int, int]] = None,
    hud_hwnd: int = 0,
) -> Optional[Tuple[int, int, int, int, bool, bool]]:
    try:
        hDesk = user32.OpenInputDesktop(0, False, 0x01FF)
        if hDesk:
            user32.SetThreadDesktop(hDesk)
    except Exception:
        pass

    fg_hwnd = user32.GetForegroundWindow()
    candidates = []

    def enum_cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return True
        hproc = kernel32.OpenProcess(0x1000, False, pid.value)
        if not hproc:
            return True
        try:
            buf = ctypes.create_unicode_buffer(512)
            size = ctypes.wintypes.DWORD(512)
            if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
                if buf.value.lower().endswith("antigravity.exe"):
                    iconic = bool(user32.IsIconic(hwnd))
                    rect = (ctypes.c_long * 4)()
                    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
                        user32.GetWindowRect(hwnd, rect)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    if iconic or (w > 350 and h > 250):
                        priority = 2 if hwnd == fg_hwnd else 1
                        candidates.append((priority, w * h, rect[0], rect[1], rect[2], rect[3], iconic, hwnd))
        finally:
            kernel32.CloseHandle(hproc)
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    _, _, l, t, r, b, iconic, agy_hwnd = candidates[0]

    is_covered = False
    if fg_hwnd and fg_hwnd != agy_hwnd and fg_hwnd != hud_hwnd and not iconic:
        fg_rect = (ctypes.c_long * 4)()
        if dwmapi.DwmGetWindowAttribute(fg_hwnd, 9, ctypes.byref(fg_rect), ctypes.sizeof(fg_rect)) != 0:
            user32.GetWindowRect(fg_hwnd, fg_rect)
        if hud_rect:
            hl, ht, hr, hb = hud_rect
            fl, ft, fr, fb = fg_rect[0], fg_rect[1], fg_rect[2], fg_rect[3]
            ow = min(hr, fr) - max(hl, fl)
            oh = min(hb, fb) - max(ht, ft)
            if ow > 15 and oh > 15:
                is_covered = True

    return (l, t, r, b, iconic, is_covered)


def _get_antigravity_rect_macos(
    hud_rect: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[int, int, int, int, bool, bool]]:
    script = '''
    tell application "System Events"
        if not (exists process "Antigravity") then return "NOT_RUNNING"
        set frontProc to first application process whose frontmost is true
        set frontName to name of frontProc
        tell process "Antigravity"
            if (count of windows) is 0 then return "NO_WINDOW"
            set w to window 1
            set isMin to value of attribute "AXMinimized" of w
            set {wx, wy} to position of w
            set {ww, wh} to size of w
        end tell
        if frontName is not "Antigravity" and (count of windows of frontProc) > 0 then
            set fw to window 1 of frontProc
            set {fx, fy} to position of fw
            set {fw_w, fw_h} to size of fw
            return (wx as text) & "," & (wy as text) & "," & (ww as text) & "," & (wh as text) & "," & (isMin as text) & "," & (fx as text) & "," & (fy as text) & "," & (fw_w as text) & "," & (fw_h as text)
        end if
        return (wx as text) & "," & (wy as text) & "," & (ww as text) & "," & (wh as text) & "," & (isMin as text) & ",0,0,0,0"
    end tell
    '''
    try:
        res = subprocess.check_output(["osascript", "-e", script], text=True, timeout=0.8).strip()
        if res in ("NOT_RUNNING", "NO_WINDOW", ""):
            return None
        p = res.split(",")
        if len(p) >= 9:
            wx, wy, ww, wh = int(p[0]), int(p[1]), int(p[2]), int(p[3])
            is_min = p[4].lower() == "true"
            fx, fy, fw_w, fw_h = int(p[5]), int(p[6]), int(p[7]), int(p[8])
            is_covered = False
            if hud_rect and fw_w > 0 and fw_h > 0:
                hl, ht, hr, hb = hud_rect
                fl, ft, fr, fb = fx, fy, fx + fw_w, fy + fw_h
                overlap_w = min(hr, fr) - max(hl, fl)
                overlap_h = min(hb, fb) - max(ht, ft)
                if overlap_w > 12 and overlap_h > 12:
                    is_covered = True
            return (wx, wy, wx + ww, wy + wh, is_min, is_covered)
    except Exception:
        pass
    return None


def get_antigravity_window_rect(
    hud_rect: Optional[Tuple[int, int, int, int]] = None,
    hud_hwnd: int = 0,
) -> Optional[Tuple[int, int, int, int, bool, bool]]:
    if IS_WINDOWS:
        return _get_antigravity_rect_windows(hud_rect, hud_hwnd)
    elif IS_MACOS:
        return _get_antigravity_rect_macos(hud_rect)
    return None


class DockedAntigravityHud:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.analyzer = AntigravityContextAnalyzer()
        self.is_mini = False
        self.is_hidden = False
        self.offset_x = -16
        self.offset_y = -32
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._last_agy_rect = None

        self._setup_window()
        self._build_ui()
        self.track_window_loop()
        self.refresh_stats_loop()

    def _setup_window(self):
        if IS_WINDOWS:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        self.root.title("AGY Context HUD")
        self.root.configure(bg=THEME["bg"])
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{WIN_W}x{WIN_H}+{sw - WIN_W - 20}+{sh - WIN_H - 60}")
        self.root.deiconify()
        self.root.lift()

    def _start_drag(self, event):
        self._dragging = True
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        nx = self.root.winfo_x() + (event.x - self._drag_start_x)
        ny = self.root.winfo_y() + (event.y - self._drag_start_y)
        cur_h = WIN_H_MINI if self.is_mini else WIN_H
        self.root.geometry(f"{WIN_W}x{cur_h}+{nx}+{ny}")
        if self._last_agy_rect:
            _, _, r, b, _ = self._last_agy_rect
            self.offset_x = nx - (r - WIN_W)
            self.offset_y = ny - (b - cur_h)

    def _end_drag(self, _event):
        self._dragging = False

    def toggle_mini(self):
        self.is_mini = not self.is_mini
        if self.is_mini:
            self.body.pack_forget()
            self.btn_mini.config(text="▢")
        else:
            self.body.pack(fill="both", expand=True, padx=10, pady=(2, 7))
            self.btn_mini.config(text="—")

    def copy_handoff(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("сохрани сессию в HANDOFF.md для переезда в новый чат")
        self.btn_copy.config(text="✓", fg="#81c995")
        self.root.after(1500, lambda: self.btn_copy.config(text="⎘", fg=THEME["muted"]))

    def _build_ui(self):
        self.outer = tk.Frame(self.root, bg=THEME["bg"], highlightbackground=THEME["border"], highlightthickness=1)
        self.outer.pack(fill="both", expand=True)

        # Header
        self.hdr = tk.Frame(self.outer, bg=THEME["bg"], height=24, cursor="fleur")
        self.hdr.pack(fill="x", padx=6, pady=(3, 0))
        for w in (self.hdr,):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", self._end_drag)

        self.dot = tk.Label(self.hdr, text="●", fg="#81c995", bg=THEME["bg"], font=(FONT_MAIN, 8))
        self.dot.pack(side="left", padx=(2, 4))

        self.title_lbl = tk.Label(self.hdr, text="Antigravity", fg=THEME["text"], bg=THEME["bg"], font=(FONT_MAIN, 8, "bold"))
        self.title_lbl.pack(side="left")
        for w in (self.dot, self.title_lbl):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", self._end_drag)

        btn_close = tk.Button(
            self.hdr, text="×", command=self.root.destroy, bg=THEME["bg"], fg=THEME["muted"],
            bd=0, font=(FONT_MAIN, 9), activebackground=THEME["surface"], activeforeground=THEME["text"], cursor="hand2"
        )
        btn_close.pack(side="right", padx=(2, 0))

        self.btn_mini = tk.Button(
            self.hdr, text="—", command=self.toggle_mini, bg=THEME["bg"], fg=THEME["muted"],
            bd=0, font=(FONT_MAIN, 8), activebackground=THEME["surface"], activeforeground=THEME["text"], cursor="hand2"
        )
        self.btn_mini.pack(side="right", padx=2)

        self.btn_copy = tk.Button(
            self.hdr, text="⎘", command=self.copy_handoff, bg=THEME["bg"], fg=THEME["muted"],
            bd=0, font=(FONT_MAIN, 9), activebackground=THEME["surface"], activeforeground=THEME["accent"], cursor="hand2"
        )
        self.btn_copy.pack(side="right", padx=2)

        # Body
        self.body = tk.Frame(self.outer, bg=THEME["bg"])
        self.body.pack(fill="both", expand=True, padx=10, pady=(2, 7))

        r1 = tk.Frame(self.body, bg=THEME["bg"])
        r1.pack(fill="x")
        self.used_lbl = tk.Label(r1, text="0k / 150k", fg=THEME["text"], bg=THEME["bg"], font=(FONT_MAIN, 8, "bold"))
        self.used_lbl.pack(side="left")
        self.free_lbl = tk.Label(r1, text="своб. 150k", fg=THEME["muted"], bg=THEME["bg"], font=(FONT_MAIN, 8))
        self.free_lbl.pack(side="right")

        self.bar = tk.Canvas(self.body, height=4, bg=THEME["surface"], highlightthickness=0)
        self.bar.pack(fill="x", pady=(5, 6))

        r2 = tk.Frame(self.body, bg=THEME["surface"], padx=6, pady=2)
        r2.pack(fill="x")
        self.cat_lbls = {}
        for key, tag, col in [
            ("sys", "Прав ", THEME["sys"]),
            ("msg", "Чат ", THEME["msg"]),
            ("tool", "Тул ", THEME["tool"]),
            ("think", "Мысл ", THEME["think"]),
        ]:
            lbl = tk.Label(r2, text=f"{tag}0k", fg=col, bg=THEME["surface"], font=(FONT_MAIN, 7))
            lbl.pack(side="left", expand=True)
            self.cat_lbls[key] = (tag, lbl)

    def track_window_loop(self):
        if not self._dragging:
            cur_h = WIN_H_MINI if self.is_mini else WIN_H
            hx = self.root.winfo_x()
            hy = self.root.winfo_y()
            hud_rect = (hx, hy, hx + WIN_W, hy + cur_h)
            hud_hwnd = 0
            if IS_WINDOWS:
                try:
                    hud_hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                except Exception:
                    pass

            rect = get_antigravity_window_rect(hud_rect, hud_hwnd)
            if rect is None or rect[4] or rect[5]:  # Closed, minimized, or covered by overlapping window
                if not self.is_hidden:
                    self.is_hidden = True
                    self.root.withdraw()
            else:
                if self.is_hidden:
                    self.is_hidden = False
                    self.root.deiconify()
                    self.root.lift()
                self._last_agy_rect = rect
                _, _, r, b, _, _ = rect
                tx = r - WIN_W + self.offset_x
                ty = b - cur_h + self.offset_y
                self.root.geometry(f"{WIN_W}x{cur_h}+{tx}+{ty}")
        
        # 35ms on Windows, 100ms on macOS (AppleScript process budget)
        delay = 35 if IS_WINDOWS else 100
        self.root.after(delay, self.track_window_loop)

    def refresh_stats_loop(self):
        if not self.is_hidden:
            stats = self.analyzer.get_active_chat()
            if stats:
                zone = stats.status_zone
                self.dot.config(fg=zone["color"])
                short = stats.title[:20] + ("…" if len(stats.title) > 20 else "")
                if self.is_mini:
                    self.title_lbl.config(text=f"{short} · {fmt_k(stats.total_tokens)} ({stats.usage_percent:.0f}%)")
                else:
                    self.title_lbl.config(text=short)
                self.used_lbl.config(text=f"{fmt_k(stats.total_tokens)} / 150k ({stats.usage_percent:.0f}%)")
                self.free_lbl.config(text=f"своб. {fmt_k(stats.free_smart_tokens)}", fg=zone["color"])

                self.bar.delete("all")
                w = max(self.bar.winfo_width(), WIN_W - 22)
                limit = max(stats.smart_limit, stats.total_tokens)
                x = 0.0
                for tok, col in [
                    (stats.system_tokens, THEME["sys"]),
                    (stats.messages_tokens, THEME["msg"]),
                    (stats.tools_tokens, THEME["tool"]),
                    (stats.thinking_tokens, THEME["think"]),
                ]:
                    sw = (tok / limit) * w
                    if sw > 0.3:
                        self.bar.create_rectangle(x, 0, x + sw, 4, fill=col, outline="")
                        x += sw

                for key, val in [
                    ("sys", stats.system_tokens),
                    ("msg", stats.messages_tokens),
                    ("tool", stats.tools_tokens),
                    ("think", stats.thinking_tokens),
                ]:
                    tag, lbl = self.cat_lbls[key]
                    lbl.config(text=f"{tag}{fmt_k(val)}")
        self.root.after(1200, self.refresh_stats_loop)


if __name__ == "__main__":
    root = tk.Tk()
    DockedAntigravityHud(root)
    root.mainloop()

