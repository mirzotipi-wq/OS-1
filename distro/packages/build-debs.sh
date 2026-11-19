#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Phase 14: Build native OS-1 .deb packages and a local APT repository with SHA-256 checksums.
set -euo pipefail
umask 022

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
PKG_WORK="${OUT_ROOT}/deb-build"
REPO_DIR="${OUT_ROOT}/apt-repo"
VERSION="${OS1_PKG_VERSION:-1.0.0}"

for tool in dpkg-deb python3 gzip sha256sum; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        echo "ERROR: Required packaging tool not found: ${tool}" >&2
        exit 1
    fi
done

rm -rf "${PKG_WORK}" "${REPO_DIR}"
mkdir -p "${PKG_WORK}" "${REPO_DIR}"

echo "[os1-debs] Building os1-branding_${VERSION}_all.deb..."
BRAND_ROOT="${PKG_WORK}/os1-branding"
mkdir -p "${BRAND_ROOT}/DEBIAN" \
    "${BRAND_ROOT}/usr/share/os1" \
    "${BRAND_ROOT}/usr/share/color-schemes" \
    "${BRAND_ROOT}/usr/share/plasma/look-and-feel/org.os1.desktop"

python3 "${REPO_ROOT}/distro/branding/generate-assets.py" "${BRAND_ROOT}"
install -m 0644 "${REPO_ROOT}/distro/branding/tokens.json" "${BRAND_ROOT}/usr/share/os1/tokens.json"
install -m 0644 "${REPO_ROOT}/distro/branding/color-schemes/OS1Light.colors" \
    "${BRAND_ROOT}/usr/share/color-schemes/OS1Light.colors"
install -m 0644 "${REPO_ROOT}/distro/branding/color-schemes/OS1Dark.colors" \
    "${BRAND_ROOT}/usr/share/color-schemes/OS1Dark.colors"
cp -a "${REPO_ROOT}/distro/branding/look-and-feel/org.os1.desktop/." \
    "${BRAND_ROOT}/usr/share/plasma/look-and-feel/org.os1.desktop/"

cat > "${BRAND_ROOT}/DEBIAN/control" <<EOF
Package: os1-branding
Version: ${VERSION}
Section: misc
Priority: optional
Architecture: all
Maintainer: OS-1 Project <https://github.com/mirzotipi-wq/OS-1>
Description: Original OS-1 visual identity, wallpapers, color schemes, and window theme
 Independently created OS-1 wallpapers (OS1Horizon Light/Dark), emblem SVG,
 OS1Sequoia Aurorae window theme, Light/Dark Plasma color schemes, and design
 tokens. Contains zero proprietary third-party assets.
EOF

dpkg-deb --build --root-owner-group "${BRAND_ROOT}" "${REPO_DIR}/os1-branding_${VERSION}_all.deb"

echo "[os1-debs] Building os1-shell_${VERSION}_all.deb..."
SHELL_ROOT="${PKG_WORK}/os1-shell"
mkdir -p "${SHELL_ROOT}/DEBIAN" \
    "${SHELL_ROOT}/etc/xdg/autostart" \
    "${SHELL_ROOT}/usr/share/os1" \
    "${SHELL_ROOT}/usr/local/bin" \
    "${SHELL_ROOT}/usr/local/sbin" \
    "${SHELL_ROOT}/usr/share/plasma/look-and-feel/org.os1.desktop/contents/layouts"

install -m 0644 "${REPO_ROOT}/distro/shell/layout/org.kde.plasma.desktop-layout.js" \
    "${SHELL_ROOT}/usr/share/plasma/look-and-feel/org.os1.desktop/contents/layouts/org.kde.plasma.desktop-layout.js"
install -m 0644 "${REPO_ROOT}/distro/shell/xdg/kdeglobals" "${SHELL_ROOT}/etc/xdg/kdeglobals"
install -m 0644 "${REPO_ROOT}/distro/shell/xdg/kwinrc" "${SHELL_ROOT}/etc/xdg/kwinrc"
install -m 0644 "${REPO_ROOT}/distro/shell/xdg/kglobalshortcutsrc" "${SHELL_ROOT}/etc/xdg/kglobalshortcutsrc"
install -m 0644 "${REPO_ROOT}/distro/shell/xdg/krunnerrc" "${SHELL_ROOT}/etc/xdg/krunnerrc"
install -m 0644 "${REPO_ROOT}/distro/apps/dolphinrc" "${SHELL_ROOT}/etc/xdg/dolphinrc"
install -m 0644 "${REPO_ROOT}/distro/shell/xdg/autostart/os1-shell-firstboot.desktop" \
    "${SHELL_ROOT}/etc/xdg/autostart/os1-shell-firstboot.desktop"
install -m 0644 "${REPO_ROOT}/distro/apps/manifest.json" "${SHELL_ROOT}/usr/share/os1/apps-manifest.json"
install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-appearance" "${SHELL_ROOT}/usr/local/bin/os1-appearance"
install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-shell-init" "${SHELL_ROOT}/usr/local/bin/os1-shell-init"
install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-accessibility" "${SHELL_ROOT}/usr/local/bin/os1-accessibility"
install -m 0755 "${REPO_ROOT}/distro/installer/os1-firstboot" "${SHELL_ROOT}/usr/local/bin/os1-firstboot"
install -m 0755 "${REPO_ROOT}/distro/tests/fs-operations-test.py" "${SHELL_ROOT}/usr/local/bin/os1-fs-test"
install -m 0755 "${REPO_ROOT}/distro/installer/os1-install" "${SHELL_ROOT}/usr/local/sbin/os1-install"

cat > "${SHELL_ROOT}/DEBIAN/control" <<EOF
Package: os1-shell
Version: ${VERSION}
Section: kde
Priority: optional
Architecture: all
Depends: os1-branding (>= ${VERSION}), plasma-desktop, kwin-wayland, libnotify-bin, python3
Maintainer: OS-1 Project <https://github.com/mirzotipi-wq/OS-1>
Description: OS-1 Top Menu Bar, Floating Dock, shortcuts, onboarding, and accessibility tools
 Provides the OS-1 Plasma Wayland layout, Spotlight/Overview/Spaces shortcut
 defaults, Finder-class Dolphin defaults, os1-appearance, os1-accessibility,
 os1-firstboot, os1-fs-test, and os1-install.
EOF

dpkg-deb --build --root-owner-group "${SHELL_ROOT}" "${REPO_DIR}/os1-shell_${VERSION}_all.deb"

echo "[os1-debs] Building os1-desktop-meta_${VERSION}_amd64.deb..."
META_ROOT="${PKG_WORK}/os1-desktop-meta"
mkdir -p "${META_ROOT}/DEBIAN"

cat > "${META_ROOT}/DEBIAN/control" <<EOF
Package: os1-desktop-meta
Version: ${VERSION}
Section: metapackages
Priority: optional
Architecture: amd64
Depends: os1-branding (>= ${VERSION}), os1-shell (>= ${VERSION}), plasma-workspace-wayland, kwin-wayland, sddm, dolphin, konsole, firefox-esr, kate, gwenview, okular, kcalc, ark, kde-spectacle, plasma-systemmonitor, systemsettings, pipewire, network-manager, ufw, orca, upower
Maintainer: OS-1 Project <https://github.com/mirzotipi-wq/OS-1>
Description: OS-1 complete Wayland desktop environment metapackage
 Installs the complete OS-1 graphical desktop experience, essential native
 applications, PipeWire audio, NetworkManager, UFW firewall, and Orca screen
 reader baseline.
EOF

dpkg-deb --build --root-owner-group "${META_ROOT}" "${REPO_DIR}/os1-desktop-meta_${VERSION}_amd64.deb"

echo "[os1-debs] Validating generated .deb packages..."
for deb in "${REPO_DIR}"/*.deb; do
    dpkg-deb --info "${deb}" >/dev/null
    dpkg-deb --contents "${deb}" >/dev/null
    echo "  [OK] $(basename "${deb}") ($(stat -c%s "${deb}") bytes)"
done

echo "[os1-debs] Generating APT Packages index, Release metadata, and SHA256SUMS..."
python3 - "${REPO_DIR}" <<'PYEOF'
import gzip
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone

repo_dir = sys.argv[1]
debs = sorted(f for f in os.listdir(repo_dir) if f.endswith(".deb"))
stanzas = []
for deb in debs:
    path = os.path.join(repo_dir, deb)
    data = open(path, "rb").read()
    ctrl = subprocess.check_output(["dpkg-deb", "--field", path], text=True).strip()
    stanza = "\n".join([
        ctrl,
        f"Filename: {deb}",
        f"Size: {len(data)}",
        f"MD5sum: {hashlib.md5(data).hexdigest()}",
        f"SHA1: {hashlib.sha1(data).hexdigest()}",
        f"SHA256: {hashlib.sha256(data).hexdigest()}",
    ])
    stanzas.append(stanza)

packages_txt = ("\n\n".join(stanzas) + "\n").encode("utf-8")
packages_path = os.path.join(repo_dir, "Packages")
packages_gz_path = os.path.join(repo_dir, "Packages.gz")
with open(packages_path, "wb") as f:
    f.write(packages_txt)
with gzip.open(packages_gz_path, "wb") as f:
    f.write(packages_txt)

now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S UTC")
release_lines = [
    "Origin: OS-1",
    "Label: OS-1 Local APT Repository",
    "Suite: bookworm",
    "Codename: os1",
    f"Date: {now}",
    "Architectures: amd64 all",
    "Components: main",
    "Description: Native OS-1 distribution packages",
    "SHA256:",
]
for fname in ("Packages", "Packages.gz"):
    fpath = os.path.join(repo_dir, fname)
    raw = open(fpath, "rb").read()
    release_lines.append(f" {hashlib.sha256(raw).hexdigest()} {len(raw):16d} {fname}")

with open(os.path.join(repo_dir, "Release"), "w", encoding="utf-8") as f:
    f.write("\n".join(release_lines) + "\n")
PYEOF

(cd "${REPO_DIR}" && sha256sum *.deb Packages Packages.gz Release > SHA256SUMS)
rm -rf "${PKG_WORK}"

echo "[os1-debs] SUCCESS: APT repository ready at ${REPO_DIR}"
