#!/bin/bash
# Makes the Raspberry Pi Zero 2W show up as a USB keyboard on its data port.
# Runs at boot (see usb-keyboard-gadget.service). Creates /dev/hidg0.
set -euo pipefail

GADGET=/sys/kernel/config/usb_gadget/keyboard

modprobe libcomposite

if [ -e "$GADGET/UDC" ] && [ -n "$(cat "$GADGET/UDC")" ]; then
    echo "Keyboard gadget is already set up."
    exit 0
fi

mkdir -p "$GADGET"
cd "$GADGET"

echo 0x1d6b > idVendor   # Linux Foundation
echo 0x0104 > idProduct  # Multifunction Composite Gadget
echo 0x0100 > bcdDevice  # v1.0.0
echo 0x0200 > bcdUSB     # USB 2

mkdir -p strings/0x409
echo "0000000000000001" > strings/0x409/serialnumber
echo "Raspberry Pi"     > strings/0x409/manufacturer
echo "Virtual Keyboard" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Keyboard" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower  # mA

# A standard boot-protocol keyboard: 8-byte reports
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' \
    > functions/hid.usb0/report_desc

ln -sf functions/hid.usb0 configs/c.1/
ls /sys/class/udc > UDC

# Let the listener (running as a normal user) write to the keyboard.
for _ in $(seq 1 20); do
    [ -e /dev/hidg0 ] && break
    sleep 0.25
done
chmod 666 /dev/hidg0
echo "Keyboard gadget ready at /dev/hidg0."
