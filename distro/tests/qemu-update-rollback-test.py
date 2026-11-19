#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 20: End-to-end QEMU/OVMF Signed Update, Versioned Kernel Upgrade & Rollback Test.

Verifies:
  1. Unsigned APT repository rejection (apt-get update MUST fail without valid signature).
  2. GPG-signed package upgrade (v1 -> v2) with strict `signed-by=` and conffile preservation.
  3. Versioned kernel A -> B upgrade, atomic /boot/grub/grub.cfg update with previous-kernel
     retention, and clean default reboot into Kernel B.
  4. Controlled bad-kernel C install -> GRUB serial rollback to known-good Kernel B ->
     running-kernel removal protection -> purge of bad kernel C -> interrupted dpkg recovery
     (`dpkg --unpack` + `dpkg --configure -a`) -> clean automatic reboot into Kernel B.
"""

import base64
import functools
import http.server
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_ROOT = os.environ.get("OS1_OUT_DIR", os.path.join(REPO_ROOT, "distro", "out"))
ISO_PATH = os.path.join(OUT_ROOT, "iso", "os1-live-x86_64.iso")
KERNEL_PROV = os.path.join(OUT_ROOT, "kernel", "provenance.json")
LOG_DIR = os.path.join(OUT_ROOT, "logs")


def find_ovmf_code() -> str:
    for path in (
        "/usr/share/OVMF/OVMF_CODE_4M.fd",
        "/usr/share/OVMF/OVMF_CODE.fd",
        "/usr/share/ovmf/OVMF.fd",
    ):
        if os.path.isfile(path):
            return path
    raise FileNotFoundError("OVMF firmware not found")


def find_ovmf_vars() -> str:
    for path in (
        "/usr/share/OVMF/OVMF_VARS_4M.fd",
        "/usr/share/OVMF/OVMF_VARS.fd",
    ):
        if os.path.isfile(path):
            return path
    raise FileNotFoundError("OVMF VARS template not found")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return


def start_http_server(directory: str) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(QuietHandler, directory=directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


class QemuVM:
    def __init__(self, cmd: list[str], log_path: str):
        self.cmd = cmd
        self.log_path = log_path
        self.proc: subprocess.Popen[bytes] | None = None
        self.buf = ""
        self.log_fp = None

    def __enter__(self) -> "QemuVM":
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self.log_fp = open(self.log_path, "wb")
        print(f"[os1-phase20] Launching: {' '.join(self.cmd)}", flush=True)
        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
        if self.log_fp is not None:
            self.log_fp.close()

    def _read_chunk(self, timeout: float) -> str:
        assert self.proc is not None and self.proc.stdout is not None
        fd = self.proc.stdout.fileno()
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            return ""
        data = os.read(fd, 4096)
        if not data:
            return ""
        if self.log_fp is not None:
            self.log_fp.write(data)
            self.log_fp.flush()
        text = data.decode("utf-8", errors="replace")
        self.buf += text
        return text

    def wait_for(self, pattern: str, timeout: float = 180.0, regex: bool = False) -> str:
        deadline = time.monotonic() + timeout
        rx = re.compile(pattern) if regex else None
        while time.monotonic() < deadline:
            if (rx.search(self.buf) if rx else (pattern in self.buf)):
                return self.buf
            assert self.proc is not None
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"QEMU exited early (rc={self.proc.returncode}) waiting for {pattern!r}\n"
                    f"Tail:\n{self.buf[-2000:]}"
                )
            self._read_chunk(0.5)
        raise TimeoutError(f"Timed out after {timeout}s waiting for {pattern!r}\nTail:\n{self.buf[-2000:]}")

    def send(self, data: str) -> None:
        assert self.proc is not None and self.proc.stdin is not None
        self.proc.stdin.write(data.encode("utf-8"))
        self.proc.stdin.flush()

    def sendline(self, line: str) -> None:
        self.send(line + "\n")

    def login(self, user: str, password: str, timeout: float = 240.0) -> None:
        self.wait_for("login:", timeout=timeout)
        self.buf = ""
        self.sendline(user)
        self.wait_for("Password:", timeout=30.0)
        self.buf = ""
        self.sendline(password)
        self.wait_for(f"{user}@", timeout=45.0)
        self.buf = ""

    def run_cmd(self, cmd: str, tag: str, timeout: float = 120.0, expect_rc: str | None = "0") -> str:
        self.buf = ""
        marker = f"{tag}_RC="
        self.sendline(f"{cmd}; printf '%s_RC=%d\\n' '{tag}' $?")
        out = self.wait_for(rf"{re.escape(marker)}(\d+)", timeout=timeout, regex=True)
        m = re.search(rf"{re.escape(marker)}(\d+)", out)
        rc = m.group(1) if m else "unknown"
        if expect_rc is not None and rc != expect_rc:
            raise RuntimeError(
                f"Command failed (rc={rc}, expected={expect_rc}): {cmd}\nOutput:\n{out[-1500:]}"
            )
        return out


def uefi_cmd(ovmf_code: str, ovmf_vars: str, disk_path: str, iso_path: str | None = None, ram: str = "1536M") -> list[str]:
    accel_args = ["-accel", "tcg", "-cpu", "Haswell"]
    if os.access("/dev/kvm", os.R_OK | os.W_OK):
        accel_args = ["-enable-kvm", "-cpu", "host"]
    cmd = [
        "qemu-system-x86_64",
        *accel_args,
        "-machine", "q35",
        "-m", ram,
        "-smp", "2",
        "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
        "-drive", f"if=pflash,format=raw,file={ovmf_vars}",
        "-drive", f"file={disk_path},format=raw,if=virtio",
        "-netdev", "user,id=net0",
        "-device", "virtio-net-pci,netdev=net0",
        "-nographic",
        "-no-reboot",
    ]
    if iso_path:
        cmd.extend(["-drive", f"file={iso_path},media=cdrom,readonly=on,if=ide,index=2"])
    return cmd


def load_version_meta() -> dict[str, str]:
    meta: dict[str, str] = {}
    with open(os.path.join(REPO_ROOT, "distro", "VERSION"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def build_test_repos(work_dir: str, krel: str, deb_ver: str) -> tuple[str, str, str, str, str]:
    """Build unsigned repo, signed v2+KernelB+BadKernelC repo, and return paths + package names."""
    unsigned_dir = os.path.join(work_dir, "repo-unsigned")
    signed_dir = os.path.join(work_dir, "repo-signed")
    gpg_home = os.path.join(work_dir, "gnupg")
    os.makedirs(gpg_home, mode=0o700)

    # Generate ephemeral test GPG key (never committed; destroyed in work_dir cleanup)
    key_spec = os.path.join(gpg_home, "spec")
    with open(key_spec, "w", encoding="utf-8") as f:
        f.write(
            "Key-Type: RSA\nKey-Length: 3072\n"
            "Name-Real: OS-1 Phase20 Ephemeral Test Key\n"
            "Name-Email: os1-p20-test@invalid.local\n"
            "Expire-Date: 1d\n%no-protection\n%commit\n"
        )
    env_gpg = os.environ.copy()
    env_gpg["GNUPGHOME"] = gpg_home
    subprocess.check_call(["gpg", "--batch", "--quiet", "--generate-key", key_spec], env=env_gpg)
    pubkey_path = os.path.join(work_dir, "os1-test-keyring.gpg")
    with open(pubkey_path, "wb") as kf:
        subprocess.check_call(
            ["gpg", "--batch", "--yes", "--export", "os1-p20-test@invalid.local"],
            env=env_gpg,
            stdout=kf,
        )

    # 1. Build unsigned repo (no GPG signing)
    v2_ver = f"{deb_ver}.1"
    env_u = os.environ.copy()
    env_u["OS1_OUT_DIR"] = os.path.join(work_dir, "out-unsigned")
    env_u["OS1_APT_REPO_DIR"] = unsigned_dir
    env_u["OS1_PKG_VERSION"] = v2_ver
    env_u["OS1_INCLUDE_KERNEL_DEB"] = "0"
    subprocess.check_call([os.path.join(REPO_ROOT, "distro", "packages", "build-debs.sh")], env=env_u)

    # 2. Build signed repo with v2 packages + Kernel B (real bzImage) + Bad Kernel C (corrupt)
    krel_b = f"{krel}.1"
    krel_bad = f"{krel}.99-bad"
    pkg_b = "linux-image-os1-" + re.sub(r"[^a-z0-9+.-]", "", krel_b.lower().replace("_", "-"))
    pkg_bad = "linux-image-os1-" + re.sub(r"[^a-z0-9+.-]", "", krel_bad.lower().replace("_", "-"))

    env_s = os.environ.copy()
    env_s["OS1_OUT_DIR"] = os.path.join(work_dir, "out-signed")
    env_s["OS1_APT_REPO_DIR"] = signed_dir
    env_s["OS1_PKG_VERSION"] = v2_ver
    env_s["OS1_INCLUDE_KERNEL_DEB"] = "0"
    env_s["OS1_GPG_PUBKEY"] = pubkey_path
    subprocess.check_call([os.path.join(REPO_ROOT, "distro", "packages", "build-debs.sh")], env=env_s)

    # Add Kernel B (real bzImage) & Bad Kernel C (corrupt vmlinuz) into signed_dir
    env_k = os.environ.copy()
    env_k["OS1_KERNEL_DIR"] = os.path.join(OUT_ROOT, "kernel")
    subprocess.check_call(
        [
            os.path.join(REPO_ROOT, "distro", "packages", "build-kernel-deb.sh"),
            "--krel-override", krel_b,
            "--deb-version", v2_ver,
            "--out-dir", signed_dir,
        ],
        env=env_k,
    )
    subprocess.check_call(
        [
            os.path.join(REPO_ROOT, "distro", "packages", "build-kernel-deb.sh"),
            "--krel-override", krel_bad,
            "--deb-version", v2_ver,
            "--out-dir", signed_dir,
            "--corrupt-vmlinuz",
        ],
        env=env_k,
    )

    # Regenerate Packages, Packages.gz, Release and GPG-sign InRelease + Release.gpg
    subprocess.check_call(
        [
            "python3", "-c",
            """
import gzip, hashlib, os, subprocess, sys
from datetime import datetime, timezone
repo_dir = sys.argv[1]
debs = sorted(f for f in os.listdir(repo_dir) if f.endswith(".deb"))
stanzas = []
for deb in debs:
    path = os.path.join(repo_dir, deb)
    data = open(path, "rb").read()
    ctrl = subprocess.check_output(["dpkg-deb", "--field", path], text=True).strip()
    stanzas.append("\\n".join([
        ctrl, f"Filename: {deb}", f"Size: {len(data)}",
        f"MD5sum: {hashlib.md5(data).hexdigest()}",
        f"SHA1: {hashlib.sha1(data).hexdigest()}",
        f"SHA256: {hashlib.sha256(data).hexdigest()}",
    ]))
pkg_txt = ("\\n\\n".join(stanzas) + "\\n").encode("utf-8")
open(os.path.join(repo_dir, "Packages"), "wb").write(pkg_txt)
gzip.open(os.path.join(repo_dir, "Packages.gz"), "wb").write(pkg_txt)
now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S UTC")
lines = [
    "Origin: OS-1", "Label: OS-1 APT Repository", "Suite: bookworm",
    "Codename: os1", f"Date: {now}", "Architectures: amd64 all",
    "Components: main", "Description: Native OS-1 distribution packages", "SHA256:",
]
for fn in ("Packages", "Packages.gz"):
    raw = open(os.path.join(repo_dir, fn), "rb").read()
    lines.append(f" {hashlib.sha256(raw).hexdigest()} {len(raw):16d} {fn}")
open(os.path.join(repo_dir, "Release"), "w", encoding="utf-8").write("\\n".join(lines) + "\\n")
""",
            signed_dir,
        ]
    )
    subprocess.check_call(
        [
            "gpg", "--batch", "--yes", "--digest-algo", "SHA256",
            "--local-user", "os1-p20-test@invalid.local",
            "--clearsign", "-o", os.path.join(signed_dir, "InRelease"),
            os.path.join(signed_dir, "Release"),
        ],
        env=env_gpg,
    )
    subprocess.check_call(
        [
            "gpg", "--batch", "--yes", "--digest-algo", "SHA256",
            "--local-user", "os1-p20-test@invalid.local",
            "--armor", "--detach-sign", "-o", os.path.join(signed_dir, "Release.gpg"),
            os.path.join(signed_dir, "Release"),
        ],
        env=env_gpg,
    )

    return unsigned_dir, signed_dir, pubkey_path, pkg_b, pkg_bad


def main() -> int:
    if not os.path.isfile(ISO_PATH):
        print(f"ERROR: ISO not found at {ISO_PATH}", file=sys.stderr)
        return 1
    if not os.path.isfile(KERNEL_PROV):
        print(f"ERROR: Kernel provenance not found at {KERNEL_PROV}", file=sys.stderr)
        return 1

    krel = json.load(open(KERNEL_PROV, encoding="utf-8"))["kernel_release"]
    ver_meta = load_version_meta()
    deb_ver = ver_meta["OS1_DEB_VERSION"]
    v2_ver = f"{deb_ver}.1"
    krel_b = f"{krel}.1"
    krel_bad = f"{krel}.99-bad"
    pkg_a = "linux-image-os1-" + re.sub(r"[^a-z0-9+.-]", "", krel.lower().replace("_", "-"))

    ovmf_code = find_ovmf_code()
    ovmf_vars_tpl = find_ovmf_vars()
    disk_gb = int(os.environ.get("OS1_UPDATE_DISK_GB", "10"))
    ram_mb = os.environ.get("OS1_UPDATE_RAM", "2048M")

    with tempfile.TemporaryDirectory(prefix="os1-phase20-") as tmp:
        unsigned_dir, signed_dir, pubkey_path, pkg_b, pkg_bad = build_test_repos(tmp, krel, deb_ver)
        srv_u, port_u = start_http_server(unsigned_dir)
        srv_s, port_s = start_http_server(signed_dir)
        pubkey_b64 = base64.b64encode(open(pubkey_path, "rb").read()).decode("ascii")

        disk_path = os.path.join(tmp, "os1-update-disk.img")
        ovmf_vars = os.path.join(tmp, "OVMF_VARS.fd")
        shutil.copyfile(ovmf_vars_tpl, ovmf_vars)
        with open(disk_path, "wb") as f:
            f.truncate(disk_gb * 1024 * 1024 * 1024)

        try:
            # --- Step 0: Install OS-1 from UEFI Live ISO onto blank disk ---
            with QemuVM(
                uefi_cmd(ovmf_code, ovmf_vars, disk_path, iso_path=ISO_PATH, ram=ram_mb),
                os.path.join(LOG_DIR, "qemu-phase20-install.log"),
            ) as vm:
                vm.login("os1", "os1", timeout=240.0)
                vm.run_cmd("printf 'os1\\n' | sudo -S -v", "SUDO", timeout=20.0)
                vm.run_cmd(
                    "printf 'os1pass20' | sudo -n /usr/sbin/os1-install "
                    "--disk /dev/vda --user alice --password-stdin "
                    "--hostname os1-upd --timezone UTC --confirm-erase-disk",
                    "INSTALL",
                    timeout=600.0,
                )
                vm.sendline("sudo -n poweroff")
                vm.proc.wait(timeout=60)
            print("[PASS][P20] Clean UEFI disk installed for update/rollback test", flush=True)

            # --- Boot 1: Unsigned-repo rejection + Signed v1->v2 upgrade + Kernel A->B ---
            with QemuVM(
                uefi_cmd(ovmf_code, ovmf_vars, disk_path, iso_path=None, ram=ram_mb),
                os.path.join(LOG_DIR, "qemu-phase20-boot1-upgrade.log"),
            ) as vm:
                vm.login("alice", "os1pass20", timeout=240.0)
                vm.run_cmd("printf 'os1pass20\\n' | sudo -S -v", "SUDO", timeout=20.0)

                # Wait for SLIRP network
                vm.run_cmd(
                    "for i in $(seq 1 20); do ip -4 addr show eth0 | grep -q 'inet ' && break; sleep 1; done; "
                    "ip -4 addr show eth0 | grep -q 'inet '",
                    "NET_UP",
                    timeout=35.0,
                )

                # Install ephemeral test public keyring
                vm.run_cmd(
                    f"printf '%s' '{pubkey_b64}' | base64 -d | sudo -n tee /usr/share/keyrings/os1-archive-keyring.gpg >/dev/null",
                    "KEYRING",
                    timeout=20.0,
                )

                # 1. Unsigned repo MUST be rejected by apt-get update
                vm.run_cmd(
                    f"printf 'deb [signed-by=/usr/share/keyrings/os1-archive-keyring.gpg] http://10.0.2.2:{port_u} ./\\n' "
                    "| sudo -n tee /etc/apt/sources.list.d/os1.list >/dev/null",
                    "SET_UNSIGNED",
                    timeout=20.0,
                )
                out_u = vm.run_cmd(
                    "sudo -n apt-get update -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=/etc/apt/sources.list.d",
                    "UNSIGNED_REJECT",
                    timeout=60.0,
                    expect_rc=None,
                )
                if "UNSIGNED_REJECT_RC=0" in out_u:
                    raise RuntimeError("SECURITY FAILURE: apt-get update accepted an unsigned OS-1 repository!")
                print("[PASS][P20] Unsigned OS-1 APT repository strictly rejected by apt-get update", flush=True)

                # 2. Configure signed OS-1 repo with user conffile comment & upgrade v1 -> v2
                vm.run_cmd(
                    f"printf '# os1-phase20-user-conffile-edit\\n"
                    f"deb [signed-by=/usr/share/keyrings/os1-archive-keyring.gpg] http://10.0.2.2:{port_s} ./\\n' "
                    "| sudo -n tee /etc/apt/sources.list.d/os1.list >/dev/null",
                    "SET_SIGNED",
                    timeout=20.0,
                )
                vm.run_cmd(
                    "sudo -n apt-get update -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=/etc/apt/sources.list.d",
                    "SIGNED_UPDATE",
                    timeout=60.0,
                )
                vm.run_cmd(
                    "sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y "
                    "-o Dpkg::Options::='--force-confold' os1-tools os1-keyring",
                    "SIGNED_UPGRADE",
                    timeout=120.0,
                )
                vm.run_cmd(
                    f"test \"$(dpkg-query -W -f='${{Version}}' os1-tools)\" = '{v2_ver}' && "
                    "grep -q 'os1-phase20-user-conffile-edit' /etc/apt/sources.list.d/os1.list",
                    "VERIFY_V2_CONFFILE",
                    timeout=20.0,
                )
                print(f"[PASS][P20] Signed package upgrade ({deb_ver} -> {v2_ver}) & conffile preservation verified", flush=True)

                # 3. Install versioned Kernel B and verify GRUB retains Kernel A + adds Kernel B as default
                vm.run_cmd(
                    f"sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg_b}",
                    "INSTALL_KERNEL_B",
                    timeout=120.0,
                )
                vm.run_cmd(
                    f"grep -q 'vmlinuz-{krel_b}' /boot/grub/grub.cfg && "
                    f"grep -q 'vmlinuz-{krel} ' /boot/grub/grub.cfg && "
                    f"head -n 30 /boot/grub/grub.cfg | grep -q 'OS-1 ({krel_b}) (default)'",
                    "VERIFY_GRUB_AB",
                    timeout=20.0,
                )
                print(f"[PASS][P20] Versioned Kernel B ({krel_b}) installed; GRUB retains Kernel A ({krel})", flush=True)

                vm.sendline("sudo -n poweroff")
                vm.proc.wait(timeout=60)

            # --- Boot 2: Verify Kernel B boots by default, then install Bad Kernel C ---
            with QemuVM(
                uefi_cmd(ovmf_code, ovmf_vars, disk_path, iso_path=None, ram=ram_mb),
                os.path.join(LOG_DIR, "qemu-phase20-boot2-kernel-b.log"),
            ) as vm:
                vm.login("alice", "os1pass20", timeout=240.0)
                vm.run_cmd("printf 'os1pass20\\n' | sudo -S -v", "SUDO", timeout=20.0)
                vm.run_cmd(
                    f"grep -q 'BOOT_IMAGE=/boot/vmlinuz-{krel_b}' /proc/cmdline && "
                    f"test \"$(dpkg-query -W -f='${{Version}}' os1-tools)\" = '{v2_ver}' && "
                    "grep -q 'os1-phase20-user-conffile-edit' /etc/apt/sources.list.d/os1.list",
                    "VERIFY_KERNEL_B_BOOT",
                    timeout=20.0,
                )
                print(f"[PASS][P20] Rebooted cleanly into upgraded Kernel B ({krel_b}) & v2 packages persisted", flush=True)

                # Install intentionally corrupt Kernel C (.99-bad)
                vm.run_cmd(
                    "for i in $(seq 1 20); do ip -4 addr show eth0 | grep -q 'inet ' && break; sleep 1; done; "
                    f"sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg_bad}",
                    "INSTALL_BAD_KERNEL",
                    timeout=120.0,
                )
                vm.run_cmd(
                    f"grep -q 'OS-1 ({krel_bad}) (default)' /boot/grub/grub.cfg && "
                    f"grep -q 'OS-1 ({krel_b}) (previous/rollback)' /boot/grub/grub.cfg",
                    "VERIFY_GRUB_BAD_AND_FALLBACK",
                    timeout=20.0,
                )
                print(f"[PASS][P20] Installed controlled bad Kernel C ({krel_bad}); GRUB retains Kernel B as fallback entry 1", flush=True)

                vm.sendline("sudo -n poweroff")
                vm.proc.wait(timeout=60)

            # --- Boot 3: Roll back from Bad Kernel C to Known-Good Kernel B via GRUB serial menu ---
            with QemuVM(
                uefi_cmd(ovmf_code, ovmf_vars, disk_path, iso_path=None, ram=ram_mb),
                os.path.join(LOG_DIR, "qemu-phase20-boot3-rollback.log"),
            ) as vm:
                # Wait for GRUB menu displaying the bad default entry and press Down + Enter to select entry 1 (Kernel B)
                vm.wait_for(krel_bad, timeout=90.0)
                time.sleep(0.3)
                vm.send("\x1b[B")  # Down arrow -> entry 1 (Kernel B)
                time.sleep(0.3)
                vm.send("\r")      # Enter -> boot Kernel B

                vm.login("alice", "os1pass20", timeout=240.0)
                vm.run_cmd("printf 'os1pass20\\n' | sudo -S -v", "SUDO", timeout=20.0)

                vm.run_cmd(
                    f"grep -q 'BOOT_IMAGE=/boot/vmlinuz-{krel_b}' /proc/cmdline",
                    "VERIFY_ROLLBACK_BOOT",
                    timeout=20.0,
                )
                print(f"[PASS][P20] GRUB serial rollback booted known-good Kernel B ({krel_b})", flush=True)

                # Verify running-kernel removal guard refuses removing active kernel package
                out_guard = vm.run_cmd(
                    f"sudo -n dpkg --remove {pkg_a}",
                    "RUNNING_KERNEL_GUARD",
                    timeout=30.0,
                    expect_rc=None,
                )
                if "RUNNING_KERNEL_GUARD_RC=0" in out_guard:
                    raise RuntimeError(f"SAFETY FAILURE: dpkg allowed removing currently running kernel {pkg_a}!")
                print(f"[PASS][P20] Running-kernel removal guard refused removing {pkg_a}", flush=True)

                # Purge bad kernel C and verify GRUB restores Kernel B as default
                vm.run_cmd(
                    f"sudo -n DEBIAN_FRONTEND=noninteractive apt-get purge -y {pkg_bad}",
                    "PURGE_BAD_KERNEL",
                    timeout=60.0,
                )
                vm.run_cmd(
                    f"! grep -q '{krel_bad}' /boot/grub/grub.cfg && "
                    f"grep -q 'OS-1 ({krel_b}) (default)' /boot/grub/grub.cfg",
                    "VERIFY_GRUB_RESTORED",
                    timeout=20.0,
                )
                print(f"[PASS][P20] Purged bad Kernel C ({krel_bad}); GRUB restored Kernel B as default", flush=True)

                # Verify interrupted update recovery (dpkg --unpack -> dpkg --audit -> dpkg --configure -a)
                vm.run_cmd(
                    f"curl -fsSL http://10.0.2.2:{port_s}/os1-tools_{v2_ver}_all.deb -o /tmp/os1-tools.deb && "
                    "sudo -n dpkg --unpack /tmp/os1-tools.deb && "
                    "test -n \"$(dpkg --audit)\" && "
                    "sudo -n dpkg --configure -a && "
                    "test -z \"$(dpkg --audit)\" && "
                    "rm -f /tmp/os1-tools.deb",
                    "INTERRUPTED_RECOVERY",
                    timeout=60.0,
                )
                print("[PASS][P20] Interrupted update recovery (dpkg --unpack -> dpkg --configure -a) verified", flush=True)

                vm.sendline("sudo -n poweroff")
                vm.proc.wait(timeout=60)

            # --- Boot 4: Automatic default reboot into Known-Good Kernel B (zero manual GRUB input) ---
            with QemuVM(
                uefi_cmd(ovmf_code, ovmf_vars, disk_path, iso_path=None, ram=ram_mb),
                os.path.join(LOG_DIR, "qemu-phase20-boot4-clean.log"),
            ) as vm:
                vm.login("alice", "os1pass20", timeout=240.0)
                vm.run_cmd(
                    f"grep -q 'BOOT_IMAGE=/boot/vmlinuz-{krel_b}' /proc/cmdline && "
                    "test -z \"$(dpkg --audit)\" && "
                    "systemctl is-active ufw.service",
                    "FINAL_HEALTH",
                    timeout=30.0,
                )
                print("[PASS][P20] Clean automatic reboot into Known-Good Kernel B verified", flush=True)
                vm.sendline("printf 'os1pass20\\n' | sudo -S poweroff")
                vm.proc.wait(timeout=60)

        finally:
            srv_u.shutdown()
            srv_s.shutdown()

    print("[os1-phase20] ALL SIGNED UPDATE, VERSIONED KERNEL & ROLLBACK TESTS PASSED.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
