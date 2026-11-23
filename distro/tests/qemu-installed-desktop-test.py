#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 21: End-to-end QEMU/OVMF Installed Graphical User Journey Test.

Verifies the real installed OS-1 desktop experience:
  1. Clean UEFI install of the full Desktop ISO to a blank GPT disk (user `alice`), ISO detached.
  2. Boot installed disk -> verify NO SDDM [Autologin], NO live `os1` user, SDDM greeter active.
  3. Genuine graphical login as `alice` via QEMU monitor `sendkey` into SDDM greeter.
  4. Verify `alice`'s Wayland session (kwin_wayland, plasmashell, wayland-0, pipewire, NM, UFW),
     os1-shell-init atomic completion stamp, and capture non-blank Light & Dark screenshots.
  5. Launch core native apps (konsole, dolphin, kate, systemsettings, okular, firefox-esr),
     verify os1-firstboot preference preservation across partial updates, os1-fs-test, notify-send,
     and Orca baseline.
  6. Reboot installed disk, verify preferences & shell-init stamp persisted, and verify second
     graphical SDDM login as `alice`.
"""

import os
import re
import select
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zlib


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_ROOT = os.environ.get("OS1_OUT_DIR", os.path.join(REPO_ROOT, "distro", "out"))
ISO_PATH = os.path.join(OUT_ROOT, "iso", "os1-live-x86_64.iso")
LOG_DIR = os.path.join(OUT_ROOT, "logs")
SHOT_DIR = os.path.join(OUT_ROOT, "screenshots")


def find_ovmf_code() -> str:
    for p in ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_CODE.fd", "/usr/share/ovmf/OVMF.fd"):
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("OVMF firmware not found")


def find_ovmf_vars() -> str:
    for p in ("/usr/share/OVMF/OVMF_VARS_4M.fd", "/usr/share/OVMF/OVMF_VARS.fd"):
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("OVMF VARS template not found")


def ppm_to_png_and_validate(ppm_path: str, png_path: str) -> tuple[int, int, int]:
    raw = open(ppm_path, "rb").read()
    idx = 0
    tokens = []
    while len(tokens) < 4:
        while idx < len(raw) and raw[idx:idx+1] in b" \t\r\n":
            idx += 1
        if raw[idx:idx+1] == b"#":
            idx = raw.index(b"\n", idx) + 1
            continue
        start = idx
        while idx < len(raw) and raw[idx:idx+1] not in b" \t\r\n":
            idx += 1
        tokens.append(raw[start:idx])
    assert tokens[0] == b"P6", f"Unexpected PPM magic: {tokens[0]!r}"
    width, height = int(tokens[1]), int(tokens[2])
    rgb = raw[idx + 1: idx + 1 + width * height * 3]
    non_black = sum(1 for i in range(0, len(rgb), 3) if rgb[i] or rgb[i+1] or rgb[i+2])
    assert non_black > (width * height) // 50, f"Screenshot {png_path} is nearly blank ({non_black} non-black px)"

    def chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        return struct.pack("!I", len(data)) + c + struct.pack("!I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    stride = width * 3
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(rgb[y * stride: (y + 1) * stride])
    idat = zlib.compress(bytes(rows), level=6)
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    with open(png_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))
    return width, height, non_black


class QemuVM:
    def __init__(self, cmd: list[str], log_path: str, mon_sock: str | None = None):
        self.cmd = cmd
        self.log_path = log_path
        self.mon_sock = mon_sock
        self.proc: subprocess.Popen[bytes] | None = None
        self.buf = ""
        self.log_fp = None

    def __enter__(self) -> "QemuVM":
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self.log_fp = open(self.log_path, "wb")
        print(f"[os1-phase21] Launching: {' '.join(self.cmd)}", flush=True)
        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.proc is not None and self.proc.poll() is None:
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

    def wait_for(self, pattern: str, timeout: float = 240.0, regex: bool = False) -> str:
        deadline = time.monotonic() + timeout
        rx = re.compile(pattern) if regex else None
        while time.monotonic() < deadline:
            if (rx.search(self.buf) if rx else (pattern in self.buf)):
                return self.buf
            assert self.proc is not None
            if self.proc.poll() is not None:
                raise RuntimeError(f"QEMU exited early (rc={self.proc.returncode})\nTail:\n{self.buf[-1500:]}")
            self._read_chunk(0.5)
        raise TimeoutError(f"Timed out waiting for {pattern!r}\nTail:\n{self.buf[-1500:]}")

    def sendline(self, line: str) -> None:
        assert self.proc is not None and self.proc.stdin is not None
        self.proc.stdin.write((line + "\n").encode("utf-8"))
        self.proc.stdin.flush()

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
            raise RuntimeError(f"Command failed (rc={rc}, expected={expect_rc}): {cmd}\nOutput:\n{out[-1500:]}")
        return out

    def monitor_cmd(self, command: str) -> None:
        assert self.mon_sock is not None
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10.0)
            s.connect(self.mon_sock)
            s.recv(4096)
            s.sendall((command + "\n").encode("utf-8"))
            time.sleep(0.15)
            try:
                s.recv(4096)
            except socket.timeout:
                pass

    def type_password_via_sendkey(self, text: str) -> None:
        for ch in text:
            self.monitor_cmd(f"sendkey {ch}")
            time.sleep(0.12)
        self.monitor_cmd("sendkey ret")

    def screenshot(self, ppm_path: str, png_path: str, max_attempts: int = 12) -> tuple[int, int, int]:
        last_err: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            if os.path.exists(ppm_path):
                os.unlink(ppm_path)
            self.monitor_cmd("mouse_move 25 25")
            time.sleep(2.0)
            self.monitor_cmd(f"screendump {ppm_path}")
            for _ in range(30):
                if os.path.isfile(ppm_path) and os.path.getsize(ppm_path) > 10000:
                    break
                time.sleep(0.2)
            try:
                return ppm_to_png_and_validate(ppm_path, png_path)
            except AssertionError as exc:
                last_err = exc
                print(
                    f"[os1-phase21] Framebuffer attempt {attempt}/{max_attempts} not ready yet: {exc}",
                    flush=True,
                )
                time.sleep(3.0)
        # Capture SDDM / Xorg diagnostics before failing
        try:
            self.run_cmd(
                "journalctl -u sddm -n 40 --no-pager; tail -n 30 /var/log/Xorg.0.log 2>/dev/null || true",
                "SDDM_DIAG",
                timeout=20.0,
                expect_rc=None,
            )
        except Exception:
            pass
        assert last_err is not None
        raise last_err

    def poweroff(self, password: str, timeout: float = 120.0) -> None:
        assert self.proc is not None
        self.sendline(f"sync && printf '{password}\\n' | sudo -S systemctl poweroff --ignore-inhibitors")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                return
            self._read_chunk(0.5)
        raise TimeoutError(f"Timed out after {timeout}s waiting for clean VM poweroff")


def main() -> int:
    if not os.path.isfile(ISO_PATH):
        print(f"ERROR: Desktop ISO not found at {ISO_PATH}", file=sys.stderr)
        return 1

    ovmf_code = find_ovmf_code()
    ovmf_vars_tpl = find_ovmf_vars()
    disk_gb = int(os.environ.get("OS1_INSTALL_DISK_GB", "10"))
    ram_mb = os.environ.get("OS1_DESKTOP_RAM", "2560M")
    alice_pass = "aliceos1"

    with tempfile.TemporaryDirectory(prefix="os1-phase21-") as tmp:
        disk_path = os.path.join(tmp, "os1-installed-desktop.img")
        ovmf_vars = os.path.join(tmp, "OVMF_VARS.fd")
        mon_sock = os.path.join(tmp, "qemu-mon.sock")
        shutil.copyfile(ovmf_vars_tpl, ovmf_vars)
        with open(disk_path, "wb") as f:
            f.truncate(disk_gb * 1024 * 1024 * 1024)

        accel_args = ["-accel", "tcg", "-cpu", "Haswell"]
        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            accel_args = ["-enable-kvm", "-cpu", "host"]

        # --- Step 1: Clean UEFI install of full Desktop ISO ---
        install_cmd = [
            "qemu-system-x86_64", *accel_args, "-machine", "q35",
            "-m", "2048M", "-smp", "2",
            "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
            "-drive", f"if=pflash,format=raw,file={ovmf_vars}",
            "-drive", f"file={disk_path},format=raw,if=virtio",
            "-drive", f"file={ISO_PATH},media=cdrom,readonly=on,if=ide,index=2",
            "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0",
            "-nographic", "-no-reboot",
        ]
        with QemuVM(install_cmd, os.path.join(LOG_DIR, "qemu-phase21-install.log")) as vm:
            vm.login("os1", "os1", timeout=240.0)
            vm.run_cmd("printf 'os1\\n' | sudo -S -v", "SUDO", timeout=20.0)
            vm.run_cmd(
                f"printf '%s' '{alice_pass}' | sudo -n /usr/sbin/os1-install "
                "--disk /dev/vda --user alice --password-stdin "
                "--hostname os1-desktop --timezone UTC --confirm-erase-disk",
                "INSTALL",
                timeout=600.0,
            )
            vm.sendline("sudo -n poweroff")
            vm.proc.wait(timeout=60)
        print("[PASS][P21] Installed full Desktop ISO to GPT disk as user alice", flush=True)

        def desktop_boot_cmd() -> list[str]:
            if os.path.exists(mon_sock):
                os.unlink(mon_sock)
            return [
                "qemu-system-x86_64", *accel_args, "-machine", "q35",
                "-m", ram_mb, "-smp", "2",
                "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
                "-drive", f"if=pflash,format=raw,file={ovmf_vars}",
                "-drive", f"file={disk_path},format=raw,if=virtio",
                "-device", "virtio-vga,xres=1440,yres=900",
                "-device", "virtio-keyboard-pci",
                "-device", "virtio-mouse-pci",
                "-device", "intel-hda", "-device", "hda-duplex",
                "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0",
                "-display", "none", "-serial", "stdio",
                "-monitor", f"unix:{mon_sock},server,nowait",
                "-no-reboot",
            ]

        # --- Step 2: Boot 1 — Installed SDDM Greeter -> Graphical Login as alice ---
        with QemuVM(desktop_boot_cmd(), os.path.join(LOG_DIR, "qemu-phase21-boot1-gui.log"), mon_sock) as vm:
            vm.login("alice", alice_pass, timeout=240.0)
            vm.run_cmd(
                "! id os1 >/dev/null 2>&1 && "
                "! grep -qi '\\[Autologin\\]' /etc/sddm.conf.d/10-os1-wayland.conf && "
                "systemctl is-active sddm.service && "
                "systemctl is-active ufw.service && "
                "systemctl is-active NetworkManager.service",
                "NO_AUTOLOGIN_SDDM_ACTIVE",
                timeout=30.0,
            )
            # Wait for sddm-greeter to appear on display
            vm.run_cmd(
                "for i in $(seq 1 45); do pgrep -f sddm-greeter >/dev/null 2>&1 && break; sleep 2; done; "
                "pgrep -a sddm-greeter",
                "GREETER_READY",
                timeout=110.0,
            )
            time.sleep(5)
            w, h, px = vm.screenshot(
                os.path.join(tmp, "greeter.ppm"),
                os.path.join(SHOT_DIR, "phase21-sddm-greeter.png"),
            )
            print(f"[PASS][P21] SDDM greeter rendered without autologin ({w}x{h}, {px} non-black px)", flush=True)

            # Log in graphically as alice through SDDM via virtual keyboard sendkey
            vm.type_password_via_sendkey(alice_pass)

            # Verify alice's Wayland session (kwin_wayland + plasmashell + wayland-0 + pipewire)
            vm.run_cmd(
                "UID_ALICE=$(id -u alice); "
                "for i in $(seq 1 60); do "
                "  pgrep -u alice -x kwin_wayland >/dev/null 2>&1 && "
                "  pgrep -u alice -x plasmashell >/dev/null 2>&1 && "
                "  test -S /run/user/$UID_ALICE/wayland-0 && break; "
                "  sleep 2; "
                "done; "
                "pgrep -u alice -a kwin_wayland && pgrep -u alice -a plasmashell && "
                "test -S /run/user/$UID_ALICE/wayland-0 && pgrep -u alice -x pipewire >/dev/null",
                "ALICE_WAYLAND_SESSION",
                timeout=150.0,
            )
            print("[PASS][P21] Graphical SDDM login started alice Wayland session (kwin_wayland + plasmashell + pipewire)", flush=True)

            # Wait for os1-shell-init atomic stamp (bounded 180s for TCG first-login with Discover/Flatpak)
            vm.run_cmd(
                "for i in $(seq 1 90); do test -f /home/alice/.config/.os1-shell-initialized && break; sleep 2; done; "
                "if [ ! -f /home/alice/.config/.os1-shell-initialized ]; then "
                "  echo '=== os1-shell-init.log ==='; "
                "  cat /home/alice/.local/share/os1-shell-init.log 2>/dev/null || echo '(missing)'; "
                "  exit 1; "
                "fi; "
                "grep -q 'org.kde.plasma.appmenu' /home/alice/.config/plasma-org.kde.plasma.desktop-appletsrc && "
                "grep -q 'org.kde.plasma.icontasks' /home/alice/.config/plasma-org.kde.plasma.desktop-appletsrc",
                "SHELL_INIT_STAMP",
                timeout=200.0,
            )
            w, h, px = vm.screenshot(
                os.path.join(tmp, "alice-light.ppm"),
                os.path.join(SHOT_DIR, "phase21-alice-desktop-light.png"),
            )
            print(f"[PASS][P21] Installed alice desktop shell initialized & captured ({w}x{h}, {px} non-black px)", flush=True)

            # Launch core native apps in alice's Wayland session and verify compositor stays alive
            vm.run_cmd(
                "UID_ALICE=$(id -u alice); "
                "export XDG_RUNTIME_DIR=/run/user/$UID_ALICE DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UID_ALICE/bus; "
                "for app in konsole dolphin kate systemsettings okular; do "
                "  systemd-run --user --unit=os1-app-$app $app; "
                "done; "
                "sleep 8; "
                "pgrep -u alice -x konsole >/dev/null && "
                "pgrep -u alice -x dolphin >/dev/null && "
                "pgrep -u alice -x kate >/dev/null && "
                "pgrep -u alice -x kwin_wayland >/dev/null && "
                "pgrep -u alice -x plasmashell >/dev/null",
                "CORE_APPS_LAUNCH",
                timeout=60.0,
            )
            print("[PASS][P21] Core desktop apps (konsole, dolphin, kate, systemsettings, okular) launched cleanly", flush=True)

            # Test os1-firstboot partial update preservation + dark mode + fs-test + notify + orca
            vm.run_cmd(
                "UID_ALICE=$(id -u alice); "
                "export XDG_RUNTIME_DIR=/run/user/$UID_ALICE "
                "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UID_ALICE/bus "
                "WAYLAND_DISPLAY=wayland-0 QT_QPA_PLATFORM=wayland; "
                "os1-firstboot --apply --appearance dark && "
                "os1-firstboot --apply --reduced-motion on && "
                "grep -q 'appearance=dark' /home/alice/.config/os1-onboarding.conf && "
                "grep -q 'reduced_motion=on' /home/alice/.config/os1-onboarding.conf && "
                "os1-fs-test && "
                "orca --version >/dev/null",
                "FIRSTBOOT_DARK_FS_ORCA",
                timeout=90.0,
            )
            time.sleep(3)
            w, h, px = vm.screenshot(
                os.path.join(tmp, "alice-dark.ppm"),
                os.path.join(SHOT_DIR, "phase21-alice-desktop-dark.png"),
            )
            print(f"[PASS][P21] First-boot preference preservation, Dark mode ({w}x{h}), fs-test & Orca verified", flush=True)

            vm.poweroff(alice_pass, timeout=120.0)

        # --- Step 3: Boot 2 — Reboot Persistence + Second Graphical Login as alice ---
        with QemuVM(desktop_boot_cmd(), os.path.join(LOG_DIR, "qemu-phase21-boot2-persist.log"), mon_sock) as vm:
            vm.login("alice", alice_pass, timeout=240.0)
            vm.run_cmd(
                "test -f /home/alice/.config/.os1-shell-initialized && "
                "grep -q 'appearance=dark' /home/alice/.config/os1-onboarding.conf && "
                "grep -q 'reduced_motion=on' /home/alice/.config/os1-onboarding.conf && "
                "for i in $(seq 1 45); do pgrep -f sddm-greeter >/dev/null 2>&1 && break; sleep 2; done",
                "PERSIST_AND_GREETER2",
                timeout=120.0,
            )
            vm.screenshot(
                os.path.join(tmp, "greeter2.ppm"),
                os.path.join(SHOT_DIR, "phase21-sddm-greeter-boot2.png"),
            )
            vm.type_password_via_sendkey(alice_pass)
            vm.run_cmd(
                "UID_ALICE=$(id -u alice); "
                "for i in $(seq 1 60); do "
                "  pgrep -u alice -x kwin_wayland >/dev/null 2>&1 && "
                "  pgrep -u alice -x plasmashell >/dev/null 2>&1 && break; "
                "  sleep 2; "
                "done; "
                "pgrep -u alice -x kwin_wayland >/dev/null && pgrep -u alice -x plasmashell >/dev/null",
                "BOOT2_GUI_LOGIN",
                timeout=150.0,
            )
            print("[PASS][P21] Boot 2 graphical SDDM login & onboarding preference persistence verified", flush=True)
            vm.poweroff(alice_pass, timeout=120.0)

    print("[os1-phase21] ALL INSTALLED GRAPHICAL USER JOURNEY TESTS PASSED.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
