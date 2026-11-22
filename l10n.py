"""Klodik's interface strings. Source strings are Ukrainian; t(s) returns them in the current language.

English and Russian are written by hand. Other languages in freeai.LANGS are machine-translated once
(through freeai.translate) and cached in l10n_cache.json next to this file.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "l10n_cache.json")

SOURCE = [
    # moods (bubble line while working)
    "думаю…", "читаю код", "пишу код", "запускаю команду", "шукаю", "лажу в інеті", "кличу помічників",
    "чекаю на тебе!", "готово", "ой, помилка",
    # cartridge tabs
    "КЛОДІК", "ДУМАЮ", "ЧИТАЮ", "ПИШУ", "ТЕРМІНАЛ", "ПОШУК", "ІНТЕРНЕТ", "КОМАНДА", "ПИТАННЯ", "ГОТОВО",
    "ПОМИЛКА", "ВІДПОВІДЬ", "ЧАТ", "МОВА", "ПІДКЛЮЧИТИ ДО ЧАТУ",
    # time
    "щойно", "хв тому", "год тому",
    # bubbles / chat
    "привіт! я тут, якщо що", "готово!", "щось пішло не так",
    "Питай що завгодно про проект. Я бачу, що робив Claude.",
    "Не вийшло відповісти: безкоштовне API не відповіло. Спробуй ще раз за хвилину.",
    "слідкую за всіма чатами", "підключився до: ", "розмовляю: ", "перекладаю…", "спитай щось",
    # menu
    "будь-який (авто)", "вибраний", "Підключити до чату…", "Мова…", "Сховати на 15 хв", "Повернути в куток",
    "Очистити чат", "Вийти", "Будь-який чат (авто)", "той, що працює останнім", "без назви", "чекає",
    "Поки немає чатів за останню добу", "напиши щось у Claude Code", "Авто (як у твоїх чатах)",
    # little props
    "хм…", "пш-ш", "ТВІЙ ХІД?", "ПОП!", "апчх!",
    "без папки",
]

EN = [
    "thinking…", "reading code", "writing code", "running a command", "searching", "surfing the web",
    "calling helpers", "waiting for you!", "done", "oops, error",
    "CLAUDIE", "THINKING", "READING", "WRITING", "TERMINAL", "SEARCH", "WEB", "TEAM", "QUESTION", "DONE",
    "ERROR", "ANSWER", "CHAT", "LANGUAGE", "CONNECT TO CHAT",
    "just now", "min ago", "h ago",
    "hi! I'm here if you need me", "done!", "something went wrong",
    "Ask me anything about the project. I see what Claude has been doing.",
    "Couldn't answer: the free API didn't respond. Try again in a minute.",
    "watching all chats", "connected to: ", "speaking: ", "translating…", "ask me something",
    "any (auto)", "selected", "Connect to chat…", "Language…", "Hide for 15 min", "Back to the corner",
    "Clear chat", "Quit", "Any chat (auto)", "the one that moved last", "untitled", "idle",
    "No chats in the last day", "write something in Claude Code", "Auto (like your chats)",
    "hmm…", "psst", "YOUR TURN?", "POP!", "achoo!",
    "no folder",
]

RU = [
    "думаю…", "читаю код", "пишу код", "запускаю команду", "ищу", "лажу в интернете", "зову помощников",
    "жду тебя!", "готово", "ой, ошибка",
    "КЛОДИК", "ДУМАЮ", "ЧИТАЮ", "ПИШУ", "ТЕРМИНАЛ", "ПОИСК", "ИНТЕРНЕТ", "КОМАНДА", "ВОПРОС", "ГОТОВО",
    "ОШИБКА", "ОТВЕТ", "ЧАТ", "ЯЗЫК", "ПОДКЛЮЧИТЬ К ЧАТУ",
    "только что", "мин назад", "ч назад",
    "привет! я тут, если что", "готово!", "что-то пошло не так",
    "Спрашивай что угодно о проекте. Я вижу, что делал Claude.",
    "Не получилось ответить: бесплатное API не ответило. Попробуй ещё раз через минуту.",
    "слежу за всеми чатами", "подключился к: ", "говорю: ", "перевожу…", "спроси что-нибудь",
    "любой (авто)", "выбранный", "Подключить к чату…", "Язык…", "Спрятать на 15 мин", "Вернуть в угол",
    "Очистить чат", "Выйти", "Любой чат (авто)", "тот, что работал последним", "без названия", "ждёт",
    "Пока нет чатов за последние сутки", "напиши что-нибудь в Claude Code", "Авто (как в твоих чатах)",
    "хм…", "пш-ш", "ТВОЙ ХОД?", "ПОП!", "апчхи!",
    "без папки",
]

assert len(EN) == len(SOURCE) and len(RU) == len(SOURCE)

_TABLES = {"uk": {}, "en": dict(zip(SOURCE, EN)), "ru": dict(zip(SOURCE, RU))}
_lang = "uk"


def _load_cache() -> None:
    try:
        with open(CACHE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    for code, tbl in data.items():
        if not isinstance(tbl, dict) or code == "uk":
            continue
        cur = _TABLES.setdefault(code, {})
        for k, v in tbl.items():
            cur.setdefault(k, v)   # hand-written strings win over cached machine translations


def _save_cache(lang: str, new: dict) -> None:
    with _lock:
        try:
            with open(CACHE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        data.setdefault(lang, {}).update(new)
        try:
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except OSError:
            pass


# ---- automatic translation of any string without a translation yet ----
import threading  # noqa: E402
import time  # noqa: E402

_lock = threading.Lock()
_translator = None          # fn(list[str], lang) -> list[str]
_pending: dict = {}         # lang -> set of source strings waiting
_failed: dict = {}          # (lang, s) -> time of the last failed try
_wake = threading.Event()


def set_translator(fn) -> None:
    """Give l10n a translator (freeai.translate). From then on t() translates unknown strings by itself."""
    global _translator
    _translator = fn
    threading.Thread(target=_worker, daemon=True).start()


def _worker() -> None:
    while True:
        _wake.wait()
        time.sleep(0.4)        # gather the strings of one redraw into one request
        _wake.clear()
        with _lock:
            jobs = {lang: sorted(v) for lang, v in _pending.items() if v}
            _pending.clear()
        for lang, items in jobs.items():
            for i in range(0, len(items), 40):
                chunk = items[i:i + 40]
                try:
                    out = _translator(chunk, lang)
                except Exception:  # noqa: BLE001
                    out = chunk
                new = {src: dst for src, dst in zip(chunk, out) if dst and dst != src}
                for src in chunk:
                    if src not in new:
                        _failed[(lang, src)] = time.time()
                if new:
                    _TABLES.setdefault(lang, {}).update(new)
                    _save_cache(lang, new)


def _queue(lang: str, s: str) -> None:
    if _translator is None or not s.strip() or len(s) > 400:
        return
    if time.time() - _failed.get((lang, s), 0) < 120:   # retry a failed string at most every 2 min
        return
    with _lock:
        _pending.setdefault(lang, set()).add(s)
    _wake.set()


def ensure(lang: str, translate) -> bool:
    """Make sure a table exists for `lang` (machine-translating once). Blocking. True when ready."""
    if lang in _TABLES and (lang in ("uk", "en", "ru") or len(_TABLES[lang]) >= len(SOURCE) // 2):
        return True
    out = translate(EN, lang)   # English source translates better than Ukrainian slang
    if not out or out == EN:
        return False
    _TABLES[lang] = dict(zip(SOURCE, out))
    try:
        with open(CACHE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data[lang] = _TABLES[lang]
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return True


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang


def get_lang() -> str:
    return _lang


def _named(text: str) -> str:
    try:
        import freeai
        return freeai.fix_name(text, _lang)
    except Exception:  # noqa: BLE001
        return text


def t(s: str) -> str:
    """`s` in the current language. A string with no translation yet is queued for the translator
    and shown meanwhile in English (if known) or as is; the overlay redraws, so it updates by itself."""
    if _lang == "uk" or not s:
        return s
    if s in ("КЛОДІК", "Клодік"):   # the name itself: always the pet name, never a machine guess
        try:
            import freeai
            n = freeai.name_for(_lang)
            return n.upper() if s.isupper() else n
        except Exception:  # noqa: BLE001
            pass
    tbl = _TABLES.get(_lang, {})
    if s in tbl:
        return _named(tbl[s])
    _queue(_lang, s)
    return _named(_TABLES["en"].get(s, s))


_load_cache()
