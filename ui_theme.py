#!/usr/bin/env python3
"""
Look and motion for DR. NILESH SHAH'S MARKET ANALYSIS
=====================================================
The Daylight design (light) and its dark mode, the ttk styling that goes with them, and a
small animation toolkit for Tkinter: tweens, colour fades, 3D-style buttons that press
down, a tab bar with a sliding underline, slide-in messages and the scan summary card.

Every animation goes through tween(), which skips straight to the end when animations
are off (Settings, or Windows' own "Animation effects" setting).
"""

import ctypes
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# ============================================================
# COLOURS
# ============================================================
# The keys before the blank line are the app's original theme keys (so every existing
# widget follows the theme); the rest are tokens added with the Daylight design.

LIGHT = {
    'bg': '#E8ECF2', 'bg2': '#FFFFFF', 'bg3': '#EDF1F6', 'card': '#FFFFFF', 'card2': '#F3F6FA', 'input': '#FFFFFF',
    'fg': '#0A101C', 'fg2': '#343E50', 'fg3': '#4A5568', 'accent': '#1A4FE6', 'accent2': '#1440C0', 'accent3': '#3D6CF5',
    'success': '#00774F', 'success2': '#00663F', 'warning': '#965C00', 'warning2': '#C27C00', 'danger': '#D0301F',
    'danger2': '#A81B0E', 'buy': '#00936A', 'sell': '#E5402E', 'hold': '#737E90', 'border': '#CDD5E0', 'glow': '#1A4FE6',
    'gold': '#0A101C', 'purple': '#6A35D9', 'cyan': '#1A4FE6', 'pink': '#C2266F', 'orange': '#C24A00', 'lime': '#3F7D00',

    'mode': 'light', 'line': '#CDD5E0', 'ink': '#FFFFFF', 'accent_hover': '#1440C0', 'accent_press': '#0F3399',
    'sb': '#00704F', 'ss': '#B8210F', 'tint_b': '#DCF3EA', 'tint_s': '#FDE7E5', 'zebra': '#F6F8FB', 'sel_bg': '#CCDBFF',
    'sel_fg': '#0A101C', 'flash': '#B5CBFF', 'warn_bg': '#FFEDC8', 'warn_fg': '#573600', 'info_bg': '#DAE5FF',
    'info_fg': '#10339E', 'risk_bg': '#FFE2DE', 'risk_fg': '#8A140C', 'reward_bg': '#D7F2E7', 'reward_fg': '#00553A',
    'err_bg': '#E9EDF2', 'err_fg': '#4A5568', 'chart_bg': '#FFFFFF', 'chart_grid': '#DEE4EC', 'chart_fg': '#4A5568',
    'series0': '#1A56E8', 'series1': '#D95200', 'series2': '#9A2EC4', 'shadow': '#B3BECD', 'btn_base': '#BAC4D2',
}

DARK = {
    'bg': '#080B11', 'bg2': '#121923', 'bg3': '#1A2230', 'card': '#121923', 'card2': '#1A2230', 'input': '#080B11',
    'fg': '#F4F7FB', 'fg2': '#BEC7D5', 'fg3': '#9AA4B5', 'accent': '#5E8EFF', 'accent2': '#86AAFF', 'accent3': '#4A7CF0',
    'success': '#22BF85', 'success2': '#45DDA0', 'warning': '#F2B431', 'warning2': '#FFC857', 'danger': '#F5634B',
    'danger2': '#FF8A75', 'buy': '#18AD76', 'sell': '#F5563F', 'hold': '#6C7586', 'border': '#2B3547', 'glow': '#5E8EFF',
    'gold': '#F4F7FB', 'purple': '#A47DFF', 'cyan': '#5E8EFF', 'pink': '#F06AB0', 'orange': '#F58A2E', 'lime': '#94D63C',

    'mode': 'dark', 'line': '#2B3547', 'ink': '#071022', 'accent_hover': '#7BA2FF', 'accent_press': '#4A79E6',
    'sb': '#34D392', 'ss': '#FF7058', 'tint_b': '#0F2A22', 'tint_s': '#311517', 'zebra': '#141B26', 'sel_bg': '#20365F',
    'sel_fg': '#F4F7FB', 'flash': '#2C4C90', 'warn_bg': '#33270C', 'warn_fg': '#FFD27A', 'info_bg': '#13244A',
    'info_fg': '#BBD0FF', 'risk_bg': '#3A1916', 'risk_fg': '#FFB0A8', 'reward_bg': '#0E3328', 'reward_fg': '#8FEBC6',
    'err_bg': '#1A2230', 'err_fg': '#9AA4B5', 'chart_bg': '#121923', 'chart_grid': '#222C3B', 'chart_fg': '#9AA4B5',
    'series0': '#4F8CFF', 'series1': '#F5992E', 'series2': '#B57BF5', 'shadow': '#020407', 'btn_base': '#05080D',
}


def palette(mode: str) -> dict:
    return dict(DARK if mode == 'dark' else LIGHT)


def blend(a: str, b: str, t: float) -> str:
    """Colour between a (t=0) and b (t=1)."""
    t = max(0.0, min(1.0, t))
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def signal_color(T: dict, rec: str) -> str:
    return {'STRONG BUY': T['sb'], 'BUY': T['buy'], 'HOLD': T['hold'], 'SELL': T['sell'], 'STRONG SELL': T['ss']}.get(rec, T['hold'])


# ============================================================
# FONTS - all come with Windows 11 (older Windows: Segoe UI / Consolas)
# ============================================================

FONT = 'Segoe UI'
DISPLAY = 'Segoe UI'
MONO = 'Consolas'


def init_fonts(root):
    global FONT, DISPLAY, MONO
    fams = set(tkfont.families(root))
    FONT = 'Segoe UI Variable Text' if 'Segoe UI Variable Text' in fams else 'Segoe UI'
    DISPLAY = 'Segoe UI Variable Display' if 'Segoe UI Variable Display' in fams else 'Segoe UI'
    MONO = 'Cascadia Mono' if 'Cascadia Mono' in fams else 'Consolas'


# ============================================================
# MOTION
# ============================================================

class Motion:
    enabled = True     # Settings > Appearance > Animations, and Windows' own setting


def windows_allows_animation() -> bool:
    """Windows Settings > Accessibility > Visual effects > Animation effects."""
    if sys.platform != 'win32':
        return True
    try:
        on = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(on), 0)   # SPI_GETCLIENTAREAANIMATION
        return bool(on.value)
    except Exception:
        return True


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


class _Tween:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def tween(widget, ms, step, done=None, ease=ease_out, frame=16):
    """Call step(v) with v going 0 -> 1 (eased) over ms milliseconds, then done().
    Stops quietly if the widget is destroyed; jumps to the end when animations are off."""
    handle = _Tween()
    if not Motion.enabled or ms <= 0:
        try:
            step(1.0)
            if done:
                done()
        except tk.TclError:
            pass
        return handle
    start = [None]

    def tick():
        if handle.cancelled:
            return
        try:
            if not widget.winfo_exists():
                return
            now = time.perf_counter() * 1000
            if start[0] is None:
                start[0] = now
            t = min(1.0, (now - start[0]) / ms)
            step(ease(t))
            if t < 1.0:
                widget.after(frame, tick)
            elif done:
                done()
        except tk.TclError:
            pass   # widget went away mid-animation

    tick()
    return handle


def fade(widget, option, start, end, ms=140, ease=ease_out):
    """Fade a colour option (e.g. 'bg', 'fg') from start to end."""
    return tween(widget, ms, lambda v: widget.configure(**{option: blend(start, end, v)}), ease=ease)


# ============================================================
# CANVAS SHAPES
# ============================================================

def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """A rounded rectangle on a canvas (a smoothed polygon)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    if r == 0:
        return canvas.create_rectangle(x1, y1, x2, y2, **kw)
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def soft_shadow(canvas, x1, y1, x2, y2, r, bg, shadow, depth=6, lift=0):
    """A soft drop shadow under a card: rings that fade from the shadow colour into the
    background. `lift` raises the card (bigger, softer shadow) - used for hover."""
    layers = depth + lift
    for i in range(layers, 0, -1):
        k = (1 - i / (layers + 1)) ** 2 * 0.55
        off = 1 + i * 0.6 + lift * 0.6
        round_rect(canvas, x1 - i * 0.5, y1 + off - i * 0.3, x2 + i * 0.5, y2 + off + i * 0.5, r + i,
                   fill=blend(bg, shadow, k), outline='')


def marker_images(T, size=14):
    """Signal markers for the results table: double triangle up (strong buy), triangle up
    (buy), bar (hold), triangle down (sell), double triangle down (strong sell)."""
    from PIL import Image, ImageDraw, ImageTk
    s = size * 4   # draw big, shrink - smooth edges
    shapes = {
        'STRONG BUY': [[(s / 2, 2), (s - 4, s / 2 - 2), (4, s / 2 - 2)], [(s / 2, s / 2 + 2), (s - 4, s - 2), (4, s - 2)]],
        'BUY': [[(s / 2, 6), (s - 4, s - 8), (4, s - 8)]],
        'HOLD': [[(6, s / 2 - 5), (s - 6, s / 2 - 5), (s - 6, s / 2 + 5), (6, s / 2 + 5)]],
        'SELL': [[(4, 8), (s - 4, 8), (s / 2, s - 6)]],
        'STRONG SELL': [[(4, 2), (s - 4, 2), (s / 2, s / 2 - 2)], [(4, s / 2 + 2), (s - 4, s / 2 + 2), (s / 2, s - 2)]],
    }
    out = {}
    for rec, polys in shapes.items():
        img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for poly in polys:
            d.polygon(poly, fill=signal_color(T, rec))
        out[rec] = ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))
    out['ERROR'] = ImageTk.PhotoImage(Image.new('RGBA', (size, size), (0, 0, 0, 0)))
    return out


# ============================================================
# TTK STYLING
# ============================================================

def style_ttk(root, T):
    s = ttk.Style(root)
    s.theme_use('clam')
    s.configure('.', background=T['bg'], foreground=T['fg'], fieldbackground=T['input'], bordercolor=T['line'],
                lightcolor=T['bg2'], darkcolor=T['line'], troughcolor=T['bg3'], focuscolor=T['accent'],
                selectbackground=T['accent'], selectforeground=T['ink'], insertcolor=T['fg'], font=(FONT, 10))
    s.configure('Treeview', background=T['card'], fieldbackground=T['card'], foreground=T['fg'], rowheight=32,
                borderwidth=0, relief='flat', font=(FONT, 10))
    s.map('Treeview', background=[('selected', T['sel_bg'])], foreground=[('selected', T['sel_fg'])])
    s.configure('Treeview.Heading', background=T['bg3'], foreground=T['fg2'], font=(FONT, 9, 'bold'),
                relief='flat', borderwidth=0, padding=(8, 8))
    s.map('Treeview.Heading', background=[('active', T['line'])], foreground=[('active', T['fg'])])
    s.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
    s.configure('Tabless.TNotebook', background=T['bg'], borderwidth=0, tabmargins=0, padding=0)
    s.layout('Tabless.TNotebook.Tab', [])
    s.configure('TNotebook', background=T['bg'], borderwidth=0)
    s.configure('TNotebook.Tab', background=T['bg3'], foreground=T['fg2'], padding=(12, 6))
    s.map('TNotebook.Tab', background=[('selected', T['bg2'])], foreground=[('selected', T['fg'])])
    s.configure('TCombobox', fieldbackground=T['input'], background=T['bg3'], foreground=T['fg'], arrowcolor=T['fg2'],
                bordercolor=T['line'], lightcolor=T['input'], darkcolor=T['input'], padding=5, arrowsize=14)
    s.map('TCombobox', fieldbackground=[('readonly', T['input'])], foreground=[('readonly', T['fg'])],
          selectbackground=[('readonly', T['input'])], selectforeground=[('readonly', T['fg'])],
          bordercolor=[('focus', T['accent'])], arrowcolor=[('hover', T['accent'])])
    root.option_add('*TCombobox*Listbox.background', T['card'])
    root.option_add('*TCombobox*Listbox.foreground', T['fg'])
    root.option_add('*TCombobox*Listbox.selectBackground', T['accent'])
    root.option_add('*TCombobox*Listbox.selectForeground', T['ink'])
    root.option_add('*TCombobox*Listbox.font', (FONT, 10))
    s.configure('Accent.Horizontal.TProgressbar', troughcolor=T['bg3'], background=T['accent'], bordercolor=T['bg3'],
                lightcolor=T['accent'], darkcolor=T['accent'], thickness=6)
    for orient in ('Vertical', 'Horizontal'):
        s.configure(f'{orient}.TScrollbar', background=T['bg3'], troughcolor=T['bg'], bordercolor=T['bg'],
                    arrowcolor=T['fg3'], lightcolor=T['bg3'], darkcolor=T['bg3'], gripcount=0)
        s.map(f'{orient}.TScrollbar', background=[('active', T['line'])])
    return s


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def skin(widget, T):
    """Give the classic Tk widgets under `widget` the theme's look: section boxes become white
    (dark: raised) cards with a thin border, lists and entries get flat borders that light up
    in the accent colour when focused, checkboxes and radio buttons lose their grey flash."""
    for w in _walk(widget):
        cls = w.winfo_class()
        try:
            if cls == 'Labelframe':
                w.configure(bg=T['card'], fg=T['fg2'], font=(FONT, 10, 'bold'), bd=0, relief='flat',
                            highlightthickness=1, highlightbackground=T['line'], highlightcolor=T['line'], padx=8, pady=6)
                for d in _walk(w):          # what sits on the page colour inside it now sits on the card
                    if d is not w and str(d.cget('bg')).lower() == T['bg'].lower():
                        d.configure(bg=T['card'])
            elif cls in ('Radiobutton', 'Checkbutton'):
                bg = w.cget('bg')
                opts = dict(activebackground=bg, activeforeground=T['fg'], fg=T['fg'], highlightthickness=0, bd=0, cursor='hand2')
                if str(w.cget('indicatoron')) in ('1', 'true'):
                    opts['selectcolor'] = T['input']
                w.configure(**opts)
            elif cls == 'Listbox':
                w.configure(bg=T['card'], fg=T['fg'], selectbackground=T['sel_bg'], selectforeground=T['sel_fg'], relief='flat',
                            bd=0, highlightthickness=1, highlightbackground=T['line'], highlightcolor=T['accent'], activestyle='none')
            elif cls in ('Entry', 'Spinbox'):
                w.configure(relief='flat', bd=0, highlightthickness=1, highlightbackground=T['line'], highlightcolor=T['accent'],
                            bg=T['input'], fg=T['fg'], insertbackground=T['fg'], disabledbackground=T['bg3'],
                            readonlybackground=T['bg3'], selectbackground=T['sel_bg'], selectforeground=T['sel_fg'])
                if cls == 'Spinbox':
                    w.configure(buttonbackground=T['bg3'])
            elif cls == 'Text':
                w.configure(relief='flat', bd=0, highlightthickness=1, highlightbackground=T['line'], highlightcolor=T['line'],
                            insertbackground=T['fg'], selectbackground=T['sel_bg'], selectforeground=T['sel_fg'])
            elif cls == 'Panedwindow':
                w.configure(bg=T['bg'], sashwidth=8, bd=0, sashrelief='flat')
        except tk.TclError:
            pass


def set_titlebar(root, dark):
    """Windows 10/11: a dark title bar in dark mode (Windows draws it, so Tk can't colour it)."""
    if sys.platform != 'win32':
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):     # DWMWA_USE_IMMERSIVE_DARK_MODE (19 on older Windows 10)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass


# ============================================================
# 3D BUTTON
# ============================================================

class RoundButton(tk.Canvas):
    """A rounded button standing on a thin base, so it reads as raised: it shades under the
    mouse and presses down onto its base when clicked. Behaves like tk.Button for the
    options the app uses (text, state, command)."""

    KINDS = ('primary', 'secondary', 'ghost', 'danger')

    def __init__(self, parent, text, command=None, kind='secondary', theme=None, height=None, font=None, padx=16):
        self.T = theme
        try:
            parent_bg = parent.cget('bg')
        except tk.TclError:
            parent_bg = theme['bg']
        self._h = height or (40 if kind == 'primary' else 34)
        super().__init__(parent, height=self._h + 2, bg=parent_bg, highlightthickness=0, bd=0, cursor='hand2', takefocus=1)
        self._text, self._cmd, self._kind, self._state = text, command, kind, 'normal'
        self._font = font or (FONT, 10, 'bold') if kind == 'primary' else (font or (FONT, 10))
        self._padx = padx
        self._hover = self._pressed = self._focus = False
        self._fill_now = None
        self._anim = None
        self._draw()
        for seq, fn in (('<Enter>', self._on_enter), ('<Leave>', self._on_leave), ('<ButtonPress-1>', self._on_press),
                        ('<ButtonRelease-1>', self._on_release), ('<FocusIn>', self._on_focus), ('<FocusOut>', self._on_blur),
                        ('<Return>', self._on_key), ('<space>', self._on_key)):
            self.bind(seq, fn, add='+')

    def _colors(self):
        T, k = self.T, self._kind
        if self._state == 'disabled':
            return T['bg3'], T['line'], T['fg3'], T['bg3']
        if k == 'primary':
            return T['accent'], T['accent'], T['ink'], T['accent_press']
        if k == 'ghost':
            return T['bg2'], T['line'], T['fg2'], T['btn_base']
        fg = (T['danger2'] if T['mode'] == 'light' else T['danger']) if k == 'danger' else T['fg']
        return T['bg3'] if T['mode'] == 'light' else T['card2'], T['line'], fg, T['btn_base']

    def _hover_fill(self):
        T = self.T
        fill = self._colors()[0]
        if self._kind == 'primary':
            return T['accent_hover']
        return blend(fill, T['accent'], 0.10) if T['mode'] == 'light' else blend(fill, '#ffffff', 0.07)

    def _draw(self, fill=None):
        self.delete('all')
        if getattr(self, '_measured', None) != self._text:      # measure only when the text changes
            self._bw = max(tkfont.Font(font=self._font).measure(self._text) + 2 * self._padx, 44)
            self._measured = self._text
            tk.Canvas.configure(self, width=self._bw + 2)
        w = self._bw
        normal, outline, fg, base = self._colors()
        fill = fill or self._fill_now or normal
        dy = 2 if self._pressed else 0
        r = 7
        round_rect(self, 1, 3, w, self._h + 1, r, fill=base, outline='')                 # the base it stands on
        round_rect(self, 1, 1 + dy, w, self._h - 1 + dy, r, fill=fill,
                   outline=self.T['accent'] if self._focus else outline, width=2 if self._focus else 1)
        self.create_text(w / 2 + 1, self._h / 2 + dy, text=self._text, fill=fg, font=self._font)

    def _fade_to(self, target):
        start = self._fill_now or self._colors()[0]
        if self._anim:
            self._anim.cancel()

        def step(v):
            self._fill_now = blend(start, target, v)
            self._draw()
        self._anim = tween(self, 130, step)

    def _on_enter(self, _e=None):
        if self._state == 'disabled':
            return
        self._hover = True
        self._fade_to(self._hover_fill())

    def _on_leave(self, _e=None):
        self._hover = self._pressed = False
        if self._state != 'disabled':
            self._fade_to(self._colors()[0])

    def _on_press(self, _e=None):
        if self._state == 'disabled':
            return
        self._pressed = True
        self.focus_set()
        self._draw()

    def _on_release(self, e=None):
        if self._state == 'disabled' or not self._pressed:
            return
        self._pressed = False
        self._draw()
        inside = e is None or (0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height())
        if inside and self._cmd:
            self._cmd()

    def _on_key(self, _e=None):
        if self._state != 'disabled' and self._cmd:
            self._pressed = True
            self._draw()
            self.after(90, lambda: (setattr(self, '_pressed', False), self._draw()))
            self._cmd()

    def _on_focus(self, _e=None):
        self._focus = True
        self._draw()

    def _on_blur(self, _e=None):
        self._focus = False
        self._draw()

    def invoke(self):
        if self._state != 'disabled' and self._cmd:
            self._cmd()

    def configure(self, cnf=None, **kw):
        changed = False
        for key in ('text', 'state', 'command'):
            if key in kw:
                val = kw.pop(key)
                if key == 'text':
                    self._text = val
                elif key == 'state':
                    self._state = str(val)
                    self._fill_now = None
                else:
                    self._cmd = val
                changed = True
        result = super().configure(cnf, **kw) if (cnf or kw) else None
        if changed:
            self._draw()
        return result

    config = configure

    def cget(self, key):
        if key == 'text':
            return self._text
        if key == 'state':
            return self._state
        if key == 'command':
            return self._cmd
        return super().cget(key)

    def __getitem__(self, key):
        return self.cget(key)


# ============================================================
# TAB BAR WITH A SLIDING UNDERLINE
# ============================================================

class TabBar(tk.Frame):
    """Tabs for a ttk.Notebook whose own tabs are hidden: the line under the open tab
    slides to the tab you pick (or that the app switches to)."""

    def __init__(self, parent, notebook, T):
        super().__init__(parent, bg=T['bg2'], highlightthickness=0)
        self.nb, self.T = notebook, T
        self.labels = []
        row = tk.Frame(self, bg=T['bg2'])
        row.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        for i, tab_id in enumerate(notebook.tabs()):
            lbl = tk.Label(row, text=notebook.tab(tab_id, 'text').strip(), bg=T['bg2'], fg=T['fg2'],
                           font=(FONT, 10), padx=13, pady=10, cursor='hand2')
            lbl.pack(side=tk.LEFT)
            lbl.bind('<Button-1>', lambda e, i=i: self.nb.select(i))
            lbl.bind('<Enter>', lambda e, l=lbl: l.configure(fg=self.T['fg']), add='+')
            lbl.bind('<Leave>', lambda e, l=lbl: self._paint(), add='+')
            self.labels.append(lbl)
        tk.Frame(self, bg=T['line'], height=1).place(relx=0, rely=1.0, relwidth=1.0, anchor='sw')
        self.bar = tk.Frame(self, bg=T['accent'], height=3)
        self._x, self._uw = 0, 0
        self._anim = None
        notebook.bind('<<NotebookTabChanged>>', lambda e: self._sync(), add='+')
        self.after(60, lambda: self._sync(animate=False))

    def _paint(self):
        try:
            cur = self.nb.index('current')
        except tk.TclError:
            return
        for i, lbl in enumerate(self.labels):
            on = i == cur
            lbl.configure(fg=self.T['fg'] if on else self.T['fg2'], font=(FONT, 10, 'bold') if on else (FONT, 10))

    def _sync(self, animate=True):
        if not self.winfo_exists():
            return
        self._paint()
        try:
            lbl = self.labels[self.nb.index('current')]
        except (tk.TclError, IndexError):
            return
        self.update_idletasks()
        tx = lbl.winfo_rootx() - self.winfo_rootx()
        tw = lbl.winfo_width()
        sx, sw = self._x, self._uw or tw
        if self._anim:
            self._anim.cancel()

        def step(v):
            self._x, self._uw = sx + (tx - sx) * v, sw + (tw - sw) * v
            self.bar.place(x=self._x + 8, rely=1.0, y=-3, width=max(self._uw - 16, 8), height=3)
        self._anim = tween(self, 230 if animate and self._uw else 0, step)


# ============================================================
# SLIDE-IN MESSAGE (toast)
# ============================================================

class Toast:
    """A message that slides up in the bottom-right corner and leaves by itself (click it
    to close it now). Several stack upwards."""
    _open = []

    def __init__(self, root, title, message, T, ms=6000, kind='info'):
        self.root = root
        edge = {'info': T['accent'], 'good': T['buy'], 'warn': T['warning'], 'bad': T['sell']}.get(kind, T['accent'])
        self.frame = tk.Frame(root, bg=T['card'], highlightthickness=1, highlightbackground=T['line'])
        tk.Frame(self.frame, bg=edge, width=4).pack(side=tk.LEFT, fill=tk.Y)
        body = tk.Frame(self.frame, bg=T['card'])
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=14, pady=10)
        tk.Label(body, text=title, bg=T['card'], fg=T['fg'], font=(FONT, 11, 'bold'), anchor='w', justify=tk.LEFT).pack(fill=tk.X)
        if message:
            tk.Label(body, text=message, bg=T['card'], fg=T['fg2'], font=(FONT, 10), anchor='w', justify=tk.LEFT,
                     wraplength=380).pack(fill=tk.X, pady=(2, 0))
        for w in [self.frame, body] + list(body.winfo_children()):
            w.bind('<Button-1>', lambda e: self.close(), add='+')
        self.frame.update_idletasks()
        self.h = self.frame.winfo_reqheight()
        self.offset = sum(t.h + 10 for t in Toast._open)
        Toast._open.append(self)
        self._place(self.h + 30)
        self.frame.lift()
        tween(self.frame, 300, lambda v: self._place((self.h + 30) * (1 - v)))
        self._timer = root.after(ms, self.close)

    def _place(self, dy):
        try:
            self.frame.place(relx=1.0, rely=1.0, anchor='se', x=-18, y=-38 - self.offset + dy)
        except tk.TclError:
            pass

    def close(self):
        if self not in Toast._open:
            return
        Toast._open.remove(self)
        try:
            self.root.after_cancel(self._timer)
        except tk.TclError:
            pass
        tween(self.frame, 200, lambda v: self._place((self.h + 30) * v), done=self.frame.destroy, ease=lambda t: t * t)


# ============================================================
# SCAN SUMMARY CARD (raised card with a soft shadow)
# ============================================================

class SummaryCard(tk.Canvas):
    """The scan summary as one raised card: stocks scanned, average score and a bar showing
    how many stocks are buy / hold / sell. Numbers count up and the bar grows after a scan;
    the card lifts slightly under the mouse."""

    ORDER = (('STRONG BUY', 'Strong buy'), ('BUY', 'Buy'), ('HOLD', 'Hold'), ('SELL', 'Sell'), ('STRONG SELL', 'Strong sell'))

    def __init__(self, parent, T):
        super().__init__(parent, height=124, bg=T['bg'], highlightthickness=0, bd=0)
        self.T = T
        self.counts = {k: 0 for k, _ in self.ORDER}
        self.total, self.avg, self.when = 0, 0.0, ''
        self.v = 1.0
        self._lifted = 0
        self._anim = None
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self._lift_to(3), add='+')
        self.bind('<Leave>', lambda e: self._lift_to(0), add='+')

    def _lift_to(self, target):
        start = self._lifted

        def step(v):
            self._lifted = start + (target - start) * v
            self.draw()
        tween(self, 160, step)

    def update_values(self, counts, total, avg, when='', animate=True):
        self.counts = {k: counts.get(k, 0) for k, _ in self.ORDER}
        self.total, self.avg, self.when = total, avg, when
        if self._anim:
            self._anim.cancel()

        def step(v):
            self.v = v
            self.draw()
        self._anim = tween(self, 1000 if animate else 0, step)

    def draw(self):
        T = self.T
        self.delete('all')
        w = self.winfo_width()
        if w < 50:
            return
        lift = self._lifted
        x1, y1, x2, y2 = 2, 6 - lift, w - 4, 112 - lift
        soft_shadow(self, x1, y1, x2, y2, 12, T['bg'], T['shadow'], depth=5, lift=int(lift))
        round_rect(self, x1, y1, x2, y2, 12, fill=T['card'], outline=T['line'])
        e = self.v
        cy = y1 + 18
        if self.total == 0:
            self.create_text(x1 + 26, cy + 30, anchor='w', text='Scan your watchlist (F5) to see how many stocks are buy, hold or sell.',
                             fill=T['fg2'], font=(FONT, 11))
            return
        self.create_text(x1 + 26, cy + 6, anchor='nw', text=str(round(self.total * e)), fill=T['fg'], font=(DISPLAY, 28, 'bold'))
        self.create_text(x1 + 28, cy + 54, anchor='nw', text='stocks scanned', fill=T['fg2'], font=(FONT, 9))
        self.create_text(x1 + 170, cy + 6, anchor='nw', text=f"{self.avg * e:.1f}", fill=T['accent'], font=(DISPLAY, 28, 'bold'))
        self.create_text(x1 + 172, cy + 54, anchor='nw', text='average score', fill=T['fg2'], font=(FONT, 9))
        bx1, bx2 = x1 + 330, x2 - 210
        if bx2 - bx1 > 120:
            by = cy + 12
            round_rect(self, bx1, by, bx2, by + 16, 8, fill=T['bg3'], outline='')
            x = bx1
            live = [(k, c) for k, c in ((k, self.counts[k]) for k, _ in self.ORDER) if c]
            for i, (k, c) in enumerate(live):
                seg = (bx2 - bx1) * c / self.total * e
                if seg >= 1:
                    end = x + seg - (2 if i < len(live) - 1 else 0)
                    round_rect(self, x, by, max(end, x + 1), by + 16, 3 if 0 < i < len(live) - 1 else 6,
                               fill=signal_color(T, k), outline='')
                x += seg
            lx = bx1
            for k, label in self.ORDER:
                n = round(self.counts[k] * e)
                self._marker(lx + 6, by + 40, k)
                t1 = self.create_text(lx + 16, by + 40, anchor='w', text=label, fill=T['fg2'], font=(FONT, 9))
                bb = self.bbox(t1)
                t2 = self.create_text(bb[2] + 6, by + 40, anchor='w', text=str(n), fill=T['fg'], font=(DISPLAY, 10, 'bold'))
                lx = self.bbox(t2)[2] + 22
        if self.when:
            self.create_text(x2 - 22, cy + 22, anchor='ne', text=self.when, fill=T['fg2'], font=(FONT, 9), justify=tk.RIGHT)

    def _marker(self, x, y, rec):
        c = signal_color(self.T, rec)
        if rec == 'HOLD':
            self.create_rectangle(x - 5, y - 2, x + 5, y + 2, fill=c, outline='')
        elif 'BUY' in rec:
            self.create_polygon(x, y - 5, x + 5, y + 4, x - 5, y + 4, fill=c, outline='')
        else:
            self.create_polygon(x - 5, y - 4, x + 5, y - 4, x, y + 5, fill=c, outline='')


# ============================================================
# SCORE RING (Score Breakdown tab)
# ============================================================

class ScoreRing(tk.Canvas):
    """The score as a ring that sweeps round to its value, with the number counting up."""

    def __init__(self, parent, T, size=168):
        super().__init__(parent, width=size, height=size, bg=parent.cget('bg'), highlightthickness=0)
        self.T, self._size = T, size

    def show(self, score, color, label):
        T, s = self.T, self._size
        pad, width = 14, 13

        def step(v):
            self.delete('all')
            self.create_oval(pad, pad, s - pad, s - pad, outline=T['bg3'], width=width)
            ext = -359.9 * (score / 100) * v
            if abs(ext) > 0.5:
                self.create_arc(pad, pad, s - pad, s - pad, start=90, extent=ext, style=tk.ARC, outline=color, width=width)
            self.create_text(s / 2, s / 2 - 8, text=f"{score * v:.1f}", fill=T['fg'], font=(DISPLAY, 26, 'bold'))
            self.create_text(s / 2, s / 2 + 20, text=label, fill=T['fg2'], font=(FONT, 10, 'bold'))
        return tween(self, 900, step)


# ============================================================
# WINDOW FADE (switching light / dark)
# ============================================================

def fade_window(root, start, end, ms, done=None):
    def step(v):
        try:
            root.attributes('-alpha', start + (end - start) * v)
        except tk.TclError:
            pass
    return tween(root, ms, step, done=done, ease=ease_in_out)
