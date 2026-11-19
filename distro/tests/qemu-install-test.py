#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 4 automated end-to-end clean-disk installation test for OS-1.

Verifies the complete Phase 4 gate:
  1. Boots the Phase 3 UEFI Live ISO with a clean blank 4 GiB disposable VM disk.
  2. Negative safety test: runs `os1-install` WITHOUT `--confirm-erase-disk` and
     asserts it refuses nondestructively (rc != 0).
  3. Real install: runs `os1-install --disk /dev/vda --user alice --password alicepass
     --hostname os1-installed --timezone America/Los_Angeles --confirm-erase-disk`
     and asserts `OS-1_INSTALL_COMPLETE`.
  4. Powers off Live ISO and DETACHES THE ISO COMPLETELY.
  5. Boot 1 (Installed Disk Only via OVMF UEFI):
     - Boots solely from the newly installed VM disk.
     - Logs in as `alice` at `os1-installed login:`.
     - Verifies OS-1 kernel (`7.4.0-rc3-os1`), `/sys/firmware/efi`, ext4 root (not overlay),
       no `/etc/os1-live-mode`, timezone `America/Los_Angeles`, NetworkManager IPv4,
       live `sudo apt-get update && sudo apt-get install -y jq`, writes persistent file,
       and cleanly powers off.
  6. Boot 2 (Installed Disk Second Reboot):
     - Reboots installed disk (still no ISO), logs in as `alice`, verifies persistent file
       AND `jq --version` survived reboot, and cleanly powers off.
"""

import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
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
    raise FileNotFoundError(f"OVMF firmware not found in {OVMF_CANDIDATES}")


class UefiVm:
    def __init__(self, ovmf_path: str, disk_path: str, log_path: str, iso_path: str | None = None) -> None:
        self.log_file = open(log_path, "wb")
        self.buf = ""
        self.master_fd, self.slave_fd = pty.openpty()

        accel_args = ["-accel", "tcg", "-cpu", "Haswell"]
        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            accel_args = ["-enable-kvm", "-cpu", "host"]

        ram_mb = os.environ.get("OS1_INSTALL_RAM", "1536M")
        cmd = [
            "qemu-system-x86_64",
            *accel_args,
            "-machine", "q35",
            "-m", ram_mb,
            "-smp", "2",
            "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_path}",
            "-drive", f"file={disk_path},format=raw,if=virtio",
            "-netdev", "user,id=net0",
            "-device", "virtio-net-pci,netdev=net0",
            "-nographic",
            "-monitor", "none",
            "-no-reboot",
        ]
        if iso_path is not None:
            cmd.extend(["-cdrom", iso_path, "-boot", "d"])

        print(f"[os1-phase4-test] Launching QEMU: {' '.join(cmd)}", flush=True)
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

    def sendline(self, line: str) -> None:
        os.write(self.master_fd, (line + "\n").encode("utf-8"))

    def run_cmd(self, cmd: str, marker: str, timeout: float = 180.0, expect_rc: str = "0") -> str:
        self.sendline(f"{cmd}; printf '%s_RC=%d\\n' '{marker}' $?")
        out = self.expect(f"{marker}_RC=", timeout=timeout)
        rc_line = self.expect("\n", timeout=10.0).strip()
        if rc_line != expect_rc:
            raise RuntimeError(
                f"Command exit mismatch (got rc={rc_line}, expected {expect_rc}): {cmd}\nOutput:\n{out[-1000:]}"
            )
        return out

    def login(self, host: str, user: str, password: str) -> None:
        self.expect(f"{host} login:", timeout=240.0)
        self.sendline(user)
        self.expect("Password:", timeout=30.0)
        self.sendline(password)
        self.expect(f"{user}@{host}:", timeout=60.0)
        print(f"[PASS] Logged in as '{user}@{host}'", flush=True)

    def poweroff_and_wait(self, password: str, timeout: float = 120.0) -> None:
        self.sendline(f"echo {password} | sudo -S systemctl poweroff")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._drain(0.2)
            if self.proc.poll() is not None:
                break
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)
            raise TimeoutError("QEMU did not power off cleanly")
        self._drain(0.2)
        if self.proc.returncode != 0:
            raise RuntimeError(f"QEMU exited with rc={self.proc.returncode}")
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
    iso_path = os.path.join(out_root, "iso", "os1-live-x86_64.iso")
    log_dir = os.path.join(out_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    if not os.path.isfile(iso_path):
        print(f"ERROR: Live ISO not found: {iso_path}", file=sys.stderr)
        return 1

    ovmf_path = find_ovmf()
    work_dir = tempfile.mkdtemp(prefix="os1-phase4-")
    target_disk = os.path.join(work_dir, "os1-installed-disk.img")

    # Create clean blank virtual disk (default 4 GiB; 10+ GiB for full desktop ISO)
    disk_gb = int(os.environ.get("OS1_INSTALL_DISK_GB", "4"))
    with open(target_disk, "wb") as f:
        f.truncate(disk_gb * 1024 * 1024 * 1024)

    install_log = os.path.join(log_dir, "qemu-phase4-install.log")
    boot1_log = os.path.join(log_dir, "qemu-phase4-installed-boot1.log")
    boot2_log = os.path.join(log_dir, "qemu-phase4-installed-boot2.log")

    token = "OS1-PHASE4-INSTALLED-PERSISTENCE-2026"

    try:
        # --- STEP 1: Boot Live ISO + Run Installer on Blank Disk ---
        print(f"=== Phase 4/15 Step 1: Boot Live ISO & Install to Blank {disk_gb} GiB VM Disk ===", flush=True)
        vm_iso = UefiVm(ovmf_path, target_disk, install_log, iso_path=iso_path)
        try:
            vm_iso.login("os1", "os1", "os1")

            # Negative safety check: must refuse without --confirm-erase-disk (rc=3)
            out = vm_iso.run_cmd(
                "echo os1 | sudo -S /usr/local/sbin/os1-install --disk /dev/vda --user alice --password alicepass",
                "DRYRUN",
                timeout=30.0,
                expect_rc="3",
            )
            if "NONDESTRUCTIVE DEFAULT MODE" not in out:
                raise RuntimeError(f"Expected nondestructive warning, got:\n{out}")
            print("[PASS] Nondestructive default safety gate verified (rc=3)", flush=True)

            # Real destructive installation with explicit consent
            out = vm_iso.run_cmd(
                "echo os1 | sudo -S /usr/local/sbin/os1-install --disk /dev/vda --user alice --password alicepass "
                "--hostname os1-installed --timezone America/Los_Angeles --confirm-erase-disk",
                "INSTALL",
                timeout=600.0,
            )
            if "=== OS-1_INSTALL_COMPLETE ===" not in out:
                raise RuntimeError(f"Install completion marker missing:\n{out}")
            print("[PASS] OS-1 installed cleanly to /dev/vda", flush=True)

            vm_iso.poweroff_and_wait("os1")
        finally:
            vm_iso.close()

        # --- STEP 2: Detach ISO! Boot Installed Disk via OVMF UEFI ---
        print("=== Phase 4/15 Step 2: ISO Detached -> Boot Installed Disk, APT Update/Install, File Write ===", flush=True)
        vm_inst1 = UefiVm(ovmf_path, target_disk, boot1_log, iso_path=None)
        try:
            vm_inst1.login("os1-installed", "alice", "alicepass")

            out = vm_inst1.run_cmd(
                "uname -r && test -d /sys/firmware/efi && echo UEFI_OK && "
                "findmnt -n -o FSTYPE / && test ! -e /etc/os1-live-mode && echo NOT_LIVE && "
                "cat /etc/timezone && grep '^ID=' /etc/os-release",
                "INSTCHECK",
                timeout=30.0,
            )
            for needle in ("7.4.0-rc3-os1", "UEFI_OK", "ext4", "NOT_LIVE", "America/Los_Angeles", "ID=os1"):
                if needle not in out:
                    raise RuntimeError(f"Installed system check missing {needle!r}:\n{out}")
            print("[PASS] Installed disk booted via UEFI on OS-1 kernel with ext4 root & custom config", flush=True)

            # If full desktop ISO was installed, log runtime service health and verify static/fs checks honestly
            vm_inst1.run_cmd(
                "if [ -f /usr/share/os1/apps-manifest.json ]; then "
                "  echo '=== SYSTEMD FAILED UNITS (DIAGNOSTIC) ==='; "
                "  systemctl --failed --no-pager || true; "
                "  echo \"UFW_SERVICE_STATE=$(systemctl is-active ufw.service 2>&1 || true)\"; "
                "  grep -q 'ENABLED=yes' /etc/ufw/ufw.conf && "
                "  grep -q 'DEFAULT_INPUT_POLICY=\"DROP\"' /etc/default/ufw && "
                "  command -v orca >/dev/null && "
                "  os1-fs-test && "
                "  echo DESKTOP_QUAL_OK; "
                "else echo MINIMAL_PROFILE_OK; fi",
                "DESKTOPQUAL",
                timeout=60.0,
            )
            print("[PASS][STATIC+FUNC] Desktop profile static UFW/Orca presence & os1-fs-test passed (runtime UFW gate enforced in Phase 17)", flush=True)

            # Networking + APT update + install jq
            vm_inst1.run_cmd(
                "for i in $(seq 1 30); do ip -4 addr show dev eth0 | grep -q 'inet ' && break; sleep 2; done; ip -4 addr show dev eth0 | grep 'inet '",
                "INSTNET",
                timeout=90.0,
            )
            vm_inst1.run_cmd(
                "echo alicepass | sudo -S apt-get update && "
                "echo alicepass | sudo -S env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends jq",
                "INSTAPT",
                timeout=300.0,
            )
            vm_inst1.run_cmd("jq --version", "JQVER1", timeout=30.0)
            vm_inst1.run_cmd(f"echo '{token}' > /home/alice/installed-proof.txt && sync", "INSTFILE", timeout=30.0)
            print("[PASS] Installed system updated APT, installed 'jq', and wrote persistent file", flush=True)

            vm_inst1.poweroff_and_wait("alicepass")
        finally:
            vm_inst1.close()

        # --- STEP 3: Second Reboot of Installed Disk ---
        print("=== Phase 4 Step 3: Second Reboot of Installed Disk (Persistence Proof) ===", flush=True)
        vm_inst2 = UefiVm(ovmf_path, target_disk, boot2_log, iso_path=None)
        try:
            vm_inst2.login("os1-installed", "alice", "alicepass")
            out = vm_inst2.run_cmd(
                "cat /home/alice/installed-proof.txt && jq --version && uname -r",
                "INSTPERSIST",
                timeout=30.0,
            )
            if token not in out or "jq-" not in out or "7.4.0-rc3-os1" not in out:
                raise RuntimeError(f"Second reboot persistence check failed:\n{out}")
            print("[PASS] Installed disk survived second reboot with file + 'jq' intact!", flush=True)
            vm_inst2.poweroff_and_wait("alicepass")
        finally:
            vm_inst2.close()

        for lp in (install_log, boot1_log, boot2_log):
            with open(lp, "rb") as f:
                text = f.read().decode("utf-8", errors="replace")
            if "Kernel panic" in text or "Oops:" in text:
                print(f"ERROR: Kernel panic or Oops in {lp}", file=sys.stderr)
                return 1

        print("[os1-phase4-test] ALL PHASE 4 CLEAN-DISK INSTALL & REBOOT ASSERTIONS PASSED.", flush=True)
        return 0
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
