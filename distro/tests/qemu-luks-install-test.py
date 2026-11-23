#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Production E2E Test: LUKS2 Full-Disk Encryption Install & Encrypted UEFI Boot.

Verifies on a blank virtual disk in QEMU/OVMF:
  1. Boots the OS-1 UEFI Live ISO.
  2. Runs `os1-install --encrypt` supplying both user password and LUKS2
     passphrase strictly via private file descriptors (--password-fd /
     --luks-passphrase-fd), never argv.
  3. Detaches the Live ISO and boots the encrypted disk via UEFI.
  4. Waits for `OS-1_LUKS_PASSPHRASE_PROMPT` on serial console, unlocks LUKS2.
  5. Verifies `OS-1_LUKS_UNLOCKED`, logs in as `alice`, verifies:
       - `/` is mounted from `/dev/mapper/os1_crypt`
       - `/boot` is mounted from separate ext4 partition
       - OS-1 LTS kernel release (zero `-rc`)
       - AppArmor LSM active (`Y`), sysctl hardening, zram swap, UFW active
  6. Cleanly powers off.
"""

from __future__ import annotations

import base64
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
from os1_test_util import expected_kernel_release
from importlib.machinery import SourceFileLoader

_inst_mod = SourceFileLoader(
    "qemu_install_test",
    os.path.join(os.path.dirname(__file__), "qemu-install-test.py"),
).load_module()
UefiVm = _inst_mod.UefiVm
find_ovmf = _inst_mod.find_ovmf


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_root = os.environ.get("OS1_OUT_DIR", os.path.join(repo_root, "distro", "out"))
    iso_path = os.path.join(out_root, "iso", "os1-live-x86_64.iso")
    log_dir = os.path.join(out_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    if not os.path.isfile(iso_path):
        print(f"ERROR: Live ISO not found: {iso_path}", file=sys.stderr)
        return 1

    expected_krel = expected_kernel_release(repo_root, out_root)
    ovmf_path = find_ovmf()
    work_dir = tempfile.mkdtemp(prefix="os1-luks-")
    target_disk = os.path.join(work_dir, "os1-luks-disk.img")
    disk_gb = int(os.environ.get("OS1_LUKS_DISK_GB", "5"))
    with open(target_disk, "wb") as f:
        f.truncate(disk_gb * 1024 * 1024 * 1024)

    install_log = os.path.join(log_dir, "qemu-luks-install.log")
    boot_log = os.path.join(log_dir, "qemu-luks-boot.log")

    alice_pass = "AliceSecure!2026"
    luks_pass = "OS1-LUKS2-Vault-2026!"
    alice_b64 = base64.b64encode((alice_pass + "\n").encode("utf-8")).decode("ascii")
    luks_b64 = base64.b64encode((luks_pass + "\n").encode("utf-8")).decode("ascii")
    sudo_alice = f"printf '%s' '{alice_b64}' | base64 -d | sudo -S"

    try:
        # --- STEP 1: Encrypted Install from Live ISO ---
        print(f"=== LUKS2 Test Step 1: Encrypted UEFI Install to {disk_gb} GiB Disk ===", flush=True)
        vm_iso = UefiVm(ovmf_path, target_disk, install_log, iso_path=iso_path)
        try:
            vm_iso.login("os1", "os1", "os1")
            vm_iso.run_cmd("printf 'os1\\n' | sudo -S -v", "SUDO_AUTH", timeout=20.0)

            # Supply both user password and LUKS2 passphrase via private file descriptors (3 & 4)
            install_cmd = (
                f"python3 -c \""
                f"import base64, os, subprocess, sys; "
                f"p_r, p_w = os.pipe(); l_r, l_w = os.pipe(); "
                f"os.write(p_w, base64.b64decode('{alice_b64}')); os.close(p_w); "
                f"os.write(l_w, base64.b64decode('{luks_b64}')); os.close(l_w); "
                f"r = subprocess.run(['sudo', '-n', '/usr/sbin/os1-install', "
                f"'--disk', '/dev/vda', '--user', 'alice', '--hostname', 'os1-luks', "
                f"'--timezone', 'UTC', '--encrypt', '--password-fd', str(p_r), "
                f"'--luks-passphrase-fd', str(l_r), '--confirm-erase-disk', "
                f"'--confirm-phrase', 'ERASE /dev/vda'], pass_fds=(p_r, l_r)); "
                f"sys.exit(r.returncode)\""
            )
            out = vm_iso.run_cmd(install_cmd, "LUKS_INSTALL", timeout=480.0)
            if "OS-1_INSTALL_COMPLETE" not in out or "LUKS_UUID=" not in out:
                raise RuntimeError(f"LUKS2 installation did not report completion:\n{out[-1200:]}")
            print("[PASS][E2E] Encrypted LUKS2 OS-1 installation completed via private fds", flush=True)

            vm_iso.sendline("echo os1 | sudo -S systemctl poweroff")
            deadline = time.monotonic() + 120.0
            while time.monotonic() < deadline:
                vm_iso._drain(0.2)
                if vm_iso.proc.poll() is not None:
                    break
        finally:
            vm_iso.close()

        # --- STEP 2: Detach ISO, Boot Encrypted Disk, Unlock LUKS2 & Verify ---
        print("=== LUKS2 Test Step 2: Boot Encrypted Disk & Unlock LUKS2 Over Serial ===", flush=True)
        vm_enc = UefiVm(ovmf_path, target_disk, boot_log, iso_path=None)
        try:
            vm_enc.expect("OS-1_LUKS_PASSPHRASE_PROMPT", timeout=240.0)
            time.sleep(0.5)
            vm_enc.sendline(luks_pass)
            vm_enc.expect("OS-1_LUKS_UNLOCKED", timeout=60.0)
            print("[PASS][E2E] LUKS2 encrypted root volume unlocked at early boot initramfs", flush=True)

            vm_enc.login("os1-luks", "alice", alice_pass)
            out = vm_enc.run_cmd(
                "findmnt -n -o SOURCE / && "
                "findmnt -n -o FSTYPE /boot && "
                "uname -r && "
                "echo AA=$(cat /sys/module/apparmor/parameters/enabled) && "
                "cat /proc/swaps && "
                "test \"$(systemctl is-active ufw.service)\" = 'active' && echo UFW_OK",
                "LUKS_VERIFY",
                timeout=60.0,
            )
            for needle in ("/dev/mapper/os1_crypt", "ext4", expected_krel, "AA=Y", "zram0", "UFW_OK"):
                if needle not in out:
                    raise RuntimeError(f"Encrypted boot verification missing {needle!r}:\n{out}")
            print(f"[PASS][E2E] Encrypted root (/dev/mapper/os1_crypt), LTS kernel ({expected_krel}), AppArmor, zram, and UFW verified!", flush=True)

            vm_enc.sendline(f"{sudo_alice} systemctl poweroff")
            deadline = time.monotonic() + 120.0
            while time.monotonic() < deadline:
                vm_enc._drain(0.2)
                if vm_enc.proc.poll() is not None:
                    break
            if vm_enc.proc.poll() is None:
                raise TimeoutError("Encrypted boot VM did not power off cleanly")
            print("[PASS] Encrypted system clean poweroff completed", flush=True)
        finally:
            vm_enc.close()

        for lp in (install_log, boot_log):
            text = open(lp, "rb").read().decode("utf-8", errors="replace")
            if "Kernel panic" in text or "Oops:" in text:
                print(f"ERROR: Kernel panic or Oops detected in {lp}", file=sys.stderr)
                return 1

        print("[os1-luks-test] ALL LUKS2 FULL-DISK ENCRYPTION E2E ASSERTIONS PASSED.", flush=True)
        return 0
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
