#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 8 automated filesystem operations test suite for OS-1.

Verifies real local filesystem semantics expected of a Finder-class desktop:
  1. Create, copy, move, rename operations
  2. FreeDesktop Trash (`~/.local/share/Trash/{files,info}`) move & restore
  3. Valid and dangling symbolic links
  4. Unicode & emoji filenames (`日本語-émoji-🚀-café.txt`)
  5. Large file (16 MiB) copy with SHA-256 integrity verification
  6. Read-only directory permission error handling (`PermissionError`)
"""

import errno
import hashlib
import os
import shutil
import stat
import sys
import tempfile
import urllib.parse


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    work = tempfile.mkdtemp(prefix="os1-fs-test-")
    trash_files = os.path.expanduser("~/.local/share/Trash/files")
    trash_info = os.path.expanduser("~/.local/share/Trash/info")
    os.makedirs(trash_files, exist_ok=True)
    os.makedirs(trash_info, exist_ok=True)

    try:
        # 1. Create, copy, move, rename
        src = os.path.join(work, "hello.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("OS-1 Phase 8 filesystem proof\n")
        copied = os.path.join(work, "hello-copy.txt")
        shutil.copy2(src, copied)
        moved = os.path.join(work, "hello-moved.txt")
        shutil.move(copied, moved)
        assert os.path.isfile(moved) and not os.path.exists(copied)
        with open(moved, "r", encoding="utf-8") as f:
            assert f.read() == "OS-1 Phase 8 filesystem proof\n"
        print("[PASS] Create, copy, move, rename verified", flush=True)

        # 2. XDG Trash move & restore
        trash_name = f"os1-trash-test-{os.getpid()}.txt"
        trashed_data = os.path.join(trash_files, trash_name)
        trashed_meta = os.path.join(trash_info, f"{trash_name}.trashinfo")
        shutil.move(moved, trashed_data)
        with open(trashed_meta, "w", encoding="utf-8") as f:
            f.write(
                f"[Trash Info]\nPath={urllib.parse.quote(moved)}\nDeletionDate=2026-11-19T00:00:00\n"
            )
        assert os.path.isfile(trashed_data) and os.path.isfile(trashed_meta)
        # Restore from Trash
        shutil.move(trashed_data, moved)
        os.remove(trashed_meta)
        assert os.path.isfile(moved)
        print("[PASS] FreeDesktop Trash move & restore verified", flush=True)

        # 3. Valid & dangling symlinks
        good_link = os.path.join(work, "valid-link")
        bad_link = os.path.join(work, "dangling-link")
        os.symlink(src, good_link)
        os.symlink(os.path.join(work, "does-not-exist"), bad_link)
        assert os.path.islink(good_link) and os.path.exists(good_link)
        assert os.path.islink(bad_link) and not os.path.exists(bad_link)
        print("[PASS] Valid & dangling symlinks verified", flush=True)

        # 4. Unicode & emoji filenames
        uni_name = "日本語-émoji-🚀-café.txt"
        uni_path = os.path.join(work, uni_name)
        with open(uni_path, "w", encoding="utf-8") as f:
            f.write("Unicode content: naïve résumé 東京\n")
        assert uni_name in os.listdir(work)
        print("[PASS] Unicode & emoji filename handling verified", flush=True)

        # 5. Large file (16 MiB) copy integrity
        big_src = os.path.join(work, "large-16m.bin")
        big_dst = os.path.join(work, "large-16m-copy.bin")
        block = os.urandom(1024 * 1024)
        with open(big_src, "wb") as f:
            for _ in range(16):
                f.write(block)
        shutil.copy2(big_src, big_dst)
        assert sha256_file(big_src) == sha256_file(big_dst)
        print("[PASS] 16 MiB large file copy SHA-256 integrity verified", flush=True)

        # 6. Permission error handling (non-root)
        if os.geteuid() != 0:
            ro_dir = os.path.join(work, "readonly-dir")
            os.mkdir(ro_dir)
            os.chmod(ro_dir, stat.S_IRUSR | stat.S_IXUSR)
            try:
                raised = False
                try:
                    with open(os.path.join(ro_dir, "blocked.txt"), "w", encoding="utf-8") as f:
                        f.write("should fail")
                except PermissionError as exc:
                    raised = exc.errno == errno.EACCES
                assert raised, "Expected EACCES PermissionError in read-only directory"
            finally:
                os.chmod(ro_dir, stat.S_IRWXU)
            print("[PASS] Read-only permission error handling (EACCES) verified", flush=True)

        print("[os1-fs-test] ALL PHASE 8 FILESYSTEM TESTS PASSED.", flush=True)
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
