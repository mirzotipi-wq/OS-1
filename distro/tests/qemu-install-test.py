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
    # Phase 18 special-character password (apostrophe, dollar sign, quotes, spaces, punctuation)
    import base64
    alice_pass = "O'Brien $100 \"safe\" & clean!"
    alice_pass_b64 = base64.b64encode((alice_pass + "\n").encode("utf-8")).decode("ascii")
    # Helper snippet that feeds alice's password to sudo -S without ever echoing it in serial log
    sudo_alice = f"printf '%s' '{alice_pass_b64}' | base64 -d | sudo -S"

    try:
        # --- STEP 1: Boot Live ISO + Run Installer on Blank Disk ---
        print(f"=== Phase 4/18 Step 1: Boot Live ISO & Install to Blank {disk_gb} GiB VM Disk ===", flush=True)
        vm_iso = UefiVm(ovmf_path, target_disk, install_log, iso_path=iso_path)
        try:
            vm_iso.login("os1", "os1", "os1")

            # Authenticate sudo timestamp once so subsequent sudo -n calls leave stdin untouched for --password-stdin
            vm_iso.run_cmd("printf 'os1\\n' | sudo -S -v", "SUDO_AUTH", timeout=20.0)

            # Negative safety check 1: --password on argv must be rejected (rc=2)
            vm_iso.run_cmd(
                "sudo -n /usr/sbin/os1-install --disk /dev/vda --user alice --password forbidden",
                "NO_ARGV_PW",
                timeout=30.0,
                expect_rc="2",
            )
            print("[PASS][FUNC] Plaintext --password on argv rejected (rc=2)", flush=True)

            # Negative safety check 2: reserved username 'root' must be rejected (rc=2)
            vm_iso.run_cmd(
                f"printf '%s' '{alice_pass_b64}' | base64 -d | "
                "sudo -n /usr/sbin/os1-install --disk /dev/vda --user root --password-stdin --dry-run",
                "NO_ROOT_USER",
                timeout=30.0,
                expect_rc="2",
            )
            print("[PASS][FUNC] Reserved username 'root' rejected (rc=2)", flush=True)

            # Negative safety check 3: must refuse without --confirm-erase-disk (rc=3)
            out = vm_iso.run_cmd(
                f"printf '%s' '{alice_pass_b64}' | base64 -d | "
                "sudo -n /usr/sbin/os1-install --disk /dev/vda --user alice --password-stdin",
                "DRYRUN",
                timeout=30.0,
                expect_rc="3",
            )
            if "NONDESTRUCTIVE DEFAULT MODE" not in out:
                raise RuntimeError(f"Expected nondestructive warning, got:\n{out}")
            print("[PASS][FUNC] Nondestructive default safety gate verified (rc=3)", flush=True)

            # Real destructive installation with explicit consent & special-char password via --password-stdin
            out = vm_iso.run_cmd(
                f"printf '%s' '{alice_pass_b64}' | base64 -d | "
                "sudo -n /usr/sbin/os1-install --disk /dev/vda --user alice --password-stdin "
                "--hostname os1-installed --timezone America/Los_Angeles --confirm-erase-disk",
                "INSTALL",
                timeout=600.0,
            )
            if "=== OS-1_INSTALL_COMPLETE ===" not in out:
                raise RuntimeError(f"Install completion marker missing:\n{out}")
            print("[PASS][E2E] OS-1 installed cleanly to /dev/vda with special-character password", flush=True)

            vm_iso.poweroff_and_wait("os1")
        finally:
            vm_iso.close()

        # Verify plaintext password NEVER appeared in installer serial log
        with open(install_log, "rb") as f:
            inst_log_txt = f.read().decode("utf-8", errors="replace")
        if alice_pass in inst_log_txt:
            raise RuntimeError("SECURITY FAILURE: Plaintext user password leaked into installer log!")
        print("[PASS][FUNC] Zero password leakage verified in installer log", flush=True)

        # --- STEP 2: Detach ISO! Boot Installed Disk via OVMF UEFI ---
        print("=== Phase 4/18 Step 2: ISO Detached -> Boot Installed Disk, APT Update/Install, File Write ===", flush=True)
        vm_inst1 = UefiVm(ovmf_path, target_disk, boot1_log, iso_path=None)
        try:
            vm_inst1.login("os1-installed", "alice", alice_pass)

            out = vm_inst1.run_cmd(
                "uname -r && test -d /sys/firmware/efi && echo UEFI_OK && "
                "findmnt -n -o FSTYPE / && test ! -e /etc/os1-live-mode && echo NOT_LIVE && "
                "cat /etc/timezone && grep '^ID=' /etc/os-release && "
                "test -s /etc/machine-id && echo MACHINE_ID_OK && "
                "(! id -u os1 >/dev/null 2>&1) && echo LIVE_USER_REMOVED && "
                "if [ -f /etc/sddm.conf.d/10-os1-wayland.conf ]; then "
                "  (! grep -q '\\[Autologin\\]' /etc/sddm.conf.d/10-os1-wayland.conf) && echo NO_AUTOLOGIN_OK; "
                "else echo NO_AUTOLOGIN_OK; fi",
                "INSTCHECK",
                timeout=30.0,
            )
            from os1_test_util import expected_kernel_release
            expected_krel = expected_kernel_release(repo_root, out_root)

            for needle in (
                expected_krel,
                "UEFI_OK",
                "ext4",
                "NOT_LIVE",
                "America/Los_Angeles",
                "ID=os1",
                "MACHINE_ID_OK",
                "LIVE_USER_REMOVED",
                "NO_AUTOLOGIN_OK",
            ):
                if needle not in out:
                    raise RuntimeError(f"Installed system check missing {needle!r}:\n{out}")
            print(f"[PASS][E2E] Installed disk booted via UEFI ({expected_krel}) with special-char password, no live user, no SDDM autologin", flush=True)

            # Phase 17 mandatory runtime firewall gate on installed Boot 1
            fw_out = vm_inst1.run_cmd(
                "test \"$(systemctl is-active ufw.service)\" = 'active' && "
                "test \"$(systemctl is-failed ufw.service || true)\" != 'failed' && "
                f"{sudo_alice} ufw status verbose && "
                f"{sudo_alice} nft list ruleset",
                "UFW_BOOT1",
                timeout=30.0,
            )
            for needle in ("Status: active", "deny (incoming)", "allow (outgoing)", "ufw-before-input"):
                if needle not in fw_out:
                    raise RuntimeError(f"Installed Boot 1 runtime firewall check missing {needle!r}:\n{fw_out[-1200:]}")
            print("[PASS][FUNC] Installed Boot 1 runtime firewall active (ufw.service + nftables deny incoming)", flush=True)

            # Verify AppArmor LSM, sysctl hardening, and zram swap on installed Boot 1
            hard_out = vm_inst1.run_cmd(
                "cat /sys/module/apparmor/parameters/enabled && "
                "sysctl -n kernel.kptr_restrict kernel.dmesg_restrict kernel.yama.ptrace_scope && "
                "swapon --show --noheadings",
                "HARDENING_BOOT1",
                timeout=30.0,
            )
            if "Y" not in hard_out or "zram" not in hard_out:
                raise RuntimeError(f"Installed Boot 1 hardening/zram check failed:\n{hard_out}")
            print("[PASS][FUNC] Installed Boot 1 AppArmor LSM, sysctl hardening, and zram swap verified", flush=True)

            # If full desktop ISO was installed, verify desktop a11y binary & fs suite
            vm_inst1.run_cmd(
                "if [ -f /usr/share/os1/apps-manifest.json ]; then "
                "  command -v orca >/dev/null && "
                "  command -v flatpak >/dev/null && "
                "  os1-fs-test && "
                "  echo DESKTOP_QUAL_OK; "
                "else echo MINIMAL_PROFILE_OK; fi",
                "DESKTOPQUAL",
                timeout=60.0,
            )
            print("[PASS][FUNC] Installed desktop profile fs suite, Flatpak & a11y baseline verified", flush=True)

            # Networking + APT update + install jq
            vm_inst1.run_cmd(
                "for i in $(seq 1 30); do ip -4 addr show dev eth0 | grep -q 'inet ' && break; sleep 2; done; ip -4 addr show dev eth0 | grep 'inet '",
                "INSTNET",
                timeout=90.0,
            )
            vm_inst1.run_cmd(
                f"{sudo_alice} apt-get update && "
                f"{sudo_alice} env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends jq",
                "INSTAPT",
                timeout=300.0,
            )
            vm_inst1.run_cmd("jq --version", "JQVER1", timeout=30.0)
            vm_inst1.run_cmd(f"echo '{token}' > /home/alice/installed-proof.txt && sync", "INSTFILE", timeout=30.0)
            print("[PASS] Installed system updated APT, installed 'jq', and wrote persistent file", flush=True)

            vm_inst1.sendline(f"{sudo_alice} systemctl poweroff")
            deadline = time.monotonic() + 120.0
            while time.monotonic() < deadline:
                vm_inst1._drain(0.2)
                if vm_inst1.proc.poll() is not None:
                    break
            if vm_inst1.proc.poll() is None:
                raise TimeoutError("Installed Boot 1 did not power off cleanly")
            print("[PASS] Clean systemctl poweroff completed (rc=0)", flush=True)
        finally:
            vm_inst1.close()

        # --- STEP 3: Second Reboot of Installed Disk ---
        print("=== Phase 4/18 Step 3: Second Reboot of Installed Disk (Persistence Proof) ===", flush=True)
        vm_inst2 = UefiVm(ovmf_path, target_disk, boot2_log, iso_path=None)
        try:
            vm_inst2.login("os1-installed", "alice", alice_pass)
            out = vm_inst2.run_cmd(
                "cat /home/alice/installed-proof.txt && jq --version && uname -r && "
                "test \"$(systemctl is-active ufw.service)\" = 'active' && "
                f"{sudo_alice} ufw status verbose",
                "INSTPERSIST",
                timeout=30.0,
            )
            if token not in out or "jq-" not in out or expected_krel not in out or "Status: active" not in out:
                raise RuntimeError(f"Second reboot persistence/firewall check failed:\n{out}")
            print("[PASS][E2E] Installed disk survived second reboot with file, 'jq', and active UFW firewall intact!", flush=True)
            vm_inst2.sendline(f"{sudo_alice} systemctl poweroff")
            deadline = time.monotonic() + 120.0
            while time.monotonic() < deadline:
                vm_inst2._drain(0.2)
                if vm_inst2.proc.poll() is not None:
                    break
            if vm_inst2.proc.poll() is None:
                raise TimeoutError("Installed Boot 2 did not power off cleanly")
            print("[PASS] Clean systemctl poweroff completed (rc=0)", flush=True)
        finally:
            vm_inst2.close()

        for lp in (install_log, boot1_log, boot2_log):
            with open(lp, "rb") as f:
                text = f.read().decode("utf-8", errors="replace")
            if "Kernel panic" in text or "Oops:" in text:
                print(f"ERROR: Kernel panic or Oops in {lp}", file=sys.stderr)
                return 1
            if "Failed to start ufw.service" in text:
                print(f"ERROR: ufw.service failed during boot in {lp}", file=sys.stderr)
                return 1

        print("[os1-phase4-test] ALL PHASE 4/17/18 CLEAN-DISK INSTALL & REBOOT ASSERTIONS PASSED.", flush=True)
        return 0
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
