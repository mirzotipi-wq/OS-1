#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Pack a directory into a Linux initramfs newc CPIO gzip archive without requiring host cpio."""

import gzip
import os
import stat
import sys


def pad4(n: int) -> bytes:
    rem = n % 4
    return b"\x00" * ((4 - rem) % 4)


def make_header(
    ino: int,
    mode: int,
    uid: int,
    gid: int,
    nlink: int,
    mtime: int,
    filesize: int,
    devmajor: int,
    devminor: int,
    rdevmajor: int,
    rdevminor: int,
    namesize: int,
) -> bytes:
    return (
        f"070701"
        f"{ino:08X}{mode:08X}{uid:08X}{gid:08X}"
        f"{nlink:08X}{mtime:08X}{filesize:08X}"
        f"{devmajor:08X}{devminor:08X}{rdevmajor:08X}{rdevminor:08X}"
        f"{namesize:08X}{0:08X}"
    ).encode("ascii")


def pack_dir(root_dir: str, out_path: str) -> None:
    entries = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        filenames.sort()
        rel_dir = os.path.relpath(dirpath, root_dir)
        if rel_dir != ".":
            entries.append((rel_dir, dirpath))
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root_dir)
            entries.append((rel, full))

    ino = 1
    with gzip.GzipFile(filename=out_path, mode="wb", mtime=0) as gz:
        for rel, full in entries:
            st = os.lstat(full)
            name_bytes = rel.encode("utf-8") + b"\x00"
            mode = st.st_mode
            if stat.S_ISDIR(mode):
                data = b""
                nlink = 2
            elif stat.S_ISLNK(mode):
                data = os.readlink(full).encode("utf-8")
                nlink = 1
            elif stat.S_ISREG(mode):
                with open(full, "rb") as f:
                    data = f.read()
                nlink = 1
            else:
                continue

            hdr = make_header(
                ino=ino,
                mode=mode,
                uid=0,
                gid=0,
                nlink=nlink,
                mtime=0,
                filesize=len(data),
                devmajor=0,
                devminor=0,
                rdevmajor=0,
                rdevminor=0,
                namesize=len(name_bytes),
            )
            gz.write(hdr)
            gz.write(name_bytes)
            gz.write(pad4(len(hdr) + len(name_bytes)))
            if data:
                gz.write(data)
                gz.write(pad4(len(data)))
            ino += 1

        trailer = b"TRAILER!!!\x00"
        hdr = make_header(0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(trailer))
        gz.write(hdr)
        gz.write(trailer)
        gz.write(pad4(len(hdr) + len(trailer)))


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <root_dir> <output.cpio.gz>", file=sys.stderr)
        return 2
    pack_dir(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
