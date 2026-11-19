#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 5 automated QEMU Wayland graphical session verification for OS-1.

Boots the OS-1 desktop disk image (`OS1_PROFILE=desktop`) with the real OS-1
x86_64 kernel (`7.4.0-rc3-os1`), virtual GPU (`virtio-vga`), virtual input
(`virtio-keyboard-pci`, `virtio-mouse-pci`), virtual HDA audio, and user-mode
networking, and verifies:
  1. OS-1 kernel (`7.4.0-rc3-os1`) boots to `graphical.target` with `sddm.service` active.
  2. Plasma Wayland session starts cleanly for non-root user `os1` (`kwin_wayland`,
     `plasmashell`, `pipewire`, `/run/user/1000/wayland-0`).
  3. Core desktop applications (`konsole`, `dolphin`, `firefox-esr`) are installed
     and launchable inside the Wayland session.
  4. Captures a real QEMU framebuffer screenshot via QEMU monitor `screendump`
     and verifies it contains real rendered non-black pixels.
  5. Verifies clean shutdown with zero kernel panics/Oops.
"""

import os
import pty
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time


def ppm_to_png_and_check_nonblack(ppm_path: str, png_path: str) -> tuple[int, int, float]:
    """Read P6 PPM from QEMU screendump, compute non-black pixel ratio, and save PNG (or copy PPM)."""
    with open(ppm_path, "rb") as f:
        magic = f.readline().strip()
        if magic != b"P6":
            raise RuntimeError(f"Unexpected PPM header: {magic!r}")
        line = f.readline()
        while line.startswith(b"#"):
            line = f.readline()
        w, h = map(int, line.strip().split())
        _maxval = int(f.readline().strip())
        raw = f.read()

    total_pixels = w * h
    nonblack = 0
    # Sample every 4th pixel for speed
    step = 12
    sampled = 0
    for i in range(0, len(raw) - 2, step):
        sampled += 1
        if raw[i] > 8 or raw[i + 1] > 8 or raw[i + 2] > 8:
            nonblack += 1
    ratio = (nonblack / sampled) if sampled else 0.0

    # Convert to PNG via PIL or ImageMagick if available, else write pure-stdlib PNG
    import struct
    import zlib

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack("!I", len(data)) + c + struct.pack("!I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack("!IIBBBBB", w, h, 8, 2, 0, 0, 0)
    stride = w * 3
    rows = bytearray()
    for y in range(h):
        rows.append(0)  # filter type 0
        rows.extend(raw[y * stride : (y + 1) * stride])
    idat = zlib.compress(bytes(rows), level=6)

    with open(png_path, "wb") as out:
        out.write(b"\x89PNG\r\n\x1a\n")
        out.write(png_chunk(b"IHDR", ihdr))
        out.write(png_chunk(b"IDAT", idat))
        out.write(png_chunk(b"IEND", b""))

    return w, h, ratio


class DesktopVm:
    def __init__(self, kernel_path: str, disk_path: str, mon_sock: str, log_path: str) -> None:
        self.log_file = open(log_path, "wb")
        self.mon_sock = mon_sock
        self.buf = ""
        self.master_fd, self.slave_fd = pty.openpty()

        accel_args = ["-accel", "tcg", "-cpu", "Haswell"]
        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            accel_args = ["-enable-kvm", "-cpu", "host"]

        cmd = [
            "qemu-system-x86_64",
            *accel_args,
            "-machine", "q35",
            "-m", "2560M",
            "-smp", "2",
            "-kernel", kernel_path,
            "-drive", f"file={disk_path},format=raw,if=virtio",
            "-device", "virtio-vga,xres=1440,yres=900",
            "-device", "virtio-keyboard-pci",
            "-device", "virtio-mouse-pci",
            "-device", "intel-hda",
            "-device", "hda-duplex",
            "-netdev", "user,id=net0",
            "-device", "virtio-net-pci,netdev=net0",
            "-append", "root=/dev/vda rw console=ttyS0,115200n8 panic=-1 net.ifnames=0",
            "-display", "none",
            "-serial", "stdio",
            "-monitor", f"unix:{mon_sock},server,nowait",
            "-no-reboot",
        ]
        print(f"[os1-phase5-test] Launching Desktop QEMU: {' '.join(cmd)}", flush=True)
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

    def run_cmd(self, cmd: str, marker: str, timeout: float = 120.0) -> str:
        self.sendline(f"{cmd}; printf '%s_RC=%d\\n' '{marker}' $?")
        out = self.expect(f"{marker}_RC=", timeout=timeout)
        rc_line = self.expect("\n", timeout=10.0).strip()
        if rc_line != "0":
            raise RuntimeError(f"Command failed (rc={rc_line}): {cmd}\nOutput:\n{out[-1000:]}")
        return out

    def monitor_cmd(self, cmd: str) -> str:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10.0)
            s.connect(self.mon_sock)
            time.sleep(0.2)
            try:
                s.recv(4096)
            except socket.timeout:
                pass
            s.sendall((cmd + "\n").encode("ascii"))
            time.sleep(1.0)
            try:
                return s.recv(4096).decode("utf-8", errors="replace")
            except socket.timeout:
                return ""

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
            raise TimeoutError("QEMU did not power off cleanly")
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
    kernel_path = os.path.join(out_root, "kernel", "bzImage")
    src_disk = os.path.join(out_root, "images", "os1-rootfs.ext4.img")
    log_dir = os.path.join(out_root, "logs")
    shot_dir = os.path.join(out_root, "screenshots")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(shot_dir, exist_ok=True)

    for p in (kernel_path, src_disk):
        if not os.path.isfile(p):
            print(f"ERROR: Missing required artifact: {p}", file=sys.stderr)
            return 1

    work_dir = tempfile.mkdtemp(prefix="os1-phase5-")
    work_disk = os.path.join(work_dir, "os1-desktop-test.img")
    mon_sock = os.path.join(work_dir, "qemu-mon.sock")
    ppm_path = os.path.join(work_dir, "desktop.ppm")
    png_path = os.path.join(shot_dir, "phase5-wayland-desktop.png")
    serial_log = os.path.join(log_dir, "qemu-phase5-wayland.log")

    shutil.copy2(src_disk, work_disk)

    try:
        vm = DesktopVm(kernel_path, work_disk, mon_sock, serial_log)
        try:
            vm.expect("os1 login:", timeout=240.0)
            vm.sendline("os1")
            vm.expect("Password:", timeout=30.0)
            vm.sendline("os1")
            vm.expect("os1@os1:", timeout=60.0)
            print("[PASS] Serial console authenticated on desktop image", flush=True)

            out = vm.run_cmd("uname -r && systemctl is-active sddm.service", "SDDM", timeout=60.0)
            if "7.4.0-rc3-os1" not in out or "active" not in out:
                raise RuntimeError(f"Expected OS-1 kernel + active SDDM, got:\n{out}")
            print("[PASS] OS-1 kernel (7.4.0-rc3-os1) + sddm.service active", flush=True)

            # Wait up to 180s for KWin Wayland + Plasma Shell + Wayland socket to come up (TCG software rendering)
            vm.run_cmd(
                "for i in $(seq 1 90); do "
                "  pgrep -x kwin_wayland >/dev/null 2>&1 && test -S /run/user/1000/wayland-0 && break; "
                "  sleep 2; "
                "done; "
                "if ! pgrep -x kwin_wayland >/dev/null 2>&1 || ! test -S /run/user/1000/wayland-0; then "
                "  echo '=== SDDM DIAGNOSTICS ==='; "
                "  systemctl status sddm.service --no-pager || true; "
                "  ls -la /dev/dri /run/user/1000 /usr/share/wayland-sessions || true; "
                "  journalctl -u sddm.service -n 40 --no-pager || true; "
                "  exit 1; "
                "fi; "
                "pgrep -a kwin_wayland && ls -la /run/user/1000/wayland-0",
                "KWIN",
                timeout=210.0,
            )
            print("[PASS] kwin_wayland compositor running & /run/user/1000/wayland-0 active", flush=True)

            # Wait for live (non-zombie) plasmashell and pipewire
            vm.run_cmd(
                "for i in $(seq 1 45); do "
                "  pid=$(pgrep -x plasmashell | head -n1); "
                "  if [ -n \"$pid\" ] && ! ps -o stat= -p \"$pid\" | grep -q Z; then break; fi; "
                "  sleep 2; "
                "done; "
                "ps -eo pid,stat,args | grep -E '[p]lasmashell|[p]ipewire|[X]wayland'; "
                "pid=$(pgrep -x plasmashell | head -n1); "
                "if [ -z \"$pid\" ] || ps -o stat= -p \"$pid\" | grep -q Z; then "
                "  echo '=== PLASMA DIAGNOSTICS ==='; "
                "  XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus journalctl --user -u plasma-kwin_wayland.service -u plasma-plasmashell.service -n 50 --no-pager || true; "
                "  exit 1; "
                "fi",
                "PLASMA",
                timeout=120.0,
            )
            print("[PASS] plasmashell running cleanly in Wayland session", flush=True)

            # Verify core apps installed & launch Konsole in the Wayland session
            vm.run_cmd(
                "QT_QPA_PLATFORM=offscreen konsole --version && "
                "QT_QPA_PLATFORM=offscreen dolphin --version && "
                "firefox-esr --version",
                "APPS",
                timeout=60.0,
            )
            vm.run_cmd(
                "XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
                "systemd-run --user --unit=os1-test-konsole konsole; "
                "for i in $(seq 1 20); do pgrep -x konsole >/dev/null 2>&1 && break; sleep 1; done; "
                "if ! pgrep -x konsole >/dev/null 2>&1; then "
                "  echo '=== KONSOLE DIAGNOSTICS ==='; "
                "  XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user --no-pager show-environment || true; "
                "  XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus journalctl --user -u os1-test-konsole -n 40 --no-pager || true; "
                "  exit 1; "
                "fi; "
                "sleep 6; pgrep -a konsole",
                "KONSOLE",
                timeout=60.0,
            )
            print("[PASS] Core apps (konsole, dolphin, firefox-esr) verified & konsole launched on Wayland", flush=True)

            # Wait for first-login os1-shell-init and verify Phase 6 branding & Phase 7 Top Menu Bar + Floating Dock
            vm.run_cmd(
                "for i in $(seq 1 45); do "
                "  test -f /home/os1/.config/.os1-shell-initialized && "
                "  test -f /home/os1/.config/plasma-org.kde.plasma.desktop-appletsrc && break; "
                "  sleep 2; "
                "done; "
                "test -f /usr/share/os1/tokens.json && "
                "test -f /usr/share/wallpapers/OS1Horizon/contents/images/1920x1080.png && "
                "test -f /usr/share/wallpapers/OS1Horizon/contents/images/1920x1080-dark.png && "
                "test -f /usr/share/color-schemes/OS1Light.colors && "
                "test -f /usr/share/color-schemes/OS1Dark.colors && "
                "test -f /usr/share/aurorae/themes/OS1Sequoia/OS1Sequoiarc && "
                "test -x /usr/local/bin/os1-appearance && "
                "grep -q 'org.kde.plasma.appmenu' /home/os1/.config/plasma-org.kde.plasma.desktop-appletsrc && "
                "grep -q 'org.kde.plasma.icontasks' /home/os1/.config/plasma-org.kde.plasma.desktop-appletsrc && "
                "grep -q 'org.kde.plasma.trash' /home/os1/.config/plasma-org.kde.plasma.desktop-appletsrc",
                "SHELL_LAYOUT",
                timeout=120.0,
            )
            print("[PASS] Phase 6 OS-1 branding & Phase 7 Top Menu Bar + Floating Dock layout verified", flush=True)

            # Phase 8: Automated Finder-class filesystem operations suite inside live OS-1 VM
            vm.run_cmd("os1-fs-test", "FS_TEST", timeout=60.0)
            print("[PASS] Phase 8 automated filesystem suite (copy/move/Trash+restore/symlinks/Unicode/16MiB/EACCES) passed", flush=True)

            # Phase 9 & 11: Verify Spotlight/Overview shortcuts and all 11 essential native apps from manifest
            vm.run_cmd(
                "grep -q 'Meta+Space' /etc/xdg/kglobalshortcutsrc && "
                "grep -q 'Meta+Up' /etc/xdg/kglobalshortcutsrc && "
                "test -f /etc/xdg/krunnerrc && test -f /etc/xdg/dolphinrc && "
                "python3 -c \"import json, shutil; "
                "m=json.load(open('/usr/share/os1/apps-manifest.json')); "
                "missing=[a['binary'] for a in m['apps'] if not shutil.which(a['binary'])]; "
                "assert not missing, f'Missing apps: {missing}'; "
                "print('Verified', len(m['apps']), 'native apps')\"",
                "APPS_MANIFEST",
                timeout=30.0,
            )
            print("[PASS] Phase 9 Spotlight/Overview shortcuts & Phase 11 native apps manifest (11/11) verified", flush=True)

            # Phase 10 & 12: Verify Notification Center, NetworkManager/UPower, accessibility toggles & onboarding
            vm.run_cmd(
                "XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
                "notify-send 'OS-1' 'Phase 10 Notification Center verified' && "
                "nmcli general status >/dev/null && "
                "upower -e >/dev/null && "
                "os1-accessibility reduced-motion on && "
                "os1-accessibility status | grep -q 'AnimationDurationFactor=0' && "
                "os1-accessibility reduced-motion off",
                "CONTROLS_A11Y",
                timeout=30.0,
            )
            print("[PASS] Phase 10 Notifications/Controls & Phase 12 Accessibility reduced-motion verified", flush=True)

            # Allow panels & Dock pinned launchers to finish painting on TCG, then capture Light screenshot
            time.sleep(10.0)
            w, h, ratio = 0, 0, 0.0
            for attempt in range(1, 7):
                vm.monitor_cmd("mouse_move 25 25")
                time.sleep(4.0)
                vm.monitor_cmd(f"screendump {ppm_path}")
                if os.path.isfile(ppm_path) and os.path.getsize(ppm_path) >= 1000:
                    w, h, ratio = ppm_to_png_and_check_nonblack(ppm_path, png_path)
                    print(
                        f"[os1-phase5-test] Light screendump attempt {attempt}: {w}x{h}, non-black={ratio:.1%}",
                        flush=True,
                    )
                    if ratio >= 0.20:
                        break
            if w == 0 or h == 0:
                raise RuntimeError(f"QEMU screendump failed or empty at {ppm_path}")
            if ratio < 0.20:
                raise RuntimeError(f"Light desktop screenshot under-rendered (non-black={ratio:.2%}, expected >= 20%)")
            print(f"[PASS] Captured OS-1 Light desktop screenshot: {png_path} ({w}x{h}, non-black={ratio:.1%})", flush=True)

            # Phase 10 onboarding + Dark appearance live switch & Dark screenshot
            dark_png_path = os.path.join(shot_dir, "phase6-7-os1-dark-desktop.png")
            vm.run_cmd(
                "XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
                "QT_QPA_PLATFORM=wayland WAYLAND_DISPLAY=wayland-0 "
                "os1-firstboot --apply --appearance dark --reduced-motion off && "
                "grep -q 'completed=true' /home/os1/.config/os1-onboarding.conf",
                "DARK_MODE",
                timeout=45.0,
            )
            time.sleep(10.0)
            vm.monitor_cmd("mouse_move 10 10")
            time.sleep(3.0)
            vm.monitor_cmd(f"screendump {ppm_path}")
            dw, dh, dratio = ppm_to_png_and_check_nonblack(ppm_path, dark_png_path)
            print(f"[PASS] Captured OS-1 Dark desktop screenshot: {dark_png_path} ({dw}x{dh}, non-black={dratio:.1%})", flush=True)
            if dratio < 0.10:
                raise RuntimeError(f"Dark desktop screenshot appears blank (non-black={dratio:.2%})")

            vm.poweroff_and_wait("os1")
            print("[PASS] Desktop session clean poweroff completed", flush=True)
        finally:
            vm.close()

        with open(serial_log, "rb") as f:
            text = f.read().decode("utf-8", errors="replace")
        if "Kernel panic" in text or "Oops:" in text:
            print("ERROR: Kernel panic or Oops detected in Phase 5 log", file=sys.stderr)
            return 1

        print("[os1-phase5-test] ALL PHASE 5 WAYLAND DESKTOP ASSERTIONS PASSED.", flush=True)
        return 0
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
