"""Claude Code hook -> writes Klodik's state, one file per chat in sessions/. Called for every hook event."""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS = os.path.join(HERE, "sessions")


def mood_for_tool(tool: str) -> str:
    t = tool or ""
    if t in ("Read", "NotebookRead"):
        return "reading"
    if t in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return "writing"
    if t in ("Bash", "PowerShell"):
        return "running"
    if t in ("Grep", "Glob", "ToolSearch"):
        return "searching"
    if t in ("WebSearch", "WebFetch") or "Browser" in t or "chrome" in t:
        return "web"
    if t in ("Agent", "Task", "SendMessage"):
        return "agent"
    if t in ("AskUserQuestion", "ExitPlanMode"):
        return "asking"
    return "thinking"


def last_assistant_text(data: dict) -> str:
    msg = data.get("last_assistant_message")
    if isinstance(msg, str) and msg.strip():
        return msg
    path = data.get("transcript_path")
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-200:]
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") != "assistant":
            continue
        content = (row.get("message") or {}).get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text = "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                return text
    return ""


def main() -> None:
    if os.environ.get("CLAUDIK_INTERNAL"):
        return  # Klodik's own helper calls: don't react to them
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")  # Windows stdin isn't UTF-8 by default
    except ValueError:
        data = {}
    event = data.get("hook_event_name", "")
    state = {"event": event, "ts": time.time(), "cwd": data.get("cwd") or os.getcwd(), "tool": data.get("tool_name", "")}

    if event == "UserPromptSubmit":
        state["mood"] = "thinking"
        state["prompt"] = str(data.get("prompt") or "")[:300]   # overlay guesses your language from it
    elif event == "PreToolUse":
        state["mood"] = mood_for_tool(state["tool"])
    elif event in ("PostToolUse", "PostToolUseFailure"):
        state["mood"] = "thinking"   # a helper agent finishing (SubagentStop) says nothing about the main chat
    elif event == "Notification":
        state["mood"] = "asking"
        state["text"] = (data.get("message") or "")[:200]
    elif event == "Stop":
        state["mood"] = "done"
        state["text"] = last_assistant_text(data)[:4000]
    elif event == "StopFailure":
        state["mood"] = "error"
    elif event == "SessionStart":
        state["mood"] = "idle"
    else:
        return

    # One file per chat, so the overlay can follow the chat the user picked.
    sid = "".join(c for c in str(data.get("session_id") or "unknown") if c.isalnum() or c in "-_")[:64]
    path = os.path.join(SESSIONS, sid + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            prev = json.load(f)
    except (OSError, ValueError):
        prev = {}
    if float(prev.get("ts", 0)) > state["ts"]:
        return  # hooks run async: a late PostToolUse must not overwrite the Stop that came after it
    state["sid"] = sid
    state["title"] = app_title(data.get("transcript_path")) or prev.get("title") or ""
    if not state["title"] and event == "UserPromptSubmit":
        state["title"] = " ".join(str(data.get("prompt") or "").split())[:48]  # until the app names the chat
    os.makedirs(SESSIONS, exist_ok=True)
    write_json(path, state)


def app_title(transcript: str | None) -> str:
    """The chat's name as the app's sidebar shows it: the last "custom-title" record in the transcript."""
    if not transcript:
        return ""
    try:
        with open(transcript, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 512 * 1024))  # shortcut: tail only; the app repeats the record often
            tail = f.read().decode("utf-8", "ignore")
    except OSError:
        return ""
    found = re.findall(r'"customTitle":("(?:[^"\\]|\\.)*")', tail)
    try:
        return json.loads(found[-1]).strip()[:60] if found else ""
    except ValueError:
        return ""


def write_json(path: str, obj: dict) -> None:
    tmp = path + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    for _ in range(5):  # Windows refuses the replace while the overlay is reading the file
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.remove(tmp)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never break Claude because of the mascot
