#!/bin/bash
# Phase 0: Pre-flight for the dicti dictation stack.
# Installs apt packages, adds user to the input group, creates a uinput udev rule.
# Idempotent. Safe to re-run. Debian/Ubuntu (apt) assumed.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash $0"
  exit 1
fi

REAL_USER="${SUDO_USER:-}"
if [[ -z "$REAL_USER" || "$REAL_USER" == "root" ]]; then
  echo "Could not determine the target user. Run via sudo as your normal user."
  exit 1
fi

echo "==> Installing apt packages"
apt update
apt install -y \
  keyd \
  ydotool \
  pipewire-bin \
  wev \
  evtest \
  libnotify-bin \
  libvulkan-dev \
  vulkan-tools \
  glslc \
  glslang-tools \
  spirv-headers \
  python3-venv \
  python3-pip \
  python3-requests \
  xclip \
  x11-utils \
  wl-clipboard \
  netcat-openbsd \
  cmake \
  git \
  build-essential

echo "==> Adding $REAL_USER to input group (for keyd + uinput access)"
if id -nG "$REAL_USER" | tr ' ' '\n' | grep -qx input; then
  echo "    already in input group"
else
  usermod -aG input "$REAL_USER"
  echo "    ADDED. Logout/login required before keyd or ydotoold will work for this user."
fi

echo "==> Installing udev rule for /dev/uinput (input group, mode 0660)"
RULE=/etc/udev/rules.d/60-uinput.rules
cat > "$RULE" <<'EOF'
# dicti dictation: allow input group to use uinput (for keyd + ydotoold)
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
EOF
udevadm control --reload-rules
udevadm trigger /dev/uinput || true
ls -l /dev/uinput

echo "==> Verifying critical bins"
for bin in keyd ydotool xclip pw-record evtest cmake notify-send; do
  if command -v "$bin" >/dev/null; then
    printf "    OK  %s -> %s\n" "$bin" "$(command -v "$bin")"
  else
    printf "    MISSING %s\n" "$bin"
  fi
done

echo
echo "==> Pre-flight done."
echo "    NEXT: log out and back in (or reboot) so 'input' group membership takes effect."
echo "    The top-bar indicator is a dicti GNOME Shell extension (installed in phase 7),"
echo "    so no generic AppIndicator extension is needed. (Only the optional non-GNOME"
echo "    indicator.py needs: python3-gi gir1.2-ayatanaappindicator3-0.1.)"
echo "    Then run: sudo bash 01-install-keyd.sh"
