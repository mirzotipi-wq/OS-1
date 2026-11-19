#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Phase 22: Automated kernel driver & module presence audit for OS-1.

Validates that every required built-in (=y) and modular/built-in (=y or =m)
driver symbol survived olddefconfig in os1_x86_64.config, optionally verifies
installed module trees under distro/out/kernel/modules, and emits a
machine-readable driver manifest (distro/out/kernel/driver-manifest.json).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_ROOT = os.environ.get("OS1_OUT_DIR", os.path.join(REPO_ROOT, "distro", "out"))

# Built-in (=y) required for deterministic boot, firewall, and early userspace
REQUIRED_BUILTIN = {
    "core": [
        "CONFIG_LOCALVERSION",
        "CONFIG_IKCONFIG",
        "CONFIG_IKCONFIG_PROC",
        "CONFIG_MODULES",
        "CONFIG_MODULE_UNLOAD",
        "CONFIG_EFI",
        "CONFIG_EFI_STUB",
        "CONFIG_BLK_DEV_INITRD",
        "CONFIG_FW_LOADER",
    ],
    "virtio_qemu": [
        "CONFIG_VIRTIO_PCI",
        "CONFIG_VIRTIO_BLK",
        "CONFIG_VIRTIO_NET",
        "CONFIG_VIRTIO_INPUT",
        "CONFIG_DRM_VIRTIO_GPU",
        "CONFIG_DRM_SIMPLEDRM",
    ],
    "storage_fs": [
        "CONFIG_SATA_AHCI",
        "CONFIG_BLK_DEV_NVME",
        "CONFIG_USB_XHCI_HCD",
        "CONFIG_USB_STORAGE",
        "CONFIG_EXT4_FS",
        "CONFIG_VFAT_FS",
        "CONFIG_ISO9660_FS",
        "CONFIG_SQUASHFS",
        "CONFIG_OVERLAY_FS",
    ],
    "firewall_netfilter": [
        "CONFIG_NETFILTER",
        "CONFIG_NF_CONNTRACK",
        "CONFIG_NF_TABLES",
        "CONFIG_NF_TABLES_INET",
        "CONFIG_NFT_COMPAT",
        "CONFIG_IP_NF_IPTABLES",
        "CONFIG_IP6_NF_IPTABLES",
    ],
    "power_tpm_hid": [
        "CONFIG_USB_HID",
        "CONFIG_ACPI_AC",
        "CONFIG_ACPI_BATTERY",
        "CONFIG_BACKLIGHT_CLASS_DEVICE",
        "CONFIG_TCG_TPM",
        "CONFIG_TCG_TIS",
        "CONFIG_TCG_CRB",
    ],
}

# Built-in or loadable module (=y or =m) required for physical x86-64 hardware readiness
REQUIRED_PRESENT = {
    "graphics_drm": [
        "CONFIG_DRM_I915",
        "CONFIG_DRM_AMDGPU",
        "CONFIG_DRM_NOUVEAU",
    ],
    "ethernet": [
        "CONFIG_E1000E",
        "CONFIG_IGB",
        "CONFIG_IGC",
        "CONFIG_R8169",
        "CONFIG_USB_NET_CDCETHER",
        "CONFIG_USB_RTL8152",
    ],
    "wifi": [
        "CONFIG_CFG80211",
        "CONFIG_MAC80211",
        "CONFIG_IWLWIFI",
        "CONFIG_IWLMVM",
        "CONFIG_ATH10K",
        "CONFIG_ATH10K_PCI",
        "CONFIG_ATH11K",
        "CONFIG_ATH11K_PCI",
        "CONFIG_RTW88",
        "CONFIG_RTW88_PCI",
    ],
    "audio": [
        "CONFIG_SND",
        "CONFIG_SND_HDA_INTEL",
        "CONFIG_SND_HDA_CODEC_REALTEK",
        "CONFIG_SND_HDA_CODEC_HDMI",
        "CONFIG_SND_USB_AUDIO",
    ],
    "bluetooth": [
        "CONFIG_BT",
        "CONFIG_BT_HCIBTUSB",
    ],
    "touchpad_input": [
        "CONFIG_HID_MULTITOUCH",
        "CONFIG_I2C_HID_ACPI",
        "CONFIG_I2C_DESIGNWARE_PLATFORM",
        "CONFIG_I2C_DESIGNWARE_PCI",
    ],
    "webcam": [
        "CONFIG_USB_VIDEO_CLASS",
    ],
}

# Key .ko basenames expected when --check-modules is enabled (for modular drivers)
EXPECTED_MODULE_BASENAMES = [
    "i915.ko",
    "amdgpu.ko",
    "nouveau.ko",
    "e1000e.ko",
    "r8169.ko",
    "iwlwifi.ko",
    "iwlmvm.ko",
    "snd-hda-intel.ko",
    "snd-usb-audio.ko",
    "btusb.ko",
    "uvcvideo.ko",
    "hid-multitouch.ko",
    "i2c-hid-acpi.ko",
]


def parse_kconfig(path: str) -> dict[str, str]:
    cfg: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit OS-1 kernel config and module driver coverage")
    ap.add_argument(
        "--config",
        default=os.path.join(OUT_ROOT, "kernel", "os1_x86_64.config"),
        help="Path to merged kernel .config",
    )
    ap.add_argument(
        "--modules-dir",
        default=os.path.join(OUT_ROOT, "kernel", "modules"),
        help="Path to installed kernel modules tree",
    )
    ap.add_argument(
        "--check-modules",
        action="store_true",
        help="Also verify compiled .ko files exist under --modules-dir",
    )
    ap.add_argument(
        "--manifest",
        default=os.path.join(OUT_ROOT, "kernel", "driver-manifest.json"),
        help="Path to write JSON driver manifest",
    )
    args = ap.parse_args()

    if not os.path.isfile(args.config):
        print(f"ERROR: Kernel config not found: {args.config}", file=sys.stderr)
        return 1

    cfg = parse_kconfig(args.config)
    failures: list[str] = []
    manifest_categories: dict[str, dict[str, str]] = {}

    for cat, syms in REQUIRED_BUILTIN.items():
        manifest_categories[cat] = {}
        for sym in syms:
            val = cfg.get(sym, "missing")
            manifest_categories[cat][sym] = val
            if sym == "CONFIG_LOCALVERSION":
                if "-os1" not in val:
                    failures.append(f"{cat}: {sym}={val} (expected to contain -os1)")
            elif val != "y":
                failures.append(f"{cat}: {sym}={val} (expected y)")

    for cat, syms in REQUIRED_PRESENT.items():
        manifest_categories[cat] = {}
        for sym in syms:
            val = cfg.get(sym, "missing")
            manifest_categories[cat][sym] = val
            if val not in ("y", "m"):
                failures.append(f"{cat}: {sym}={val} (expected y or m)")

    module_summary: dict[str, object] = {"checked": args.check_modules}
    if args.check_modules:
        found_kos: dict[str, str] = {}
        if os.path.isdir(args.modules_dir):
            for dirpath, _, filenames in os.walk(args.modules_dir):
                for fn in filenames:
                    base = fn
                    for ext in (".zst", ".xz", ".gz"):
                        if base.endswith(ext):
                            base = base[: -len(ext)]
                    if base.endswith(".ko"):
                        found_kos[base] = os.path.relpath(os.path.join(dirpath, fn), args.modules_dir)
        missing_kos = [ko for ko in EXPECTED_MODULE_BASENAMES if ko not in found_kos]
        module_summary["total_ko_files"] = len(found_kos)
        module_summary["verified_key_modules"] = {
            ko: found_kos.get(ko, "MISSING") for ko in EXPECTED_MODULE_BASENAMES
        }
        if len(found_kos) == 0:
            failures.append(f"modules: zero .ko files found under {args.modules_dir}")
        for ko in missing_kos:
            failures.append(f"modules: expected module {ko} missing under {args.modules_dir}")

    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config_path": os.path.relpath(args.config, REPO_ROOT)
        if args.config.startswith(REPO_ROOT)
        else args.config,
        "categories": manifest_categories,
        "modules": module_summary,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    os.makedirs(os.path.dirname(args.manifest), exist_ok=True)
    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    if failures:
        print(f"[os1-driver-audit] FAILED ({len(failures)} issues):", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1

    total_syms = sum(len(v) for v in manifest_categories.values())
    extra = f", {module_summary.get('total_ko_files')} .ko modules" if args.check_modules else ""
    print(f"[os1-driver-audit] PASSED ({total_syms} driver symbols verified{extra}) -> {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
