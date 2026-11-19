#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 23: Dual-build byte-for-byte reproducibility check for OS-1 native .deb packages.

Builds all 8 native OS-1 Debian packages twice into isolated temporary output
directories under a fixed SOURCE_DATE_EPOCH and asserts identical SHA-256
digests for every generated .deb archive.
"""

import hashlib
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_once(out_dir: str, epoch: str) -> dict[str, str]:
    env = os.environ.copy()
    env["OS1_OUT_DIR"] = out_dir
    env["SOURCE_DATE_EPOCH"] = epoch
    env.pop("OS1_EPHEMERAL_GPG", None)
    env.pop("OS1_GPG_KEY_ID", None)
    subprocess.check_call(
        [os.path.join(REPO_ROOT, "distro", "packages", "build-debs.sh")],
        env=env,
        stdout=subprocess.DEVNULL,
    )
    repo_dir = os.path.join(out_dir, "apt-repo")
    return {
        fn: sha256_file(os.path.join(repo_dir, fn))
        for fn in sorted(os.listdir(repo_dir))
        if fn.endswith(".deb")
    }


def main() -> int:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if not epoch:
        epoch = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "log", "-1", "--format=%ct"], text=True
        ).strip()

    with tempfile.TemporaryDirectory(prefix="os1-repro-a-") as dir_a, \
         tempfile.TemporaryDirectory(prefix="os1-repro-b-") as dir_b:
        hashes_a = build_once(dir_a, epoch)
        hashes_b = build_once(dir_b, epoch)

    if set(hashes_a.keys()) != set(hashes_b.keys()) or not hashes_a:
        print("ERROR: Package sets differ between build A and build B", file=sys.stderr)
        return 1

    diffs = []
    for fn in sorted(hashes_a):
        if hashes_a[fn] != hashes_b[fn]:
            diffs.append((fn, hashes_a[fn], hashes_b[fn]))

    if diffs:
        print(f"[FAIL] Reproducibility mismatch ({len(diffs)} packages differ):", file=sys.stderr)
        for fn, ha, hb in diffs:
            print(f"  {fn}: A={ha} B={hb}", file=sys.stderr)
        return 1

    print(
        f"[PASS] Byte-for-byte reproducibility verified for {len(hashes_a)} OS-1 .deb packages "
        f"(SOURCE_DATE_EPOCH={epoch})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
