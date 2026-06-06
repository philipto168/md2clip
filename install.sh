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
echo "Note: On macOS, grant Accessibility permission for global hotkey."
echo "For auto-start, add md2clip --tray to Login Items in System Settings."
