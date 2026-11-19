#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 14: Generate a CycloneDX 1.5 JSON SBOM for an OS-1 release build.

Combines:
  - OS-1 kernel provenance (distro/out/kernel/provenance.json)
  - Installed Debian userspace packages (distro/out/images/rootfs-packages.tsv)
  - Native OS-1 .deb packages (distro/out/apt-repo/*.deb)
  - Optional ISO provenance (distro/out/iso/iso-provenance.json)
"""

import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_root = os.environ.get("OS1_OUT_DIR", os.path.join(repo_root, "distro", "out"))
    release_dir = os.path.join(out_root, "release")
    os.makedirs(release_dir, exist_ok=True)

    components = []

    kernel_prov = os.path.join(out_root, "kernel", "provenance.json")
    if os.path.isfile(kernel_prov):
        kp = json.load(open(kernel_prov, encoding="utf-8"))
        components.append({
            "type": "operating-system",
            "name": "linux-os1-kernel",
            "version": kp.get("kernel_release", "7.4.0-rc3-os1"),
            "licenses": [{"license": {"id": "GPL-2.0-only"}}],
            "purl": f"pkg:generic/linux-os1-kernel@{kp.get('kernel_release', '7.4.0-rc3-os1')}",
            "properties": [
                {"name": "os1:git_sha", "value": kp.get("git_sha", "unknown")},
                {"name": "os1:bzImage_sha256", "value": kp.get("bzImage_sha256", "unknown")},
            ],
        })

    apt_repo = os.path.join(out_root, "apt-repo")
    if os.path.isdir(apt_repo):
        for fname in sorted(os.listdir(apt_repo)):
            if not fname.endswith(".deb"):
                continue
            fpath = os.path.join(apt_repo, fname)
            pkg_name = fname.split("_")[0]
            pkg_ver = fname.split("_")[1] if len(fname.split("_")) > 1 else "1.0.0"
            components.append({
                "type": "application",
                "name": pkg_name,
                "version": pkg_ver,
                "licenses": [{"license": {"id": "GPL-2.0-only"}}],
                "hashes": [{"alg": "SHA-256", "content": sha256_file(fpath)}],
                "purl": f"pkg:deb/os1/{pkg_name}@{pkg_ver}",
            })

    pkg_tsv = os.path.join(out_root, "images", "rootfs-packages.tsv")
    if os.path.isfile(pkg_tsv):
        with open(pkg_tsv, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) < 3:
                    continue
                name, ver, arch = parts[0], parts[1], parts[2]
                components.append({
                    "type": "library",
                    "name": name,
                    "version": ver,
                    "purl": f"pkg:deb/debian/{name}@{ver}?arch={arch}",
                })

    git_sha = subprocess.check_output(
        ["git", "-C", repo_root, "rev-parse", "HEAD"], text=True
    ).strip()

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "operating-system",
                "name": "OS-1",
                "version": "1.0-rc1",
                "properties": [
                    {"name": "os1:git_sha", "value": git_sha},
                    {"name": "os1:debian_suite", "value": "bookworm"},
                ],
            },
        },
        "components": components,
    }

    sbom_path = os.path.join(release_dir, "os1-sbom.cdx.json")
    with open(sbom_path, "w", encoding="utf-8") as f:
        json.dump(sbom, f, indent=2)
        f.write("\n")

    print(f"[os1-sbom] Generated {sbom_path} ({len(components)} components)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
