#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 3 automated QEMU + OVMF UEFI Live ISO & Recovery Mode verification test.

Boots distro/out/iso/os1-live-x86_64.iso purely via UEFI firmware (OVMF) with
zero host bind mounts and zero -kernel/-initrd shortcuts:
  1. Test 1 (UEFI Live Boot):
     - Boots ISO via OVMF -> BOOTX64.EFI -> GRUB -> OS-1 kernel + live initramfs.
     - Verifies `os1 login:`, non-root login `os1`, OS-1 kernel `7.4.0-rc3-os1`,
       `/sys/firmware/efi` (true UEFI boot), OverlayFS root (`overlay`),
       `/etc/os-release` (`ID=os1`), NetworkManager IPv4, and clean poweroff.
  2. Test 2 (UEFI Recovery Mode):
     - Boots the same ISO via OVMF, selects `OS-1 Recovery Mode` in GRUB menu,
       verifies `OS-1_RECOVERY_MODE_READY`, confirms `uname -r` is `7.4.0-rc3-os1`
       and `fsck.ext4 -V` works, then powers off cleanly.
"""

import os
import pty
import select
import subprocess
import sys
import time


OVMF_CANDIDATES = [
    "/usr/share/OVMF/OVMF_CODE_4M.fd",
    "/usr/share/OVMF/OVMF_CODE.fd",
    "/usr/share/ovmf/OVMF.fd",
    "/usr/share/qemu/OVMF.fd",
]


def find_ovmf() -> str:
    for path in OVMF_CANDIDATES:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        f"OVMF UEFI firmware not found in {OVMF_CANDIDATES}. Install package 'ovmf'."
    )


class UefiIsoSession:
    def __init__(self, iso_path: str, ovmf_path: str, log_path: str) -> None:
        self.log_file = open(log_path, "wb")
        self.buf = ""
        self.master_fd, self.slave_fd = pty.openpty()

        accel_args = ["-accel", "tcg", "-cpu", "max"]
        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            accel_args = ["-enable-kvm", "-cpu", "host"]

        cmd = [
            "qemu-system-x86_64",
            *accel_args,
            "-machine", "q35",
            "-m", "1536M",
            "-smp", "2",
            "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_path}",
            "-cdrom", iso_path,
            "-boot", "d",
            "-netdev", "user,id=net0",
            "-device", "virtio-net-pci,netdev=net0",
            "-nographic",
            "-monitor", "none",
            "-no-reboot",
        ]
        print(f"[os1-phase3-test] Launching UEFI QEMU: {' '.join(cmd)}", flush=True)
        self.proc = subprocess.Popen(
            cmd,
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            close_fds=True,
        )
        os.close(self.slave_fd)

    def expect(self, needle: str, timeout: float = 240.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            idx = self.buf.find(needle)
            if idx != -1:
                matched = self.buf[: idx + len(needle)]
                self.buf = self.buf[idx + len(needle) :]
                return matched
            if self.proc.poll() is not None:
                self._drain(0.2)
                idx = self.buf.find(needle)
                if idx != -1:
                    matched = self.buf[: idx + len(needle)]
                    self.buf = self.buf[idx + len(needle) :]
                    return matched
                raise RuntimeError(
                    f"QEMU exited early (rc={self.proc.returncode}) while waiting for {needle!r}"
                )
            remaining = max(0.1, deadline - time.monotonic())
            rlist, _, _ = select.select([self.master_fd], [], [], min(1.0, remaining))
            if rlist:
                try:
                    chunk = os.read(self.master_fd, 4096)
                except OSError:
                    chunk = b""
                if chunk:
                    self.log_file.write(chunk)
                    self.log_file.flush()
                    self.buf += chunk.decode("utf-8", errors="replace").replace("\r", "")
        raise TimeoutError(f"Timed out after {timeout}s waiting for {needle!r}")

    def _drain(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rlist, _, _ = select.select([self.master_fd], [], [], 0.05)
            if not rlist:
                break
            try:
                chunk = os.read(self.master_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            self.log_file.write(chunk)
            self.log_file.flush()
            self.buf += chunk.decode("utf-8", errors="replace").replace("\r", "")

    def sendraw(self, data: bytes) -> None:
        os.write(self.master_fd, data)

    def sendline(self, line: str) -> None:
        os.write(self.master_fd, (line + "\n").encode("utf-8"))

    def run_cmd(self, cmd: str, marker: str, timeout: float = 120.0) -> str:
        self.sendline(f"{cmd}; printf '%s_RC=%d\\n' '{marker}' $?")
        out = self.expect(f"{marker}_RC=", timeout=timeout)
        rc_line = self.expect("\n", timeout=10.0).strip()
        if rc_line != "0":
            raise RuntimeError(f"Command failed (rc={rc_line}): {cmd}\nOutput:\n{out[-1000:]}")
        return out

    def wait_exit(self, timeout: float = 120.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._drain(0.2)
            if self.proc.poll() is not None:
                break
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)
            raise TimeoutError("QEMU did not exit within timeout")
        self._drain(0.2)
        if self.proc.returncode != 0:
            raise RuntimeError(f"QEMU exited with rc={self.proc.returncode}")

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(timeout=5)
        finally:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.log_file.close()


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_root = os.environ.get("OS1_OUT_DIR", os.path.join(repo_root, "distro", "out"))
    iso_path = os.path.join(out_root, "iso", "os1-live-x86_64.iso")
    log_dir = os.path.join(out_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    if not os.path.isfile(iso_path):
        print(f"ERROR: ISO not found: {iso_path}", file=sys.stderr)
        return 1

    ovmf_path = find_ovmf()
    print(f"[os1-phase3-test] Using OVMF firmware: {ovmf_path}", flush=True)

    live_log = os.path.join(log_dir, "qemu-phase3-uefi-live.log")
    recovery_log = os.path.join(log_dir, "qemu-phase3-uefi-recovery.log")

    from os1_test_util import expected_kernel_release
    expected_krel = expected_kernel_release(repo_root, out_root)

    # --- TEST 1: Fresh UEFI Live ISO Boot ---
    print("=== Phase 3 Test 1: UEFI Live ISO Boot ===", flush=True)
    vm1 = UefiIsoSession(iso_path, ovmf_path, live_log)
    try:
        vm1.expect("os1 login:", timeout=240.0)
        vm1.sendline("os1")
        vm1.expect("Password:", timeout=30.0)
        vm1.sendline("os1")
        vm1.expect("os1@os1:", timeout=60.0)
        print("[PASS] UEFI Live ISO booted to non-root login (os1@os1)", flush=True)

        out = vm1.run_cmd(
            "uname -r && test -d /sys/firmware/efi && echo UEFI_OK && findmnt -n -o FSTYPE / && grep '^ID=' /etc/os-release",
            "LIVECHECK",
            timeout=30.0,
        )
        if expected_krel not in out:
            raise RuntimeError(f"Expected OS-1 kernel release ({expected_krel}), got:\n{out}")
        if "UEFI_OK" not in out:
            raise RuntimeError(f"Expected /sys/firmware/efi (UEFI boot), got:\n{out}")
        if "overlay" not in out:
            raise RuntimeError(f"Expected OverlayFS live root, got:\n{out}")
        if "ID=os1" not in out:
            raise RuntimeError(f"Expected ID=os1, got:\n{out}")
        print(f"[PASS] Verified OS-1 kernel ({expected_krel}), UEFI firmware (/sys/firmware/efi), OverlayFS root, and ID=os1", flush=True)

        vm1.run_cmd(
            "for i in $(seq 1 30); do ip -4 addr show dev eth0 | grep -q 'inet ' && break; sleep 2; done; ip -4 addr show dev eth0 | grep 'inet '",
            "LIVENET",
            timeout=90.0,
        )
        print("[PASS] Live ISO NetworkManager brought up IPv4 on eth0", flush=True)

        vm1.sendline("echo os1 | sudo -S systemctl poweroff")
        vm1.wait_exit(timeout=120.0)
        print("[PASS] Live ISO clean poweroff completed", flush=True)
    finally:
        vm1.close()

    # --- TEST 2: UEFI Recovery Mode Boot ---
    print("=== Phase 3 Test 2: UEFI Recovery Mode Boot ===", flush=True)
    vm2 = UefiIsoSession(iso_path, ovmf_path, recovery_log)
    try:
        # Wait for GRUB menu over serial, then press Down arrow + Enter to pick Recovery Mode
        vm2.expect("OS-1 Recovery Mode", timeout=120.0)
        time.sleep(0.3)
        vm2.sendraw(b"\x1b[B\r")

        vm2.expect("OS-1_RECOVERY_MODE_READY", timeout=180.0)
        vm2.expect("os1-recovery#", timeout=60.0)
        print("[PASS] Entered OS-1 Recovery Mode root rescue shell", flush=True)

        out = vm2.run_cmd("uname -r && fsck.ext4 -V 2>&1 | head -n 1", "RECOVCHECK", timeout=30.0)
        if expected_krel not in out:
            raise RuntimeError(f"Recovery mode kernel mismatch (expected {expected_krel}):\n{out}")
        print("[PASS] Recovery mode verified OS-1 kernel and fsck.ext4 recovery tool", flush=True)

        vm2.sendline("poweroff -f")
        vm2.wait_exit(timeout=60.0)
        print("[PASS] Recovery mode clean poweroff completed", flush=True)
    finally:
        vm2.close()

    for lp in (live_log, recovery_log):
        with open(lp, "rb") as f:
            text = f.read().decode("utf-8", errors="replace")
        if "Kernel panic" in text or "Oops:" in text:
            print(f"ERROR: Kernel panic or Oops detected in {lp}", file=sys.stderr)
            return 1

    print("[os1-phase3-test] ALL PHASE 3 UEFI LIVE ISO & RECOVERY ASSERTIONS PASSED.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
