"""Klodik's world: themes (costume, weather, own idle shows, an intro when you switch to one) and what
is plugged in (headphones, controllers, other Bluetooth gadgets, music). Drawn through the overlay's px/rect."""
import base64
import json
import math
import random
import re
import subprocess
import threading

ORANGE = "#d97757"
INK = "#1a1410"
P = 8

# name/hint are interface strings (translated by l10n.t); accent recolours the cartridge tabs.
THEMES = {
    "none": {"name": "Без теми", "hint": "просто Клодік"},
    "spring": {"name": "Весна", "hint": "паросток на голові, пелюстки, чай"},
    "summer": {"name": "Літо", "hint": "солом'яний капелюх, сонце, морозиво"},
    "autumn": {"name": "Осінь", "hint": "берет, шарф, купа листя біля ніг"},
    "winter": {"name": "Зима", "hint": "шапка з помпоном, сніг лягає на голову"},
    "sakura": {"name": "Сакура", "hint": "хатімакі, поклони, чай і журавлик"},
    "matrix": {"name": "Матриця", "hint": "чорні окуляри, зелений дощ, кулі", "accent": ("#3ddc84", "#1d6b40")},
    "neon": {"name": "Неон-Маямі", "hint": "пальми, авіатори, сам сідає в спорткар", "accent": ("#ff5fa2", "#a3326a")},
    "halloween": {"name": "Хелловін", "hint": "капелюх відьми, кажани, гарбуз", "accent": ("#b07be0", "#5b2a86")},
}
THEME_SHOWS = {  # theme: {show: frames}
    "spring": {"water": 56, "tea": 56},
    "summer": {"icecream": 60},
    "autumn": {"kickleaves": 40, "cocoa": 46},
    "winter": {"snowball": 44, "shiver": 30},
    "sakura": {"bow": 30, "tea": 56, "crane": 60},
    "matrix": {"bullets": 50, "glitch": 24},
    "neon": {"car": 86, "phone": 50},
    "halloween": {"pumpkin": 60, "boo": 40},
}
# What he does right after dressing up for a theme you just picked.
INTRO_SHOW = {"spring": "tea", "summer": "icecream", "autumn": "kickleaves", "winter": "shiver", "sakura": "bow",
              "matrix": "glitch", "neon": "car", "halloween": "pumpkin"}
GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄ0123456789"


class Weather:
    """Falling things per theme, plus what piles up: leaves at his feet, snow on his hat."""

    def __init__(self) -> None:
        self.theme = "none"
        self.parts: list[list] = []      # [x, y, vx, vy, kind, phase, colour]
        self.cols: list[list] = []       # matrix rain: [x, y, speed, glyphs]
        self.bats: list[list] = []       # halloween: [x, y, speed, phase]
        self.pile = 0                    # leaves / snow at his feet
        self.cap = 0                     # snow on his head
        self.win = None                  # window's screen position last frame: particles stay put on screen
        self.cx, self.top = 318, 446     # mascot centre x / head y in window coords (updated each frame)

    # Particles live near Klodik: they spawn in a small cloud above him and are dropped once they
    # drift too far, so dragging him leaves the old ones behind and new ones appear around him.
    SPREAD_X = 70      # how far left/right of his centre new ones appear
    SPAWN_UP = 150     # how high above his head they start
    KEEP_R = 130       # farther than this from him: a left-behind particle that keeps falling where it was

    def set_theme(self, theme: str, w: int, h: int) -> None:
        self.theme = theme
        self.parts, self.cols, self.bats, self.pile, self.cap = [], [], [], 0, 0
        n = {"spring": 12, "autumn": 10, "winter": 22, "sakura": 16}.get(theme, 0)
        for _ in range(n):
            self.parts.append(self._spawn(w, random.uniform(self.top - self.SPAWN_UP, self.top + 40)))
        if theme == "matrix":
            self.cols = [[x, random.uniform(-h, h), random.uniform(5, 11), [random.choice(GLYPHS) for _ in range(9)]]
                         for x in range(8, w, 26)]
        if theme == "halloween":
            self.bats = [[random.uniform(0, w), random.uniform(40, h - 200), random.uniform(1.5, 3), random.random() * 6]
                         for _ in range(4)]

    def _spawn(self, w: int, y: float) -> list:
        kind = {"spring": random.choice(["petal", "leaf"]), "autumn": "leaf", "winter": "snow", "sakura": "petal"}[self.theme]
        colour = {
            ("spring", "petal"): random.choice(["#f6b3c8", "#fff1a8"]), ("spring", "leaf"): "#7ec850",
            ("autumn", "leaf"): random.choice(["#d9662b", "#b8442a", "#e0a33a", "#8a5a2b"]),
            ("winter", "snow"): "#f4f8ff", ("sakura", "petal"): random.choice(["#f7c6d9", "#f29bbd", "#ffe3ee"]),
        }[(self.theme, kind)]
        vy = {"snow": random.uniform(1.2, 2.6), "leaf": random.uniform(1.5, 2.8), "petal": random.uniform(1.0, 2.0)}[kind]
        x = self.cx + random.uniform(-self.SPREAD_X, self.SPREAD_X)
        return [x, y, random.uniform(-0.4, 0.2), vy, kind, random.random() * 6.28, colour]

    def shake_off(self) -> None:
        self.cap = 0
        self.pile = max(0, self.pile - 10)

    def _recycle(self, app, p: list, w: int, head: tuple, respawn_y: float, ground: float) -> bool:
        """Replace a particle that has landed, left the screen or drifted away. True if it was replaced.
        Only called while the animation moves, so a draw-only redraw never changes the scene."""
        if self.theme == "winter" and head[0] <= p[0] <= head[1] and abs(p[1] - head[2]) < 4 and app.mood == "idle":
            self.cap = min(22, self.cap + 1)                    # snow settles on his hat while he idles
            p[:] = self._spawn(w, respawn_y)
            return True
        far = abs(p[0] - self.cx) > self.KEEP_R
        if p[0] < -10 or p[0] > w + 10 or p[1] > 570 or p[1] < -200:
            p[:] = self._spawn(w, respawn_y + random.uniform(-20, 20))   # gone off screen: a new one near him
            return True
        if far and random.random() < 0.004:
            p[:] = self._spawn(w, respawn_y)   # left behind: lingers a while, then a new one near him
            return True
        if p[1] >= ground and not far:
            if self.theme in ("autumn", "winter") and abs(p[0] - (app.mx + 56)) < 90:
                self.pile = min(40, self.pile + 1)
            p[:] = self._spawn(w, respawn_y)
            return True
        return False

    def step_and_draw(self, app, move: bool = True) -> None:
        """Behind everything else; called once per frame. move=False only redraws (extra frames while dragging)."""
        w, ground = 400, app.my + 8 * P + 8
        head = (app.mx + 2 * P, app.mx + 12 * P, app.my)
        fr = app.frame
        if self.theme == "matrix":
            for col in self.cols:
                col[1] += col[2] if move else 0
                if col[1] - 9 * 14 > 560:
                    col[1] = random.uniform(-200, 0)
                if random.random() < 0.15:
                    col[3][random.randrange(9)] = random.choice(GLYPHS)
                for i, g in enumerate(col[3]):
                    y = col[1] - i * 14
                    if 0 <= y <= 560:
                        shade = "#d6ffe4" if i == 0 else ("#3ddc84" if i < 4 else "#1d6b40")
                        app.cv.create_text(col[0], y, text=g, fill=shade, font=app.f_mono, tags="d")
            return
        if self.theme == "summer":
            sx, sy = app.mx - 60, app.my - 120                      # a small pixel sun with turning rays
            app.cv.create_oval(sx - 16, sy - 16, sx + 16, sy + 16, fill="#f6c445", outline="#e8a92a", width=2, tags="d")
            for i in range(8):
                a = fr / 20 + i * math.pi / 4
                rx, ry = sx + math.cos(a) * 26, sy + math.sin(a) * 26
                app.rect(rx - 2, ry - 2, rx + 2, ry + 2, "#f6c445")
            return
        if self.theme == "neon":
            sx, sy = app.mx - 70, app.my - 30                       # low sun behind a palm
            app.cv.create_oval(sx - 30, sy - 30, sx + 30, sy + 30, fill="#ff8a5c", outline="#ff5fa2", width=2, tags="d")
            app.rect(sx - 32, sy + 8, sx + 32, sy + 11, app.KEY)    # two cuts let the desktop show through
            app.rect(sx - 32, sy + 17, sx + 32, sy + 20, app.KEY)
            bx, by = app.mx - 30, ground
            for i in range(9):                                      # a leaning trunk
                app.rect(bx - i * 2, by - i * 10, bx - i * 2 + 7, by - i * 10 + 9, "#7a4a2a" if i % 2 else "#8e5a33")
            tx, ty = bx - 18, by - 92
            sway = math.sin(fr / 12) * 3
            for dx, dy in ((-34, 10), (-22, -4), (0, -10), (22, -4), (34, 10)):
                for k in range(5):
                    x = tx + dx * k / 4 + sway * k / 4
                    y = ty + dy * k / 4 + (k * k * 0.8 if abs(dx) > 20 else 0)
                    app.rect(x, y, x + 6, y + 4, "#2fbf9a" if k % 2 else "#1f9a7a")
            return
        if self.theme == "halloween":
            for b in self.bats:
                b[0] += b[2] if move else 0
                if b[0] > w + 20:
                    b[0], b[1] = -20, random.uniform(40, 360)
                x, y = b[0], b[1] + math.sin(fr / 6 + b[3]) * 10
                flap = (fr // 3 + int(b[3])) % 2
                app.rect(x - 3, y - 2, x + 3, y + 3, "#1b1022")
                app.rect(x - 11, y - (5 if flap else 0), x - 3, y + (1 if flap else 3), "#1b1022")
                app.rect(x + 3, y - (5 if flap else 0), x + 11, y + (1 if flap else 3), "#1b1022")
                app.rect(x - 2, y - 1, x - 1, y, "#f2c14e")
                app.rect(x + 1, y - 1, x + 2, y, "#f2c14e")
            gx, gy = (fr * 0.7) % (w + 60) - 30, app.my - 150 + math.sin(fr / 15) * 12   # a drifting ghost
            app.cv.create_oval(gx, gy, gx + 18, gy + 16, fill="#eef0f5", outline="#eef0f5", tags="d")
            app.rect(gx, gy + 8, gx + 18, gy + 22, "#eef0f5")
            for k in range(3):
                app.rect(gx + k * 6 + (fr // 4) % 2 * 2, gy + 22, gx + k * 6 + 3 + (fr // 4) % 2 * 2, gy + 25, "#eef0f5")
            app.rect(gx + 4, gy + 6, gx + 7, gy + 10, "#1b1022")
            app.rect(gx + 11, gy + 6, gx + 14, gy + 10, "#1b1022")
            return
        self.cx, self.top = app.mx + 56, app.my
        try:   # the window moved (dragged): shift particles back so they stay where they were on screen
            pos = (app.root.winfo_x(), app.root.winfo_y())
        except Exception:  # noqa: BLE001
            pos = None
        if pos and self.win and pos != self.win:
            dx, dy = pos[0] - self.win[0], pos[1] - self.win[1]
            for p in self.parts:
                p[0] -= dx
                p[1] -= dy
        self.win = pos
        respawn_y = self.top - self.SPAWN_UP
        for p in self.parts:
            if move:
                p[5] += 0.12
                p[0] += p[2] + math.sin(p[5]) * (0.9 if p[4] != "snow" else 0.4)
                p[1] += p[3]
            if move and self._recycle(app, p, w, head, respawn_y, ground):
                continue
            x, y, c = p[0], p[1], p[6]
            if p[4] == "snow":
                app.rect(x, y, x + 3, y + 3, c)
            elif p[4] == "leaf":
                flip = math.sin(p[5] * 2) > 0
                app.rect(x, y, x + (5 if flip else 3), y + (3 if flip else 5), c)
            else:
                app.rect(x, y, x + 4, y + 3, c)
                app.rect(x + 1, y + 3, x + 3, y + 4, c)

    def draw_pile(self, app) -> None:
        """In front of his feet: leaves or snow that landed."""
        if self.pile <= 0 or self.theme not in ("autumn", "winter"):
            return
        cx, gy = app.mx + 56, app.my + 8 * P + 10
        rnd = random.Random(7)
        for i in range(self.pile):
            x = cx + rnd.uniform(-1, 1) * (30 + i * 1.4)
            y = gy - rnd.uniform(0, 1) * min(14, 2 + self.pile * 0.3)
            col = "#f4f8ff" if self.theme == "winter" else rnd.choice(["#d9662b", "#b8442a", "#e0a33a", "#8a5a2b"])
            app.rect(x, y, x + 5, y + 3, col)


def draw_costume(app, p: dict, ox: float, oy: float, top: float, weather: Weather, idle_for: float,
                 theme: str, drop: float = 0.0) -> None:
    """The theme's outfit. `drop` (in mascot pixels) lifts it above his head while he is putting it on."""
    if theme == "none":
        return
    oy = oy - drop * P
    px = app.px
    shades = p["eyes"] in ("normal", "wide", "squint", "glasses") and drop < 0.5
    if theme == "spring":
        h = min(6.0, 1.5 + idle_for / 30)            # the sprout grows while he idles
        px(6.8, top - h, "#5aa83c", 0.4, h, ox=ox, oy=oy)
        px(5.6, top - h * 0.6, "#7ec850", 1.2, 0.6, ox=ox, oy=oy)
        px(7.2, top - h * 0.8, "#7ec850", 1.2, 0.6, ox=ox, oy=oy)
        if h >= 4:
            px(6.4, top - h - 0.9, "#f6b3c8", 1.2, 1.0, ox=ox, oy=oy)
            px(6.75, top - h - 0.55, "#fff1a8", 0.5, 0.4, ox=ox, oy=oy)
    elif theme == "summer":
        px(0.5, top - 0.8, "#e8c873", 13, 0.8, ox=ox, oy=oy)
        px(3.5, top - 2.6, "#e8c873", 7, 1.9, ox=ox, oy=oy)
        px(3.5, top - 1.3, "#c0392b", 7, 0.5, ox=ox, oy=oy)
        if shades:
            _shades(app, ox, oy + drop * P, top, "#2a1d12")
    elif theme == "autumn":
        px(3, top - 1.1, "#7a3b2e", 8, 1.3, ox=ox, oy=oy)
        px(9.8, top - 1.6, "#7a3b2e", 0.6, 0.7, ox=ox, oy=oy)
        px(2, 4.6, "#c8762b", 10, 0.9, ox=ox, oy=oy)
        px(9, 5.4, "#c8762b", 1.2, 1.6, ox=ox, oy=oy)
    elif theme == "winter":
        cap = weather.cap / 8
        px(2.5, top - 1.6, "#3f6fb5", 9, 1.8, ox=ox, oy=oy)
        px(2.3, top - 0.4, "#e9eef5", 9.4, 0.7, ox=ox, oy=oy)
        px(6.4, top - 2.6 - cap, "#e9eef5", 1.2, 1.1, ox=ox, oy=oy)
        if cap:
            px(2.7, top - 1.6 - cap, "#ffffff", 8.6, cap, ox=ox, oy=oy)
        px(2, 4.6, "#c0392b", 10, 0.9, ox=ox, oy=oy)
        px(3, 5.4, "#c0392b", 1.2, 1.6, ox=ox, oy=oy)
    elif theme == "sakura":
        px(2, top + 0.15, "#f4f1ea", 10, 0.6, ox=ox, oy=oy)
        px(6.6, top + 0.2, "#d6302c", 0.8, 0.5, ox=ox, oy=oy)
        wave = (app.frame // 4) % 2 * 0.2
        px(12, top + 0.1 + wave, "#f4f1ea", 1.3, 0.4, ox=ox, oy=oy)
        px(12.7, top + 0.5 - wave, "#f4f1ea", 1.1, 0.4, ox=ox, oy=oy)
    elif theme == "matrix":
        px(2, 3.4, "#0f1410", 1.6, 2.6, ox=ox, oy=oy)    # coat lapels
        px(10.4, 3.4, "#0f1410", 1.6, 2.6, ox=ox, oy=oy)
        px(6.6, 3.6, "#1d6b40", 0.8, 2.2, ox=ox, oy=oy)  # thin green tie
        if shades:
            _shades(app, ox, oy + drop * P, top, "#050805")
    elif theme == "neon":
        px(2, 3.6, "#2fbf9a", 10, 2.4, ox=ox, oy=oy)     # open Hawaiian shirt
        for fx, fy in ((3, 4.2), (5.6, 5.0), (9.2, 4.0), (10.4, 5.2)):
            px(fx, fy, "#ff5fa2", 0.8, 0.6, ox=ox, oy=oy)
            px(fx + 0.25, fy + 0.15, "#fff1a8", 0.3, 0.3, ox=ox, oy=oy)
        px(6, 3.6, ORANGE, 2, 1.2, ox=ox, oy=oy)          # the collar opens on his body
        if shades:
            ey = 1 + top * 0.6
            for x in (3, 8):
                px(x - 0.2, ey - 0.2, "#d4a93a", 3.4, 1.8, ox=ox, oy=oy + drop * P)
                px(x, ey, "#2a1530", 3, 1.4, ox=ox, oy=oy + drop * P)
            px(6, ey + 0.2, "#d4a93a", 2, 0.3, ox=ox, oy=oy + drop * P)
    elif theme == "halloween":
        px(1, top - 0.6, "#2d1840", 12, 0.7, ox=ox, oy=oy)
        px(3.5, top - 2, "#2d1840", 7, 1.5, ox=ox, oy=oy)
        px(4.8, top - 3.2, "#2d1840", 4.4, 1.3, ox=ox, oy=oy)
        px(6, top - 4.2, "#2d1840", 2.2, 1.1, ox=ox, oy=oy)
        px(7.6, top - 4.8, "#2d1840", 1.4, 0.7, ox=ox, oy=oy)
        px(3.5, top - 1.0, "#f28c28", 7, 0.4, ox=ox, oy=oy)
        px(1.6, 1.6, "#3a1d52", 0.5, 4.4, ox=ox, oy=oy)   # cape edges
        px(11.9, 1.6, "#3a1d52", 0.5, 4.4, ox=ox, oy=oy)


def _shades(app, ox: float, oy: float, top: float, colour: str) -> None:
    ey = 1 + top * 0.6
    app.px(3, ey, colour, 3, 1.5, ox=ox, oy=oy)
    app.px(8, ey, colour, 3, 1.5, ox=ox, oy=oy)
    app.px(6, ey + 0.3, colour, 2, 0.3, ox=ox, oy=oy)
    app.px(3.4, ey + 0.2, "#5a6a70", 0.8, 0.3, ox=ox, oy=oy)   # glint
    app.px(8.4, ey + 0.2, "#5a6a70", 0.8, 0.3, ox=ox, oy=oy)


def draw_gear(app, gear: dict, music: bool, ox: float, oy: float, top: float) -> None:
    """Things he wears because they are plugged in. gear: {"headphones": lift, "gadget": lift}, lift in mascot
    pixels above the head (0 = on); a missing key = not worn."""
    px = app.px
    if "gadget" in gear:
        o = oy - gear["gadget"] * P
        px(3, top - 1.6, "#9aa8b8", 0.3, 1.6, ox=ox, oy=o)
        if (app.frame // 5) % 2:
            px(2.8, top - 2.1, "#3d8bff", 0.7, 0.6, ox=ox, oy=o)
    if "headphones" in gear:
        o = oy - gear["headphones"] * P
        px(1.6, top - 1.0, "#2b2b2b", 10.8, 0.6, ox=ox, oy=o)
        px(1.2, top - 0.7, "#2b2b2b", 0.6, 1.8, ox=ox, oy=o)
        px(12.2, top - 0.7, "#2b2b2b", 0.6, 1.8, ox=ox, oy=o)
        px(0.7, 1.0 + top * 0.5, "#3a3a3a", 1.5, 2.2, ox=ox, oy=o)
        px(11.8, 1.0 + top * 0.5, "#3a3a3a", 1.5, 2.2, ox=ox, oy=o)
        if music and gear["headphones"] == 0 and (app.frame // 4) % 2:
            px(1.1, 1.6 + top * 0.5, "#7ee787", 0.6, 0.6, ox=ox, oy=o)
            px(12.2, 1.6 + top * 0.5, "#7ee787", 0.6, 0.6, ox=ox, oy=o)


def draw_pad(app, ox: float, oy: float, light: bool, lift: float = 0.0) -> None:
    """A gamepad in his hands; `lift` > 0 = still on its way up from the floor."""
    x, y = ox + 3.5 * P, oy + 3.6 * P + lift * P
    app.rect(x, y + 4, x + 7 * P, y + 2 * P, "#2e2e33")
    app.rect(x - 4, y + 8, x + 6, y + 2 * P + 6, "#2e2e33")
    app.rect(x + 7 * P - 6, y + 8, x + 7 * P + 4, y + 2 * P + 6, "#2e2e33")
    app.rect(x + 8, y + 9, x + 16, y + 11, "#888")              # d-pad
    app.rect(x + 11, y + 6, x + 13, y + 14, "#888")
    for i, col in enumerate(("#e8455c", "#6cb8ff", "#7ee787", "#f2c14e")):
        on = light and (app.frame // 2 + i) % 4 == 0
        bx = x + 40 + (i % 2) * 6
        by = y + 6 + (i // 2) * 6
        app.rect(bx, by, bx + 4, by + 4, col if on else "#55555c")


def car_track(f: int) -> tuple[float, float, bool]:
    """Neon theme's car ride: (car x offset, his x offset, sitting in it) in mascot pixels for frame f."""
    if f < 16:
        return -34 * (1 - f / 16), 0, False                  # car pulls up
    if f < 24:
        return 0, 0, f >= 21                                # he hops in
    if f < 50:
        k = (f - 24) / 26
        return 42 * k * k, 42 * k * k, True                 # drives off, speeding up
    if f < 56:
        return 42, 42, True
    if f < 74:
        k = 1 - (f - 56) / 18
        return -42 * k * k, -42 * k * k, True               # comes back from the left
    if f < 80:
        return 0, 0, f < 77                                 # hops out
    k = (f - 80) / 6
    return 40 * k * k, 0, False                             # car leaves


def theme_pose(show: str, f: int, p: dict) -> None:
    """Body language for the theme's own shows (also played as a theme's intro)."""
    if show == "water":
        p.update(arms="up" if f < 40 else "down", look=(0.3, -0.8), eyes="happy" if f > 40 else "normal")
    elif show == "icecream":
        p.update(arms="hold_mouth", mouth="o" if (f // 4) % 2 else None, eyes="happy" if f > 36 else "normal")
    elif show == "kickleaves":
        p.update(legs="kick", eyes="happy", dy=-0.4 if (f // 4) % 2 else 0)
    elif show == "tea":
        p.update(arms="hold" if f < 24 else "hold_mouth", look=(0, 0.7) if f < 24 else p["look"],
                 eyes="closed" if 30 < f < 48 else "normal")
    elif show == "cocoa":
        p.update(arms="hold_mouth", eyes="closed" if 16 < f < 40 else "normal")
    elif show == "snowball":
        p.update(arms="up" if f < 16 else "pump", look=(-0.8, -0.3), eyes="squint" if f < 16 else "happy")
    elif show == "shiver":
        p.update(dx=[-0.15, 0.15][f % 2], eyes="squint", mouth="o", arms="hold")
    elif show == "bow":
        depth = min(1.0, f / 8) if f < 20 else max(0.0, (30 - f) / 10)
        p.update(sq=0.5 * depth, dy=0.4 * depth, eyes="closed" if depth > 0.3 else "normal", look=(0, 0.8))
    elif show == "crane":
        p.update(arms="hold" if f < 34 else "up", look=(0, 0.6) if f < 34 else (-0.6, -0.8),
                 eyes="happy" if f >= 34 else "normal")
    elif show == "bullets":
        lean = min(1.0, f / 10) if f < 40 else max(0.0, (50 - f) / 10)
        p.update(dx=-0.8 * lean, sq=0.35 * lean, arms="out", legs="stand")
    elif show == "glitch":
        p.update(dx=random.choice([-0.5, 0, 0.5]), body=random.choice([ORANGE, "#3ddc84", ORANGE]))
    elif show == "car":
        _, his, sitting = car_track(f)
        hop = 16 <= f < 24 or 74 <= f < 80
        p.update(dx=his, legs="sit" if sitting else "stand", arms="out" if sitting else "down",
                 dy=(1.6 if sitting else 0) - (2.2 * math.sin(((f - 16) if f < 24 else (f - 74)) / 8 * math.pi) if hop else 0),
                 eyes="happy" if sitting else "normal", look=(-0.7, 0) if f < 16 else (0.7, 0))
    elif show == "phone":
        p.update(arms="chin", look=(-0.5, 0), mouth="o" if (f // 5) % 2 else None, eyes="happy" if f > 40 else "normal")
    elif show == "pumpkin":
        p.update(arms="hold", look=(0, 0.8), eyes="happy" if f > 44 else "normal")
    elif show == "boo":
        p.update(dy=-1.2 if 14 <= f < 28 else 0, arms="up" if 14 <= f < 28 else "down")


def theme_prop(app, show: str, f: int, ox: float, oy: float) -> None:
    rect = app.rect
    if show == "water":
        cx, cy = ox + 12 * P, oy - 34
        rect(cx, cy, cx + 18, cy + 12, "#5b8fd6")
        rect(cx - 10, cy + 2, cx, cy + 5, "#5b8fd6")
        if f < 40:
            for i in range(3):
                y = cy + 8 + ((f * 4 + i * 9) % 26)
                rect(cx - 12 - i * 2, y, cx - 10 - i * 2, y + 4, "#9fd3ff")
    elif show == "icecream":
        x, y = ox + 6 * P, oy + 3.6 * P
        scoop = max(0, 7 - f // 9)
        app.cv.create_polygon(x, y + 4, x + 14, y + 4, x + 7, y + 22, fill="#d9a35b", outline="#a8743a", tags="d")
        if scoop:
            app.cv.create_oval(x + 7 - scoop, y + 4 - scoop * 1.6, x + 7 + scoop, y + 6, fill="#f7c6d9",
                               outline="#e391b3", tags="d")
            rect(x + 3, y + 6 + (f % 10), x + 5, y + 9 + (f % 10), "#f7c6d9")
    elif show == "kickleaves":
        rnd = random.Random(f // 3)
        for _ in range(6):
            x = ox + 5 * P + rnd.uniform(-40, 40)
            y = oy + 8 * P - (f % 20) * 3 - rnd.uniform(0, 20)
            rect(x, y, x + 5, y + 3, rnd.choice(["#d9662b", "#b8442a", "#e0a33a"]))
    elif show == "tea":
        x, y = ox + 6 * P, oy + 3.4 * P
        if f < 24:   # brewing: a kettle pours into the cup
            kx, ky = ox + 11 * P, oy + 1.2 * P
            rect(kx, ky, kx + 16, ky + 12, "#9aa0a6")
            rect(kx - 6, ky + 2, kx, ky + 4, "#9aa0a6")
            for i in range(3):
                rect(kx - 8 - i, ky + 6 + ((f * 3 + i * 5) % 14), kx - 6 - i, ky + 9 + ((f * 3 + i * 5) % 14), "#7fa84a")
        rect(x, y, x + 14, y + 12, "#e9e4d8")
        rect(x + 14, y + 3, x + 18, y + 8, "#e9e4d8")
        rect(x + 2, y + 2, x + 12, y + 2 + min(4, f // 5), "#7fa84a")
        for i in range(2):
            s = (f + i * 6) % 14
            rect(x + 4 + i * 5 + math.sin((f + i) / 3) * 2, y - 4 - s, x + 6 + i * 5, y - 2 - s, "#bdb3a6")
    elif show == "cocoa":
        x, y = ox + 6 * P, oy + 3.4 * P
        rect(x, y, x + 14, y + 12, "#c98a4b")
        rect(x + 14, y + 3, x + 18, y + 8, "#c98a4b")
        for i in range(2):
            s = (f + i * 6) % 14
            rect(x + 4 + i * 5 + math.sin((f + i) / 3) * 2, y - 4 - s, x + 6 + i * 5, y - 2 - s, "#bdb3a6")
    elif show == "snowball":
        if f < 16:
            rect(ox + 6 * P, oy - 14, ox + 6 * P + 8, oy - 6, "#ffffff")
        elif f < 36:
            k = (f - 16) / 20
            x = ox + 6 * P - k * 170
            y = oy - 10 - math.sin(k * math.pi) * 60 + k * 40
            app.cv.create_oval(x, y, x + 8, y + 8, fill="#ffffff", outline="#cfd8e3", tags="d")
        else:
            for dx, dy in ((-6, 0), (0, -5), (6, 1), (2, 5)):
                rect(ox - 116 + dx, oy + 24 + dy, ox - 112 + dx, oy + 28 + dy, "#ffffff")
    elif show == "shiver":
        for i in range(2):
            rect(ox + (2 + i * 9) * P, oy - 6 - (f % 4), ox + (2 + i * 9) * P + 2, oy - 3 - (f % 4), "#cfe8ff")
    elif show == "crane":
        if f < 34:
            x, y = ox + 5 * P, oy + 3.2 * P
            size = 16 - (f // 8) * 3
            app.cv.create_polygon(x + 8, y, x + 8 + size, y + size / 2, x + 8, y + size, x + 8 - size / 2, y + size / 2,
                                  fill="#f29bbd", outline="#d6709a", tags="d")
        else:
            k = (f - 34) / 26
            x, y = ox + 6 * P - k * 140, oy - k * 120
            wing = 6 if (f // 2) % 2 else -2
            app.cv.create_polygon(x, y, x + 14, y + 2, x + 6, y - wing, fill="#f29bbd", outline="#d6709a", tags="d")
    elif show == "bullets":
        for i in range(3):
            x = ox - 60 + ((f * 9 + i * 40) % 260)
            y = oy + (1.5 + i * 1.3) * P
            rect(x, y, x + 8, y + 3, "#b9c2c9")
            for k in range(1, 5):
                rect(x - k * 9, y + 1, x - k * 9 + 5, y + 2, "#3ddc84" if k < 3 else "#1d6b40")
    elif show == "car":
        car_dx, _, _ = car_track(f)
        x, y = app.mx + (car_dx - 3) * P, app.my + 3.4 * P
        rect(x + 2 * P, y + 1.4 * P, x + 19 * P, y + 3.6 * P, "#ff5fa2")       # body
        rect(x + 6 * P, y + 0.2 * P, x + 14 * P, y + 1.4 * P, "#c93f80")      # cabin edge
        rect(x + 7 * P, y + 0.5 * P, x + 13 * P, y + 1.4 * P, "#9fe3f0")      # windshield
        rect(x + 2 * P, y + 2.2 * P, x + 19 * P, y + 2.6 * P, "#2fbf9a")      # stripe
        rect(x + 18.2 * P, y + 1.7 * P, x + 19 * P, y + 2.2 * P, "#fff1a8")   # headlight
        for wx in (5, 16):
            app.cv.create_oval(x + (wx - 1.3) * P, y + 2.8 * P, x + (wx + 1.3) * P, y + 5.4 * P,
                               fill="#141414", outline="#141414", tags="d")
            rect(x + (wx - 0.4) * P, y + 3.7 * P, x + (wx + 0.4) * P, y + 4.5 * P, "#9aa0a6")
        if 24 <= f < 50 or 56 <= f < 74:
            for i in range(3):   # speed lines
                rect(x - 10 - i * 14, y + (1.8 + i * 0.6) * P, x - i * 14, y + (1.8 + i * 0.6) * P + 2, "#ff5fa2")
    elif show == "phone":
        x, y = ox + 12 * P, oy + 1 * P
        rect(x, y, x + 8, y + 16, "#2b2b2b")
        rect(x + 1, y + 2, x + 7, y + 7, "#7ee787" if (f // 4) % 2 else "#4a9a5a")
        if (f // 5) % 2:
            for i in range(3):
                rect(x + 12 + i * 5, y - 2 - i * 2, x + 14 + i * 5, y + i * 2, "#bdb3a6")
    elif show == "pumpkin":
        x, y = ox + 5 * P, oy + 4.2 * P
        app.cv.create_oval(x - 2, y, x + 4 * P + 2, y + 3.2 * P, fill="#e8761c", outline="#b5560d", width=2, tags="d")
        rect(x + 1.8 * P, y - 6, x + 2.2 * P, y + 2, "#4a7a2a")
        lit = f > 44 and (f // 2) % 5 != 0
        inside = "#f6c445" if lit else "#3a1d0a"
        if f > 16:
            rect(x + 0.8 * P, y + 0.8 * P, x + 1.4 * P, y + 1.4 * P, inside)
            rect(x + 2.6 * P, y + 0.8 * P, x + 3.2 * P, y + 1.4 * P, inside)
        if f > 30:
            rect(x + 1 * P, y + 2 * P, x + 3 * P, y + 2.4 * P, inside)
    elif show == "boo":
        x, y = ox + 1.2 * P, oy - 1.8 * P - (1.2 * P if 14 <= f < 28 else 0)
        app.cv.create_oval(x, y, x + 11.6 * P, y + 7 * P, fill="#eef0f5", outline="#cfd3dc", tags="d")
        rect(x, y + 3.5 * P, x + 11.6 * P, y + 9.6 * P, "#eef0f5")
        for k in range(6):   # wavy hem
            rect(x + k * 2 * P + ((f // 3) % 2) * 4, y + 9.6 * P, x + k * 2 * P + P + ((f // 3) % 2) * 4, y + 10.4 * P,
                 "#eef0f5")
        rect(x + 3 * P, y + 3 * P, x + 4.4 * P, y + 4.8 * P, "#1b1022")
        rect(x + 7.2 * P, y + 3 * P, x + 8.6 * P, y + 4.8 * P, "#1b1022")
        if 14 <= f < 28:
            app.cv.create_oval(x + 5 * P, y + 5.6 * P, x + 6.6 * P, y + 7.4 * P, fill="#1b1022", outline="#1b1022", tags="d")


# ---- devices and music ----
_PS = r"""
$ErrorActionPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $null = $t.Wait(3000); $t.Result }
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType=WindowsRuntime]
$mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$dev = @(); $n = 0
while ($true) {
  if (-not (Get-Process -Id OWNER)) { exit }
  if ($n % 5 -eq 0) { $dev = @(Get-PnpDevice -PresentOnly -Status OK | ? { $_.Class -in 'AudioEndpoint','HIDClass','XnaComposite','XboxComposite' } | % { "$($_.Class)|$($_.FriendlyName)|$($_.InstanceId)" }) }
  $play = ''; $title = ''
  if ($mgr) {
    $s = $mgr.GetCurrentSession()
    if (-not $s -or [string]$s.GetPlaybackInfo().PlaybackStatus -ne 'Playing') {
      foreach ($other in $mgr.GetSessions()) {
        if ([string]$other.GetPlaybackInfo().PlaybackStatus -eq 'Playing') { $s = $other; break }
      }
    }
    if ($s) {
      $play = [string]$s.GetPlaybackInfo().PlaybackStatus
      $p = Await ($s.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
      if ($p) { $title = (@($p.Artist, $p.Title) | ? { $_ }) -join ' - ' }
      if (-not $title) { $title = $s.SourceAppId }
    }
  }
  @{ dev = $dev; play = $play; title = $title } | ConvertTo-Json -Compress
  $n++; Start-Sleep -Seconds 3
}
"""
_PAD = re.compile(r"dualsense|dualshock|wireless controller|game ?controller|gamecontroller|gamepad|joystick|"
                  r"xbox (wireless |one |series )?controller|spielsteuer|геймпад|джойстик", re.I)
_PAD_NOT = re.compile(r"bus|synthetic|airplane|system|systemcontroller", re.I)
_PHONES = re.compile(r"headphone|headset|kopfh|наушн|навушн|гарнитур|гарнітур|airpods|buds|earphone|hands-free", re.I)
_BT_HID = re.compile(r"\{0000(1124|1812)-", re.I)          # Bluetooth classic / LE HID profiles
_NOT_GADGET = re.compile(r"mouse|maus|keyboard|tastatur|consumer|benutzersteuer|vendor|hersteller|system|миш|клав", re.I)


def classify(lines: list[str]) -> dict:
    dev = {"headphones": False, "gamepad": False, "gadget": False}
    for line in lines:
        cls, name, inst = (line.split("|") + ["", "", ""])[:3]
        if _PAD.search(name) and not _PAD_NOT.search(name):
            dev["gamepad"] = True
        elif cls == "AudioEndpoint" and _PHONES.search(name):
            dev["headphones"] = True
        elif cls == "HIDClass" and _BT_HID.search(inst) and not _NOT_GADGET.search(name):
            dev["gadget"] = True   # shortcut: any non-mouse/keyboard Bluetooth HID; may catch odd BT mouse parts
    return dev


class DeviceWatch:
    """A small PowerShell loop reports devices every ~15 s and music every 3 s. It exits with the overlay."""

    def __init__(self, owner_pid: int) -> None:
        self.dev = {"headphones": False, "gamepad": False, "gadget": False}
        self.music = False
        self.track = ""
        script = _PS.replace("OWNER", str(owner_pid))
        enc = base64.b64encode(script.encode("utf-16-le")).decode()
        try:
            self.proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                creationflags=0x08000000)
        except OSError:
            self.proc = None
            return
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for raw in self.proc.stdout:
            try:
                msg = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            self.dev = classify(msg.get("dev") or [])
            self.music = msg.get("play") == "Playing"
            self.track = msg.get("title") or ""

    def stop(self) -> None:
        if self.proc:
            self.proc.kill()
