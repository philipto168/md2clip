#!/bin/bash
# Install md2clip on macOS
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Installing md2clip..."

# Create venv
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

# Install dependencies
"$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet

# Optional: install pynput for global hotkey
read -p "Install pynput for Cmd+Opt+M hotkey? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    "$SCRIPT_DIR/.venv/bin/pip" install pynput --quiet
    echo "  pynput installed. Grant Accessibility permission when prompted."
fi

# Create shell wrapper
cat > "$SCRIPT_DIR/md2clip" << EOF
#!/bin/bash
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/md2clip.py" "\$@"
EOF
chmod +x "$SCRIPT_DIR/md2clip"

# Symlink to /usr/local/bin
if [ -d "/usr/local/bin" ]; then
    ln -sf "$SCRIPT_DIR/md2clip" /usr/local/bin/md2clip 2>/dev/null || true
    echo "Linked to /usr/local/bin/md2clip"
fi

echo ""
echo "Done! Usage:"
echo "  md2clip        # Convert clipboard markdown to rich text (one-shot)"
echo "  md2clip --tray # Run as menu bar icon"
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "IMPORTANT: Grant Accessibility permission for hotkey"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "The Cmd+Opt+M hotkey requires Accessibility access."
    echo "macOS will prompt you on first run. If it doesn't:"
    echo ""
    echo "  1. Open System Settings → Privacy & Security → Accessibility"
    echo "  2. Click the + button"
    echo "  3. Navigate to: $SCRIPT_DIR/.venv/bin/python"
    echo "     (or /usr/local/bin/python3 if using system Python)"
    echo "  4. Toggle it ON"
    echo ""
    echo "If you use Terminal.app or iTerm2 to run md2clip --tray,"
    echo "you may also need to add your terminal app to the list."
    echo ""
fi

echo "Auto-start on login:"
echo "  1. Open System Settings → General → Login Items"
echo "  2. Click + under 'Open at Login'"
echo "  3. Navigate to: $SCRIPT_DIR/md2clip"
echo "  Or create an Automator app that runs: md2clip --tray"
echo ""
