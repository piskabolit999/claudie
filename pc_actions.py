"""PC actions and intent recognition for Claudie.

Handles desktop actions: creating folders, opening apps, opening folders/URLs,
and controlling media on Windows.
"""
import ctypes
import os
import re
import shutil
import subprocess
import webbrowser

# Special Windows folder paths
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
DOCUMENTS = os.path.join(os.path.expanduser("~"), "Documents")

# Protocol and app mapping
KNOWN_APPS = {
    "telegram": {"exe": "telegram.exe", "proto": "tg://"},
    "телеграм": {"exe": "telegram.exe", "proto": "tg://"},
    "тг": {"exe": "telegram.exe", "proto": "tg://"},
    "steam": {"exe": "steam.exe", "proto": "steam://"},
    "стім": {"exe": "steam.exe", "proto": "steam://"},
    "стим": {"exe": "steam.exe", "proto": "steam://"},
    "discord": {"exe": "Discord.exe", "proto": "discord://"},
    "діскорд": {"exe": "Discord.exe", "proto": "discord://"},
    "дискорд": {"exe": "Discord.exe", "proto": "discord://"},
    "spotify": {"exe": "Spotify.exe", "proto": "spotify://"},
    "спотіфай": {"exe": "Spotify.exe", "proto": "spotify://"},
    "спотифай": {"exe": "Spotify.exe", "proto": "spotify://"},
    "calc": {"exe": "calc.exe"},
    "calculator": {"exe": "calc.exe"},
    "калькулятор": {"exe": "calc.exe"},
    "notepad": {"exe": "notepad.exe"},
    "блокнот": {"exe": "notepad.exe"},
    "terminal": {"exe": "wt.exe", "fallback": "powershell.exe"},
    "термінал": {"exe": "wt.exe", "fallback": "powershell.exe"},
    "терминал": {"exe": "wt.exe", "fallback": "powershell.exe"},
    "консоль": {"exe": "powershell.exe"},
    "powershell": {"exe": "powershell.exe"},
    "cmd": {"exe": "cmd.exe"},
    "paint": {"exe": "mspaint.exe"},
    "пейнт": {"exe": "mspaint.exe"},
    "taskmgr": {"exe": "taskmgr.exe"},
    "диспетчер": {"exe": "taskmgr.exe"},
    "диспетчер задач": {"exe": "taskmgr.exe"},
    "explorer": {"exe": "explorer.exe"},
    "провідник": {"exe": "explorer.exe"},
    "проводник": {"exe": "explorer.exe"},
    "code": {"exe": "code.cmd", "fallback": "code.exe"},
    "vs code": {"exe": "code.cmd", "fallback": "code.exe"},
    "vscode": {"exe": "code.cmd", "fallback": "code.exe"},
    "chrome": {"exe": "chrome.exe"},
    "хром": {"exe": "chrome.exe"},
    "edge": {"exe": "msedge.exe"},
    "едж": {"exe": "msedge.exe"},
    "браузер": {"exe": "msedge.exe", "fallback": "chrome.exe"},
    "browser": {"exe": "msedge.exe", "fallback": "chrome.exe"},
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


def send_media_key(key_code: int, times: int = 1) -> None:
    """Send virtual key event via user32."""
    try:
        u = ctypes.windll.user32
        for _ in range(times):
            u.keybd_event(key_code, 0, 0, 0)
            u.keybd_event(key_code, 0, 2, 0)
    except Exception:
        pass


def find_start_menu_shortcut(name: str) -> str | None:
    """Scan Start Menu .lnk shortcuts for a matching application name."""
    dirs = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    ]
    target = name.lower().strip()
    for d in dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.lower().endswith(".lnk"):
                    stem = f[:-4].lower()
                    if target == stem or target in stem:
                        return os.path.join(root, f)
    return None


def launch_app(name: str) -> bool:
    """Launch an application by friendly name, executable, or protocol."""
    target = name.lower().strip()

    # Check known apps
    if target in KNOWN_APPS:
        spec = KNOWN_APPS[target]
        proto = spec.get("proto")
        if proto:
            try:
                os.startfile(proto)
                return True
            except Exception:
                pass
        exe = spec.get("exe")
        if exe:
            which_p = shutil.which(exe)
            if which_p:
                try:
                    subprocess.Popen([which_p])
                    return True
                except Exception:
                    pass
            # Try direct launch
            try:
                subprocess.Popen([exe])
                return True
            except Exception:
                pass
        fb = spec.get("fallback")
        if fb:
            try:
                subprocess.Popen([fb])
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

    # Check start menu shortcut
    lnk = find_start_menu_shortcut(target)
    if lnk:
        try:
            os.startfile(lnk)
            return True
        except Exception:
            pass

    # Fallback to start command via shell
    try:
        subprocess.Popen(f'start "" "{target}"', shell=True)
        return True
    except Exception:
        return False


def create_user_folder(name: str = "", location: str = "", cwd: str | None = None) -> tuple[str, str]:
    """Create a folder on the requested or default location.
    Returns (created_full_path, location_label)."""
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

    # 2. OPEN FOLDERS
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

    # 4. OPEN APPS
    open_app_m = re.search(r"(?:відкрий|открой|open|запусти|запустить|launch|start)\s+(.+)", low)
    if open_app_m:
        app_target = open_app_m.group(1).strip()
        # Clean common words
        app_target = re.sub(r"^(?:програму|додаток|приложение|app|прогу)\s+", "", app_target).strip()
        for kw in KNOWN_APPS:
            if kw == app_target or (len(kw) > 2 and kw in app_target):
                ok = launch_app(kw)
                if ok:
                    return True, f"Запускаю {kw.capitalize()}! ⚡"

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
            return launch_app(app_name)

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
