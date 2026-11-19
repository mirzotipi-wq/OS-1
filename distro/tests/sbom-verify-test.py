#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 23: Strict CycloneDX 1.5 SBOM validator for OS-1.

Verifies:
  - CycloneDX 1.5 schema fields (bomFormat, specVersion, serialNumber, metadata)
  - linux-os1-kernel component is present with valid 64-hex SHA-256 hash
    (NEVER 'unknown') matching distro/out/kernel/provenance.json
  - Kernel config SHA-256 property is valid 64-hex and matches provenance.json
  - All 8 native OS-1 .deb packages are recorded with valid SHA-256 hashes
  - Supports --self-test for fast offline unit testing during os1.sh audit
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_ROOT = os.environ.get("OS1_OUT_DIR", os.path.join(REPO_ROOT, "distro", "out"))
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_OS1_PKGS = {
    "os1-release",
    "os1-keyring",
    "os1-branding",
    "os1-shell",
    "os1-firstboot",
    "os1-installer",
    "os1-tools",
    "os1-desktop-meta",
}


def validate_sbom(sbom_path: str, kernel_prov_path: str | None = None, require_iso: bool = False) -> None:
    if not os.path.isfile(sbom_path):
        raise RuntimeError(f"SBOM file not found: {sbom_path}")
    sbom = json.load(open(sbom_path, encoding="utf-8"))

    if sbom.get("bomFormat") != "CycloneDX":
        raise RuntimeError(f"Unexpected bomFormat: {sbom.get('bomFormat')!r}")
    if sbom.get("specVersion") != "1.5":
        raise RuntimeError(f"Unexpected specVersion: {sbom.get('specVersion')!r}")
    if not str(sbom.get("serialNumber", "")).startswith("urn:uuid:"):
        raise RuntimeError(f"Invalid serialNumber: {sbom.get('serialNumber')!r}")

    components = sbom.get("components") or []
    by_name = {c.get("name"): c for c in components}

    # 1. Kernel component must exist with real 64-hex SHA-256 (never 'unknown')
    kcomp = by_name.get("linux-os1-kernel")
    if not kcomp:
        raise RuntimeError("Missing linux-os1-kernel component in SBOM")
    khashes = {h.get("alg"): h.get("content") for h in (kcomp.get("hashes") or [])}
    bz_hash = khashes.get("SHA-256", "")
    if not HEX64_RE.match(bz_hash):
        raise RuntimeError(f"Invalid or unknown linux-os1-kernel SHA-256 hash: {bz_hash!r}")
    kprops = {p.get("name"): p.get("value") for p in (kcomp.get("properties") or [])}
    if kprops.get("os1:bzImage_sha256") != bz_hash:
        raise RuntimeError(f"os1:bzImage_sha256 property mismatch: {kprops.get('os1:bzImage_sha256')!r} != {bz_hash!r}")
    if not HEX64_RE.match(str(kprops.get("os1:config_sha256", ""))):
        raise RuntimeError(f"Invalid os1:config_sha256 property: {kprops.get('os1:config_sha256')!r}")

    if kernel_prov_path and os.path.isfile(kernel_prov_path):
        kp = json.load(open(kernel_prov_path, encoding="utf-8"))
        expected_bz = (kp.get("artifacts") or {}).get("bzImage", {}).get("sha256", "")
        expected_cfg = (kp.get("artifacts") or {}).get("config", {}).get("sha256", "")
        if expected_bz and bz_hash != expected_bz:
            raise RuntimeError(f"SBOM kernel hash {bz_hash} != provenance.json {expected_bz}")
        if expected_cfg and kprops.get("os1:config_sha256") != expected_cfg:
            raise RuntimeError(f"SBOM config hash {kprops.get('os1:config_sha256')} != provenance.json {expected_cfg}")

    # 2. All 8 native OS-1 .deb packages must exist with valid SHA-256 hashes
    missing_pkgs = sorted(REQUIRED_OS1_PKGS - set(by_name.keys()))
    if missing_pkgs:
        raise RuntimeError(f"Missing OS-1 native packages in SBOM: {missing_pkgs}")
    for pkg in sorted(REQUIRED_OS1_PKGS):
        ph = {h.get("alg"): h.get("content") for h in (by_name[pkg].get("hashes") or [])}
        if not HEX64_RE.match(str(ph.get("SHA-256", ""))):
            raise RuntimeError(f"Missing/invalid SHA-256 for {pkg} in SBOM: {ph!r}")

    # 3. Optional ISO component check
    if require_iso:
        iso_comps = [c for c in components if c.get("type") == "file" and str(c.get("name", "")).endswith(".iso")]
        if not iso_comps:
            raise RuntimeError("No .iso file component found in SBOM")
        for ic in iso_comps:
            ih = {h.get("alg"): h.get("content") for h in (ic.get("hashes") or [])}
            if not HEX64_RE.match(str(ih.get("SHA-256", ""))):
                raise RuntimeError(f"Invalid SHA-256 for ISO {ic.get('name')}: {ih!r}")


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="os1-sbom-selftest-") as tmp:
        kdir = os.path.join(tmp, "kernel")
        adir = os.path.join(tmp, "apt-repo")
        idir = os.path.join(tmp, "iso")
        os.makedirs(kdir)
        os.makedirs(adir)
        os.makedirs(idir)

        bz_sha = hashlib.sha256(b"synthetic-bzImage").hexdigest()
        cfg_sha = hashlib.sha256(b"synthetic-config").hexdigest()
        prov_path = os.path.join(kdir, "provenance.json")
        with open(prov_path, "w", encoding="utf-8") as f:
            json.dump({
                "kernel_release": "7.4.0-rc3-os1",
                "git_sha": "0" * 40,
                "compiler": "gcc-selftest",
                "artifacts": {
                    "bzImage": {"path": "distro/out/kernel/bzImage", "sha256": bz_sha},
                    "config": {"path": "distro/out/kernel/os1_x86_64.config", "sha256": cfg_sha},
                },
            }, f)

        for pkg in sorted(REQUIRED_OS1_PKGS):
            with open(os.path.join(adir, f"{pkg}_1.0.0~rc2-1_all.deb"), "wb") as f:
                f.write(f"dummy-{pkg}".encode("utf-8"))
        with open(os.path.join(idir, "os1-1.0-rc2-x86_64.iso"), "wb") as f:
            f.write(b"dummy-iso")

        env = os.environ.copy()
        env["OS1_OUT_DIR"] = tmp
        subprocess.check_call(
            [sys.executable, os.path.join(REPO_ROOT, "distro", "build", "generate-sbom.py")],
            env=env,
            stdout=subprocess.DEVNULL,
        )
        sbom_path = os.path.join(tmp, "release", "os1-sbom.cdx.json")
        validate_sbom(sbom_path, prov_path, require_iso=True)

        # Negative check: corrupt bzImage hash to 'unknown' and confirm validator rejects it
        data = json.load(open(sbom_path, encoding="utf-8"))
        for c in data["components"]:
            if c["name"] == "linux-os1-kernel":
                c["hashes"][0]["content"] = "unknown"
        with open(sbom_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        try:
            validate_sbom(sbom_path, prov_path, require_iso=True)
            raise AssertionError("Validator failed to reject 'unknown' kernel hash!")
        except RuntimeError:
            pass

    print("[PASS] SBOM generator & validator self-test passed (real SHA-256 enforced, 'unknown' rejected)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate OS-1 CycloneDX 1.5 SBOM")
    ap.add_argument("--sbom", default=os.path.join(OUT_ROOT, "release", "os1-sbom.cdx.json"))
    ap.add_argument("--kernel-provenance", default=os.path.join(OUT_ROOT, "kernel", "provenance.json"))
    ap.add_argument("--require-iso", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return run_self_test()

    validate_sbom(args.sbom, args.kernel_provenance, require_iso=args.require_iso)
    print(f"[PASS] OS-1 SBOM validated cleanly: {args.sbom}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
