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

# shellcheck source=../VERSION
source "${REPO_ROOT}/distro/VERSION"
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
    python3
    ufw
    nftables
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
    power-profiles-daemon
    ufw
    orca
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

echo "[os1-rootfs] Configuring OS-1 hostname, networking, storage, locales, and user..."

# /etc/os-release is owned and installed by the native os1-release .deb package below.
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

# Phase 17 security baseline: UFW default-deny incoming / allow outgoing (all profiles)
if [[ -f "${ROOTFS_DIR}/etc/ufw/ufw.conf" ]]; then
    sed -i 's/^ENABLED=.*/ENABLED=yes/' "${ROOTFS_DIR}/etc/ufw/ufw.conf"
fi
if [[ -f "${ROOTFS_DIR}/etc/default/ufw" ]]; then
    sed -i 's/^DEFAULT_INPUT_POLICY=.*/DEFAULT_INPUT_POLICY="DROP"/' "${ROOTFS_DIR}/etc/default/ufw"
    sed -i 's/^DEFAULT_OUTPUT_POLICY=.*/DEFAULT_OUTPUT_POLICY="ACCEPT"/' "${ROOTFS_DIR}/etc/default/ufw"
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
systemctl enable ufw.service
if [ -d /lib/modules ]; then
    for kdir in /lib/modules/*; do
        [ -d \"\$kdir\" ] && depmod -a \"\$(basename \"\$kdir\")\"
    done
fi
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

    chroot "${ROOTFS_DIR}" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin bash -euo pipefail -c "
systemctl enable sddm.service
systemctl set-default graphical.target
fc-cache -f || true
"
fi

# Phase 19: Package-owned OS-1 system assembly (install native .debs instead of direct file copies)
APT_REPO_DIR="${OS1_APT_REPO_DIR:-${OUT_ROOT}/apt-repo}"
if [[ ! -f "${APT_REPO_DIR}/os1-release_${OS1_DEB_VERSION}_all.deb" ]]; then
    echo "[os1-rootfs] Building native OS-1 .deb packages (${OS1_DEB_VERSION})..."
    OS1_OUT_DIR="${OUT_ROOT}" "${REPO_ROOT}/distro/packages/build-debs.sh"
fi

echo "[os1-rootfs] Installing native OS-1 Debian packages into rootfs (profile=${OS1_PROFILE})..."
mkdir -p "${ROOTFS_DIR}/tmp/os1-debs"
cp -f "${APT_REPO_DIR}"/*.deb "${ROOTFS_DIR}/tmp/os1-debs/"

if [[ "${OS1_PROFILE}" == "desktop" ]]; then
    OS1_PKGS=(
        os1-release
        os1-keyring
        os1-branding
        os1-shell
        os1-firstboot
        os1-installer
        os1-tools
        os1-desktop-meta
    )
else
    OS1_PKGS=(
        os1-release
        os1-keyring
        os1-installer
        os1-tools
    )
fi

OS1_DEB_ARGS=()
for pkg in "${OS1_PKGS[@]}"; do
    for match in "${ROOTFS_DIR}/tmp/os1-debs/${pkg}_"*.deb; do
        if [[ ! -f "${match}" ]]; then
            echo "ERROR: Expected OS-1 package not found in ${APT_REPO_DIR}: ${pkg}" >&2
            exit 1
        fi
        OS1_DEB_ARGS+=("/tmp/os1-debs/$(basename "${match}")")
    done
done

chroot "${ROOTFS_DIR}" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin DEBIAN_FRONTEND=noninteractive \
    dpkg -i "${OS1_DEB_ARGS[@]}"

echo "[os1-rootfs] Verifying OS-1 package database integrity (dpkg --audit & dpkg -V)..."
AUDIT_OUT="$(chroot "${ROOTFS_DIR}" dpkg --audit)"
if [[ -n "${AUDIT_OUT}" ]]; then
    echo "ERROR: dpkg --audit reported broken packages:" >&2
    echo "${AUDIT_OUT}" >&2
    exit 1
fi
chroot "${ROOTFS_DIR}" dpkg -V "${OS1_PKGS[@]}"
rm -rf "${ROOTFS_DIR}/tmp/os1-debs"

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

python3 - "${IMAGE_DIR}/rootfs-provenance.json" "${OS1_PKGS[@]}" <<PYEOF
import json, sys
data = {
    "project": "OS-1",
    "os1_version": "${OS1_VERSION}",
    "os1_deb_version": "${OS1_DEB_VERSION}",
    "phase": 5 if "${OS1_PROFILE}" == "desktop" else 2,
    "profile": "${OS1_PROFILE}",
    "debian_suite": "${DEBIAN_SUITE}",
    "debian_mirror": "${DEBIAN_MIRROR}",
    "arch": "amd64",
    "git_sha": "${GIT_SHA}",
    "build_timestamp_utc": "${BUILD_UTC}",
    "package_count": int("${PKG_COUNT}"),
    "os1_packages": sys.argv[2:],
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
    if [[ -d "${APT_REPO_DIR}" ]]; then
        chown -R "${SUDO_UID}:${SUDO_GID}" "${APT_REPO_DIR}"
    fi
fi

echo "[os1-rootfs] SUCCESS"
echo "[os1-rootfs]   Image:    ${DISK_IMG} (${IMAGE_SIZE_MB} MiB, ${PKG_COUNT} packages)"
echo "[os1-rootfs]   SHA-256:  ${IMG_SHA256}"
echo "[os1-rootfs]   Manifest: ${IMAGE_DIR}/rootfs-provenance.json"
