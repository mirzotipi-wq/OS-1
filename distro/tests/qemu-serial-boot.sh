#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Phase 1 automated QEMU serial boot proof for the OS-1 x86_64 kernel.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_ROOT="${OS1_OUT_DIR:-${REPO_ROOT}/distro/out}"
KERNEL_IMG="${OUT_ROOT}/kernel/bzImage"
INITRAMFS_IMG="${OUT_ROOT}/initramfs/os1-initramfs.cpio.gz"
LOG_DIR="${OUT_ROOT}/logs"
SERIAL_LOG="${LOG_DIR}/qemu-serial.log"
TIMEOUT_SEC="${OS1_QEMU_TIMEOUT:-120}"

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
    echo "ERROR: qemu-system-x86_64 not found in PATH." >&2
    echo "Install with: sudo apt-get install -y qemu-system-x86" >&2
    exit 1
fi

if [[ ! -f "${KERNEL_IMG}" ]]; then
    echo "ERROR: OS-1 kernel bzImage not found: ${KERNEL_IMG}" >&2
    echo "Run: ./distro/tools/os1.sh kernel" >&2
    exit 1
fi

if [[ ! -f "${INITRAMFS_IMG}" ]]; then
    echo "ERROR: OS-1 initramfs not found: ${INITRAMFS_IMG}" >&2
    echo "Run: ./distro/tools/os1.sh initramfs" >&2
    exit 1
fi

mkdir -p "${LOG_DIR}"
rm -f "${SERIAL_LOG}"

ACCEL_ARGS=(-accel tcg -cpu max)
ACCEL_MODE="tcg"
if [[ -r /dev/kvm && -w /dev/kvm ]]; then
    ACCEL_ARGS=(-enable-kvm -cpu host)
    ACCEL_MODE="kvm"
fi

echo "[os1-boot-test] Launching QEMU (${ACCEL_MODE}) with OS-1 kernel..."
echo "[os1-boot-test]   Kernel:    ${KERNEL_IMG}"
echo "[os1-boot-test]   Initramfs: ${INITRAMFS_IMG}"
echo "[os1-boot-test]   Log:       ${SERIAL_LOG}"

set +e
timeout "${TIMEOUT_SEC}" qemu-system-x86_64 \
    "${ACCEL_ARGS[@]}" \
    -m 512M \
    -smp 2 \
    -kernel "${KERNEL_IMG}" \
    -initrd "${INITRAMFS_IMG}" \
    -append "console=ttyS0 panic=-1" \
    -nographic \
    -monitor none \
    -no-reboot \
    > "${SERIAL_LOG}" 2>&1
QEMU_RC=$?
set -e

echo "[os1-boot-test] QEMU exited with code ${QEMU_RC}"

if (( QEMU_RC == 124 )); then
    echo "ERROR: QEMU timed out after ${TIMEOUT_SEC}s." >&2
    tail -n 50 "${SERIAL_LOG}" >&2 || true
    exit 1
fi

if (( QEMU_RC != 0 )); then
    echo "ERROR: QEMU exited abnormally (rc=${QEMU_RC})." >&2
    tail -n 50 "${SERIAL_LOG}" >&2 || true
    exit 1
fi

# Strip carriage returns for clean grepping
CLEAN_LOG="${LOG_DIR}/qemu-serial-clean.log"
tr -d '\r' < "${SERIAL_LOG}" > "${CLEAN_LOG}"

fail=0
assert_contains() {
    local pattern="$1"
    local desc="$2"
    if grep -Fq "${pattern}" "${CLEAN_LOG}"; then
        echo "[PASS] ${desc}"
    else
        echo "[FAIL] ${desc} (missing: ${pattern})" >&2
        fail=1
    fi
}

assert_absent() {
    local pattern="$1"
    local desc="$2"
    if grep -Fq "${pattern}" "${CLEAN_LOG}"; then
        echo "[FAIL] ${desc} (unexpected: ${pattern})" >&2
        fail=1
    else
        echo "[PASS] ${desc}"
    fi
}

assert_contains "Linux version 7.4.0-rc3-os1" "Kernel banner identifies OS-1 7.4.0-rc3-os1"
assert_contains "=== OS-1_INIT_START ===" "Kernel transitioned to PID 1 userspace init"
assert_contains "OS-1_UNAME: Linux" "Userspace uname reports Linux"
assert_contains "7.4.0-rc3-os1" "Userspace uname confirms OS-1 kernel release"
assert_contains "OS-1_TMP_WRITE_OK" "Userspace writable /tmp smoke test passed"
assert_contains "=== OS-1_BOOT_PROOF_PASS ===" "Userspace completed boot proof and requested poweroff"
assert_absent "Kernel panic" "No kernel panic in serial log"
assert_absent "Oops:" "No kernel Oops in serial log"

echo "--- OS-1 Boot Proof Excerpt ---"
grep -E "(Linux version |OS-1_)" "${CLEAN_LOG}" || true
echo "-------------------------------"

if (( fail != 0 )); then
    echo "ERROR: One or more QEMU boot proof assertions failed." >&2
    exit 1
fi

echo "[os1-boot-test] ALL ASSERTIONS PASSED."
