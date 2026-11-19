#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Unified one-command CLI for OS-1 build, audit, boot, and cleanup tasks.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"

cmd="${1:-help}"
shift || true

case "${cmd}" in
    audit)
        echo "=== OS-1 Repository & Toolchain Audit ==="
        echo "Branch: $(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD)"
        echo "HEAD:   $(git -C "${REPO_ROOT}" rev-parse HEAD)"
        echo "Kernel Makefile:"
        grep -E '^(VERSION|PATCHLEVEL|SUBLEVEL|EXTRAVERSION|NAME) =' "${REPO_ROOT}/Makefile"
        echo "Shell script syntax check (bash -n):"
        for f in \
            "${REPO_ROOT}/distro/kernel/build-kernel.sh" \
            "${REPO_ROOT}/distro/build/build-initramfs.sh" \
            "${REPO_ROOT}/distro/build/build-rootfs.sh" \
            "${REPO_ROOT}/distro/tests/qemu-serial-boot.sh" \
            "${REPO_ROOT}/distro/tools/os1.sh"; do
            bash -n "${f}"
            echo "  [OK] ${f#${REPO_ROOT}/}"
        done
        echo "Python syntax check:"
        for f in \
            "${REPO_ROOT}/distro/build/pack-initramfs.py" \
            "${REPO_ROOT}/distro/tests/qemu-userspace-test.py"; do
            python3 -m py_compile "${f}"
            echo "  [OK] ${f#${REPO_ROOT}/}"
        done
        echo "Disk space:"
        df -h "${REPO_ROOT}"
        ;;
    kernel)
        exec "${REPO_ROOT}/distro/kernel/build-kernel.sh" "$@"
        ;;
    initramfs)
        exec "${REPO_ROOT}/distro/build/build-initramfs.sh" "$@"
        ;;
    boot-test)
        exec "${REPO_ROOT}/distro/tests/qemu-serial-boot.sh" "$@"
        ;;
    rootfs)
        exec "${REPO_ROOT}/distro/build/build-rootfs.sh" "$@"
        ;;
    userspace-test)
        exec python3 "${REPO_ROOT}/distro/tests/qemu-userspace-test.py" "$@"
        ;;
    clean)
        echo "[os1] Removing ephemeral build outputs: ${OUT_ROOT}"
        rm -rf "${OUT_ROOT}"
        ;;
    help|-h|--help)
        cat <<EOF
OS-1 Build & Verification CLI

Usage: ./distro/tools/os1.sh <command> [args...]

Commands:
  audit           Verify git state, kernel version, script syntax, and disk space
  kernel          Build the OS-1 x86_64 kernel (--config-only, --with-modules, -j N)
  initramfs       Build the minimal bootable OS-1 userspace initramfs (Phase 1)
  boot-test       Boot OS-1 kernel + initramfs in QEMU and assert serial proof (Phase 1)
  rootfs          Build pinned Debian stable rootfs + persistent ext4 disk image (Phase 2, root)
  userspace-test  Boot OS-1 kernel on persistent disk, login, network, APT, reboot test (Phase 2)
  clean           Remove generated build outputs in distro/out/
EOF
        ;;
    *)
        echo "ERROR: Unknown command: ${cmd}" >&2
        exit 2
        ;;
esac
