# md2clip

Convert markdown on your clipboard to rich formatted text — then paste into OneNote, Outlook, Word, or Teams with proper formatting.

No more pasting raw `#` headers, `**bold**`, and `` ```code blocks``` `` into your notes. Copy from ChatGPT, GitHub Copilot, or any AI chat → convert → paste beautifully.

## The Problem

You copy a response from ChatGPT or Copilot Chat. You paste it into OneNote. You get this:

```
## Steps
1. Run `scripts/validate_pm_schema.py`.
2. Run `scripts/analyze_pm_stats.py`.
```

Instead of nicely formatted headings, bold text, code blocks, and tables.

## The Solution

**md2clip** sits in your system tray. Press **Ctrl+Alt+M** (or double-click the tray icon), and your clipboard is instantly converted from markdown to rich text. Paste with Ctrl+V and get:

- Formatted **headings** (H1–H4)
- **Bold**, *italic*, and `inline code`
- Fenced code blocks in **shaded gray boxes** with syntax highlighting
- Tables with borders
- Bulleted and numbered lists
- Blockquotes with blue left border

Works with **OneNote**, **Outlook**, **Word**, **Teams**, and any app that supports rich paste.

## Install

Requires **Python 3.10+** and **Windows**.

```powershell
git clone https://github.com/philipto168/md2clip.git
cd md2clip
.\install.ps1
```

This creates a virtual environment, installs dependencies, and adds `md2clip` to your PATH.

## Usage

### One-shot (CLI)

```
md2clip
```

Reads markdown from clipboard, converts to rich text, puts it back. Then paste.

### System tray (background)

```
md2clip --tray
```

Runs silently in the background. Convert anytime with:

- **Ctrl+Alt+M** — global hotkey (works from any app)
- **Double-click** the tray icon
- **Right-click** → Convert Clipboard

The tray mode uses `pythonw.exe` so there's no console window.

### Auto-start on login

The installer can create a Windows Startup shortcut:

```powershell
$startup = [Environment]::GetFolderPath("Startup")
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut("$startup\md2clip.lnk")
$shortcut.TargetPath = "C:\Tools\md2clip\.venv\Scripts\pythonw.exe"
$shortcut.Arguments = "C:\Tools\md2clip\md2clip.py --tray"
$shortcut.Save()
```

## Configuration

Edit `md2clip.ini` to customize fonts and sizes:

```ini
[style]
font_size = 11
font_family = Calibri, sans-serif
code_font_family = Consolas, Courier New, monospace
code_font_size = 10
```

Headings scale automatically relative to `font_size` (H1 = +7pt, H2 = +4pt, H3 = +1pt).

Changes take effect on the next conversion — no restart needed.

## How It Works

1. Reads plain text (markdown) from the Windows clipboard
2. Checks if it looks like markdown (headers, bold, code blocks, lists, etc.)
3. Converts to HTML using the Python `markdown` library with Pygments syntax highlighting
4. Injects **inline CSS** on every element (OneNote/Outlook ignore `<style>` blocks)
5. Wraps code blocks in `<table><td>` with background color (the only way to get shaded boxes in OneNote)
6. Sets the clipboard as `CF_HTML` + `CF_UNICODETEXT` via Win32 API
7. Apps that support rich paste (OneNote, Outlook, Word) pick up the HTML; plain-text editors get the original text

## Dependencies

- [markdown](https://pypi.org/project/markdown/) — Markdown to HTML conversion
- [Pygments](https://pypi.org/project/Pygments/) — Syntax highlighting for code blocks
- [pystray](https://pypi.org/project/pystray/) — System tray icon
- [Pillow](https://pypi.org/project/Pillow/) — Icon image generation

No external tools (no pandoc, no Node.js). Pure Python + Win32 API via ctypes.

## License

MIT
