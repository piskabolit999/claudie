"""PC actions and intent recognition for Claudie.

Handles desktop actions: creating folders, opening apps, opening folders/URLs,
and controlling media on Windows with full Program Files search and fuzzy typo matching.
"""
import ctypes
from ctypes import wintypes
import difflib
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import webbrowser
import winreg

# Special Windows folder paths
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
DOCUMENTS = os.path.join(os.path.expanduser("~"), "Documents")

CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "є": "ye",
    "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "yi", "й": "y", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "",
    "ю": "yu", "я": "ya", "ы": "y", "э": "e", "ъ": "", "ё": "yo",
}


def transliterate(s: str) -> str:
    """Convert Ukrainian/Russian Cyrillic to phonetic Latin."""
    return "".join(CYR_TO_LAT.get(c, c) for c in (s or "").lower()).strip()


# Common aliases mapping user input variants to canonical name and protocol
KNOWN_APPS = {
    "telegram": {"name": "Telegram", "exe": "telegram.exe", "proto": "tg://"},
    "телеграм": {"name": "Telegram", "exe": "telegram.exe", "proto": "tg://"},
    "телега": {"name": "Telegram", "exe": "telegram.exe", "proto": "tg://"},
    "тг": {"name": "Telegram", "exe": "telegram.exe", "proto": "tg://"},
    "steam": {"name": "Steam", "exe": "steam.exe", "proto": "steam://"},
    "стім": {"name": "Steam", "exe": "steam.exe", "proto": "steam://"},
    "стим": {"name": "Steam", "exe": "steam.exe", "proto": "steam://"},
    "discord": {"name": "Discord", "exe": "Discord.exe", "proto": "discord://"},
    "діскорд": {"name": "Discord", "exe": "Discord.exe", "proto": "discord://"},
    "дискорд": {"name": "Discord", "exe": "Discord.exe", "proto": "discord://"},
    "дс": {"name": "Discord", "exe": "Discord.exe", "proto": "discord://"},
    "spotify": {"name": "Spotify", "exe": "Spotify.exe", "proto": "spotify://"},
    "спотіфай": {"name": "Spotify", "exe": "Spotify.exe", "proto": "spotify://"},
    "спотифай": {"name": "Spotify", "exe": "Spotify.exe", "proto": "spotify://"},
    "спотік": {"name": "Spotify", "exe": "Spotify.exe", "proto": "spotify://"},
    "calc": {"name": "Калькулятор", "exe": "calc.exe"},
    "calculator": {"name": "Калькулятор", "exe": "calc.exe"},
    "калькулятор": {"name": "Калькулятор", "exe": "calc.exe"},
    "кальк": {"name": "Калькулятор", "exe": "calc.exe"},
    "notepad": {"name": "Блокнот", "exe": "notepad.exe"},
    "блокнот": {"name": "Блокнот", "exe": "notepad.exe"},
    "блокнотик": {"name": "Блокнот", "exe": "notepad.exe"},
    "terminal": {"name": "Термінал", "exe": "wt.exe", "fallback": "powershell.exe"},
    "термінал": {"name": "Термінал", "exe": "wt.exe", "fallback": "powershell.exe"},
    "терминал": {"name": "Термінал", "exe": "wt.exe", "fallback": "powershell.exe"},
    "консоль": {"name": "PowerShell", "exe": "powershell.exe"},
    "powershell": {"name": "PowerShell", "exe": "powershell.exe"},
    "cmd": {"name": "Командний рядок", "exe": "cmd.exe"},
    "paint": {"name": "Paint", "exe": "mspaint.exe"},
    "пейнт": {"name": "Paint", "exe": "mspaint.exe"},
    "паінт": {"name": "Paint", "exe": "mspaint.exe"},
    "taskmgr": {"name": "Диспетчер завдань", "exe": "taskmgr.exe"},
    "диспетчер": {"name": "Диспетчер завдань", "exe": "taskmgr.exe"},
    "диспетчер задач": {"name": "Диспетчер завдань", "exe": "taskmgr.exe"},
    "explorer": {"name": "Провідник", "exe": "explorer.exe"},
    "провідник": {"name": "Провідник", "exe": "explorer.exe"},
    "проводник": {"name": "Провідник", "exe": "explorer.exe"},
    "code": {"name": "Visual Studio Code", "exe": "code.cmd", "fallback": "code.exe"},
    "vs code": {"name": "Visual Studio Code", "exe": "code.cmd", "fallback": "code.exe"},
    "vscode": {"name": "Visual Studio Code", "exe": "code.cmd", "fallback": "code.exe"},
    "вскод": {"name": "Visual Studio Code", "exe": "code.cmd", "fallback": "code.exe"},
    "chrome": {"name": "Google Chrome", "exe": "chrome.exe"},
    "хром": {"name": "Google Chrome", "exe": "chrome.exe"},
    "edge": {"name": "Microsoft Edge", "exe": "msedge.exe"},
    "едж": {"name": "Microsoft Edge", "exe": "msedge.exe"},
    "opera": {"name": "Opera", "exe": "opera.exe"},
    "опера": {"name": "Opera", "exe": "opera.exe"},
    "браузер": {"name": "Браузер", "exe": "msedge.exe", "fallback": "chrome.exe"},
    "browser": {"name": "Браузер", "exe": "msedge.exe", "fallback": "chrome.exe"},
    "canva": {"name": "Canva", "exe": "Canva.exe"},
    "канва": {"name": "Canva", "exe": "Canva.exe"},
    "anydesk": {"name": "AnyDesk", "exe": "AnyDesk.exe"},
    "енідіск": {"name": "AnyDesk", "exe": "AnyDesk.exe"},
    "анідеск": {"name": "AnyDesk", "exe": "AnyDesk.exe"},
    "cheat engine": {"name": "Cheat Engine", "exe": "Cheat Engine.exe"},
    "чит енджин": {"name": "Cheat Engine", "exe": "Cheat Engine.exe"},
    "everything": {"name": "Everything", "exe": "Everything.exe"},
    "burp suite": {"name": "Burp Suite", "exe": "BurpSuite.exe"},
    "бурп": {"name": "Burp Suite", "exe": "BurpSuite.exe"},
}

KNOWN_URLS = {
    "youtube": "https://youtube.com",
    "ютуб": "https://youtube.com",
    "ютубчик": "https://youtube.com",
    "github": "https://github.com",
    "гітхаб": "https://github.com",
    "гитхаб": "https://github.com",
    "google": "https://google.com",
    "гугл": "https://google.com",
    "twitch": "https://twitch.tv",
    "твіч": "https://twitch.tv",
    "твич": "https://twitch.tv",
    "netflix": "https://netflix.com",
    "нетфлікс": "https://netflix.com",
}

# Cache for scanned applications
_APP_CATALOG: dict[str, tuple[str, str]] = {}
_LAST_SCAN_TIME: float = 0.0


def scan_installed_applications() -> dict[str, tuple[str, str]]:
    """Scan Start Menu, Program Files, AppData for installed apps.
    Returns dict: clean_key -> (display_name, target_path)."""
    global _APP_CATALOG, _LAST_SCAN_TIME
    now = time.time()
    if _APP_CATALOG and (now - _LAST_SCAN_TIME < 300):
        return _APP_CATALOG

    catalog: dict[str, tuple[str, str]] = {}

    # 1. Start Menu Shortcuts (.lnk files)
    start_dirs = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    ]
    for sd in start_dirs:
        if not os.path.exists(sd):
            continue
        for root, _, files in os.walk(sd):
            for f in files:
                if f.lower().endswith(".lnk"):
                    stem = f[:-4].strip()
                    clean = re.sub(r"[\(\)\d\.\-_]+", " ", stem).strip().lower()
                    catalog[clean] = (stem, os.path.join(root, f))
                    catalog[stem.lower()] = (stem, os.path.join(root, f))

    # 2. LocalAppData Programs
    local_prog = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")
    if os.path.exists(local_prog):
        for entry in os.listdir(local_prog):
            full = os.path.join(local_prog, entry)
            if os.path.isdir(full):
                try:
                    for f in os.listdir(full):
                        if f.lower().endswith(".exe") and not any(k in f.lower() for k in ("unins", "update", "crash")):
                            catalog[entry.lower()] = (entry, os.path.join(full, f))
                            catalog[f[:-4].lower()] = (f[:-4], os.path.join(full, f))
                except Exception:
                    pass

    # 3. WindowsApps
    win_apps = os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WindowsApps")
    if os.path.exists(win_apps):
        try:
            for f in os.listdir(win_apps):
                if f.lower().endswith(".exe"):
                    stem = f[:-4]
                    catalog[stem.lower()] = (stem, os.path.join(win_apps, f))
        except Exception:
            pass

    # 4. Program Files & Program Files (x86)
    program_dirs = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]
    for pd in program_dirs:
        if not os.path.exists(pd):
            continue
        try:
            for root, dirs, files in os.walk(pd):
                depth = root[len(pd):].count(os.sep)
                if depth > 3:
                    dirs.clear()
                    continue
                for f in files:
                    if f.lower().endswith(".exe"):
                        stem = f[:-4].lower()
                        if not any(k in stem for k in ("unins", "update", "crash", "reporter", "helper", "elevat", "install", "setup")):
                            if stem not in catalog:
                                catalog[stem] = (f[:-4], os.path.join(root, f))
        except Exception:
            pass

    _APP_CATALOG = catalog
    _LAST_SCAN_TIME = now
    return catalog


def resolve_app_target(query: str) -> tuple[str | None, str, bool]:
    """Find the best matching application for user query using exact, substring and fuzzy matching.
    Returns: (target_path_or_proto, display_name, is_fuzzy)."""
    q = query.lower().strip()
    q = re.sub(r"^(?:програму|додаток|приложение|app|прогу|файл)\s+", "", q).strip(' \t\r\n:"\'')
    if not q:
        return None, "", False

    # Check default browser if requested
    if q in ("браузер", "browser", "веб-браузер", "веб браузер"):
        b_info = get_default_browser()
        if b_info.get("exe"):
            return b_info["exe"], b_info["name"], False

    # 1. Check Known Apps exact match
    if q in KNOWN_APPS:
        item = KNOWN_APPS[q]
        name = item.get("name", q.capitalize())
        target = item.get("proto") or item.get("exe")
        return target, name, False

    # 2. Check Installed Catalog exact match
    cat = scan_installed_applications()
    if q in cat:
        display, target = cat[q]
        return target, display, False

    # 3. Transliterated match
    q_lat = transliterate(q)
    if q_lat in KNOWN_APPS:
        item = KNOWN_APPS[q_lat]
        return item.get("proto") or item.get("exe"), item.get("name", q_lat.capitalize()), True

    if q_lat in cat:
        display, target = cat[q_lat]
        return target, display, True

    # 4. Substring match
    for k, v in cat.items():
        if len(q) >= 3 and (q == k or q in k or k in q):
            display, target = v
            return target, display, True

    for k, item in KNOWN_APPS.items():
        if len(q) >= 3 and (q == k or q in k or k in q):
            name = item.get("name", k.capitalize())
            target = item.get("proto") or item.get("exe")
            return target, name, True

    # 5. Fuzzy matching with difflib
    best_cand = None
    best_score = 0.0

    # Match against known apps
    for k, item in KNOWN_APPS.items():
        s1 = difflib.SequenceMatcher(None, q, k).ratio()
        s2 = difflib.SequenceMatcher(None, q_lat, transliterate(k)).ratio()
        s = max(s1, s2)
        if s > best_score:
            best_score = s
            name = item.get("name", k.capitalize())
            target = item.get("proto") or item.get("exe")
            best_cand = (target, name, True)

    # Match against catalog
    for k, v in cat.items():
        s1 = difflib.SequenceMatcher(None, q, k).ratio()
        s2 = difflib.SequenceMatcher(None, q_lat, k).ratio()
        s = max(s1, s2)
        if s > best_score:
            best_score = s
            display, target = v
            best_cand = (target, display, True)

    if best_score >= 0.60 and best_cand:
        return best_cand

    return None, q, False


def launch_target(target: str, display_name: str = "") -> bool:
    """Launch target (protocol, .lnk file, or .exe path)."""
    if not target:
        return False

    # Protocol e.g. tg://, steam://
    if "://" in target:
        try:
            os.startfile(target)
            return True
        except Exception:
            pass

    # Windows shortcut or executable
    if os.path.exists(target):
        try:
            os.startfile(target)
            return True
        except Exception:
            try:
                subprocess.Popen([target])
                return True
            except Exception:
                pass

    # Check which in PATH
    w = shutil.which(target) or shutil.which(target + ".exe")
    if w:
        try:
            subprocess.Popen([w])
            return True
        except Exception:
            pass

    # Fallback to shell start
    try:
        subprocess.Popen(f'start "" "{target}"', shell=True)
        return True
    except Exception:
        return False


def send_media_key(key_code: int, times: int = 1) -> None:
    """Send virtual key event via user32."""
    try:
        u = ctypes.windll.user32
        for _ in range(times):
            u.keybd_event(key_code, 0, 0, 0)
            u.keybd_event(key_code, 0, 2, 0)
    except Exception:
        pass


def create_user_folder(name: str = "", location: str = "", cwd: str | None = None) -> tuple[str, str, str]:
    """Create a folder on requested or default location.
    Returns (created_full_path, location_label, folder_name)."""
    loc_lower = (location or "").lower()
    if any(k in loc_lower for k in ("завантажен", "download", "загрузк")):
        base = DOWNLOADS
        loc_label = "Завантаженнях"
    elif any(k in loc_lower for k in ("документ", "document")):
        base = DOCUMENTS
        loc_label = "Документах"
    elif any(k in loc_lower for k in ("проект", "проєкт", "project")) and cwd and os.path.exists(cwd):
        base = cwd
        loc_label = "папці проекту"
    else:
        base = DESKTOP
        loc_label = "робочому столі"

    os.makedirs(base, exist_ok=True)

    folder_name = name.strip() if name else ""
    if not folder_name:
        folder_name = "Нова папка"
        candidate = os.path.join(base, folder_name)
        k = 2
        while os.path.exists(candidate):
            folder_name = f"Нова папка ({k})"
            candidate = os.path.join(base, folder_name)
            k += 1

    full_path = os.path.join(base, folder_name)
    os.makedirs(full_path, exist_ok=True)
    try:
        os.startfile(full_path)
    except Exception:
        pass
    return full_path, loc_label, folder_name


# Windows Default Browser and Window Management helpers
_DEFAULT_BROWSER_CACHE: dict[str, str] = {}
_DEFAULT_BROWSER_TIME: float = 0.0


def get_default_browser() -> dict[str, str]:
    """Auto-detect Windows default browser from Registry (HKCU UserChoice).
    Returns dict: {'name': str, 'exe': str, 'prog_id': str, 'cmd': str}."""
    global _DEFAULT_BROWSER_CACHE, _DEFAULT_BROWSER_TIME
    now = time.time()
    if _DEFAULT_BROWSER_CACHE and (now - _DEFAULT_BROWSER_TIME < 60):
        return _DEFAULT_BROWSER_CACHE

    prog_id = None
    for sub in (
        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
    ):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as key:
                prog_id, _ = winreg.QueryValueEx(key, "ProgId")
                if prog_id:
                    break
        except Exception:
            pass

    cmd = ""
    exe = ""
    if prog_id:
        roots = [winreg.HKEY_CLASSES_ROOT, winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
        for r in roots:
            for p in (rf"{prog_id}\shell\open\command", rf"Software\Classes\{prog_id}\shell\open\command"):
                try:
                    with winreg.OpenKey(r, p) as key:
                        cmd, _ = winreg.QueryValueEx(key, "")
                        if cmd:
                            break
                except Exception:
                    pass
            if cmd:
                break

    if cmd:
        m = re.search(r'"([^"]+\.exe)"', cmd, re.IGNORECASE) or re.search(r'([^\s"]+\.exe)', cmd, re.IGNORECASE)
        if m:
            exe = m.group(1)

    if not exe or not os.path.exists(exe):
        candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
            shutil.which("msedge.exe"),
            shutil.which("chrome.exe"),
            shutil.which("firefox.exe"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                exe = c
                break

    name = "Браузер"
    low = ((prog_id or "") + " " + (exe or "")).lower()
    if "edge" in low or "msedge" in low:
        name = "Microsoft Edge"
    elif "chrome" in low:
        name = "Google Chrome"
    elif "firefox" in low:
        name = "Mozilla Firefox"
    elif "opera" in low:
        name = "Opera"
    elif "brave" in low:
        name = "Brave"
    elif "vivaldi" in low:
        name = "Vivaldi"
    elif exe:
        name = os.path.splitext(os.path.basename(exe))[0].capitalize()

    res = {"name": name, "exe": exe or "", "prog_id": prog_id or "", "cmd": cmd or ""}
    _DEFAULT_BROWSER_CACHE = res
    _DEFAULT_BROWSER_TIME = now
    return res


def open_in_browser(target: str = "") -> bool:
    """Open a URL, search query, or empty browser in the user's default browser."""
    target = (target or "").strip()
    b_info = get_default_browser()
    exe = b_info.get("exe")

    if not target:
        if exe and os.path.exists(exe):
            try:
                subprocess.Popen([exe])
                return True
            except Exception:
                pass
        webbrowser.open("about:blank")
        return True

    if not (target.startswith("http://") or target.startswith("https://")):
        if re.match(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/.*)?$", target):
            url = "https://" + target
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(target)}"
    else:
        url = target

    if exe and os.path.exists(exe):
        try:
            subprocess.Popen([exe, url])
            return True
        except Exception:
            pass

    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def open_web_search(query: str) -> bool:
    """Search Google in the default browser."""
    q = (query or "").strip()
    if not q:
        return open_in_browser("")
    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}"
    return open_in_browser(url)


def new_browser_tab() -> tuple[bool, str]:
    """Open a new tab in browser (Ctrl + T) or launch default browser."""
    try:
        u = ctypes.windll.user32
        u.keybd_event(0x11, 0, 0, 0)
        u.keybd_event(0x54, 0, 0, 0)
        u.keybd_event(0x54, 0, 2, 0)
        u.keybd_event(0x11, 0, 2, 0)
        return True, "Нову вкладку відкрито. 🌐"
    except Exception:
        open_in_browser("")
        return True, "Браузер відкрито. 🌐"


def close_tab() -> tuple[bool, str]:
    """Close the current tab (Ctrl + W)."""
    try:
        u = ctypes.windll.user32
        u.keybd_event(0x11, 0, 0, 0)
        u.keybd_event(0x57, 0, 0, 0)
        u.keybd_event(0x57, 0, 2, 0)
        u.keybd_event(0x11, 0, 2, 0)
        return True, "Вкладку закрито. ✖️"
    except Exception as e:
        return False, f"Помилка закриття вкладки: {e}"


def close_active_window(active_title: str = "", active_pname: str = "") -> tuple[bool, str]:
    """Close the currently active user window gracefully."""
    u = ctypes.windll.user32
    my_pid = os.getpid()

    def get_title(h):
        length = u.GetWindowTextLengthW(h)
        if not length:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        u.GetWindowTextW(h, buf, length + 1)
        return buf.value.strip()

    def get_pid(h):
        p = ctypes.c_ulong()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        return p.value

    target_hwnd = 0
    target_title = active_title.strip() if active_title else ""

    fg = u.GetForegroundWindow()
    if fg and u.IsWindow(fg) and u.IsWindowVisible(fg) and get_pid(fg) != my_pid:
        target_hwnd = fg
        if not target_title:
            target_title = get_title(fg)

    if not target_hwnd:
        curr = fg or u.GetTopWindow(0)
        count = 0
        while curr and count < 100:
            count += 1
            if u.IsWindowVisible(curr) and not u.IsIconic(curr):
                p = get_pid(curr)
                if p != my_pid and p != 0:
                    t = get_title(curr)
                    if t and t not in ("Program Manager", "Settings", "Windows Shell Experience Host"):
                        target_hwnd = curr
                        if not target_title:
                            target_title = t
                        break
            curr = u.GetWindow(curr, 2)  # GW_HWNDNEXT = 2

    if target_hwnd:
        u.PostMessageW(target_hwnd, 0x0010, 0, 0)  # WM_CLOSE
        label = f" «{target_title}»" if target_title else " активне вікно"
        return True, f"Закрив{label}. ✖️"

    # Fallback Alt+F4
    try:
        u.keybd_event(0x12, 0, 0, 0)  # VK_MENU (Alt)
        u.keybd_event(0x73, 0, 0, 0)  # VK_F4
        u.keybd_event(0x73, 0, 2, 0)
        u.keybd_event(0x12, 0, 2, 0)
        return True, "Закрив активне вікно. ✖️"
    except Exception:
        pass

    if active_pname and not any(k in active_pname.lower() for k in ("python", "explorer", "claud")):
        try:
            subprocess.run(f'taskkill /IM "{active_pname}"', shell=True, capture_output=True)
            return True, f"Закрив вікно {active_pname}. ✖️"
        except Exception:
            pass

    return False, "Не вдалося визначити активне вікно для закриття. 🤔"


def _close_process_gracefully(exe_name: str, title_pattern: str = "") -> bool:
    """Send WM_CLOSE to matching windows and graceful taskkill signal."""
    success = False
    u = ctypes.windll.user32
    k = ctypes.windll.kernel32
    my_pid = os.getpid()

    try:
        def enum_cb(hwnd, lparam):
            nonlocal success
            if not u.IsWindowVisible(hwnd):
                return True
            pid = ctypes.c_ulong()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == my_pid or pid.value == 0:
                return True
            length = u.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                u.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()

            pname = ""
            hproc = k.OpenProcess(0x1000, False, pid.value)
            if hproc:
                pbuf = ctypes.create_unicode_buffer(512)
                sz = ctypes.c_ulong(512)
                k.QueryFullProcessImageNameW(hproc, 0, pbuf, ctypes.byref(sz))
                k.CloseHandle(hproc)
                pname = os.path.basename(pbuf.value).lower()

            matched = False
            if exe_name and pname == exe_name.lower():
                matched = True
            elif title_pattern and title and (title_pattern.lower() in title.lower()):
                matched = True

            if matched:
                u.PostMessageW(hwnd, 0x0010, 0, 0)
                success = True
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        u.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

    if exe_name:
        try:
            res = subprocess.run(f'taskkill /IM "{exe_name}"', shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                success = True
        except Exception:
            pass

    return success


def close_app_by_name(query: str) -> tuple[bool, str]:
    """Close a specific application by name, window title, or process."""
    q = query.strip().lower()
    q = re.sub(r"^(?:програму|додаток|приложение|app|прогу|вікно|процес)\s+", "", q).strip(' \t\r\n:"\'')
    if not q:
        return False, "Вкажи назву програми, яку закрити."

    if q in ("браузер", "browser", "веб-браузер", "веб браузер"):
        b_info = get_default_browser()
        exe = os.path.basename(b_info.get("exe", "msedge.exe"))
        name = b_info.get("name", "Браузер")
        _close_process_gracefully(exe)
        return True, f"Закрив «{name}». ✖️"

    target, display_name, _ = resolve_app_target(q)
    exe_name = ""
    if target:
        if target.endswith(".exe"):
            exe_name = os.path.basename(target)
        elif target.endswith(".lnk"):
            exe_name = os.path.basename(target)[:-4] + ".exe"

    if not display_name:
        display_name = q.capitalize()

    if not exe_name:
        for k, item in KNOWN_APPS.items():
            if q == k or q in k:
                exe_name = item.get("exe") or ""
                display_name = item.get("name", display_name)
                break

    if not exe_name:
        candidate = q if q.endswith(".exe") else f"{q}.exe"
        exe_name = candidate

    _close_process_gracefully(exe_name, title_pattern=q)
    return True, f"Закрив «{display_name}». ✖️"


def handle_local_intent(
    text: str, cwd: str | None = None, active_title: str = "", active_pname: str = ""
) -> tuple[bool, str | None]:
    """Check if user query is a direct PC command.
    Returns (handled: bool, mascot_reply: str | None)."""
    t = text.strip()
    low = t.lower()

    # 1. CREATE FOLDER
    create_match = re.search(
        r"(?:створ(?:и|ить|яй)?|создай(?:те)?|зроби|create|make)\s+(?:нову\s+|новую\s+|new\s+)?(?:папку|директорію|директорию|каталог|folder|dir)(.*)",
        t, re.IGNORECASE,
    )
    if create_match:
        rest = create_match.group(1).strip()
        loc = ""
        # Check location mentions
        if re.search(r"(?:на\s+)?(?:робоч(?:ому|ий)\s+стол(?:і|е)|desktop|десктоп)", rest, re.IGNORECASE):
            loc = "desktop"
            rest = re.sub(r"(?:на\s+)?(?:робоч(?:ому|ий)\s+стол(?:і|е)|desktop|десктоп)", "", rest, flags=re.IGNORECASE).strip()
        elif re.search(r"(?:в\s+)?(?:завантаженн(?:ях|я)|downloads|загрузк(?:ах|и))", rest, re.IGNORECASE):
            loc = "downloads"
            rest = re.sub(r"(?:в\s+)?(?:завантаженн(?:ях|я)|downloads|загрузк(?:ах|и))", "", rest, flags=re.IGNORECASE).strip()
        elif re.search(r"(?:в\s+)?(?:документ(?:ах|и)|documents)", rest, re.IGNORECASE):
            loc = "documents"
            rest = re.sub(r"(?:в\s+)?(?:документ(?:ах|и)|documents)", "", rest, flags=re.IGNORECASE).strip()
        elif re.search(r"(?:в\s+)?(?:проект(?:і|и)|проєкт(?:і|и)|project)", rest, re.IGNORECASE):
            loc = "project"
            rest = re.sub(r"(?:в\s+)?(?:проект(?:і|и)|проєкт(?:і|и)|project)", "", rest, flags=re.IGNORECASE).strip()

        # Extract clean folder name
        name = re.sub(r"^(?:під назвою|з назвою|с именем|named|called|ім'я|имя|\"|\')+", "", rest, flags=re.IGNORECASE).strip(' \t\r\n:"\'')
        path, loc_label, final_name = create_user_folder(name=name, location=loc, cwd=cwd)
        return True, f"Папку «{final_name}» створено на {loc_label}. 📁"

    # 2. OPEN SPECIAL FOLDERS
    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:робоч(?:ий|ого)\s+стіл|рабочий\s+стол|desktop|десктоп)", low):
        try:
            os.startfile(DESKTOP)
        except Exception:
            pass
        return True, "Робочий стіл відкрито. 🖥️"

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:завантаженн(?:я|ь)|downloads|загрузк(?:и|ек))", low):
        try:
            os.startfile(DOWNLOADS)
        except Exception:
            pass
        return True, "Папку Завантаження відкрито. 📂"

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:документ(?:и|ів)|documents)", low):
        try:
            os.startfile(DOCUMENTS)
        except Exception:
            pass
        return True, "Папку Документи відкрито. 📄"

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:проект(?:у|а)?|проєкт(?:у|а)?|project|файли)", low):
        folder = cwd if (cwd and os.path.exists(cwd)) else DESKTOP
        try:
            os.startfile(folder)
        except Exception:
            pass
        return True, "Папку проекту відкрито. 📁"

    # 3. DEFAULT BROWSER QUERY
    if any(k in low for k in ("браузер по дефолту", "браузер за замовчуванням", "браузер по замовчуванню", "браузер по умолчанию", "дефолтний браузер", "дефолтный браузер")) or (
        re.search(r"(?:який|какой|що|what).*(?:браузер|browser)", low) and not any(k in low for k in ("відкрий", "запусти", "закрий", "скачай"))
    ):
        b_info = get_default_browser()
        return True, f"Твій браузер за замовчуванням — {b_info['name']}. 🌐"

    # 4. WINDOW & TAB CLOSING
    if re.search(r"^(?:закрий|закрити|close)\s+(?:цю\s+)?(?:вкладку|таб|tab)$", low):
        _, reply = close_tab()
        return True, reply

    if re.search(r"^(?:закрий|закрити|close)\s+(?:це\s+|поточне\s+|активне\s+)?вікно$", low) or re.search(r"^(?:закрий|закрити|close)\s+це$", low):
        _, reply = close_active_window(active_title=active_title, active_pname=active_pname)
        return True, reply

    if re.search(r"^(?:закрий|закрити|close|сховай)\s+(?:чат|діалог|вікно чату)$", low) or low in ("закрийся", "сховайся", "закрий чат"):
        return True, "Ховаю чат. 👋<!--ACTION:chat:close-->"

    close_app_m = re.search(r"^(?:закрий|закрити|close|вигрузи|закрий програму|закрий процес)\s+(.+)", low)
    if close_app_m:
        app_target = close_app_m.group(1).strip()
        if app_target not in ("вкладку", "таб", "tab", "вікно", "це вікно", "активне вікно", "поточне вікно", "чат"):
            _, reply = close_app_by_name(app_target)
            return True, reply

    # 5. BROWSER NAVIGATION & WEB SEARCH
    if re.search(r"^(?:нова вкладка|відкрий нову вкладку|новий таб|new tab)$", low):
        _, reply = new_browser_tab()
        return True, reply

    search_m = re.search(r"^(?:загугли|гугли|пошукай в інтернеті|пошукай в гуглі|знайди в інтернеті|знайди в гуглі|search|пошукай)\s+(.+)", low)
    if search_m:
        query = search_m.group(1).strip()
        open_web_search(query)
        return True, f"Шукаю в браузері: «{query}». 🌐"

    if low.startswith("знайди "):
        rest = t[7:].strip()
        if rest and not any(rest.lower().startswith(k) for k in ("папку", "файл", "програму", "додаток")):
            open_web_search(rest)
            return True, f"Шукаю в браузері: «{rest}». 🌐"

    if re.search(r"^(?:відкрий|відкрити|запусти|open)\s+(?:браузер|browser)$", low):
        b_info = get_default_browser()
        open_in_browser("")
        return True, f"Відкрив браузер {b_info['name']}. 🌐"

    url_m = re.search(r"^(?:відкрий|відкрити|open)\s+(https?://\S+|www\.\S+|\S+\.(?:com|org|net|io|ua|tv|gov|edu|dev)\S*)$", low)
    if url_m:
        u_target = url_m.group(1).strip()
        open_in_browser(u_target)
        return True, "Відкрив посилання в браузері. 🌐"

    # 6. OPEN WEBSITES
    for kw, url in KNOWN_URLS.items():
        if re.search(rf"(?:відкрий|открой|open)\s+{kw}\b", low):
            open_in_browser(url)
            name_cap = kw.capitalize()
            return True, f"{name_cap} відкрито. 🚀"

    # 7. OPEN / LAUNCH APPS (with Program Files scanning & fuzzy matching)
    open_app_m = re.search(r"^(?:відкрий|відкрити|открой|открыть|open|запусти|запустити|запустить|launch|start)\s+(.+)", low)
    if open_app_m:
        app_query = open_app_m.group(1).strip()
        target, display_name, is_fuzzy = resolve_app_target(app_query)
        if target:
            launched = launch_target(target, display_name)
            if launched:
                if is_fuzzy:
                    return True, f"Малося на увазі «{display_name}» — запущено. 🚀"
                return True, f"Запущено {display_name}. ⚡"
        else:
            return True, f"Програму «{app_query}» не знайдено серед встановлених. 🤔"

    # 5. MEDIA CONTROLS
    if re.search(r"^(?:пауза|постав на паузу|стоп музика|пауза музика|pause)$", low) or "постав музику на паузу" in low:
        send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE
        return True, "Відтворення призупинено. ⏸️"

    if re.search(r"^(?:плей|продовж|продовжити|play|resume)$", low) or "увімкни музику" in low or "включи музику" in low:
        send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE
        return True, "Відтворення відновлено. 🎵"

    if "голосніше" in low or "добав звук" in low or "додай звук" in low or "volume up" in low:
        send_media_key(0xAF, 4)  # VK_VOLUME_UP
        return True, "Гучність збільшено. 🔊"

    if "тихіше" in low or "зменш звук" in low or "убав звук" in low or "volume down" in low:
        send_media_key(0xAE, 4)  # VK_VOLUME_DOWN
        return True, "Гучність зменшено. 🔉"

    if "вимкни звук" in low or "без звуку" in low or "мут" in low or "mute" in low:
        send_media_key(0xAD)  # VK_VOLUME_MUTE
        return True, "Звук вимкнено. 🔇"

    if "наступний трек" in low or "наступна пісня" in low or "next track" in low or "переключи" in low:
        send_media_key(0xB0)  # VK_MEDIA_NEXT_TRACK
        return True, "Перемкнуто на наступний трек. ⏭️"

    return False, None


def execute_action_tag(tag: str, cwd: str | None = None) -> bool:
    """Execute an action extracted from LLM reply (e.g. create_folder:..., app:..., url:...)."""
    tag = tag.strip()
    if not tag:
        return False
    try:
        if tag.startswith("create_folder:"):
            arg = tag[14:].strip()
            parts = arg.split("|", 1)
            name = parts[0].strip() if parts else ""
            loc = parts[1].strip() if len(parts) > 1 else ""
            create_user_folder(name=name, location=loc, cwd=cwd)
            return True

        if tag.startswith("open_path:"):
            target = tag[10:].strip().lower()
            if "desktop" in target:
                os.startfile(DESKTOP)
            elif "downloads" in target:
                os.startfile(DOWNLOADS)
            elif "documents" in target:
                os.startfile(DOCUMENTS)
            elif os.path.exists(target):
                os.startfile(target)
            else:
                os.startfile(cwd if cwd and os.path.exists(cwd) else DESKTOP)
            return True

        if tag in ("open_folder", "app:explorer"):
            folder = cwd if (cwd and os.path.exists(cwd)) else DESKTOP
            os.startfile(folder)
            return True

        if tag == "close_window":
            close_active_window()
            return True

        if tag == "close_tab":
            close_tab()
            return True

        if tag.startswith("close_app:"):
            app_name = tag[10:].strip()
            close_app_by_name(app_name)
            return True

        if tag == "new_tab":
            new_browser_tab()
            return True

        if tag.startswith("browser_search:"):
            query = tag[15:].strip()
            open_web_search(query)
            return True

        if tag.startswith("browser_open:"):
            url = tag[13:].strip()
            open_in_browser(url)
            return True

        if tag.startswith("url:"):
            url = tag[4:].strip()
            open_in_browser(url)
            return True

        if tag.startswith("app:"):
            app_name = tag[4:].strip()
            target, display_name, _ = resolve_app_target(app_name)
            if target:
                return launch_target(target, display_name)
            return launch_target(app_name, app_name)

        if tag.startswith("media:"):
            sub = tag[6:].strip().lower()
            vk_map = {
                "play_pause": 0xB3,
                "pause": 0xB3,
                "play": 0xB3,
                "mute": 0xAD,
                "volume_up": 0xAF,
                "volume_down": 0xAE,
                "next": 0xB0,
                "prev": 0xB1,
            }
            vk = vk_map.get(sub)
            if vk:
                times = 4 if sub in ("volume_up", "volume_down") else 1
                send_media_key(vk, times)
                return True

        if tag.startswith("cmd:"):
            cmd = tag[4:].strip()
            subprocess.Popen(cmd, shell=True)
            return True

    except Exception:
        pass
    return False
