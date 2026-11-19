#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Reproducible out-of-tree x86_64 kernel builder for OS-1.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
BUILD_DIR="${OUT_ROOT}/kernel-build"
ARTIFACT_DIR="${OUT_ROOT}/kernel"
FRAGMENT="${SCRIPT_DIR}/os1_x86_64.fragment"

CONFIG_ONLY=0
BUILD_MODULES=0
JOBS="${OS1_JOBS:-$(nproc)}"

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --config-only     Generate and validate merged x86_64 .config without compiling bzImage
  --with-modules    Also compile kernel modules and install them into distro/out/kernel/modules
  -j, --jobs N      Parallel make jobs (default: nproc = ${JOBS})
  -h, --help        Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config-only) CONFIG_ONLY=1; shift ;;
        --with-modules) BUILD_MODULES=1; shift ;;
        -j|--jobs) JOBS="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: Unknown argument: $1" >&2; usage; exit 2 ;;
    esac
done

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
    echo "[os1-kernel] Disk preflight OK: ${avail_mb} MiB available (need >= ${required_mb} MiB)"
}

check_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: Required build tool not found in PATH: $1" >&2
        return 1
    fi
}

echo "[os1-kernel] Repository root: ${REPO_ROOT}"
echo "[os1-kernel] Out-of-tree build dir: ${BUILD_DIR}"
echo "[os1-kernel] Artifact dir: ${ARTIFACT_DIR}"

# Required tools for Kconfig
missing=0
for tool in gcc make flex bison awk sed perl python3; do
    check_cmd "${tool}" || missing=1
done
if (( CONFIG_ONLY == 0 )); then
    for tool in bc objcopy objdump readelf nm strip ar; do
        check_cmd "${tool}" || missing=1
    done
fi
if (( missing != 0 )); then
    echo "ERROR: Missing required kernel build tools. On Debian/Ubuntu install:" >&2
    echo "  build-essential bc bison flex libssl-dev libelf-dev kmod" >&2
    exit 1
fi

if (( CONFIG_ONLY == 1 )); then
    check_disk_space_mb "${OUT_ROOT}" 256
else
    check_disk_space_mb "${OUT_ROOT}" 4096
fi

mkdir -p "${BUILD_DIR}" "${ARTIFACT_DIR}"

echo "[os1-kernel] Generating base x86_64_defconfig..."
make -C "${REPO_ROOT}" O="${BUILD_DIR}" ARCH=x86_64 defconfig

echo "[os1-kernel] Merging OS-1 fragment: ${FRAGMENT}"
"${REPO_ROOT}/scripts/kconfig/merge_config.sh" -m -O "${BUILD_DIR}" "${BUILD_DIR}/.config" "${FRAGMENT}"
make -C "${REPO_ROOT}" O="${BUILD_DIR}" ARCH=x86_64 olddefconfig

cp -f "${BUILD_DIR}/.config" "${ARTIFACT_DIR}/os1_x86_64.config"

# Verify critical OS-1 options survived olddefconfig
for sym in CONFIG_LOCALVERSION=\"-os1\" CONFIG_VIRTIO_BLK=y CONFIG_SERIAL_8250_CONSOLE=y CONFIG_BLK_DEV_INITRD=y CONFIG_EFI_STUB=y; do
    if ! grep -Fq "${sym}" "${ARTIFACT_DIR}/os1_x86_64.config"; then
        echo "ERROR: Expected Kconfig symbol missing after merge: ${sym}" >&2
        exit 1
    fi
done
echo "[os1-kernel] Kconfig validation PASSED -> ${ARTIFACT_DIR}/os1_x86_64.config"

make -C "${REPO_ROOT}" O="${BUILD_DIR}" ARCH=x86_64 include/config/kernel.release
KERNEL_RELEASE="$(cat "${BUILD_DIR}/include/config/kernel.release")"
if [[ "${KERNEL_RELEASE}" != *"-os1"* ]]; then
    echo "ERROR: Expected -os1 in kernelrelease, got: ${KERNEL_RELEASE}" >&2
    exit 1
fi
echo "[os1-kernel] Computed kernelrelease: ${KERNEL_RELEASE}"

if (( CONFIG_ONLY == 1 )); then
    echo "[os1-kernel] --config-only requested; skipping bzImage compilation."
    exit 0
fi

echo "[os1-kernel] Compiling OS-1 x86_64 bzImage with -j${JOBS}..."
make -C "${REPO_ROOT}" O="${BUILD_DIR}" ARCH=x86_64 -j"${JOBS}" bzImage

BZIMAGE_SRC="${BUILD_DIR}/arch/x86/boot/bzImage"
if [[ ! -f "${BZIMAGE_SRC}" ]]; then
    echo "ERROR: Expected bzImage not found at ${BZIMAGE_SRC}" >&2
    exit 1
fi

cp -f "${BZIMAGE_SRC}" "${ARTIFACT_DIR}/bzImage"
cp -f "${BUILD_DIR}/System.map" "${ARTIFACT_DIR}/System.map"

if (( BUILD_MODULES == 1 )); then
    echo "[os1-kernel] Compiling and installing modules..."
    make -C "${REPO_ROOT}" O="${BUILD_DIR}" ARCH=x86_64 -j"${JOBS}" modules
    rm -rf "${ARTIFACT_DIR}/modules"
    make -C "${REPO_ROOT}" O="${BUILD_DIR}" ARCH=x86_64 INSTALL_MOD_PATH="${ARTIFACT_DIR}/modules" modules_install
fi

GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
GIT_DIRTY="$(git -C "${REPO_ROOT}" status --porcelain | wc -l | tr -d ' ')"
BZIMAGE_SHA256="$(sha256sum "${ARTIFACT_DIR}/bzImage" | awk '{print $1}')"
CONFIG_SHA256="$(sha256sum "${ARTIFACT_DIR}/os1_x86_64.config" | awk '{print $1}')"
GCC_VER="$(gcc --version | head -n 1)"
MAKE_VER="$(make --version | head -n 1)"
BUILD_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 - "${ARTIFACT_DIR}/provenance.json" <<PYEOF
import json, sys
data = {
    "project": "OS-1",
    "arch": "x86_64",
    "kernel_release": "${KERNEL_RELEASE}",
    "git_sha": "${GIT_SHA}",
    "git_dirty_entries": int("${GIT_DIRTY}"),
    "compiler": "${GCC_VER}",
    "make": "${MAKE_VER}",
    "build_timestamp_utc": "${BUILD_UTC}",
    "artifacts": {
        "bzImage": {
            "path": "distro/out/kernel/bzImage",
            "sha256": "${BZIMAGE_SHA256}",
        },
        "config": {
            "path": "distro/out/kernel/os1_x86_64.config",
            "sha256": "${CONFIG_SHA256}",
        },
    },
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

echo "[os1-kernel] Build SUCCESS"
echo "[os1-kernel]   bzImage:       ${ARTIFACT_DIR}/bzImage"
echo "[os1-kernel]   bzImage SHA256:${BZIMAGE_SHA256}"
echo "[os1-kernel]   kernelrelease: ${KERNEL_RELEASE}"
echo "[os1-kernel]   provenance:    ${ARTIFACT_DIR}/provenance.json"
