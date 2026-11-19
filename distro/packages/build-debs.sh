#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Phase 14 / 19: Build native OS-1 .deb packages and a local APT repository with SHA-256 checksums.
set -euo pipefail
umask 022

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
PKG_WORK="${OUT_ROOT}/deb-build"
REPO_DIR="${OS1_APT_REPO_DIR:-${OUT_ROOT}/apt-repo}"

# shellcheck source=../VERSION
source "${REPO_ROOT}/distro/VERSION"
VERSION="${OS1_PKG_VERSION:-${OS1_DEB_VERSION}}"
MAINTAINER="OS-1 Project <os1-maintainers@users.noreply.github.com>"

for tool in dpkg-deb python3 gzip sha256sum md5sum; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        echo "ERROR: Required packaging tool not found: ${tool}" >&2
        exit 1
    fi
done

rm -rf "${PKG_WORK}" "${REPO_DIR}"
mkdir -p "${PKG_WORK}" "${REPO_DIR}"

write_copyright() {
    local pkg_root="$1"
    local pkg_name="$2"
    mkdir -p "${pkg_root}/usr/share/doc/${pkg_name}"
    cat > "${pkg_root}/usr/share/doc/${pkg_name}/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: ${pkg_name}
Source: ${OS1_HOME_URL}

Files: *
Copyright: 2025-2026 OS-1 Project Contributors
License: GPL-2.0-only
 On Debian systems, the complete text of the GNU General Public License
 version 2 can be found in "/usr/share/common-licenses/GPL-2".
EOF
    chmod 0644 "${pkg_root}/usr/share/doc/${pkg_name}/copyright"
}

finalize_deb() {
    local pkg_root="$1"
    local deb_out="$2"

    # Compute Installed-Size (KiB) and append to control if not already present
    local size_kb
    size_kb="$(du -sk --exclude=DEBIAN "${pkg_root}" | awk '{print $1}')"
    if ! grep -q '^Installed-Size:' "${pkg_root}/DEBIAN/control"; then
        sed -i "/^Maintainer:/i Installed-Size: ${size_kb}" "${pkg_root}/DEBIAN/control"
    fi

    # Record all /etc files in DEBIAN/conffiles automatically
    if [[ -d "${pkg_root}/etc" ]]; then
        (cd "${pkg_root}" && find etc -type f | sort | sed 's|^|/|') > "${pkg_root}/DEBIAN/conffiles"
        if [[ ! -s "${pkg_root}/DEBIAN/conffiles" ]]; then
            rm -f "${pkg_root}/DEBIAN/conffiles"
        else
            chmod 0644 "${pkg_root}/DEBIAN/conffiles"
        fi
    fi

    # Generate DEBIAN/md5sums so `dpkg -V` verifies file integrity
    (
        cd "${pkg_root}"
        find . -path ./DEBIAN -prune -o -type f -print | sed 's|^\./||' | sort | while IFS= read -r rel; do
            md5sum "${rel}"
        done
    ) > "${pkg_root}/DEBIAN/md5sums"
    chmod 0644 "${pkg_root}/DEBIAN/md5sums"

    # Ensure strict permissions on maintainer scripts if present
    for script in preinst postinst prerm postrm; do
        if [[ -f "${pkg_root}/DEBIAN/${script}" ]]; then
            chmod 0755 "${pkg_root}/DEBIAN/${script}"
        fi
    done

    dpkg-deb --build --root-owner-group "${pkg_root}" "${deb_out}"
}

# ---------------------------------------------------------------------------
# 1. os1-release
# ---------------------------------------------------------------------------
echo "[os1-debs] Building os1-release_${VERSION}_all.deb..."
REL_ROOT="${PKG_WORK}/os1-release"
mkdir -p "${REL_ROOT}/DEBIAN" "${REL_ROOT}/etc" "${REL_ROOT}/usr/share/os1"

install -m 0644 "${REPO_ROOT}/distro/VERSION" "${REL_ROOT}/usr/share/os1/VERSION"
cat > "${REL_ROOT}/etc/os-release" <<EOF
PRETTY_NAME="${OS1_NAME} ${OS1_VERSION} (Debian ${OS1_DEBIAN_SUITE} base)"
NAME="${OS1_NAME}"
VERSION_ID="${OS1_VERSION_ID}"
VERSION="${OS1_VERSION} (Debian ${OS1_DEBIAN_SUITE} base)"
ID=${OS1_ID}
ID_LIKE=debian
HOME_URL="${OS1_HOME_URL}"
SUPPORT_URL="${OS1_SUPPORT_URL}"
BUG_REPORT_URL="${OS1_BUG_REPORT_URL}"
EOF
chmod 0644 "${REL_ROOT}/etc/os-release"

cat > "${REL_ROOT}/DEBIAN/preinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "install" ]; then
    dpkg-divert --package os1-release --add --rename \
        --divert /etc/os-release.debian /etc/os-release
fi
EOF

cat > "${REL_ROOT}/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "abort-install" ] || [ "$1" = "disappear" ]; then
    dpkg-divert --package os1-release --remove --rename \
        --divert /etc/os-release.debian /etc/os-release
fi
EOF

cat > "${REL_ROOT}/DEBIAN/control" <<EOF
Package: os1-release
Version: ${VERSION}
Section: misc
Priority: optional
Architecture: all
Maintainer: ${MAINTAINER}
Description: OS-1 distribution release identity and version metadata
 Provides canonical OS-1 release identification (/etc/os-release via
 dpkg-divert) and /usr/share/os1/VERSION metadata.
EOF
write_copyright "${REL_ROOT}" "os1-release"
finalize_deb "${REL_ROOT}" "${REPO_DIR}/os1-release_${VERSION}_all.deb"

# ---------------------------------------------------------------------------
# 2. os1-keyring
# ---------------------------------------------------------------------------
echo "[os1-debs] Building os1-keyring_${VERSION}_all.deb..."
KEY_ROOT="${PKG_WORK}/os1-keyring"
mkdir -p "${KEY_ROOT}/DEBIAN" \
    "${KEY_ROOT}/usr/share/keyrings" \
    "${KEY_ROOT}/etc/apt/sources.list.d"

if [[ -n "${OS1_GPG_PUBKEY:-}" && -f "${OS1_GPG_PUBKEY}" ]]; then
    install -m 0644 "${OS1_GPG_PUBKEY}" "${KEY_ROOT}/usr/share/keyrings/os1-archive-keyring.gpg"
fi

if [[ -n "${OS1_APT_REPO_URL:-}" ]]; then
    cat > "${KEY_ROOT}/etc/apt/sources.list.d/os1.list" <<EOF
# OS-1 signed APT repository (strictly verified via signed-by; never trusted=yes)
deb [signed-by=/usr/share/keyrings/os1-archive-keyring.gpg] ${OS1_APT_REPO_URL} ./
EOF
else
    cat > "${KEY_ROOT}/etc/apt/sources.list.d/os1.list" <<EOF
# OS-1 APT repository configuration
# Configure a signed OS-1 archive URL with signed-by=/usr/share/keyrings/os1-archive-keyring.gpg
# Example:
# deb [signed-by=/usr/share/keyrings/os1-archive-keyring.gpg] https://packages.os1.example/apt ./
EOF
fi
chmod 0644 "${KEY_ROOT}/etc/apt/sources.list.d/os1.list"

cat > "${KEY_ROOT}/DEBIAN/control" <<EOF
Package: os1-keyring
Version: ${VERSION}
Section: misc
Priority: optional
Architecture: all
Maintainer: ${MAINTAINER}
Description: OS-1 APT archive signing keyring and repository configuration
 Installs the OS-1 archive public keyring and signed-by APT source entry.
 Never enables unsigned or trusted=yes repositories.
EOF
write_copyright "${KEY_ROOT}" "os1-keyring"
finalize_deb "${KEY_ROOT}" "${REPO_DIR}/os1-keyring_${VERSION}_all.deb"

# ---------------------------------------------------------------------------
# 3. os1-branding
# ---------------------------------------------------------------------------
echo "[os1-debs] Building os1-branding_${VERSION}_all.deb..."
BRAND_ROOT="${PKG_WORK}/os1-branding"
mkdir -p "${BRAND_ROOT}/DEBIAN" \
    "${BRAND_ROOT}/usr/share/os1" \
    "${BRAND_ROOT}/usr/share/color-schemes" \
    "${BRAND_ROOT}/usr/share/plasma/look-and-feel/org.os1.desktop"

python3 "${REPO_ROOT}/distro/branding/generate-assets.py" "${BRAND_ROOT}/usr/share"
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
Maintainer: ${MAINTAINER}
Description: Original OS-1 visual identity, wallpapers, color schemes, and window theme
 Independently created OS-1 wallpapers (OS1Horizon Light/Dark), emblem SVG,
 OS1Sequoia Aurorae window theme, Light/Dark Plasma color schemes, and design
 tokens under /usr/share. Contains zero proprietary third-party assets.
EOF
write_copyright "${BRAND_ROOT}" "os1-branding"
finalize_deb "${BRAND_ROOT}" "${REPO_DIR}/os1-branding_${VERSION}_all.deb"

# ---------------------------------------------------------------------------
# 4. os1-shell
# ---------------------------------------------------------------------------
echo "[os1-debs] Building os1-shell_${VERSION}_all.deb..."
SHELL_ROOT="${PKG_WORK}/os1-shell"
mkdir -p "${SHELL_ROOT}/DEBIAN" \
    "${SHELL_ROOT}/etc/xdg/autostart" \
    "${SHELL_ROOT}/etc/profile.d" \
    "${SHELL_ROOT}/usr/lib/systemd/user-environment-generators" \
    "${SHELL_ROOT}/usr/share/os1" \
    "${SHELL_ROOT}/usr/bin" \
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
install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-appearance" "${SHELL_ROOT}/usr/bin/os1-appearance"
install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-shell-init" "${SHELL_ROOT}/usr/bin/os1-shell-init"
install -m 0755 "${REPO_ROOT}/distro/shell/bin/os1-accessibility" "${SHELL_ROOT}/usr/bin/os1-accessibility"

cat > "${SHELL_ROOT}/etc/profile.d/10-os1-graphics.sh" <<'EOF'
# OS-1 Wayland desktop session defaults
export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-wayland}"
export MOZ_ENABLE_WAYLAND=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1
if ! ls /dev/dri/renderD* >/dev/null 2>&1; then
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
fi
EOF
chmod 0644 "${SHELL_ROOT}/etc/profile.d/10-os1-graphics.sh"

cat > "${SHELL_ROOT}/usr/lib/systemd/user-environment-generators/10-os1-gpu-env" <<'EOF'
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
chmod 0755 "${SHELL_ROOT}/usr/lib/systemd/user-environment-generators/10-os1-gpu-env"

cat > "${SHELL_ROOT}/DEBIAN/control" <<EOF
Package: os1-shell
Version: ${VERSION}
Section: kde
Priority: optional
Architecture: all
Depends: os1-branding (>= ${VERSION}), plasma-desktop, kwin-wayland, libnotify-bin, python3
Maintainer: ${MAINTAINER}
Description: OS-1 Top Menu Bar, Floating Dock, shortcuts, and accessibility shell
 Provides the OS-1 Plasma Wayland layout, Spotlight/Overview/Spaces shortcut
 defaults, Dolphin defaults, Wayland GPU environment defaults, os1-appearance,
 os1-shell-init, and os1-accessibility.
EOF
write_copyright "${SHELL_ROOT}" "os1-shell"
finalize_deb "${SHELL_ROOT}" "${REPO_DIR}/os1-shell_${VERSION}_all.deb"

# ---------------------------------------------------------------------------
# 5. os1-firstboot
# ---------------------------------------------------------------------------
echo "[os1-debs] Building os1-firstboot_${VERSION}_all.deb..."
FB_ROOT="${PKG_WORK}/os1-firstboot"
mkdir -p "${FB_ROOT}/DEBIAN" "${FB_ROOT}/usr/bin"
install -m 0755 "${REPO_ROOT}/distro/installer/os1-firstboot" "${FB_ROOT}/usr/bin/os1-firstboot"

cat > "${FB_ROOT}/DEBIAN/control" <<EOF
Package: os1-firstboot
Version: ${VERSION}
Section: misc
Priority: optional
Architecture: all
Depends: os1-shell (>= ${VERSION}), bash
Maintainer: ${MAINTAINER}
Description: OS-1 first-run onboarding and user preference helper
 Manages idempotent first-run user appearance and accessibility preferences
 for newly created OS-1 desktop accounts.
EOF
write_copyright "${FB_ROOT}" "os1-firstboot"
finalize_deb "${FB_ROOT}" "${REPO_DIR}/os1-firstboot_${VERSION}_all.deb"

# ---------------------------------------------------------------------------
# 6. os1-installer
# ---------------------------------------------------------------------------
echo "[os1-debs] Building os1-installer_${VERSION}_all.deb..."
INST_ROOT="${PKG_WORK}/os1-installer"
mkdir -p "${INST_ROOT}/DEBIAN" "${INST_ROOT}/usr/sbin" "${INST_ROOT}/usr/share/os1/calamares"
install -m 0755 "${REPO_ROOT}/distro/installer/os1-install" "${INST_ROOT}/usr/sbin/os1-install"
install -m 0644 "${REPO_ROOT}/distro/installer/calamares/settings.conf" \
    "${INST_ROOT}/usr/share/os1/calamares/settings.conf"

cat > "${INST_ROOT}/DEBIAN/control" <<EOF
Package: os1-installer
Version: ${VERSION}
Section: admin
Priority: optional
Architecture: all
Depends: python3, parted, e2fsprogs, dosfstools, grub-efi-amd64-bin, grub-common, util-linux
Maintainer: ${MAINTAINER}
Description: OS-1 preflight-complete, credential-safe UEFI GPT installer
 Installs OS-1 from the UEFI live environment onto a target GPT disk with
 full preflight validation, stdin/fd credential handling, and clean installed
 system identity.
EOF
write_copyright "${INST_ROOT}" "os1-installer"
finalize_deb "${INST_ROOT}" "${REPO_DIR}/os1-installer_${VERSION}_all.deb"

# ---------------------------------------------------------------------------
# 7. os1-tools
# ---------------------------------------------------------------------------
echo "[os1-debs] Building os1-tools_${VERSION}_all.deb..."
TOOLS_ROOT="${PKG_WORK}/os1-tools"
mkdir -p "${TOOLS_ROOT}/DEBIAN" "${TOOLS_ROOT}/usr/bin"
install -m 0755 "${REPO_ROOT}/distro/tests/fs-operations-test.py" "${TOOLS_ROOT}/usr/bin/os1-fs-test"

cat > "${TOOLS_ROOT}/DEBIAN/control" <<EOF
Package: os1-tools
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3
Maintainer: ${MAINTAINER}
Description: OS-1 system verification and diagnostic utilities
 Provides native OS-1 diagnostic and verification utilities including
 os1-fs-test.
EOF
write_copyright "${TOOLS_ROOT}" "os1-tools"
finalize_deb "${TOOLS_ROOT}" "${REPO_DIR}/os1-tools_${VERSION}_all.deb"

# ---------------------------------------------------------------------------
# 8. os1-desktop-meta
# ---------------------------------------------------------------------------
echo "[os1-debs] Building os1-desktop-meta_${VERSION}_amd64.deb..."
META_ROOT="${PKG_WORK}/os1-desktop-meta"
mkdir -p "${META_ROOT}/DEBIAN"

cat > "${META_ROOT}/DEBIAN/control" <<EOF
Package: os1-desktop-meta
Version: ${VERSION}
Section: metapackages
Priority: optional
Architecture: amd64
Depends: os1-release (>= ${VERSION}), os1-keyring (>= ${VERSION}), os1-branding (>= ${VERSION}), os1-shell (>= ${VERSION}), os1-firstboot (>= ${VERSION}), os1-installer (>= ${VERSION}), os1-tools (>= ${VERSION}), plasma-workspace-wayland, kwin-wayland, sddm, dolphin, konsole, firefox-esr, kate, gwenview, okular, kcalc, ark, kde-spectacle, plasma-systemmonitor, systemsettings, pipewire, network-manager, ufw, nftables, orca, upower
Maintainer: ${MAINTAINER}
Description: OS-1 complete Wayland desktop environment metapackage
 Installs the complete OS-1 graphical desktop experience, native OS-1
 packages, essential applications, PipeWire audio, NetworkManager, UFW/nftables
 firewall, and Orca screen reader baseline.
EOF
write_copyright "${META_ROOT}" "os1-desktop-meta"
finalize_deb "${META_ROOT}" "${REPO_DIR}/os1-desktop-meta_${VERSION}_amd64.deb"

echo "[os1-debs] Validating generated .deb packages..."
for deb in "${REPO_DIR}"/*.deb; do
    dpkg-deb --info "${deb}" >/dev/null
    dpkg-deb --contents "${deb}" >/dev/null
    echo "  [OK] $(basename "${deb}") ($(stat -c%s "${deb}") bytes)"
done

echo "[os1-debs] Generating APT Packages index, Release metadata, and SHA256SUMS..."
python3 - "${REPO_DIR}" "${OS1_DEBIAN_SUITE}" "${OS1_CODENAME}" <<'PYEOF'
import gzip
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone

repo_dir, suite, codename = sys.argv[1], sys.argv[2], sys.argv[3]
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
    "Label: OS-1 APT Repository",
    f"Suite: {suite}",
    f"Codename: {codename}",
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
