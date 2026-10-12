#!/bin/bash
# Sets up a Raspberry Pi Zero 2W as the bot's "hands". Run on the Pi from this folder:
#     sudo ./install.sh
# Then reboot, and move the cable to the Pi's USB (data) port.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run with sudo: sudo ./install.sh"
    exit 1
fi
RUN_AS="${SUDO_USER:-pi}"
HERE="$(cd "$(dirname "$0")" && pwd)"

# 1. Let the USB port act as a device (a "gadget") instead of a host.
BOOT_CONFIG=/boot/firmware/config.txt
[ -f "$BOOT_CONFIG" ] || BOOT_CONFIG=/boot/config.txt
grep -q '^dtoverlay=dwc2' "$BOOT_CONFIG" || echo 'dtoverlay=dwc2' >> "$BOOT_CONFIG"
for module in dwc2 libcomposite; do
    grep -q "^$module\$" /etc/modules || echo "$module" >> /etc/modules
done

# 2. Turn off services from an earlier, hand-made setup (they'd claim the same USB
#    port and network port). Names from the original build; harmless if missing.
for old in xbox_bot.service virtual_keyboard.service; do
    if systemctl cat "$old" >/dev/null 2>&1; then
        echo "Turning off the old $old"
        systemctl disable --now "$old" || true
    fi
done

# 3. Install the scripts.
install -m 755 "$HERE/usb-keyboard-gadget.sh" /usr/local/bin/usb-keyboard-gadget.sh
install -m 755 "$HERE/listener.py" /usr/local/bin/bejeweled-listener.py

# 4. Start both at every boot.
install -m 644 "$HERE/usb-keyboard-gadget.service" /etc/systemd/system/
sed "s/__USER__/$RUN_AS/" "$HERE/bejeweled-listener.service" > /etc/systemd/system/bejeweled-listener.service
systemctl daemon-reload
systemctl enable usb-keyboard-gadget.service bejeweled-listener.service

echo
echo "Done. Next:"
echo "  1. sudo poweroff"
echo "  2. Move the cable to the Pi's USB (data) port and plug it into the Cronus Zen."
echo "  3. Check it's running:  systemctl status bejeweled-listener"
echo "  4. Find the Pi's address for config.toml:  hostname -I"
