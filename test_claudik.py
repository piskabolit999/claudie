"""Self-check for the parts of Klodik with real logic. Run: python test_claudik.py"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys

import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REAL_CONFIG = os.path.join(HERE, "config.json")
before_cfg = open(REAL_CONFIG, encoding="utf-8").read() if os.path.exists(REAL_CONFIG) else None
os.environ["CLAUDIK_CONFIG"] = os.path.join(tempfile.mkdtemp(), "config.json")   # never touch the user's settings
loader =importlib.machinery.SourceFileLoader("overlay", os.path.join(HERE, "overlay.pyw"))
spec = importlib.util.spec_from_loader("overlay", loader)
ov = importlib.util.module_from_spec(spec)
loader.exec_module(ov)
import hook  # noqa: E402

assert ov.first_sentence("Зробив оверлей. Потім ще щось.") == "Зробив оверлей."
assert ov.first_sentence("Без крапки в кінці") == "Без крапки в кінці"
assert ov.first_sentence("Перший абзац\n\nДругий.") == "Перший абзац"
assert "—" not in ov.shorten("швидко — і просто", 50)
assert ov.shorten("a" * 20, 10) == "a" * 9 + "…"

assert hook.mood_for_tool("Edit") == "writing"
assert hook.mood_for_tool("PowerShell") == "running"
assert hook.mood_for_tool("mcp__Claude_Browser__navigate") == "web"
assert hook.mood_for_tool("SomethingNew") == "thinking"

# The hook writes one file per chat, names it by the first prompt, and leaves no temp file behind.
env = {k: v for k, v in os.environ.items() if k != "CLAUDIK_INTERNAL"}
path = os.path.join(hook.SESSIONS, "selftest.json")
for event in ({"hook_event_name": "UserPromptSubmit", "prompt": "зроби  оверлей", "session_id": "selftest", "cwd": HERE},
              {"hook_event_name": "UserPromptSubmit", "prompt": "інше", "session_id": "selftest", "cwd": HERE},
              {"hook_event_name": "PreToolUse", "tool_name": "Grep", "session_id": "selftest", "cwd": HERE},
              {"hook_event_name": "SubagentStop", "session_id": "selftest", "cwd": HERE}):   # must not change the mood
    subprocess.run([sys.executable, os.path.join(HERE, "hook.py")], input=json.dumps(event), text=True, check=True, env=env)
with open(path, encoding="utf-8") as f:
    st = json.load(f)
os.remove(path)
assert st["mood"] == "searching" and st["sid"] == "selftest", st
assert st["title"] == "зроби оверлей", st
assert not [n for n in os.listdir(hook.SESSIONS) if n.endswith(".tmp")]

# Every mood variant and idle show draws without raising (offscreen window, no timers).
ov.Claudik.loop = lambda self: None
app = ov.Claudik()
app.root.withdraw()


def frames(n: int) -> None:
    for _ in range(n):
        app.cv.delete("d")
        app.tick_intro()
        app.weather.step_and_draw(app)
        app.draw_bubble(); app.draw_chat(); app.draw_mascot(); app.weather.draw_pile(app); app.draw_pill()
        app.frame += 1; app.mood_frame += 1; app.show_frame += 1


for mood, variants in ov.VARIANTS.items():
    for v in variants:
        app.set_mood(mood); app.variant = v
        frames(30)
app.set_mood("idle")
for show, length in ov.IDLE_SHOWS.items():
    app.show, app.show_frame = show, 0
    frames(length)

# Device names: this PC's always-present virtual devices must not count; real ones must.
import world  # noqa: E402
none = world.classify(["HIDClass|XBOX Synthetic Gamepad Bus|ROOT\\X", "HIDClass|Acer Airplane Mode Controller|ACPI\\X",
                       "AudioEndpoint|Lautsprecher (Realtek(R) Audio)|SWD\\X", "HIDClass|HID-konformer Systemcontroller|HID\\X"])
assert not any(none.values()), none
some = world.classify(["HIDClass|DualSense Wireless Controller|HID\\{00001124-0000}_X",
                       "AudioEndpoint|Kopfhörer (WH-1000XM4)|SWD\\X"])
assert some["gamepad"] and some["headphones"], some

# Every theme, its own shows, the struggle, music and the gamepad draw without raising.
assert "space" not in world.THEMES and {"neon", "halloween"} <= set(world.THEMES)
for theme in world.THEMES:
    app.set_theme(theme, save=False)
    app.set_mood("idle"); app.show = ""
    app.intro = {"kind": "undress" if theme == "none" else "dress", "f": 0, "len": 20 if theme == "none" else 36}
    frames(40)                                   # dressing up, then the theme's intro show
    assert app.intro is None and app.costume_theme == theme, (theme, app.costume_theme)
    frames(90)
    for show, length in world.THEME_SHOWS.get(theme, {}).items():
        app.show, app.show_frame = show, 0
        frames(length)
app.show = ""
app.devices.dev = {"headphones": True, "gamepad": True, "gadget": True}
frames(60)                                       # puts the headphones on, then picks the pad up
assert app.worn_phones and app.pad_held
app.devices.music = True
frames(20)
app.devices.dev = {"headphones": False, "gamepad": False, "gadget": False}
frames(60)
assert not app.worn_phones and not app.pad_held
app.drag = (0, 0, 0, 0, True, 0, 0)
frames(20)
app.drag = None
# The autostart shortcut can be made (into a temp folder, not the real Startup folder).
lnk = os.path.join(tempfile.mkdtemp(), "Claudik.lnk")
ov.make_shortcut(lnk)
assert os.path.exists(lnk)

# A picked theme is saved and comes back on the next start.
app.set_theme("winter")
assert app.load_cfg()["theme"] == "winter"
# An extra redraw while dragging must not advance the falling particles.
before = [p[:2] for p in app.weather.parts]
app.redraw(move=False)
assert [p[:2] for p in app.weather.parts] == before
app.devices.stop()
app.root.destroy()
after_cfg = open(REAL_CONFIG, encoding="utf-8").read() if os.path.exists(REAL_CONFIG) else None
assert after_cfg == before_cfg, "the test changed the user's config.json"

print("ok")
