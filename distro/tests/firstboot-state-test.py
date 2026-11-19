#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 21: Unit tests for os1-firstboot state preservation and os1-shell-init retryability."""

import os
import stat
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FIRSTBOOT = os.path.join(REPO_ROOT, "distro", "installer", "os1-firstboot")
SHELL_INIT = os.path.join(REPO_ROOT, "distro", "shell", "bin", "os1-shell-init")


def test_firstboot() -> None:
    with tempfile.TemporaryDirectory(prefix="os1-fb-test-") as tmp:
        cfg_dir = os.path.join(tmp, "config")
        state_file = os.path.join(cfg_dir, "os1-onboarding.conf")
        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = cfg_dir
        env["OS1_FIRSTBOOT_NO_APPLY"] = "1"

        # 1. Missing state file -> completed=false
        out = subprocess.check_output([FIRSTBOOT, "--status"], env=env, text=True)
        assert "completed=false" in out, f"Unexpected status: {out}"

        # 2. Apply appearance=dark
        subprocess.check_call([FIRSTBOOT, "--apply", "--appearance", "dark"], env=env, stdout=subprocess.DEVNULL)
        out = subprocess.check_output([FIRSTBOOT, "--status"], env=env, text=True)
        assert "completed=true" in out and "appearance=dark" in out and "reduced_motion=off" in out

        # 3. Partial update (--reduced-motion on) MUST preserve appearance=dark (Baseline Defect #15)
        subprocess.check_call([FIRSTBOOT, "--apply", "--reduced-motion", "on"], env=env, stdout=subprocess.DEVNULL)
        out = subprocess.check_output([FIRSTBOOT, "--status"], env=env, text=True)
        assert "appearance=dark" in out, f"Partial update clobbered appearance=dark:\n{out}"
        assert "reduced_motion=on" in out

        # 4. Partial update (--high-contrast on --screen-reader on) preserves previous choices
        subprocess.check_call(
            [FIRSTBOOT, "--apply", "--high-contrast", "on", "--screen-reader", "on"],
            env=env,
            stdout=subprocess.DEVNULL,
        )
        out = subprocess.check_output([FIRSTBOOT, "--status"], env=env, text=True)
        for expected in ("appearance=dark", "reduced_motion=on", "high_contrast=on", "screen_reader=on"):
            assert expected in out, f"Missing {expected} in:\n{out}"

        # 5. Invalid value rejected (rc=2) without modifying state file
        before = open(state_file, "rb").read()
        res = subprocess.run([FIRSTBOOT, "--apply", "--appearance", "neon"], env=env, capture_output=True)
        assert res.returncode == 2, f"Expected rc=2, got {res.returncode}"
        assert open(state_file, "rb").read() == before, "State file modified on invalid argument"

        # 6. Corrupt state file recovery: preserve valid keys, ignore garbage
        with open(state_file, "wb") as f:
            f.write(b"\x00\xffCORRUPT_LINE\nappearance=dark\nbad_key=invalid\nreduced_transparency=on\n")
        subprocess.check_call([FIRSTBOOT, "--apply", "--reduced-motion", "off"], env=env, stdout=subprocess.DEVNULL)
        out = subprocess.check_output([FIRSTBOOT, "--status"], env=env, text=True)
        assert "appearance=dark" in out and "reduced_transparency=on" in out and "reduced_motion=off" in out

    print("[PASS] os1-firstboot state preservation, validation, and corrupt-file recovery verified")


def _write_stub(bin_dir: str, name: str, body: str) -> None:
    path = os.path.join(bin_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env bash\n" + body + "\n")
    os.chmod(path, stat.S_IRWXU)


def test_shell_init() -> None:
    with tempfile.TemporaryDirectory(prefix="os1-si-test-") as tmp:
        bin_dir = os.path.join(tmp, "bin")
        home_dir = os.path.join(tmp, "home")
        cfg_dir = os.path.join(home_dir, ".config")
        os.makedirs(bin_dir)
        os.makedirs(home_dir)

        layout_js = os.path.join(tmp, "layout.js")
        wallpaper = os.path.join(tmp, "wp.png")
        call_log = os.path.join(tmp, "calls.log")
        open(layout_js, "w").write("// test layout\n")
        open(wallpaper, "wb").write(b"PNG")

        _write_stub(bin_dir, "qdbus", f'echo "qdbus $*" >> "{call_log}"; exit 0')
        _write_stub(bin_dir, "plasma-apply-lookandfeel", f'echo "laf $*" >> "{call_log}"; exit 0')
        _write_stub(bin_dir, "plasma-apply-wallpaperimage", f'echo "wp $*" >> "{call_log}"; exit 0')
        # First run: force plasma-apply-colorscheme to FAIL
        _write_stub(bin_dir, "plasma-apply-colorscheme", f'echo "cs-fail $*" >> "{call_log}"; exit 1')

        env = os.environ.copy()
        env["HOME"] = home_dir
        env["XDG_CONFIG_HOME"] = cfg_dir
        env["XDG_RUNTIME_DIR"] = tmp
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        env["OS1_LAYOUT_JS"] = layout_js
        env["OS1_WALLPAPER"] = wallpaper

        # 1. Failure in required step MUST exit non-zero and NOT write completion stamp
        res = subprocess.run([SHELL_INIT], env=env, capture_output=True)
        assert res.returncode != 0, "os1-shell-init returned 0 despite required step failing!"
        stamp = os.path.join(cfg_dir, ".os1-shell-initialized")
        assert not os.path.exists(stamp), "os1-shell-init wrote completion stamp despite failure!"

        # 2. Fix colorscheme stub -> retry succeeds and writes stamp
        _write_stub(bin_dir, "plasma-apply-colorscheme", f'echo "cs-ok $*" >> "{call_log}"; exit 0')
        subprocess.check_call([SHELL_INIT], env=env)
        assert os.path.isfile(stamp), "os1-shell-init did not write completion stamp on success!"

        # 3. Re-run when stamp exists -> idempotent no-op
        before_calls = open(call_log).read()
        subprocess.check_call([SHELL_INIT], env=env)
        assert open(call_log).read() == before_calls, "os1-shell-init was not idempotent after stamp existed!"

    print("[PASS] os1-shell-init failure detection, non-stamp on error, retry, and idempotency verified")


def main() -> int:
    test_firstboot()
    test_shell_init()
    print("[os1-firstboot-state-test] ALL PHASE 21 FIRST-BOOT & SHELL-INIT UNIT TESTS PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
