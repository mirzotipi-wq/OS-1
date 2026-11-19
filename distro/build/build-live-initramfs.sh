#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Phase 3: Build live SquashFS + OverlayFS initramfs for OS-1 UEFI Live ISO.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
STAGE_DIR="${OUT_ROOT}/live-initramfs-root"
INITRAMFS_DIR="${OUT_ROOT}/initramfs"
OUT_IMG="${INITRAMFS_DIR}/os1-live-initramfs.cpio.gz"

BUSYBOX_BIN=""
for candidate in /bin/busybox /usr/bin/busybox; do
    if [[ -x "${candidate}" ]] && file "${candidate}" 2>/dev/null | grep -qi "statically linked"; then
        BUSYBOX_BIN="${candidate}"
        break
    fi
done

if [[ -z "${BUSYBOX_BIN}" ]]; then
    echo "ERROR: Static BusyBox (/bin/busybox from busybox-static) is required for live ISO initramfs." >&2
    exit 1
fi

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}"/{bin,sbin,etc,proc,sys,dev,run,newroot,tmp} "${INITRAMFS_DIR}"

cp -f "${BUSYBOX_BIN}" "${STAGE_DIR}/bin/busybox"
chmod 0755 "${STAGE_DIR}/bin/busybox"

for applet in sh mount umount switch_root mkdir rmdir sleep cat echo grep ls mknod ln cp mv rm poweroff reboot uname; do
    ln -sf busybox "${STAGE_DIR}/bin/${applet}"
done
ln -sf ../bin/busybox "${STAGE_DIR}/sbin/switch_root"

cat > "${STAGE_DIR}/init" <<'INITEOF'
#!/bin/sh
set -u
export PATH=/bin:/sbin

mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mount -t tmpfs -o mode=0755 tmpfs /run

echo "=== OS-1_LIVE_INITRAMFS_START ==="
echo "OS-1_CMDLINE: $(cat /proc/cmdline)"

mkdir -p /run/live/medium /run/live/ro /run/live/rw /newroot

# Locate OS-1 live ISO medium containing /live/filesystem.squashfs
FOUND_DEV=""
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    for dev in /dev/sr0 /dev/sr1 /dev/vda /dev/vdb /dev/sda /dev/sdb /dev/nvme0n1; do
        [ -b "${dev}" ] || continue
        if mount -t iso9660 -o ro "${dev}" /run/live/medium 2>/dev/null; then
            if [ -f /run/live/medium/live/filesystem.squashfs ]; then
                FOUND_DEV="${dev}"
                break
            fi
            umount /run/live/medium 2>/dev/null || true
        fi
    done
    [ -n "${FOUND_DEV}" ] && break
    sleep 1
done

if [ -z "${FOUND_DEV}" ]; then
    echo "ERROR: Could not locate OS-1 live medium (/live/filesystem.squashfs)!"
    ls -la /dev/sr* /dev/vd* /dev/sd* 2>/dev/null || true
    exec /bin/sh
fi

echo "OS-1_LIVE_MEDIUM: ${FOUND_DEV}"

# Mount SquashFS read-only lower layer
mount -t squashfs -o loop,ro /run/live/medium/live/filesystem.squashfs /run/live/ro || {
    echo "ERROR: Failed to mount SquashFS rootfs!"
    exec /bin/sh
}

# Mount OverlayFS writable live root
mount -t tmpfs -o mode=0755 tmpfs /run/live/rw
mkdir -p /run/live/rw/upper /run/live/rw/work
mount -t overlay overlay -o "lowerdir=/run/live/ro,upperdir=/run/live/rw/upper,workdir=/run/live/rw/work" /newroot || {
    echo "ERROR: Failed to mount OverlayFS live root!"
    exec /bin/sh
}

# Move /run (a tmpfs mountpoint) into /newroot/run so systemd preserves /run/live/{medium,ro}
mkdir -p /newroot/run
mount --move /run /newroot/run 2>/dev/null || true

# Write live mode marker & neutralize /etc/fstab root mount for live session
echo "live" > /newroot/etc/os1-live-mode
cat > /newroot/etc/fstab <<'FSTABEOF'
# OS-1 Live ISO fstab (OverlayFS root managed by live initramfs)
tmpfs /tmp tmpfs defaults,nosuid,nodev 0 0
FSTABEOF

# Check for OS-1 Recovery Mode kernel parameter
if grep -qw "os1.recovery=1" /proc/cmdline; then
    echo "=== OS-1_RECOVERY_MODE_READY ==="
    mount --move /proc /newroot/proc 2>/dev/null || mount -t proc proc /newroot/proc
    mount --move /sys /newroot/sys 2>/dev/null || mount -t sysfs sysfs /newroot/sys
    mount --move /dev /newroot/dev 2>/dev/null || mount -t devtmpfs devtmpfs /newroot/dev
    exec switch_root /newroot /bin/bash -c '
        export PATH=/usr/sbin:/usr/bin:/sbin:/bin
        export PS1="os1-recovery# "
        echo "OS-1 Recovery Shell (root, live OverlayFS). Tools: fsck.ext4, parted, mount, chroot, poweroff -f"
        exec /bin/bash --norc --noprofile -i
    '
fi

echo "=== OS-1_LIVE_SWITCH_ROOT ==="
exec switch_root /newroot /sbin/init
INITEOF
chmod 0755 "${STAGE_DIR}/init"

python3 "${SCRIPT_DIR}/pack-initramfs.py" "${STAGE_DIR}" "${OUT_IMG}"
SHA="$(sha256sum "${OUT_IMG}" | awk '{print $1}')"
echo "[os1-live-initramfs] Built ${OUT_IMG} (sha256=${SHA})"
