#!/bin/bash
# Install AGY Context HUD as a macOS LaunchAgent (auto-starts on login)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.gr1nis.agy-context-hud.plist"

mkdir -p "$PLIST_DIR"

cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gr1nis.agy-context-hud</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$DIR/hud_app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "✓ AGY Context HUD зарегистрирован в LaunchAgents macOS: $PLIST_PATH"
echo "Запущен через launchctl."
