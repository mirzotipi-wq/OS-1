#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Phase 3: Build reproducible x86-64 UEFI bootable OS-1 Live ISO with Recovery Mode.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
KERNEL_IMG="${OUT_ROOT}/kernel/bzImage"
KERNEL_PROV="${OUT_ROOT}/kernel/provenance.json"
ROOTFS_DIR="${OUT_ROOT}/rootfs"
LIVE_INITRAMFS="${OUT_ROOT}/initramfs/os1-live-initramfs.cpio.gz"
ISO_WORK="${OUT_ROOT}/iso-work"
ISO_DIR="${OUT_ROOT}/iso"
ISO_OUT="${ISO_DIR}/os1-live-x86_64.iso"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: build-iso.sh must run as root (e.g. via sudo) to package rootfs into SquashFS and EFI image." >&2
    exit 1
fi

for tool in mksquashfs xorriso grub-mkstandalone mkfs.fat mmd mcopy; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        echo "ERROR: Required ISO build tool not found: ${tool}" >&2
        echo "Install: squashfs-tools xorriso grub-efi-amd64-bin grub-common dosfstools mtools" >&2
        exit 1
    fi
done

if [[ ! -f "${KERNEL_IMG}" ]]; then
    echo "ERROR: OS-1 kernel bzImage not found at ${KERNEL_IMG}. Run ./distro/tools/os1.sh kernel first." >&2
    exit 1
fi

if [[ ! -d "${ROOTFS_DIR}/etc" ]]; then
    echo "[os1-iso] Rootfs not found at ${ROOTFS_DIR}; building Phase 2 Debian rootfs..."
    "${SCRIPT_DIR}/build-rootfs.sh"
fi

echo "[os1-iso] Building live SquashFS + OverlayFS initramfs..."
"${SCRIPT_DIR}/build-live-initramfs.sh"

rm -rf "${ISO_WORK}"
mkdir -p "${ISO_WORK}"/{boot/grub,EFI/BOOT,live} "${ISO_DIR}"

echo "[os1-iso] Copying OS-1 kernel and live initramfs..."
cp -f "${KERNEL_IMG}" "${ISO_WORK}/boot/vmlinuz"
cp -f "${LIVE_INITRAMFS}" "${ISO_WORK}/boot/initrd.img"

echo "[os1-iso] Compressing rootfs into SquashFS (zstd)..."
mksquashfs "${ROOTFS_DIR}" "${ISO_WORK}/live/filesystem.squashfs" \
    -comp zstd \
    -noappend \
    -no-progress

KERNEL_REL="7.4.0-rc3-os1"
if [[ -f "${KERNEL_PROV}" ]]; then
    KERNEL_REL="$(python3 -c "import json; print(json.load(open('${KERNEL_PROV}'))['kernel_release'])")"
fi

cat > "${ISO_WORK}/boot/grub/grub.cfg" <<EOF
search --no-floppy --set=root --file /live/filesystem.squashfs

serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial

set default=0
set timeout=3

menuentry "OS-1 Live (${KERNEL_REL})" {
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200n8 net.ifnames=0 panic=-1
    initrd /boot/initrd.img
}

menuentry "OS-1 Recovery Mode (${KERNEL_REL})" {
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200n8 net.ifnames=0 os1.recovery=1 panic=-1
    initrd /boot/initrd.img
}
EOF

echo "[os1-iso] Generating standalone x86-64 UEFI GRUB image (BOOTX64.EFI)..."
grub-mkstandalone \
    --format=x86_64-efi \
    --output="${ISO_WORK}/EFI/BOOT/BOOTX64.EFI" \
    --locales="" \
    --fonts="" \
    "boot/grub/grub.cfg=${ISO_WORK}/boot/grub/grub.cfg"

echo "[os1-iso] Creating FAT EFI System Partition image (efiboot.img)..."
EFI_IMG="${ISO_WORK}/boot/grub/efiboot.img"
truncate -s 16M "${EFI_IMG}"
mkfs.fat -F 16 -n OS1_EFI "${EFI_IMG}" >/dev/null
mmd -i "${EFI_IMG}" ::/EFI ::/EFI/BOOT
mcopy -i "${EFI_IMG}" "${ISO_WORK}/EFI/BOOT/BOOTX64.EFI" ::/EFI/BOOT/BOOTX64.EFI

echo "[os1-iso] Generating UEFI bootable ISO via xorriso..."
rm -f "${ISO_OUT}"
xorriso -as mkisofs \
    -iso-level 3 \
    -full-iso9660-filenames \
    -volid "OS1_LIVE" \
    -eltorito-alt-boot \
    -e boot/grub/efiboot.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -output "${ISO_OUT}" \
    "${ISO_WORK}"

ISO_SHA256="$(sha256sum "${ISO_OUT}" | awk '{print $1}')"
SQUASH_SHA256="$(sha256sum "${ISO_WORK}/live/filesystem.squashfs" | awk '{print $1}')"
KERNEL_SHA256="$(sha256sum "${KERNEL_IMG}" | awk '{print $1}')"
ISO_SIZE_BYTES="$(stat -c%s "${ISO_OUT}")"
GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
BUILD_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 - "${ISO_DIR}/iso-provenance.json" <<PYEOF
import json, sys
data = {
    "project": "OS-1",
    "phase": 3,
    "arch": "x86_64",
    "boot_mode": "UEFI",
    "git_sha": "${GIT_SHA}",
    "kernel_release": "${KERNEL_REL}",
    "build_timestamp_utc": "${BUILD_UTC}",
    "artifacts": {
        "iso": {
            "path": "distro/out/iso/os1-live-x86_64.iso",
            "size_bytes": int("${ISO_SIZE_BYTES}"),
            "sha256": "${ISO_SHA256}",
        },
        "kernel_bzImage_sha256": "${KERNEL_SHA256}",
        "squashfs_sha256": "${SQUASH_SHA256}",
    },
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

if [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
    chown -R "${SUDO_UID}:${SUDO_GID}" "${ISO_DIR}" "${OUT_ROOT}/initramfs"
fi

echo "[os1-iso] SUCCESS"
echo "[os1-iso]   ISO:      ${ISO_OUT} ($(( ISO_SIZE_BYTES / 1024 / 1024 )) MiB)"
echo "[os1-iso]   SHA-256:  ${ISO_SHA256}"
echo "[os1-iso]   Manifest: ${ISO_DIR}/iso-provenance.json"
