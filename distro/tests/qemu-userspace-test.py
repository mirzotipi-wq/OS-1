#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 2 automated QEMU userspace & persistence verification test for OS-1.

Verifies on a clean disposable copy of distro/out/images/os1-rootfs.ext4.img:
  Boot 1:
    1. Boots the real OS-1 x86_64 kernel (bzImage) into Debian systemd PID 1.
    2. Reaches serial login prompt (`os1 login:`).
    3. Logs in as non-root user `os1` (uid != 0).
    4. Verifies `uname -r` matches `7.4.0-rc3-os1` and `/etc/os-release` identifies `ID=os1`.
    5. Verifies NetworkManager brings up networking with an IPv4 lease and DNS.
    6. Runs `sudo apt-get update && sudo apt-get install -y tree` over the network.
    7. Creates a persistent file `/home/os1/os1-phase2-persistence.txt` and syncs.
    8. Cleanly powers off via `sudo systemctl poweroff`.
  Boot 2 (reboot persistence check):
    9. Reboots the exact same disk image with the OS-1 kernel.
   10. Logs in as non-root `os1`, confirms the persistent file AND `tree` survived reboot.
   11. Cleanly powers off.
"""

import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time


class QemuSession:
    def __init__(self, kernel_path: str, disk_path: str, log_path: str) -> None:
        self.log_file = open(log_path, "wb")
        self.buf = ""
        self.master_fd, self.slave_fd = pty.openpty()

        accel_args = ["-accel", "tcg", "-cpu", "max"]
        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            accel_args = ["-enable-kvm", "-cpu", "host"]

        cmd = [
            "qemu-system-x86_64",
            *accel_args,
            "-m", "1024M",
            "-smp", "2",
            "-kernel", kernel_path,
            "-drive", f"file={disk_path},format=raw,if=virtio",
            "-netdev", "user,id=net0",
            "-device", "virtio-net-pci,netdev=net0",
            "-append", "root=/dev/vda rw console=ttyS0 panic=-1 net.ifnames=0",
            "-nographic",
            "-monitor", "none",
            "-no-reboot",
        ]
        print(f"[os1-phase2-test] Launching QEMU: {' '.join(cmd)}", flush=True)
        self.proc = subprocess.Popen(
            cmd,
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            close_fds=True,
        )
        os.close(self.slave_fd)

    def expect(self, needle: str, timeout: float = 180.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            idx = self.buf.find(needle)
            if idx != -1:
                matched = self.buf[: idx + len(needle)]
                self.buf = self.buf[idx + len(needle) :]
                return matched
            if self.proc.poll() is not None:
                # Drain any remaining bytes
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

    def sendline(self, line: str) -> None:
        os.write(self.master_fd, (line + "\n").encode("utf-8"))

    def run_cmd(self, cmd: str, marker: str, timeout: float = 120.0) -> str:
        self.sendline(f"{cmd}; printf '%s_RC=%d\\n' '{marker}' $?")
        out = self.expect(f"{marker}_RC=", timeout=timeout)
        rc_line = self.expect("\n", timeout=10.0).strip()
        if rc_line != "0":
            raise RuntimeError(f"Command failed (rc={rc_line}): {cmd}\nOutput:\n{out[-1000:]}")
        return out

    def login(self, user: str = "os1", password: str = "os1") -> None:
        self.expect("os1 login:", timeout=240.0)
        self.sendline(user)
        self.expect("Password:", timeout=30.0)
        self.sendline(password)
        self.expect(f"{user}@os1:", timeout=60.0)
        print(f"[PASS] Logged in as non-root user '{user}'", flush=True)

    def poweroff_and_wait(self, password: str = "os1", timeout: float = 120.0) -> None:
        self.sendline(f"echo {password} | sudo -S systemctl poweroff")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._drain(0.2)
            if self.proc.poll() is not None:
                break
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)
            raise TimeoutError("QEMU did not power off cleanly within timeout")
        self._drain(0.2)
        if self.proc.returncode != 0:
            raise RuntimeError(f"QEMU poweroff exited with rc={self.proc.returncode}")
        print("[PASS] Clean systemctl poweroff completed (rc=0)", flush=True)

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
    kernel_path = os.path.join(out_root, "kernel", "bzImage")
    src_disk = os.path.join(out_root, "images", "os1-rootfs.ext4.img")
    work_dir = tempfile.mkdtemp(prefix="os1-phase2-")
    work_disk = os.path.join(work_dir, "os1-phase2-test-disk.img")
    log_dir = os.path.join(out_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    for p in (kernel_path, src_disk):
        if not os.path.isfile(p):
            print(f"ERROR: Required artifact missing: {p}", file=sys.stderr)
            return 1

    shutil.copy2(src_disk, work_disk)
    boot1_log = os.path.join(log_dir, "qemu-phase2-boot1.log")
    boot2_log = os.path.join(log_dir, "qemu-phase2-boot2.log")

    persistence_token = "OS1-PHASE2-PERSISTENCE-VERIFIED-2026"

    # --- BOOT 1: Login, kernel check, network, apt install, file write, poweroff ---
    print("=== Phase 2 Boot 1: Userspace, Networking, APT Install, File Write ===", flush=True)
    vm1 = QemuSession(kernel_path, work_disk, boot1_log)
    try:
        vm1.login("os1", "os1")

        out = vm1.run_cmd("id -u && uname -r && grep '^ID=' /etc/os-release", "IDCHECK", timeout=30.0)
        if "7.4.0-rc3-os1" not in out:
            raise RuntimeError(f"Kernel release mismatch! Output:\n{out}")
        if "ID=os1" not in out:
            raise RuntimeError(f"/etc/os-release mismatch! Output:\n{out}")
        if "\n0\n" in out:
            raise RuntimeError(f"Expected non-root UID, got 0! Output:\n{out}")
        print("[PASS] Non-root UID, OS-1 kernel (7.4.0-rc3-os1), and ID=os1 verified", flush=True)

        # Wait up to 60s for NetworkManager DHCP on eth0
        vm1.run_cmd(
            "for i in $(seq 1 30); do ip -4 addr show dev eth0 | grep -q 'inet ' && break; sleep 2; done; ip -4 addr show dev eth0 | grep 'inet '",
            "NETCHECK",
            timeout=90.0,
        )
        print("[PASS] NetworkManager brought up IPv4 on eth0", flush=True)

        # Real APT update & package install over network
        vm1.run_cmd(
            "echo os1 | sudo -S apt-get update && echo os1 | sudo -S env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tree",
            "APTINSTALL",
            timeout=300.0,
        )
        vm1.run_cmd("tree --version", "TREEVER1", timeout=30.0)
        print("[PASS] Installed and executed 'tree' via APT over live network", flush=True)

        # Write persistent file and sync
        vm1.run_cmd(
            f"echo '{persistence_token}' > /home/os1/os1-phase2-persistence.txt && sync",
            "FILEWRITE",
            timeout=30.0,
        )
        print("[PASS] Wrote persistent file /home/os1/os1-phase2-persistence.txt", flush=True)

        vm1.poweroff_and_wait("os1")
    finally:
        vm1.close()

    # --- BOOT 2: Verify persistence of both file and installed package across reboot ---
    print("=== Phase 2 Boot 2: Reboot Persistence Verification ===", flush=True)
    vm2 = QemuSession(kernel_path, work_disk, boot2_log)
    try:
        vm2.login("os1", "os1")

        out = vm2.run_cmd(
            "cat /home/os1/os1-phase2-persistence.txt && tree --version && uname -r",
            "PERSISTCHECK",
            timeout=30.0,
        )
        if persistence_token not in out:
            raise RuntimeError(f"Persistent file content missing after reboot! Output:\n{out}")
        if "7.4.0-rc3-os1" not in out:
            raise RuntimeError(f"OS-1 kernel release missing on Boot 2! Output:\n{out}")
        print("[PASS] Persistent file AND installed 'tree' package survived reboot!", flush=True)

        vm2.poweroff_and_wait("os1")
    finally:
        vm2.close()

    # Check both logs for Kernel panic / Oops
    for lp in (boot1_log, boot2_log):
        with open(lp, "rb") as f:
            text = f.read().decode("utf-8", errors="replace")
        if "Kernel panic" in text or "Oops:" in text:
            print(f"ERROR: Kernel panic or Oops detected in {lp}", file=sys.stderr)
            return 1

    shutil.rmtree(work_dir, ignore_errors=True)
    print("[os1-phase2-test] ALL PHASE 2 USERSPACE & PERSISTENCE ASSERTIONS PASSED.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
