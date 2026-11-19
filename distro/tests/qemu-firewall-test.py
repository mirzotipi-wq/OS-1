#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 17: Behavioral runtime firewall verification for OS-1 in isolated QEMU.

Verifies inside a running OS-1 guest (using QEMU user-mode hostfwd as an isolated
external peer, without touching the host firewall):
  1. `systemctl is-active ufw.service` == active & `systemctl is-failed ufw.service` != failed
  2. `ufw status verbose` reports `Status: active`, `deny (incoming)`, `allow (outgoing)`
  3. `nft list ruleset` reports loaded UFW nftables rules
  4. Loopback traffic functions (guest reaches its own listener on 127.0.0.1:18080)
  5. Outbound DNS / APT / established connections function
  6. External peer (host -> QEMU hostfwd -> guest eth0:18080) is BLOCKED by default
  7. After `ufw allow 18080/tcp`, external peer REACHES the guest HTTP service
  8. After `ufw delete allow 18080/tcp`, external peer is BLOCKED again
  9. Persistent rule (`ufw allow 18081/tcp`) and active firewall survive reboot
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
import urllib.error
import urllib.request


def find_free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def probe_http(host_port: int, timeout: float = 4.0) -> tuple[bool, str]:
    """Attempt an HTTP GET from the external peer (host) to the guest via hostfwd."""
    url = f"http://127.0.0.1:{host_port}/"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return True, f"HTTP {resp.status}: {body.strip()}"
    except Exception as exc:
        return False, str(exc)


class FirewallVm:
    def __init__(self, kernel_path: str, disk_path: str, log_path: str, host_port: int) -> None:
        self.log_file = open(log_path, "wb")
        self.buf = ""
        self.master_fd, self.slave_fd = pty.openpty()

        accel_args = ["-accel", "tcg", "-cpu", "Haswell"]
        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            accel_args = ["-enable-kvm", "-cpu", "host"]

        cmd = [
            "qemu-system-x86_64",
            *accel_args,
            "-machine", "q35",
            "-m", "1536M",
            "-smp", "2",
            "-kernel", kernel_path,
            "-drive", f"file={disk_path},format=raw,if=virtio",
            "-netdev", f"user,id=net0,hostfwd=tcp:127.0.0.1:{host_port}-:18080",
            "-device", "virtio-net-pci,netdev=net0",
            "-append", "root=/dev/vda rw console=ttyS0,115200n8 panic=-1 net.ifnames=0",
            "-nographic",
            "-monitor", "none",
            "-no-reboot",
        ]
        print(f"[os1-firewall-test] Launching QEMU: {' '.join(cmd)}", flush=True)
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

    def run_cmd(self, cmd: str, marker: str, timeout: float = 90.0, expect_rc: str = "0") -> str:
        self.sendline(f"{cmd}; printf '%s_RC=%d\\n' '{marker}' $?")
        out = self.expect(f"{marker}_RC=", timeout=timeout)
        rc_line = self.expect("\n", timeout=10.0).strip()
        if rc_line != expect_rc:
            raise RuntimeError(
                f"Command exit mismatch (got rc={rc_line}, expected {expect_rc}): {cmd}\nOutput:\n{out[-1200:]}"
            )
        return out

    def login(self, user: str = "os1", password: str = "os1") -> None:
        self.expect("os1 login:", timeout=180.0)
        self.sendline(user)
        self.expect("Password:", timeout=30.0)
        self.sendline(password)
        self.expect(f"{user}@os1:", timeout=60.0)

    def poweroff_and_wait(self, password: str = "os1", timeout: float = 120.0) -> None:
        self.sendline(f"printf '%s\\n' '{password}' | sudo -S systemctl poweroff")
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

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
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
    os.makedirs(log_dir, exist_ok=True)

    for p in (kernel_path, src_disk):
        if not os.path.isfile(p):
            print(f"ERROR: Missing required artifact: {p}", file=sys.stderr)
            return 1

    work_dir = tempfile.mkdtemp(prefix="os1-firewall-")
    work_disk = os.path.join(work_dir, "os1-fw-disk.img")
    shutil.copy2(src_disk, work_disk)
    host_port = find_free_tcp_port()

    boot1_log = os.path.join(log_dir, "qemu-phase17-firewall-boot1.log")
    boot2_log = os.path.join(log_dir, "qemu-phase17-firewall-boot2.log")

    try:
        # --- BOOT 1: Runtime state, loopback, outbound, external block/allow/delete, persistent rule ---
        vm1 = FirewallVm(kernel_path, work_disk, boot1_log, host_port)
        try:
            vm1.login()
            print("[PASS][FUNC] Boot 1 logged in", flush=True)

            # 1. Service health & ruleset
            out = vm1.run_cmd(
                "test \"$(systemctl is-active ufw.service)\" = 'active' && "
                "test \"$(systemctl is-failed ufw.service || true)\" != 'failed' && "
                "printf 'os1\\n' | sudo -S ufw status verbose && "
                "printf 'os1\\n' | sudo -S nft list ruleset",
                "UFW_STATE",
                timeout=30.0,
            )
            for needle in ("Status: active", "deny (incoming)", "allow (outgoing)", "ufw-before-input"):
                if needle not in out:
                    raise RuntimeError(f"Expected {needle!r} in UFW/nft output:\n{out[-1500:]}")
            print("[PASS][FUNC] ufw.service active, default deny incoming / allow outgoing, nft ruleset loaded", flush=True)

            # 2. Wait for eth0 IPv4 and verify outbound DNS + HTTP/APT
            vm1.run_cmd(
                "for i in $(seq 1 30); do ip -4 addr show dev eth0 | grep -q 'inet ' && break; sleep 2; done; "
                "ip -4 addr show dev eth0 | grep 'inet ' && "
                "printf 'os1\\n' | sudo -S apt-get update",
                "OUTBOUND",
                timeout=120.0,
            )
            print("[PASS][FUNC] Outbound DNS & APT connectivity verified while UFW is active", flush=True)

            # 3. Start an HTTP server inside the guest on 0.0.0.0:18080 and verify loopback works
            vm1.run_cmd(
                "mkdir -p /tmp/fw-www && echo 'OS1-FW-TEST-OK' > /tmp/fw-www/index.html && "
                "nohup python3 -m http.server 18080 --bind 0.0.0.0 --directory /tmp/fw-www >/tmp/fw-srv.log 2>&1 & "
                "echo $! > /tmp/fw-srv.pid; sleep 2; "
                "curl -sf http://127.0.0.1:18080/ | grep -q 'OS1-FW-TEST-OK'",
                "LOOPBACK",
                timeout=30.0,
            )
            print("[PASS][FUNC] Guest loopback HTTP traffic verified on 127.0.0.1:18080", flush=True)

            # 4. External peer MUST be blocked by default
            ok, detail = probe_http(host_port, timeout=4.0)
            if ok:
                raise RuntimeError(f"FIREWALL FAILURE: External peer reached port 18080 by default! ({detail})")
            print(f"[PASS][FUNC] External peer BLOCKED by default on port 18080 ({detail})", flush=True)

            # 5. Explicitly allow 18080/tcp -> external peer MUST reach guest
            vm1.run_cmd("printf 'os1\\n' | sudo -S ufw allow 18080/tcp", "UFW_ALLOW", timeout=20.0)
            ok, detail = probe_http(host_port, timeout=6.0)
            if not ok or "OS1-FW-TEST-OK" not in detail:
                raise RuntimeError(f"External peer failed to reach allowed port 18080: {detail}")
            print(f"[PASS][FUNC] External peer REACHED port 18080 after temporary allow ({detail})", flush=True)

            # 6. Remove allow rule -> external peer MUST be blocked again
            vm1.run_cmd("printf 'os1\\n' | sudo -S ufw delete allow 18080/tcp", "UFW_DENY_AGAIN", timeout=20.0)
            ok, detail = probe_http(host_port, timeout=4.0)
            if ok:
                raise RuntimeError(f"FIREWALL FAILURE: External peer still reached port 18080 after rule removal! ({detail})")
            print(f"[PASS][FUNC] External peer BLOCKED again after removing allow rule ({detail})", flush=True)

            # 7. Add persistent test rule (18081/tcp) to verify persistence across reboot
            vm1.run_cmd("printf 'os1\\n' | sudo -S ufw allow 18081/tcp && sync", "UFW_PERSIST_RULE", timeout=20.0)
            vm1.poweroff_and_wait("os1")
        finally:
            vm1.close()

        # --- BOOT 2: Verify firewall + rules survive reboot ---
        vm2 = FirewallVm(kernel_path, work_disk, boot2_log, host_port)
        try:
            vm2.login()
            out = vm2.run_cmd(
                "test \"$(systemctl is-active ufw.service)\" = 'active' && "
                "test \"$(systemctl is-failed ufw.service || true)\" != 'failed' && "
                "printf 'os1\\n' | sudo -S ufw status verbose",
                "UFW_REBOOT",
                timeout=30.0,
            )
            for needle in ("Status: active", "deny (incoming)", "18081/tcp", "ALLOW"):
                if needle not in out:
                    raise RuntimeError(f"Firewall reboot persistence check missing {needle!r}:\n{out[-1200:]}")
            print("[PASS][E2E] UFW active state and rules survived reboot cleanly", flush=True)

            # Clean up test rule
            vm2.run_cmd("printf 'os1\\n' | sudo -S ufw delete allow 18081/tcp", "UFW_CLEANUP", timeout=20.0)
            vm2.poweroff_and_wait("os1")
        finally:
            vm2.close()

        print("[os1-firewall-test] ALL PHASE 17 BEHAVIORAL FIREWALL ASSERTIONS PASSED.", flush=True)
        return 0
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
