# Klodik: a pixel desk buddy for Claude Code

Klodik is a small pixel-art crab that sits on your desktop, above every window,
and reacts to what Claude Code is doing. He flinches when you grab him, puts on
headphones when you plug them in, dances to music, and changes outfit with the
season: spring sprout and tea, sakura with bows, Neon Miami, Halloween and more.

Click him to ask a question about the project you are working on, or pick a chat
from the right-click menu to follow.

## What he reacts to

- Claude Code hooks: thinking, reading, writing, running commands, searching, waiting for you, done, error.
- Plugged-in devices on Windows: headphones, game controllers, other Bluetooth gadgets.
- Music playing on the PC (Windows media session): he sways and shows the track.
- Idle time: he plays one of a dozen small shows, and falls asleep after five minutes.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer, with tkinter (the standard installer includes it)
- Claude Code

## Install

1. Copy the folder somewhere permanent, for example `%USERPROFILE%\.claude\claudik`.
2. Add the hooks to `%USERPROFILE%\.claude\settings.json`, replacing the two paths with your own:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "C:/Python310/pythonw.exe", "args": ["C:/Users/YOU/.claude/claudik/hook.py"], "async": true}]}],
    "PreToolUse":       [{"hooks": [{"type": "command", "command": "C:/Python310/pythonw.exe", "args": ["C:/Users/YOU/.claude/claudik/hook.py"], "async": true}]}],
    "PostToolUse":      [{"hooks": [{"type": "command", "command": "C:/Python310/pythonw.exe", "args": ["C:/Users/YOU/.claude/claudik/hook.py"], "async": true}]}],
    "Stop":             [{"hooks": [{"type": "command", "command": "C:/Python310/pythonw.exe", "args": ["C:/Users/YOU/.claude/claudik/hook.py"], "async": true}]}],
    "SessionStart":     [{"hooks": [{"type": "command", "command": "C:/Python310/pythonw.exe", "args": ["C:/Users/YOU/.claude/claudik/hook.py"], "async": true}]}]
  }
}
```

3. Start him: double-click `overlay.pyw` (or run `pythonw overlay.pyw`).
4. Right-click him and choose **Autostart with Windows** to start him at login.

## Controls

- **Drag** him to move him. He struggles while you hold him.
- **Click** him (or the hint under him) to open the chat box. Enter sends, Esc closes.
- **Right-click** for the menu: connect to a chat, language, theme, do-not-disturb, autostart, clear chat, quit.
- **Do not disturb** makes him click-through. A quick triple click on him brings him back.

## Free AI backends (optional)

Chat answers and translations use free services, and nothing is required to run him:

- Pollinations (no key needed, rate limited)
- Groq or Gemini, if you add a key

To add a key, create `keys.json` next to `freeai.py`:

```json
{"GEMINI_API_KEY": "your key here"}
```

or set the same name as an environment variable. Keep `keys.json` private; it is listed in `.gitignore`.

## Files

| File | What it is |
|---|---|
| `overlay.pyw` | The window, the chat, the menus, the animation loop |
| `world.py` | Themes, weather, costumes, devices and music |
| `hook.py` | Claude Code hook: writes one state file per chat |
| `freeai.py` | Free LLM backends for chat and translation |
| `l10n.py` | Interface strings and translations |
| `test_claudik.py` | Self-check: logic plus a draw of every state |

## Tests

```powershell
python test_claudik.py
```

The test uses a temporary config file and never touches your settings.

## Limits

- Windows only: device and music detection use Windows APIs.
- The free chat backend cannot read your project files; it only sees what Claude said in recent answers.

## License

MIT, see [LICENSE](LICENSE).
