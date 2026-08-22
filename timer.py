# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import colorchooser
import ctypes
import ctypes.wintypes
import time
import datetime
import json
import os
import sys
import winsound
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRESETS_FILE = os.path.join(SCRIPT_DIR, "timer_presets.json")
PROJECTOR_CFG = os.path.join(SCRIPT_DIR, "projector_cfg.json")


class MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szDevice", ctypes.wintypes.WCHAR * 32),
    ]


def get_monitors():
    monitors = []
    _enum = ctypes.windll.user32.EnumDisplayMonitors
    _info = ctypes.windll.user32.GetMonitorInfoW
    PROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.wintypes.HMONITOR,
                               ctypes.wintypes.HDC, ctypes.POINTER(ctypes.wintypes.RECT),
                               ctypes.wintypes.LPARAM)

    def cb(hmon, hdc, lprect, lparam):
        mi = MONITORINFOEX()
        mi.cbSize = ctypes.sizeof(MONITORINFOEX)
        if _info(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            monitors.append({"x": r.left, "y": r.top,
                             "w": r.right - r.left, "h": r.bottom - r.top,
                             "primary": bool(mi.dwFlags & 1)})
        return 1
    _enum(0, 0, PROC(cb), 0)
    return monitors


def get_second_monitor():
    ms = get_monitors()
    for m in ms:
        if not m["primary"]:
            return m
    return ms[0] if ms else {"x": 0, "y": 0, "w": 1920, "h": 1080, "primary": True}


BG = "#0b0f1c"
CARD = "#141a2b"
BORDER = "#2e3a55"
INP = "#1e2740"
FG = "#e0e6f0"
DIM = "#5a6a8a"
LBL = "#7b93cc"
ACC = "#6f9aff"
GRN = "#16a34a"
YLW = "#eab308"
RED = "#dc2626"
PRJ_BG = "#080b16"


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Rounded Button ──

class RBtn(tk.Canvas):
    def __init__(self, parent, text, bg, fg="#fff", command=None, width=100, height=36, radius=12, font=("Segoe UI", 10, "bold")):
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg") if hasattr(parent, "cget") else BG,
                         highlightthickness=0, bd=0)
        self._cmd = command
        self._bg = bg
        self._fg = fg
        self._bw = width
        self._bh = height
        self._r = radius
        self._text = text
        self._font = font
        self._draw(bg)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._draw(self._lighten(bg, 0.15)))
        self.bind("<Leave>", lambda e: self._draw(bg))

    def _draw(self, bg):
        self.delete("all")
        self._round_rect(0, 0, self._bw, self._bh, self._r, fill=bg, outline="")
        self.create_text(self._bw // 2, self._bh // 2, text=self._text, fill=self._fg, font=self._font)

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r,
               x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _on_click(self, _):
        if self._cmd:
            self._cmd()

    @staticmethod
    def _lighten(hex_color, factor):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"


# ── Main App ──

class TimerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Timer | DAps")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(10, self.root.deiconify)

        self.remaining = 0
        self.total = 0
        self.running = False
        self.paused = False
        self.tid = None
        self.proj = None
        self.proj_chars = []
        self.color = ACC
        self.presets = load_json(PRESETS_FILE, [])
        self.pcfg = load_json(PROJECTOR_CFG, {})

        self.prj_bg = self.pcfg.get("bg", PRJ_BG)
        self.prj_timer_color = self.pcfg.get("timer_color", ACC)
        self.prj_label_color = self.pcfg.get("label_color", LBL)
        self.prj_status_color = self.pcfg.get("status_color", DIM)
        self.prj_font_size = self.pcfg.get("font_size", 200)
        self.prj_show_bar = self.pcfg.get("show_bar", True)
        self.prj_bar_color = self.pcfg.get("bar_color", ACC)
        self.prj_bar_height = self.pcfg.get("bar_height", 8)

        self._build()
        self._center()
        self._update_display()
        self._set_icon()

    def _set_icon(self):
        icon_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "timer_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

    def _center(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"{w}x{h}+{sw - w - 30}+50")

    def _build(self):
        root = self.root

        bar = tk.Frame(root, bg=CARD, height=32)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="  \u0422\u0410\u0419\u041c\u0415\u0420", font=("Segoe UI", 9, "bold"),
                 fg=ACC, bg=CARD).pack(side="left")
        tk.Button(bar, text=" \u2014 ", font=("Segoe UI", 10, "bold"), bg=CARD, fg=DIM,
                  activebackground=BORDER, activeforeground=FG, relief="flat", bd=0,
                  command=root.iconify).pack(side="right")
        tk.Button(bar, text=" \u2715 ", font=("Segoe UI", 10, "bold"), bg=CARD, fg=RED,
                  activebackground="#7f1d1d", activeforeground="#fff", relief="flat", bd=0,
                  command=self._on_close).pack(side="right")

        card = tk.Frame(root, bg=CARD)
        card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        inner = tk.Frame(card, bg=CARD, padx=14, pady=8)
        inner.pack(fill="both", expand=True)

        self.time_lbl = tk.Label(inner, text="00:00:00", font=("Consolas", 44, "bold"), fg=ACC, bg=CARD)
        self.time_lbl.pack(pady=(4, 2))

        self.status_lbl = tk.Label(inner, text="\u041e\u0447\u0456\u043a\u0443\u0432\u0430\u043d\u043d\u044f",
                                   font=("Segoe UI", 10), fg=DIM, bg=CARD)
        self.status_lbl.pack(pady=(0, 8))

        qf = tk.Frame(inner, bg=CARD)
        qf.pack(fill="x", pady=(0, 6))
        for i, (t, s) in enumerate([
            ("-10\u043c", -600), ("-5\u043c", -300), ("-1\u043c", -60),
            ("+1\u043c", 60), ("+5\u043c", 300), ("+10\u043c", 600),
        ]):
            qf.columnconfigure(i, weight=1)
            RBtn(qf, t, INP, FG, command=lambda d=s: self._adjust(d), width=55, height=30, radius=10,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=i, sticky="ew", padx=2)

        self.dur_frame = tk.Frame(inner, bg=CARD)
        self.dur_frame.pack(fill="x", pady=(0, 4))
        self._lbl(self.dur_frame, "\u0425\u0432\u0438\u043b\u0438\u043d\u0438")
        self.min_var = tk.StringVar(value="15")
        tk.Entry(self.dur_frame, textvariable=self.min_var, font=("Segoe UI", 12), bg=INP, fg=FG,
                 insertbackground=FG, relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACC).pack(fill="x", ipady=4, pady=(0, 4))
        self._lbl(self.dur_frame, "\u0421\u0435\u043a\u0443\u043d\u0434\u0438")
        self.sec_var = tk.StringVar(value="0")
        tk.Entry(self.dur_frame, textvariable=self.sec_var, font=("Segoe UI", 12), bg=INP, fg=FG,
                 insertbackground=FG, relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACC).pack(fill="x", ipady=4, pady=(0, 4))

        self._lbl(inner, "\u0420\u0435\u0436\u0438\u043c")
        self.mode_var = tk.StringVar(value="\u0417\u043e\u0440\u043e\u0442\u043d\u0456\u0439 \u0432\u0456\u0434\u043b\u0456\u043a")
        om = tk.OptionMenu(inner, self.mode_var,
                           "\u0417\u043e\u0440\u043e\u0442\u043d\u0456\u0439 \u0432\u0456\u0434\u043b\u0456\u043a",
                           "\u0414\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0433\u043e \u0447\u0430\u0441\u0443",
                           command=self._on_mode)
        om.configure(font=("Segoe UI", 10), bg=INP, fg=FG, activebackground=BORDER,
                     activeforeground=FG, highlightthickness=0, relief="flat", indicatoron=True)
        om["menu"].configure(bg=INP, fg=FG, activebackground=ACC, activeforeground="#fff")
        om.pack(fill="x", ipady=2, pady=(0, 4))
        self.mode_var.trace_add("write", lambda *_: self._on_mode())

        self.time_frame = tk.Frame(inner, bg=CARD)
        self._lbl(self.time_frame, "\u0427\u0430\u0441 (\u0413\u0413:\u0425\u0425)")
        self.time_var = tk.StringVar(value="12:00")
        tk.Entry(self.time_frame, textvariable=self.time_var, font=("Segoe UI", 12), bg=INP, fg=FG,
                 insertbackground=FG, relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACC).pack(fill="x", ipady=4, pady=(0, 4))
        self.time_frame.pack_forget()

        self._lbl(inner, "\u0422\u0435\u043a\u0441\u0442")
        self.lbl_var = tk.StringVar(value="\u0421\u0435\u043c\u0456\u043d\u0430\u0440 \u043f\u043e\u0447\u043d\u0435\u0442\u044c\u0441\u044f \u0447\u0435\u0440\u0435\u0437:")
        tk.Entry(inner, textvariable=self.lbl_var, font=("Segoe UI", 10), bg=INP, fg=FG,
                 insertbackground=FG, relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACC).pack(fill="x", ipady=4, pady=(0, 4))

        cf = tk.Frame(inner, bg=CARD)
        cf.pack(fill="x", pady=(0, 6))
        self.color_cv = tk.Canvas(cf, width=24, height=24, bg=self.color, bd=0, highlightthickness=1, highlightbackground=BORDER)
        self.color_cv.pack(side="left", padx=(0, 6))
        tk.Label(cf, text="\u041a\u043e\u043b\u0456\u0440", font=("Segoe UI", 9), fg=DIM, bg=CARD).pack(side="left")
        RBtn(cf, "\u041e\u0431\u0440\u0430\u0442\u0438", INP, FG, command=self._pick_color,
             width=70, height=26, radius=8, font=("Segoe UI", 8)).pack(side="right")

        bf = tk.Frame(inner, bg=CARD)
        bf.pack(fill="x", pady=(4, 4))
        bf.columnconfigure(0, weight=1)
        bf.columnconfigure(1, weight=1)
        bf.columnconfigure(2, weight=1)

        self.btn_go = RBtn(bf, "\u0421\u0442\u0430\u0440\u0442", ACC, "#fff",
                           command=self._start, height=36, radius=10,
                           font=("Segoe UI", 11, "bold"))
        self.btn_go.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        self.btn_pas = RBtn(bf, "\u041f\u0430\u0443\u0437\u0430", "#b45309", "#fff",
                            command=self._toggle_pause, height=36, radius=10,
                            font=("Segoe UI", 11, "bold"))
        self.btn_pas.grid(row=0, column=1, sticky="ew", padx=2)
        self.btn_rst = RBtn(bf, "\u0421\u0442\u043e\u043f", RED, "#fff",
                            command=self._stop, height=36, radius=10,
                            font=("Segoe UI", 11, "bold"))
        self.btn_rst.grid(row=0, column=2, sticky="ew", padx=(2, 0))

        RBtn(inner, "\u041f\u0440\u043e\u0435\u043a\u0442\u043e\u0440", GRN, "#fff",
             command=self._open_projector, height=34, radius=10,
             font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(4, 6))

        RBtn(inner, "\u0420\u0435\u0434\u0430\u043a\u0442\u043e\u0440 \u0441\u043b\u0430\u0439\u0434\u0443", "#7c3aed", "#fff",
             command=self._open_editor, height=40, radius=12,
             font=("Segoe UI", 12, "bold")).pack(fill="x", pady=(0, 6))

        self._lbl(inner, "\u041f\u0440\u0435\u0441\u0435\u0442\u0438")
        pf = tk.Frame(inner, bg=CARD)
        pf.pack(fill="x", pady=(0, 4))
        self.preset_var = tk.StringVar()
        self.preset_menu = tk.OptionMenu(pf, self.preset_var, "")
        self.preset_menu["menu"].delete(0, "end")
        self.preset_menu.configure(bg=INP, fg=FG, font=("Segoe UI", 9), activebackground=BORDER,
                                   activeforeground=FG, highlightthickness=0, relief="flat")
        self.preset_menu["menu"].configure(bg=INP, fg=FG)
        self.preset_menu.pack(side="left", fill="x", expand=True)
        for t, c in [("\u0417\u0431\u0435\u0440.", self._save_preset_dlg),
                     ("\u0417\u0430\u0432.", self._load_preset),
                     ("\u0412\u0438\u0434.", self._delete_preset)]:
            RBtn(pf, t, INP, FG, command=c, width=42, height=24, radius=7,
                 font=("Segoe UI", 7, "bold")).pack(side="left", padx=1)

        sb = tk.Frame(root, bg="#0f1525", height=24)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self.proj_dot = tk.Canvas(sb, width=6, height=6, bg=RED, highlightthickness=0, bd=0)
        self.proj_dot.place(x=8, rely=0.5, anchor="w")
        self.proj_lbl = tk.Label(sb, text="\u041f\u0440\u043e\u0435\u043a\u0442\u043e\u0440: \u0437\u0430\u043a\u0440\u0438\u0442\u043e",
                                 font=("Segoe UI", 8), fg=DIM, bg="#0f1525")
        self.proj_lbl.place(x=20, rely=0.5, anchor="w")
        tk.Label(sb, text="DAps | Diachyk Andrii Private Solutions",
                 font=("Segoe UI", 7), fg="#444", bg="#0f1525").pack(side="right", padx=8)

        self.root.bind("<Double-Button-1>", lambda _: self._toggle_pause())
        self.root.bind("<Escape>", lambda _: self._toggle_pause())

    def _lbl(self, parent, text):
        tk.Label(parent, text=text, font=("Segoe UI", 9, "bold"), fg=DIM, bg=CARD,
                 anchor="w").pack(fill="x", pady=(0, 1))

    def _on_mode(self, *_):
        if self.mode_var.get() == "\u0414\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0433\u043e \u0447\u0430\u0441\u0443":
            self.dur_frame.pack_forget()
            self.time_frame.pack(fill="x")
        else:
            self.time_frame.pack_forget()
            self.dur_frame.pack(fill="x", pady=(0, 4))

    # ── Projector Editor ──

    def _open_editor(self):
        d = tk.Toplevel(self.root)
        d.title("\u0420\u0435\u0434\u0430\u043a\u0442\u043e\u0440 \u0441\u043b\u0430\u0439\u0434\u0443")
        d.configure(bg="#1e1e2e")
        d.attributes("-topmost", True)
        d.geometry("900x560")
        d.minsize(800, 500)
        d.transient(self.root)
        d.grab_set()
        icon_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "timer_icon.ico")
        if os.path.exists(icon_path):
            try:
                d.iconbitmap(icon_path)
            except Exception:
                pass

        SW, SH = 480, 270
        ed = {"sel": None, "drag": None, "offset": (0, 0)}
        el_pos = {
            "label": [self.pcfg.get("pos_label_x", SW // 2), self.pcfg.get("pos_label_y", 50)],
            "timer": [self.pcfg.get("pos_timer_x", SW // 2), self.pcfg.get("pos_timer_y", SH // 2)],
            "status": [self.pcfg.get("pos_status_x", SW // 2), self.pcfg.get("pos_status_y", SH - 60)],
            "bar":   [self.pcfg.get("pos_bar_x", SW // 2), self.pcfg.get("pos_bar_y", SH - 20)],
        }
        el_size = {
            "label": self.pcfg.get("label_size", 28),
            "timer": self.pcfg.get("timer_size", 72),
            "status": self.pcfg.get("status_size", 18),
        }

        left = tk.Frame(d, bg="#1e1e2e")
        left.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)

        tk.Label(left, text="\u041f\u0440\u0435\u0432\u044e \u0441\u043b\u0430\u0439\u0434\u0443",
                 font=("Segoe UI", 11, "bold"), fg="#ccc", bg="#1e1e2e").pack(anchor="w", pady=(0, 6))

        pv = tk.Canvas(left, width=SW, height=SH, bg=self.prj_bg,
                       highlightthickness=2, highlightbackground="#555", bd=0, cursor="fleur")
        pv.pack(anchor="center")

        hint = tk.Label(left, text="\u041f\u0435\u0440\u0435\u0442\u044f\u0433\u043d\u0456\u0442\u044c \u0435\u043b\u0435\u043c\u0435\u043d\u0442\u0438 \u043c\u0438\u0448\u043a\u043e\u044e \u043d\u0430 \u0441\u043b\u0430\u0439\u0434\u0456",
                       font=("Segoe UI", 9), fg="#666", bg="#1e1e2e")
        hint.pack(anchor="center", pady=(6, 0))

        right = tk.Frame(d, bg="#2a2a3c", width=320, bd=0, highlightthickness=1, highlightbackground="#444")
        right.pack(side="right", fill="y", padx=(6, 12), pady=12)
        right.pack_propagate(False)

        def _update_preview():
            pv.delete("all")
            pv.configure(bg=self.prj_bg)
            isz = el_size

            def _grad_colors(base, steps=6):
                try:
                    r, g, b = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
                except (ValueError, IndexError):
                    return [base] * steps
                return [f"#{max(0, r - i * 8):02x}{max(0, g - i * 8):02x}{max(0, b - i * 8):02x}"
                        for i in range(steps)]

            def _timer_text():
                if self.timer_running and not self.paused:
                    return self._fmt(self.remaining)
                if self.time_mode and self.target_time:
                    try:
                        h, m, s = map(int, self.target_time.split(":"))
                        diff = datetime.combine(date.today(), time(h, m, s)) - datetime.now()
                        return self._fmt(max(0, int(diff.total_seconds())))
                    except Exception:
                        return "--:--:--"
                try:
                    m = int(self.min_var.get())
                except ValueError:
                    m = 0
                try:
                    s = int(self.sec_var.get())
                except ValueError:
                    s = 0
                return self._fmt(m * 60 + s) if (m or s) else "--:--:--"

            try:
                fsz = int(isz["timer"])
            except (ValueError, TypeError):
                fsz = 72

            ttxt = _timer_text()
            chars = list(ttxt)
            colors = _grad_colors(self.prj_timer_color, len(chars))
            cw = fsz * 0.65
            tw = cw * len(chars)
            sx = el_pos["timer"][0] - tw / 2
            for i, ch in enumerate(chars):
                self._draw_char(pv, ch, sx + cw * i + cw / 2, el_pos["timer"][1], fsz, colors[i])

            try:
                lfsz = int(isz["label"])
            except (ValueError, TypeError):
                lfsz = 28
            lv = self.label_var.get() or "Seminar Timer"
            pv.create_text(el_pos["label"][0], el_pos["label"][1], text=lv,
                           fill=self.prj_label_color, font=("Segoe UI", lfsz, "bold"))

            try:
                sfsz = int(isz["status"])
            except (ValueError, TypeError):
                sfsz = 18
            stxt = "\u23f8 \u041f\u0430\u0443\u0437\u0430" if self.paused else "\u25b6 \u0422\u0440\u0438\u0432\u0430\u0454\u0442\u044c\u0441\u044f" if self.timer_running else "\u23f6 \u0413\u043e\u0442\u043e\u0432\u0438\u0439"
            pv.create_text(el_pos["status"][0], el_pos["status"][1], text=stxt,
                           fill=self.prj_status_color, font=("Segoe UI", sfsz))

            if self.prj_show_bar:
                bsz = self.prj_bar_height
                bw = SW * 0.7
                bx = (SW - bw) / 2
                by = el_pos["bar"][1] - bsz / 2
                pv.create_rectangle(bx, by, bx + bw, by + bsz,
                                    fill="#333", outline="", width=0)
                pct = max(0, min(1, self.remaining / self.total)) if self.total else 0
                pv.create_rectangle(bx, by, bx + bw * pct, by + bsz,
                                    fill=self.prj_bar_color, outline="", width=0)

            sel_id = ed["sel"]
            for eid, (ex, ey) in el_pos.items():
                if eid == sel_id:
                    bw_ = max(60, cw if eid == "timer" else 80)
                    bh_ = (fsz if eid == "timer" else lfsz if eid == "label" else sfsz if eid == "status" else bsz) + 10
                    pv.create_rectangle(ex - bw_ / 2 - 3, ey - bh_ / 2 - 3,
                                        ex + bw_ / 2 + 3, ey + bh_ / 2 + 3,
                                        outline="#3b82f6", width=2, dash=(5, 3))
                    for dx, dy, c in [(-1, -1, "#3b82f6"), (1, -1, "#3b82f6"),
                                      (-1, 1, "#3b82f6"), (1, 1, "#3b82f6")]:
                        vx = ex + dx * (bw_ / 2 + 3)
                        vy = ey + dy * (bh_ / 2 + 3)
                        pv.create_rectangle(vx - 4, vy - 4, vx + 4, vy + 4,
                                            fill=c, outline="#1e1e2e", width=1)

        def _on_press(ev):
            mx, my = ev.x, ev.y
            hit = None
            best = 30
            for eid, (ex, ey) in el_pos.items():
                d2 = ((mx - ex) ** 2 + (my - ey) ** 2) ** 0.5
                if d2 < best:
                    best = d2
                    hit = eid
            ed["sel"] = hit
            if hit:
                ed["drag"] = hit
                ed["offset"] = (mx - el_pos[hit][0], my - el_pos[hit][1])
            _update_preview()
            _show_props()

        def _on_drag(ev):
            if ed["drag"]:
                ex = ev.x - ed["offset"][0]
                ey = ev.y - ed["offset"][1]
                ex = max(20, min(SW - 20, ex))
                ey = max(20, min(SH - 20, ey))
                el_pos[ed["drag"]] = [ex, ey]
                _update_preview()

        def _on_release(ev):
            ed["drag"] = None

        pv.bind("<Button-1>", _on_press)
        pv.bind("<B1-Motion>", _on_drag)
        pv.bind("<ButtonRelease-1>", _on_release)

        props_frame = tk.Frame(right, bg="#2a2a3c")
        props_frame.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(props_frame, text="\u0412\u043b\u0430\u0441\u0442\u0438\u0432\u0456\u0441\u0442\u0456",
                 font=("Segoe UI", 12, "bold"), fg="#fff", bg="#2a2a3c").pack(anchor="w", pady=(0, 8))

        el_list = tk.Frame(props_frame, bg="#2a2a3c")
        el_list.pack(fill="x", pady=(0, 10))
        elements_info = {
            "label": ("\u041f\u0456\u0434\u043f\u0438\u0441", "#f59e0b"),
            "timer": ("\u0422\u0430\u0439\u043c\u0435\u0440", "#3b82f6"),
            "status": ("\u0421\u0442\u0430\u0442\u0443\u0441", "#10b981"),
            "bar": ("\u041f\u0440\u043e\u0433\u0440\u0435\u0441", "#8b5cf6"),
        }
        el_btns = {}
        for eid, (etxt, ecol) in elements_info.items():
            btn = tk.Label(el_list, text=f"  {etxt}  ", font=("Segoe UI", 10),
                           fg="#aaa", bg="#1e1e2e", cursor="hand2", padx=8, pady=4)
            btn.pack(fill="x", pady=1)
            btn.bind("<Button-1>", lambda e, i=eid: _select_el(i))
            el_btns[eid] = btn

        sep = tk.Frame(props_frame, bg="#444", height=1)
        sep.pack(fill="x", pady=(6, 10))

        detail_frame = tk.Frame(props_frame, bg="#2a2a3c")
        detail_frame.pack(fill="both", expand=True)

        def _select_el(eid):
            ed["sel"] = eid
            _update_preview()
            _show_props()
            for k, b in el_btns.items():
                b.configure(bg="#3b82f6" if k == eid else "#1e1e2e",
                            fg="#fff" if k == eid else "#aaa")

        def _show_props():
            for w in detail_frame.winfo_children():
                w.destroy()
            sel = ed["sel"]
            if not sel:
                tk.Label(detail_frame, text="\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0435\u043b\u0435\u043c\u0435\u043d\u0442",
                         font=("Segoe UI", 10), fg="#666", bg="#2a2a3c").pack(anchor="w")
                return

            elabel, ecol = elements_info[sel]
            tk.Label(detail_frame, text=f"\u2022 {elabel}",
                     font=("Segoe UI", 11, "bold"), fg=ecol, bg="#2a2a3c").pack(anchor="w", pady=(0, 8))

            if sel in ("label", "timer", "status"):
                tk.Label(detail_frame, text="\u0420\u043e\u0437\u043c\u0456\u0440 \u0448\u0440\u0438\u0444\u0442\u0443",
                         font=("Segoe UI", 9, "bold"), fg="#aaa", bg="#2a2a3c").pack(anchor="w")
                fs_var = tk.StringVar(value=str(el_size[sel]))
                fs_e = tk.Entry(detail_frame, textvariable=fs_var, font=("Segoe UI", 11),
                                bg="#1e1e2e", fg="#fff", insertbackground="#fff",
                                relief="flat", highlightthickness=1,
                                highlightbackground="#555", highlightcolor="#3b82f6")
                fs_e.pack(fill="x", ipady=3, pady=(2, 8))

                def _apply_fs(v=fs_var, s=sel):
                    try:
                        el_size[s] = int(v.get())
                    except ValueError:
                        pass
                    _update_preview()

                fs_e.bind("<Return>", lambda e: _apply_fs())
                fs_e.bind("<FocusOut>", lambda e: _apply_fs())

            if sel == "timer":
                tk.Label(detail_frame, text="\u041a\u043e\u043b\u0456\u0440 \u0442\u0430\u0439\u043c\u0435\u0440\u0430",
                         font=("Segoe UI", 9, "bold"), fg="#aaa", bg="#2a2a3c").pack(anchor="w")
                tc_frame = tk.Frame(detail_frame, bg="#2a2a3c")
                tc_frame.pack(fill="x", pady=(2, 8))
                tc_cv = tk.Canvas(tc_frame, width=28, height=28, bg=self.prj_timer_color,
                                  highlightthickness=1, highlightbackground="#555", bd=0)
                tc_cv.pack(side="left", padx=(0, 6))
                tk.Label(tc_frame, text=self.prj_timer_color, font=("Segoe UI", 9), fg="#888", bg="#2a2a3c").pack(side="left")

                def pick_tc(ev=None, cv=tc_cv, lb=tc_frame.winfo_children()[-1]):
                    c = colorchooser.askcolor(initialcolor=self.prj_timer_color, parent=d)
                    if c and c[1]:
                        self.prj_timer_color = c[1]
                        cv.configure(bg=c[1])
                        lb.configure(text=c[1])
                        _update_preview()

                RBtn(tc_frame, "\u041e\u0431\u0440\u0430\u0442\u0438", "#555", "#fff", pick_tc, 70, 24, 8, ("Segoe UI", 8)).pack(side="right")

            if sel == "label":
                tk.Label(detail_frame, text="\u041a\u043e\u043b\u0456\u0440 \u043f\u0456\u0434\u043f\u0438\u0441\u0443",
                         font=("Segoe UI", 9, "bold"), fg="#aaa", bg="#2a2a3c").pack(anchor="w")
                lc_frame = tk.Frame(detail_frame, bg="#2a2a3c")
                lc_frame.pack(fill="x", pady=(2, 8))
                lc_cv = tk.Canvas(lc_frame, width=28, height=28, bg=self.prj_label_color,
                                  highlightthickness=1, highlightbackground="#555", bd=0)
                lc_cv.pack(side="left", padx=(0, 6))
                tk.Label(lc_frame, text=self.prj_label_color, font=("Segoe UI", 9), fg="#888", bg="#2a2a3c").pack(side="left")

                def pick_lc(ev=None, cv=lc_cv, lb=lc_frame.winfo_children()[-1]):
                    c = colorchooser.askcolor(initialcolor=self.prj_label_color, parent=d)
                    if c and c[1]:
                        self.prj_label_color = c[1]
                        cv.configure(bg=c[1])
                        lb.configure(text=c[1])
                        _update_preview()

                RBtn(lc_frame, "\u041e\u0431\u0440\u0430\u0442\u0438", "#555", "#fff", pick_lc, 70, 24, 8, ("Segoe UI", 8)).pack(side="right")

            if sel == "status":
                tk.Label(detail_frame, text="\u041a\u043e\u043b\u0456\u0440 \u0441\u0442\u0430\u0442\u0443\u0441\u0443",
                         font=("Segoe UI", 9, "bold"), fg="#aaa", bg="#2a2a3c").pack(anchor="w")
                sc_frame = tk.Frame(detail_frame, bg="#2a2a3c")
                sc_frame.pack(fill="x", pady=(2, 8))
                sc_cv = tk.Canvas(sc_frame, width=28, height=28, bg=self.prj_status_color,
                                  highlightthickness=1, highlightbackground="#555", bd=0)
                sc_cv.pack(side="left", padx=(0, 6))
                tk.Label(sc_frame, text=self.prj_status_color, font=("Segoe UI", 9), fg="#888", bg="#2a2a3c").pack(side="left")

                def pick_sc(ev=None, cv=sc_cv, lb=sc_frame.winfo_children()[-1]):
                    c = colorchooser.askcolor(initialcolor=self.prj_status_color, parent=d)
                    if c and c[1]:
                        self.prj_status_color = c[1]
                        cv.configure(bg=c[1])
                        lb.configure(text=c[1])
                        _update_preview()

                RBtn(sc_frame, "\u041e\u0431\u0440\u0430\u0442\u0438", "#555", "#fff", pick_sc, 70, 24, 8, ("Segoe UI", 8)).pack(side="right")

            if sel == "bar":
                tk.Label(detail_frame, text="\u041a\u043e\u043b\u0456\u0440 \u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0443",
                         font=("Segoe UI", 9, "bold"), fg="#aaa", bg="#2a2a3c").pack(anchor="w")
                bc_frame = tk.Frame(detail_frame, bg="#2a2a3c")
                bc_frame.pack(fill="x", pady=(2, 8))
                bc_cv = tk.Canvas(bc_frame, width=28, height=28, bg=self.prj_bar_color,
                                  highlightthickness=1, highlightbackground="#555", bd=0)
                bc_cv.pack(side="left", padx=(0, 6))
                tk.Label(bc_frame, text=self.prj_bar_color, font=("Segoe UI", 9), fg="#888", bg="#2a2a3c").pack(side="left")

                def pick_bc(ev=None, cv=bc_cv, lb=bc_frame.winfo_children()[-1]):
                    c = colorchooser.askcolor(initialcolor=self.prj_bar_color, parent=d)
                    if c and c[1]:
                        self.prj_bar_color = c[1]
                        cv.configure(bg=c[1])
                        lb.configure(text=c[1])
                        _update_preview()

                RBtn(bc_frame, "\u041e\u0431\u0440\u0430\u0442\u0438", "#555", "#fff", pick_bc, 70, 24, 8, ("Segoe UI", 8)).pack(side="right")

                tk.Label(detail_frame, text="\u0412\u0438\u0441\u043e\u0442\u0430 \u043f\u043e\u043b\u043e\u0441\u0438 (\u043f\u043a\u0441)",
                         font=("Segoe UI", 9, "bold"), fg="#aaa", bg="#2a2a3c").pack(anchor="w", pady=(4, 0))
                bh_var = tk.StringVar(value=str(self.prj_bar_height))
                bh_e = tk.Entry(detail_frame, textvariable=bh_var, font=("Segoe UI", 11),
                                bg="#1e1e2e", fg="#fff", insertbackground="#fff",
                                relief="flat", highlightthickness=1,
                                highlightbackground="#555", highlightcolor="#3b82f6")
                bh_e.pack(fill="x", ipady=3, pady=(2, 8))

                def _apply_bh(v=bh_var):
                    try:
                        self.prj_bar_height = int(v.get())
                    except ValueError:
                        pass
                    _update_preview()

                bh_e.bind("<Return>", lambda e: _apply_bh())
                bh_e.bind("<FocusOut>", lambda e: _apply_bh())

                self.ed_bar_var2 = tk.BooleanVar(value=self.prj_show_bar)
                tk.Checkbutton(detail_frame, text="\u041f\u043e\u043a\u0430\u0437\u0443\u0432\u0430\u0442\u0438 \u043f\u043e\u043b\u043e\u0441\u0443",
                               variable=self.ed_bar_var2, font=("Segoe UI", 10), fg="#ccc", bg="#2a2a3c",
                               activebackground="#2a2a3c", activeforeground="#fff", selectcolor="#1e1e2e",
                               command=_update_preview).pack(fill="x", pady=(4, 0))

            tk.Label(detail_frame, text="\u0426\u0435\u0432\u043e \u043f\u043e\u0437\u0438\u0446\u0456\u044f:",
                     font=("Segoe UI", 9), fg="#666", bg="#2a2a3c").pack(anchor="w", pady=(8, 0))
            tk.Label(detail_frame, text=f"  x={int(el_pos[sel][0])}  y={int(el_pos[sel][1])}",
                     font=("Consolas", 9), fg="#888", bg="#2a2a3c").pack(anchor="w")

        _update_preview()
        _show_props()

        bot = tk.Frame(d, bg="#1e1e2e")
        bot.pack(side="bottom", fill="x", padx=12, pady=(0, 12))

        def _reset():
            el_pos["label"] = [SW // 2, 50]
            el_pos["timer"] = [SW // 2, SH // 2]
            el_pos["status"] = [SW // 2, SH - 60]
            el_pos["bar"] = [SW // 2, SH - 20]
            el_size["label"] = 28
            el_size["timer"] = 72
            el_size["status"] = 18
            ed["sel"] = None
            _update_preview()
            _show_props()

        def _save():
            self.prj_font_size = el_size["timer"]
            self.prj_show_bar = self.ed_bar_var2.get() if hasattr(self, "ed_bar_var2") else self.prj_show_bar
            self.pcfg = {
                "bg": self.prj_bg, "timer_color": self.prj_timer_color,
                "label_color": self.prj_label_color, "status_color": self.prj_status_color,
                "font_size": self.prj_font_size, "show_bar": self.prj_show_bar,
                "bar_color": self.prj_bar_color, "bar_height": self.prj_bar_height,
                "label_size": el_size["label"], "timer_size": el_size["timer"],
                "status_size": el_size["status"],
                "pos_label_x": el_pos["label"][0], "pos_label_y": el_pos["label"][1],
                "pos_timer_x": el_pos["timer"][0], "pos_timer_y": el_pos["timer"][1],
                "pos_status_x": el_pos["status"][0], "pos_status_y": el_pos["status"][1],
                "pos_bar_x": el_pos["bar"][0], "pos_bar_y": el_pos["bar"][1],
            }
            save_json(PROJECTOR_CFG, self.pcfg)
            self._sync()
            d.destroy()
            self._toast("\u041d\u0430\u043b\u0430\u0448\u0442\u0443\u0432\u0430\u043d\u043d\u044f \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043e")

        RBtn(bot, "\u0421\u043a\u0443\u0441\u0442\u0438\u0442\u0438", "#555", "#fff", _reset,
             100, 32, 8, ("Segoe UI", 9, "bold")).pack(side="left")
        RBtn(bot, "\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438", GRN, "#fff", _save,
             120, 36, 10, ("Segoe UI", 11, "bold")).pack(side="right")

        d.bind("<Escape>", lambda _: d.destroy())

    # ── Timer ──

    def _get_total(self):
        if self.mode_var.get() == "\u0417\u043e\u0440\u043e\u0442\u043d\u0456\u0439 \u0432\u0456\u0434\u043b\u0456\u043a":
            try:
                m = int(self.min_var.get())
            except ValueError:
                m = 0
            try:
                s = int(self.sec_var.get())
            except ValueError:
                s = 0
            return max(0, m * 60 + s)
        return self._calc_to()

    def _calc_to(self):
        v = self.time_var.get()
        if not v:
            return 0
        try:
            p = v.split(":")
            h, m = int(p[0]), int(p[1])
        except (ValueError, IndexError):
            return 0
        now = time.time()
        t = time.localtime(now)
        tgt = datetime.datetime(t.tm_year, t.tm_mon, t.tm_mday, h, m, 0).timestamp()
        if tgt <= now:
            tgt += 86400
        return int(tgt - now)

    def _fmt(self, sec):
        sec = max(0, sec)
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _update_display(self):
        if self.mode_var.get() == "\u0414\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0433\u043e \u0447\u0430\u0441\u0443":
            sec = self._calc_to()
        else:
            sec = self.remaining
        self.time_lbl.configure(text=self._fmt(sec))

    def _start(self):
        self._cancel()
        self.mode = self.mode_var.get()
        self.total = self._get_total()
        if self.total <= 0:
            self._toast("\u0412\u0432\u0435\u0434\u0456\u0442\u044c \u0447\u0430\u0441!", "err")
            return
        self.remaining = self.total
        self.running = True
        self.paused = False
        self._set_st("\u0412\u0456\u0434\u043b\u0456\u043a...", GRN)
        self._open_projector()
        self._tick()
        self._update_display()

    def _toggle_pause(self, _=None):
        if not self.running:
            return
        if self.paused:
            self.paused = False
            self._set_st("\u0412\u0456\u0434\u043b\u0456\u043a...", GRN)
            self._tick()
        else:
            self.paused = True
            self._cancel()
            self._set_st("\u041f\u0430\u0443\u0437\u0430", YLW)
        self._sync()

    def _stop(self):
        self._cancel()
        self.running = False
        self.paused = False
        self.remaining = self._get_total()
        self.total = self.remaining
        self._set_st("\u0421\u043a\u0438\u043d\u0443\u0442\u043e", DIM)
        self._update_display()
        self._close_proj()
        self._sync()

    def _adjust(self, delta):
        if self.mode_var.get() == "\u0414\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0433\u043e \u0447\u0430\u0441\u0443":
            return
        if self.running:
            self.remaining = max(0, self.remaining + delta)
            self.total = max(self.total, self.remaining)
            if self.remaining <= 0:
                self.running = False
                self._set_st("\u0427\u0430\u0441 \u0432\u0439\u0448\u043e\u0432!", RED)
                self._alarm()
        else:
            try:
                m = int(self.min_var.get())
            except ValueError:
                m = 0
            try:
                s = int(self.sec_var.get())
            except ValueError:
                s = 0
            total = max(0, min(180 * 60, m * 60 + s + delta))
            self.min_var.set(str(total // 60))
            self.sec_var.set(str(total % 60))
            self.remaining = total
            self.total = total
        self._update_display()
        self._sync()

    def _tick(self):
        if not self.running or self.paused:
            return
        if self.remaining <= 0:
            self.running = False
            self._set_st("\u0427\u0430\u0441 \u0432\u0439\u0448\u043e\u0432!", RED)
            self._alarm()
            self._sync()
            return
        self.remaining -= 1
        if self.mode == "\u0414\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0433\u043e \u0447\u0430\u0441\u0443":
            c = self._calc_to()
            if c <= 0:
                self.running = False
                self.remaining = 0
                self._set_st("\u0427\u0430\u0441 \u0432\u0439\u0448\u043e\u0432!", RED)
                self._alarm()
                self._sync()
                return
            self.remaining = c
        self._update_display()
        self._sync()
        self.tid = self.root.after(1000, self._tick)

    def _cancel(self):
        if self.tid:
            self.root.after_cancel(self.tid)
            self.tid = None

    def _alarm(self):
        def beep():
            try:
                for _ in range(3):
                    winsound.Beep(880, 200)
                    time.sleep(0.1)
            except Exception:
                pass
        threading.Thread(target=beep, daemon=True).start()

    def _set_st(self, txt, clr):
        self.status_lbl.configure(text=txt, fg=clr)

    # ── Projector ──

    def _open_projector(self):
        if self.proj and self.proj.winfo_exists():
            self.proj.lift()
            self.proj.focus_force()
            self._sync()
            return
        mon = get_second_monitor()
        self.proj = tk.Toplevel(self.root)
        self.proj.configure(bg=self.prj_bg)
        self.proj.overrideredirect(True)
        self.proj.geometry(f"{mon['w']}x{mon['h']}+{mon['x']}+{mon['y']}")
        self.proj.configure(cursor="none")
        self.proj.protocol("WM_DELETE_WINDOW", self._close_proj)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "timer_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.proj.iconbitmap(icon_path)
            except Exception:
                pass
        self.proj.update_idletasks()
        self.proj.lift()
        self.proj.focus_force()
        self.proj.bind("<Double-Button-1>", lambda _: self._toggle_pause())
        self.proj.bind("<Escape>", lambda _: self._stop())

        self.pf = tk.Frame(self.proj, bg=self.prj_bg)
        self.pf.place(relx=0.5, rely=0.5, anchor="center")

        pLX = self.pcfg.get("pos_label_x", 0.5)
        pLY = self.pcfg.get("pos_label_y", 0.19)
        pTX = self.pcfg.get("pos_timer_x", 0.5)
        pTY = self.pcfg.get("pos_timer_y", 0.5)
        pSX = self.pcfg.get("pos_status_x", 0.5)
        pSY = self.pcfg.get("pos_status_y", 0.78)
        pBX = self.pcfg.get("pos_bar_x", 0.5)
        pBY = self.pcfg.get("pos_bar_y", 0.92)

        lbl_sz = self.pcfg.get("label_size", 28)
        st_sz = self.pcfg.get("status_size", 20)

        self.p_label = tk.Label(self.proj, text="", font=("Segoe UI", lbl_sz),
                                fg=self.prj_label_color, bg=self.prj_bg)
        self.p_label.place(relx=pLX / 480, rely=pLY / 270, anchor="center")

        self.p_chars = []
        self.p_single = tk.Label(self.proj, text="", font=("Consolas", self.prj_font_size, "bold"),
                                 fg=self.prj_timer_color, bg=self.prj_bg)
        self.p_single.place_forget()

        self.bar_frame = tk.Frame(self.proj, bg="#151c30", height=self.prj_bar_height, width=600)
        self.bar_frame.place(relx=pBX / 480, rely=pBY / 270, anchor="center")
        self.p_bar = tk.Canvas(self.bar_frame, bg=self.prj_bar_color, highlightthickness=0, bd=0,
                               height=self.prj_bar_height)
        self.p_bar.place(relx=0, rely=0, relwidth=1.0, relheight=1.0, anchor="nw")

        self.p_status = tk.Label(self.proj, text="\u041e\u0447\u0456\u043a\u0443\u0432\u0430\u043d\u043d\u044f",
                                 font=("Segoe UI", st_sz), fg=self.prj_status_color, bg=self.prj_bg)
        self.p_status.place(relx=pSX / 480, rely=pSY / 270, anchor="center")

        tk.Label(self.proj, text="DAps | Diachyk Andrii Private Solutions",
                 font=("Segoe UI", 10), fg="#333", bg=self.prj_bg).pack(side="bottom", pady=8)

        self._sync()
        self.proj_dot.configure(bg=GRN)
        self.proj_lbl.configure(text="\u041f\u0440\u043e\u0435\u043a\u0442\u043e\u0440: \u0430\u043a\u0442\u0438\u0432\u043d\u0439")

    def _update_proj(self):
        if not self.proj or not self.proj.winfo_exists():
            return
        if self.mode == "\u0414\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0433\u043e \u0447\u0430\u0441\u0443":
            sec = max(0, self._calc_to())
        else:
            sec = max(0, self.remaining)
        txt = self._fmt(sec)

        if sec <= 0 and not self.running:
            st = "\u0427\u0430\u0441 \u0432\u0439\u0448\u043e\u0432!"
            self._flash()
        elif self.paused:
            st = "\u041f\u0430\u0443\u0437\u0430"
        elif self.running:
            st = "\u0412\u0456\u0434\u043b\u0456\u043a"
        else:
            st = "\u041e\u0447\u0456\u043a\u0443\u0432\u0430\u043d\u043d\u044f"

        mon = get_second_monitor()
        mw, mh = mon["w"], mon["h"]

        pTX = self.pcfg.get("pos_timer_x", 480 / 2)
        pTY = self.pcfg.get("pos_timer_y", 270 / 2)
        pLX = self.pcfg.get("pos_label_x", 480 / 2)
        pLY = self.pcfg.get("pos_label_y", 270 * 0.19)
        pSX = self.pcfg.get("pos_status_x", 480 / 2)
        pSY = self.pcfg.get("pos_status_y", 270 * 0.78)
        pBX = self.pcfg.get("pos_bar_x", 480 / 2)
        pBY = self.pcfg.get("pos_bar_y", 270 * 0.92)

        def sx(v): return v / 480 * mw
        def sy(v): return v / 270 * mh

        self.proj.configure(bg=self.prj_bg)
        self.p_label.configure(text=self.lbl_var.get(), fg=self.prj_label_color, bg=self.prj_bg)
        self.p_label.place(relx=sx(pLX) / mw, rely=sy(pLY) / mh, anchor="center")
        self.p_status.configure(text=st, fg=self.prj_status_color, bg=self.prj_bg)
        st_sz = self.pcfg.get("status_size", 20)
        self.p_status.configure(font=("Segoe UI", st_sz))
        self.p_status.place(relx=sx(pSX) / mw, rely=sy(pSY) / mh, anchor="center")

        if self.prj_show_bar:
            self.bar_frame.place(relx=sx(pBX) / mw, rely=sy(pBY) / mh, anchor="center")
            self.bar_frame.configure(bg="#151c30", height=self.prj_bar_height)
            self.p_bar.configure(bg=self.prj_bar_color, height=self.prj_bar_height)
            pct = max(0, min(1, sec / self.total)) if self.total > 0 else (1.0 if sec > 0 else 0)
            self.p_bar.place(relx=0, rely=0, relwidth=pct, relheight=1.0, anchor="nw")
        else:
            self.bar_frame.place_forget()

        self._render(txt, sx(pTX), sy(pTY))

    def _render(self, txt, tx, ty):
        if len(txt) <= 1:
            self.p_single.configure(text=txt, fg=self.prj_timer_color, bg=self.prj_bg,
                                    font=("Consolas", self.prj_font_size, "bold"))
            self.p_single.place(relx=tx / self.proj.winfo_width(), rely=ty / self.proj.winfo_height(), anchor="center")
            for c in self.p_chars:
                c.place_forget()
            return
        self.p_single.place_forget()
        while len(self.p_chars) < len(txt):
            l = tk.Label(self.proj, text="", font=("Consolas", self.prj_font_size, "bold"), bg=self.prj_bg)
            self.p_chars.append(l)
        for c in self.p_chars:
            c.place_forget()
        rgb = self._hex2rgb(self.prj_timer_color)
        cw = self.prj_font_size * 0.65
        tw = cw * len(txt)
        sx = tx - tw / 2
        mw = self.proj.winfo_width()
        mh = self.proj.winfo_height()
        for i, ch in enumerate(txt):
            lbl = self.p_chars[i]
            t = i / max(1, len(txt) - 1)
            r = int(rgb[0] * (1 - t * 0.4))
            g = int(rgb[1] * (1 - t * 0.4))
            b = int(rgb[2] * (1 - t * 0.4))
            lbl.configure(text=ch, fg=f"#{r:02x}{g:02x}{b:02x}", bg=self.prj_bg,
                          font=("Consolas", self.prj_font_size, "bold"))
            cx = sx + cw * i + cw / 2
            lbl.place(relx=cx / mw, rely=ty / mh, anchor="center")

    def _flash(self):
        if not self.proj or not self.proj.winfo_exists():
            return
        try:
            self.proj.configure(bg="#1a0505")
            self.proj.after(300, lambda: self.proj.configure(bg=self.prj_bg) if self.proj.winfo_exists() else None)
        except Exception:
            pass

    def _close_proj(self):
        if self.proj and self.proj.winfo_exists():
            self.proj.destroy()
        self.proj = None
        self.proj_dot.configure(bg=RED)
        self.proj_lbl.configure(text="\u041f\u0440\u043e\u0435\u043a\u0442\u043e\u0440: \u0437\u0430\u043a\u0440\u0438\u0442\u043e")

    def _sync(self):
        self.root.after_idle(self._update_proj)

    # ── Color ──

    def _pick_color(self):
        c = colorchooser.askcolor(initialcolor=self.color, title="Color")
        if c and c[1]:
            self.color = c[1]
            self.color_cv.configure(bg=self.color)
            self._sync()

    @staticmethod
    def _hex2rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    # ── Toast ──

    def _toast(self, msg, kind="ok"):
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        border = RED if kind == "err" else GRN
        f = tk.Frame(t, bg=border, padx=2, pady=2)
        f.pack()
        tk.Label(f, text=msg, font=("Segoe UI", 10), fg="#fff", bg=INP, padx=12, pady=8, wraplength=280).pack()
        t.update_idletasks()
        w = t.winfo_width()
        x = self.root.winfo_x() + self.root.winfo_width() - w - 20
        y = self.root.winfo_y() + 40
        t.geometry(f"+{x}+{y}")
        t.after(3000, t.destroy)

    # ── Presets ──

    def _save_preset_dlg(self):
        d = tk.Toplevel(self.root)
        d.title("\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u043f\u0440\u0435\u0441\u0435\u0442")
        d.configure(bg=BG)
        d.attributes("-topmost", True)
        d.geometry("300x110")
        d.transient(self.root)
        d.grab_set()
        tk.Label(d, text="\u041d\u0430\u0437\u0432\u0430:", font=("Segoe UI", 10), fg=FG, bg=BG).pack(pady=(12, 4))
        var = tk.StringVar()
        e = tk.Entry(d, textvariable=var, font=("Segoe UI", 11), bg=INP, fg=FG, insertbackground=FG,
                     relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACC)
        e.pack(fill="x", padx=20, ipady=4)
        e.focus_set()
        result = [None]
        def ok():
            result[0] = var.get().strip()
            d.destroy()
        RBtn(d, "OK", ACC, "#fff", ok, 80, 30, 8, ("Segoe UI", 10, "bold")).pack(pady=8)
        d.bind("<Return>", lambda _: ok())
        self.root.wait_window(d)
        name = result[0]
        if not name:
            return
        preset = {"name": name, "minutes": self.min_var.get(), "seconds": self.sec_var.get(),
                  "mode": self.mode_var.get(), "time": self.time_var.get(),
                  "label": self.lbl_var.get(), "color": self.color}
        self.presets = [p for p in self.presets if p["name"] != name]
        self.presets.append(preset)
        save_json(PRESETS_FILE, self.presets)
        self._refresh_menu()
        self._toast(f"'{name}' \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043e")

    def _load_preset(self):
        name = self.preset_var.get()
        if not name:
            return
        p = next((x for x in self.presets if x["name"] == name), None)
        if not p:
            return
        self.min_var.set(p.get("minutes", "15"))
        self.sec_var.set(p.get("seconds", "0"))
        self.mode_var.set(p.get("mode", "\u0417\u043e\u0440\u043e\u0442\u043d\u0456\u0439 \u0432\u0456\u0434\u043b\u0456\u043a"))
        self.time_var.set(p.get("time", "12:00"))
        self.lbl_var.set(p.get("label", "\u0421\u0435\u043c\u0456\u043d\u0430\u0440 \u043f\u043e\u0447\u043d\u0435\u0442\u044c\u0441\u044f \u0447\u0435\u0440\u0435\u0437:"))
        self.color = p.get("color", ACC)
        self.color_cv.configure(bg=self.color)
        self._on_mode()
        self.remaining = self._get_total()
        self.total = self.remaining
        self._update_display()
        self._sync()
        self._toast(f"'{name}' \u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0435\u043d\u043e")

    def _delete_preset(self):
        name = self.preset_var.get()
        if not name:
            return
        self.presets = [p for p in self.presets if p["name"] != name]
        save_json(PRESETS_FILE, self.presets)
        self._refresh_menu()
        self._toast(f"'{name}' \u0432\u0438\u0434\u0430\u043b\u0435\u043d\u043e")

    def _refresh_menu(self):
        menu = self.preset_menu["menu"]
        menu.delete(0, "end")
        for p in self.presets:
            menu.add_command(label=p["name"], command=lambda n=p["name"]: self.preset_var.set(n))
        if self.presets:
            self.preset_var.set(self.presets[0]["name"])
        else:
            self.preset_var.set("")

    def _on_close(self):
        self._cancel()
        self._close_proj()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    TimerApp().run()
