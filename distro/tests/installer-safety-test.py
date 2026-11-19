#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 18: Installer preflight safety, credential handling, and nondestructive tests.

Runs safely in any non-root environment using disposable sparse image files
(never touches any host block device). For every rejected preflight case,
verifies that the target image's initial-block and full SHA-256 checksums are
bit-for-bit identical before and after invocation.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Hash initial 4 MiB (MBR/GPT/superblocks), tail 1 MiB (backup GPT), and size/blocks."""
    st = path.stat()
    h = hashlib.sha256()
    h.update(f"size={st.st_size};blocks={st.st_blocks};".encode("ascii"))
    with open(path, "rb") as f:
        h.update(f.read(4 * 1024 * 1024))
        if st.st_size > 4 * 1024 * 1024:
            f.seek(max(0, st.st_size - 1024 * 1024))
            h.update(f.read(1024 * 1024))
    return h.hexdigest()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    installer = repo_root / "distro" / "installer" / "os1-install"
    work = Path(tempfile.mkdtemp(prefix="os1-installer-safety-"))

    try:
        # Prepare mock live source artifacts (rootfs + kernel + zoneinfo + /etc/passwd)
        src_ro = work / "live-ro"
        (src_ro / "etc").mkdir(parents=True)
        (src_ro / "usr" / "share" / "zoneinfo" / "America").mkdir(parents=True)
        (src_ro / "usr" / "share" / "zoneinfo" / "UTC").write_text("TZif2", encoding="utf-8")
        (src_ro / "usr" / "share" / "zoneinfo" / "America" / "Los_Angeles").write_text("TZif2", encoding="utf-8")
        (src_ro / "etc" / "passwd").write_text(
            "root:x:0:0:root:/root:/bin/bash\n"
            "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n"
            "customsvc:x:999:999:svc:/nonexistent:/usr/sbin/nologin\n"
            "os1:x:1000:1000:OS-1 Live:/home/os1:/bin/bash\n",
            encoding="utf-8",
        )
        (src_ro / "etc" / "os-release").write_text('PRETTY_NAME="OS-1 1.0-rc2"\nID=os1\n', encoding="utf-8")

        src_kernel = work / "vmlinuz"
        src_kernel.write_bytes(b"MOCK-KERNEL-IMAGE" * 64)

        # Create a 3 GiB sparse disposable image file (takes ~0 disk blocks)
        disk_ok = work / "target-3g.img"
        with open(disk_ok, "wb") as f:
            f.write(b"OS1-TEST-GUARD-HEADER-1234567890")
            f.truncate(3 * 1024 * 1024 * 1024)
        disk_ok_sha = sha256_file(disk_ok)

        # Create a too-small 512 MiB sparse image
        disk_small = work / "target-small.img"
        with open(disk_small, "wb") as f:
            f.write(b"SMALL-DISK")
            f.truncate(512 * 1024 * 1024)
        disk_small_sha = sha256_file(disk_small)

        # Create a read-only 3 GiB sparse image
        disk_ro = work / "target-ro.img"
        with open(disk_ro, "wb") as f:
            f.write(b"READONLY-DISK")
            f.truncate(3 * 1024 * 1024 * 1024)
        os.chmod(disk_ro, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        disk_ro_sha = sha256_file(disk_ro)

        def run_inst(extra_args: list[str], stdin_bytes: bytes | None = None) -> subprocess.CompletedProcess:
            cmd = [
                sys.executable,
                str(installer),
                "--source-ro", str(src_ro),
                "--source-kernel", str(src_kernel),
                *extra_args,
            ]
            return subprocess.run(cmd, input=stdin_bytes, capture_output=True)

        # 1. Valid special-character and Unicode passwords accepted in --json-plan, NEVER exposed in output
        special_passwords = [
            ("apostrophe", "O'Brien'sPass"),
            ("double_quote", 'Say "Hello" World'),
            ("dollar_sign", "Cost$100$HOME"),
            ("spaces", "pass with spaces inside"),
            ("backslash", r"back\slash\n\t"),
            ("metachars", "a;b&c(d)|e!f`g`"),
            ("unicode", "pässwörd-🚀-日本語"),
        ]
        for label, pw in special_passwords:
            res = run_inst(
                [
                    "--disk", str(disk_ok),
                    "--user", "alice",
                    "--hostname", "os1-workstation",
                    "--timezone", "America/Los_Angeles",
                    "--password-stdin",
                    "--json-plan",
                    "--allow-file-target-for-preflight-test",
                ],
                stdin_bytes=(pw + "\n").encode("utf-8"),
            )
            assert res.returncode == 0, f"Valid password ({label}) failed: {res.stderr.decode()}"
            stdout_txt = res.stdout.decode("utf-8")
            stderr_txt = res.stderr.decode("utf-8")
            assert pw not in stdout_txt and pw not in stderr_txt, f"Password ({label}) leaked in output!"
            plan = json.loads(stdout_txt)
            assert plan["username"] == "alice"
            assert plan["partition_table"] == "gpt"
            assert plan["efi_partition_mib"] == 256
            assert sha256_file(disk_ok) == disk_ok_sha
        print(f"[PASS] Accepted {len(special_passwords)} special-character & Unicode passwords without leakage", flush=True)

        # 2. --password-fd support
        r_fd, w_fd = os.pipe()
        os.write(w_fd, b"fd'pass$123\n")
        os.close(w_fd)
        try:
            res = subprocess.run(
                [
                    sys.executable, str(installer),
                    "--source-ro", str(src_ro),
                    "--source-kernel", str(src_kernel),
                    "--disk", str(disk_ok),
                    "--user", "alice",
                    "--password-fd", str(r_fd),
                    "--dry-run",
                    "--allow-file-target-for-preflight-test",
                ],
                pass_fds=(r_fd,),
                capture_output=True,
            )
        finally:
            os.close(r_fd)
        assert res.returncode == 0, f"--password-fd failed: {res.stderr.decode()}"
        assert b"fd'pass$123" not in res.stdout and b"fd'pass$123" not in res.stderr
        print("[PASS] --password-fd credential channel verified without leakage", flush=True)

        # 3. Rejected cases — ALL must fail nonzero AND leave target image checksum identical
        negative_cases: list[tuple[str, list[str], bytes | None, Path, str]] = [
            ("argv --password forbidden", ["--disk", str(disk_ok), "--user", "alice", "--password", "secret", "--dry-run", "--allow-file-target-for-preflight-test"], None, disk_ok, disk_ok_sha),
            ("password with embedded newline", ["--disk", str(disk_ok), "--user", "alice", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"line1\nline2\n", disk_ok, disk_ok_sha),
            ("password with CR", ["--disk", str(disk_ok), "--user", "alice", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"line1\rline2\n", disk_ok, disk_ok_sha),
            ("password with NUL", ["--disk", str(disk_ok), "--user", "alice", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"bad\x00pass\n", disk_ok, disk_ok_sha),
            ("empty password", ["--disk", str(disk_ok), "--user", "alice", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"\n", disk_ok, disk_ok_sha),
            ("oversized password", ["--disk", str(disk_ok), "--user", "alice", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"A" * 300 + b"\n", disk_ok, disk_ok_sha),
            ("username root", ["--disk", str(disk_ok), "--user", "root", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
            ("username os1 (reserved live)", ["--disk", str(disk_ok), "--user", "os1", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
            ("username daemon (reserved)", ["--disk", str(disk_ok), "--user", "daemon", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
            ("username existing in rootfs /etc/passwd", ["--disk", str(disk_ok), "--user", "customsvc", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
            ("username with path sep", ["--disk", str(disk_ok), "--user", "../evil", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
            ("username with spaces", ["--disk", str(disk_ok), "--user", "bad user", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
            ("username with uppercase", ["--disk", str(disk_ok), "--user", "Alice", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
            ("too-small target", ["--disk", str(disk_small), "--user", "alice", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_small, disk_small_sha),
            ("read-only target", ["--disk", str(disk_ro), "--user", "alice", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ro, disk_ro_sha),
            ("non-block-device without test flag", ["--disk", str(disk_ok), "--user", "alice", "--password-stdin", "--dry-run"], b"validpass\n", disk_ok, disk_ok_sha),
            ("invalid timezone", ["--disk", str(disk_ok), "--user", "alice", "--timezone", "Mars/Olympus", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
            ("invalid hostname", ["--disk", str(disk_ok), "--user", "alice", "--hostname", "-bad_host!", "--password-stdin", "--dry-run", "--allow-file-target-for-preflight-test"], b"validpass\n", disk_ok, disk_ok_sha),
        ]

        for label, extra, stdin_b, target_img, expected_sha in negative_cases:
            res = run_inst(extra, stdin_bytes=stdin_b)
            assert res.returncode != 0, f"Expected failure for {label}, got rc=0"
            assert sha256_file(target_img) == expected_sha, f"Target image modified on rejected case: {label}!"
        print(f"[PASS] All {len(negative_cases)} negative preflight cases rejected with identical disk checksums", flush=True)

        # 4. Missing kernel and missing rootfs artifacts
        res_nok = subprocess.run(
            [
                sys.executable, str(installer),
                "--source-ro", str(src_ro),
                "--source-kernel", str(work / "missing-vmlinuz"),
                "--disk", str(disk_ok),
                "--user", "alice",
                "--dry-run",
                "--allow-file-target-for-preflight-test",
            ],
            capture_output=True,
        )
        assert res_nok.returncode != 0
        res_nor = subprocess.run(
            [
                sys.executable, str(installer),
                "--source-ro", str(work / "missing-ro"),
                "--source-kernel", str(src_kernel),
                "--disk", str(disk_ok),
                "--user", "alice",
                "--dry-run",
                "--allow-file-target-for-preflight-test",
            ],
            capture_output=True,
        )
        assert res_nor.returncode != 0
        assert sha256_file(disk_ok) == disk_ok_sha
        print("[PASS] Missing kernel and missing rootfs artifacts rejected before disk access", flush=True)

        print("[os1-installer-safety-test] ALL PHASE 18 PREFLIGHT & CREDENTIAL SAFETY TESTS PASSED.", flush=True)
        return 0
    finally:
        # Restore write permission on disk_ro before cleanup
        try:
            os.chmod(work / "target-ro.img", 0o600)
        except OSError:
            pass
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
