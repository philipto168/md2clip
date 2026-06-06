# md2clip

Convert markdown on your clipboard to rich formatted text — then paste into OneNote, Outlook, Word, or Teams with proper formatting.

No more pasting raw `#` headers, `**bold**`, and `` ```code blocks``` `` into your notes. Copy from ChatGPT, GitHub Copilot, or any AI chat → convert → paste beautifully.

**Works on Windows, macOS, and Linux.**

## The Problem

You copy a response from ChatGPT or Copilot Chat. You paste it into OneNote. You get this:

```
## Steps
1. Run `scripts/validate_pm_schema.py`.
2. Run `scripts/analyze_pm_stats.py`.
```

Instead of nicely formatted headings, bold text, code blocks, and tables.

## The Solution

**md2clip** sits in your system tray (or macOS menu bar). Press a hotkey, and your clipboard is instantly converted from markdown to rich text. Paste with Ctrl+V (or Cmd+V) and get:

- Formatted **headings** (H1–H4)
- **Bold**, *italic*, and `inline code`
- Fenced code blocks in **shaded gray boxes** with syntax highlighting
- Tables with borders
- Bulleted and numbered lists
- Blockquotes with blue left border
- Informal headers auto-detected (lines ending with `:` get bolded)
- Optional bordered card wrapper (like ChatGPT's UI)

Works with **OneNote**, **Outlook**, **Word**, **Teams**, **Apple Mail**, **Pages**, and any app that supports rich paste.

## Install

Requires **Python 3.10+**.

### Windows

```powershell
git clone https://github.com/philipto168/md2clip.git
cd md2clip
.\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/philipto168/md2clip.git
cd md2clip
chmod +x install.sh
./install.sh
```

The installer creates a virtual environment, installs dependencies, and makes `md2clip` available from your terminal.

## Usage

### One-shot (CLI)

```
md2clip
```

Reads markdown from clipboard, converts to rich text, puts it back. Then paste.

### System tray / menu bar (background)

```
md2clip --tray
```

Runs silently in the background. Convert anytime with:

| Platform | Hotkey | Alternative |
|----------|--------|-------------|
| Windows | **Ctrl+Alt+M** | Double-click tray icon |
| macOS | **Cmd+Opt+M** | Click menu bar icon |

On Windows, tray mode uses `pythonw.exe` (no console window).

### Auto-start on login

**Windows:**

```powershell
$startup = [Environment]::GetFolderPath("Startup")
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut("$startup\md2clip.lnk")
$shortcut.TargetPath = "C:\Tools\md2clip\.venv\Scripts\pythonw.exe"
$shortcut.Arguments = "C:\Tools\md2clip\md2clip.py --tray"
$shortcut.Save()
```

**macOS:**

1. Open **System Settings → General → Login Items**
2. Click **+** under "Open at Login"
3. Navigate to the `md2clip` script in your clone directory

## Configuration

Edit `md2clip.ini` to customize fonts and sizes:

```ini
[style]
font_size = 11
font_family = Aptos, SF Pro, Helvetica Neue, Calibri, sans-serif
code_font_family = Consolas, Menlo, Courier New, monospace
code_font_size = 10
content_box = true
```

| Setting | Description |
|---------|-------------|
| `font_size` | Base body text size (pt). Headings scale: H1=+7, H2=+4, H3=+1 |
| `font_family` | Font cascade — first available is used (Aptos on Windows, SF Pro on macOS) |
| `code_font_family` | Monospace font for code blocks (Consolas on Windows, Menlo on macOS) |
| `code_font_size` | Code block font size (pt) |
| `content_box` | Wrap output in a subtle bordered card (`true`/`false`) |

Changes take effect on the next conversion — no restart needed.

## How It Works

1. Reads plain text (markdown) from the clipboard
2. Checks if it looks like markdown (headers, bold, code blocks, lists, etc.) — skips plain text
3. Converts to HTML using the Python `markdown` library with Pygments syntax highlighting
4. Injects **inline CSS** on every element (OneNote/Outlook ignore `<style>` blocks)
5. Wraps code blocks in `<table><td>` with background color (reliable shaded boxes across all apps)
6. Sets the clipboard with rich HTML format:
   - **Windows:** `CF_HTML` + `CF_UNICODETEXT` via Win32 API (ctypes)
   - **macOS:** `public.html` + `public.utf8-plain-text` via NSPasteboard
   - **Linux:** `text/html` via xclip
7. Apps that support rich paste pick up the HTML; plain-text editors get the original text

## Dependencies

- [markdown](https://pypi.org/project/markdown/) — Markdown to HTML conversion
- [Pygments](https://pypi.org/project/Pygments/) — Syntax highlighting for code blocks
- [pystray](https://pypi.org/project/pystray/) — System tray / menu bar icon
- [Pillow](https://pypi.org/project/Pillow/) — Icon image generation
- [pynput](https://pypi.org/project/pynput/) — *(optional, macOS only)* Global hotkey support

No external tools (no pandoc, no Node.js). Pure Python + native OS APIs.

## macOS Notes

- The **Cmd+Opt+M** hotkey requires `pynput` (optional during install) and **Accessibility** permission
- Grant access in: **System Settings → Privacy & Security → Accessibility** → add your Python or Terminal app
- Without `pynput`, the menu bar icon still works via click

## License

MIT
