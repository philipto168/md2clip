"""
md2clip - Convert markdown in clipboard to rich formatted text (HTML).

Usage:
    python md2clip.py          # one-shot: convert clipboard and exit
    python md2clip.py --tray   # run as system tray icon
"""

import sys
import time
import ctypes
import os
import configparser
from ctypes import wintypes
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
FONT_FAMILY = _config.get("style", "font_family", fallback="Calibri, sans-serif")
CODE_FONT_FAMILY = _config.get("style", "code_font_family", fallback="Consolas, Courier New, monospace")
CODE_FONT_SIZE = _config.getint("style", "code_font_size", fallback=10)

# Win32 clipboard API via ctypes (thread-safe)
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

OpenClipboard = user32.OpenClipboard
OpenClipboard.argtypes = [wintypes.HWND]
OpenClipboard.restype = wintypes.BOOL

CloseClipboard = user32.CloseClipboard
CloseClipboard.argtypes = []
CloseClipboard.restype = wintypes.BOOL

EmptyClipboard = user32.EmptyClipboard
EmptyClipboard.argtypes = []
EmptyClipboard.restype = wintypes.BOOL

SetClipboardData = user32.SetClipboardData
SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
SetClipboardData.restype = wintypes.HANDLE

GetClipboardData = user32.GetClipboardData
GetClipboardData.argtypes = [wintypes.UINT]
GetClipboardData.restype = wintypes.HANDLE

IsClipboardFormatAvailable = user32.IsClipboardFormatAvailable
IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
IsClipboardFormatAvailable.restype = wintypes.BOOL

RegisterClipboardFormatW = user32.RegisterClipboardFormatW
RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
RegisterClipboardFormatW.restype = wintypes.UINT

GlobalAlloc = kernel32.GlobalAlloc
GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
GlobalAlloc.restype = wintypes.HANDLE

GlobalLock = kernel32.GlobalLock
GlobalLock.argtypes = [wintypes.HANDLE]
GlobalLock.restype = ctypes.c_void_p

GlobalUnlock = kernel32.GlobalUnlock
GlobalUnlock.argtypes = [wintypes.HANDLE]
GlobalUnlock.restype = wintypes.BOOL

GMEM_MOVEABLE = 0x0002
CF_UNICODETEXT = 13


# Inline CSS that works well in OneNote, Outlook, Word
STYLE = """\
<style>
body { font-family: Calibri, Segoe UI, sans-serif; font-size: 11pt; line-height: 1.5; color: #1a1a1a; }
h1 { font-size: 18pt; font-weight: bold; margin: 12pt 0 6pt 0; color: #1a1a1a; }
h2 { font-size: 15pt; font-weight: bold; margin: 10pt 0 5pt 0; color: #1a1a1a; }
h3 { font-size: 12pt; font-weight: bold; margin: 8pt 0 4pt 0; color: #1a1a1a; }
h4 { font-size: 11pt; font-weight: bold; margin: 6pt 0 3pt 0; color: #1a1a1a; }
code { font-family: Consolas, Courier New, monospace; font-size: 10pt; background-color: #f4f4f4; padding: 1px 4px; border-radius: 3px; }
pre { font-family: Consolas, Courier New, monospace; font-size: 10pt; background-color: #f4f4f4; padding: 8pt; border-radius: 4px; border: 1px solid #e0e0e0; overflow-x: auto; white-space: pre-wrap; }
pre code { background-color: transparent; padding: 0; }
blockquote { border-left: 3px solid #0078d4; margin: 6pt 0; padding: 4pt 12pt; color: #444; background-color: #f8f9fa; }
table { border-collapse: collapse; margin: 8pt 0; }
th, td { border: 1px solid #c0c0c0; padding: 4pt 8pt; text-align: left; }
th { background-color: #f0f0f0; font-weight: bold; }
ul, ol { margin: 4pt 0; padding-left: 24pt; }
li { margin: 2pt 0; }
a { color: #0078d4; }
hr { border: none; border-top: 1px solid #d0d0d0; margin: 12pt 0; }
strong { font-weight: bold; }
em { font-style: italic; }
</style>
"""


def _open_clipboard(retries=10, delay=0.05):
    """Open clipboard with retries (handles thread contention)."""
    for i in range(retries):
        if OpenClipboard(None):
            return True
        time.sleep(delay)
    return False


def _alloc_global(data: bytes):
    """Allocate a GMEM_MOVEABLE block and copy data into it."""
    h = GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        raise MemoryError("GlobalAlloc failed")
    ptr = GlobalLock(h)
    if not ptr:
        raise MemoryError("GlobalLock failed")
    ctypes.memmove(ptr, data, len(data))
    GlobalUnlock(h)
    return h


def get_clipboard_text():
    """Get plain text from clipboard."""
    if not _open_clipboard():
        return None
    try:
        if IsClipboardFormatAvailable(CF_UNICODETEXT):
            h = GetClipboardData(CF_UNICODETEXT)
            if h:
                ptr = GlobalLock(h)
                if ptr:
                    text = ctypes.wstring_at(ptr)
                    GlobalUnlock(h)
                    return text
    finally:
        CloseClipboard()
    return None


def md_to_html(md_text):
    """Convert markdown to styled HTML with inline styles for Office compatibility."""
    import re as _re
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


def set_clipboard_html(html, plain_text):
    """Set clipboard with both HTML and plain text formats."""
    cf_html_fmt = RegisterClipboardFormatW("HTML Format")
    html_bytes = make_cf_html(html)

    if not _open_clipboard():
        raise RuntimeError("Could not open clipboard after retries.")
    try:
        EmptyClipboard()
        # Set HTML format (rich)
        h_html = _alloc_global(html_bytes)
        if not SetClipboardData(cf_html_fmt, h_html):
            raise RuntimeError(f"SetClipboardData HTML failed, error={ctypes.GetLastError()}")
        # Also keep plain text as fallback
        text_bytes = (plain_text + "\0").encode("utf-16-le")
        h_text = _alloc_global(text_bytes)
        if not SetClipboardData(CF_UNICODETEXT, h_text):
            raise RuntimeError(f"SetClipboardData text failed, error={ctypes.GetLastError()}")
    finally:
        CloseClipboard()


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

    # Register global hotkey (Ctrl+Alt+M) via Win32 API
    import threading

    MOD_CONTROL = 0x0002
    MOD_ALT = 0x0001
    MOD_NOREPEAT = 0x4000
    VK_M = 0x4D
    HOTKEY_ID = 1
    WM_HOTKEY = 0x0312

    # MSG structure for GetMessage
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
        """Listen for global hotkey in a separate thread."""
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

    hotkey_thread = threading.Thread(target=hotkey_listener, daemon=True)
    hotkey_thread.start()

    icon = pystray.Icon(
        "md2clip",
        create_icon_image(),
        "MD → Clipboard (Ctrl+Alt+M)",
        menu=pystray.Menu(
            pystray.MenuItem("Convert Clipboard (Ctrl+Alt+M)", on_convert, default=True),
            pystray.MenuItem("Quit", on_quit),
        ),
    )
    print("md2clip tray icon running. Ctrl+Alt+M to convert, or double-click icon.")
    icon.run()


if __name__ == "__main__":
    if "--tray" in sys.argv:
        run_tray()
    else:
        convert_clipboard()
