"""Free LLM backend for Claudik.

Order: Groq (if GROQ_API_KEY) -> Gemini lite models (GEMINI_API_KEY, ~1 s) -> Pollinations
(free, no key, 1 reply per 45 s). Keys come from env vars or keys.json next to this file.

    from freeai import ask
    text = ask("question", system="be brief")   # returns str or None
"""
import json
import re
import os
import urllib.error
import urllib.request

TIMEOUT = 45
FAST_TIMEOUT = 8   # per fast model; a slow model is skipped instead of waited for
_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")


def _key(name):
    """Env var first, then keys.json next to this file."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        with open(_KEYS_FILE, encoding="utf-8") as f:
            return json.load(f).get(name)
    except Exception:
        return None


def _post(url, payload, headers=None, timeout=None):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "claudik-overlay")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _openai_style(url, model, messages, key=None, timeout=None):
    h = {"Authorization": f"Bearer {key}"} if key else None
    out = _post(url, {"model": model, "messages": messages}, h, timeout)
    return out["choices"][0]["message"]["content"].strip()


GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.8-flash"]


def _groq(messages):
    key = _key("GROQ_API_KEY")
    if not key:
        return None
    return _openai_style("https://api.groq.com/openai/v1/chat/completions",
                         "llama-3.3-70b-versatile", messages, key, FAST_TIMEOUT)


def _gemini(messages):
    key = _key("GEMINI_API_KEY")
    if not key:
        return None
    # Lite models answer in ~1-2 s; try them in order, each with a short timeout.
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    last = None
    for model in GEMINI_MODELS:
        try:
            return _openai_style(url, model, messages, key, FAST_TIMEOUT)
        except Exception as e:  # overloaded / retired / slow: next one
            last = e
    raise last


def _pollinations(messages):
    # Anonymous tier: 1 reply per 45 s per IP. On FREE_LIMIT wait as long as the server says, once.
    import re, time
    key = _key("POLLINATIONS_KEY")
    url = "https://text.pollinations.ai/openai"
    try:
        return _openai_style(url, "openai", messages, key)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        m = re.search(r"Retry after (\d+)s", body)
        if e.code not in (402, 429) or not m:
            raise
        time.sleep(int(m.group(1)) + 1)
        return _openai_style(url, "openai", messages, key)


LANGS = {   # code -> (menu label, name the model understands)
    "uk": ("Українська", "Ukrainian"),
    "en": ("English", "English"),
    "ru": ("Русский", "Russian"),
    "pl": ("Polski", "Polish"),
    "de": ("Deutsch", "German"),
    "es": ("Español", "Spanish"),
}

# Klodik's affectionate name in each language (a pet form of "Claude").
NAMES = {"uk": "Клодік", "en": "Claudie", "ru": "Клодик", "pl": "Claudek", "de": "Claudchen", "es": "Claudito"}

PERSONA = (
    "You are {name}, a tiny orange pixel-art crab mascot sitting in the corner of the "
    "user's screen, watching Claude Code work on their project. You are cute, cheerful and a bit "
    "playful, you talk like a friend, informally. Answer VERY briefly: 1-3 sentences, because your "
    "words appear in a small speech bubble above you. No markdown, no lists, no code; one emoji at "
    "most. If you don't know something about the project, say so honestly and suggest asking Claude "
    "itself. Never invent facts about files or code."
)


def name_for(lang):
    return NAMES.get(lang, "Claudie")


_NAME_RE = re.compile(r"\b(?:[KC]l[oóa]u?d[iíy]k|Claudik|Клод[іи]к|КЛОД[ІИ]К)\w*", re.IGNORECASE)


def fix_name(text, lang):
    """Replace any spelling of the mascot's name (Klodik, Clodik, Клодик...) with this language's pet name."""
    if not text or not lang:
        return text
    name = name_for(lang)

    def rep(m):
        w = m.group(0)
        return name.upper() if w.isupper() and len(w) > 1 else name
    return _NAME_RE.sub(rep, text)


def _lang_rule(lang):
    name = LANGS.get(lang, (None, None))[1]
    return f"Always reply in {name}, whatever language the input is in." if name else         "Reply in the language the user writes in."


def detect_lang(text):
    """Guess uk/ru/en/pl/de/es from a user's own writing; None if unsure."""
    t = (text or "").lower()
    if not t.strip():
        return None
    if any(c in t for c in "ієїґ"):
        return "uk"
    if any(c in t for c in "ыэъё"):
        return "ru"
    cyr = sum("а" <= c <= "я" for c in t)
    lat = sum("a" <= c <= "z" for c in t)
    if cyr > lat:
        return "uk"   # Cyrillic with no telltale letters: lean Ukrainian
    if any(c in t for c in "ąćęłńóśźż"):
        return "pl"
    if any(c in t for c in "äöüß"):
        return "de"
    if any(c in t for c in "ñ¿¡"):
        return "es"
    return "en" if lat else None


def ask(prompt, system=None, lang=None, persona=True):
    sys_text = (PERSONA.replace("{name}", name_for(lang)) if persona else "You are a precise translator. "
                f"The mascot's name is written as {name_for(lang)} in this language.") + "\n\n" + _lang_rule(lang) + ("\n\n" + system if system else "")
    messages = [{"role": "system", "content": sys_text}]
    lname = LANGS.get(lang, (None, None))[1]
    if lname:   # lite models follow a reminder next to the input better than one in the system prompt
        prompt = f"{prompt}\n\n(Reply only in {lname}.)" if persona else prompt
    messages.append({"role": "user", "content": prompt})
    for backend in (_groq, _gemini, _pollinations):
        try:
            text = backend(messages)
            if text:
                return fix_name(text, lang)
        except Exception:
            continue
    return None


def summarize(answer_text, lang=None):
    """<=10-word summary of what Claude just did."""
    return ask(
        answer_text[:4000],
        system="You are given Claude's report of the work it just finished. Retell it as yourself in "
               "ONE very short sentence (max 10 words), no intro, no quotes: what was done.",
        lang=lang,
    )


def chat(question, context="", lang=None):
    """Answer a user's question about the project. `context` = recent Claude activity/answers."""
    prompt = question if not context else f"What Claude did recently:\n{context[:6000]}\n\nQuestion: {question}"
    return ask(prompt, lang=lang)


def translate(texts, lang):
    """Translate a list of short bubble/chat texts into `lang`, keeping order and the mascot's tone.
    Returns a list of the same length (originals kept where translation failed)."""
    texts = list(texts)
    if not texts or lang not in LANGS:
        return texts
    name = LANGS[lang][1]
    payload = json.dumps(texts, ensure_ascii=False)
    out = ask(
        payload,
        system=f"Translate each string of this JSON array into {name}. Keep meaning, tone, emoji, "
               "names, file names and code as is. Reply with ONLY a JSON array of the same length. Do not add emoji.",
        lang=lang,
        persona=False,
    )
    if not out:
        return texts
    out = out.strip().strip("`")
    if out.lower().startswith("json"):
        out = out[4:]
    try:
        arr = json.loads(out[out.index("["): out.rindex("]") + 1])
    except ValueError:
        return texts
    if not isinstance(arr, list) or len(arr) != len(texts):
        return texts
    return [str(x) if isinstance(x, str) and x.strip() else t for x, t in zip(arr, texts)]


if __name__ == "__main__":
    import sys
    print(ask(" ".join(sys.argv[1:]) or "Скажи привіт одним словом", system="Відповідай коротко."))
