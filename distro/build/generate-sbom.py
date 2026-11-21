#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 14 / 23: Generate a CycloneDX 1.5 JSON SBOM for an OS-1 release build.

Combines:
  - OS-1 kernel provenance (distro/out/kernel/provenance.json)
  - Native OS-1 .deb packages (distro/out/apt-repo/*.deb)
  - Installed Debian userspace packages (distro/out/images/rootfs-packages.tsv)
  - Generated UEFI Live ISO (distro/out/iso/*.iso)
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


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

    components: list[dict[str, object]] = []

    kernel_prov = os.path.join(out_root, "kernel", "provenance.json")
    if os.path.isfile(kernel_prov):
        kp = json.load(open(kernel_prov, encoding="utf-8"))
        artifacts = kp.get("artifacts") or {}
        bz_info = artifacts.get("bzImage") or {}
        cfg_info = artifacts.get("config") or {}
        bz_sha = bz_info.get("sha256") or kp.get("bzImage_sha256") or ""
        cfg_sha = cfg_info.get("sha256") or ""

        if not HEX64_RE.match(bz_sha):
            bz_path = os.path.join(out_root, "kernel", "bzImage")
            if os.path.isfile(bz_path):
                bz_sha = sha256_file(bz_path)
        if not HEX64_RE.match(cfg_sha):
            cfg_path = os.path.join(out_root, "kernel", "os1_x86_64.config")
            if os.path.isfile(cfg_path):
                cfg_sha = sha256_file(cfg_path)

        if not HEX64_RE.match(bz_sha):
            print(
                f"ERROR: Missing or invalid bzImage SHA-256 in {kernel_prov}: {bz_sha!r}",
                file=sys.stderr,
            )
            return 1
        if not HEX64_RE.match(cfg_sha):
            print(
                f"ERROR: Missing or invalid kernel config SHA-256 in {kernel_prov}: {cfg_sha!r}",
                file=sys.stderr,
            )
            return 1

        krel = kp.get("kernel_release", "")
        if not krel:
            print(f"ERROR: Missing kernel_release in {kernel_prov}", file=sys.stderr)
            return 1

        components.append({
            "type": "operating-system",
            "name": "linux-os1-kernel",
            "version": krel,
            "licenses": [{"license": {"id": "GPL-2.0-only"}}],
            "hashes": [{"alg": "SHA-256", "content": bz_sha}],
            "purl": f"pkg:generic/linux-os1-kernel@{krel}",
            "properties": [
                {"name": "os1:git_sha", "value": kp.get("git_sha", "")},
                {"name": "os1:bzImage_sha256", "value": bz_sha},
                {"name": "os1:config_sha256", "value": cfg_sha},
                {"name": "os1:compiler", "value": kp.get("compiler", "")},
            ],
        })

    os1_pkg_names: set[str] = set()
    apt_repo = os.path.join(out_root, "apt-repo")
    if os.path.isdir(apt_repo):
        for fname in sorted(os.listdir(apt_repo)):
            if not fname.endswith(".deb"):
                continue
            fpath = os.path.join(apt_repo, fname)
            parts = fname.split("_")
            pkg_name = parts[0]
            pkg_ver = parts[1] if len(parts) > 1 else "1.0.0"
            os1_pkg_names.add(pkg_name)
            components.append({
                "type": "application",
                "name": pkg_name,
                "version": pkg_ver,
                "licenses": [{"license": {"id": "GPL-2.0-only"}}],
                "hashes": [{"alg": "SHA-256", "content": sha256_file(fpath)}],
                "purl": f"pkg:deb/os1/{pkg_name}@{pkg_ver}",
            })

    iso_dir = os.path.join(out_root, "iso")
    if os.path.isdir(iso_dir):
        for fname in sorted(os.listdir(iso_dir)):
            if not fname.endswith(".iso"):
                continue
            fpath = os.path.join(iso_dir, fname)
            components.append({
                "type": "file",
                "name": fname,
                "version": fname.replace(".iso", ""),
                "hashes": [{"alg": "SHA-256", "content": sha256_file(fpath)}],
            })

    pkg_tsv = os.path.join(out_root, "images", "rootfs-packages.tsv")
    if os.path.isfile(pkg_tsv):
        with open(pkg_tsv, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) < 3:
                    continue
                name, ver, arch = parts[0], parts[1], parts[2]
                if name in os1_pkg_names:
                    continue
                components.append({
                    "type": "library",
                    "name": name,
                    "version": ver,
                    "purl": f"pkg:deb/debian/{name}@{ver}?arch={arch}",
                })

    git_sha = subprocess.check_output(
        ["git", "-C", repo_root, "rev-parse", "HEAD"], text=True
    ).strip()

    version_meta: dict[str, str] = {}
    ver_file = os.path.join(repo_root, "distro", "VERSION")
    if os.path.isfile(ver_file):
        with open(ver_file, encoding="utf-8") as vf:
            for line in vf:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                version_meta[k.strip()] = v.strip().strip('"').strip("'")

    meta_props = [
        {"name": "os1:git_sha", "value": git_sha},
        {"name": "os1:debian_suite", "value": version_meta.get("OS1_DEBIAN_SUITE", "bookworm")},
        {"name": "os1:deb_version", "value": version_meta.get("OS1_DEB_VERSION", "1.0.0~rc2-1")},
    ]
    sde = os.environ.get("SOURCE_DATE_EPOCH")
    if sde:
        meta_props.append({"name": "os1:source_date_epoch", "value": sde})

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "operating-system",
                "name": version_meta.get("OS1_NAME", "OS-1"),
                "version": version_meta.get("OS1_VERSION", "1.0-rc2"),
                "properties": meta_props,
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
