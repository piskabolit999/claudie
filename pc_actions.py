"""PC actions and intent recognition for Claudie.

Handles desktop actions: creating folders, opening apps, opening folders/URLs,
and controlling media on Windows with full Program Files search and fuzzy typo matching.
"""
import base64
import ctypes
from ctypes import wintypes
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
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
    "librewolf": {"name": "LibreWolf", "exe": "librewolf.exe"},
    "лібревулф": {"name": "LibreWolf", "exe": "librewolf.exe"},
    "лібревольф": {"name": "LibreWolf", "exe": "librewolf.exe"},
    "либревулф": {"name": "LibreWolf", "exe": "librewolf.exe"},
    "либревольф": {"name": "LibreWolf", "exe": "librewolf.exe"},
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


LOCALIZED_STRINGS: dict[str, dict[str, str]] = {
    "folder_created": {
        "uk": "Папку «{name}» створено на {loc}. 📁",
        "en": "Folder '{name}' created on {loc}. 📁",
        "ru": "Папка «{name}» создана в {loc}. 📁",
        "pl": "Folder «{name}» został utworzony w {loc}. 📁",
        "de": "Ordner '{name}' wurde erstellt in {loc}. 📁",
        "es": "Carpeta '{name}' creada en {loc}. 📁",
    },
    "loc_desktop": {
        "uk": "робочому столі", "en": "Desktop", "ru": "рабочем столе",
        "pl": "Pulpicie", "de": "Desktop", "es": "Escritorio",
    },
    "loc_downloads": {
        "uk": "Завантаженнях", "en": "Downloads", "ru": "Загрузках",
        "pl": "Pobranych", "de": "Downloads", "es": "Descargas",
    },
    "loc_documents": {
        "uk": "Документах", "en": "Documents", "ru": "Документах",
        "pl": "Dokumentach", "de": "Dokumente", "es": "Documentos",
    },
    "loc_project": {
        "uk": "папці проекту", "en": "project folder", "ru": "папке проекта",
        "pl": "folderze projektu", "de": "Projektordner", "es": "carpeta del proyecto",
    },
    "desktop_opened": {
        "uk": "Робочий стіл відкрито. 🖥️", "en": "Desktop opened. 🖥️",
        "ru": "Рабочий стол открыт. 🖥️", "pl": "Pulpit otwarty. 🖥️",
        "de": "Desktop geöffnet. 🖥️", "es": "Escritorio abierto. 🖥️",
    },
    "downloads_opened": {
        "uk": "Папку Завантаження відкрито. 📂", "en": "Downloads folder opened. 📂",
        "ru": "Папка Загрузки открыта. 📂", "pl": "Folder Pobrane otwarty. 📂",
        "de": "Downloads-Ordner geöffnet. 📂", "es": "Carpeta Descargas abierta. 📂",
    },
    "documents_opened": {
        "uk": "Папку Документи відкрито. 📄", "en": "Documents folder opened. 📄",
        "ru": "Папка Документы открыта. 📄", "pl": "Folder Dokumenty otwarty. 📄",
        "de": "Dokumenten-Ordner geöffnet. 📄", "es": "Carpeta Documentos abierta. 📄",
    },
    "project_opened": {
        "uk": "Папку проекту відкрито. 📁", "en": "Project folder opened. 📁",
        "ru": "Папка проекта открыта. 📁", "pl": "Folder projektu otwarty. 📁",
        "de": "Projektordner geöffnet. 📁", "es": "Carpeta del proyecto abierta. 📁",
    },
    "default_browser_info": {
        "uk": "Твій браузер за замовчуванням — {name}. 🌐",
        "en": "Your default browser is {name}. 🌐",
        "ru": "Твой браузер по умолчанию — {name}. 🌐",
        "pl": "Twoja domyślna przeglądarka to {name}. 🌐",
        "de": "Dein Standardbrowser ist {name}. 🌐",
        "es": "Tu navegador predeterminado es {name}. 🌐",
    },
    "tab_closed": {
        "uk": "Вкладку закрито. ✖️", "en": "Tab closed. ✖️",
        "ru": "Вкладка закрыта. ✖️", "pl": "Karta zamknięta. ✖️",
        "de": "Tab geschlossen. ✖️", "es": "Pestaña cerrada. ✖️",
    },
    "window_closed": {
        "uk": "Закрив «{title}». ✖️", "en": "Closed '{title}'. ✖️",
        "ru": "Закрыл «{title}». ✖️", "pl": "Zamknięto «{title}». ✖️",
        "de": "'{title}' geschlossen. ✖️", "es": "Cerrado '{title}'. ✖️",
    },
    "active_window_closed": {
        "uk": "Закрив активне вікно. ✖️", "en": "Active window closed. ✖️",
        "ru": "Закрыл активное окно. ✖️", "pl": "Aktywne okno zamknięte. ✖️",
        "de": "Aktives Fenster geschlossen. ✖️", "es": "Ventana activa cerrada. ✖️",
    },
    "close_window_failed": {
        "uk": "Не вдалося визначити активне вікно для закриття. 🤔",
        "en": "Could not determine active window to close. 🤔",
        "ru": "Не удалось определить активное окно для закрытия. 🤔",
        "pl": "Nie udało się określić aktywnego okna do zamknięcia. 🤔",
        "de": "Aktives Fenster zum Schließen konnte nicht ermittelt werden. 🤔",
        "es": "No se pudo determinar la ventana activa para cerrar. 🤔",
    },
    "chat_closed": {
        "uk": "Ховаю чат. 👋<!--ACTION:chat:close-->",
        "en": "Hiding chat. 👋<!--ACTION:chat:close-->",
        "ru": "Прячу чат. 👋<!--ACTION:chat:close-->",
        "pl": "Chowam czat. 👋<!--ACTION:chat:close-->",
        "de": "Chat wird ausgeblendet. 👋<!--ACTION:chat:close-->",
        "es": "Ocultando chat. 👋<!--ACTION:chat:close-->",
    },
    "app_closed": {
        "uk": "Закрив «{name}». ✖️", "en": "Closed '{name}'. ✖️",
        "ru": "Закрыл «{name}». ✖️", "pl": "Zamknięto «{name}». ✖️",
        "de": "'{name}' geschlossen. ✖️", "es": "Cerrado '{name}'. ✖️",
    },
    "new_tab_opened": {
        "uk": "Нову вкладку відкрито. 🌐", "en": "New tab opened. 🌐",
        "ru": "Новая вкладка открыта. 🌐", "pl": "Nowa karta otwarta. 🌐",
        "de": "Neuer Tab geöffnet. 🌐", "es": "Nueva pestaña abierta. 🌐",
    },
    "searching_web": {
        "uk": "Шукаю в браузері: «{query}». 🌐",
        "en": "Searching in browser: '{query}'. 🌐",
        "ru": "Ищу в браузере: «{query}». 🌐",
        "pl": "Szukam w przeglądarce: «{query}». 🌐",
        "de": "Suche im Browser: '{query}'. 🌐",
        "es": "Buscando en el navegador: '{query}'. 🌐",
    },
    "browser_opened": {
        "uk": "Відкрив браузер {name}. 🌐", "en": "Opened browser {name}. 🌐",
        "ru": "Открыл браузер {name}. 🌐", "pl": "Otwarto przeglądarkę {name}. 🌐",
        "de": "Browser {name} geöffnet. 🌐", "es": "Navegador {name} abierto. 🌐",
    },
    "link_opened": {
        "uk": "Відкрив посилання в браузері. 🌐", "en": "Link opened in browser. 🌐",
        "ru": "Ссылка открыта в браузере. 🌐", "pl": "Link otwarty w przeglądarce. 🌐",
        "de": "Link im Browser geöffnet. 🌐", "es": "Enlace abierto en el navegador. 🌐",
    },
    "site_opened": {
        "uk": "{name} відкрито. 🚀", "en": "{name} opened. 🚀",
        "ru": "{name} открыт. 🚀", "pl": "{name} otwarty. 🚀",
        "de": "{name} geöffnet. 🚀", "es": "{name} abierto. 🚀",
    },
    "app_launched": {
        "uk": "Запущено {name}. ⚡", "en": "Launched {name}. ⚡",
        "ru": "Запущено {name}. ⚡", "pl": "Uruchomiono {name}. ⚡",
        "de": "{name} gestartet. ⚡", "es": "{name} iniciado. ⚡",
    },
    "app_fuzzy_launched": {
        "uk": "Малося на увазі «{name}» — запущено. 🚀",
        "en": "Meant '{name}' — launched. 🚀",
        "ru": "Имелось в виду «{name}» — запущено. 🚀",
        "pl": "Chodziło o «{name}» — uruchomiono. 🚀",
        "de": "Gemeint war '{name}' — gestartet. 🚀",
        "es": "Te referías a '{name}' — iniciado. 🚀",
    },
    "app_not_found": {
        "uk": "Програму «{name}» не знайдено серед встановлених. 🤔",
        "en": "Application '{name}' not found among installed apps. 🤔",
        "ru": "Программа «{name}» не найдена среди установленных. 🤔",
        "pl": "Nie znaleziono aplikacji «{name}» wśród zainstalowanych. 🤔",
        "de": "Anwendung '{name}' nicht gefunden. 🤔",
        "es": "Aplicación '{name}' no encontrada. 🤔",
    },
    "media_paused": {
        "uk": "Відтворення призупинено. ⏸️", "en": "Playback paused. ⏸️",
        "ru": "Воспроизведение приостановлено. ⏸️", "pl": "Odtwarzanie wstrzymane. ⏸️",
        "de": "Wiedergabe pausiert. ⏸️", "es": "Reproducción pausada. ⏸️",
    },
    "media_resumed": {
        "uk": "Відтворення відновлено. 🎵", "en": "Playback resumed. 🎵",
        "ru": "Воспроизведение возобновлено. 🎵", "pl": "Wznowiono odtwarzanie. 🎵",
        "de": "Wiedergabe fortgesetzt. 🎵", "es": "Reproducción reanudada. 🎵",
    },
    "volume_up": {
        "uk": "Гучність збільшено. 🔊", "en": "Volume increased. 🔊",
        "ru": "Громкость увеличена. 🔊", "pl": "Głośność zwiększona. 🔊",
        "de": "Lautstärke erhöht. 🔊", "es": "Volumen aumentado. 🔊",
    },
    "volume_down": {
        "uk": "Гучність зменшено. 🔉", "en": "Volume decreased. 🔉",
        "ru": "Громкость уменьшена. 🔉", "pl": "Głośność zmniejszona. 🔉",
        "de": "Lautstärke verringert. 🔉", "es": "Volumen reducido. 🔉",
    },
    "mute": {
        "uk": "Звук вимкнено. 🔇", "en": "Sound muted. 🔇",
        "ru": "Звук выключен. 🔇", "pl": "Dźwięk wyciszony. 🔇",
        "de": "Ton stummgeschaltet. 🔇", "es": "Sonido silenciado. 🔇",
    },
    "next_track": {
        "uk": "Перемкнуто на наступний трек. ⏭️", "en": "Skipped to next track. ⏭️",
        "ru": "Переключено на следующий трек. ⏭️", "pl": "Przełączono na następny utwór. ⏭️",
        "de": "Zum nächsten Titel gewechselt. ⏭️", "es": "Saltado a la siguiente pista. ⏭️",
    },
    "librewolf_prefer_enabled": {
        "uk": "Тепер LibreWolf використовується для відкривання посилань. 🐺",
        "en": "LibreWolf is now set to open web links. 🐺",
        "ru": "Теперь LibreWolf используется для открытия ссылок. 🐺",
        "pl": "LibreWolf jest teraz używany do otwierania linków. 🐺",
        "de": "LibreWolf wird jetzt zum Öffnen von Links verwendet. 🐺",
        "es": "LibreWolf ahora se usa para abrir enlaces. 🐺",
    },
    "librewolf_opened": {
        "uk": "Відкрив LibreWolf. 🐺", "en": "LibreWolf opened. 🐺",
        "ru": "Открыл LibreWolf. 🐺", "pl": "Otwarto LibreWolf. 🐺",
        "de": "LibreWolf geöffnet. 🐺", "es": "LibreWolf abierto. 🐺",
    },
    "librewolf_not_found": {
        "uk": "LibreWolf не знайдено на комп'ютері. 🤔",
        "en": "LibreWolf was not found on this computer. 🤔",
        "ru": "LibreWolf не найден на компьютере. 🤔",
        "pl": "Nie znaleziono LibreWolf na komputerze. 🤔",
        "de": "LibreWolf wurde auf diesem Computer nicht gefunden. 🤔",
        "es": "No se encontró LibreWolf en este equipo. 🤔",
    },
    "click_success": {
        "uk": "Натиснув на «{target}» ({x}, {y}). 🖱️",
        "en": "Clicked on '{target}' ({x}, {y}). 🖱️",
        "ru": "Нажал на «{target}» ({x}, {y}). 🖱️",
        "pl": "Kliknięto w «{target}» ({x}, {y}). 🖱️",
        "de": "Auf '{target}' geklickt ({x}, {y}). 🖱️",
        "es": "Hizo clic en '{target}' ({x}, {y}). 🖱️",
    },
    "click_not_found": {
        "uk": "Не зміг знайти «{target}» на екрані. 🤔",
        "en": "Could not find '{target}' on screen. 🤔",
        "ru": "Не смог найти «{target}» на экране. 🤔",
        "pl": "Nie udało się znaleźć «{target}» na ekranie. 🤔",
        "de": "'{target}' konnte auf dem Bildschirm nicht gefunden werden. 🤔",
        "es": "No se pudo encontrar '{target}' en la pantalla. 🤔",
    },
    "screen_error": {
        "uk": "Не вдалося отримати знімок екрана. 🤔",
        "en": "Failed to capture screenshot. 🤔",
        "ru": "Не удалось сделать снимок экрана. 🤔",
        "pl": "Nie udało się przechwycić ekranu. 🤔",
        "de": "Screenshot konnte nicht erstellt werden. 🤔",
        "es": "No se pudo capturar la pantalla. 🤔",
    },
}


def tr(key: str, lang: str | None = None, **kwargs) -> str:
    """Format a localized string according to lang."""
    if not lang:
        try:
            import l10n
            lang = l10n.get_lang()
        except Exception:
            lang = "uk"
    item = LOCALIZED_STRINGS.get(key, {})
    tmpl = item.get(lang) or item.get("en") or item.get("uk") or key
    try:
        return tmpl.format(**kwargs)
    except Exception:
        return tmpl


# LibreWolf browser support
_USE_LIBREWOLF_FOR_LINKS: bool = False


def find_librewolf() -> str | None:
    """Find LibreWolf executable path on Windows."""
    candidates = [
        r"C:\Program Files\LibreWolf\librewolf.exe",
        r"C:\Program Files (x86)\LibreWolf\librewolf.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\LibreWolf\librewolf.exe"),
        os.path.expandvars(r"%APPDATA%\LibreWolf\librewolf.exe"),
        shutil.which("librewolf.exe") or "",
        shutil.which("librewolf") or "",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\librewolf.exe") as k:
                val, _ = winreg.QueryValueEx(k, "")
                if val and os.path.exists(val):
                    return val
        except Exception:
            pass
    return None


def set_prefer_librewolf(enable: bool = True) -> None:
    """Set LibreWolf as preferred browser for opening links."""
    global _USE_LIBREWOLF_FOR_LINKS, _DEFAULT_BROWSER_CACHE
    _USE_LIBREWOLF_FOR_LINKS = enable
    _DEFAULT_BROWSER_CACHE.clear()


def open_in_librewolf(target: str = "") -> bool:
    """Open target URL or search query specifically in LibreWolf."""
    lw = find_librewolf()
    if not lw:
        return open_in_browser(target)
    target = (target or "").strip()
    if not target:
        try:
            subprocess.Popen([lw])
            return True
        except Exception:
            return False
    if not (target.startswith("http://") or target.startswith("https://")):
        if re.match(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/.*)?$", target):
            url = "https://" + target
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(target)}"
    else:
        url = target
    try:
        subprocess.Popen([lw, url])
        return True
    except Exception:
        return False


# Screen Vision & GUI Click Automation
def capture_screen_image() -> tuple[object | None, int, int]:
    """Capture screen as PIL Image and return (image, width, height)."""
    try:
        from PIL import ImageGrab
        im = ImageGrab.grab()
        if im and im.width > 0 and im.height > 0:
            return im, im.width, im.height
    except Exception:
        pass

    try:
        import mss
        from PIL import Image
        with mss.MSS() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(mon)
            im = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            if im and im.width > 0 and im.height > 0:
                return im, im.width, im.height
    except Exception:
        pass

    return None, 0, 0


def _get_gemini_key() -> str | None:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    try:
        keys_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")
        with open(keys_file, encoding="utf-8") as f:
            return json.load(f).get("GEMINI_API_KEY")
    except Exception:
        return None


def _query_gemini_vision(prompt: str, b64_img: str, json_mode: bool = False, timeout: int = 15) -> str | None:
    key = _get_gemini_key()
    if not key:
        return None
    models = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.8-flash"]
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                ]
            }
        ]
    }
    if json_mode:
        payload["generationConfig"] = {"response_mime_type": "application/json"}

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "claudie-vision"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = json.loads(r.read().decode("utf-8"))
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            continue
    return None


def inspect_screen_vision(b64_img: str, lang: str = "uk") -> str | None:
    """Ask Gemini Vision to inspect what is on the screen."""
    import freeai
    lang_name = freeai.LANGS.get(lang, (None, "Ukrainian"))[1]
    prompt = (
        f"You are an intelligent desktop assistant observing the user's screen. "
        f"Describe what is happening on screen or what open window/task is visible in 1-2 short factual sentences "
        f"(max 25 words). Reply in {lang_name}. Strictly by facts, zero baby talk, zero rudeness. One emoji max. No quotes."
    )
    return _query_gemini_vision(prompt, b64_img, json_mode=False)


def locate_target_coordinates(b64_img: str, width: int, height: int, target: str) -> dict[str, object]:
    """Ask Gemini Vision to find pixel coordinates (center) of target on screenshot."""
    prompt = (
        f"You are an accurate screen GUI element locator. The screenshot resolution is {width}x{height} pixels.\n"
        f"Locate the element or text: '{target}'.\n"
        "Return ONLY a JSON object: {\"found\": true, \"x\": <int>, \"y\": <int>} where x and y are the exact pixel "
        "coordinates of the center of the element to click.\n"
        "If the element cannot be found or is not visible, return {\"found\": false}."
    )
    raw = _query_gemini_vision(prompt, b64_img, json_mode=True)
    if not raw:
        return {"found": False}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    m = re.search(r'\"found\"\s*:\s*(true|false)', raw, re.IGNORECASE)
    if m:
        found = m.group(1).lower() == "true"
        x_m = re.search(r'\"x\"\s*:\s*(\d+)', raw)
        y_m = re.search(r'\"y\"\s*:\s*(\d+)', raw)
        if found and x_m and y_m:
            return {"found": True, "x": int(x_m.group(1)), "y": int(y_m.group(1))}
    return {"found": False}


def take_screenshot_and_inspect(lang: str = "uk") -> tuple[bool, str]:
    """Capture screen, inspect via vision AI, and delete the screenshot file."""
    im, w, h = capture_screen_image()
    if not im:
        return False, tr("screen_error", lang)

    tmp_path = os.path.join(tempfile.gettempdir(), f"claudie_screen_{int(time.time()*1000)}.jpg")
    try:
        im.save(tmp_path, "JPEG", quality=85)
        with open(tmp_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        desc = inspect_screen_vision(b64, lang=lang)
        if desc:
            return True, desc
        return False, tr("screen_error", lang)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def take_screenshot_and_click(target: str, lang: str = "uk") -> tuple[bool, str]:
    """Capture screen, find coordinates of target, click on it, and delete screenshot."""
    im, w, h = capture_screen_image()
    if not im:
        return False, tr("screen_error", lang)

    tmp_path = os.path.join(tempfile.gettempdir(), f"claudie_click_{int(time.time()*1000)}.jpg")
    try:
        im.save(tmp_path, "JPEG", quality=85)
        with open(tmp_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        coords = locate_target_coordinates(b64, w, h, target)
        if coords and coords.get("found"):
            x = max(0, min(w - 1, int(coords.get("x", 0))))
            y = max(0, min(h - 1, int(coords.get("y", 0))))
            # Move mouse and click
            u = ctypes.windll.user32
            u.SetCursorPos(x, y)
            time.sleep(0.05)
            u.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            u.mouse_event(0x0004, 0, 0, 0, 0)
            return True, tr("click_success", lang, target=target, x=x, y=y)
        else:
            return True, tr("click_not_found", lang, target=target)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


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


def open_in_browser(target: str = "", prefer_browser: str | None = None) -> bool:
    """Open a URL, search query, or empty browser in default or preferred browser."""
    target = (target or "").strip()
    if prefer_browser == "librewolf" or _USE_LIBREWOLF_FOR_LINKS:
        lw = find_librewolf()
        if lw:
            return open_in_librewolf(target)

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


def open_web_search(query: str, prefer_browser: str | None = None) -> bool:
    """Search Google in the default or preferred browser."""
    q = (query or "").strip()
    if not q:
        return open_in_browser("", prefer_browser=prefer_browser)
    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}"
    return open_in_browser(url, prefer_browser=prefer_browser)


def new_browser_tab(lang: str | None = None) -> tuple[bool, str]:
    """Open a new tab in browser (Ctrl + T) or launch default browser."""
    try:
        u = ctypes.windll.user32
        u.keybd_event(0x11, 0, 0, 0)
        u.keybd_event(0x54, 0, 0, 0)
        u.keybd_event(0x54, 0, 2, 0)
        u.keybd_event(0x11, 0, 2, 0)
        return True, tr("new_tab_opened", lang)
    except Exception:
        open_in_browser("")
        b_info = get_default_browser()
        return True, tr("browser_opened", lang, name=b_info.get("name", "Браузер"))


def close_tab(lang: str | None = None) -> tuple[bool, str]:
    """Close the current tab (Ctrl + W)."""
    try:
        u = ctypes.windll.user32
        u.keybd_event(0x11, 0, 0, 0)
        u.keybd_event(0x57, 0, 0, 0)
        u.keybd_event(0x57, 0, 2, 0)
        u.keybd_event(0x11, 0, 2, 0)
        return True, tr("tab_closed", lang)
    except Exception as e:
        return False, f"Помилка закриття вкладки: {e}"


def close_active_window(
    active_title: str = "", active_pname: str = "", lang: str | None = None
) -> tuple[bool, str]:
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
        if target_title:
            return True, tr("window_closed", lang, title=target_title)
        return True, tr("active_window_closed", lang)

    # Fallback Alt+F4
    try:
        u.keybd_event(0x12, 0, 0, 0)  # VK_MENU (Alt)
        u.keybd_event(0x73, 0, 0, 0)  # VK_F4
        u.keybd_event(0x73, 0, 2, 0)
        u.keybd_event(0x12, 0, 2, 0)
        return True, tr("active_window_closed", lang)
    except Exception:
        pass

    if active_pname and not any(k in active_pname.lower() for k in ("python", "explorer", "claud")):
        try:
            subprocess.run(f'taskkill /IM "{active_pname}"', shell=True, capture_output=True)
            return True, tr("window_closed", lang, title=active_pname)
        except Exception:
            pass

    return False, tr("close_window_failed", lang)


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


def close_app_by_name(query: str, lang: str | None = None) -> tuple[bool, str]:
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
        return True, tr("app_closed", lang, name=name)

    if q in ("librewolf", "лібревулф", "лібревольф", "либревулф"):
        _close_process_gracefully("librewolf.exe", title_pattern="librewolf")
        return True, tr("app_closed", lang, name="LibreWolf")

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
    return True, tr("app_closed", lang, name=display_name)


def handle_local_intent(
    text: str, cwd: str | None = None, active_title: str = "", active_pname: str = "", lang: str | None = None
) -> tuple[bool, str | None]:
    """Check if user query is a direct PC command.
    Returns (handled: bool, mascot_reply: str | None)."""
    t = text.strip()
    low = t.lower()

    if not lang:
        try:
            import l10n
            lang = l10n.get_lang()
        except Exception:
            lang = "uk"

    # 1. SCREEN INSPECTION
    if any(re.search(p, low) for p in (
        r"(?:подивись|подивися|глянь|передивись|переглянь|посмотри)\s+(?:на\s+)?(?:екран|экран|дисплей|screen)",
        r"(?:що|что|what)\s+(?:зараз\s+|сейчас\s+)?(?:на\s+)?(?:екрані|экране|screen)",
        r"(?:зроби|сделай|take)\s+(?:скрін|скрин|скріншот|скриншот|screenshot)\s+(?:і|и|and)\s+(?:подивись|глянь|look)",
        r"(?:look\s+at\s+screen|inspect\s+screen)",
    )):
        ok, desc = take_screenshot_and_inspect(lang=lang)
        return True, desc

    # 2. SCREEN CLICK (calculate coordinates and click)
    click_m = re.search(r"^(?:натисни|клікни|клацни|нажми|тыкни|click|press)\s+(?:на\s+|по\s+|on\s+)?(.+)", low)
    if click_m:
        target_el = click_m.group(1).strip(' \t\r\n:"\'')
        if not any(target_el.lower() == m for m in ("паузу", "пауза", "плей", "play", "pause", "стоп")):
            ok, click_rep = take_screenshot_and_click(target_el, lang=lang)
            return True, click_rep

    # 3. LIBREWOLF SUPPORT
    if any(k in low for k in ("використовуй librewolf для ссилок", "відкривай ссилки в librewolf", "зроби librewolf основним", "use librewolf for links")):
        set_prefer_librewolf(True)
        return True, tr("librewolf_prefer_enabled", lang)

    lw_open_m = (
        re.search(r"^(?:відкрий|відкрити|запусти|open)\s+(?:в\s+|через\s+|in\s+)?librewolf\s*(.*)", low)
        or re.search(r"^(?:відкрий|відкрити|запусти)\s+(?:в\s+|через\s+)?(?:лібревулф|лібревольф|либревулф)\s*(.*)", low)
    )
    if lw_open_m:
        target_link = lw_open_m.group(1).strip()
        lw = find_librewolf()
        if not lw:
            return True, tr("librewolf_not_found", lang)
        open_in_librewolf(target_link)
        if target_link:
            return True, tr("link_opened", lang)
        return True, tr("librewolf_opened", lang)

    if re.search(r"^(?:загугли|пошукай)\s+(?:в\s+|через\s+)?(?:librewolf|лібревулф|лібревольф)\s+(.+)", low):
        q_term = re.sub(r"^(?:загугли|пошукай)\s+(?:в\s+|через\s+)?(?:librewolf|лібревулф|лібревольф)\s+", "", low).strip()
        open_in_librewolf(q_term)
        return True, tr("searching_web", lang, query=q_term)

    # 4. CREATE FOLDER
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
        loc_str = tr(f"loc_{loc}" if loc else "loc_desktop", lang)
        return True, tr("folder_created", lang, name=final_name, loc=loc_str)

    # 5. OPEN SPECIAL FOLDERS
    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:робоч(?:ий|ого)\s+стіл|рабочий\s+стол|desktop|десктоп)", low):
        try:
            os.startfile(DESKTOP)
        except Exception:
            pass
        return True, tr("desktop_opened", lang)

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:завантаженн(?:я|ь)|downloads|загрузк(?:и|ек))", low):
        try:
            os.startfile(DOWNLOADS)
        except Exception:
            pass
        return True, tr("downloads_opened", lang)

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:документ(?:и|ів)|documents)", low):
        try:
            os.startfile(DOCUMENTS)
        except Exception:
            pass
        return True, tr("documents_opened", lang)

    if re.search(r"(?:відкрий|открой|open)\s+(?:папку\s+)?(?:проект(?:у|а)?|проєкт(?:у|а)?|project|файли)", low):
        folder = cwd if (cwd and os.path.exists(cwd)) else DESKTOP
        try:
            os.startfile(folder)
        except Exception:
            pass
        return True, tr("project_opened", lang)

    # 6. DEFAULT BROWSER QUERY
    if any(k in low for k in ("браузер по дефолту", "браузер за замовчуванням", "браузер по замовчуванню", "браузер по умолчанию", "дефолтний браузер", "дефолтный браузер")) or (
        re.search(r"(?:який|какой|що|what).*(?:браузер|browser)", low) and not any(k in low for k in ("відкрий", "запусти", "закрий", "скачай"))
    ):
        b_info = get_default_browser()
        return True, tr("default_browser_info", lang, name=b_info["name"])

    # 7. WINDOW & TAB CLOSING
    if re.search(r"^(?:закрий|закрити|close)\s+(?:цю\s+)?(?:вкладку|таб|tab)$", low):
        _, reply = close_tab(lang=lang)
        return True, reply

    if re.search(r"^(?:закрий|закрити|close)\s+(?:це\s+|поточне\s+|активне\s+)?вікно$", low) or re.search(r"^(?:закрий|закрити|close)\s+це$", low):
        _, reply = close_active_window(active_title=active_title, active_pname=active_pname, lang=lang)
        return True, reply

    if re.search(r"^(?:закрий|закрити|close|сховай)\s+(?:чат|діалог|вікно чату)$", low) or low in ("закрийся", "сховайся", "закрий чат"):
        return True, tr("chat_closed", lang)

    close_app_m = re.search(r"^(?:закрий|закрити|close|вигрузи|закрий програму|закрий процес)\s+(.+)", low)
    if close_app_m:
        app_target = close_app_m.group(1).strip()
        if app_target not in ("вкладку", "таб", "tab", "вікно", "це вікно", "активне вікно", "поточне вікно", "чат"):
            _, reply = close_app_by_name(app_target, lang=lang)
            return True, reply

    # 8. BROWSER NAVIGATION & WEB SEARCH
    if re.search(r"^(?:нова вкладка|відкрий нову вкладку|новий таб|new tab)$", low):
        _, reply = new_browser_tab(lang=lang)
        return True, reply

    search_m = re.search(r"^(?:загугли|гугли|пошукай в інтернеті|пошукай в гуглі|знайди в інтернеті|знайди в гуглі|search|пошукай)\s+(.+)", low)
    if search_m:
        query = search_m.group(1).strip()
        open_web_search(query)
        return True, tr("searching_web", lang, query=query)

    if low.startswith("знайди "):
        rest = t[7:].strip()
        if rest and not any(rest.lower().startswith(k) for k in ("папку", "файл", "програму", "додаток")):
            open_web_search(rest)
            return True, tr("searching_web", lang, query=rest)

    if re.search(r"^(?:відкрий|відкрити|запусти|open)\s+(?:браузер|browser)$", low):
        b_info = get_default_browser()
        open_in_browser("")
        return True, tr("browser_opened", lang, name=b_info["name"])

    url_m = re.search(r"^(?:відкрий|відкрити|open)\s+(https?://\S+|www\.\S+|\S+\.(?:com|org|net|io|ua|tv|gov|edu|dev)\S*)$", low)
    if url_m:
        u_target = url_m.group(1).strip()
        open_in_browser(u_target)
        return True, tr("link_opened", lang)

    # 9. OPEN WEBSITES
    for kw, url in KNOWN_URLS.items():
        if re.search(rf"(?:відкрий|открой|open)\s+{kw}\b", low):
            open_in_browser(url)
            name_cap = kw.capitalize()
            return True, tr("site_opened", lang, name=name_cap)

    # 10. OPEN / LAUNCH APPS (with Program Files scanning & fuzzy matching)
    open_app_m = re.search(r"^(?:відкрий|відкрити|открой|открыть|open|запусти|запустити|запустить|launch|start)\s+(.+)", low)
    if open_app_m:
        app_query = open_app_m.group(1).strip()
        target, display_name, is_fuzzy = resolve_app_target(app_query)
        if target:
            launched = launch_target(target, display_name)
            if launched:
                if is_fuzzy:
                    return True, tr("app_fuzzy_launched", lang, name=display_name)
                return True, tr("app_launched", lang, name=display_name)
        else:
            return True, tr("app_not_found", lang, name=app_query)

    # 11. MEDIA CONTROLS
    if re.search(r"^(?:пауза|постав на паузу|стоп музика|пауза музика|pause)$", low) or "постав музику на паузу" in low:
        send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE
        return True, tr("media_paused", lang)

    if re.search(r"^(?:плей|продовж|продовжити|play|resume)$", low) or "увімкни музику" in low or "включи музику" in low:
        send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE
        return True, tr("media_resumed", lang)

    if "голосніше" in low or "добав звук" in low or "додай звук" in low or "volume up" in low:
        send_media_key(0xAF, 4)  # VK_VOLUME_UP
        return True, tr("volume_up", lang)

    if "тихіше" in low or "зменш звук" in low or "убав звук" in low or "volume down" in low:
        send_media_key(0xAE, 4)  # VK_VOLUME_DOWN
        return True, tr("volume_down", lang)

    if "вимкни звук" in low or "без звуку" in low or "мут" in low or "mute" in low:
        send_media_key(0xAD)  # VK_VOLUME_MUTE
        return True, tr("mute", lang)

    if "наступний трек" in low or "наступна пісня" in low or "next track" in low or "переключи" in low:
        send_media_key(0xB0)  # VK_MEDIA_NEXT_TRACK
        return True, tr("next_track", lang)

    return False, None


def execute_action_tag(tag: str, cwd: str | None = None, lang: str | None = None) -> bool:
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

        if tag == "screen_inspect":
            ok, desc = take_screenshot_and_inspect(lang=lang)
            return desc if ok else False

        if tag.startswith("screen_click:"):
            target = tag[13:].strip()
            ok, rep = take_screenshot_and_click(target, lang=lang)
            return rep if ok else False

        if tag.startswith("librewolf_open:"):
            url = tag[15:].strip()
            open_in_librewolf(url)
            return True

        if tag == "librewolf_prefer":
            set_prefer_librewolf(True)
            return True

        if tag == "close_window":
            close_active_window(lang=lang)
            return True

        if tag == "close_tab":
            close_tab(lang=lang)
            return True

        if tag.startswith("close_app:"):
            app_name = tag[10:].strip()
            close_app_by_name(app_name, lang=lang)
            return True

        if tag == "new_tab":
            new_browser_tab(lang=lang)
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
