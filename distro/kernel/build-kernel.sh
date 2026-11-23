#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Reproducible out-of-tree x86_64 Linux LTS kernel builder for OS-1.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
BUILD_DIR="${OUT_ROOT}/kernel-build"
ARTIFACT_DIR="${OUT_ROOT}/kernel"
SRC_CACHE_DIR="${OS1_KERNEL_CACHE_DIR:-${OUT_ROOT}/kernel-src}"
FRAGMENT="${SCRIPT_DIR}/os1_x86_64.fragment"
LTS_ENV="${SCRIPT_DIR}/KERNEL_LTS.env"

# shellcheck source=KERNEL_LTS.env
source "${LTS_ENV}"

CONFIG_ONLY=0
BUILD_MODULES=0
JOBS="${OS1_JOBS:-$(nproc)}"
KERNEL_SRC_OVERRIDE="${OS1_KERNEL_SRC:-}"

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --config-only     Generate and validate merged x86_64 .config without compiling bzImage
  --with-modules    Also compile kernel modules and install them into distro/out/kernel/modules
  --source-dir DIR  Build from an existing local kernel source directory instead of downloading LTS tarball
  -j, --jobs N      Parallel make jobs (default: nproc = ${JOBS})
  -h, --help        Show this help message

Environment:
  OS1_KERNEL_SRC          Override kernel source directory
  OS1_KERNEL_CACHE_DIR    Directory to cache downloaded/extracted LTS tarballs
  OS1_ALLOW_RC_KERNEL=1   Permit building an -rc kernel (disallowed by default for GA readiness)
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config-only) CONFIG_ONLY=1; shift ;;
        --with-modules) BUILD_MODULES=1; shift ;;
        --source-dir) KERNEL_SRC_OVERRIDE="$2"; shift 2 ;;
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
echo "[os1-kernel] Pinned upstream LTS: Linux ${OS1_KERNEL_VERSION} (${OS1_KERNEL_CHANNEL})"
echo "[os1-kernel] Out-of-tree build dir: ${BUILD_DIR}"
echo "[os1-kernel] Artifact dir: ${ARTIFACT_DIR}"

# Required tools for Kconfig + tarball verification
missing=0
for tool in gcc make flex bison awk sed perl python3 tar xz sha256sum; do
    check_cmd "${tool}" || missing=1
done
if [[ -z "${KERNEL_SRC_OVERRIDE}" ]]; then
    check_cmd curl || missing=1
fi
if (( CONFIG_ONLY == 0 )); then
    for tool in bc objcopy objdump readelf nm strip ar; do
        check_cmd "${tool}" || missing=1
    done
fi
if (( missing != 0 )); then
    echo "ERROR: Missing required kernel build tools. On Debian/Ubuntu install:" >&2
    echo "  build-essential bc bison flex libssl-dev libelf-dev kmod curl xz-utils" >&2
    exit 1
fi

if (( CONFIG_ONLY == 1 )); then
    check_disk_space_mb "${OUT_ROOT}" 1536
else
    check_disk_space_mb "${OUT_ROOT}" 5120
fi

mkdir -p "${BUILD_DIR}" "${ARTIFACT_DIR}" "${SRC_CACHE_DIR}"

# Resolve kernel source tree: either explicit local override or SHA-256 verified upstream LTS tarball
if [[ -n "${KERNEL_SRC_OVERRIDE}" ]]; then
    if [[ ! -f "${KERNEL_SRC_OVERRIDE}/Makefile" ]]; then
        echo "ERROR: --source-dir / OS1_KERNEL_SRC does not contain a kernel Makefile: ${KERNEL_SRC_OVERRIDE}" >&2
        exit 1
    fi
    KERNEL_SRC="$(cd "${KERNEL_SRC_OVERRIDE}" && pwd)"
    KERNEL_SOURCE_MODE="local-override"
    echo "[os1-kernel] Using local kernel source override: ${KERNEL_SRC}"
else
    TARBALL_PATH="${SRC_CACHE_DIR}/${OS1_KERNEL_TARBALL}"
    EXTRACTED_DIR="${SRC_CACHE_DIR}/linux-${OS1_KERNEL_VERSION}"
    STAMP_FILE="${EXTRACTED_DIR}/.os1-verified-sha256"

    if [[ ! -f "${TARBALL_PATH}" ]]; then
        echo "[os1-kernel] Downloading ${OS1_KERNEL_URL}..."
        TMP_TAR="${TARBALL_PATH}.part.$$"
        curl -fL --retry 3 --retry-delay 3 -o "${TMP_TAR}" "${OS1_KERNEL_URL}"
        mv -f "${TMP_TAR}" "${TARBALL_PATH}"
    fi

    ACTUAL_SHA256="$(sha256sum "${TARBALL_PATH}" | awk '{print $1}')"
    if [[ "${ACTUAL_SHA256}" != "${OS1_KERNEL_SHA256}" ]]; then
        echo "ERROR: SHA-256 mismatch for ${TARBALL_PATH}!" >&2
        echo "  Expected: ${OS1_KERNEL_SHA256}" >&2
        echo "  Actual:   ${ACTUAL_SHA256}" >&2
        rm -f "${TARBALL_PATH}"
        exit 1
    fi
    echo "[os1-kernel] Verified ${OS1_KERNEL_TARBALL} SHA-256: ${ACTUAL_SHA256}"

    if [[ ! -f "${STAMP_FILE}" ]] || [[ "$(cat "${STAMP_FILE}")" != "${OS1_KERNEL_SHA256}" ]]; then
        echo "[os1-kernel] Extracting ${OS1_KERNEL_TARBALL} into ${SRC_CACHE_DIR}..."
        rm -rf "${EXTRACTED_DIR}"
        tar -xf "${TARBALL_PATH}" -C "${SRC_CACHE_DIR}"
        if [[ ! -f "${EXTRACTED_DIR}/Makefile" ]]; then
            echo "ERROR: Extracted kernel tree missing Makefile at ${EXTRACTED_DIR}" >&2
            exit 1
        fi
        printf '%s\n' "${OS1_KERNEL_SHA256}" > "${STAMP_FILE}"
    fi
    KERNEL_SRC="${EXTRACTED_DIR}"
    KERNEL_SOURCE_MODE="pinned-upstream-lts"
fi

echo "[os1-kernel] Kernel source tree: ${KERNEL_SRC}"

echo "[os1-kernel] Generating base x86_64_defconfig..."
make -C "${KERNEL_SRC}" O="${BUILD_DIR}" ARCH=x86_64 defconfig

echo "[os1-kernel] Merging OS-1 fragment: ${FRAGMENT}"
"${KERNEL_SRC}/scripts/kconfig/merge_config.sh" -m -O "${BUILD_DIR}" "${BUILD_DIR}/.config" "${FRAGMENT}"
make -C "${KERNEL_SRC}" O="${BUILD_DIR}" ARCH=x86_64 olddefconfig

cp -f "${BUILD_DIR}/.config" "${ARTIFACT_DIR}/os1_x86_64.config"

# Verify critical OS-1 options survived olddefconfig
for sym in \
    CONFIG_LOCALVERSION=\"-os1\" \
    CONFIG_VIRTIO_BLK=y \
    CONFIG_SERIAL_8250_CONSOLE=y \
    CONFIG_BLK_DEV_INITRD=y \
    CONFIG_EFI_STUB=y \
    CONFIG_NETFILTER=y \
    CONFIG_NF_TABLES=y \
    CONFIG_NFT_COMPAT=y \
    CONFIG_NF_CONNTRACK=y \
    CONFIG_SECURITY_APPARMOR=y \
    CONFIG_BLK_DEV_DM=y \
    CONFIG_DM_CRYPT=y \
    CONFIG_ZRAM=y; do
    if ! grep -Fq "${sym}" "${ARTIFACT_DIR}/os1_x86_64.config"; then
        echo "ERROR: Expected Kconfig symbol missing after merge: ${sym}" >&2
        exit 1
    fi
done
echo "[os1-kernel] Kconfig validation PASSED -> ${ARTIFACT_DIR}/os1_x86_64.config"

python3 "${REPO_ROOT}/distro/tests/kernel-driver-audit.py" \
    --config "${ARTIFACT_DIR}/os1_x86_64.config" \
    --manifest "${ARTIFACT_DIR}/driver-manifest.json"

make -C "${KERNEL_SRC}" O="${BUILD_DIR}" ARCH=x86_64 include/config/kernel.release
KERNEL_RELEASE="$(cat "${BUILD_DIR}/include/config/kernel.release")"
if [[ "${KERNEL_RELEASE}" != *"-os1"* ]]; then
    echo "ERROR: Expected -os1 in kernelrelease, got: ${KERNEL_RELEASE}" >&2
    exit 1
fi
if [[ "${OS1_ALLOW_RC_KERNEL:-0}" != "1" && "${KERNEL_RELEASE}" == *"-rc"* ]]; then
    echo "ERROR: Refusing to build release-candidate kernel (${KERNEL_RELEASE}) for production OS-1. Set OS1_ALLOW_RC_KERNEL=1 only for experimental RC builds." >&2
    exit 1
fi
echo "[os1-kernel] Computed kernelrelease: ${KERNEL_RELEASE}"

if (( CONFIG_ONLY == 1 )); then
    echo "[os1-kernel] --config-only requested; skipping bzImage compilation."
    exit 0
fi

echo "[os1-kernel] Compiling OS-1 x86_64 bzImage with -j${JOBS}..."
make -C "${KERNEL_SRC}" O="${BUILD_DIR}" ARCH=x86_64 -j"${JOBS}" bzImage

BZIMAGE_SRC="${BUILD_DIR}/arch/x86/boot/bzImage"
if [[ ! -f "${BZIMAGE_SRC}" ]]; then
    echo "ERROR: Expected bzImage not found at ${BZIMAGE_SRC}" >&2
    exit 1
fi

cp -f "${BZIMAGE_SRC}" "${ARTIFACT_DIR}/bzImage"
cp -f "${BUILD_DIR}/System.map" "${ARTIFACT_DIR}/System.map"

if (( BUILD_MODULES == 1 )); then
    echo "[os1-kernel] Compiling and installing modules..."
    make -C "${KERNEL_SRC}" O="${BUILD_DIR}" ARCH=x86_64 -j"${JOBS}" modules
    rm -rf "${ARTIFACT_DIR}/modules"
    make -C "${KERNEL_SRC}" O="${BUILD_DIR}" ARCH=x86_64 INSTALL_MOD_PATH="${ARTIFACT_DIR}/modules" modules_install
    if command -v depmod >/dev/null 2>&1; then
        depmod -b "${ARTIFACT_DIR}/modules" "${KERNEL_RELEASE}"
    fi
    python3 "${REPO_ROOT}/distro/tests/kernel-driver-audit.py" \
        --config "${ARTIFACT_DIR}/os1_x86_64.config" \
        --modules-dir "${ARTIFACT_DIR}/modules" \
        --check-modules \
        --manifest "${ARTIFACT_DIR}/driver-manifest.json"
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
    "kernel_upstream_version": "${OS1_KERNEL_VERSION}",
    "kernel_channel": "${OS1_KERNEL_CHANNEL}",
    "kernel_source_mode": "${KERNEL_SOURCE_MODE}",
    "kernel_source_url": "${OS1_KERNEL_URL}",
    "kernel_tarball_sha256": "${OS1_KERNEL_SHA256}",
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
