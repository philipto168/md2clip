"""
md2clip - Convert markdown in clipboard to rich formatted text (HTML).

Usage:
    python md2clip.py          # one-shot: convert clipboard and exit
    python md2clip.py --tray   # run as system tray icon
"""

import sys
import time
import os
import platform
import configparser
import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.nl2br import Nl2BrExtension

# Load config from md2clip.ini next to this script
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "md2clip.ini")
_config = configparser.ConfigParser()
_config.read(_CONFIG_PATH)

FONT_SIZE = _config.getint("style", "font_size", fallback=11)
FONT_FAMILY = _config.get("style", "font_family", fallback="Aptos, Calibri, sans-serif")
CODE_FONT_FAMILY = _config.get("style", "code_font_family", fallback="Consolas, Courier New, monospace")
CODE_FONT_SIZE = _config.getint("style", "code_font_size", fallback=10)
CONTENT_BOX = _config.getboolean("style", "content_box", fallback=True)

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

# ─── Platform-specific clipboard implementation ───────────────────────────────

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    _OpenClipboard = user32.OpenClipboard
    _OpenClipboard.argtypes = [wintypes.HWND]
    _OpenClipboard.restype = wintypes.BOOL

    _CloseClipboard = user32.CloseClipboard
    _CloseClipboard.argtypes = []
    _CloseClipboard.restype = wintypes.BOOL

    _EmptyClipboard = user32.EmptyClipboard
    _EmptyClipboard.argtypes = []
    _EmptyClipboard.restype = wintypes.BOOL

    _SetClipboardData = user32.SetClipboardData
    _SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    _SetClipboardData.restype = wintypes.HANDLE

    _GetClipboardData = user32.GetClipboardData
    _GetClipboardData.argtypes = [wintypes.UINT]
    _GetClipboardData.restype = wintypes.HANDLE

    _IsClipboardFormatAvailable = user32.IsClipboardFormatAvailable
    _IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    _IsClipboardFormatAvailable.restype = wintypes.BOOL

    _RegisterClipboardFormatW = user32.RegisterClipboardFormatW
    _RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    _RegisterClipboardFormatW.restype = wintypes.UINT

    _GlobalAlloc = kernel32.GlobalAlloc
    _GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _GlobalAlloc.restype = wintypes.HANDLE

    _GlobalLock = kernel32.GlobalLock
    _GlobalLock.argtypes = [wintypes.HANDLE]
    _GlobalLock.restype = ctypes.c_void_p

    _GlobalUnlock = kernel32.GlobalUnlock
    _GlobalUnlock.argtypes = [wintypes.HANDLE]
    _GlobalUnlock.restype = wintypes.BOOL

    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    def _open_clipboard_win(retries=10, delay=0.05):
        for i in range(retries):
            if _OpenClipboard(None):
                return True
            time.sleep(delay)
        return False

    def _alloc_global(data: bytes):
        h = _GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            raise MemoryError("GlobalAlloc failed")
        ptr = _GlobalLock(h)
        if not ptr:
            raise MemoryError("GlobalLock failed")
        ctypes.memmove(ptr, data, len(data))
        _GlobalUnlock(h)
        return h

    def get_clipboard_text():
        if not _open_clipboard_win():
            return None
        try:
            if _IsClipboardFormatAvailable(CF_UNICODETEXT):
                h = _GetClipboardData(CF_UNICODETEXT)
                if h:
                    ptr = _GlobalLock(h)
                    if ptr:
                        text = ctypes.wstring_at(ptr)
                        _GlobalUnlock(h)
                        return text
        finally:
            _CloseClipboard()
        return None

    def set_clipboard_html(html, plain_text):
        cf_html_fmt = _RegisterClipboardFormatW("HTML Format")
        html_bytes = make_cf_html(html)
        if not _open_clipboard_win():
            raise RuntimeError("Could not open clipboard after retries.")
        try:
            _EmptyClipboard()
            h_html = _alloc_global(html_bytes)
            if not _SetClipboardData(cf_html_fmt, h_html):
                raise RuntimeError(f"SetClipboardData HTML failed, error={ctypes.GetLastError()}")
            text_bytes = (plain_text + "\0").encode("utf-16-le")
            h_text = _alloc_global(text_bytes)
            if not _SetClipboardData(CF_UNICODETEXT, h_text):
                raise RuntimeError(f"SetClipboardData text failed, error={ctypes.GetLastError()}")
        finally:
            _CloseClipboard()

elif IS_MACOS:
    import subprocess

    def get_clipboard_text():
        try:
            result = subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=5
            )
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    def set_clipboard_html(html, plain_text):
        """Set macOS clipboard with HTML (public.html) and plain text via AppleScript + pbcopy."""
        # Use osascript to set both HTML and plain text on the pasteboard
        # This is the most reliable way without PyObjC
        applescript = f'''
use framework "AppKit"
set theHTML to "{_escape_applescript(html)}"
set theText to "{_escape_applescript(plain_text)}"
set pb to current application's NSPasteboard's generalPasteboard()
pb's clearContents()
pb's setString:theHTML forType:(current application's NSPasteboardType's NSHTMLPboardType)
pb's setString:theText forType:(current application's NSPasteboardType's NSStringPboardType)
'''
        # AppleScript has string length limits; use a temp file approach instead
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            html_path = f.name
        try:
            # Use hexdump + osascript for reliable HTML pasteboard setting
            script = f'''
set htmlData to (read POSIX file "{html_path}" as «class utf8»)
set pb to current application's NSPasteboard's generalPasteboard()
pb's clearContents()
pb's setString:htmlData forType:"public.html"
pb's setString:"{_escape_applescript(plain_text)}" forType:"public.utf8-plain-text"
'''
            subprocess.run(
                ["osascript", "-l", "AppleScript", "-e",
                 'use framework "AppKit"', "-e", script],
                capture_output=True, timeout=10,
            )
        finally:
            os.unlink(html_path)

    def _escape_applescript(s):
        """Escape a string for AppleScript."""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")

else:
    # Linux / other — use xclip if available
    import subprocess

    def get_clipboard_text():
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    def set_clipboard_html(html, plain_text):
        """Set clipboard HTML via xclip."""
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard", "-t", "text/html"],
                stdin=subprocess.PIPE
            )
            proc.communicate(html.encode("utf-8"))
        except FileNotFoundError:
            raise RuntimeError("xclip not found. Install with: sudo apt install xclip")


def _preprocess_md(md_text):
    """Enhance markdown before conversion: detect informal headers (lines ending with colon)."""
    import re
    lines = md_text.splitlines()
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Standalone short line ending with ':' → make it bold (informal header)
        # Must not be inside a list, not already bold, and reasonably short
        if (stripped.endswith(':') and
                len(stripped) <= 80 and
                not stripped.startswith(('#', '-', '*', '+', '>', '`')) and
                not re.match(r'^\d+\.', stripped) and
                not stripped.startswith('**')):
            # Check it's a standalone paragraph (blank line before or start of doc)
            prev_blank = (i == 0 or not lines[i-1].strip())
            if prev_blank:
                result.append(f'**{stripped}**')
                continue
        result.append(line)
    return '\n'.join(result)


def md_to_html(md_text):
    """Convert markdown to styled HTML with inline styles for Office compatibility."""
    import re as _re

    # Pre-process: enhance informal headers
    md_text = _preprocess_md(md_text)

    extensions = [
        TableExtension(),
        FencedCodeExtension(),
        CodeHiliteExtension(css_class="highlight", noclasses=True),
        Nl2BrExtension(),
        "markdown.extensions.sane_lists",
        "markdown.extensions.smarty",
    ]
    html_body = markdown.markdown(md_text, extensions=extensions)

    # OneNote/Outlook ignore <style> blocks — inject inline styles directly
    # Font sizes scale relative to the configured base size
    sz = FONT_SIZE
    h1_sz = sz + 7
    h2_sz = sz + 4
    h3_sz = sz + 1
    h4_sz = sz
    ff = FONT_FAMILY
    cff = CODE_FONT_FAMILY
    csz = CODE_FONT_SIZE

    inline_styles = {
        "<h1": f'<h1 style="font-size:{h1_sz}pt;font-weight:bold;margin:12pt 0 6pt 0;font-family:{ff};"',
        "<h2": f'<h2 style="font-size:{h2_sz}pt;font-weight:bold;margin:10pt 0 5pt 0;font-family:{ff};"',
        "<h3": f'<h3 style="font-size:{h3_sz}pt;font-weight:bold;margin:8pt 0 4pt 0;font-family:{ff};"',
        "<h4": f'<h4 style="font-size:{h4_sz}pt;font-weight:bold;margin:6pt 0 3pt 0;font-family:{ff};"',
        "<p": f'<p style="font-family:{ff};font-size:{sz}pt;line-height:1.5;margin:4pt 0;"',
        "<ul": f'<ul style="font-family:{ff};font-size:{sz}pt;margin:4pt 0;padding-left:24pt;"',
        "<ol": f'<ol style="font-family:{ff};font-size:{sz}pt;margin:4pt 0;padding-left:24pt;"',
        "<li": '<li style="margin:2pt 0;"',
        "<blockquote": f'<blockquote style="border-left:3px solid #0078d4;margin:6pt 0;padding:4pt 12pt;color:#444;background-color:#f8f9fa;font-family:{ff};font-size:{sz}pt;"',
        "<table": f'<table style="border-collapse:collapse;margin:8pt 0;font-family:{ff};font-size:{sz}pt;"',
        "<th": '<th style="border:1px solid #c0c0c0;padding:4pt 8pt;text-align:left;background-color:#f0f0f0;font-weight:bold;"',
        "<td": '<td style="border:1px solid #c0c0c0;padding:4pt 8pt;text-align:left;"',
        "<pre": f'<pre style="font-family:{cff};font-size:{csz}pt;background-color:#f4f4f4;padding:8pt;border:1px solid #e0e0e0;white-space:pre-wrap;"',
        "<code": f'<code style="font-family:{cff};font-size:{csz}pt;background-color:#f4f4f4;padding:1px 4px;"',
        "<hr": '<hr style="border:none;border-top:1px solid #d0d0d0;margin:12pt 0;"',
    }

    for tag, replacement in inline_styles.items():
        # Replace both <tag> and <tag attr...>
        html_body = _re.sub(
            _re.escape(tag) + r'([ >])',
            replacement + r'\1',
            html_body
        )

    # For <pre><code> combos, remove background from inner code
    html_body = html_body.replace(
        f'style="font-family:{cff};font-size:{csz}pt;background-color:#f4f4f4;padding:1px 4px;">',
        f'style="font-family:{cff};font-size:{csz}pt;">',
    )

    # Wrap code blocks in a table cell for reliable shaded box in OneNote/Outlook
    # OneNote ignores background-color on <pre>/<div> but respects it on <td>
    # Handle CodeHilite output: <div class="highlight" style="..."><pre ...>...</pre></div>
    html_body = _re.sub(
        r'<div class="[^"]*"[^>]*>\s*(<pre[^>]*>)(.*?)(</pre>)\s*</div>',
        lambda m: (
            f'<table style="border-collapse:collapse;margin:8pt 0;width:100%;"><tr>'
            f'<td style="background-color:#f4f4f4;border:1px solid #e0e0e0;padding:8pt;">'
            f'<pre style="font-family:{cff};font-size:{csz}pt;margin:0;white-space:pre-wrap;">'
            + m.group(2)
            + f'</pre></td></tr></table>'
        ),
        html_body,
        flags=_re.DOTALL,
    )

    # Optionally wrap entire content in a bordered box (like ChatGPT's card UI)
    if CONTENT_BOX:
        html_body = (
            f'<table style="border-collapse:collapse;margin:4pt 0;width:100%;"><tr>'
            f'<td style="border:1px solid #d0d0d0;padding:12pt 16pt;border-radius:6px;'
            f'font-family:{ff};font-size:{sz}pt;line-height:1.5;">'
            f'{html_body}'
            f'</td></tr></table>'
        )

    html = f"<html><body>{html_body}</body></html>"
    return html


def make_cf_html(html):
    """Build the CF_HTML clipboard format with required header."""
    # CF_HTML requires a specific header with byte offsets
    header_template = (
        "Version:0.9\r\n"
        "StartHTML:{start_html:010d}\r\n"
        "EndHTML:{end_html:010d}\r\n"
        "StartFragment:{start_frag:010d}\r\n"
        "EndFragment:{end_frag:010d}\r\n"
    )
    # Calculate with dummy values first to get header length
    dummy_header = header_template.format(
        start_html=0, end_html=0, start_frag=0, end_frag=0
    )
    # The fragment markers
    start_marker = "<!--StartFragment-->"
    end_marker = "<!--EndFragment-->"

    # Build the full content
    # Insert fragment markers around the body content
    html_with_markers = html.replace("<body>", f"<body>{start_marker}")
    html_with_markers = html_with_markers.replace("</body>", f"{end_marker}</body>")

    # Encode to get byte positions
    encoded = html_with_markers.encode("utf-8")
    header_len = len(dummy_header.encode("utf-8"))

    start_html = header_len
    end_html = header_len + len(encoded)
    start_frag = header_len + encoded.find(start_marker.encode("utf-8")) + len(
        start_marker.encode("utf-8")
    )
    end_frag = header_len + encoded.find(end_marker.encode("utf-8"))

    header = header_template.format(
        start_html=start_html,
        end_html=end_html,
        start_frag=start_frag,
        end_frag=end_frag,
    )

    return (header + html_with_markers).encode("utf-8") + b"\0"


def looks_like_markdown(text):
    """Check if text contains markdown formatting indicators."""
    import re

    lines = text.splitlines()
    indicators = 0

    for line in lines:
        # Headers
        if re.match(r"^#{1,6}\s", line):
            indicators += 1
        # Unordered list items
        elif re.match(r"^\s*[-*+]\s", line):
            indicators += 1
        # Ordered list items
        elif re.match(r"^\s*\d+\.\s", line):
            indicators += 1
        # Blockquotes
        elif re.match(r"^\s*>", line):
            indicators += 1
        # Table rows
        elif re.match(r"^\s*\|.*\|", line):
            indicators += 1
        # Horizontal rules
        elif re.match(r"^\s*([-*_])\s*\1\s*\1", line):
            indicators += 1
        # Fenced code blocks
        elif re.match(r"^\s*```", line):
            indicators += 1

    # Inline patterns (check whole text)
    # Bold/italic
    indicators += len(re.findall(r"\*\*[^*]+\*\*", text))
    indicators += len(re.findall(r"__[^_]+__", text))
    # Inline code
    indicators += len(re.findall(r"`[^`]+`", text))
    # Links [text](url)
    indicators += len(re.findall(r"\[[^\]]+\]\([^)]+\)", text))
    # Images ![alt](url)
    indicators += len(re.findall(r"!\[[^\]]*\]\([^)]+\)", text))

    return indicators >= 2


def convert_clipboard():
    """Main conversion: read MD from clipboard, write HTML back."""
    text = get_clipboard_text()
    if not text:
        print("Clipboard is empty or has no text.")
        return False

    text = text.strip()
    if not text:
        print("Clipboard text is empty.")
        return False

    if not looks_like_markdown(text):
        print("Clipboard does not appear to contain markdown. No changes made.")
        return False

    html = md_to_html(text)
    set_clipboard_html(html, text)
    print(f"Converted {len(text)} chars of markdown to rich text. Ready to paste!")
    return True


def run_tray():
    """Run as system tray icon."""
    import threading
    import pystray
    from PIL import Image, ImageDraw, ImageFont

    def create_icon_image():
        """Create a simple 'M' icon."""
        img = Image.new("RGB", (64, 64), color=(0, 120, 212))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("segoeui.ttf", 36)
        except OSError:
            font = ImageFont.load_default()
        draw.text((14, 10), "M", fill="white", font=font)
        return img

    def on_convert(icon, item):
        """Tray menu: convert clipboard."""
        convert_clipboard()

    def on_quit(icon, item):
        icon.stop()

    # Platform-specific global hotkey registration
    hotkey_label = ""

    if IS_WINDOWS:
        import ctypes
        from ctypes import wintypes

        MOD_CONTROL = 0x0002
        MOD_ALT = 0x0001
        MOD_NOREPEAT = 0x4000
        VK_M = 0x4D
        HOTKEY_ID = 1
        WM_HOTKEY = 0x0312

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("pt", wintypes.POINT),
            ]

        def hotkey_listener():
            RegisterHotKey = user32.RegisterHotKey
            RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            RegisterHotKey.restype = wintypes.BOOL
            GetMessageW = user32.GetMessageW
            GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            GetMessageW.restype = wintypes.BOOL

            if not RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_M):
                print("Warning: Could not register Ctrl+Alt+M hotkey (may be in use).")
                return
            print("Global hotkey: Ctrl+Alt+M")
            msg = MSG()
            while GetMessageW(ctypes.byref(msg), None, 0, 0):
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    convert_clipboard()

        threading.Thread(target=hotkey_listener, daemon=True).start()
        hotkey_label = " (Ctrl+Alt+M)"

    elif IS_MACOS:
        # On macOS, suggest using system Automator/Shortcuts for a global hotkey,
        # or use pynput if installed
        try:
            from pynput import keyboard

            HOTKEY_COMBO = {keyboard.Key.cmd, keyboard.Key.alt, keyboard.KeyCode.from_char('m')}
            current_keys = set()

            def on_press(key):
                current_keys.add(key)
                if HOTKEY_COMBO.issubset(current_keys):
                    convert_clipboard()

            def on_release(key):
                current_keys.discard(key)

            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.daemon = True
            listener.start()
            hotkey_label = " (Cmd+Opt+M)"
            print("Global hotkey: Cmd+Opt+M")
        except ImportError:
            print("Tip: Install 'pynput' for global hotkey support on macOS.")
            print("  pip install pynput")
            hotkey_label = ""

    icon = pystray.Icon(
        "md2clip",
        create_icon_image(),
        f"MD → Clipboard{hotkey_label}",
        menu=pystray.Menu(
            pystray.MenuItem(f"Convert Clipboard{hotkey_label}", on_convert, default=True),
            pystray.MenuItem("Quit", on_quit),
        ),
    )
    print(f"md2clip tray icon running.{hotkey_label} to convert, or double-click icon.")
    icon.run()


if __name__ == "__main__":
    if "--tray" in sys.argv:
        run_tray()
    else:
        convert_clipboard()
