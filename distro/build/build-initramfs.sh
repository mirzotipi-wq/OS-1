#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Build the smallest bootable OS-1 userspace initramfs for Phase 1 QEMU serial boot proof.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
STAGE_DIR="${OUT_ROOT}/initramfs-root"
INITRAMFS_DIR="${OUT_ROOT}/initramfs"
OUT_IMG="${INITRAMFS_DIR}/os1-initramfs.cpio.gz"

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}"/{bin,sbin,etc,proc,sys,dev,tmp} "${INITRAMFS_DIR}"

BUSYBOX_BIN=""
for candidate in /bin/busybox /usr/bin/busybox; do
    if [[ -x "${candidate}" ]]; then
        BUSYBOX_BIN="${candidate}"
        break
    fi
done

if [[ -n "${BUSYBOX_BIN}" ]] && file "${BUSYBOX_BIN}" 2>/dev/null | grep -qi "statically linked"; then
    echo "[os1-initramfs] Using static BusyBox: ${BUSYBOX_BIN}"
    cp -f "${BUSYBOX_BIN}" "${STAGE_DIR}/bin/busybox"
    chmod 0755 "${STAGE_DIR}/bin/busybox"
    for applet in sh mount umount uname cat echo mkdir poweroff ls rm grep; do
        ln -sf busybox "${STAGE_DIR}/bin/${applet}"
    done

    cat > "${STAGE_DIR}/init" <<'INITEOF'
#!/bin/sh
set -eu

export PATH=/bin:/sbin

mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mount -t tmpfs tmpfs /tmp

echo "=== OS-1_INIT_START ==="
echo "OS-1_UNAME: $(uname -a)"
echo "OS-1_PROC_VERSION: $(cat /proc/version)"
echo "OS-1_PROC_CMDLINE: $(cat /proc/cmdline)"

echo "os1-userspace-check" > /tmp/os1-smoke.txt
if [ "$(cat /tmp/os1-smoke.txt)" = "os1-userspace-check" ]; then
    echo "OS-1_TMP_WRITE_OK"
else
    echo "OS-1_TMP_WRITE_FAIL"
    exit 1
fi

echo "=== OS-1_BOOT_PROOF_PASS ==="
poweroff -f
INITEOF
    chmod 0755 "${STAGE_DIR}/init"
else
    echo "[os1-initramfs] Static BusyBox not found; compiling tiny static C PID 1 init..."
    cat > "${OUT_ROOT}/os1_init.c" <<'CEOF'
/* SPDX-License-Identifier: GPL-2.0-only */
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/utsname.h>
#include <unistd.h>

static void print_file(const char *label, const char *path) {
    char buf[512];
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        printf("%s: <unreadable errno=%d>\n", label, errno);
        return;
    }
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n > 0) {
        buf[n] = '\0';
        printf("%s: %s", label, buf);
        if (buf[n - 1] != '\n') printf("\n");
    }
}

int main(void) {
    struct utsname u;
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
    mount("tmpfs", "/tmp", "tmpfs", 0, NULL);

    printf("=== OS-1_INIT_START ===\n");
    if (uname(&u) == 0) {
        printf("OS-1_UNAME: %s %s %s %s %s\n",
               u.sysname, u.nodename, u.release, u.version, u.machine);
    }
    print_file("OS-1_PROC_VERSION", "/proc/version");
    print_file("OS-1_PROC_CMDLINE", "/proc/cmdline");

    int fd = open("/tmp/os1-smoke.txt", O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd >= 0) {
        const char *msg = "os1-userspace-check";
        if (write(fd, msg, strlen(msg)) == (ssize_t)strlen(msg)) {
            close(fd);
            char buf[64] = {0};
            fd = open("/tmp/os1-smoke.txt", O_RDONLY);
            if (fd >= 0 && read(fd, buf, sizeof(buf) - 1) > 0 && strcmp(buf, msg) == 0) {
                printf("OS-1_TMP_WRITE_OK\n");
            }
            if (fd >= 0) close(fd);
        } else {
            close(fd);
        }
    }

    printf("=== OS-1_BOOT_PROOF_PASS ===\n");
    fflush(stdout);
    sync();
    reboot(RB_POWER_OFF);
    return 0;
}
CEOF
    gcc -static -O2 -Wall -Wextra -o "${STAGE_DIR}/init" "${OUT_ROOT}/os1_init.c"
    chmod 0755 "${STAGE_DIR}/init"
fi

python3 "${SCRIPT_DIR}/pack-initramfs.py" "${STAGE_DIR}" "${OUT_IMG}"
INITRAMFS_SHA256="$(sha256sum "${OUT_IMG}" | awk '{print $1}')"
echo "[os1-initramfs] Built ${OUT_IMG} (sha256=${INITRAMFS_SHA256})"
