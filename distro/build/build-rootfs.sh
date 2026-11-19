#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Phase 2: Build pinned Debian 12 (bookworm) OS-1 userspace rootfs and persistent ext4 disk image.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
ROOTFS_DIR="${OUT_ROOT}/rootfs"
IMAGE_DIR="${OUT_ROOT}/images"
DISK_IMG="${IMAGE_DIR}/os1-rootfs.ext4.img"

DEBIAN_SUITE="${OS1_DEBIAN_SUITE:-bookworm}"
DEBIAN_MIRROR="${OS1_DEBIAN_MIRROR:-http://deb.debian.org/debian}"
OS1_PROFILE="${OS1_PROFILE:-minimal}"
if [[ "${OS1_PROFILE}" == "desktop" ]]; then
    IMAGE_SIZE_MB="${OS1_ROOTFS_SIZE_MB:-6144}"
else
    IMAGE_SIZE_MB="${OS1_ROOTFS_SIZE_MB:-2048}"
fi
DEV_USER="${OS1_DEV_USER:-os1}"
DEV_PASS="${OS1_DEV_PASS:-os1}"
DESKTOP_AUTOLOGIN="${OS1_DESKTOP_AUTOLOGIN:-0}"

PACKAGES=(
    systemd
    systemd-sysv
    libpam-systemd
    dbus
    dbus-user-session
    udev
    sudo
    locales
    tzdata
    ca-certificates
    apt
    network-manager
    iproute2
    iputils-ping
    dnsutils
    curl
    openssh-client
    pipewire
    wireplumber
    pipewire-audio
    kmod
    e2fsprogs
    dosfstools
    parted
    grub-efi-amd64-bin
    grub-common
    nano
    less
    bash-completion
    procps
    util-linux
    login
    passwd
)

DESKTOP_PACKAGES=(
    plasma-desktop
    plasma-workspace-wayland
    kwin-wayland
    sddm
    breeze
    breeze-icon-theme
    qml-module-org-kde-qqc2desktopstyle
    qtwayland5
    libqt5svg5
    systemsettings
    xkb-data
    xwayland
    xserver-xorg-core
    xserver-xorg-input-libinput
    xserver-xorg-video-fbdev
    libgl1
    libegl1
    libgles2
    libgl1-mesa-dri
    mesa-vulkan-drivers
    libegl-mesa0
    libgbm1
    pipewire-pulse
    pipewire-alsa
    xdg-desktop-portal-kde
    polkit-kde-agent-1
    kscreen
    plasma-nm
    plasma-pa
    upower
    konsole
    dolphin
    kio-extras
    libnotify-bin
    firefox-esr
    kate
    gwenview
    okular
    kcalc
    ark
    kde-spectacle
    plasma-systemmonitor
    fonts-noto-core
    fonts-noto-color-emoji
    fonts-dejavu-core
    fonts-liberation
    fontconfig
    dbus-x11
)

if [[ "${OS1_PROFILE}" == "desktop" ]]; then
    PACKAGES+=("${DESKTOP_PACKAGES[@]}")
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: build-rootfs.sh must run as root (e.g. via sudo) to preserve rootfs ownership and chroot." >&2
    exit 1
fi

check_disk_space_mb() {
    local target_dir="$1"
    local required_mb="$2"
    mkdir -p "${target_dir}"
    local avail_mb
    avail_mb="$(df -Pm "${target_dir}" | awk 'NR==2 {print $4}')"
    if (( avail_mb < required_mb )); then
        echo "ERROR: Insufficient disk space in ${target_dir}: ${avail_mb} MiB available, ${required_mb} MiB required." >&2
        exit 1
    fi
    echo "[os1-rootfs] Disk preflight OK: ${avail_mb} MiB available (need >= ${required_mb} MiB)"
}

if [[ "${OS1_PROFILE}" == "desktop" ]]; then
    check_disk_space_mb "${OUT_ROOT}" 8192
else
    check_disk_space_mb "${OUT_ROOT}" 4096
fi

if ! command -v mkfs.ext4 >/dev/null 2>&1; then
    echo "ERROR: mkfs.ext4 (e2fsprogs) not found." >&2
    exit 1
fi

rm -rf "${ROOTFS_DIR}"
mkdir -p "${ROOTFS_DIR}" "${IMAGE_DIR}"

PKG_CSV="$(IFS=,; echo "${PACKAGES[*]}")"

if command -v mmdebstrap >/dev/null 2>&1; then
    echo "[os1-rootfs] Bootstrapping Debian ${DEBIAN_SUITE} via mmdebstrap..."
    mmdebstrap \
        --arch=amd64 \
        --variant=minbase \
        --include="${PKG_CSV}" \
        "${DEBIAN_SUITE}" \
        "${ROOTFS_DIR}" \
        "${DEBIAN_MIRROR}"
elif command -v debootstrap >/dev/null 2>&1; then
    echo "[os1-rootfs] Bootstrapping Debian ${DEBIAN_SUITE} via debootstrap..."
    debootstrap \
        --arch=amd64 \
        --variant=minbase \
        --include="${PKG_CSV}" \
        "${DEBIAN_SUITE}" \
        "${ROOTFS_DIR}" \
        "${DEBIAN_MIRROR}"
else
    echo "ERROR: Neither mmdebstrap nor debootstrap is installed." >&2
    exit 1
fi

echo "[os1-rootfs] Configuring OS-1 system identity, networking, storage, locales, and user..."

# OS identity
cat > "${ROOTFS_DIR}/etc/os-release" <<EOF
PRETTY_NAME="OS-1 0.2-dev (Debian ${DEBIAN_SUITE} base)"
NAME="OS-1"
VERSION_ID="0.2"
VERSION="0.2-dev (Phase 2)"
ID=os1
ID_LIKE=debian
HOME_URL="https://github.com/mirzotipi-wq/OS-1"
SUPPORT_URL="https://github.com/mirzotipi-wq/OS-1/issues"
BUG_REPORT_URL="https://github.com/mirzotipi-wq/OS-1/issues"
EOF

echo "os1" > "${ROOTFS_DIR}/etc/hostname"

cat > "${ROOTFS_DIR}/etc/hosts" <<'EOF'
127.0.0.1	localhost
127.0.1.1	os1
::1		localhost ip6-localhost ip6-loopback
EOF

cat > "${ROOTFS_DIR}/etc/fstab" <<'EOF'
LABEL=OS1_ROOT  /  ext4  defaults,noatime,errors=remount-ro  0  1
EOF

# APT sources (pinned Debian stable + security + updates)
cat > "${ROOTFS_DIR}/etc/apt/sources.list" <<EOF
deb ${DEBIAN_MIRROR} ${DEBIAN_SUITE} main contrib non-free-firmware
deb ${DEBIAN_MIRROR} ${DEBIAN_SUITE}-updates main contrib non-free-firmware
deb http://security.debian.org/debian-security ${DEBIAN_SUITE}-security main contrib non-free-firmware
EOF

# Persistent systemd journal
mkdir -p "${ROOTFS_DIR}/var/log/journal"
mkdir -p "${ROOTFS_DIR}/etc/systemd/journald.conf.d"
cat > "${ROOTFS_DIR}/etc/systemd/journald.conf.d/10-os1-persistent.conf" <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=128M
EOF

# NetworkManager: manage all ethernet interfaces and DNS cleanly
mkdir -p "${ROOTFS_DIR}/etc/NetworkManager/conf.d"
cat > "${ROOTFS_DIR}/etc/NetworkManager/conf.d/10-os1-managed.conf" <<'EOF'
[main]
dns=default

[ifupdown]
managed=true
EOF

# Locale & timezone
sed -i 's/^# *en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' "${ROOTFS_DIR}/etc/locale.gen" || echo "en_US.UTF-8 UTF-8" >> "${ROOTFS_DIR}/etc/locale.gen"
echo "LANG=en_US.UTF-8" > "${ROOTFS_DIR}/etc/default/locale"
ln -sf /usr/share/zoneinfo/UTC "${ROOTFS_DIR}/etc/localtime"
echo "UTC" > "${ROOTFS_DIR}/etc/timezone"

# Install OS-1 kernel modules if present from Phase 1 (--with-modules)
if [[ -d "${OUT_ROOT}/kernel/modules/lib/modules" ]]; then
    echo "[os1-rootfs] Installing OS-1 kernel modules..."
    mkdir -p "${ROOTFS_DIR}/lib/modules"
    cp -a "${OUT_ROOT}/kernel/modules/lib/modules/." "${ROOTFS_DIR}/lib/modules/"
fi

# Configure inside chroot
chroot "${ROOTFS_DIR}" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin DEBIAN_FRONTEND=noninteractive bash -euo pipefail -c "
locale-gen
# Lock root password by default; administration via non-root sudo user
passwd -l root
# Create non-root bring-up user (replaced by installer/onboarding in Phase 4/10)
if ! id -u '${DEV_USER}' >/dev/null 2>&1; then
    useradd -m -s /bin/bash -G sudo,audio,video,netdev,plugdev '${DEV_USER}'
fi
echo '${DEV_USER}:${DEV_PASS}' | chpasswd
systemctl enable NetworkManager.service
systemctl enable serial-getty@ttyS0.service
"

# Sudo policy (standard least-privilege password-authenticated sudo for %sudo)
cat > "${ROOTFS_DIR}/etc/sudoers.d/10-os1-sudo" <<'EOF'
%sudo ALL=(ALL:ALL) ALL
EOF
chmod 0440 "${ROOTFS_DIR}/etc/sudoers.d/10-os1-sudo"

# Desktop Wayland session configuration (Phase 5+)
if [[ "${OS1_PROFILE}" == "desktop" ]]; then
    echo "[os1-rootfs] Configuring KDE Plasma / KWin Wayland session and SDDM..."
    mkdir -p "${ROOTFS_DIR}/etc/sddm.conf.d" "${ROOTFS_DIR}/etc/profile.d"

    WAYLAND_SESSION="plasmawayland.desktop"
    if [[ -f "${ROOTFS_DIR}/usr/share/wayland-sessions/plasmawayland.desktop" ]]; then
        WAYLAND_SESSION="plasmawayland.desktop"
    elif [[ -f "${ROOTFS_DIR}/usr/share/wayland-sessions/plasma.desktop" ]]; then
        WAYLAND_SESSION="plasma.desktop"
    fi

    cat > "${ROOTFS_DIR}/etc/sddm.conf.d/10-os1-wayland.conf" <<EOF
[General]
InputMethod=
Numlock=none

[Wayland]
SessionDir=/usr/share/wayland-sessions
EnableHiDPI=true

[X11]
EnableHiDPI=true
EOF

    if [[ "${DESKTOP_AUTOLOGIN}" == "1" ]]; then
        cat >> "${ROOTFS_DIR}/etc/sddm.conf.d/10-os1-wayland.conf" <<EOF

[Autologin]
User=${DEV_USER}
Session=${WAYLAND_SESSION}
Relogin=false
EOF
    fi

    cat > "${ROOTFS_DIR}/etc/profile.d/10-os1-graphics.sh" <<'EOF'
# OS-1 Wayland desktop session defaults
export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-wayland}"
export MOZ_ENABLE_WAYLAND=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1
if ! ls /dev/dri/renderD* >/dev/null 2>&1; then
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
fi
EOF
    chmod 0644 "${ROOTFS_DIR}/etc/profile.d/10-os1-graphics.sh"

    mkdir -p "${ROOTFS_DIR}/usr/lib/systemd/user-environment-generators"
    cat > "${ROOTFS_DIR}/usr/lib/systemd/user-environment-generators/10-os1-gpu-env" <<'EOF'
#!/bin/sh
# OS-1 GPU environment generator: enable Mesa llvmpipe fallback only when no 3D render node exists.
echo "XDG_SESSION_TYPE=wayland"
echo "MOZ_ENABLE_WAYLAND=1"
echo "QT_AUTO_SCREEN_SCALE_FACTOR=1"
if ! ls /dev/dri/renderD* >/dev/null 2>&1; then
    echo "LIBGL_ALWAYS_SOFTWARE=1"
    echo "GALLIUM_DRIVER=llvmpipe"
fi
EOF
    chmod 0755 "${ROOTFS_DIR}/usr/lib/systemd/user-environment-generators/10-os1-gpu-env"

    chroot "${ROOTFS_DIR}" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin bash -euo pipefail -c "
systemctl enable sddm.service
systemctl set-default graphical.target
fc-cache -f || true
"

    # Phase 6 & 7: Install original OS-1 visual identity, wallpapers, Aurorae theme, Look-and-Feel, and Top Bar + Dock shell layout
    echo "[os1-rootfs] Installing OS-1 branding (Phase 6) and Top Menu Bar + Dock shell layout (Phase 7)..."
    python3 "${REPO_ROOT}/distro/branding/generate-assets.py" "${ROOTFS_DIR}/usr/share"

    mkdir -p "${ROOTFS_DIR}/usr/share/color-schemes"
    install -m 0644 "${REPO_ROOT}/distro/branding/color-schemes/OS1Light.colors" "${ROOTFS_DIR}/usr/share/color-schemes/OS1Light.colors"
    install -m 0644 "${REPO_ROOT}/distro/branding/color-schemes/OS1Dark.colors" "${ROOTFS_DIR}/usr/share/color-schemes/OS1Dark.colors"

    mkdir -p "${ROOTFS_DIR}/usr/share/plasma/look-and-feel/org.os1.desktop/contents/layouts"
    install -m 0644 "${REPO_ROOT}/distro/branding/look-and-feel/org.os1.desktop/metadata.json" \
        "${ROOTFS_DIR}/usr/share/plasma/look-and-feel/org.os1.desktop/metadata.json"
    install -m 0644 "${REPO_ROOT}/distro/branding/look-and-feel/org.os1.desktop/contents/defaults" \
        "${ROOTFS_DIR}/usr/share/plasma/look-and-feel/org.os1.desktop/contents/defaults"
    install -m 0644 "${REPO_ROOT}/distro/shell/layout/org.kde.plasma.desktop-layout.js" \
        "${ROOTFS_DIR}/usr/share/plasma/look-and-feel/org.os1.desktop/contents/layouts/org.kde.plasma.desktop-layout.js"

    mkdir -p "${ROOTFS_DIR}/etc/xdg/autostart" "${ROOTFS_DIR}/usr/share/os1" "${ROOTFS_DIR}/usr/local/bin"
    install -m 0644 "${REPO_ROOT}/distro/shell/xdg/kdeglobals" "${ROOTFS_DIR}/etc/xdg/kdeglobals"
    install -m 0644 "${REPO_ROOT}/distro/shell/xdg/kwinrc" "${ROOTFS_DIR}/etc/xdg/kwinrc"
    install -m 0644 "${REPO_ROOT}/distro/shell/xdg/kglobalshortcutsrc" "${ROOTFS_DIR}/etc/xdg/kglobalshortcutsrc"
    install -m 0644 "${REPO_ROOT}/distro/shell/xdg/krunnerrc" "${ROOTFS_DIR}/etc/xdg/krunnerrc"
    install -m 0644 "${REPO_ROOT}/distro/apps/dolphinrc" "${ROOTFS_DIR}/etc/xdg/dolphinrc"
    install -m 0644 "${REPO_ROOT}/distro/shell/xdg/autostart/os1-shell-firstboot.desktop" \
        "${ROOTFS_DIR}/etc/xdg/autostart/os1-shell-firstboot.desktop"
    install -m 0644 "${REPO_ROOT}/distro/branding/tokens.json" "${ROOTFS_DIR}/usr/share/os1/tokens.json"
    install -m 0644 "${REPO_ROOT}/distro/apps/manifest.json" "${ROOTFS_DIR}/usr/share/os1/apps-manifest.json"
    install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-appearance" "${ROOTFS_DIR}/usr/local/bin/os1-appearance"
    install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-shell-init" "${ROOTFS_DIR}/usr/local/bin/os1-shell-init"
    install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-accessibility" "${ROOTFS_DIR}/usr/local/bin/os1-accessibility"
    install -m 0755 "${REPO_ROOT}/distro/installer/os1-firstboot" "${ROOTFS_DIR}/usr/local/bin/os1-firstboot"
    install -m 0755 "${REPO_ROOT}/distro/tests/fs-operations-test.py" "${ROOTFS_DIR}/usr/local/bin/os1-fs-test"
fi

# Install OS-1 UEFI system installer into rootfs
if [[ -f "${REPO_ROOT}/distro/installer/os1-install" ]]; then
    mkdir -p "${ROOTFS_DIR}/usr/local/sbin"
    install -m 0755 "${REPO_ROOT}/distro/installer/os1-install" "${ROOTFS_DIR}/usr/local/sbin/os1-install"
fi

# Clean apt caches to keep disk image compact
rm -rf "${ROOTFS_DIR}/var/lib/apt/lists/"* "${ROOTFS_DIR}/var/cache/apt/archives/"*.deb

# Record installed package manifest
chroot "${ROOTFS_DIR}" dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > "${IMAGE_DIR}/rootfs-packages.tsv"

echo "[os1-rootfs] Building persistent ext4 disk image (${IMAGE_SIZE_MB} MiB)..."
rm -f "${DISK_IMG}"
truncate -s "${IMAGE_SIZE_MB}M" "${DISK_IMG}"
mkfs.ext4 -F -L OS1_ROOT -d "${ROOTFS_DIR}" "${DISK_IMG}"

IMG_SHA256="$(sha256sum "${DISK_IMG}" | awk '{print $1}')"
PKG_COUNT="$(wc -l < "${IMAGE_DIR}/rootfs-packages.tsv" | tr -d ' ')"
GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
BUILD_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 - "${IMAGE_DIR}/rootfs-provenance.json" <<PYEOF
import json, sys
data = {
    "project": "OS-1",
    "phase": 5 if "${OS1_PROFILE}" == "desktop" else 2,
    "profile": "${OS1_PROFILE}",
    "debian_suite": "${DEBIAN_SUITE}",
    "debian_mirror": "${DEBIAN_MIRROR}",
    "arch": "amd64",
    "git_sha": "${GIT_SHA}",
    "build_timestamp_utc": "${BUILD_UTC}",
    "package_count": int("${PKG_COUNT}"),
    "disk_image": {
        "path": "distro/out/images/os1-rootfs.ext4.img",
        "size_mb": int("${IMAGE_SIZE_MB}"),
        "filesystem": "ext4",
        "label": "OS1_ROOT",
        "sha256": "${IMG_SHA256}",
    },
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

if [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
    chown -R "${SUDO_UID}:${SUDO_GID}" "${IMAGE_DIR}"
fi

echo "[os1-rootfs] SUCCESS"
echo "[os1-rootfs]   Image:    ${DISK_IMG} (${IMAGE_SIZE_MB} MiB, ${PKG_COUNT} packages)"
echo "[os1-rootfs]   SHA-256:  ${IMG_SHA256}"
echo "[os1-rootfs]   Manifest: ${IMAGE_DIR}/rootfs-provenance.json"
