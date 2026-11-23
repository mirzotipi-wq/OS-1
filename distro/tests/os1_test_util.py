#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Shared test utilities for OS-1 verification suites."""

from __future__ import annotations

import json
import os


def expected_kernel_release(repo_root: str, out_root: str | None = None) -> str:
    """Resolve the expected OS-1 kernel release from provenance.json or KERNEL_LTS.env."""
    if out_root is None:
        out_root = os.environ.get("OS1_OUT_DIR", os.path.join(repo_root, "distro", "out"))
    prov_path = os.path.join(out_root, "kernel", "provenance.json")
    if os.path.isfile(prov_path):
        try:
            data = json.load(open(prov_path, encoding="utf-8"))
            krel = str(data.get("kernel_release", "")).strip()
            if krel:
                return krel
        except Exception:
            pass

    lts_env = os.path.join(repo_root, "distro", "kernel", "KERNEL_LTS.env")
    if os.path.isfile(lts_env):
        with open(lts_env, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OS1_KERNEL_VERSION="):
                    ver = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if ver:
                        return f"{ver}-os1"
    return "6.12.119-os1"
