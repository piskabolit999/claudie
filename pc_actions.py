"""PC actions and intent recognition for Claudie.

Handles desktop actions: creating folders, opening apps, opening folders/URLs,
and controlling media on Windows with full Program Files search and fuzzy typo matching.
"""
import ctypes
import difflib
import os
import re
import shutil
import subprocess
import time
import webbrowser

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


def handle_local_intent(text: str, cwd: str | None = None) -> tuple[bool, str | None]:
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
        return True, f"Створив папку «{final_name}» на {loc_label}! 📁✨"

    # 2. OPEN SPECIAL FOLDERS
    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:робоч(?:ий|ого)\s+стіл|рабочий\s+стол|desktop|десктоп)", low):
        try:
            os.startfile(DESKTOP)
        except Exception:
            pass
        return True, "Відкрив робочий стіл! 🖥️"

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:завантаженн(?:я|ь)|downloads|загрузк(?:и|ек))", low):
        try:
            os.startfile(DOWNLOADS)
        except Exception:
            pass
        return True, "Відкрив папку Завантаження! 📂"

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:документ(?:и|ів)|documents)", low):
        try:
            os.startfile(DOCUMENTS)
        except Exception:
            pass
        return True, "Відкрив Документи! 📄"

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:проект(?:у|а)?|проєкт(?:у|а)?|project|файли)", low):
        folder = cwd if (cwd and os.path.exists(cwd)) else DESKTOP
        try:
            os.startfile(folder)
        except Exception:
            pass
        return True, "Ось файли проекту! 📁"

    # 3. OPEN WEBSITES
    for kw, url in KNOWN_URLS.items():
        if re.search(rf"(?:відкрий|открой|open)\s+{kw}\b", low):
            webbrowser.open(url)
            name_cap = kw.capitalize()
            return True, f"Відкриваю {name_cap}! 🚀"

    # 4. OPEN / LAUNCH APPS (with Program Files scanning & fuzzy matching)
    open_app_m = re.search(r"^(?:відкрий|відкрити|открой|открыть|open|запусти|запустити|запустить|launch|start)\s+(.+)", low)
    if open_app_m:
        app_query = open_app_m.group(1).strip()
        target, display_name, is_fuzzy = resolve_app_target(app_query)
        if target:
            launched = launch_target(target, display_name)
            if launched:
                if is_fuzzy:
                    return True, f"Схоже, ти мав на увазі «{display_name}» — відкриваю! 🚀"
                return True, f"Запускаю {display_name}! ⚡"
        else:
            return True, f"Не знайшов програму «{app_query}» у папках з програмами. Перевір назву чи шлях! 🤔"

    # 5. MEDIA CONTROLS
    if re.search(r"^(?:пауза|постав на паузу|стоп музика|пауза музика|pause)$", low) or "постав музику на паузу" in low:
        send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE
        return True, "Поставив на паузу! ⏸️"

    if re.search(r"^(?:плей|продовж|продовжити|play|resume)$", low) or "увімкни музику" in low or "включи музику" in low:
        send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE
        return True, "Грає далі! 🎵"

    if "голосніше" in low or "добав звук" in low or "додай звук" in low or "volume up" in low:
        send_media_key(0xAF, 4)  # VK_VOLUME_UP
        return True, "Зробив голосніше! 🔊"

    if "тихіше" in low or "зменш звук" in low or "убав звук" in low or "volume down" in low:
        send_media_key(0xAE, 4)  # VK_VOLUME_DOWN
        return True, "Зробив тихіше! 🔉"

    if "вимкни звук" in low or "без звуку" in low or "мут" in low or "mute" in low:
        send_media_key(0xAD)  # VK_VOLUME_MUTE
        return True, "Вимкнув звук! 🔇"

    if "наступний трек" in low or "наступна пісня" in low or "next track" in low or "переключи" in low:
        send_media_key(0xB0)  # VK_MEDIA_NEXT_TRACK
        return True, "Перемкнув на наступний трек! ⏭️"

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

        if tag.startswith("url:"):
            url = tag[4:].strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            webbrowser.open(url)
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
