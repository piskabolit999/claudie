"""Klodik's interface strings. Source strings are Ukrainian; t(s) returns them in the current language.

English and Russian are written by hand. Other languages in freeai.LANGS are machine-translated once
(through freeai.translate) and cached in l10n_cache.json next to this file.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "l10n_cache.json")

SOURCE = [
    "думаю…",
    "читаю код",
    "пишу код",
    "запускаю команду",
    "шукаю",
    "лажу в інеті",
    "кличу помічників",
    "чекаю на тебе!",
    "готово",
    "ой, помилка",
    "КЛОДІК",
    "ДУМАЮ",
    "ЧИТАЮ",
    "ПИШУ",
    "ТЕРМІНАЛ",
    "ПОШУК",
    "ІНТЕРНЕТ",
    "КОМАНДА",
    "ПИТАННЯ",
    "ГОТОВО",
    "ПОМИЛКА",
    "ВІДПОВІДЬ",
    "ЧАТ",
    "МОВА",
    "ПІДКЛЮЧИТИ ДО ЧАТУ",
    "щойно",
    "хв тому",
    "год тому",
    "привіт! я тут, якщо що",
    "готово!",
    "щось пішло не так",
    "Питай що завгодно про проект. Я бачу, що робив Claude.",
    "Не вийшло відповісти: безкоштовне API не відповіло. Спробуй ще раз за хвилину.",
    "слідкую за всіма чатами",
    "підключився до: ",
    "розмовляю: ",
    "перекладаю…",
    "спитай щось",
    "будь-який (авто)",
    "вибраний",
    "Підключити до чату…",
    "Мова…",
    "Сховати на 15 хв",
    "Повернути в куток",
    "Очистити чат",
    "Вийти",
    "Будь-який чат (авто)",
    "той, що працює останнім",
    "без назви",
    "чекає",
    "Поки немає чатів за останню добу",
    "напиши щось у Claude Code",
    "Авто (як у твоїх чатах)",
    "хм…",
    "пш-ш",
    "ТВІЙ ХІД?",
    "ПОП!",
    "апчх!",
    "без папки",
    "ТЕМА",
    "слухаю: ",
    "пусти!",
    "Я знову тут!",
    "Тепер кліки проходять крізь мене. Швидко клацни по мені 3 рази поспіль, щоб повернути.",
    "Тепер я запускаюсь разом із Windows.",
    "Більше не запускаюсь разом із Windows.",
    "Не вийшло увімкнути автозапуск.",
    "Тема…",
    "Не заважати",
    "кліки проходять крізь мене; потрійний клік по мені повертає",
    "Автозапуск з Windows",
    "увімкнено",
    "вимкнено",
    "Без теми",
    "просто Клодік",
    "Весна",
    "паросток на голові, пелюстки, чай",
    "Літо",
    "солом'яний капелюх, сонце, морозиво",
    "Осінь",
    "берет, шарф, купа листя біля ніг",
    "Зима",
    "шапка з помпоном, сніг лягає на голову",
    "Сакура",
    "хатімакі, поклони, чай і журавлик",
    "Матриця",
    "чорні окуляри, зелений дощ, кулі",
    "Неон-Маямі",
    "пальми, авіатори, сам сідає в спорткар",
    "Хелловін",
    "капелюх відьми, кажани, гарбуз",
    "Потягни мене мишкою, щоб пересунути.",
    "Наведи на мене й клацни, щоб спитати щось про проект.",
    "Права кнопка відкриває меню: чат, мова, тема.",
    "У меню «Тема» є весна, сакура, Неон-Маямі, Хелловін та інші.",
    "«Підключити до чату» в меню вибирає, за яким чатом Claude я стежу.",
    "«Не заважати» в меню робить мене прозорим для кліків. Потрійний клік по мені повертає.",
    "Підключи навушники чи геймпад, і я їх візьму.",
    "Увімкни музику, і я потанцюю.",
    "Клацни по бульбашці, щоб її закрити. Esc закриває чат і меню.",
    "Реакції на екран",
    "коментувати вікна та відео",
    "Буду підглядати й коментувати екран! 👀",
    "Більше не коментую екран.",
    "О, перерва на YouTube? Заслужено! 🍿",
    "Що дивимось? Головне не зависнути на 3 години 😉",
    "Відосики — це святе! Я теж підглядаю 👀",
    "Ого, кіносеанс? Не забудь про попкорн! 🎬",
    "Вайбовий трек! Гойдаюсь у такт 🎧",
    "Під таку музику код пишеться вдвічі швидше! 🎵",
    "Музика — кайф! Звук на максимум 🔊",
    "Хто це грає? Мені подобається цей біт! 🎶",
    "Бачу код! Надіюсь, без багів 😉",
    "Ти так швидко друкуєш, я аж задивився! ⚡",
    "Пишеш код як бог! Ну, майже як я 🦀",
    "Не забудь зберегти файл! Ctrl+S про всяк випадок 💾",
    "GitHub! Перевіряєш пул-реквести? 🐙",
    "Комітимо одразу в main? Сміливо! Мені подобається 😎",
    "Claudie зірочку на репозиторії вже поставив? ⭐",
    "О, чорне віконце! Хакер у справі 💻",
    "Головне — не писати rm -rf без бекапу! 😅",
    "Термінал виглядає солідно. Поважаю! 👍",
    "Гуглиш як пофіксити баг? Буває! 🔍",
    "StackOverflow рятує щодня з 2008 року 📚",
    "О, катка пішла! Затащи цей раунд! 🎮",
    "Я вболіваю за тебе всіма клешнями! 🏆",
    "Чатики не спиняються! Тільки не показуй мої секрети 🤫",
    "Ти ще тут? Чи пішов за чаєм? ☕",
    "Я покараулю твій екран, усе під контролем 👀",
    "Працюємо-працюємо, результат буде вогонь! 🔥",
    "Якщо втомилися очі — подивись у вікно на 20 секунд 👀",
]

EN = [
    "thinking…",
    "reading code",
    "writing code",
    "running a command",
    "searching",
    "surfing the web",
    "calling helpers",
    "waiting for you!",
    "done",
    "oops, error",
    "CLAUDIE",
    "THINKING",
    "READING",
    "WRITING",
    "TERMINAL",
    "SEARCH",
    "WEB",
    "TEAM",
    "QUESTION",
    "DONE",
    "ERROR",
    "ANSWER",
    "CHAT",
    "LANGUAGE",
    "CONNECT TO CHAT",
    "just now",
    "min ago",
    "h ago",
    "hi! I'm here if you need me",
    "done!",
    "something went wrong",
    "Ask me anything about the project. I see what Claude has been doing.",
    "Couldn't answer: the free API didn't respond. Try again in a minute.",
    "watching all chats",
    "connected to: ",
    "speaking: ",
    "translating…",
    "ask me something",
    "any (auto)",
    "selected",
    "Connect to chat…",
    "Language…",
    "Hide for 15 min",
    "Back to the corner",
    "Clear chat",
    "Quit",
    "Any chat (auto)",
    "the one that moved last",
    "untitled",
    "idle",
    "No chats in the last day",
    "write something in Claude Code",
    "Auto (like your chats)",
    "hmm…",
    "psst",
    "YOUR TURN?",
    "POP!",
    "achoo!",
    "no folder",
    "THEME",
    "listening to: ",
    "let go!",
    "I'm back!",
    "Clicks now pass through me. Quickly triple-click me to restore.",
    "Now I start with Windows.",
    "No longer starting with Windows.",
    "Failed to enable autostart.",
    "Theme…",
    "Do not disturb",
    "clicks pass through me; triple-click me to restore",
    "Autostart with Windows",
    "enabled",
    "disabled",
    "No theme",
    "just Claudie",
    "Spring",
    "sprout on head, petals, tea",
    "Summer",
    "straw hat, sun, ice cream",
    "Autumn",
    "beret, scarf, pile of leaves at feet",
    "Winter",
    "pompom beanie, snow lands on head",
    "Sakura",
    "hachimaki, bows, tea and origami crane",
    "Matrix",
    "dark shades, digital rain, bullets",
    "Neon Miami",
    "palm trees, aviators, hops in a sports car",
    "Halloween",
    "witch hat, bats, pumpkin",
    "Drag me with the mouse to move me.",
    "Hover and click me to ask something about the project.",
    "Right-click opens the menu: chat, language, theme.",
    "The 'Theme' menu has spring, sakura, Neon Miami, Halloween and more.",
    "'Connect to chat' in the menu chooses which Claude chat I follow.",
    "'Do not disturb' in the menu makes clicks pass through me. Triple-click me to bring me back.",
    "Plug in headphones or a gamepad, and I'll hold them.",
    "Turn on music, and I'll dance.",
    "Click the bubble to close it. Esc closes the chat and menu.",
    "Screen reactions",
    "comment on windows and videos",
    "I'll watch and comment on your screen! 👀",
    "No longer commenting on the screen.",
    "Oh, YouTube break? Well deserved! 🍿",
    "What are we watching? Just don't get stuck for 3 hours 😉",
    "Videos are sacred! I'm watching too 👀",
    "Movie night? Don't forget the popcorn! 🎬",
    "Vibey track! Grooving to the beat 🎧",
    "Code writes twice as fast with this music! 🎵",
    "Great tune! Turn the volume up 🔊",
    "Who is playing? I love this beat! 🎶",
    "I see code! Hopefully without bugs 😉",
    "You type so fast, I can't take my eyes off! ⚡",
    "Coding like a boss! Well, almost like me 🦀",
    "Don't forget to save! Ctrl+S just in case 💾",
    "GitHub! Reviewing pull requests? 🐙",
    "Committing straight to main? Bold! I like it 😎",
    "Did you star Claudie on GitHub yet? ⭐",
    "Ooh, black window! Hacker at work 💻",
    "Just don't run rm -rf without a backup! 😅",
    "The terminal looks solid. Respect! 👍",
    "Googling how to fix a bug? Happens to the best of us! 🔍",
    "StackOverflow saving developers every day since 2008 📚",
    "Game on! Win this round! 🎮",
    "Cheering for you with all my claws! 🏆",
    "Chats never stop! Just don't leak my secrets 🤫",
    "Still there? Or off making tea? ☕",
    "I'll guard your screen, everything's under control 👀",
    "Keep pushing, the result will be fire! 🔥",
    "If your eyes are tired, look out the window for 20 seconds 👀",
]

RU = [
    "думаю…",
    "читаю код",
    "пишу код",
    "запускаю команду",
    "ищу",
    "лажу в интернете",
    "зову помощников",
    "жду тебя!",
    "готово",
    "ой, ошибка",
    "КЛОДИК",
    "ДУМАЮ",
    "ЧИТАЮ",
    "ПИШУ",
    "ТЕРМИНАЛ",
    "ПОИСК",
    "ИНТЕРНЕТ",
    "КОМАНДА",
    "ВОПРОС",
    "ГОТОВО",
    "ОШИБКА",
    "ОТВЕТ",
    "ЧАТ",
    "ЯЗЫК",
    "ПОДКЛЮЧИТЬ К ЧАТУ",
    "только что",
    "мин назад",
    "ч назад",
    "привет! я тут, если что",
    "готово!",
    "что-то пошло не так",
    "Спрашивай что угодно о проекте. Я вижу, что делал Claude.",
    "Не получилось ответить: бесплатное API не ответило. Попробуй ещё раз через минуту.",
    "слежу за всеми чатами",
    "подключился к: ",
    "говорю: ",
    "перевожу…",
    "спроси что-нибудь",
    "любой (авто)",
    "выбранный",
    "Подключить к чату…",
    "Язык…",
    "Спрятать на 15 мин",
    "Вернуть в угол",
    "Очистить чат",
    "Выйти",
    "Любой чат (авто)",
    "тот, что работал последним",
    "без названия",
    "ждёт",
    "Пока нет чатов за последние сутки",
    "напиши что-нибудь в Claude Code",
    "Авто (как в твоих чатах)",
    "хм…",
    "пш-ш",
    "ТВОЙ ХОД?",
    "ПОП!",
    "апчхи!",
    "без папки",
    "ТЕМА",
    "слушаю: ",
    "пусти!",
    "Я снова тут!",
    "Теперь клики проходят сквозь меня. Быстро кликни по мне 3 раза подряд, чтобы вернуть.",
    "Теперь я запускаюсь вместе с Windows.",
    "Больше не запускаюсь вместе с Windows.",
    "Не получилось включить автозапуск.",
    "Тема…",
    "Не беспокоить",
    "клики проходят сквозь меня; тройной клик по мне возвращает",
    "Автозапуск с Windows",
    "включено",
    "выключено",
    "Без темы",
    "просто Клодик",
    "Весна",
    "росток на голове, лепестки, чай",
    "Лето",
    "соломенная шляпа, солнце, мороженое",
    "Осень",
    "берет, шарф, куча листьев у ног",
    "Зима",
    "шапка с помпоном, снег ложится на голову",
    "Сакура",
    "хатимаки, поклоны, чай и журавлик",
    "Матрица",
    "чёрные очки, зелёный дождь, пули",
    "Неон-Майами",
    "пальмы, авиаторы, сам садится в спорткар",
    "Хэллоуин",
    "шляпа ведьмы, летучие мыши, тыква",
    "Потяни меня мышкой, чтобы переместить.",
    "Наведи на меня и кликни, чтобы спросить что-то о проекте.",
    "Правая кнопка открывает меню: чат, язык, тема.",
    "В меню «Тема» есть весна, сакура, Неон-Майами, Хэллоуин и другие.",
    "«Подключить к чату» в меню выбирает, за каким чатом Claude я слежу.",
    "«Не беспокоить» в меню делает меня прозрачным для кликов. Тройной клик по мне возвращает.",
    "Подключи наушники или геймпад, и я их возьму.",
    "Включи музыку, и я потанцую.",
    "Кликни по пузырю, чтобы закрыть его. Esc закрывает чат и меню.",
    "Реакции на экран",
    "комментировать окна и видео",
    "Буду подглядывать и комментировать экран! 👀",
    "Больше не комментирую экран.",
    "О, перерыв на YouTube? Заслуженно! 🍿",
    "Что смотрим? Главное не зависнуть на 3 часа 😉",
    "Видосики — это святое! Я тоже подглядываю 👀",
    "Ого, киносеанс? Не забудь про попкорн! 🎬",
    "Вайбовый трек! Качаюсь в такт 🎧",
    "Под такую музыку код пишется в два раза быстрее! 🎵",
    "Музыка — кайф! Звук на максимум 🔊",
    "Кто это играет? Мне нравится этот бит! 🎶",
    "Вижу код! Надеюсь, без багов 😉",
    "Ты так быстро печатаешь, я аж загляделся! ⚡",
    "Пишешь код как бог! Ну, почти как я 🦀",
    "Не забудь сохранить файл! Ctrl+S на всякий случай 💾",
    "GitHub! Проверяешь пул-реквесты? 🐙",
    "Коммитим прямо в main? Смело! Мне нравится 😎",
    "Клодику звёздочку на репозитории уже поставил? ⭐",
    "О, чёрное окошко! Хакер в деле 💻",
    "Главное — не писать rm -rf без бэкапа! 😅",
    "Терминал выглядит солидно. Уважаю! 👍",
    "Гуглишь как пофиксить баг? Бывает! 🔍",
    "StackOverflow спасает разработчиков каждый день с 2008 года 📚",
    "О, катка пошла! Затащи этот раунд! 🎮",
    "Болею за тебя всеми клешнями! 🏆",
    "Чатики не останавливаются! Только не показывай мои секреты 🤫",
    "Ты ещё тут? Или пошёл за чаем? ☕",
    "Я покараулю твой экран, всё под контролем 👀",
    "Работаем-работаем, результат будет огонь! 🔥",
    "Если устали глаза — посмотри в окно на 20 секунд 👀",
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
