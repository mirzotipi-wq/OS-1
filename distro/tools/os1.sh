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
            "${REPO_ROOT}/distro/build/build-live-initramfs.sh" \
            "${REPO_ROOT}/distro/build/build-rootfs.sh" \
            "${REPO_ROOT}/distro/build/build-iso.sh" \
            "${REPO_ROOT}/distro/packages/build-debs.sh" \
            "${REPO_ROOT}/distro/packages/build-kernel-deb.sh" \
            "${REPO_ROOT}/distro/installer/os1-firstboot" \
            "${REPO_ROOT}/distro/shell/bin/os1-appearance" \
            "${REPO_ROOT}/distro/shell/bin/os1-shell-init" \
            "${REPO_ROOT}/distro/shell/bin/os1-accessibility" \
            "${REPO_ROOT}/distro/tests/qemu-serial-boot.sh" \
            "${REPO_ROOT}/distro/tools/os1.sh"; do
            bash -n "${f}"
            echo "  [OK] ${f#${REPO_ROOT}/}"
        done
        echo "Python syntax check:"
        for f in \
            "${REPO_ROOT}/distro/branding/generate-assets.py" \
            "${REPO_ROOT}/distro/build/pack-initramfs.py" \
            "${REPO_ROOT}/distro/build/generate-sbom.py" \
            "${REPO_ROOT}/distro/installer/os1-install" \
            "${REPO_ROOT}/distro/tools/os1-update-boot" \
            "${REPO_ROOT}/distro/tests/ci-integrity-test.py" \
            "${REPO_ROOT}/distro/tests/installer-safety-test.py" \
            "${REPO_ROOT}/distro/tests/package-verify-test.py" \
            "${REPO_ROOT}/distro/tests/fs-operations-test.py" \
            "${REPO_ROOT}/distro/tests/qemu-userspace-test.py" \
            "${REPO_ROOT}/distro/tests/qemu-firewall-test.py" \
            "${REPO_ROOT}/distro/tests/qemu-iso-uefi-test.py" \
            "${REPO_ROOT}/distro/tests/qemu-install-test.py" \
            "${REPO_ROOT}/distro/tests/qemu-update-rollback-test.py" \
            "${REPO_ROOT}/distro/tests/qemu-wayland-test.py"; do
            python3 -m py_compile "${f}"
            echo "  [OK] ${f#${REPO_ROOT}/}"
        done
        echo "CI workflow integrity check:"
        python3 "${REPO_ROOT}/distro/tests/ci-integrity-test.py"
        echo "Installer preflight & credential safety check:"
        python3 "${REPO_ROOT}/distro/tests/installer-safety-test.py"
        echo "Native Debian package correctness check:"
        python3 "${REPO_ROOT}/distro/tests/package-verify-test.py"
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
    firewall-test)
        exec python3 "${REPO_ROOT}/distro/tests/qemu-firewall-test.py" "$@"
        ;;
    iso)
        exec "${REPO_ROOT}/distro/build/build-iso.sh" "$@"
        ;;
    iso-test)
        exec python3 "${REPO_ROOT}/distro/tests/qemu-iso-uefi-test.py" "$@"
        ;;
    install-test)
        exec python3 "${REPO_ROOT}/distro/tests/qemu-install-test.py" "$@"
        ;;
    update-rollback-test)
        exec python3 "${REPO_ROOT}/distro/tests/qemu-update-rollback-test.py" "$@"
        ;;
    wayland-test)
        exec python3 "${REPO_ROOT}/distro/tests/qemu-wayland-test.py" "$@"
        ;;
    debs)
        exec "${REPO_ROOT}/distro/packages/build-debs.sh" "$@"
        ;;
    pkg-verify)
        exec python3 "${REPO_ROOT}/distro/tests/package-verify-test.py" "$@"
        ;;
    sbom)
        exec python3 "${REPO_ROOT}/distro/build/generate-sbom.py" "$@"
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
  rootfs          Build pinned Debian stable rootfs + persistent ext4 disk image (Phase 2/5, root)
  userspace-test  Boot OS-1 kernel on persistent disk, login, network, APT, reboot test (Phase 2)
  iso             Build x86-64 UEFI bootable Live ISO with Recovery Mode (Phase 3, root)
  iso-test        Boot fresh UEFI Live ISO + Recovery Mode in QEMU/OVMF (Phase 3)
  install-test    Boot UEFI Live ISO, install to blank disk, verify installed UEFI boot (Phase 4/15)
  wayland-test    Boot OS-1 Wayland desktop in QEMU, verify KWin/Plasma & capture screenshot (Phase 5-12)
  debs            Build native OS-1 .deb packages and local APT repository (Phase 14)
  sbom            Generate CycloneDX 1.5 JSON SBOM for current build outputs (Phase 14)
  clean           Remove generated build outputs in distro/out/
EOF
        ;;
    *)
        echo "ERROR: Unknown command: ${cmd}" >&2
        exit 2
        ;;
esac
