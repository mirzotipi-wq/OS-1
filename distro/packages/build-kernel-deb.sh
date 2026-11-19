#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Phase 20: Package a built OS-1 x86_64 kernel + modules into a versioned Debian package.
set -euo pipefail
umask 022

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
KERNEL_DIR="${OS1_KERNEL_DIR:-${OUT_ROOT}/kernel}"
REPO_DIR="${OS1_APT_REPO_DIR:-${OUT_ROOT}/apt-repo}"

# shellcheck source=../VERSION
source "${REPO_ROOT}/distro/VERSION"
DEB_VERSION="${OS1_PKG_VERSION:-${OS1_DEB_VERSION}}"
KREL_OVERRIDE=""
CORRUPT_VMLINUZ=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --krel-override) KREL_OVERRIDE="$2"; shift 2 ;;
        --deb-version) DEB_VERSION="$2"; shift 2 ;;
        --out-dir) REPO_DIR="$2"; shift 2 ;;
        --corrupt-vmlinuz) CORRUPT_VMLINUZ=1; shift ;;
        -h|--help)
            echo "Usage: $(basename "$0") [--krel-override REL] [--deb-version VER] [--out-dir DIR] [--corrupt-vmlinuz]"
            exit 0
            ;;
        *) echo "ERROR: Unknown argument: $1" >&2; exit 2 ;;
    esac
done

BZIMAGE="${KERNEL_DIR}/bzImage"
PROV="${KERNEL_DIR}/provenance.json"
if [[ "${CORRUPT_VMLINUZ}" -eq 0 && ! -f "${BZIMAGE}" ]]; then
    echo "ERROR: Kernel bzImage not found at ${BZIMAGE}. Build kernel first." >&2
    exit 1
fi

if [[ -n "${KREL_OVERRIDE}" ]]; then
    KREL="${KREL_OVERRIDE}"
elif [[ -f "${PROV}" ]]; then
    KREL="$(python3 -c "import json; print(json.load(open('${PROV}'))['kernel_release'])")"
else
    echo "ERROR: Cannot determine kernel_release (missing ${PROV} and --krel-override)" >&2
    exit 1
fi

# Sanitize kernel release for Debian package name (lowercase, [a-z0-9+.-])
PKG_SUFFIX="$(echo "${KREL}" | tr '[:upper:]_' '[:lower:]-' | sed 's/[^a-z0-9+.-]//g')"
PKG_NAME="linux-image-os1-${PKG_SUFFIX}"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/os1-kdeb.XXXXXX")"
trap 'rm -rf "${WORK_DIR}"' EXIT

PKG_ROOT="${WORK_DIR}/${PKG_NAME}"
mkdir -p "${PKG_ROOT}/DEBIAN" "${PKG_ROOT}/boot" "${PKG_ROOT}/usr/share/doc/${PKG_NAME}" "${REPO_DIR}"

if [[ "${CORRUPT_VMLINUZ}" -eq 1 ]]; then
    # Intentionally invalid kernel image for automated QEMU rollback qualification
    printf 'OS1-INTENTIONAL-CORRUPT-KERNEL-FOR-ROLLBACK-TEST\n' > "${PKG_ROOT}/boot/vmlinuz-${KREL}"
    chmod 0644 "${PKG_ROOT}/boot/vmlinuz-${KREL}"
else
    install -m 0644 "${BZIMAGE}" "${PKG_ROOT}/boot/vmlinuz-${KREL}"
    if [[ -f "${KERNEL_DIR}/System.map" ]]; then
        install -m 0644 "${KERNEL_DIR}/System.map" "${PKG_ROOT}/boot/System.map-${KREL}"
    fi
    if [[ -f "${KERNEL_DIR}/os1_x86_64.config" ]]; then
        install -m 0644 "${KERNEL_DIR}/os1_x86_64.config" "${PKG_ROOT}/boot/config-${KREL}"
    fi
    if [[ -d "${KERNEL_DIR}/modules/lib/modules" ]]; then
        mkdir -p "${PKG_ROOT}/usr/lib/modules"
        # Copy modules under KREL (if overriding KREL, copy from first dir found)
        SRC_MOD_DIR="${KERNEL_DIR}/modules/lib/modules/${KREL}"
        if [[ ! -d "${SRC_MOD_DIR}" ]]; then
            SRC_MOD_DIR="$(find "${KERNEL_DIR}/modules/lib/modules" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
        fi
        if [[ -n "${SRC_MOD_DIR}" && -d "${SRC_MOD_DIR}" ]]; then
            cp -a "${SRC_MOD_DIR}" "${PKG_ROOT}/usr/lib/modules/${KREL}"
            rm -f "${PKG_ROOT}/usr/lib/modules/${KREL}/build" "${PKG_ROOT}/usr/lib/modules/${KREL}/source"
        fi
    fi
fi

cat > "${PKG_ROOT}/usr/share/doc/${PKG_NAME}/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Linux kernel (OS-1 build)
Source: ${OS1_HOME_URL}

Files: *
Copyright: Linux Kernel Contributors and OS-1 Project Contributors
License: GPL-2.0-only
 On Debian systems, the complete text of the GNU General Public License
 version 2 can be found in "/usr/share/common-licenses/GPL-2".
EOF

cat > "${PKG_ROOT}/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e
if [ "\$1" = "configure" ]; then
    if [ -d "/lib/modules/${KREL}" ] && command -v depmod >/dev/null 2>&1; then
        depmod -a "${KREL}" || true
    fi
    if [ -x /usr/sbin/os1-update-boot ]; then
        /usr/sbin/os1-update-boot
    fi
fi
EOF
chmod 0755 "${PKG_ROOT}/DEBIAN/postinst"

cat > "${PKG_ROOT}/DEBIAN/prerm" <<EOF
#!/bin/sh
set -e
if [ "\$1" = "remove" ] || [ "\$1" = "purge" ]; then
    RUNNING="\$(uname -r || true)"
    if [ "\${RUNNING}" = "${KREL}" ] && [ "\${OS1_ALLOW_REMOVE_RUNNING_KERNEL:-0}" != "1" ]; then
        echo "ERROR: Refusing to remove currently running OS-1 kernel (${KREL})." >&2
        echo "Boot into another installed kernel first before removing ${PKG_NAME}." >&2
        exit 1
    fi
fi
EOF
chmod 0755 "${PKG_ROOT}/DEBIAN/prerm"

cat > "${PKG_ROOT}/DEBIAN/postrm" <<EOF
#!/bin/sh
set -e
if [ "\$1" = "remove" ] || [ "\$1" = "purge" ]; then
    if [ -x /usr/sbin/os1-update-boot ]; then
        /usr/sbin/os1-update-boot
    fi
fi
EOF
chmod 0755 "${PKG_ROOT}/DEBIAN/postrm"

SIZE_KB="$(du -sk --exclude=DEBIAN "${PKG_ROOT}" | awk '{print $1}')"
cat > "${PKG_ROOT}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${DEB_VERSION}
Section: kernel
Priority: optional
Architecture: amd64
Installed-Size: ${SIZE_KB}
Depends: kmod
Recommends: os1-tools
Provides: linux-image-os1
Maintainer: OS-1 Project <os1-maintainers@users.noreply.github.com>
Description: OS-1 Linux kernel image (${KREL})
 Versioned OS-1 Linux x86-64 kernel image and loadable modules for ${KREL}.
 Automatically updates /boot/grub/grub.cfg via os1-update-boot while retaining
 previously installed kernels for safe rollback.
EOF

(
    cd "${PKG_ROOT}"
    find . -path ./DEBIAN -prune -o -type f -print | sed 's|^\./||' | sort | while IFS= read -r rel; do
        md5sum "${rel}"
    done
) > "${PKG_ROOT}/DEBIAN/md5sums"
chmod 0644 "${PKG_ROOT}/DEBIAN/md5sums"

DEB_OUT="${REPO_DIR}/${PKG_NAME}_${DEB_VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "${PKG_ROOT}" "${DEB_OUT}"
echo "[os1-kdeb] Built ${DEB_OUT} ($(stat -c%s "${DEB_OUT}") bytes)"
