"""Klodik: a pixel desktop overlay that mirrors what Claude Code is doing.

State comes from state.json, written by hook.py (Claude Code hooks).
Hover: a small "ask" pill slides out. Click the mascot or the pill: the chat cartridge unfolds.
Drag the mascot to move. Right-click for the menu. Esc closes the chat or the menu.

Design: dark 8-bit "cartridges" with stepped pixel corners and an orange label tab; text types out
with a block cursor, windows unfold in pixel steps from the speech tail. Eyes follow the cursor.
Respects the Windows "show animations" setting.
"""
import ctypes
import json
import math
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import freeai  # noqa: E402  free LLM backend (Groq / Gemini / Pollinations)
import l10n  # noqa: E402  interface strings in the chosen language
from l10n import t  # noqa: E402
import world  # noqa: E402  themes, weather, devices and music
import pc_actions  # noqa: E402  local PC actions and intent recognition
l10n.set_translator(freeai.translate)   # any interface string without a translation gets one by itself

SESSIONS = os.path.join(HERE, "sessions")   # one state file per chat, written by hook.py
CONFIG = os.environ.get("CLAUDIK_CONFIG") or os.path.join(HERE, "config.json")   # tests point this elsewhere
STARTUP_LNK = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup\Claudik.lnk")
LOG = os.path.join(HERE, "overlay.log")

# Layout: one transparent window; mascot pinned bottom-right, cartridges unfold upward from its head.
# Dark is the user's explicit choice. Tabs are uppercase mono on purpose: they are the cartridge label motif.
KEY = "#020203"          # transparent colour key, never drawn; near-black so text edges blend to a dark outline, not magenta
C = {
    "bg": "#15110e",       # cartridge body: warm near-black, biased to the orange
    "surface": "#211a15",  # inner wells, bot messages
    "line": "#3b2d23",     # pixel borders
    "line_hi": "#5b4130",  # top highlight row
    "text": "#f1e7dc",
    "muted": "#9a8878",
    "accent": "#d97757",   # Claude orange
    "accent_dk": "#8f4a33",
    "gold": "#f2c14e",
    "mint": "#7ee787",
    "sky": "#6cb8ff",
    "rose": "#e8455c",
    "ink": "#1a1410",
    "shadow": "#0b0907",
}
ORANGE, ORANGE_DARK, INK = C["accent"], "#b85f40", C["ink"]

W, H = 400, 560
P = 8                    # one mascot pixel
TICK = 80                # ms per frame: ~12 fps reads as pixel art, not video
STEP = 3                 # size of a stepped corner

LABEL = {
    "idle": "", "thinking": "думаю…", "reading": "читаю код", "writing": "пишу код",
    "running": "запускаю команду", "searching": "шукаю", "web": "лажу в інеті",
    "agent": "кличу помічників", "asking": "чекаю на тебе!", "done": "готово", "error": "ой, помилка",
}
TAB = {
    "idle": "КЛОДІК", "thinking": "ДУМАЮ", "reading": "ЧИТАЮ", "writing": "ПИШУ", "running": "ТЕРМІНАЛ",
    "searching": "ПОШУК", "web": "ІНТЕРНЕТ", "agent": "КОМАНДА", "asking": "ПИТАННЯ", "done": "ГОТОВО",
    "error": "ПОМИЛКА", "answer": "ВІДПОВІДЬ", "tip": "ПІДКАЗКА",
}
WORKING = {"thinking", "reading", "writing", "running", "searching", "web", "agent"}

# One variant is picked at random when a process starts and re-rolled every ~12 s,
# so the same work rarely looks the same twice.
VARIANTS = {
    "thinking": ["dots", "bulb", "gears", "tap"],
    "reading": ["book", "scroll", "glasses"],
    "writing": ["pencil", "keyboard", "hammer"],
    "running": ["terminal", "sprint", "progress"],
    "searching": ["magnifier", "radar", "binoculars"],
    "web": ["globe", "antenna", "surf"],
    "agent": ["minis", "walkie"],
    "asking": ["question", "sign"],
    "done": ["flag", "confetti", "hearts", "spin"],
    "error": ["shake", "smoke", "flat"],
}
# One idle show plays every 3 to 8 s while nothing is going on.
IDLE_SHOWS = {  # name: frames
    "look": 34, "yawn": 30, "stretch": 24, "dance": 48, "juggle": 54, "bug": 80,
    "cookie": 50, "kick": 40, "sneeze": 26, "yoyo": 48, "game": 60, "blow": 46,
}
# What he explains now and then while idle, in this order.
TIPS = [
    "Потягни мене мишкою, щоб пересунути.",
    "Наведи на мене й клацни, щоб спитати щось про проект.",
    "Права кнопка відкриває меню: чат, мова, тема.",
    "У меню «Тема» є весна, сакура, Неон-Маямі, Хелловін та інші.",
    "«Підключити до чату» в меню вибирає, за яким чатом Claude я стежу.",
    "«Не заважати» в меню робить мене прозорим для кліків. Потрійний клік по мені повертає.",
    "Підключи навушники чи геймпад, і я їх візьму.",
    "Увімкни музику, і я потанцюю.",
    "Клацни по бульбашці, щоб її закрити. Esc закриває чат і меню.",
]

SCREEN_COMMENTS = {
    "youtube": [
        "YouTube? Головне, щоб робота не стояла.",
        "Дивишся відео замість коду? Класика. 💀",
        "Сподіваюся, це хоча б корисний туторіал, а не чергові меми.",
    ],
    "video": [
        "Фільм у робочий час? Сміливо. 🎬",
    ],
    "music": [
        "Нормальний трек, працювати можна. 🎧",
        "Звук навалює, аби тільки код не ламався.",
    ],
    "code": [
        "Бачу код. Дивись не накатай нових багів. 💀",
        "Ctrl+S тицьни, поки світло не вирубили. 💾",
        "Пишеш код? Головне тести не забудь написати.",
    ],
    "github": [
        "GitHub. Знову коміт у main без тестів? 🐙",
        "Дивись уважно в diff, щоб не пушити сміття.",
    ],
    "terminal": [
        "Термінал відкритий. Тільки без бездумних команд з інтернету. 💻",
        "Хакер у справі. Сподіваюся, ти знаєш, що робиш.",
    ],
    "search": [
        "Гуглиш помилку? Читай уважніше, що там пишуть на StackOverflow. 🔍",
    ],
    "chat": [
        "Знову переписки. Менше балачок — більше діла.",
    ],
    "gaming": [
        "Катка? Сподіваюся, не зливаєш рейтинг. 🎮",
        "Грай нормально, я все бачу. 💀",
    ],
    "idle": [
        "Екран пустує. Пішов чай пити чи здався? ☕",
        "Я покараулю екран, усе під контролем 👀",
    ],
    "general": [
        "Працюй, результат сам себе не зробить.",
        "Якщо очі втомилися — подивись у вікно на 20 секунд.",
    ],
}


def get_foreground_info() -> tuple[str, str]:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return "", ""
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
        title = buf.value.strip()

        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pname = ""
        hproc = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
        if hproc:
            pbuf = ctypes.create_unicode_buffer(512)
            sz = ctypes.c_ulong(512)
            ctypes.windll.kernel32.QueryFullProcessImageNameW(hproc, 0, pbuf, ctypes.byref(sz))
            ctypes.windll.kernel32.CloseHandle(hproc)
            pname = os.path.basename(pbuf.value).lower()
        return title, pname
    except Exception:
        return "", ""


def classify_screen(title: str, pname: str) -> tuple[str, str]:
    t = (title or "").lower()
    p = (pname or "").lower()
    if not title or title == "Program Manager" or not t.strip():
        return ("idle", "")
    if "youtube" in t or "youtu.be" in t:
        clean = title.split(" - YouTube")[0].split(" - Google Chrome")[0].split(" - Microsoft​ Edge")[0].split(" - Mozilla Firefox")[0].split(" - Opera")[0].split(" - Brave")[0].strip()
        return ("youtube", clean)
    if any(k in t for k in ("netflix", "twitch", "vlc media player", "megogo", "kinogo", "prime video")):
        return ("video", title)
    if any(k in t or k in p for k in ("spotify", "soundcloud", "apple music", "deezer", "aimp", "foobar")):
        return ("music", title)
    if any(k in t or k in p for k in ("visual studio code", "code.exe", "pycharm", "sublime", "notepad++", "cursor.exe", "intellij", "clion")):
        return ("code", title)
    if "github" in t or "gitlab" in t:
        return ("github", title)
    if any(k in t or k in p for k in ("powershell", "cmd.exe", "terminal", "bash", "wsl", "mintty")):
        return ("terminal", title)
    if any(k in t for k in ("google search", "пошук google", "поиск в google", "stackoverflow", "chatgpt", "claude")):
        return ("search", title)
    if any(k in t or k in p for k in ("telegram", "discord", "slack", "whatsapp", "viber")):
        return ("chat", title)
    if any(k in t or k in p for k in ("steam", "minecraft", "dota", "cs2", "roblox", "genshin")):
        return ("gaming", title)
    return ("general", title)


def log(msg: str) -> None:
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def work_area() -> tuple[int, int, int, int]:
    try:
        class RECT(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]
        rc = RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rc), 0)
        return rc.l, rc.t, rc.r, rc.b
    except Exception:  # noqa: BLE001
        return 0, 0, 1920, 1040


def ago(ts: float) -> str:
    m = int((time.time() - float(ts)) // 60)
    return t("щойно") if m < 1 else (f"{m} {t('хв тому')}" if m < 60 else f"{m // 60} {t('год тому')}")


def make_shortcut(path: str) -> None:
    """A .lnk that starts the overlay with pythonw (no console window)."""
    q = lambda s: "'" + s.replace("'", "''") + "'"   # PowerShell single-quoted literal
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    script = os.path.join(HERE, "overlay.pyw")
    icon = os.path.join(HERE, "icon.ico")
    icon_ps = f";$s.IconLocation={q(icon + ',0')}" if os.path.exists(icon) else ""
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(path)});$s.TargetPath={q(pythonw)};"
          f"$s.Arguments={q(chr(34) + script + chr(34))};$s.WorkingDirectory={q(HERE)}{icon_ps};$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000, timeout=20)


def animations_on() -> bool:
    """Windows 'Show animations in Windows' (SPI_GETCLIENTAREAANIMATION)."""
    try:
        on = ctypes.c_bool(True)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(on), 0)
        return bool(on.value)
    except Exception:  # noqa: BLE001
        return True


MOTION = animations_on()


def shorten(s: str, n: int) -> str:
    s = s.replace(" — ", ", ").replace("—", "-")  # model answers love em dashes; the bubble doesn't
    s = " ".join(s.replace("*", "").replace("`", "").replace("#", "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def first_sentence(text: str, n: int = 110) -> str:
    """Local, offline summary: the first sentence of Claude's answer."""
    para = text.strip().split("\n\n")[0]
    m = re.match(r"(.+?[.!?…])(\s|$)", " ".join(para.split()))
    return shorten(m.group(1) if m else para, n)


def ease_steps(p: float, steps: int = 6) -> float:
    """Ease-out, quantised to a few steps so windows open like 8-bit sprites."""
    if not MOTION:
        return 1.0
    p = max(0.0, min(1.0, p))
    e = 1 - (1 - p) ** 3
    return round(e * steps) / steps


class Claudik:
    def __init__(self) -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
        self.root = tk.Tk()
        self.root.title("Клодік")
        icon_path = os.path.join(HERE, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)

        fams = set(tkfont.families())
        mono = next((f for f in ("Cascadia Mono", "Cascadia Code", "Consolas") if f in fams), "Courier New")
        body = next((f for f in ("Segoe UI Variable Text", "Segoe UI") if f in fams), "Arial")
        self.f_body = tkfont.Font(family=body, size=9)
        self.f_small = tkfont.Font(family=body, size=8)
        self.f_tab = tkfont.Font(family=mono, size=7, weight="bold")
        self.f_mono = tkfont.Font(family=mono, size=8)
        self.f_big = tkfont.Font(family=body, size=11, weight="bold")
        self.KEY = KEY

        cfg = self.load_cfg()
        l, t, r, b = work_area()
        migrate = cfg.get("v") != 2 and "x" in cfg   # saved by the older, smaller window: keep the mascot put
        if migrate:
            cfg["x"] += 340 - W
            cfg["y"] += 330 - H
        x, y = cfg.get("x", r - W - 6), cfg.get("y", b - H + 4)
        x = min(max(l - W + 120, x), r - W - 6)
        y = min(max(t - H + 140, y), b - H + 4)
        self.root.geometry(f"{W}x{H}+{x}+{y}")
        if migrate:
            self.root.update_idletasks()
            self.save_cfg()   # otherwise the shift is applied again on every launch

        self.cv = tk.Canvas(self.root, width=W, height=H, bg=KEY, highlightthickness=0)
        self.cv.pack()

        self.mx = W - 14 * P - 26          # mascot top-left
        self.my = H - 8 * P - 50
        self.head = (self.mx + 7 * P, self.my)  # where speech tails point

        # chat input (lives inside the chat cartridge)
        self.entry = tk.Entry(self.root, bg=C["surface"], fg=C["text"], insertbackground=C["accent"],
                              relief="flat", font=self.f_body, highlightthickness=0, bd=0,
                              insertwidth=6, selectbackground=C["accent_dk"])
        self.entry.bind("<Return>", self.on_ask)
        self.entry.bind("<Escape>", lambda e: self.close_chat())
        self.entry_win = self.cv.create_window(0, 0, window=self.entry, anchor="w", state="hidden")

        # state
        self.mood = "idle"
        self.variant = ""
        self.mood_since = time.time()
        self.mood_frame = 0
        self.frame = 0
        self.state_key = None                # (file, mtime) last read
        self.state_ts = 0.0
        self.cwd = os.path.expanduser("~")
        self.follow = cfg.get("follow", "auto")   # "auto" = whichever chat moved last, else a session id
        self.lang_pref = cfg.get("lang", "auto")  # "auto" = the language you write to Claude in, else a code
        self.auto_lang = cfg.get("auto_lang", "uk")
        l10n.set_lang(self.lang())
        self.weather = world.Weather()
        self.theme = "none"
        self.costume_theme = "none"          # what he is wearing; lags behind self.theme while he changes
        self.intro: dict | None = None       # a short transition: {"kind", "f", "len"}
        self.worn_phones = False
        self.pad_held = False
        self.ghost = False                   # clicks pass through him
        self.ghost_clicks: list[float] = []
        self.mouse_was_down = False
        self.tip_i = int(cfg.get("tip", 0))
        self.next_tip_at = time.time() + 40
        self.set_theme(cfg.get("theme", "none"), save=False)
        self.devices = world.DeviceWatch(os.getpid())
        self.track_seen = ""
        self.screen_react = cfg.get("screen_react", True)
        self.media_active = False
        self.next_screen_check = time.time() + 2.0
        self.next_screen_comment_at = time.time() + random.uniform(20.0, 45.0)
        self.last_screen_comment = ""
        self.active_win_title = ""
        self.active_pname = ""
        self.active_cat = "idle"
        self.active_media = ""
        self.commenting_ai = False
        self.last_redraw = 0.0
        self.drag_v = 0.0                    # horizontal drag speed, for the struggle
        self.drag_lastx = 0
        self.sid = ""
        self.title = ""
        self.recent: dict[str, list[str]] = {}    # per chat: last Claude answers, context for questions
        self.busy_q = False
        self.hidden_until = 0.0
        self.drag = None
        self.last_activity = time.time()

        self.bubble: dict | None = None      # {text, tab, until}
        self.bubble_born_frame = 0
        self.bubble_box = None

        self.chat_open = False
        self.chat_anim = 0.0                 # 0 closed .. 1 open
        self.chat_msgs: list[dict] = []      # {who: "me"|"bot"|"note", text, born}
        self.hover = False
        self.pill_anim = 0.0
        self.hover_job = None

        self.show = ""                       # current idle show
        self.show_frame = 0
        self.next_show_at = time.time() + random.uniform(5, 9)
        self.greet_frame = -100

        self.root.bind("<Enter>", self.on_enter)
        self.root.bind("<Leave>", self.on_leave)
        self.cv.bind("<ButtonPress-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_drag)
        self.cv.bind("<ButtonRelease-1>", self.on_release)
        self.cv.bind("<Button-3>", self.on_menu)
        self.root.bind("<Escape>", lambda e: self.close_chat())

        self.menu_win: tk.Toplevel | None = None
        self.menu_outside = 0

        self.read_state(initial=True)
        self.say_t("привіт! я тут, якщо що", 6, "idle")
        if cfg.get("ghost"):
            self.root.after(300, lambda: self.set_ghost(True, announce=False))
        self.apply_overlay_styles()
        self.loop()

    def apply_overlay_styles(self) -> None:
        try:
            u = ctypes.windll.user32
            self.root.update_idletasks()
            w_id = self.root.winfo_id()
            hwnd = u.GetParent(w_id) or w_id

            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_LAYERED = 0x00080000
            WS_EX_NOACTIVATE = 0x08000000

            ex = u.GetWindowLongW(hwnd, -20)
            ex = (ex | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW
            if getattr(self, "ghost", False):
                ex |= 0x00000020  # WS_EX_TRANSPARENT
            u.SetWindowLongW(hwnd, -20, ex)

            # Keep topmost without stealing focus
            u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)

            # Windows 11 DWM: disable window corner rounding and drop shadow on transparent overlay
            try:
                dwm = ctypes.windll.dwmapi
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_DONOTROUND = ctypes.c_int(1)
                dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(DWMWCP_DONOTROUND), 4)
            except Exception:
                pass
        except Exception as e:
            log(f"apply_overlay_styles: {e!r}")

    def _set_noactivate(self, enable: bool) -> None:
        try:
            u = ctypes.windll.user32
            hwnd = u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            ex = u.GetWindowLongW(hwnd, -20)
            if enable:
                u.SetWindowLongW(hwnd, -20, ex | 0x08000000)
            else:
                u.SetWindowLongW(hwnd, -20, ex & ~0x08000000)
        except Exception:
            pass

    # config
    def load_cfg(self) -> dict:
        try:
            with open(CONFIG, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_cfg(self) -> None:
        g = lambda name, default: getattr(self, name, default)   # the first save can run before __init__ ends
        try:
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump({"v": 2, "x": self.root.winfo_x(), "y": self.root.winfo_y(), "follow": g("follow", "auto"),
                           "lang": g("lang_pref", "auto"), "auto_lang": g("auto_lang", "uk"), "theme": g("theme", "none"),
                           "ghost": g("ghost", False), "tip": g("tip_i", 0), "screen_react": g("screen_react", True)}, f)
        except OSError:
            pass

    # state
    def set_mood(self, m: str) -> None:
        if m != self.mood:
            self.mood = m
            self.mood_since = time.time()
            self.mood_frame = 0
            self.variant = random.choice(VARIANTS.get(m, [""]))
            if m == "done" and self.theme == "sakura" and random.random() < 0.5:
                self.variant = "bow"
            if m != "idle":
                self.weather.shake_off()       # work starts: snow and leaves get shaken off
            self.show = ""
            self.last_activity = time.time()

    # themes
    def set_theme(self, key: str, save: bool = True) -> None:
        new = key if key in world.THEMES else "none"
        animate = save and MOTION and new != self.theme
        self.theme = new
        accent = world.THEMES[self.theme].get("accent", ("#d97757", "#8f4a33"))
        C["accent"], C["accent_dk"] = accent
        self.weather.set_theme(self.theme, W, H)
        self.show = ""
        if not animate:
            self.costume_theme = new
        elif new == "none":
            self.intro = {"kind": "undress", "f": 0, "len": 20}     # he lifts the outfit off
        else:
            self.intro = {"kind": "dress", "f": 0, "len": 36}       # spins, then pulls the new outfit on
        if save:
            self.save_cfg()

    # ghost mode: clicks pass through him; three quick clicks on him bring him back
    def set_ghost(self, on: bool, announce: bool = True) -> None:
        u = ctypes.windll.user32
        hwnd = u.GetParent(self.root.winfo_id())
        ex = u.GetWindowLongW(hwnd, -20)                      # GWL_EXSTYLE
        u.SetWindowLongW(hwnd, -20, (ex | 0x80020) if on else (ex & ~0x20))   # WS_EX_LAYERED | WS_EX_TRANSPARENT
        self.ghost = on
        self.ghost_clicks = []
        if on:
            self.close_chat()
            self.hover = False
        if announce:
            self.say_t("Тепер кліки проходять крізь мене. Швидко клацни по мені 3 рази поспіль, щоб повернути." if on else
                       "Я знову тут!", 7, "idle")
            self.save_cfg()

    def tick_ghost(self) -> None:
        """While clicks pass through, watch the mouse button ourselves and count clicks on him."""
        if not self.ghost:
            return
        down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        if down and not self.mouse_was_down:
            x, y = self.root.winfo_pointerxy()
            now = time.time()
            if not self.in_mascot(x - self.root.winfo_rootx(), y - self.root.winfo_rooty()):
                self.ghost_clicks = []                       # a click elsewhere breaks the series
            else:
                if self.ghost_clicks and now - self.ghost_clicks[-1] > 0.45:
                    self.ghost_clicks = []                   # too slow: only a quick triple click counts
                self.ghost_clicks.append(now)
                if len(self.ghost_clicks) >= 3:
                    self.set_ghost(False)
        self.mouse_was_down = down

    def toggle_autostart(self) -> None:
        if os.path.exists(STARTUP_LNK):
            os.remove(STARTUP_LNK)
            self.say_t("Більше не запускаюсь разом із Windows.", 6, "idle")
            return
        make_shortcut(STARTUP_LNK)
        if os.path.exists(STARTUP_LNK):
            self.say_t("Тепер я запускаюсь разом із Windows.", 6, "idle")
        else:
            self.say_t("Не вийшло увімкнути автозапуск.", 6, "error")

    def toggle_screen_react(self) -> None:
        self.screen_react = not self.screen_react
        self.save_cfg()
        if self.screen_react:
            self.say_t("Буду підглядати й коментувати екран! 👀", 5, "idle")
        else:
            self.say_t("Більше не коментую екран.", 5, "idle")

    def tick_screen(self) -> None:
        now = time.time()
        if now < self.next_screen_check:
            return
        self.next_screen_check = now + 2.5

        title, pname = get_foreground_info()
        cat, clean_title = classify_screen(title, pname)
        self.active_win_title = title
        self.active_pname = pname
        self.active_cat = cat

        # Detect active media playback from window or system
        fg_media = cat in ("youtube", "video", "music")
        self.media_active = fg_media or bool(self.devices.music)

        # Track name from system player or foreground window
        active_media = ""
        if self.devices.music and self.devices.track:
            active_media = self.devices.track
        elif fg_media and clean_title:
            active_media = clean_title
        self.active_media = active_media

        if active_media and active_media != self.track_seen:
            self.track_seen = active_media
            if self.mood == "idle" and not self.chat_open:
                self.say(t("слухаю: ") + shorten(active_media, 50), 6, "idle")

        # Screen commentary at random intervals
        if not self.screen_react:
            return
        if now < self.next_screen_comment_at or self.mood != "idle" or self.chat_open or self.bubble or self.intro or self.commenting_ai:
            return

        self.next_screen_comment_at = now + random.uniform(35.0, 75.0)
        self.commenting_ai = True
        comment_item = active_media or clean_title or title
        threading.Thread(target=self._ai_comment_worker, args=(cat, comment_item), daemon=True).start()

    def _ai_comment_worker(self, cat: str, item: str) -> None:
        comment = None
        lang = self.lang()
        try:
            comment = freeai.comment_screen(cat, item, lang=lang)
        except Exception as e:
            log(f"comment_screen: {e!r}")

        def apply_comment() -> None:
            self.commenting_ai = False
            if self.chat_open or self.mood != "idle" or self.bubble:
                return
            if comment and len(comment.strip()) > 3:
                self.last_screen_comment = comment.strip()
                self.say(comment.strip(), 7, "tip")
            else:
                comments = SCREEN_COMMENTS.get(cat, SCREEN_COMMENTS["general"])
                candidates = [c for c in comments if c != self.last_screen_comment] or comments
                chosen = random.choice(candidates)
                self.last_screen_comment = chosen
                self.say_t(chosen, 7, "tip")

        self.root.after(0, apply_comment)

    def execute_pc_action(self, tag: str) -> None:
        """Execute a PC action requested by the user / decided by the AI."""
        tag = (tag or "").strip()
        if not tag:
            return
        log(f"execute_pc_action: {tag}")
        try:
            if tag.startswith("theme:"):
                th = tag[6:].strip().lower()
                if th in world.THEMES:
                    self.set_theme(th)
            elif tag == "mascot:corner":
                self.reset_pos()
            elif tag == "mascot:snooze":
                self.snooze()
            elif tag in ("chat:close", "close_chat"):
                self.close_chat()
            else:
                pc_actions.execute_action_tag(tag, cwd=self.cwd)
        except Exception as e:
            log(f"execute_pc_action error: {e!r}")

    def tick_tip(self) -> None:
        """Now and then, while idle, he explains one of his features."""
        now = time.time()
        if now < self.next_tip_at or self.mood != "idle" or self.chat_open or self.bubble or self.intro:
            return
        self.next_tip_at = now + random.uniform(240, 360)
        self.say_t(TIPS[self.tip_i % len(TIPS)], 10, "tip")
        self.tip_i += 1
        self.save_cfg()

    def tick_intro(self) -> None:
        """Advance the current transition, and start one when a device was plugged in or out."""
        it = self.intro
        if it:
            it["f"] += 1
            if it["kind"] == "dress" and it["f"] == 4:
                self.costume_theme = self.theme   # swapped mid-spin
            if it["f"] >= it["len"]:
                self.intro = None
                kind = it["kind"]
                if kind == "undress":
                    self.costume_theme = "none"
                elif kind == "dress" and self.mood == "idle" and world.INTRO_SHOW.get(self.theme):
                    self.show, self.show_frame = world.INTRO_SHOW[self.theme], 0   # e.g. brews tea, gets in the car
                self.worn_phones = {"phones_on": True, "phones_off": False}.get(kind, self.worn_phones)
                self.pad_held = {"pad_on": True, "pad_off": False}.get(kind, self.pad_held)
            return
        dev = self.devices.dev
        if dev["headphones"] != self.worn_phones:
            kind = "phones_on" if dev["headphones"] else "phones_off"
        elif dev["gamepad"] != self.pad_held:
            kind = "pad_on" if dev["gamepad"] else "pad_off"
        else:
            return
        if not MOTION:
            self.worn_phones, self.pad_held = dev["headphones"], dev["gamepad"]
            return
        self.intro = {"kind": kind, "f": 0, "len": {"phones_on": 24, "phones_off": 18, "pad_on": 18, "pad_off": 14}[kind]}
        self.show = ""

    def intro_lift(self, kind_on: str, kind_off: str, height: float) -> float:
        """How far above its worn spot a thing is during its on/off transition."""
        it = self.intro
        if not it or it["kind"] not in (kind_on, kind_off):
            return 0.0
        k = it["f"] / it["len"]
        return height * (1 - k) if it["kind"] == kind_on else height * k

    def pick_theme(self, x: int, y: int) -> None:
        self.popup(x, y, t("ТЕМА"), [
            (t(v["name"]), lambda k=k: self.set_theme(k), self.theme == k, t(v["hint"]))
            for k, v in world.THEMES.items()])

    def say(self, text: str, seconds: float, tab: str, src: str | None = None) -> None:
        """Show a bubble. `src` = a fixed interface string (re-rendered on a language switch);
        otherwise the text is free text, machine-translated on a switch."""
        if not text:
            self.bubble = None
            return
        self.bubble = {"text": text, "tab": tab, "until": time.time() + seconds, "src": src, "lang": self.lang()}
        self.bubble_born_frame = self.frame

    def say_t(self, src: str, seconds: float, tab: str, suffix: str = "") -> None:
        self.say(t(src) + suffix, seconds, tab, src=None if suffix else src)

    # language
    def lang(self) -> str:
        return self.auto_lang if self.lang_pref == "auto" else self.lang_pref

    def pick_lang(self, x: int, y: int) -> None:
        auto_name = freeai.LANGS.get(self.auto_lang, ("?",))[0]
        items = [(t("Авто (як у твоїх чатах)"), lambda: self.set_lang("auto"), self.lang_pref == "auto", auto_name)]
        for code, (name, _en) in freeai.LANGS.items():
            items.append((name, lambda c=code: self.set_lang(c), self.lang_pref == code, ""))
        self.popup(x, y, t("МОВА"), items)

    def set_lang(self, pref: str) -> None:
        old = self.lang()
        self.lang_pref = pref
        self.save_cfg()
        self.apply_lang(old)

    def apply_lang(self, old: str) -> None:
        """Switch the interface and translate everything Klodik already said into the new language."""
        new = self.lang()
        if new == old and l10n.get_lang() == new:
            return
        name = freeai.LANGS.get(new, (new,))[0]
        free = []   # bubble / chat messages holding free text to machine-translate
        if self.bubble and not self.bubble.get("src") and self.bubble.get("lang") != new:
            free.append(self.bubble)
        free += [m for m in self.chat_msgs if m.get("who") in ("bot", "note") and not m.get("src")
                 and m.get("text") and m.get("lang") != new]
        busy = {"who": "note", "text": t("перекладаю…"), "born": self.frame, "src": "перекладаю…"}
        if self.chat_open and free:
            self.chat_msgs.append(busy)
        if new in ("uk", "en", "ru"):
            l10n.set_lang(new)   # hand-written tables switch at once; only free texts wait for the API

        def work() -> None:
            ok = l10n.ensure(new, freeai.translate)
            texts = [h["text"] for h in free]
            out = freeai.translate(texts, new) if texts else texts

            def done() -> None:
                if ok:
                    l10n.set_lang(new)
                for h, txt in zip(free, out):
                    h["text"], h["lang"] = txt, new
                for m in self.chat_msgs:
                    if m.get("src"):
                        m["text"] = t(m["src"])
                if self.bubble and self.bubble.get("src"):
                    self.bubble["text"] = t(self.bubble["src"])
                if busy in self.chat_msgs:
                    self.chat_msgs.remove(busy)
                if not self.chat_open and not free:
                    self.say(t("розмовляю: ") + name, 5, "idle")
            self.root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def list_sessions(self, limit: int = 8) -> list[dict]:
        """Chats that moved in the last day, newest first."""
        out = []
        try:
            entries = list(os.scandir(SESSIONS))
        except OSError:
            return out
        for ent in entries:
            if not ent.name.endswith(".json"):
                continue
            try:
                with open(ent.path, encoding="utf-8") as f:
                    st = json.load(f)
            except (OSError, ValueError):
                continue
            if time.time() - float(st.get("ts", 0)) < 86400:
                out.append(st)
        return sorted(out, key=lambda s: s.get("ts", 0), reverse=True)[:limit]

    def session_path(self) -> str | None:
        if self.follow != "auto":
            return os.path.join(SESSIONS, self.follow + ".json")
        try:
            files = [e for e in os.scandir(SESSIONS) if e.name.endswith(".json")]
        except OSError:
            return None
        return max(files, key=lambda e: e.stat().st_mtime).path if files else None

    def read_state(self, initial: bool = False) -> None:
        path = self.session_path()
        try:
            key = (path, os.path.getmtime(path)) if path else None
        except OSError:
            return
        if not key or key == self.state_key:
            return
        self.state_key = key
        try:
            with open(path, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            return
        ts = float(st.get("ts", 0))
        same_chat = st.get("sid") == self.sid
        if same_chat and ts < self.state_ts:
            return  # an out-of-order (async) hook
        self.state_ts = ts
        self.sid = st.get("sid", "")
        self.title = st.get("title") or os.path.basename(str(st.get("cwd", "")).rstrip("\\/"))
        if st.get("cwd"):
            self.cwd = st["cwd"]
        guess = freeai.detect_lang(st.get("prompt", ""))
        if guess and guess in freeai.LANGS and guess != self.auto_lang:
            old = self.lang()
            self.auto_lang = guess
            self.save_cfg()
            if self.lang_pref == "auto":
                self.apply_lang(old)
        if initial:
            return
        m = st.get("mood", "idle")
        prev = self.mood
        self.set_mood(m)
        if m == "done":
            text = st.get("text", "")
            if text:
                summary = first_sentence(text)
                self.say(summary, 25, "done")   # instant local line, replaced by the API summary
                self.recent[self.sid] = (self.recent.get(self.sid, []) + [text[:2000]])[-3:]
                note = {"who": "note", "text": "✓ " + summary, "born": self.frame, "lang": ""}
                if self.chat_open:
                    self.chat_msgs.append(note)
                threading.Thread(target=self.summarize, args=(text, ts, note), daemon=True).start()
            else:
                self.say_t("готово!", 25, "done")
        elif m == "asking":
            if st.get("text"):
                self.say(shorten(st["text"], 90), 30, "asking")
            else:
                self.say_t("чекаю на тебе!", 30, "asking")
        elif m == "error":
            self.say_t("щось пішло не так", 15, "error")
        elif m in WORKING and prev not in WORKING and self.bubble and self.bubble["tab"] in ("done", "idle"):
            self.bubble = None  # new work started: drop the old summary

    def summarize(self, text: str, ts: float, note: dict) -> None:
        lang = self.lang()
        try:
            out = freeai.summarize(text, lang)
        except Exception as e:  # noqa: BLE001
            log(f"summary: {e!r}")
            out = None
        if not out:
            return

        def done() -> None:
            note["text"], note["lang"] = "✓ " + shorten(out, 140), lang
            if ts == self.state_ts and self.bubble and self.bubble["tab"] == "done":
                self.bubble["text"], self.bubble["lang"] = shorten(out, 140), lang
        self.root.after(0, done)

    # chat
    def open_chat(self) -> None:
        if not self.chat_open:
            self.chat_open = True
            self.bubble = None
            if not self.chat_msgs:
                src = "Питай що завгодно про проект. Я бачу, що робив Claude."
                self.chat_msgs.append({"who": "bot", "text": t(src), "src": src, "born": self.frame})
        self._set_noactivate(False)
        self.root.after(300, self.focus_entry)

    def close_chat(self) -> None:
        self.chat_open = False
        self.cv.itemconfigure(self.entry_win, state="hidden")
        self._set_noactivate(True)
        self.root.focus_set()

    def focus_entry(self) -> None:
        if self.chat_open:
            self.root.focus_force()
            self.entry.focus_force()

    def on_ask(self, _e=None) -> None:
        q = self.entry.get().strip()
        if not q or self.busy_q:
            return
        self.busy_q = True
        self.entry.delete(0, "end")
        self.chat_msgs.append({"who": "me", "text": q, "born": self.frame})
        self.chat_msgs.append({"who": "bot", "text": "", "born": self.frame, "pending": True})
        self.set_mood("thinking")
        threading.Thread(target=self.answer, args=(q,), daemon=True).start()

    def answer(self, q: str) -> None:
        lang = self.lang()
        context = (f"Chat: {self.title}\nProject folder: {self.cwd}\n"
                   + "\n\n---\n".join(self.recent.get(self.sid, [])))
        pc_state = (f"Active window: {self.active_win_title or 'Desktop'} ({self.active_cat})\n"
                    f"Media / Music: {self.active_media or 'None'}")
        action_found = None
        out = None

        # Tier 1: Check direct local intent first (instant, 100% reliable)
        try:
            handled, local_reply = pc_actions.handle_local_intent(
                q, cwd=self.cwd, active_title=self.active_win_title, active_pname=self.active_pname
            )
            if handled and local_reply:
                m = re.search(r"<!--ACTION:(.*?)-->", local_reply)
                if m:
                    action_found = m.group(1).strip()
                    local_reply = re.sub(r"<!--ACTION:.*?-->", "", local_reply).strip()
                out = local_reply
        except Exception as e:
            log(f"local_intent error: {e!r}")

        # Tier 2: FreeAI / LLM query if not a direct local action
        if not out:
            try:
                out = freeai.chat(q, context, lang, pc_state=pc_state)
                if out:
                    m = re.search(r"<!--ACTION:(.*?)-->", out)
                    if m:
                        action_found = m.group(1).strip()
                        out = re.sub(r"<!--ACTION:.*?-->", "", out).strip()
            except Exception as e:  # noqa: BLE001
                log(f"chat: {e!r}")
                out = None

        def done() -> None:
            self.busy_q = False
            self.chat_msgs = [m for m in self.chat_msgs if not m.get("pending")]
            fail = "Не вийшло відповісти: безкоштовне API не відповіло. Спробуй ще раз за хвилину."
            text = shorten(out, 600) if out else t(fail)
            self.chat_msgs.append({"who": "bot", "text": text, "born": self.frame, "lang": lang,
                                   "src": None if out else fail})
            self.chat_msgs = self.chat_msgs[-30:]
            self.set_mood("done" if out else "error")
            self.variant = "flag" if out else "shake"
            if not self.chat_open:
                self.say(shorten(text, 200), 30, "answer")
            if action_found:
                self.execute_pc_action(action_found)
        self.root.after(0, done)

    # mouse
    def on_enter(self, _e=None) -> None:
        if self.hover_job:
            self.root.after_cancel(self.hover_job)
            self.hover_job = None
        if not self.hover:
            self.hover = True
            self.last_activity = time.time()
            if self.mood == "idle" and self.frame - self.greet_frame > 60:
                self.greet_frame = self.frame   # a little wave hello
                self.show = ""

    def on_leave(self, _e=None) -> None:
        if self.hover_job:
            self.root.after_cancel(self.hover_job)
        self.hover_job = self.root.after(900, self._unhover)

    def _unhover(self) -> None:
        self.hover = False
        self.hover_job = None

    def in_mascot(self, x: float, y: float) -> bool:
        return self.mx - 10 <= x <= self.mx + 14 * P + 10 and self.my - 10 <= y <= self.my + 8 * P + 6

    def in_pill(self, x: float, y: float) -> bool:
        return self.pill_anim > 0.5 and H - 30 <= y <= H - 2 and self.mx - 40 <= x <= W - 6

    def on_press(self, e) -> None:
        self.close_menu()
        self.drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y(), False, e.x, e.y)
        self.drag_v, self.drag_lastx = 0.0, e.x_root

    def on_drag(self, e) -> None:
        if not self.drag:
            return
        sx, sy, wx, wy, moved, px0, py0 = self.drag
        if not (self.in_mascot(px0, py0) or self.in_pill(px0, py0)):
            return  # only the mascot is a drag handle
        dx, dy = e.x_root - sx, e.y_root - sy
        if moved or abs(dx) + abs(dy) > 4:
            self.drag = (sx, sy, wx, wy, True, px0, py0)
            self.root.geometry(f"+{wx + dx}+{wy + dy}")
            self.drag_v = 0.6 * self.drag_v + 0.4 * (e.x_root - self.drag_lastx)
            self.drag_lastx = e.x_root
            if time.time() - self.last_redraw > 0.016:
                # Between the 80 ms ticks the window moves but its picture doesn't, so particles that stay
                # put on screen would jump; redraw right away (without advancing the animation).
                self.root.update_idletasks()
                self.redraw(move=False)

    def on_release(self, e) -> None:
        d = self.drag
        self.drag = None
        if d and d[4]:
            self.save_cfg()
            return
        x, y = e.x, e.y
        if self.chat_open and self.chat_anim > 0.9:
            x0, y0, x1, y1 = self.chat_box()
            if x1 - 30 <= x <= x1 - 6 and y0 + 4 <= y <= y0 + 28:
                self.close_chat()
                return
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.focus_entry()
                return
        if self.in_mascot(x, y) or self.in_pill(x, y):
            if self.chat_open:
                self.close_chat()
            else:
                self.open_chat()
        elif self.bubble and self.bubble_box and self._inside(self.bubble_box, x, y):
            self.bubble = None   # click a bubble to dismiss it

    @staticmethod
    def _inside(box, x, y) -> bool:
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    # custom dark menu
    def on_menu(self, e) -> None:
        chat = t("будь-який (авто)") if self.follow == "auto" else shorten(self.title or t("вибраний"), 22)
        lang_hint = freeai.LANGS.get(self.lang(), ("?",))[0] + (" · auto" if self.lang_pref == "auto" else "")
        self.popup(e.x_root, e.y_root, t("КЛОДІК"), [
            (t("Підключити до чату…"), lambda: self.pick_chat(e.x_root, e.y_root), False, chat),
            (t("Мова…"), lambda: self.pick_lang(e.x_root, e.y_root), False, lang_hint),
            (t("Тема…"), lambda: self.pick_theme(e.x_root, e.y_root), False, t(world.THEMES[self.theme]["name"])),
            (t("Не заважати"), lambda: self.set_ghost(True), False, t("кліки проходять крізь мене; потрійний клік по мені повертає")),
            (t("Автозапуск з Windows"), self.toggle_autostart, os.path.exists(STARTUP_LNK),
             t("увімкнено") if os.path.exists(STARTUP_LNK) else t("вимкнено")),
            (t("Реакції на екран"), self.toggle_screen_react, self.screen_react,
             t("коментувати вікна та відео") if self.screen_react else t("вимкнено")),
            None,
            (t("Сховати на 15 хв"), self.snooze, False, ""), (t("Повернути в куток"), self.reset_pos, False, ""),
            (t("Очистити чат"), self.clear_chat, False, ""), None, (t("Вийти"), self.root.destroy, False, "")])

    def pick_chat(self, x: int, y: int) -> None:
        items = [(t("Будь-який чат (авто)"), lambda: self.set_follow("auto", ""), self.follow == "auto",
                  t("той, що працює останнім"))]
        for s in self.list_sessions():
            sid = s.get("sid", "")
            title = s.get("title") or t("без назви")
            folder = os.path.basename(str(s.get("cwd", "")).rstrip("\\/"))
            if folder.startswith("scratch-"):   # the app's own temp folder for chats opened with no folder
                folder = t("без папки")
            items.append((shorten(title, 34), lambda sid=sid, ti=title: self.set_follow(sid, ti), self.follow == sid,
                          f"{shorten(folder, 22)} · {ago(s.get('ts', 0))} · {t(LABEL.get(s.get('mood', ''), '')) if LABEL.get(s.get('mood', '')) else t('чекає')}"))
        if len(items) == 1:
            items.append((t("Поки немає чатів за останню добу"), lambda: None, False, t("напиши щось у Claude Code")))
        self.popup(x, y, t("ПІДКЛЮЧИТИ ДО ЧАТУ"), items)

    def set_follow(self, sid: str, title: str) -> None:
        self.follow = sid
        self.state_key = None
        self.save_cfg()
        self.read_state(initial=True)
        self.set_mood("idle")
        if sid == "auto":
            self.say_t("слідкую за всіма чатами", 6, "idle")
        else:
            self.say_t("підключився до: ", 6, "idle", shorten(title, 60))

    def popup(self, x_root: int, y_root: int, title: str, items: list) -> None:
        """Dark pixel menu. items: (label, command, is_selected, hint) or None for a divider."""
        self.close_menu()
        mw = tk.Toplevel(self.root)
        mw.overrideredirect(True)
        mw.attributes("-topmost", True)
        mw.configure(bg=C["line"])
        self.menu_win = mw
        outer = tk.Frame(mw, bg=C["bg"], padx=3, pady=3)
        outer.pack(padx=2, pady=2)
        tk.Label(outer, text=f" {title} ", bg=C["accent"], fg=C["ink"], font=self.f_tab).pack(anchor="w", pady=(0, 3))
        # Long lists scroll: the rows sit on a canvas the mouse wheel moves; short lists show whole.
        holder = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, bd=0)
        holder.pack(side="left")
        inner = tk.Frame(holder, bg=C["bg"])
        holder.create_window(0, 0, window=inner, anchor="nw")
        for it in items:
            if it is None:
                tk.Frame(inner, bg=C["line"], height=2).pack(fill="x", pady=3)
                continue
            label, cmd, selected, hint = it
            row = tk.Frame(inner, bg=C["bg"], cursor="hand2", padx=8, pady=2)
            row.pack(fill="x")
            parts = [row, tk.Label(row, text=("● " if selected else "") + label, bg=C["bg"],
                                   fg=C["accent"] if selected else C["text"], font=self.f_body, anchor="w")]
            parts[1].pack(fill="x")
            if hint:
                parts.append(tk.Label(row, text=hint, bg=C["bg"], fg=C["muted"], font=self.f_small, anchor="w"))
                parts[2].pack(fill="x")

            def paint(on: bool, ps=parts, sel=selected) -> None:
                for i, w in enumerate(ps):
                    w.configure(bg=C["accent"] if on else C["bg"])
                    if i:
                        w.configure(fg=C["ink"] if on else (C["muted"] if i == 2 else (C["accent"] if sel else C["text"])))
            for w in parts:
                w.bind("<Enter>", lambda ev, p=paint: p(True))
                w.bind("<Leave>", lambda ev, p=paint: p(False))
                w.bind("<ButtonRelease-1>", lambda ev, c=cmd: self.run_item(c))
        inner.update_idletasks()
        iw, ih = inner.winfo_reqwidth(), inner.winfo_reqheight()
        view = min(ih, 260)
        holder.configure(width=iw, height=view, scrollregion=(0, 0, iw, ih), yscrollincrement=20)
        if ih > view:
            bar = tk.Canvas(outer, width=4, height=view, bg=C["surface"], highlightthickness=0, bd=0)
            bar.pack(side="left", padx=(3, 0))
            thumb = bar.create_rectangle(0, 0, 4, view * view / ih, fill=C["accent"], outline="")

            def wheel(ev) -> None:
                holder.yview_scroll(-1 if ev.delta > 0 else 1, "units")
                top = holder.yview()[0]
                bar.coords(thumb, 0, top * view, 4, top * view + view * view / ih)
            for w in [holder, inner, *inner.winfo_children(), *(g for c in inner.winfo_children() for g in c.winfo_children())]:
                w.bind("<MouseWheel>", wheel)
        mw.update_idletasks()
        fw, fh = mw.winfo_reqwidth(), mw.winfo_reqheight()
        x, y = x_root - fw + 10, y_root - fh + 10
        self._grow_menu(mw, x, y, fw, fh, 1)
        self.menu_outside = 0   # the loop closes the menu after ~2 s with the pointer outside it
        mw.bind("<Escape>", lambda ev: self.close_menu())
        mw.focus_force()

    def _grow_menu(self, mw: tk.Toplevel, x: int, y: int, fw: int, fh: int, step: int) -> None:
        try:
            if not mw.winfo_exists():
                return
        except tk.TclError:
            return
        h = max(8, int(fh * ease_steps(step / 4, 4)))
        mw.geometry(f"{fw}x{h}+{x}+{y + fh - h}")
        if step < 4:
            self.root.after(30, lambda: self._grow_menu(mw, x, y, fw, fh, step + 1))

    def run_item(self, cmd) -> None:
        self.close_menu()
        try:
            cmd()
        except Exception as e:  # noqa: BLE001
            log(f"menu: {e!r}")

    def tick_menu(self) -> None:
        mw = self.menu_win
        if mw is None:
            return
        try:
            px, py = mw.winfo_pointerxy()
            inside = mw.winfo_rootx() <= px <= mw.winfo_rootx() + mw.winfo_width() and \
                mw.winfo_rooty() <= py <= mw.winfo_rooty() + mw.winfo_height()
        except tk.TclError:
            self.menu_win = None
            return
        self.menu_outside = 0 if inside else self.menu_outside + 1
        if self.menu_outside > 2000 // TICK:
            self.close_menu()

    def close_menu(self) -> None:
        if self.menu_win is not None:
            try:
                self.menu_win.destroy()
            except tk.TclError:
                pass
            self.menu_win = None

    def snooze(self) -> None:
        self.hidden_until = time.time() + 15 * 60
        self.root.withdraw()

    def reset_pos(self) -> None:
        l, t, r, b = work_area()
        self.root.geometry(f"+{r - W - 6}+{b - H + 4}")
        self.save_cfg()

    def clear_chat(self) -> None:
        self.chat_msgs = []

    # drawing primitives
    def px(self, gx, gy, color, w=1, h=1, size=P, ox=0, oy=0) -> None:
        x0 = ox + gx * size
        y0 = oy + gy * size
        self.cv.create_rectangle(x0, y0, x0 + w * size, y0 + h * size, fill=color, outline=color, tags="d")

    def rect(self, x0, y0, x1, y1, color) -> None:
        self.cv.create_rectangle(x0, y0, x1, y1, fill=color, outline=color, tags="d")

    def stepped(self, x0, y0, x1, y1, fill, s=STEP) -> None:
        pts = [x0 + 2 * s, y0, x1 - 2 * s, y0, x1 - 2 * s, y0 + s, x1 - s, y0 + s, x1 - s, y0 + 2 * s, x1, y0 + 2 * s,
               x1, y1 - 2 * s, x1 - s, y1 - 2 * s, x1 - s, y1 - s, x1 - 2 * s, y1 - s, x1 - 2 * s, y1,
               x0 + 2 * s, y1, x0 + 2 * s, y1 - s, x0 + s, y1 - s, x0 + s, y1 - 2 * s, x0, y1 - 2 * s,
               x0, y0 + 2 * s, x0 + s, y0 + 2 * s, x0 + s, y0 + s, x0 + 2 * s, y0 + s]
        self.cv.create_polygon(pts, fill=fill, outline=fill, tags="d")

    def cartridge(self, x0, y0, x1, y1, tab: str | None, tail_x: float | None) -> None:
        """The signature window: stepped pixel frame, highlight row, orange label tab, stair tail."""
        if x1 - x0 < 16 or y1 - y0 < 12:
            return
        self.stepped(x0 + 4, y0 + 4, x1 + 4, y1 + 4, C["shadow"])            # hard pixel shadow
        if tail_x is not None:
            for i, w in enumerate((10, 7, 4)):
                self.rect(tail_x - w + 4, y1 + i * 3 + 4, tail_x + w + 4, y1 + i * 3 + 7, C["shadow"])
        self.stepped(x0, y0, x1, y1, C["line"])
        self.stepped(x0 + 2, y0 + 2, x1 - 2, y1 - 2, C["bg"])
        self.rect(x0 + 2 * STEP + 2, y0 + 2, x1 - 2 * STEP - 2, y0 + 4, C["line_hi"])
        if tail_x is not None:
            for i, w in enumerate((10, 7, 4)):
                self.rect(tail_x - w, y1 - 2 + i * 3, tail_x + w, y1 + 1 + i * 3, C["line"])
                self.rect(tail_x - w + 2, y1 - 3 + i * 3, tail_x + w - 2, y1 - 1 + i * 3, C["bg"])
        if tab and x1 - x0 > 60:
            tw = self.f_tab.measure(tab) + 14
            self.rect(x0 + 10, y0 - 7, x0 + 10 + tw, y0 + 8, C["accent"])
            self.rect(x0 + 10, y0 + 6, x0 + 10 + tw, y0 + 8, C["accent_dk"])
            self.cv.create_text(x0 + 17, y0, text=tab, anchor="w", fill=C["ink"], font=self.f_tab, tags="d")

    def wrap(self, text: str, font: tkfont.Font, width: int) -> list[str]:
        lines: list[str] = []
        for para in text.split("\n"):
            cur = ""
            for word in para.split(" "):
                trial = (cur + " " + word).strip()
                if font.measure(trial) <= width:
                    cur = trial
                    continue
                if cur:
                    lines.append(cur)
                while font.measure(word) > width and len(word) > 1:  # hard-break long tokens
                    cut = len(word)
                    while cut > 1 and font.measure(word[:cut]) > width:
                        cut -= 1
                    lines.append(word[:cut])
                    word = word[cut:]
                cur = word
            lines.append(cur)
        return lines

    def typed(self, lines: list[str], born: int, speed: float = 3.2) -> tuple[list[str], bool]:
        """Typewriter: the part of the wrapped text that is visible this frame."""
        total = sum(len(s) for s in lines)
        n = int((self.frame - born) * speed)
        if n >= total or not MOTION:
            return lines, True
        out, left = [], n
        for s in lines:
            if left <= 0:
                break
            out.append(s[:left])
            left -= len(s)
        return out or [""], False

    # mascot
    def pose(self) -> dict:
        """Body language for this frame: offsets, arms, legs, eyes, mouth + which prop to draw."""
        m, f, v = self.mood, self.mood_frame, self.variant
        p = {"dx": 0.0, "dy": 0.0, "sq": 0.0, "arms": "down", "legs": "stand", "eyes": "normal",
             "look": self.look_at_cursor(), "mouth": None, "prop": v, "body": ORANGE}

        if self.drag and self.drag[4]:   # picked up: kicks, flails and leans against the pull
            fr = self.frame
            p.update(legs="run", arms="pump", eyes="wide" if (fr // 5) % 3 else "x", mouth="o", prop="struggle",
                     dx=max(-1.0, min(1.0, -self.drag_v / 10)) + [-0.2, 0.2][fr % 2], dy=-(fr % 2) * 0.4)
            return p

        if self.intro:                    # changing clothes, putting things on or picking them up
            k, f, n = self.intro["kind"], self.intro["f"], self.intro["len"]
            p["prop"] = ""
            if k == "dress" and f < 8:
                p.update(dx=[0.5, -0.5][f % 2], eyes="back" if f % 2 else "happy")
            elif k in ("pad_on", "pad_off"):
                p.update(arms="hold" if k == "pad_on" else "down", look=(0, 0.9), sq=0.2 if k == "pad_on" and f < 8 else 0)
            else:
                p.update(arms="up", look=(0, -0.9), eyes="happy" if f > n - 6 else "normal")
            return p

        if m == "idle":
            p["dy"] = [0, 0, 0, 0.25, 0.25, 0.25][(self.frame // 6) % 6]  # breathing
            idle_for = time.time() - self.last_activity
            fr = self.frame
            if self.show:
                self.apply_show(p)
            elif idle_for > 300 and not self.hover and not (self.devices.music or self.media_active):
                p.update(sq=0.35, eyes="closed", prop="sleep", dy=0, legs="sit")
            elif fr - self.greet_frame < 22 and self.theme == "sakura":
                depth = min(1.0, (fr - self.greet_frame) / 6)
                p.update(sq=0.45 * depth, dy=0.4 * depth, eyes="closed", prop="ojigi")
            elif fr - self.greet_frame < 22:
                p.update(arms="wave_r", eyes="happy", prop="hi", dy=-0.5 if fr - self.greet_frame < 4 else 0)
            elif self.devices.music or self.media_active:     # listening: an easy sway on the beat
                p.update(dx=math.sin(fr / 8) * 0.35, dy=-0.3 if (fr // 4) % 2 else 0, prop="groove",
                         eyes="closed" if (fr // 32) % 2 else "happy", arms="out" if (fr // 8) % 2 else "down")
            elif self.pad_held:
                p.update(arms="hold", look=(0, 0.7), prop="pad")
            else:
                p["prop"] = ""
            if self.frame % 53 in (0, 1) and p["eyes"] == "normal":
                p["eyes"] = "closed"   # blink
            return p

        if m == "thinking":
            p["dy"] = -[0, 0, 0.25, 0.25][(f // 3) % 4]
            p["look"] = (0.3, -0.6)
            if v == "tap":
                p.update(legs="tap", arms="chin")
        elif m == "reading":
            p["look"] = ([-0.5, -0.2, 0.2, 0.5, 0.2, -0.2][(f // 4) % 6], 0.5)
            p["arms"] = "hold"
            if v == "glasses":
                p.update(arms="down", eyes="glasses")
        elif m == "writing":
            p["dy"] = -(f % 2) * 0.25
            p["eyes"] = "squint"
            p["arms"] = "type" if v == "keyboard" else ("hammer" if v == "hammer" else "hold")
        elif m == "running":
            if v == "sprint":
                p.update(legs="run", arms="pump", dy=-(f % 2) * 0.5, eyes="wide")
            else:
                p.update(legs="walk", dy=-(f % 2) * 0.25)
        elif m == "searching":
            sh = [-0.6, -0.2, 0.2, 0.6, 0.2, -0.2][(f // 3) % 6]
            p["look"] = (sh, -0.2)
            p["dx"] = sh * 0.3
            if v == "binoculars":
                p.update(eyes="binoculars", arms="up_close")
        elif m == "web":
            p["legs"] = "walk" if v == "surf" else "stand"
            p["look"] = (0.4, -0.5)
            p["dy"] = -[0, 0.25][(f // 3) % 2]
            if v == "surf":
                p["dx"] = math.sin(f / 5) * 0.4
                p["arms"] = "out"
        elif m == "agent":
            p["legs"] = "walk"
            p["arms"] = "hold" if v == "walkie" else "wave_r"
        elif m == "asking":
            p["eyes"] = "wide"
            p["dy"] = -[0, 0, 0.5, 0.5][(f // 3) % 4]
            p["arms"] = "sign" if v == "sign" else ("wave_both" if (f // 4) % 2 else "down")
            p["mouth"] = "o"
        elif m == "done" and v == "bow":   # sakura theme: a polite bow when work is finished
            depth = min(1.0, f / 6) if f < 30 else max(0.0, (40 - f) / 10)
            p.update(sq=0.5 * depth, dy=0.4 * depth, eyes="closed", prop="ojigi")
        elif m == "done":
            if v == "spin" and f < 24:
                p["dx"] = [0, 0.5, 0, -0.5][(f // 2) % 4]
                p["eyes"] = ["happy", "back", "happy", "back"][(f // 2) % 4]
            elif v == "hearts":
                p["eyes"] = "heart"
            else:
                p["eyes"] = "happy"
            p["dy"] = -[0, 1, 2, 2.4, 2, 1, 0, 0][f % 8] if f < 24 else 0
            p["arms"] = "up" if f < 30 else "down"
            p["mouth"] = "smile"
        elif m == "error":
            p["body"] = ORANGE_DARK
            p["eyes"] = "x"
            if v == "flat":
                p.update(sq=0.5 if f > 6 else f / 12, legs="sit", dy=0)
            elif f < 20:
                p["dx"] = [-0.4, 0.4][f % 2]
        return p

    def apply_show(self, p: dict) -> None:
        s, f = self.show, self.show_frame
        p["prop"] = s
        if s in world.THEME_SHOWS.get(self.theme, {}):
            world.theme_pose(s, f, p)
        elif s == "look":
            p["look"] = (-0.7, 0) if f < 14 else ((0.7, 0) if f < 28 else (0, -0.5))
        elif s == "yawn":
            mid = 6 < f < 24
            p.update(eyes="closed", mouth="yawn" if mid else None, sq=-0.25 if mid else 0, arms="up" if 8 < f < 22 else "down")
        elif s == "stretch":
            p.update(arms="up", dy=-0.5, sq=-0.3, eyes="closed" if f < 18 else "normal")
        elif s == "dance":
            p.update(dx=[-0.5, 0, 0.5, 0][(f // 3) % 4], arms="wave_both" if (f // 3) % 2 else "up", legs="walk", eyes="happy")
        elif s == "juggle":
            p.update(arms="juggle", look=(0, -0.8))
        elif s == "bug":
            bx, by = self.bug_pos(f)
            cx, cy = self.mx + 7 * P, self.my + 2 * P
            dx, dy = bx - cx, by - cy
            d = max(1.0, math.hypot(dx, dy))
            p["look"] = (dx / d * 0.7, dy / d * 0.7)
            if f > 66:
                p.update(dy=-1.5 if f < 72 else 0, arms="up", eyes="happy")
        elif s == "cookie":
            p.update(arms="hold_mouth", mouth="o" if (f // 4) % 2 else None, eyes="happy" if f > 30 else "normal")
        elif s == "kick":
            p.update(legs="kick", sq=0.2)
        elif s == "sneeze":
            if f < 14:
                p.update(eyes="squint", sq=-0.15 * (f / 14))
            else:
                p.update(eyes="closed", dx=0.6 if f < 18 else 0, sq=0.15, mouth="o")
        elif s == "yoyo":
            p["arms"] = "yoyo"
        elif s == "game":
            p.update(arms="hold", look=(0, 0.7))
        elif s == "blow":
            p.update(mouth="o", look=(0.5, -0.5), sq=-0.1 if f < 16 else 0)

    def look_at_cursor(self) -> tuple[float, float]:
        try:
            x, y = self.root.winfo_pointerxy()
            cx = self.root.winfo_rootx() + self.mx + 7 * P
            cy = self.root.winfo_rooty() + self.my + 2 * P
        except tk.TclError:
            return 0.0, 0.0
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d < 8:
            return 0.0, 0.0
        k = min(1.0, d / 300) * 0.6
        return dx / d * k, dy / d * k

    def bug_pos(self, f: int) -> tuple[float, float]:
        t = f / 9
        return (self.mx + 7 * P + math.sin(t * 1.3) * 90 - 20, self.my - 40 + math.sin(t * 2.1) * 30)

    def draw_mascot(self) -> None:
        p = self.pose()
        f = self.frame
        ox = self.mx + p["dx"] * P
        oy = self.my + p["dy"] * P
        top = p["sq"]                     # squash: body top moves down (negative = taller)
        body = p["body"]

        lift = max(0.0, -p["dy"])         # shadow shrinks while airborne
        sw = 6 * P - lift * 6
        cx = self.mx + 7 * P
        self.cv.create_oval(cx - sw, self.my + 8 * P + 4, cx + sw, self.my + 8 * P + 12,
                            fill=C["shadow"], outline=C["shadow"], tags="d")

        prop = p["prop"]
        self.draw_prop_back(prop, ox, oy)

        self.px(2, top, body, 10, 6 - top, ox=ox, oy=oy)              # body
        a = p["arms"]
        al = ar = 2.0
        if a == "up":
            al = ar = -0.5
        elif a == "wave_r":
            ar = [-0.5, 0.5][(f // 3) % 2]
        elif a == "wave_both":
            al, ar = ([-0.5, 1.5] if (f // 3) % 2 else [1.5, -0.5])
        elif a == "pump":
            al, ar = ([1, 3] if f % 2 else [3, 1])
        elif a == "type":
            al, ar = 3, 3 - (f % 2)
        elif a == "hammer":
            al, ar = 3, [0, 1, 3][f % 3]
        elif a == "juggle":
            al, ar = ([0.5, 2] if (f // 4) % 2 else [2, 0.5])
        elif a == "out":
            al, ar = 1, 1
        if a in ("hold", "hold_mouth", "chin", "sign", "up_close", "yoyo"):
            y_in = {"hold": 3, "hold_mouth": 2.5, "chin": 3, "sign": 1, "up_close": 1.2, "yoyo": 2}[a]
            self.px(1, y_in, body, 2, 2, ox=ox, oy=oy)
            self.px(11, y_in if a != "chin" else 2, body, 2, 2, ox=ox, oy=oy)
        else:
            self.px(0, al + top * 0.5, body, 2, 2, ox=ox, oy=oy)
            self.px(12, ar + top * 0.5, body, 2, 2, ox=ox, oy=oy)
        lg = p["legs"]
        for i, lx in enumerate((3, 5, 8, 10)):
            h = 2.0
            if lg == "walk":
                h = 1 if (i + f // 2) % 2 == 0 else 2
            elif lg == "run":
                h = 1 if (i + f) % 2 == 0 else 2
            elif lg == "sit":
                h = 1
            elif lg == "tap" and i == 3:
                h = 1 if (f // 3) % 2 else 2
            elif lg == "kick":
                h = 1
                if i in (0, 3) and ((f // 4) % 2 == (0 if i == 0 else 1)):
                    self.px(lx + (-1 if i == 0 else 1), 6.5, body, 1, 1, ox=ox, oy=oy)
                    continue
            self.px(lx, 6, body, 1, h, ox=ox, oy=oy)

        self.draw_eyes(p, ox, oy, top)
        mo = p["mouth"]
        if mo == "o":
            self.px(6.5, 4 + top * 0.4, INK, 1, 1, ox=ox, oy=oy)
        elif mo == "yawn":
            self.px(6, 3.5, INK, 2, 1.5, ox=ox, oy=oy)
            self.px(6.3, 4.3, "#e86b7a", 1.4, 0.6, ox=ox, oy=oy)
        elif mo == "smile":
            self.px(6, 4, INK, 2, 0.5, ox=ox, oy=oy)
            self.px(5.5, 3.5, INK, 0.5, 0.5, ox=ox, oy=oy)
            self.px(8, 3.5, INK, 0.5, 0.5, ox=ox, oy=oy)

        it = self.intro
        drop = 0.0
        if it and it["kind"] == "dress":
            drop = 7.0 if it["f"] < 8 else 7.0 * (1 - (it["f"] - 8) / (it["len"] - 8))
        elif it and it["kind"] == "undress":
            drop = 8.0 * it["f"] / it["len"]
        world.draw_costume(self, p, ox, oy, top, self.weather, time.time() - self.last_activity, self.costume_theme, drop)
        gear = {"gadget": 0.0} if self.devices.dev["gadget"] else {}
        if self.worn_phones or (it and it["kind"] in ("phones_on", "phones_off")):
            gear["headphones"] = self.intro_lift("phones_on", "phones_off", 6.0)
        world.draw_gear(self, gear, self.devices.music or self.media_active, ox, oy, top)
        if it and it["kind"] in ("pad_on", "pad_off"):
            world.draw_pad(self, ox, oy, light=False, lift=self.intro_lift("pad_on", "pad_off", 4.0))
        elif prop == "pad":
            world.draw_pad(self, ox, oy, light=True)
        elif prop in world.THEME_SHOWS.get(self.theme, {}):
            world.theme_prop(self, prop, self.show_frame, ox, oy)
        if self.ghost:   # a little ghost by his feet says clicks pass through
            gx, gy = self.mx - 6, self.my + 6 * P
            self.rect(gx, gy, gx + 12, gy + 12, "#eef0f5")
            for k in range(3):
                self.rect(gx + k * 4, gy + 12, gx + k * 4 + 2, gy + 14, "#eef0f5")
            self.rect(gx + 3, gy + 4, gx + 5, gy + 7, INK)
            self.rect(gx + 7, gy + 4, gx + 9, gy + 7, INK)
        if prop == "struggle":
            for i in range(2):   # sweat drops fly off
                k = (self.frame * 2 + i * 7) % 14
                self.rect(ox + (1 if i else 13) * P + (-k if i else k), oy - 4 + k, ox + (1 if i else 13) * P + (-k if i else k) + 3,
                          oy + k, C["sky"])
            if (self.frame // 6) % 2:
                self.cv.create_text(ox - 20, oy - 12, text=t("пусти!"), fill=C["text"], font=self.f_tab, tags="d")
        elif prop == "groove":
            for i in range(2):
                y = oy - 10 - ((self.frame * 1.5 + i * 18) % 36)
                self.cv.create_text(ox + (13 if i else 1) * P, y, text="♪" if i else "♫", fill=C["gold"],
                                    font=self.f_big, tags="d")
        elif prop == "ojigi":
            word = "お疲れさま" if self.mood == "done" else "こんにちは"   # "good work" / "hello", kept in Japanese on purpose
            self.cv.create_text(ox + 7 * P, oy - 18, text=word, fill=C["muted"], font=self.f_small, tags="d")
        self.draw_prop_front(prop, ox, oy)

    def draw_eyes(self, p: dict, ox: float, oy: float, top: float) -> None:
        e = p["eyes"]
        lx, ly = p["look"]
        ey = 1 + top * 0.6
        if e == "happy":
            for x in (3, 8):
                self.px(x, ey + 1, INK, ox=ox, oy=oy); self.px(x + 1, ey, INK, ox=ox, oy=oy); self.px(x + 2, ey + 1, INK, ox=ox, oy=oy)
        elif e == "x":
            for x in (3, 8):
                for gx, gy in ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)):
                    self.px(x + gx, ey + gy - 0.3, INK, 1, 0.8, ox=ox, oy=oy)
        elif e == "closed":
            self.px(3.5, ey + 1.3, INK, 2, 0.5, ox=ox, oy=oy); self.px(8.5, ey + 1.3, INK, 2, 0.5, ox=ox, oy=oy)
        elif e == "squint":
            self.px(3.5, ey + 1 + ly * 0.3, INK, 2, 0.6, ox=ox, oy=oy); self.px(8.5, ey + 1 + ly * 0.3, INK, 2, 0.6, ox=ox, oy=oy)
        elif e == "wide":
            for x in (3.5, 8.5):
                self.px(x, ey - 0.2, "#fff4ea", 1.6, 2.2, ox=ox, oy=oy)
                self.px(x + 0.3 + lx * 0.4, ey + 0.4 + ly * 0.4, INK, 1, 1.2, ox=ox, oy=oy)
        elif e == "heart":
            for x in (3, 8):
                for gx, gy in ((0, 0), (2, 0), (0, 0.6), (1, 0.6), (2, 0.6), (0.5, 1.2), (1.5, 1.2), (1, 1.8)):
                    self.px(x + gx * 0.9, ey + gy - 0.2, C["rose"], 0.9, 0.7, ox=ox, oy=oy)
        elif e == "back":
            pass  # turned away mid-spin
        elif e == "glasses":
            for x in (3, 8):
                self.cv.create_rectangle(ox + x * P - 2, oy + ey * P - 2, ox + (x + 3) * P + 2, oy + (ey + 2) * P + 2,
                                         outline=INK, width=2, tags="d")
                self.px(x + 1 + lx * 0.6, ey + 0.5, INK, 1, 1.2, ox=ox, oy=oy)
            self.px(6, ey + 0.7, INK, 2, 0.3, ox=ox, oy=oy)
        elif e == "binoculars":
            for x in (3, 8):
                self.px(x - 0.5, ey - 0.6, "#3a3a3a", 3, 3, ox=ox, oy=oy)
                self.px(x, ey - 0.1, C["sky"], 2, 2, ox=ox, oy=oy)
        else:  # normal, following the gaze
            self.px(4 + lx, ey + ly * 0.6, INK, 1, 2, ox=ox, oy=oy)
            self.px(9 + lx, ey + ly * 0.6, INK, 1, 2, ox=ox, oy=oy)

    # props
    def draw_prop_back(self, prop: str, ox: float, oy: float) -> None:
        f = self.mood_frame if self.mood != "idle" else self.show_frame
        if prop == "radar":
            cx, cy = ox + 7 * P, oy + 3 * P
            r = 30 + (f * 6) % 60
            self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=C["mint"], width=2, tags="d")
        elif prop == "confetti":
            rnd = random.Random(self.mood_since)
            for _ in range(26):
                x0 = rnd.uniform(-20, 14 * P + 20)   # close around him, not across the whole window
                spd = rnd.uniform(3, 7)
                y = (rnd.uniform(-80, -30) + f * spd) % 120 - 70
                col = rnd.choice([C["gold"], C["accent"], C["mint"], C["sky"], C["rose"]])
                self.rect(ox + x0, oy + y, ox + x0 + 5, oy + y + 5, col)

    def draw_prop_front(self, prop: str, ox: float, oy: float) -> None:
        idle = self.mood == "idle"
        f = self.show_frame if idle else self.mood_frame
        s = 4
        hx, hy = ox + 12 * P, oy - 26     # above-right of the head
        if prop == "dots":
            for i in range(3):
                if (f // 3) % 4 > i:
                    self.px(i * 2, 2, C["muted"], size=s, ox=hx - 8, oy=hy)
        elif prop == "bulb":
            on = (f // 2) % 7 not in (0, 3)
            col = C["gold"] if on else "#6a5a3a"
            for gx, gy in ((1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (0, 2), (1, 2), (2, 2), (3, 2), (4, 2),
                           (1, 3), (2, 3), (3, 3)):
                self.px(gx, gy, col, size=s, ox=hx - 4, oy=hy - 10)
            self.px(1.5, 4, "#9a9a9a", 2, 1, size=s, ox=hx - 4, oy=hy - 10)
            if on:
                for gx, gy in ((-2, 1), (6, 1), (2, -2)):
                    self.px(gx, gy, C["gold"], size=s, ox=hx - 4, oy=hy - 10)
        elif prop == "gears":
            for k, (gx, gy, r) in enumerate(((hx, hy, 9), (hx + 16, hy - 8, 6))):
                ang = (f / 3) * (1 if k == 0 else -1.5)
                for i in range(6):
                    a = ang + i * math.pi / 3
                    tx, ty = gx + math.cos(a) * (r + 3), gy + math.sin(a) * (r + 3)
                    self.rect(tx - 2, ty - 2, tx + 2, ty + 2, C["muted"])
                self.cv.create_oval(gx - r, gy - r, gx + r, gy + r, fill=C["muted"], outline=C["muted"], tags="d")
                self.cv.create_oval(gx - 3, gy - 3, gx + 3, gy + 3, fill=C["bg"], outline=C["bg"], tags="d")
        elif prop == "tap":
            if (f // 6) % 2:
                self.cv.create_text(hx, hy + 4, text=t("хм…"), fill=C["muted"], font=self.f_mono, tags="d")
        elif prop == "book":
            bx, by = ox + 3 * P, oy + 3.6 * P
            self.rect(bx, by, bx + 8 * P, by + 3 * P, "#f4efe6")
            self.cv.create_rectangle(bx, by, bx + 8 * P, by + 3 * P, outline="#7a5a40", width=2, tags="d")
            self.rect(bx + 4 * P - 1, by, bx + 4 * P + 1, by + 3 * P, "#7a5a40")
            flip = (f // 10) % 2
            for i in range(2):
                yy = by + 7 + i * 7
                self.rect(bx + 5, yy, bx + 4 * P - 5, yy + 1, "#b9a58f")
                self.rect(bx + 4 * P + 5, yy, bx + 8 * P - 5 - (12 if flip else 0), yy + 1, "#b9a58f")
        elif prop == "scroll":
            bx, by = ox + 2.5 * P, oy + 3.2 * P
            ln = 2 + (f % 24) / 6
            self.rect(bx, by, bx + 9 * P, by + ln * P, "#efe2c4")
            for i in range(int(ln * 2)):
                self.rect(bx + 6, by + 5 + i * 5, bx + 9 * P - 6 - (i * 13) % 20, by + 6 + i * 5, "#b39a72")
            self.rect(bx - 3, by - 3, bx + 9 * P + 3, by + 3, "#9a7a50")
            self.rect(bx - 3, by + ln * P - 3, bx + 9 * P + 3, by + ln * P + 3, "#9a7a50")
        elif prop == "pencil":
            wob = (f % 2) * 2
            px0, py0 = ox + 14 * P - 4 + wob, oy + 3.5 * P
            for i in range(5):
                self.px(-i, i, C["gold"], size=s, ox=px0, oy=py0)
            self.px(1, -1, C["rose"], size=s, ox=px0, oy=py0)
            self.px(-5, 5, INK, size=s, ox=px0, oy=py0)
            for i in range(f % 8):
                self.rect(px0 - 22 - i * 5, py0 + 26, px0 - 19 - i * 5, py0 + 27, C["muted"])
        elif prop == "keyboard":
            kx, ky = ox + 1 * P, oy + 5.2 * P
            self.rect(kx, ky, kx + 12 * P, ky + 2 * P, "#2b2b2b")
            for r in range(2):
                for c in range(10):
                    lit = (c + r * 3 + f) % 7 == 0
                    self.rect(kx + 4 + c * 9, ky + 3 + r * 7, kx + 10 + c * 9, ky + 8 + r * 7, C["accent"] if lit else "#555")
        elif prop == "hammer":
            ph = f % 3
            hx0, hy0 = ox + 13 * P, oy + (0 if ph == 0 else (P if ph == 1 else 3 * P))
            self.rect(hx0, hy0, hx0 + 4, hy0 + 26, "#8a6a40")
            self.rect(hx0 - 8, hy0 - 4, hx0 + 12, hy0 + 6, "#9aa0a6")
            if ph == 2:
                for gx, gy in ((-10, 30), (14, 28), (2, 36)):
                    self.rect(hx0 + gx, hy0 + gy, hx0 + gx + 4, hy0 + gy + 4, C["gold"])
        elif prop == "terminal":
            self.rect(hx - 6, hy - 8, hx + 36, hy + 18, "#0d0d0d")
            self.cv.create_rectangle(hx - 6, hy - 8, hx + 36, hy + 18, outline=C["line"], width=2, tags="d")
            self.cv.create_text(hx, hy + 5, text=">_" if f % 6 < 3 else ">", fill=C["mint"], anchor="w",
                                font=self.f_mono, tags="d")
        elif prop == "sprint":
            for i in range(3):
                y = oy + (2 + i * 1.5) * P
                x = ox - 10 - ((f * 6 + i * 11) % 30)
                self.rect(x, y, x + 16, y + 2, C["muted"])
        elif prop == "progress":   # a pixel progress bar filling while the command runs
            self.rect(hx - 30, hy - 2, hx + 30, hy + 10, C["line"])
            self.rect(hx - 28, hy, hx + 28, hy + 8, C["bg"])
            for i in range((f // 2) % 15):
                self.rect(hx - 27 + i * 4, hy + 1, hx - 25 + i * 4, hy + 7, C["mint"])
        elif prop == "magnifier":
            k = [0, 1, 2, 1][(f // 3) % 4]
            gx0 = hx - 8 + k * s
            for gx, gy in ((1, 0), (2, 0), (0, 1), (3, 1), (0, 2), (3, 2), (1, 3), (2, 3), (4, 4), (5, 5)):
                self.px(gx, gy, "#cfcfcf", size=s, ox=gx0, oy=hy - 4)
            self.px(1, 1, C["sky"], 2, 2, size=s, ox=gx0, oy=hy - 4)
        elif prop == "radar":
            if (f // 3) % 2:
                self.rect(hx, hy, hx + 5, hy + 5, C["mint"])
        elif prop == "globe":
            k = f % 8
            self.cv.create_oval(hx - 2, hy - 8, hx + 22, hy + 16, fill="#3f8fe0", outline="#2a6aa8", width=2, tags="d")
            xx = hx - 2 + (k * 3) % 24
            self.rect(xx, hy - 6, xx + 2, hy + 14, "#2a6aa8")
            self.rect(hx - 2, hy + 3, hx + 22, hy + 5, "#2a6aa8")
            self.rect(hx + 6, hy - 2, hx + 12, hy + 3, C["mint"])
        elif prop == "antenna":
            ax, ay = ox + 7 * P, oy - 3 * P
            self.rect(ax - 1, ay, ax + 1, oy, C["muted"])
            self.rect(ax - 3, ay - 3, ax + 3, ay + 3, C["rose"])
            for i in range(3):
                if (f // 2) % 4 > i:
                    r = 8 + i * 7
                    self.cv.create_arc(ax - r, ay - r, ax + r, ay + r, start=30, extent=120, style="arc",
                                       outline=C["sky"], width=2, tags="d")
        elif prop == "surf":
            for i in range(12):
                y = oy + 8 * P + 6 + math.sin((i + f) / 2) * 3
                self.rect(ox - 10 + i * 12, y, ox + i * 12, y + 4, C["sky"])
        elif prop == "minis":
            for j, bx in enumerate((ox - 9 * 3, ox - 19 * 3)):
                by = oy + 8 * P - 6 * 3 - (((f // 2) + j) % 2) * 3
                self.px(1, 0, ORANGE, 5, 3, size=3, ox=bx, oy=by)
                for lx in (1.5, 4.5):
                    self.px(lx, 3, ORANGE, 1, 1, size=3, ox=bx, oy=by)
                self.px(2, 1, INK, size=3, ox=bx, oy=by); self.px(4, 1, INK, size=3, ox=bx, oy=by)
        elif prop == "walkie":
            wx, wy = ox + 12 * P, oy + 1 * P
            self.rect(wx, wy, wx + 10, wy + 20, "#333")
            self.rect(wx + 6, wy - 8, wx + 8, wy, "#333")
            if (f // 3) % 2:
                self.cv.create_text(wx + 14, wy - 10, text=t("пш-ш"), fill=C["muted"], anchor="w", font=self.f_mono, tags="d")
        elif prop == "question":
            if (f // 4) % 2 == 0:
                for gx, gy in ((1, 0), (2, 0), (3, 1), (2, 2), (2, 4)):
                    self.px(gx, gy, C["gold"], size=s, ox=hx, oy=hy - 8)
        elif prop == "sign":
            sx, sy = ox + 1.5 * P, oy - 3.2 * P
            self.rect(sx + 5 * P - 2, sy + 2 * P, sx + 5 * P + 2, oy + 2 * P, "#8a6a40")
            self.rect(sx, sy, sx + 10 * P, sy + 2.4 * P, "#f4efe6")
            self.cv.create_rectangle(sx, sy, sx + 10 * P, sy + 2.4 * P, outline="#7a5a40", width=2, tags="d")
            self.cv.create_text(sx + 5 * P, sy + 1.2 * P, text=t("ТВІЙ ХІД?"), fill=INK, font=self.f_tab, tags="d")
        elif prop == "flag":       # a finish-line flag planted next to him, waving
            fx, fy = ox - 5 * P, oy - 2 * P
            self.rect(fx, fy, fx + 3, oy + 8 * P, C["muted"])
            wave = (f // 3) % 2
            for r in range(3):
                for c in range(4):
                    col = C["text"] if (r + c) % 2 == 0 else C["ink"]
                    self.rect(fx + 3 + c * 6, fy + r * 6 + (wave if c % 2 else 0),
                              fx + 9 + c * 6, fy + 6 + r * 6 + (wave if c % 2 else 0), col)
        elif prop == "hearts" and f < 70:
            for i in range(3):
                y = hy + 10 - ((f * 2 + i * 14) % 44)
                x = hx - 30 + i * 18 + math.sin((f + i * 5) / 3) * 4
                for gx, gy in ((0, 0), (2, 0), (0, 1), (1, 1), (2, 1), (1, 2)):
                    self.px(gx, gy, C["rose"], size=3, ox=x, oy=y)
        elif prop == "smoke":
            for i in range(3):
                age = (f + i * 6) % 18
                r = 4 + age * 0.6
                x, y = ox + 7 * P + math.sin(age / 2 + i) * 6, oy - 4 - age * 2
                self.cv.create_oval(x - r, y - r, x + r, y + r, fill="#4a4a4a", outline="#4a4a4a", tags="d")
        elif prop in ("shake", "flat"):
            self.px(0, (f % 6) * 0.5, C["sky"], 1, 2, size=s, ox=hx, oy=hy + 10)
        # idle shows
        elif prop == "sleep":
            k = (self.frame // 6) % 3
            for i in range(2):
                kk = (k + i) % 3
                sz = 3 + i
                for gx, gy in ((0, 0), (1, 0), (2, 0), (1, 1), (0, 2), (1, 2), (2, 2)):
                    self.px(gx + kk * 1.5, gy - kk * 2.5, C["muted"], size=sz, ox=hx - i * 14, oy=hy + 14 - i * 10)
        elif prop == "hi":
            self.cv.create_text(hx + 6, hy + 2, text="!", fill=C["gold"], font=self.f_big, tags="d")
        elif prop == "dance":
            for i in range(2):
                y = hy - ((f * 2 + i * 16) % 30)
                x = hx - 20 + i * 22
                self.cv.create_text(x, y, text="♪" if i else "♫", fill=C["gold"], font=self.f_big, tags="d")
        elif prop == "juggle":
            for i in range(3):
                ang = (f / 5 + i * 2.1) % 6.28
                x = ox + 7 * P + math.cos(ang) * 46
                y = oy - 10 - abs(math.sin(ang)) * 40
                self.cv.create_oval(x - 5, y - 5, x + 5, y + 5, fill=[C["gold"], C["sky"], C["rose"]][i],
                                    outline=C["ink"], tags="d")
        elif prop == "bug":
            bx, by = self.bug_pos(f)
            wing = (f // 2) % 2
            self.rect(bx - 1, by - 3, bx + 1, by + 3, C["ink"])
            col = C["sky"] if f < 66 else C["gold"]
            self.rect(bx - 7, by - (6 if wing else 2), bx - 1, by + (0 if wing else 2), col)
            self.rect(bx + 1, by - (6 if wing else 2), bx + 7, by + (0 if wing else 2), col)
        elif prop == "cookie":
            r = max(0, 9 - f // 6)
            cx, cy = ox + 7 * P, oy + 3.4 * P
            if r > 0:
                self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#c98a4b", outline="#8a5a2b", width=2, tags="d")
                self.rect(cx - 2, cy - 2, cx + 1, cy + 1, "#4a2a14")
            for i in range(min(5, f // 8)):
                self.rect(cx - 12 + i * 6, oy + 8 * P + 2, cx - 9 + i * 6, oy + 8 * P + 5, "#c98a4b")
        elif prop == "yoyo":
            ax, ay = ox + 13 * P, oy + 3 * P
            ln = abs(math.sin(f / 6)) * 50
            self.rect(ax, ay, ax + 1, ay + ln, C["muted"])
            self.cv.create_oval(ax - 6, ay + ln - 6, ax + 7, ay + ln + 7, fill=C["rose"], outline=C["ink"], tags="d")
        elif prop == "game":
            gx, gy = ox + 4.5 * P, oy + 3.4 * P
            self.rect(gx, gy, gx + 5 * P, gy + 3.2 * P, "#8b8f99")
            self.rect(gx + 4, gy + 3, gx + 5 * P - 4, gy + 1.8 * P, "#9bbc0f" if (f // 5) % 2 else "#8bac0f")
            self.rect(gx + 6 + (f % 12) * 2, gy + 8, gx + 9 + (f % 12) * 2, gy + 11, "#306230")
        elif prop == "blow":
            r = min(18, f * 0.6) if f < 34 else 0
            if r:
                cx, cy = ox + 7 * P + 8, oy + 4 * P - r
                self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#f49ac1", outline="#c2678f", width=2, tags="d")
            elif f < 40:
                self.cv.create_text(ox + 7 * P, oy - 6, text=t("ПОП!"), fill="#f49ac1", font=self.f_tab, tags="d")
        elif prop == "sneeze" and f >= 14:
            self.cv.create_text(ox - 30, oy + 10, text=t("апчх!"), fill=C["muted"], font=self.f_mono, tags="d")
        elif prop == "look" and f > 28:
            self.cv.create_text(hx, hy, text="?", fill=C["muted"], font=self.f_mono, tags="d")

    # windows
    def draw_bubble(self) -> None:
        self.bubble_box = None
        b = self.bubble
        if b and time.time() > b["until"]:
            self.bubble = b = None
        live = None
        if not b and self.mood in WORKING | {"error"} and not self.chat_open:
            live = {"text": t(LABEL[self.mood]), "tab": self.mood}
        if self.chat_anim > 0.05 or not (b or live):
            return
        data = b or live
        lines = self.wrap(data["text"], self.f_body, 240)[:8]
        lh = self.f_body.metrics("linespace")
        tw = max(self.f_body.measure(s) for s in lines) if lines else 40
        tab_text = t(TAB.get(data["tab"], str(data["tab"]).upper()))
        tw = max(tw, self.f_tab.measure(tab_text) + 20)
        bw, bh = tw + 32, lh * len(lines) + 30
        x1 = min(W - 8, self.head[0] + bw * 0.6)
        x0 = max(8, x1 - bw)
        x1 = x0 + bw
        y1 = self.my - 22
        y0 = y1 - bh
        tail = self.head[0]
        age = self.frame - self.bubble_born_frame
        e = ease_steps(age / 5) if b else 1.0          # unfold from the tail in pixel steps
        if e < 1:
            self.cartridge(tail - (tail - x0) * e, y1 - (y1 - y0) * e, tail + (x1 - tail) * e, y1, None, tail)
            return
        self.cartridge(x0, y0, x1, y1, tab_text, tail)
        self.bubble_box = (x0, y0 - 8, x1, y1 + 10)
        shown, full = self.typed(lines, self.bubble_born_frame + 5) if b else (lines, True)
        tx, ty = x0 + 16, y0 + 15
        for i, s in enumerate(shown):
            self.cv.create_text(tx, ty + i * lh, text=s, anchor="nw", fill=C["text"], font=self.f_body, tags="d")
        if not full or (self.frame // 5) % 2 == 0:       # block cursor
            last = shown[-1] if shown else ""
            cx = tx + self.f_body.measure(last) + 3
            cy = ty + (len(shown) - 1) * lh + 3
            self.rect(cx, cy, cx + 7, cy + lh - 5, C["accent"])

    def chat_box(self) -> tuple[float, float, float, float]:
        return W - 300, 110, W - 10, self.my - 22

    def draw_chat(self) -> None:
        target = 1.0 if self.chat_open else 0.0
        if self.chat_anim != target:
            self.chat_anim = min(1.0, self.chat_anim + 0.2) if target else max(0.0, self.chat_anim - 0.25)
        if self.chat_anim <= 0:
            self.cv.itemconfigure(self.entry_win, state="hidden")
            return
        x0, y0, x1, y1 = self.chat_box()
        tail = self.head[0]
        e = ease_steps(self.chat_anim, 5)
        if e < 1:
            self.cv.itemconfigure(self.entry_win, state="hidden")
            self.cartridge(tail - (tail - x0) * e, y1 - (y1 - y0) * e, tail + (x1 - tail) * e, y1, None, tail)
            return
        name = self.title or os.path.basename(self.cwd.rstrip("\\/")) or self.cwd
        self.cartridge(x0, y0, x1, y1, t("ЧАТ") + " · " + shorten(name, 30).upper(), tail)
        # close button
        cxb, cyb = x1 - 18, y0 + 16
        self.rect(cxb - 9, cyb - 9, cxb + 9, cyb + 9, C["surface"])
        for i in range(-4, 5, 2):
            self.rect(cxb + i - 1, cyb + i - 1, cxb + i + 1, cyb + i + 1, C["muted"])
            self.rect(cxb - i - 1, cyb + i - 1, cxb - i + 1, cyb + i + 1, C["muted"])
        # input well
        iy0, iy1 = y1 - 44, y1 - 12
        self.stepped(x0 + 12, iy0, x1 - 12, iy1, C["line"], 2)
        self.stepped(x0 + 14, iy0 + 2, x1 - 14, iy1 - 2, C["surface"], 2)
        self.cv.create_text(x0 + 24, (iy0 + iy1) / 2, text="›", fill=C["accent"], font=self.f_big, tags="d")
        self.cv.coords(self.entry_win, x0 + 38, (iy0 + iy1) / 2)
        self.cv.itemconfigure(self.entry_win, state="normal", width=x1 - x0 - 64, height=22)
        # messages, newest at the bottom
        area_top, y = y0 + 34, iy0 - 10
        maxw = x1 - x0 - 90
        for msg in reversed(self.chat_msgs):
            if msg.get("pending"):
                h = self.f_body.metrics("linespace") + 14
                if y - h < area_top:
                    break
                self.stepped(x0 + 40, y - h, x0 + 96, y, C["surface"], 2)
                for i in range(3):   # bouncing typing dots
                    by = y - h / 2 - (3 if (self.frame // 2) % 3 == i else 0)
                    self.rect(x0 + 54 + i * 10, by - 2, x0 + 59 + i * 10, by + 3, C["accent"])
                self.mini_face(x0 + 16, y - h + 2)
                y -= h + 10
                continue
            font = self.f_small if msg["who"] == "note" else self.f_body
            full_lines = self.wrap(msg["text"], font, maxw)
            lines = self.typed(full_lines, msg["born"], 4.5)[0] if msg["who"] == "bot" else full_lines
            mlh = font.metrics("linespace")
            h = mlh * len(full_lines) + 14
            if y - h < area_top:
                break
            tw = max((font.measure(s) for s in full_lines), default=20)
            if msg["who"] == "me":
                bx1, bx0 = x1 - 18, x1 - 18 - tw - 22
                self.stepped(bx0, y - h, bx1, y, C["accent_dk"], 2)
                col = C["text"]
            elif msg["who"] == "note":
                bx0, bx1 = x0 + 40, x0 + 40 + tw + 22
                self.cv.create_rectangle(bx0, y - h, bx1, y, outline=C["line"], dash=(2, 2), tags="d")
                col = C["muted"]
            else:
                bx0, bx1 = x0 + 40, x0 + 40 + tw + 22
                self.stepped(bx0, y - h, bx1, y, C["surface"], 2)
                self.mini_face(x0 + 16, y - h + 2)
                col = C["text"]
            for i, s in enumerate(lines):
                self.cv.create_text(bx0 + 11, y - h + 7 + i * mlh, text=s, anchor="nw", fill=col, font=font, tags="d")
            y -= h + 10

    def mini_face(self, x: float, y: float) -> None:
        self.px(1, 0, ORANGE, 5, 3, size=3, ox=x, oy=y)
        self.px(0, 1, ORANGE, 1, 1, size=3, ox=x, oy=y)
        self.px(6, 1, ORANGE, 1, 1, size=3, ox=x, oy=y)
        for lx in (1.5, 4.5):
            self.px(lx, 3, ORANGE, 1, 1, size=3, ox=x, oy=y)
        blink = (self.frame // 3) % 20 == 0
        self.px(2, 1, INK, 1, 0.4 if blink else 1, size=3, ox=x, oy=y)
        self.px(4, 1, INK, 1, 0.4 if blink else 1, size=3, ox=x, oy=y)

    def draw_pill(self) -> None:
        target = 1.0 if (self.hover and not self.chat_open and not self.drag) else 0.0
        self.pill_anim = min(1.0, self.pill_anim + 0.25) if target else max(0.0, self.pill_anim - 0.25)
        if self.pill_anim <= 0:
            return
        e = ease_steps(self.pill_anim, 4)
        label = t("спитай щось")
        tw = self.f_small.measure(label) + 40
        x1 = self.mx + 14 * P + 6
        x0 = x1 - tw
        y1 = H - 4
        y0 = y1 - 22
        off = (1 - e) * 16                                  # slides up into place
        self.stepped(x0 + 3, y0 + 3 + off, x1 + 3, y1 + 3 + off, C["shadow"], 2)
        self.stepped(x0, y0 + off, x1, y1 + off, C["line"], 2)
        self.stepped(x0 + 2, y0 + 2 + off, x1 - 2, y1 - 2 + off, C["bg"], 2)
        if e >= 1:
            mid = (y0 + y1) / 2
            self.cv.create_text(x0 + 12, mid, text="›", anchor="w", fill=C["accent"], font=self.f_tab, tags="d")
            self.cv.create_text(x0 + 24, mid, text=label, anchor="w", fill=C["text"], font=self.f_small, tags="d")
            if (self.frame // 5) % 2:
                cx = x0 + 24 + self.f_small.measure(label) + 3
                self.rect(cx, y0 + 6, cx + 5, y1 - 6, C["accent"])

    # loop
    def tick_idle(self) -> None:
        now = time.time()
        if self.mood != "idle" or self.chat_open or not MOTION:
            return
        own = world.THEME_SHOWS.get(self.theme, {})
        if self.show:
            self.show_frame += 1
            if self.show_frame >= {**IDLE_SHOWS, **own}.get(self.show, 0):
                self.show = ""
                self.next_show_at = now + random.uniform(3, 8)
        elif self.devices.music or self.media_active:
            return   # music on: he just grooves
        elif now >= self.next_show_at and now - self.last_activity < 300:
            pool = list(own) if own and random.random() < 0.5 else list(IDLE_SHOWS)   # half the time, the theme's own
            self.show = random.choice(pool)
            self.show_frame = 0

    def loop(self) -> None:
        try:
            now = time.time()
            if self.hidden_until and now >= self.hidden_until:
                self.hidden_until = 0
                self.root.deiconify()
                self.apply_overlay_styles()
            self.read_state()
            age = now - self.mood_since
            if not self.busy_q:
                if self.mood in ("done", "error") and age > 9:
                    self.set_mood("idle")
                elif self.mood in WORKING and now - self.state_ts > (600 if self.mood == "running" else 90):
                    self.set_mood("idle")  # Claude went quiet (a stopped turn sends no Stop); commands may run long
                elif self.mood in WORKING and self.mood_frame and self.mood_frame % 150 == 0:
                    self.variant = random.choice(VARIANTS[self.mood])  # keep long work fresh
            self.tick_intro()
            self.tick_idle()
            self.tick_menu()
            self.tick_ghost()
            self.tick_tip()
            self.tick_screen()
            if self.frame % 60 == 0:
                try:
                    u = ctypes.windll.user32
                    hwnd = u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                    u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
                except Exception:
                    self.root.attributes("-topmost", True)
            self.redraw()
            self.frame += 1
            self.mood_frame += 1
        except Exception as e:  # noqa: BLE001
            log(f"loop: {e!r}")
        self.root.after(TICK, self.loop)

    def redraw(self, move: bool = True) -> None:
        self.cv.delete("d")
        self.weather.step_and_draw(self, move)
        self.draw_bubble()
        self.draw_chat()
        self.draw_mascot()
        self.weather.draw_pile(self)
        self.draw_pill()
        self.last_redraw = time.time()


def main() -> None:
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 47613))  # single instance
    except OSError:
        log("single instance lock busy")
        return
    try:
        app = Claudik()
        app.root.mainloop()
    except Exception as e:
        log(f"fatal crash: {e!r}")


if __name__ == "__main__":
    main()
